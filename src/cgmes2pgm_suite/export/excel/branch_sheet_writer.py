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

from abc import abstractmethod

import numpy as np
import pandas as pd
from power_grid_model import ComponentType, MeasuredTerminalType

from cgmes2pgm_suite.export.utils import convert_dataframe

from .abstract_result_sheet_writer import AbstractResultSheetWriter


class AbstractBranchSheetWriter(AbstractResultSheetWriter):

    def _write_side(
        self,
        df: pd.DataFrame,
        side: str,
        terminal_type: MeasuredTerminalType,
        component_name: str,
    ):
        """Add Columns for the given side of a branch to the DataFrame
        (e.g for side 1: p_1_est, q_1_est, ...

        Args:
            df (pd.DataFrame): The DataFrame to add the columns to
            side (str): The side of the branch (1, 2)
            terminal_type (MeasuredTerminalType): The terminal type of the side
        """

        df[f"p_{side}_est"] = self._stes_result.data[component_name][f"p_{side}"]
        df[f"q_{side}_est"] = self._stes_result.data[component_name][f"q_{side}"]

        self._add_power_measurements(df, side, terminal_type)
        df[f"deviation_p_{side}"] = df[f"p_{side}_residual"] / df[f"p_{side}_sigma"]
        df[f"deviation_q_{side}"] = df[f"q_{side}_residual"] / df[f"q_{side}_sigma"]

        df.drop(
            columns=[
                f"p_{side}_sigma",
                f"q_{side}_sigma",
                f"p_{side}_residual",
                f"q_{side}_residual",
            ],
            inplace=True,
        )

    def _add_power_measurements(
        self,
        df: pd.DataFrame,
        side: str,
        terminal_type: MeasuredTerminalType,
    ):
        """Add the power measurements for the given side of the branch to the DataFrame

        Args:
            df (pd.DataFrame): The DataFrame to add the columns to
            side (str): The side of the branch (1, 2)
            terminal_type (MeasuredTerminalType): The terminal type of the side
        """
        power_sensors = self._stes_result.data["sym_power_sensor"]

        df["energized"] = False

        df[f"p_{side}_meas"] = np.nan
        df[f"q_{side}_meas"] = np.nan
        df[f"p_{side}_sigma"] = np.nan
        df[f"q_{side}_sigma"] = np.nan
        df[f"p_{side}_residual"] = 0.0
        df[f"q_{side}_residual"] = 0.0

        for index, row in df.iterrows():
            # get the power sensors for the current row

            curr_sensors = power_sensors[
                (power_sensors["measured_object"] == row["id"])
                & (power_sensors["measured_terminal_type"] == terminal_type)
            ]

            if len(curr_sensors) >= 1:
                sensor = curr_sensors.iloc[0]
                df.at[index, "energized"] = sensor["energized"].astype(bool)
                df.at[index, f"p_{side}_meas"] = sensor["p_measured"]
                df.at[index, f"q_{side}_meas"] = sensor["q_measured"]
                df.at[index, f"p_{side}_sigma"] = sensor["p_sigma"]
                df.at[index, f"q_{side}_sigma"] = sensor["q_sigma"]
                df.at[index, f"p_{side}_residual"] = sensor["p_residual"]
                df.at[index, f"q_{side}_residual"] = sensor["q_residual"]

    @abstractmethod
    def write(self):
        raise NotImplementedError


class Branch3SheetWriter(AbstractBranchSheetWriter):
    """Creates the Excel sheet for the branches with 3 sides containing measured
    and estimated values for each side of the branch.
    If multiple sensors are connected to a side, a random one is chosen
    """

    def write(self):

        if (
            not ComponentType.three_winding_transformer in self._stes_result.data
            or len(self._stes_result.data[ComponentType.three_winding_transformer]) == 0
        ):
            return

        df = pd.DataFrame()
        df["id"] = self._stes_result.data[ComponentType.three_winding_transformer]["id"]
        df["name"] = df["id"].map(lambda x: self._stes_result.extra_info[x]["_name"])

        for i, terminal_type in zip(
            ["1", "2", "3"],
            [
                MeasuredTerminalType.branch3_1,
                MeasuredTerminalType.branch3_2,
                MeasuredTerminalType.branch3_3,
            ],
        ):
            self._write_side(df, i, terminal_type, "three_winding_transformer")

        df = convert_dataframe(df)
        worksheet = self._write_df(df, self._writer)

        sigma_cols = [6, 7, 12, 13, 18, 19]
        for i in sigma_cols:
            self._format_sigmas(i, i, worksheet)


class Branch2SheetWriter(AbstractBranchSheetWriter):
    """Creates the Excel sheet for the branches with 2 sides containing measured
    and estimated values for each side of the branch.
    If multiple sensors are connected to a side, a random one is chosen
    """

    def write(self):

        component_names = [
            ComponentType.line,
            ComponentType.generic_branch,
            ComponentType.transformer,
            ComponentType.link,
        ]
        df = pd.DataFrame()

        for component_name in component_names:
            if (
                component_name in self._stes_result.data
                and len(self._stes_result.data[component_name]) > 0
            ):
                df = pd.concat([df, self._get_branch_df(component_name)])

        if df.empty:
            return

        df.insert(
            1, "name", df["id"].map(lambda x: self._stes_result.extra_info[x]["_name"])
        )

        df = self._reorder_columns(df)
        df = convert_dataframe(df)

        worksheet = self._write_df(df, self._writer)

        self.draw_vert_line(worksheet, 1)
        self.draw_vert_line(worksheet, 2)
        self.draw_vert_line(worksheet, 6)

    def _get_branch_df(self, component_name: str):
        df = pd.DataFrame()
        df["id"] = self._stes_result.data[component_name]["id"]

        for side, terminal_type in zip(
            ["from", "to"],
            [
                MeasuredTerminalType.branch_from,
                MeasuredTerminalType.branch_to,
            ],
        ):
            self._write_side(df, side, terminal_type, component_name)

        return df

    def _reorder_columns(self, df: pd.DataFrame):
        return df[
            [
                "id",
                "name",
                "energized",
                "p_from_est",
                "q_from_est",
                "p_from_meas",
                "q_from_meas",
                "p_to_est",
                "q_to_est",
                "p_to_meas",
                "q_to_meas",
            ]
        ]
