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
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
from cgmes2pgm_converter.common import (
    APPLIANCE_COMPONENTS,
    BRANCH_COMPONENTS,
    CIM_ID_OBJ,
    CgmesDataset,
    Topology,
)
from power_grid_model import ComponentType

from cgmes2pgm_suite.state_estimation import PgmDataset

from .utils import CgmesFullModel


@dataclass
class TopologicalIsland:
    """Wrapper for the CIM TopologicalIsland object."""

    mrid: str
    iri: str
    name: str
    topological_nodes: list[str]
    angle_ref_node: Optional[str]

    def to_triples(self) -> list[tuple[str, str, str]]:
        """
        Convert the TopologicalIsland instance to RDF triples.

        Returns:
            list[tuple[str, str, str]]: List of RDF triples representing the TopologicalIsland
        """
        CLS = "cim:TopologicalIsland"
        triples = [
            (self.iri, "rdf:type", "cim:TopologicalIsland"),
            (self.iri, "cim:IdentifiedObject.mRID", f'"{self.mrid}"'),
            (self.iri, "cim:IdentifiedObject.name", f'"{self.name}"'),
        ]

        if self.angle_ref_node is not None:
            triples.append(
                (self.iri, f"{CLS}.angleRefTopologicalNode", f"<{self.angle_ref_node}>")
            )

        triples += [
            (self.iri, f"{CLS}.TopologicalNodes", f"<{node}>")
            for node in self.topological_nodes
        ]
        return triples


