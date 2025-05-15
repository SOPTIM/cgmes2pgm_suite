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

from enum import Enum

from cgmes2pgm_converter.common import CgmesDataset, Topology
from power_grid_model import ComponentType

from .utils.current_measurement import CurrentMeasurements
from .utils.sv_lookup import SvVoltageLookup


class AnalysisMode(Enum):
    MORE_THAN_ONE_MISSING = 1
    """Print any node that has more than one missing measurement.
    Multiple appliances without measurements are counted as one missing measurement.
    """

    MORE_THAN_TWO_MISSING = 2
    """Print any node that has more than two missing measurement.
    Multiple appliances without measurements are counted as one missing measurement.
    """

    VOLTAGE_MISSING = 3
    """Print any node that has no voltage sensor."""

    THREE_WINDING_TRANSFORMER = 4
    """Print any node that has a 3WT with more than one missing measurement."""

    ANY_POWER_MISSING = 5
    """Print any node that has more than one missing power measurement."""

    @staticmethod
    def from_string(mode: str):
        match mode.lower():
            case "more_than_one_missing":
                return AnalysisMode.MORE_THAN_ONE_MISSING
            case "more_than_two_missing":
                return AnalysisMode.MORE_THAN_TWO_MISSING
            case "voltage_missing":
                return AnalysisMode.VOLTAGE_MISSING
            case "three_winding_transformer":
                return AnalysisMode.THREE_WINDING_TRANSFORMER
            case "any_power_missing":
                return AnalysisMode.ANY_POWER_MISSING
            case _:
                raise ValueError(f"Unknown AnalysisMode: {mode}")


class NodeMeasurementStatistics:
    def __init__(
        self,
        node: dict,
        topology: Topology,
        current_measurements: CurrentMeasurements,
        sv_lookup: SvVoltageLookup,
    ):
        self.node = node
        self.topology = topology
        self._current_measurements = current_measurements
        self._sv_lookup = sv_lookup

        self.has_voltage = self.node.get("_sensor_v") is not None

        self.no_meas_branches, self.number_branches = self._get_no_meas_branches()
        self.no_meas_appliances, self.number_appliances = self._get_no_meas_appliances()

        self.sv_voltage, _ = self._sv_lookup.get_voltage(self.node["_extra"]["_mrid"])

    def _get_no_meas_branches(self):

        branch_ids = self.node.get("_branches", [])
        branches = [self.topology[branch_id] for branch_id in branch_ids]

        total_count = len(branches)

        filtered_branches = [
            branch
            for branch in branches
            if branch.get("_sensor_p_from") is None
            and branch.get("_sensor_p_to") is None
            and branch.get(ComponentType.three_winding_transformer)
            is None  # 3WTs need to be handled differently, since they connect to 3 nodes
            and branch.get(ComponentType.link) is None  # Links dont have measurements
        ]

        # Add three winding transformers that have zero or one measurement.
        # If there is just one measurement missing, the flow to the missing side
        # can be calculated based on the other two sides
        filtered_branches += [
            branch
            for branch in branches
            if branch.get(ComponentType.three_winding_transformer) is not None
            and (
                sum(
                    1
                    for sensor in ["_sensor_p_1", "_sensor_p_2", "_sensor_p_3"]
                    if branch.get(sensor) is None
                )
                >= 2
            )
        ]

        return filtered_branches, total_count

    def _get_no_meas_appliances(self):
        appliance_ids = []

        appliance_ids += self.node.get(ComponentType.sym_load, [])
        appliance_ids += self.node.get(ComponentType.sym_gen, [])
        appliance_ids += self.node.get(ComponentType.source, [])
        appliance_ids += self.node.get(ComponentType.shunt, [])

        appliances = [self.topology[appliance_id] for appliance_id in appliance_ids]
        total_count = len(appliances)

        appliances = [
            appliance for appliance in appliances if appliance.get("_sensor_p") is None
        ]

        return appliances, total_count

    def write(self, writer):

        writer.write(
            f"\tNode: {self.node["_extra"]['_name']} ({self.node["_extra"]['_mrid'].split("#")[-1]})\n"
        )
        writer.write(f"\t\tHas voltage sensor: {self.has_voltage}\n")
        writer.write(f"\t\tSV Voltage: {self.sv_voltage}\n")
        writer.write(
            f"\t\tBranches without measurements: {len(self.no_meas_branches)} von {self.number_branches}\n"
        )

        for branch in self.no_meas_branches:
            has_current_meas = self.has_current_meas(branch["_extra"]["_mrid"])
            writer.write(
                f"\t\t  - {branch["_extra"]['_name']}{'*' if has_current_meas else ''} ({branch["_extra"]['_type']})\n"
            )

        writer.write(
            f"\t\tNumber of appliances without measurements: {len(self.no_meas_appliances)} von {self.number_appliances}\n"
        )

        for appliance in self.no_meas_appliances:
            has_current_meas = self.has_current_meas(appliance["_extra"]["_mrid"])
            writer.write(
                f"\t\t  - {appliance["_extra"]['_name']}{'*' if has_current_meas else ''} ({appliance["_extra"]['_type']})\n"
            )

        writer.write("\n")

    def has_current_meas(self, pgm_mrid: str):

        splited_mrid = pgm_mrid.split(",")
        if len(splited_mrid) == 1:
            return self._current_measurements.has_current_meas(pgm_mrid)

        # _mrid may be a combination of equipment and terminal mrid
        # this is the case for 3WTs split into 3 generic branches
        # we want to check if there is a current-measurement at the current generic branch

        terminal_mrid = splited_mrid[1]
        return self._current_measurements.has_current_meas(terminal_mrid)


