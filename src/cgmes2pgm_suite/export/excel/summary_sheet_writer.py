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

import logging

from .abstract_result_sheet_writer import AbstractResultSheetWriter


class SummarySheetWriter(AbstractResultSheetWriter):
    def write(self):
        worksheet = self._writer.book.add_worksheet(self._sheet_name)
        worksheet.write("B2", "State Estimation Results")

        ej_minus_3sigma = int(self._stes_result.e_j - 3 * self._stes_result.sigma_j)
        ej_plus_3sigma = int(self._stes_result.e_j + 3 * self._stes_result.sigma_j)

        logging.debug("J: %d", int(self._stes_result.j))
        logging.debug("E(J) ± 3σ: [%d; %d]", ej_minus_3sigma, ej_plus_3sigma)

        # fmt: off
        values = [
            ("n_measurements", self._stes_result.n_meas_actual),
            ("n_pseudo_measurements", self._stes_result.n_meas - self._stes_result.n_meas_actual),
            ("n_statevars", self._stes_result.n_statevars),
            ("", ""),
            ("J", int(self._stes_result.j)),
            ("E(J)", int(self._stes_result.e_j)),
            ("E(J) - 3σ", ej_minus_3sigma),
            ("E(J) + 3σ", ej_plus_3sigma),
            ("", ""),
            ("Redundancy", self._stes_result.redundancy),
            ("", ""),
            ("Bad Measurements U", len(self._stes_result.get_bad_measurements_u())),
            ("Bad Measurements P", len(self._stes_result.get_bad_measurements_p())),
            ("Bad Measurements Q", len(self._stes_result.get_bad_measurements_q())),
        ]
        # fmt: on

        col_description = 2
        col_value = 3

        start_row = 4
        row = start_row

        for description, value in values:
            worksheet.write(row, col_description, description)
            worksheet.write(row, col_value, value)
            row += 1

        # Adjust column width of col C
        worksheet.set_column(2, 2, 25)
