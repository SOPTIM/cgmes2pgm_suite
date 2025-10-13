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

from cgmes2pgm_suite.common import CgmesFullModel

from .meas_ranges import MeasurementSimulationConfiguration
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
        config: MeasurementSimulationConfiguration,
        model_info_op: CgmesFullModel | None = None,
        model_info_meas: CgmesFullModel | None = None,
    ):

        if Profile.OP not in datasource.graphs:
            raise ValueError("Requires graph name for the OP profile")

        if Profile.MEAS not in datasource.graphs:
            raise ValueError("Requires graph name for the MEAS profile")

        if (
            datasource.graphs[Profile.MEAS] == datasource.graphs[Profile.OP]
            and model_info_meas is not None
        ):
            raise ValueError(
                "Cannot use separate model info for OP and MEAS profiles if they share the same graph."
            )

        self._model_info_op = model_info_op or CgmesFullModel(
            profile=["http://iec.ch/TC57/ns/CIM/Operation/4.0"]
        )
        self._model_info_meas = model_info_meas or CgmesFullModel(
            profile=["http://iec.ch/TC57/ns/CIM/Operation/4.0"]
        )

        self._datasource = datasource
        self._config = config

    def build_from_sv(self):

        self._datasource.drop_profile(Profile.OP)
        self._datasource.drop_profile(Profile.MEAS)

        self._build_model_info()

        builder = ValueSourceBuilder(self._datasource)
        builder.build_from_sv()
        sources = builder.get_sources()

        builder = VoltageMeasurementBuilder(
            self._datasource,
            self._config.voltage_ranges,
            sources,
        )
        with Timer("Building Voltage Measurements", loglevel=logging.INFO):
            builder.build_from_sv()

        builder = PowerMeasurementBuilder(
            self._datasource,
            self._config.power_ranges,
            sources,
        )
        with Timer("Building Power Measurements", loglevel=logging.INFO):
            builder.build_from_sv()

    def _build_model_info(self):
        """
        Builds the model information for the OP and MEAS profiles.
        """

        self._datasource.insert_triples(self._model_info_op.to_triples(), Profile.OP)

        if self._datasource.graphs[Profile.MEAS] == self._datasource.graphs[Profile.OP]:
            return

        self._datasource.insert_triples(
            self._model_info_meas.to_triples(), Profile.MEAS
        )
