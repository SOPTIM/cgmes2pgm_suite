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
from cgmes2pgm_converter.common import CgmesDataset, SymPowerType, Topology
from power_grid_model import ComponentType, MeasuredTerminalType

from .excel.excel_sheet_writer import ExcelSheetWriter
from .utils import convert_dataframe


class SshSubstitutionExport:

    def __init__(
        self,
        path: str,
        datasource: CgmesDataset,
        topology: Topology,
    ):
        self._path = path
        self._datasource = datasource
        self._topology = topology

    def export(self):
        with pd.ExcelWriter(self._path, engine="xlsxwriter") as writer:
            SshSubstitutionSheetWriter(
                writer,
                self._datasource,
                self._topology,
            ).write()


class SshSubstitutionSheetWriter(ExcelSheetWriter):
    def __init__(
        self,
        writer: pd.ExcelWriter,
        datasource: CgmesDataset,
        topology: Topology,
    ):
        super().__init__(writer=writer, sheet_name="SSH Substitution")
        self.datasource = datasource
        self.topology = topology

    def write(self):
        substituted_appliances = self.get_substituted_appliances()

        if substituted_appliances.empty:
            return

        substituted_appliances = self.add_sv_values(substituted_appliances)
        substituted_appliances = self.compare_values(substituted_appliances)

        substituted_appliances = convert_dataframe(substituted_appliances)
        self._write_df(substituted_appliances, self._writer)

    def get_substituted_appliances(self):

        # get all Measurements with type SymPowerType.SSH

        measurements = self.topology.get_input_data()[ComponentType.sym_power_sensor]
        is_substituted = [
            self.topology.get_extra_info()[i].get("_type", "") == SymPowerType.SSH
            for i in measurements["id"]
        ]
        ssh_measurements = measurements[is_substituted]

        df = pd.DataFrame()
        df["measured_object"] = ssh_measurements["measured_object"]
        df["measured_terminal_type"] = ssh_measurements["measured_terminal_type"]
        df["name"] = [
            self.topology.get_topology()[obj_id]["_extra"]["_name"]
            for obj_id in df["measured_object"]
        ]
        df["type"] = [
            self.topology.get_topology()[obj_id]["_extra"]["_type"]
            for obj_id in df["measured_object"]
        ]

        df["p_ssh"] = ssh_measurements["p_measured"]
        df["q_ssh"] = ssh_measurements["q_measured"]

        # negate if terminal type is generator
        is_generator = df["measured_terminal_type"] == MeasuredTerminalType.generator
        df.loc[is_generator, "p_ssh"] *= -1
        df.loc[is_generator, "q_ssh"] *= -1

        # drop measured_terminal_type column
        df.drop(columns=["measured_terminal_type"], inplace=True)

        return df

    def add_sv_values(self, df):
        query = """
        SELECT ?p ?q ?eq
        WHERE {

            ?power_flow cim:SvPowerFlow.Terminal ?terminal;
                        cim:SvPowerFlow.p ?p;
                        cim:SvPowerFlow.q ?q.

            ?terminal cim:Terminal.ConductingEquipment ?eq.
        }
        """
        result = self.datasource.query(query)

        for i, row in df.iterrows():

            appliance_iri = self.topology.get_extra_info()[row["measured_object"]][
                "_mrid"
            ]
            appliance_sv = result[result["eq"] == appliance_iri]
            if len(appliance_sv) == 0:
                continue

            p_sv = appliance_sv["p"].values[0]
            q_sv = appliance_sv["q"].values[0]
            df.loc[i, "p_sv"] = p_sv * 1e6
            df.loc[i, "q_sv"] = q_sv * 1e6

        return df

    def compare_values(self, df):
        df["p_diff"] = df["p_ssh"] - df["p_sv"]
        df["q_diff"] = df["q_ssh"] - df["q_sv"]
        return df
