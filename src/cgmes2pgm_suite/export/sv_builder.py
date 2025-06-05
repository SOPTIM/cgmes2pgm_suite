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
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from cgmes2pgm_converter.common import CIM_ID_OBJ, CgmesDataset
from power_grid_model import ComponentType

from cgmes2pgm_suite.state_estimation import PgmDataset


def _format_current_time() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(sep="T")
        .replace("+00:00", "Z")
    )


@dataclass
class CgmesFullModel:
    """Represents the Model Header of an CGMES Profile.

    Attributes:
        profile (str): Profile Type (URN/URI)
            e. g. http://entsoe.eu/CIM/StateVariables/4/1
        iri (str): A unique identifier for the model. Typically an URN starting with "urn:uuid:".
        description (str): Description of the model (free text).
        version (int): Version of the model.
        modeling_authority_set (str): The authority that created the model.
        dependent_on (list[str]): FullModel URN/URIs of the dependent profiles.
        scenario_time (str): The time of the scenario in ISO 8601 format.
        created (str): The creation time of the model in ISO 8601 format.


    """

    profile: str
    iri: str = field(default_factory=lambda: f"urn:uuid:{uuid.uuid4()}")
    description: str = "Model"
    version: int = 1
    modeling_authority_set: str = "CGMES2PGM"
    dependent_on: list[str] = field(default_factory=list)
    scenario_time: str = field(default_factory=_format_current_time)
    created: str = field(default_factory=_format_current_time)

    def to_triples(self) -> list[tuple[str, str, str]]:
        """
        Convert the CgmesFullModel instance to RDF triples.

        Returns:
            list[tuple[str, str, str]]: A list of RDF triples representing the model.
        """

        prefix = "md:Model."
        type_ = "<http://iec.ch/TC57/61970-552/ModelDescription/1#FullModel>"

        formatted_iri = f"<{self.iri}>"

        return [
            (formatted_iri, "rdf:type", type_),
            (formatted_iri, f"{prefix}scenarioTime", f'"{self.scenario_time}"'),
            (formatted_iri, f"{prefix}created", f'"{self.created}"'),
            (formatted_iri, f"{prefix}description", f'"{self.description}"'),
            (formatted_iri, f"{prefix}version", f'"{self.version}"'),
            (formatted_iri, f"{prefix}profile", f'"{self.profile}"'),
            (
                formatted_iri,
                f"{prefix}modelingAuthoritySet",
                f'"{self.modeling_authority_set}"',
            ),
        ]


class SvProfileBuilder:
    """
    Generates the state variable (SV) profile for a provided power flow or state estimation result.

    Attributes:
        cgmes_dataset (CgmesDataset): The CGMES dataset to save the SV-profile to.
        pgm_dataset (PgmDataset): The PGM dataset to convert to a state variable profile.
        model_info (CgmesFullModel): The model information to include in the SV-profile.
        target_graph (str): The name of the target graph to write the SV-profile to.
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

    def _write_sv_voltage(self):
        """Create SvVoltage objects"""

        CLS = "cim:SvVoltage"

        if not self.pgm_dataset.result_data:
            return

        node_results = self.pgm_dataset.result_data[ComponentType.node]

        df = pd.DataFrame()
        df["_pgm_id"] = node_results["id"]

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
            print(f"Nodes without TopologicalNode: {missing_toponode}")
        df = df[df[f"{CLS}.TopologicalNode"].notnull()]

        # drop _pgm_id column
        df.drop(columns=["_pgm_id"], inplace=True)

        self.cgmes_dataset.insert_df(
            df,
            self.target_graph,
            include_mrid=True,
        )

    def _write_power_flow(self):
        """Create SvPowerFlow objects"""
        pass

    def _write_model_info(self):
        """Write model information to the CGMES dataset."""

        self.cgmes_dataset.insert_triples(
            self.model_info.to_triples(), self.target_graph
        )
