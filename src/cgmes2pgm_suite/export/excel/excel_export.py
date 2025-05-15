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

import pandas as pd
from cgmes2pgm_converter.common import CgmesDataset

from cgmes2pgm_suite.state_estimation import StateEstimationResult

from .branch_sheet_writer import Branch2SheetWriter, Branch3SheetWriter
from .documentation_writer import DocSheetWriter
from .meas_sheet_writer import MeasSheetWriter
from .node_sheet_writer import NodeSheetWriter
from .summary_sheet_writer import SummarySheetWriter
from .sv_comparison_sheet_writer import SvFlowCompWriter, SvVoltageCompWriter


class StesResultExcelExport:
    def __init__(
        self,
        path: str,
        result: StateEstimationResult,
        datasource: CgmesDataset,
        sv_comparison=False,
    ):
        self._path = path
        self._result = result
        self._datasource = datasource
        self._sv_comparison = sv_comparison

    def export(self):

        if not self._result.converged:
            logging.warning(
                "Excel-Export not possible, state estimation did not converge"
            )
            return False

        try:
            with pd.ExcelWriter(self._path, engine="xlsxwriter") as writer:
                SummarySheetWriter(writer, "Summary", self._result).write()
                NodeSheetWriter(writer, "Nodes", self._result, self._datasource).write()
                Branch2SheetWriter(writer, "Branches", self._result).write()
                Branch3SheetWriter(writer, "Branches3", self._result).write()
                MeasSheetWriter(
                    writer, "Power-Meas", self._result, self._datasource
                ).write()

                if self._sv_comparison:
                    SvVoltageCompWriter(
                        writer, "SV Comparison Nodes", self._result, self._datasource
                    ).write()
                    SvFlowCompWriter(
                        writer, "SV Comparison Branches", self._result, self._datasource
                    ).write()
                DocSheetWriter(writer, "Documentation", self._result).write()

                return True
        except Exception as e:
            logging.error("Error during export: %s", e)
            return False
