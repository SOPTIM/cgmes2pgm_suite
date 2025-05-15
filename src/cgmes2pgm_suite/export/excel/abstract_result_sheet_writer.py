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
from xlsxwriter.workbook import Worksheet

from cgmes2pgm_suite.state_estimation import StateEstimationResult

from .excel_sheet_writer import ExcelSheetWriter


class AbstractResultSheetWriter(ExcelSheetWriter):

    def __init__(
        self,
        writer: pd.ExcelWriter,
        sheet_name: str,
        stes_result: StateEstimationResult,
    ):
        super().__init__(writer, sheet_name)
        self._stes_result = stes_result

    def _format_sigmas(self, first_col: int, last_col: int, worksheet: Worksheet):
        """Formats a range of columns in a worksheet to highlight values
        that are greater or less than the bad data tolerance.
        Used to highlight sigma values larger than the bad data tolerance

        Args:
            first_col (int): The first column to format
            last_col (int): The last column to format
            worksheet (Worksheet): The worksheet to format
        """

        # TODO: Merge with _format_larger_abs_values in excel_sheet_writer.py

        worksheet.conditional_format(
            first_row=1,
            first_col=first_col,
            last_row=worksheet.dim_rowmax,
            last_col=last_col,
            options={
                "type": "cell",
                "criteria": "greater than",
                "value": self._stes_result.params.bad_data_tolerance,
                "format": self._highlight_format,
            },
        )
        worksheet.conditional_format(
            first_row=1,
            first_col=first_col,
            last_row=worksheet.dim_rowmax,
            last_col=last_col,
            options={
                "type": "cell",
                "criteria": "less than",
                "value": -self._stes_result.params.bad_data_tolerance,
                "format": self._highlight_format,
            },
        )

    def draw_vert_line(self, worksheet: Worksheet, col: int, thickness: int = 2):
        """
        Draws a vertical line in a worksheet on the right side of the specified column.
        """

        # Define the border format
        border_format = self._writer.book.add_format({"right": thickness})

        # Duplicated format is needed, because conditional_format needs type
        # however with this method iterating over all rows is not needed

        worksheet.conditional_format(
            0,
            col,
            1048575,
            col,
            {"type": "no_blanks", "format": border_format},
        )

        worksheet.conditional_format(
            0,
            col,
            1048575,
            col,
            {"type": "blanks", "format": border_format},
        )
