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

from cgmes2pgm_converter.common import CgmesDataset


class CurrentMeasurements:

    _query = """
    SELECT DISTINCT ?eq ?term
    WHERE {
        ?term cim:Terminal.ConductingEquipment ?eq.

        ?_meas cim:Measurement.measurementType "LineCurrent";
            cim:Measurement.PowerSystemResource ?eq;
            cim:Measurement.Terminal ?term.
    }
   """

    def __init__(self, datasource: CgmesDataset):
        self.datasource = datasource

        res = self.datasource.query(self._query)

        self._eq_with_current_meas = list(res["eq"])
        self._term_with_current_meas = list(res["term"])

    def has_current_meas(self, equipment_mrid: str) -> bool:
        return (
            equipment_mrid in self._eq_with_current_meas
            or equipment_mrid in self._term_with_current_meas
        )