class MeasurementAnalyzer:

    def __init__(
        self,
        topology: Topology,
        datasource: CgmesDataset,
        mode: AnalysisMode = AnalysisMode.MORE_THAN_ONE_MISSING,
        exclude_110kv: bool = False,
    ):
        self._topology = topology
        self._datasource = datasource

        self._mode = mode
        self._exclude_110kv = exclude_110kv

        self._current_measurements = CurrentMeasurements(datasource)
        self._sv_lookup = SvVoltageLookup(datasource)

        self.node_statistics = self.build_node_measurement_statistics()
        self.filter_nodes()

    def build_node_measurement_statistics(self):

        nodes = self._topology.get_nodes()

        return [
            NodeMeasurementStatistics(
                node, self._topology, self._current_measurements, self._sv_lookup
            )
            for node in nodes
        ]

    def filter_nodes(self):

        def only_no_voltage(n: NodeMeasurementStatistics):
            return not n.has_voltage

        def just_3wts(n: NodeMeasurementStatistics):
            return (
                any(
                    branch["_extra"]["_type"] == "PowerTransformer-3W"
                    for branch in n.no_meas_branches
                )
                and n.node["_extra"].get("_type", "") == "PowerTransformer-3W-AuxNode"
            )

        def has_missing_measurements(n: NodeMeasurementStatistics):
            return len(n.no_meas_branches) + len(n.no_meas_appliances) > 0

        def remove_110kv(n: NodeMeasurementStatistics):
            return n.sv_voltage is None or n.sv_voltage > 120 or n.sv_voltage < 90

        def more_than_one_missing(n: NodeMeasurementStatistics):
            return len(n.no_meas_branches) + min(len(n.no_meas_appliances), 1) > 1

        def more_than_two_missing(n: NodeMeasurementStatistics):
            return len(n.no_meas_branches) + min(len(n.no_meas_appliances), 1) > 2

        mode_filters = {
            AnalysisMode.MORE_THAN_ONE_MISSING: [
                has_missing_measurements,
                more_than_one_missing,
            ],
            AnalysisMode.MORE_THAN_TWO_MISSING: [
                has_missing_measurements,
                more_than_two_missing,
            ],
            AnalysisMode.VOLTAGE_MISSING: [
                only_no_voltage,
            ],
            AnalysisMode.THREE_WINDING_TRANSFORMER: [
                more_than_one_missing,
                just_3wts,
            ],
            AnalysisMode.ANY_POWER_MISSING: [
                has_missing_measurements,
            ],
        }

        filters = mode_filters.get(self._mode, [])

        if self._exclude_110kv:
            filters.append(remove_110kv)

        for f in filters:
            self.node_statistics = list(filter(f, self.node_statistics))

    def write(self, writer):

        writer.write("Measurement Analysis\n")
        writer.write("\n====================================\n")

        writer.write(
            "\nHint: * indicates, that a branch without a power measurement has a current measurement\n"
        )

        self._write_statistics(writer)

        writer.write("\n====================================\n")

        # sort by substation
        self.node_statistics.sort(key=lambda n: str(n.node["_extra"]["_substation"]))
        last_substation = ""

        for node_stat in self.node_statistics:
            current_substation = str(node_stat.node["_extra"]["_substation"])

            if current_substation != last_substation:
                writer.write(f"\nSubstation: {current_substation}\n")
                last_substation = current_substation

            node_stat.write(writer)

    def _write_statistics(self, writer):
        writer.write(f"\nNodes without measurements: {len(self.node_statistics)}\n")

        # Per SV-Voltage Level
        writer.write("\nNodes per SV-Voltage Level\n")
        voltage_levels = [
            (360, 500),
            (200, 360),
            (100, 200),
            (0, 100),
        ]
        total = 0
        for low, high in voltage_levels:
            nodes = [
                n
                for n in self.node_statistics
                if n.sv_voltage is not None and low <= n.sv_voltage < high
            ]
            writer.write(f" - ({low}, {high}) {len(nodes)} nodes\n")
            total += len(nodes)

        writer.write(f" - Unknown Sv-Voltage {len(self.node_statistics) - total}\n")

    def _get_distinct_substations(self):
        return {str(n.node["_extra"]["_substation"]) for n in self.node_statistics}
