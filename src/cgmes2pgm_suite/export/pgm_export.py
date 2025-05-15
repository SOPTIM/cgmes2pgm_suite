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

from cgmes2pgm_converter.common import AbstractCgmesIdMapping
from power_grid_model_io.converters import PgmJsonConverter


# pylint: disable=too-few-public-methods
class PgmJsonExport:
    """
    Export PGM data to JSON file
    """

    def __init__(
        self,
        path: str,
        data: dict,
        id_mapping: AbstractCgmesIdMapping,
        header: bool = False,
    ):
        self._path = path
        self._data = data
        self._id_mapping = id_mapping
        self._header = header

    def export(self):
        converter = PgmJsonConverter(destination_file=self._path)
        converter.save(data=self._data, extra_info=self._build_extra_info())

        if self._header:
            header = """
            {
              "version": "1.0",
              "type": "input",
              "is_batch": false,
              "attributes": {},
              "data":
            """
            with open(self._path, "r", encoding="utf-8") as file:
                file_data = file.read()
                file_data = header + file_data

            # Add } at end of file
            file_data += "}"

            with open(self._path, "w", encoding="utf-8") as file:
                file.write(file_data)

    def _build_extra_info(self) -> dict:
        d = {}
        for cgmes_iri, pgm_id in self._id_mapping.items():
            d[pgm_id] = {
                "_name": str(self._id_mapping.get_name_from_pgm(pgm_id)),
                "_mrid": cgmes_iri,
            }

        return d
