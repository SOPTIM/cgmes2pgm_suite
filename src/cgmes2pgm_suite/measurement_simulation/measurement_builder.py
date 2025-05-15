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

from cgmes2pgm_converter.common import CgmesDataset, Profile, Timer

from .meas_ranges import MeasurementRangeSet
from .power_measurement_builder import PowerMeasurementBuilder
from .value_source_builder import ValueSourceBuilder
from .voltage_measurement_builder import VoltageMeasurementBuilder


# pylint: disable=too-few-public-methods
class MeasurementBuilder:
    """
    Simulates measurements based on the SV-Profile in the CGMES dataset.
    The current OP- and MEAS-Profile are dropped and replaced by the simulated measurements.
    """

    def __init__(
        self,
        datasource: CgmesDataset,
        v_ranges: MeasurementRangeSet,
        pq_ranges: MeasurementRangeSet,
    ):

        if Profile.OP not in datasource.graphs:
            raise ValueError("Requires graph name for the OP profile")

        if Profile.MEAS not in datasource.graphs:
            raise ValueError("Requires graph name for the MEAS profile")

        self._datasource = datasource
        self._v_ranges = v_ranges
        self._pq_ranges = pq_ranges

    def build_from_sv(self):

        self._datasource.drop_profile(Profile.OP)
        self._datasource.drop_profile(Profile.MEAS)

        builder = ValueSourceBuilder(self._datasource)
        builder.build_from_sv()
        sources = builder.get_sources()

        builder = VoltageMeasurementBuilder(
            self._datasource,
            self._v_ranges,
            sources,
        )
        with Timer("Building Voltage Measurements", loglevel=logging.INFO):
            builder.build_from_sv()

        builder = PowerMeasurementBuilder(
            self._datasource,
            self._pq_ranges,
            sources,
        )
        with Timer("Building Power Measurements", loglevel=logging.INFO):
            builder.build_from_sv()
