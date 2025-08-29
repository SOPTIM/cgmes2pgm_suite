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
from typing import Any

from power_grid_model_io.data_types import ExtraInfo


def extra_info_with_clean_iris(extra_info: ExtraInfo):
    new_extra_info = extra_info.copy()
    for key, value in extra_info.items():
        if isinstance(value, dict):
            new_extra_info[key] = _clean_iris_dict(value)
        if isinstance(value, str) and value.startswith("http") and "#" in value:
            new_extra_info[key] = _clean_iri_string(value)
    return new_extra_info


def _clean_iris_dict(_dict: dict[Any, Any]):
    new_dict = _dict.copy()
    for key, value in _dict.items():
        if isinstance(value, dict):
            new_dict[key] = _clean_iris_dict(value)
        elif isinstance(value, str) and value.startswith("http") and "#" in value:
            new_dict[key] = _clean_iri_string(value)
        else:
            new_dict[key] = value
    return new_dict


def _clean_iri_string(value: str) -> str:
    match = re.search(r".*#(.*)", value)
    if match:
        return match.group(1)
    return value
