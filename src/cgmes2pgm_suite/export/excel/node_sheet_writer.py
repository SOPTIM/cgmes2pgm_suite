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

from cgmes2pgm_suite.export.utils import SvVoltageLookup, convert_dataframe

from .abstract_result_sheet_writer import AbstractResultSheetWriter


class NodeSheetWriter(AbstractResultSheetWriter):

    def __init__(
        self,
        writer: pd.ExcelWriter,
        sheet_name: str,
        stes_result,
        datasource: CgmesDataset,
    ):
        super().__init__(writer, sheet_name, stes_result)
        self._datasource = datasource

    def write(self):
        df = pd.DataFrame()
        df["id"] = self._stes_result.data["node"]["id"]
        df["name"] = df["id"].map(lambda x: self._stes_result.extra_info[x]["_name"])
        df["iri"] = df["id"].map(lambda x: self._stes_result.extra_info[x]["_mrid"])
        df["substation"] = df["id"].map(
            lambda x: self._stes_result.extra_info[x]["_substation"]
        )
        df["energized"] = self._stes_result.data["node"]["energized"].astype(bool)
        df["u_pgm"] = self._stes_result.data["node"]["u"]
        df["u_angle_pgm"] = self._stes_result.data["node"]["u_angle"]

        self._add_voltage_measurements(df)
        self._add_sv_values(df)
        self._add_deltas(df)
        self._add_power_balance(df)

        df = self._reorder_columns(df)

        df = convert_dataframe(df)
        worksheet = self._write_df(df, self._writer)

        self.draw_vert_line(worksheet, 3)
        self.draw_vert_line(worksheet, 4)
        self.draw_vert_line(worksheet, 8)
        self.draw_vert_line(worksheet, 9)
        self.draw_vert_line(worksheet, 12)

        self._format_sigmas(len(df.columns) - 5, len(df.columns) - 5, worksheet)

    def _add_voltage_measurements(self, df: pd.DataFrame):
        df["u_meas"] = np.nan
        df["u_sigma"] = np.nan
        df["Meas_Type"] = ""

        sensors = self._stes_result.data["sym_voltage_sensor"]
        for index, row in df.iterrows():

            sensor = sensors[sensors["measured_object"] == row["id"]]
            if len(sensor) == 1:
                sensor = sensor.iloc[0]
                df.at[index, "u_meas"] = sensor["u_measured"]
                df.at[index, "u_sigma"] = sensor["u_sigma"]
                df.at[index, "Meas_Type"] = self._stes_result.extra_info[sensor["id"]][
                    "_type"
                ]

    def _add_sv_values(self, df: pd.DataFrame):
        voltage_lookup = SvVoltageLookup(self._datasource)
        for index, row in df.iterrows():
            voltage, _ = voltage_lookup.get_voltage(row["iri"])
            df.at[index, "u_sv"] = voltage * 1e3 if voltage is not None else None

    def _add_deltas(self, df: pd.DataFrame):
        df["u_delta_meas_pgm"] = df["u_meas"] - df["u_pgm"]
        df["u_delta_pgm_sv"] = df["u_pgm"] - df["u_sv"]

        df["deviation_meas_pgm"] = df["u_delta_meas_pgm"] / df["u_sigma"]

    def _add_power_balance(self, df: pd.DataFrame):
        df["p_load_est"] = 0.0
        df["q_load_est"] = 0.0
        df["p_gen_est"] = 0.0
        df["q_gen_est"] = 0.0

        appliance_types = ["sym_load", "sym_gen", "shunt", "source"]
        reference_dir = [-1, 1, -1, 1]  # -1 for load, 1 for gen

        for i, appliance_type in enumerate(appliance_types):
            for _, appliance in self._stes_result.data[appliance_type].iterrows():
                node_id = appliance["node"]
                node_index = df[df["id"] == node_id].index[0]
                p = appliance["p"] * reference_dir[i]
                q = appliance["q"] * reference_dir[i]

                df.at[node_index, "p_load_est"] += p if p < 0 else 0
                df.at[node_index, "q_load_est"] += q if q < 0 else 0
                df.at[node_index, "p_gen_est"] += p if p > 0 else 0
                df.at[node_index, "q_gen_est"] += q if q > 0 else 0

    def _reorder_columns(self, df: pd.DataFrame):
        return df[
            [
                "id",
                "name",
                "substation",
                "Meas_Type",
                "energized",
                "u_sigma",
                "u_pgm",
                "u_meas",
                "u_sv",
                "u_angle_pgm",
                "u_delta_meas_pgm",
                "u_delta_pgm_sv",
                "deviation_meas_pgm",
                "p_load_est",
                "q_load_est",
                "p_gen_est",
                "q_gen_est",
            ]
        ]
