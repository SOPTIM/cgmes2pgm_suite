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

import numpy as np
import pandas as pd
from cgmes2pgm_converter.common import CgmesDataset
from power_grid_model import ComponentType

from cgmes2pgm_suite.export.utils import convert_dataframe
from cgmes2pgm_suite.state_estimation import StateEstimationResult

from .abstract_result_sheet_writer import AbstractResultSheetWriter


class SvVoltageCompWriter(AbstractResultSheetWriter):

    def __init__(
        self,
        writer: pd.ExcelWriter,
        sheet_name: str,
        stes_result: StateEstimationResult,
        datasource: CgmesDataset,
    ):
        super().__init__(writer, sheet_name, stes_result)
        self.datasource = datasource

    def write(self):

        df = pd.DataFrame()

        df["id"] = self._stes_result.data["node"]["id"]
        df["u_pgm"] = self._stes_result.data["node"]["u"]
        df["u_angle_pgm"] = self._stes_result.data["node"]["u_angle"]

        df["iri"] = [self._stes_result.extra_info[x]["_mrid"] for x in df["id"]]

        self.add_sv_data(df)

        df["u_delta"] = df["u_pgm"] - df["u_sv"]
        df["u_angle_delta"] = df["u_angle_pgm"] - df["u_angle_sv"]

        # rearrange columns
        df = df[
            [
                "id",
                "u_pgm",
                "u_sv",
                "u_delta",
                "u_angle_pgm",
                "u_angle_sv",
                "u_angle_delta",
                "iri",
            ]
        ]

        df = convert_dataframe(df)

        self._write_df(df, self._writer)

    def add_sv_data(self, df: pd.DataFrame):

        _query_voltage = """
                SELECT ?tn ?u ?angle
                WHERE {
                    ?_sv a cim:SvVoltage;
                        cim:SvVoltage.v ?u;
                        cim:SvVoltage.angle ?angle;
                        cim:SvVoltage.TopologicalNode ?tn.
                }
            """
        query_result = self.datasource.query(_query_voltage)

        query_result["u"] *= 1000
        query_result["angle"] = np.deg2rad(query_result["angle"])

        u_sv = []
        angle_sv = []
        for x in df["iri"]:

            sv_voltage = query_result[query_result["tn"] == x]

            if len(sv_voltage) > 0:
                u_sv.append(sv_voltage["u"].values[0])
                angle_sv.append(sv_voltage["angle"].values[0])
            else:
                u_sv.append(None)
                angle_sv.append(None)

        df["u_sv"] = u_sv
        df["u_angle_sv"] = angle_sv


class SvFlowCompWriter(AbstractResultSheetWriter):

    def __init__(
        self,
        writer: pd.ExcelWriter,
        sheet_name: str,
        stes_result: StateEstimationResult,
        datasource: CgmesDataset,
    ):
        super().__init__(writer, sheet_name, stes_result)
        self.datasource = datasource

    def write(self):

        df = pd.DataFrame()

        # Merge all branches
        branch_types = [
            ComponentType.line,
            ComponentType.generic_branch,
            ComponentType.link,
            ComponentType.transformer,
        ]

        for branch_type in branch_types:

            if (
                branch_type not in self._stes_result.data
                or len(self._stes_result.data[branch_type]["id"]) == 0
            ):
                continue

            type_df = pd.DataFrame()
            type_df["id"] = self._stes_result.data[branch_type]["id"]
            type_df["on"] = self._stes_result.data[branch_type]["energized"]
            type_df["p_from_pgm"] = self._stes_result.data[branch_type]["p_from"]
            type_df["q_from_pgm"] = self._stes_result.data[branch_type]["q_from"]
            type_df["p_to_pgm"] = self._stes_result.data[branch_type]["p_to"]
            type_df["q_to_pgm"] = self._stes_result.data[branch_type]["q_to"]
            type_df["from_node"] = self._stes_result.data[branch_type]["from_node"]
            type_df["to_node"] = self._stes_result.data[branch_type]["to_node"]

            df = pd.concat([df, type_df], ignore_index=True)

        if df.empty:
            return

        df["iri"] = [self._stes_result.extra_info[x]["_mrid"] for x in df["id"]]
        df["from_iri"] = [
            self._stes_result.extra_info[x]["_mrid"] for x in df["from_node"]
        ]
        df["to_iri"] = [self._stes_result.extra_info[x]["_mrid"] for x in df["to_node"]]

        self.add_branch_data(df)

        df["p_from_delta"] = df["p_from_pgm"] - df["p_from_sv"]
        df["q_from_delta"] = df["q_from_pgm"] - df["q_from_sv"]
        df["p_to_delta"] = df["p_to_pgm"] - df["p_to_sv"]
        df["q_to_delta"] = df["q_to_pgm"] - df["q_to_sv"]

        # rearrange columns
        df = df[
            [
                "id",
                "on",
                "p_from_pgm",
                "p_from_sv",
                "p_from_delta",
                "q_from_pgm",
                "q_from_sv",
                "q_from_delta",
                "p_to_pgm",
                "p_to_sv",
                "p_to_delta",
                "q_to_pgm",
                "q_to_sv",
                "q_to_delta",
                "iri",
            ]
        ]

        df = convert_dataframe(df)
        self._write_df(df, self._writer)

    def add_branch_data(self, df: pd.DataFrame):

        _query_power = """
                    SELECT ?p ?q ?tn ?eq ?term
                    WHERE {
                        ?sv a cim:SvPowerFlow;
                            cim:SvPowerFlow.p ?p;
                            cim:SvPowerFlow.q ?q;
                            cim:SvPowerFlow.Terminal ?term.

                        ?term cim:Terminal.TopologicalNode ?tn;
                            cim:Terminal.ConductingEquipment ?eq.
                    }
                """

        query_result = self.datasource.query(_query_power)

        query_result["p"] *= 1e6
        query_result["q"] *= 1e6

        p_from_sv = []
        q_from_sv = []
        p_to_sv = []
        q_to_sv = []

        for x in df.itertuples():

            # branch from
            sv_power = query_result[
                (query_result["eq"] == x.iri) & (query_result["tn"] == x.from_iri)
            ]
            if len(sv_power) > 0:
                p_from_sv.append(sv_power["p"].values[0])
                q_from_sv.append(sv_power["q"].values[0])
            else:
                p_from_sv.append(None)
                q_from_sv.append(None)

            # branch to
            sv_power = query_result[
                (query_result["eq"] == x.iri) & (query_result["tn"] == x.to_iri)
            ]
            if len(sv_power) > 0:
                p_to_sv.append(sv_power["p"].values[0])
                q_to_sv.append(sv_power["q"].values[0])
            else:
                p_to_sv.append(None)
                q_to_sv.append(None)

        df["p_from_sv"] = p_from_sv
        df["q_from_sv"] = q_from_sv
        df["p_to_sv"] = p_to_sv
        df["q_to_sv"] = q_to_sv
