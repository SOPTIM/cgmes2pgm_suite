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

from typing import TextIO

import numpy as np
import pandas as pd
from power_grid_model import ComponentType

from cgmes2pgm_suite.export.utils import convert_dataframe, format_dataframe
from cgmes2pgm_suite.state_estimation import StateEstimationResult


# pylint: disable=too-few-public-methods
class ResultTextExport:
    """
    Simplified export of state estimation results to text file
    """

    def __init__(self, path: str, data: StateEstimationResult):
        self.path = path
        self.data = data.data
        self.extra_info = data.extra_info

    def export(self):
        with open(self.path, "w", encoding="utf-8") as file:
            self._print_bus_data(file)
            file.write("\n" * 2)
            self._print_branch_data(file)
            file.write("\n" * 2)
            self._print_branch3_data(file)
            file.write("\n" * 2)
            self._print_vol_sensor_data(file)
            file.write("\n" * 2)
            self._print_pow_sensor_data(file)

    def _print_bus_data(self, file: TextIO):

        self._print_header(file, "Bus Data")

        # Construct DataFrame to create the table
        df = pd.DataFrame()
        df["id"] = self.data["node"]["id"]
        df["u_pu"] = self.data["node"]["u_pu"]
        df["u"] = self.data["node"]["u"]
        df["u_angle"] = self.data["node"]["u_angle"]

        df["p_gen"] = np.where(
            self.data["node"]["p"].round(4) > 0,
            self.data["node"]["p"],
            np.nan,
        )
        df["q_gen"] = np.where(
            self.data["node"]["q"].round(4) > 0,
            self.data["node"]["q"],
            np.nan,
        )
        df["p_load"] = np.where(
            self.data["node"]["p"].round(4) < 0,
            self.data["node"]["p"],
            np.nan,
        )
        df["q_load"] = np.where(
            self.data["node"]["q"].round(4) < 0,
            self.data["node"]["q"],
            np.nan,
        )

        self._add_name(df)

        # Add Totals as new row
        total = df[["p_gen", "q_gen", "p_load", "q_load"]].sum()
        total["id"] = "Total"
        df.loc[-1] = total

        # Add * to slack bus
        df["id"] = [
            f"*{id}" if id in list(self.data["source"]["node"]) else id
            for id in df["id"]
        ]

        df = convert_dataframe(df)

        file.write(format_dataframe(df, indentation=4))

    def _print_branch_data(self, file: TextIO):
        # Header
        self._print_header(file, "Branch Data")

        df = self._build_branch_df()

        df = convert_dataframe(df)
        self._add_name(df)
        file.write(format_dataframe(df, indentation=4))

    def _build_branch_df(self):
        id = np.array([], dtype=int)
        type = np.array([], dtype=str)
        from_node = np.array([], dtype=int)
        to_node = np.array([], dtype=int)
        p_from = np.array([])
        q_from = np.array([])
        p_to = np.array([])
        q_to = np.array([])
        components = [
            ComponentType.line,
            ComponentType.generic_branch,
            ComponentType.transformer,
            ComponentType.link,
        ]
        for component in components:
            if component not in self.data or len(self.data[component]["id"]) == 0:
                continue
            id = np.concatenate([id, self.data[component]["id"]])
            type = np.concatenate(
                [type, np.full(len(self.data[component]["id"]), component.value)]
            )
            from_node = np.concatenate([from_node, self.data[component]["from_node"]])
            to_node = np.concatenate([to_node, self.data[component]["to_node"]])
            p_from = np.concatenate([p_from, self.data[component]["p_from"]])
            q_from = np.concatenate([q_from, self.data[component]["q_from"]])
            p_to = np.concatenate([p_to, self.data[component]["p_to"]])
            q_to = np.concatenate([q_to, self.data[component]["q_to"]])

        df = pd.DataFrame()
        df["id"] = id
        df["type"] = type
        df["from"] = from_node
        df["to"] = to_node
        df["p_from"] = p_from
        df["q_from"] = q_from
        df["p_to"] = p_to
        df["q_to"] = q_to
        return df

    def _print_branch3_data(self, file: TextIO):
        if (
            "three_winding_transformer" not in self.data
            or len(self.data["three_winding_transformer"]["id"]) == 0
        ):
            return

        self._print_header(file, "Branch3 Data")

        df = pd.DataFrame()
        df["id"] = self.data["three_winding_transformer"]["id"]
        df["node_1"] = self.data["three_winding_transformer"]["node_1"]
        df["node_2"] = self.data["three_winding_transformer"]["node_2"]
        df["node_3"] = self.data["three_winding_transformer"]["node_3"]
        df["p_1"] = self.data["three_winding_transformer"]["p_1"]
        df["q_1"] = self.data["three_winding_transformer"]["q_1"]
        df["p_2"] = self.data["three_winding_transformer"]["p_2"]
        df["q_2"] = self.data["three_winding_transformer"]["q_2"]
        df["p_3"] = self.data["three_winding_transformer"]["p_3"]
        df["q_3"] = self.data["three_winding_transformer"]["q_3"]

        df = convert_dataframe(df)
        self._add_name(df)
        file.write(format_dataframe(df, indentation=4))

    def _print_vol_sensor_data(self, file: TextIO):

        if "sym_voltage_sensor" not in self.data:
            return

        self._print_header(file, "Sym Voltage Sensor Data")

        df = pd.DataFrame()
        df["id"] = self.data["sym_voltage_sensor"]["id"]
        df["u_measured"] = self.data["sym_voltage_sensor"]["u_measured"]
        df["u_actual"] = (
            self.data["sym_voltage_sensor"]["u_measured"]
            - self.data["sym_voltage_sensor"]["u_residual"]
        )
        df["u_sigma"] = self.data["sym_voltage_sensor"]["u_sigma"]
        df["u_residual"] = self.data["sym_voltage_sensor"]["u_residual"]
        df["bad_data"] = np.where(
            np.abs(df["u_residual"]) > (3 * df["u_sigma"]), "*", ""
        )

        df = convert_dataframe(df)
        self._add_name(df)
        file.write(format_dataframe(df, indentation=4))

    def _print_pow_sensor_data(self, file: TextIO):

        if "sym_power_sensor" not in self.data:
            return

        self._print_header(file, "Sym Power Sensor Data")

        df = pd.DataFrame()
        df["id"] = self.data["sym_power_sensor"]["id"]
        df["p_measured"] = self.data["sym_power_sensor"]["p_measured"]
        df["q_measured"] = self.data["sym_power_sensor"]["q_measured"]
        df["p_actual"] = (
            self.data["sym_power_sensor"]["p_measured"]
            - self.data["sym_power_sensor"]["p_residual"]
        )
        df["q_actual"] = (
            self.data["sym_power_sensor"]["q_measured"]
            - self.data["sym_power_sensor"]["q_residual"]
        )
        df["p_sigma"] = self.data["sym_power_sensor"]["p_sigma"]
        df["q_sigma"] = self.data["sym_power_sensor"]["q_sigma"]
        df["p_residual"] = self.data["sym_power_sensor"]["p_residual"]
        df["q_residual"] = self.data["sym_power_sensor"]["q_residual"]
        df["bad_p"] = np.where(np.abs(df["p_residual"]) > (3 * df["p_sigma"]), "*", "")
        df["bad_q"] = np.where(np.abs(df["q_residual"]) > (3 * df["q_sigma"]), "*", "")

        df = convert_dataframe(df)
        file.write(format_dataframe(df, indentation=4))

    def _add_name(self, df: pd.DataFrame):
        df.insert(1, "Name", df["id"].map(lambda x: self.extra_info[x]["_name"]))

    def _print_header(self, file: TextIO, header: str):
        file.write(f"\n===== {header} =====\n\n")