class SvProfileBuilder:
    """
    Generates the state variable (SV) profile for a provided power flow or state estimation result.

    Attributes:
        cgmes_dataset (CgmesDataset): The CGMES dataset to save the SV-profile to
        pgm_dataset (PgmDataset): The PGM dataset to convert to a state variable profile
        model_info (CgmesFullModel): The model information to include in the SV-profile
        target_graph (str): The name of the target graph to write the SV-profile to
    """

    def __init__(
        self,
        cgmes_dataset: CgmesDataset,
        pgm_dataset: PgmDataset,
        target_graph: str,
        model_info: CgmesFullModel | None = None,
    ):
        self.cgmes_dataset = cgmes_dataset
        self.pgm_dataset = pgm_dataset
        self.target_graph = target_graph
        self.model_info = model_info or CgmesFullModel(
            profile="http://entsoe.eu/CIM/StateVariables/4/1"
        )

    def build(self, overwrite_existing: bool = False):
        """
        Write the SV-profile to the CGMES dataset.
        """

        if overwrite_existing:
            self.cgmes_dataset.drop_graph(self.target_graph)

        if not self.pgm_dataset.result_data:
            return

        self._write_model_info()
        self._write_sv_voltage()
        self._write_power_flow()
        self._add_topological_islands()

    def _write_sv_voltage(self):
        """Create SvVoltage objects"""

        CLS = "cim:SvVoltage"

        if not self.pgm_dataset.result_data:
            return

        node_results = self.pgm_dataset.result_data[ComponentType.node]

        df = pd.DataFrame()
        df["_pgm_id"] = node_results["id"]
        df["rdf:type"] = CLS

        df[f"{CLS}.v"] = node_results["u"] / 1e3
        df[f"{CLS}.angle"] = np.rad2deg(node_results["u_angle"])
        df[f"{CIM_ID_OBJ}.mRID"] = [f'"{uuid.uuid4()}"' for _ in range(len(df))]

        df[f"{CLS}.TopologicalNode"] = None
        for idx, row in df.iterrows():
            node_id = row["_pgm_id"]
            toponode_iri = self.pgm_dataset.extra_info.get(node_id, {}).get(
                "_mrid", None
            )
            df.at[idx, f"{CLS}.TopologicalNode"] = (
                f"<{toponode_iri}>" if toponode_iri else None
            )

        # drop rows without TopologicalNode and log node ids w/o TopologicalNode
        missing_toponode = df[df[f"{CLS}.TopologicalNode"].isnull()]["_pgm_id"].tolist()
        if missing_toponode:
            logging.warning("Nodes without TopologicalNode: %s", missing_toponode)
        df = df[df[f"{CLS}.TopologicalNode"].notnull()]

        df.drop(columns=["_pgm_id"], inplace=True)

        self.cgmes_dataset.insert_df(
            df,
            self.target_graph,
            include_mrid=True,
        )

    def _write_power_flow(self):
        """Create SvPowerFlow objects"""

        if not self.pgm_dataset.result_data:
            return

        for type_ in BRANCH_COMPONENTS:
            if type_ in self.pgm_dataset.result_data:
                self._add_branch_flows(type_)

        for type_ in APPLIANCE_COMPONENTS:
            if type_ in self.pgm_dataset.result_data:
                self._add_appliance_flows(type_)

    def _add_branch_flows(self, type_: ComponentType):
        """Add generic branch flows to the DataFrame."""

        if not self.pgm_dataset.result_data:
            return

        CLS = "cim:SvPowerFlow"

        result_data = self.pgm_dataset.result_data[type_]

        for direction in ["from", "to"]:

            df = pd.DataFrame()
            df["_pgm_id"] = result_data["id"]
            df["rdf:type"] = CLS
            df[f"{CLS}.p"] = result_data[f"p_{direction}"] / 1e6
            df[f"{CLS}.q"] = result_data[f"q_{direction}"] / 1e6
            df[f"{CIM_ID_OBJ}.mRID"] = [f'"{uuid.uuid4()}"' for _ in range(len(df))]

            terminal_number = 1 if direction == "from" else 2
            terminal_key = f"_term{terminal_number}"
            df[f"{CLS}.Terminal"] = df["_pgm_id"].apply(
                lambda pid, terminal_key=terminal_key: self._get_terminal_from_extra_info(
                    pid, terminal_key
                )
            )

            missing_term = df[df[f"{CLS}.Terminal"].isnull()]["_pgm_id"].tolist()
            if missing_term:
                logging.warning(
                    "Branches without Terminal (%s): %s", direction, missing_term
                )
            df.dropna(subset=[f"{CLS}.Terminal"], inplace=True)
            df.drop(columns=["_pgm_id"], inplace=True)

            self.cgmes_dataset.insert_df(
                df,
                self.target_graph,
                include_mrid=True,
            )

    def _add_appliance_flows(self, type_: ComponentType):
        """Add appliance flows to the DataFrame."""

        if not self.pgm_dataset.result_data:
            return

        CLS = "cim:SvPowerFlow"

        df = pd.DataFrame()
        result_data = self.pgm_dataset.result_data[type_]

        df["_pgm_id"] = result_data["id"]
        df["rdf:type"] = CLS
        df[f"{CLS}.p"] = result_data["p"] / 1e6
        df[f"{CLS}.q"] = result_data["q"] / 1e6
        df[f"{CIM_ID_OBJ}.mRID"] = [f'"{uuid.uuid4()}"' for _ in range(len(df))]

        df[f"{CLS}.Terminal"] = df["_pgm_id"].apply(
            lambda pid: self._get_terminal_from_extra_info(pid, "_terminal")
        )

        missing_term_from = df[df[f"{CLS}.Terminal"].isnull()]["_pgm_id"].tolist()
        if missing_term_from:
            logging.warning("Appliance without Terminal: %s", missing_term_from)

        df.dropna(subset=[f"{CLS}.Terminal"], inplace=True)
        df.drop(columns=["_pgm_id"], inplace=True)

        self.cgmes_dataset.insert_df(
            df,
            self.target_graph,
            include_mrid=True,
        )

    def _add_topological_islands(self):

        subnets = self._get_islands()

        for subnet in subnets:
            self.cgmes_dataset.insert_triples(subnet.to_triples(), self.target_graph)

    def _get_islands(self) -> list[TopologicalIsland]:

        if not self.pgm_dataset.result_data:
            return []

        topology = Topology(
            self.pgm_dataset.input_data,
            self.pgm_dataset.extra_info,
            self.pgm_dataset.result_data,
        )
        topology.add_results(self.pgm_dataset.result_data)

        nodes = topology.get_nodes()
        nodes_per_subnet: dict[str, list] = {}
        ref_node_per_subnet: dict[str, str | None] = {}
        subnet_energized: dict[str, bool] = {}

        for node in nodes:
            node_mrid = node["_extra"]["_mrid"]
            subnet_name = node["_subnet"]

            if subnet_name not in nodes_per_subnet:
                nodes_per_subnet[subnet_name] = []
                subnet_energized[subnet_name] = bool(node["_result"]["energized"])

            nodes_per_subnet[subnet_name].append(node_mrid)

            if self._has_active_source(node, topology):
                # CIM only allows one source per subnet.
                # If there are multiple nodes with active sources, no angleRef node is set.
                if subnet_name in ref_node_per_subnet:
                    ref_node_per_subnet[subnet_name] = None
                    continue

                ref_node_per_subnet[subnet_name] = node["_extra"]["_mrid"]

        return self._create_topological_islands(
            nodes_per_subnet, ref_node_per_subnet, subnet_energized
        )

    def _create_topological_islands(
        self,
        nodes_per_subnet: dict[str, list],
        ref_node_per_subnet: dict[str, str | None],
        subnet_energized: dict[str, bool],
    ) -> list[TopologicalIsland]:
        islands = []
        for subnet_name, node_mrids in nodes_per_subnet.items():

            if not subnet_energized.get(subnet_name, False):
                continue

            mrid = str(uuid.uuid4())
            islands.append(
                TopologicalIsland(
                    mrid=mrid,
                    iri=self.cgmes_dataset.mrid_to_uri(mrid),
                    name=subnet_name,
                    topological_nodes=node_mrids,
                    angle_ref_node=ref_node_per_subnet.get(subnet_name, None),
                )
            )
        return islands

    def _has_active_source(
        self, node: dict[str | ComponentType, Any], topology: Topology
    ) -> bool:
        """Check if a node has one or multiple active sources."""

        sources = node.get(ComponentType.source, [])
        for source_id in sources:
            source = topology[source_id].get(ComponentType.source, {})
            if source["status"]:
                return True
        return False

    def _write_model_info(self):
        """Write model information to the CGMES dataset."""

        self.cgmes_dataset.insert_triples(
            self.model_info.to_triples(), self.target_graph
        )

    def _get_terminal_from_extra_info(self, pgm_id, terminal_key):
        """Get the terminal IRI from the extra info of the PGM dataset."""
        terminal_iri = self.pgm_dataset.extra_info.get(pgm_id, {}).get(terminal_key)
        return f"<{terminal_iri}>" if terminal_iri else None
