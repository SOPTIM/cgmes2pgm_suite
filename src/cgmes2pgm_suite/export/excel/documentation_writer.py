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

from cgmes2pgm_converter.common import SymPowerType, VoltageMeasType
from xlsxwriter.workbook import Worksheet

from .abstract_result_sheet_writer import AbstractResultSheetWriter


class DocSheetWriter(AbstractResultSheetWriter):

    def write(self):
        worksheet = self._writer.book.add_worksheet(self._sheet_name)

        self.write_value_type_desc(worksheet, 1, 1)
        self.write_power_meas_type_desc(worksheet, 1, 12)

    def write_power_meas_type_desc(
        self,
        worksheet: Worksheet,
        start_row: int,
        start_col: int,
    ):

        worksheet.write(start_row, start_col, "Types in Power-Meas")

        row = start_row + 2
        for meas_type in SymPowerType:
            worksheet.write(row, start_col + 1, meas_type.value)
            worksheet.write(row, start_col + 2, meas_type.doc())
            row += 1

        row += 3
        worksheet.write(row, start_col, "Types in Nodes")
        row += 2
        for meas_type in VoltageMeasType:
            worksheet.write(row, start_col + 1, meas_type.value)
            worksheet.write(row, start_col + 2, meas_type.doc())
            row += 1

        # Adjust column width
        worksheet.set_column(start_col + 1, start_col + 1, 20)

    def write_value_type_desc(
        self, worksheet: Worksheet, start_col: int, start_row: int
    ):

        types = [
            ("[p/q/u]_meas", "Measured Value"),
            ("[p/q/u]_pgm", "Estimation Result from PGM"),
            ("[p/q/u]_sv", "Value from SV-Profile"),
            (
                "deviation_[p/q/u]",
                "Deviation of Estimation Result from Measured Value relative to Sigma",
            ),
            ("", "Deviation > 3σ is highlighted red as discrepancy"),
        ]

        worksheet.write(start_row, start_col, "Column Types")
        row = start_row + 2
        for type_name, desc in types:
            worksheet.write(row, start_col + 1, type_name)
            worksheet.write(row, start_col + 2, desc)
            row += 1

        # Adjust column width
        worksheet.set_column(start_col + 1, start_col + 1, 20)
