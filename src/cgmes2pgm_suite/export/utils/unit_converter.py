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

import re

import numpy as np
import pandas as pd


def e3(x):
    return x / 1e3


def e6(x):
    return x / 1e6


def e_deg(x):
    return np.rad2deg(x)


# List of fields, conversion_function, and unit symbols to be used in the text export
# fmt: off
_exclusions = ["id", "u_pu", "u_ref"]
_conversions = [
    {"regex": "^p(_.*)?$", "unit": "MW", "func": e6, "decimal_places": 3},
    {"regex": "^q(_.*)?$", "unit": "MVar", "func": e6, "decimal_places": 3},
    {"regex": "^power_sigma$", "unit": "MVar", "func": e6, "decimal_places": 3},
    {"regex": "^u_angle(_.*)?$", "unit": "°", "func": e_deg, "decimal_places": 3},
    {"regex": "^u(_.*|\\d)?$", "unit": "kV", "func": e3, "decimal_places": 3}, # u1, u_1, ...
    {"regex": "^s(_.*)?$", "unit": "MVA", "func": e6, "decimal_places": 3},
    {"regex": "^sn(_.*)?$", "unit": "MVA", "func": e6, "decimal_places": 3},
    {"regex": "^sk(_.*)?$", "unit": "MVA", "func": e6, "decimal_places": 3},
    {"regex": "^i(_.*)?$", "unit": "A", "func": lambda x: x, "decimal_places": 3},
    {"regex": "^deviation(_.*)?$", "unit": "σ", "func": lambda x: x, "decimal_places": 3},
    {"regex": "^pk(_.*)?$", "unit": "kW", "func": e3, "decimal_places": 3},
    {"regex": "^tap_size(_.*)?$", "unit": "kW", "func": e3, "decimal_places": 3},
]
# fmt: on


def convert_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Convert the units of a DataFrame to readable units for the text export

    Args:
        df (pd.DataFrame): The DataFrame to convert

    Returns:
        pd.DataFrame: The converted DataFrame
    """
    for name in df.columns:
        for conversion in _conversions:
            if name in _exclusions:
                continue

            if re.match(conversion["regex"], name):
                df[name] = conversion["func"](df[name])
                df[name] = df[name].round(conversion["decimal_places"])
                df[name] = df[name].mask(df[name].abs() < 0.001, 0)
                df = df.rename(columns={name: f"{name} [{conversion['unit']}]"})
                break

    return df
