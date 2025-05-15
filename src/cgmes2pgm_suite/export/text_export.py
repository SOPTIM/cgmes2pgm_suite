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
from power_grid_model_io.data_types import ExtraInfo

from cgmes2pgm_suite.export.utils import convert_dataframe, format_dataframe


# pylint: disable=too-few-public-methods
class TextExport:
    """
    Text export for PGM input or result data.
    The export contains extra_infos and converts values from SI units to more readable units
    (e. g. V -> kV, W -> MW).
    """

    def __init__(
        self,
        path: str,
        data: dict,
        extra_info: ExtraInfo,
        print_mrid: bool = False,
    ):
        self.path = path
        self.data = data
        self.extra_info = extra_info
        self.print_mrid = print_mrid

    def export(self):
        with open(self.path, "w", encoding="utf-8") as file:
            for k, v in self.data.items():
                self._print_component(k, v, file)
                file.write("\n")

    def _print_component(
        self,
        component_name: str | ComponentType,
        component: np.ndarray,
        file: TextIO,
    ):
        name = (
            component_name.value
            if isinstance(component_name, ComponentType)
            else component_name
        )

        # Header
        file.write(f"\n===== {name} =====\n\n")
        file.write(f"    Shape: {component.shape}\n\n")

        df = pd.DataFrame(component)

        # Add extra info
        for row in range(df.shape[0]):
            id = df.at[row, "id"]

            for key, value in self.extra_info[id].items():
                if ("mrid" in key or "Mrid" in key) and not self.print_mrid:
                    continue

                if key in df.columns:
                    df.at[row, key] = value
                else:
                    # Add new column
                    df[key] = None
                    df.at[row, key] = value

        df = convert_dataframe(df)

        # if _name column exists, move it to the front
        if "_name" in df.columns:
            names = df.pop("_name")
            df.insert(0, "_name", names)

        file.write(format_dataframe(df, indentation=4))
        file.write("\n" * 2)
