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

from abc import abstractmethod

import pandas as pd
from xlsxwriter.workbook import Worksheet


class ExcelSheetWriter:
    def __init__(
        self,
        writer: pd.ExcelWriter,
        sheet_name: str,
    ):
        self._writer = writer
        self._sheet_name = sheet_name
        self._highlight_format = writer.book.add_format({"bg_color": "#FFC7CE"})

    @abstractmethod
    def write(self):
        raise NotImplementedError

    def _write_df(
        self,
        df: pd.DataFrame,
        writer: pd.ExcelWriter,
    ) -> Worksheet:
        """Writes a DataFrame to an Excel sheet, containing a header row and an autofilter
        The first column is formatted as an id column with a right border

        Args:
            df (pd.DataFrame): The DataFrame to write
            writer (pd.ExcelWriter): The ExcelWriter to write to

        Returns:
            Worksheet: The worksheet that was written to. Can be used for further formatting
        """

        df.to_excel(
            writer,
            sheet_name=self._sheet_name,
            index=False,
            startrow=0,
            startcol=0,
            header=True,
            freeze_panes=(1, 0),
        )
        worksheet = writer.sheets[self._sheet_name]
        worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

        # Adjust column widths
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col))
            worksheet.set_column(i, i, max_len + 5)

        # Format Header
        header_format = writer.book.add_format(
            {"bold": True, "align": "center", "fg_color": "#D7E4BC", "bottom": 2}
        )
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)

        # Format id row
        id_format = writer.book.add_format({"right": 2})
        worksheet.set_column(0, 0, None, id_format)

        return worksheet

    def _create_border(self, worksheet: Worksheet, col: int):
        """Creates vertical separation line between two columns

        Args:
            col (int): border is created between col and col+1
            worksheet (Worksheet): Worksheet
        """

        border_format = self._writer.book.add_format({"right": 2})

        worksheet.set_column(col, col, None, border_format)
        worksheet.autofit()

    def _format_larger_abs_values(
        self, first_col: int, last_col: int, worksheet: Worksheet, threshold: float
    ):

        worksheet.conditional_format(
            first_row=1,
            first_col=first_col,
            last_row=worksheet.dim_rowmax,
            last_col=last_col,
            options={
                "type": "cell",
                "criteria": "greater than",
                "value": threshold,
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
                "value": -threshold,
                "format": self._highlight_format,
            },
        )
