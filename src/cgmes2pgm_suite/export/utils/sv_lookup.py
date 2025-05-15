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
from cgmes2pgm_converter.common import CgmesDataset


class SvVoltageLookup:

    _query = """
    SELECT DISTINCT ?node ?voltage ?angle
    WHERE {
        ?sv cim:SvVoltage.TopologicalNode ?node;
            cim:SvVoltage.v ?voltage;
            cim:SvVoltage.angle ?angle.
    }
    """

    def __init__(self, datasource: CgmesDataset):
        self.datasource = datasource
        self._voltage_meas = self._get_voltage_meas()

    def _get_voltage_meas(self) -> dict:
        df = self.datasource.query(self._query)
        return {
            str(row["node"]): (row["voltage"], row["angle"]) for _, row in df.iterrows()
        }

    def get_voltage(self, node_mrid: str) -> tuple:
        return self._voltage_meas.get(node_mrid, (None, None))


class SvPowerFlowLookup:

    _query = """
    SELECT DISTINCT ?node ?eq ?p ?q
    WHERE {
        ?sv cim:SvPowerFlow.Terminal ?term;
            cim:SvPowerFlow.p ?p;
            cim:SvPowerFlow.q ?q.

        ?term cim:Terminal.TopologicalNode ?node;
              cim:Terminal.ConductingEquipment ?eq.
    }
    """

    def __init__(self, datasource: CgmesDataset):
        self.datasource = datasource
        self._power_flow_meas = self._get_power_flow_meas()

    def _get_power_flow_meas(self) -> dict:
        df = self.datasource.query(self._query)
        return {
            (str(row["node"]), str(row["eq"])): (row["p"] * 1e6, row["q"] * 1e6)
            for _, row in df.iterrows()
        }

    def get_power_flow(self, node_mrid: str, eq_mrid: str) -> tuple:
        return self._power_flow_meas.get((node_mrid, eq_mrid), (np.nan, np.nan))
