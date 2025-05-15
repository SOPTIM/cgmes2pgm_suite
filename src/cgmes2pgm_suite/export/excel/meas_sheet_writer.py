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

import pandas as pd
from cgmes2pgm_converter.common import CgmesDataset
from power_grid_model import ComponentType

from cgmes2pgm_suite.common import InputDataIdCache
from cgmes2pgm_suite.export.utils import SvPowerFlowLookup, convert_dataframe
from cgmes2pgm_suite.state_estimation import StateEstimationResult

from .abstract_result_sheet_writer import AbstractResultSheetWriter


class MeasSheetWriter(AbstractResultSheetWriter):

    def __init__(
        self,
        writer: pd.ExcelWriter,
        sheet_name: str,
        stes_result: StateEstimationResult,
        datasource: CgmesDataset,
    ):
        super().__init__(writer, sheet_name, stes_result)

        self.datasource = datasource
        self._sv_power_flow_lookup = SvPowerFlowLookup(datasource)

        # Move to attributes to simplify code
        self._extra_info = self._stes_result.extra_info
        self._data = self._stes_result.data
        self._id_cache = InputDataIdCache(stes_result.input_data)

    def write(self):

        df = pd.DataFrame()
        df["id"] = self._stes_result.data["sym_power_sensor"]["id"]
        df["Sensor_Name"] = df["id"].map(lambda x: self._extra_info[x]["_name"])

        self._add_equipment_data(df)
        self._add_meas_and_pgm(df)
        self._add_node_data(df)
        self._add_sv_values(df)
        self._add_meas_type(df)

        df = self._reorder_columns(df)
        df = convert_dataframe(df)

        worksheet = self._write_df(df, self._writer)

        self.draw_vert_line(worksheet, 5)
        self.draw_vert_line(worksheet, 6)
        self.draw_vert_line(worksheet, 8)
        self.draw_vert_line(worksheet, 11)
        self.draw_vert_line(worksheet, 14)
        self.draw_vert_line(worksheet, 16)
        self.draw_vert_line(worksheet, 18)
        self.draw_vert_line(worksheet, 20)

        self._format_sigmas(len(df.columns) - 3, len(df.columns) - 2, worksheet)

    def _add_meas_and_pgm(self, df: pd.DataFrame):

        df["p_meas"] = self._data[ComponentType.sym_power_sensor]["p_measured"]
        df["q_meas"] = self._data[ComponentType.sym_power_sensor]["q_measured"]

        df["p_delta_meas_pgm"] = self._data[ComponentType.sym_power_sensor][
            "p_residual"
        ]
        df["q_delta_meas_pgm"] = self._data[ComponentType.sym_power_sensor][
            "q_residual"
        ]

        df["p_sigma"] = self._data[ComponentType.sym_power_sensor]["p_sigma"]
        df["q_sigma"] = self._data[ComponentType.sym_power_sensor]["q_sigma"]

        df["p_pgm"] = df["p_meas"] - df["p_delta_meas_pgm"]
        df["q_pgm"] = df["q_meas"] - df["q_delta_meas_pgm"]

        df["deviation_p"] = df["p_delta_meas_pgm"] / df["p_sigma"]
        df["deviation_q"] = df["q_delta_meas_pgm"] / df["q_sigma"]

        df["energized"] = self._data[ComponentType.sym_power_sensor][
            "energized"
        ].astype(bool)

        # set p,q_pgm to none if not energized
        df.loc[~df["energized"], ["p_pgm", "q_pgm"]] = None

    def _add_equipment_data(self, df: pd.DataFrame):
        equipment_ids = self._data[ComponentType.sym_power_sensor]["measured_object"]
        df["Equipment"] = [self._extra_info[e_id]["_name"] for e_id in equipment_ids]
        df["Eq_Type"] = [self._extra_info[e_id]["_type"] for e_id in equipment_ids]

    def _add_node_data(self, df: pd.DataFrame):
        node_ids = [self._id_cache.get_node_id_from_sensor(s_id) for s_id in df["id"]]
        df["_node_id"] = node_ids
        df["Node"] = [self._extra_info[n_id]["_name"] for n_id in node_ids]
        df["Substation"] = [self._extra_info[n_id]["_substation"] for n_id in node_ids]

    def _add_sv_values(self, df: pd.DataFrame):

        node_mrids = [self._extra_info[n_id]["_mrid"] for n_id in df["_node_id"]]
        eq_mrids = [
            self._extra_info[e_id]["_mrid"]
            for e_id in self._data[ComponentType.sym_power_sensor]["measured_object"]
        ]
        p, q = zip(
            *[
                self._sv_power_flow_lookup.get_power_flow(n_id, e_id)
                for n_id, e_id in zip(node_mrids, eq_mrids)
            ]
        )
        df["p_sv"] = p
        df["q_sv"] = q

        # flip sv where component_type is gen
        for i, e_id in enumerate(
            self._data[ComponentType.sym_power_sensor]["measured_object"]
        ):
            if (
                self._id_cache.get_component_type(e_id) == ComponentType.sym_gen
                or self._id_cache.get_component_type(e_id) == ComponentType.source
            ):
                df.at[i, "p_sv"] *= -1
                df.at[i, "q_sv"] *= -1

        df["p_delta_pgm_sv"] = df["p_pgm"] - df["p_sv"]
        df["q_delta_pgm_sv"] = df["q_pgm"] - df["q_sv"]

    def _add_meas_type(self, df: pd.DataFrame):
        df["Meas_Type"] = [
            self._extra_info[sensor_id]["_type"] for sensor_id in df["id"]
        ]

    def _reorder_columns(self, df: pd.DataFrame):
        return df[
            [
                "id",
                "Meas_Type",
                "Equipment",
                "Eq_Type",
                "Node",
                "Substation",
                "energized",
                "p_sigma",
                "q_sigma",
                "p_meas",
                "p_pgm",
                "p_sv",
                "q_meas",
                "q_pgm",
                "q_sv",
                "p_delta_meas_pgm",
                "p_delta_pgm_sv",
                "q_delta_meas_pgm",
                "q_delta_pgm_sv",
                "deviation_p",
                "deviation_q",
                "Sensor_Name",
            ]
        ]
