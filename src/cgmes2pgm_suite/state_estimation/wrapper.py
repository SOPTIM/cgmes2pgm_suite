# Copyright [2025] [SOPTIM AG]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

import numpy as np
from cgmes2pgm_converter.common import Timer, Topology
from power_grid_model import (
    CalculationMethod,
    CalculationType,
    ComponentType,
    PowerGridModel,
)
from power_grid_model.errors import IterationDiverge, SparseMatrixError
from power_grid_model.validation import validate_input_data
from power_grid_model_io.data_types import ExtraInfo

from .extract_subnet import connect_branch, extract_subnet_from_input_data
from .options import StesOptions
from .results import StateEstimationResult


class StateEstimationWrapper:
    def __init__(
        self,
        input_data: dict[str, np.ndarray],
        extra_info: ExtraInfo,
        stes_options: StesOptions = None,
        network_name: str = "network",
    ):
        self.input_data = input_data
        self.extra_info = extra_info
        self.stes_options = stes_options or StesOptions()
        self.network_name = network_name
        self._model: PowerGridModel = None
        self._results: list[StateEstimationResult] = []

        self._topology = Topology(self.input_data, self.extra_info)

    def run(self) -> list[StateEstimationResult] | StateEstimationResult:
        """Run state estimation on the input data.

        Returns:
            list[StateEstimationResult]: List of state estimation results.
                Multiple results if subnets are computed separately.
        """
        input_errors = validate_input_data(
            input_data=self.input_data,
            calculation_type=CalculationType.state_estimation,
            symmetric=True,
        )
        if input_errors:
            raise ValueError("Validation Errors: " + str(input_errors))

        if self.stes_options.compute_islands_separately:
            self._run_subnets_separately()
        else:
            self._single_run()
            if self.stes_options.reconnect_branches:
                self._reconnect_branches()

        if len(self._results) == 1:
            return self._results[0]

        return self._results

    def _single_run(self):
        self._model = PowerGridModel(self.input_data)
        try:
            self._run_pgm(self.network_name)
        except (SparseMatrixError, IterationDiverge) as e:
            logging.error(
                "\tState Estimation failed: %s", str(e).split("\n", maxsplit=1)[0]
            )

    def _run_subnets_separately(self):
        sources = self.input_data[ComponentType.source]
        finished_subnets = set()

        for i in range(sources.shape[0]):

            node = sources["node"][i]
            topo_node = self._topology.get_topology()[node]
            subnet = topo_node.get("_subnet")

            if subnet in finished_subnets:
                continue

            allowed_subnets = self.stes_options.compute_only_subnets
            if allowed_subnets and subnet not in allowed_subnets:
                continue

            finished_subnets.add(subnet)
            logging.info(
                "Running state estimation with slack at node %s in substation %s in subnet %s",
                node,
                topo_node["_extra"].get("_substation"),
                subnet,
            )

            sub_input_data = extract_subnet_from_input_data(
                self.input_data, self.extra_info, subnet
            )
            self._model = PowerGridModel(sub_input_data)

            try:
                self._run_pgm(f"sub_{subnet}")
                logging.info("\tState Estimation for subnet %s successful", subnet)
            except (SparseMatrixError, IterationDiverge) as e:
                logging.error(
                    "\tState Estimation for subnet %s failed: %s",
                    subnet,
                    str(e).split("\n", maxsplit=1)[0],
                )

    def _run_pgm(self, run_name: str):
        params = self.stes_options.pgm_parameters
        try:
            with Timer("State Estimation", loglevel=logging.INFO):
                result = self._model.calculate_state_estimation(
                    calculation_method=CalculationMethod.newton_raphson,
                    max_iterations=params.max_iterations,
                    error_tolerance=params.error_tolerance,
                    threading=params.threads,
                    symmetric=True,
                )
            self._results.append(
                StateEstimationResult(
                    run_name, self.input_data, self.extra_info, result, params
                )
            )
        except (SparseMatrixError, IterationDiverge) as e:
            self._results.append(
                StateEstimationResult(
                    run_name,
                    self.input_data,
                    self.extra_info,
                    None,
                    params,
                )
            )
            raise e

    def _reconnect_branches(self):
        """Consecutively reconnect previously disabled branches
        and run STES on the resulting subnets.

        Find branches of type `line` and `generic_branch` and try to reconnect them.
        Only branches that were previously disabled by Network Splitting
        will be processed this way.
        The reconnection is done by disabling the sources and enabling
        the branch again.

        The connection of the branch results in a new subnet, which is then used
        as input for the STES.
        If the STES converges, then the next branch is processed.
        If the STES does not converge, the branch is disabled again and its name is stored in list.

        Then the next branch is processed. This continues until all branches have been processed.

        At the end the list of branches that could not be connected is printed.
        This list can be used in the configuration file to be disabled,
        so that the STES can be computed successfully on the maximum size subnet.
        """
        # TODO: Split this function

        main_topo = Topology(self.input_data, self.extra_info)
        all_branches = [
            b
            for b in main_topo.get_topology().values()
            if b.get(ComponentType.line) is not None
            or b.get(ComponentType.generic_branch) is not None
        ]
        cuttable_branches = [
            b
            for b in all_branches
            if b["_extra"].get("source1") is not None
            and b["_extra"].get("source2") is not None
        ]

        ignore_branches = set()
        connected_substations = set()
        connect_counter = 0
        total_counter = 0
        current_topo = main_topo

        for topo_item in cuttable_branches:
            total_counter += 1

            line_name = topo_item["_extra"]["_name"]
            pgm_branch = topo_item.get(ComponentType.line)

            if pgm_branch is None:
                pgm_branch = topo_item[ComponentType.generic_branch]

            pgm_id = pgm_branch["id"]
            if pgm_id in ignore_branches:
                logging.warning("Skipping line %s", line_name)
                continue

            connected = connect_branch(topo_item, current_topo, connect=True)

            from_subnet_before = current_topo[pgm_branch["from_node"]]["_subnet"]
            to_subnet_before = current_topo[pgm_branch["to_node"]]["_subnet"]

            if not connected:
                logging.warning(
                    "Branch '%s' cannot be connected, skipping it",
                    line_name,
                )
                continue

            from_substation = current_topo[pgm_branch["from_node"]]["_extra"][
                "_substation"
            ]
            to_substation = current_topo[pgm_branch["to_node"]]["_extra"]["_substation"]

            current_topo = Topology(self.input_data, self.extra_info)
            subg = current_topo.get_topology_subnets().get_subnets()

            from_subnet_after = current_topo[pgm_branch["from_node"]]["_subnet"]
            to_subnet_after = current_topo[pgm_branch["to_node"]]["_subnet"]
            if from_subnet_after != to_subnet_after:
                logging.warning(
                    "Branch '%s' connects different subnets '%s' and '%s'",
                    line_name,
                    from_subnet_after,
                    to_subnet_after,
                )
                continue

            current_subs = set()
            for ii in range(1, len(subg) + 1):
                current_subs.add(f"subnet_{ii}")

            logging.info(
                "#%d / %d / %d: Connecting subnets '%s' and '%s' with line '%s' (subnets=%d)",
                connect_counter,
                total_counter,
                len(cuttable_branches),
                from_subnet_before,
                to_subnet_before,
                line_name,
                len(subg),
            )

            sub = from_subnet_after
            sub_input_data = extract_subnet_from_input_data(
                self.input_data, self.extra_info, sub
            )

            self._model = PowerGridModel(sub_input_data)
            try:
                self._run_pgm(f"{total_counter}_add_{line_name}")

                connect_counter += 1
                connected_substations.add(from_substation)
                connected_substations.add(to_substation)
            except (SparseMatrixError, IterationDiverge) as _:
                ignore_branches.add(pgm_id)
                connect_branch(topo_item, current_topo, connect=False)

        ignored_branch_names = [
            main_topo[_id]["_extra"]["_name"] for _id in ignore_branches
        ]
        ignored_branch_names.sort()

        connected_substation_names = list(connected_substations)
        connected_substation_names.sort()

        self.print_in_columns("Ingored branches", ignored_branch_names, 4)
        self.print_in_columns("Connected substations", connected_substation_names, 8)

    def print_in_columns(self, title: str, data: list[str], columns: int):

        if len(data) == 0:
            return

        max_len = max(len(s) for s in data)
        col_width = max_len + 4
        print(f"  {title}:")
        print("-" * (col_width * columns))
        for i in range(0, len(data), columns):
            print(
                "".join(
                    [f"{'"' + s + '",':<{col_width}}" for s in data[i : i + columns]]
                )
            )
