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


def format_dataframe(df: pd.DataFrame, indentation: int = 0) -> str:
    """
    Formats a DataFrame for printing.
    Indentation is used to allow folding and to use work with sticky scroll in vs code

    Args:
        df (pd.DataFrame): The DataFrame to format

    Returns:
        str: The formatted DataFrame as a string
    """
    res = df.to_string(index=False, na_rep="-")

    res = res.replace("\n", "\n" + " " * (indentation + 4))
    res = indentation * " " + "x   " + res
    return res
