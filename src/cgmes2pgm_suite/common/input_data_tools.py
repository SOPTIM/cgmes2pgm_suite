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

from power_grid_model import ComponentType, MeasuredTerminalType


class CacheEntry:
    def __init__(self, _type: ComponentType, _data: dict):
        self.type = _type
        self.data = _data


class InputDataIdCache:

    def __init__(self, input_data: dict):
        self._input_data = input_data
        self._id_cache: dict[int, CacheEntry] = {}
        for component_type in input_data:
            for ct_data in input_data[component_type]:
                self._id_cache[ct_data["id"]] = CacheEntry(component_type, ct_data)

    def get_component_type(self, component_id: int) -> ComponentType:
        component_data = self._id_cache.get(component_id)
        if component_data is None:
            raise ValueError(f"Component ID {component_id} not found in input data")

        return component_data.type

    def get_component(self, component_id: int) -> dict:
        component_data = self._id_cache.get(component_id)
        if component_data is None:
            raise ValueError(f"Component ID {component_id} not found in input data")

        return component_data.data

    def get_node_id_from_sensor(self, sensor_id: int) -> int:
        sensor = self.get_component(sensor_id)
        measured_terminal_type = sensor["measured_terminal_type"]
        measured_object_id = sensor["measured_object"]
        measured_object = self.get_component(measured_object_id)

        match measured_terminal_type:
            case MeasuredTerminalType.node:
                return measured_object_id
            case (
                MeasuredTerminalType.generator
                | MeasuredTerminalType.load
                | MeasuredTerminalType.shunt
                | MeasuredTerminalType.source
            ):
                return measured_object["node"]
            case MeasuredTerminalType.branch_from:
                return measured_object["from_node"]
            case MeasuredTerminalType.branch_to:
                return measured_object["to_node"]
            case MeasuredTerminalType.branch3_1:
                return measured_object["node_1"]
            case MeasuredTerminalType.branch3_2:
                return measured_object["node_2"]
            case MeasuredTerminalType.branch3_3:
                return measured_object["node_3"]

        raise ValueError(f"Sensor ID {sensor_id} not found in input data")
