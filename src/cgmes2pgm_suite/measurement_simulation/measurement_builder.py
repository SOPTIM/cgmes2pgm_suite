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
        separate_models: bool = False,
    ):

        if separate_models:
            self._model_info_op = CgmesFullModel(
                profile=["http://iec.ch/TC57/ns/CIM/Operation/4.0"]
            )
            self._model_info_meas = CgmesFullModel(
                profile=["http://iec.ch/TC57/ns/CIM/OperationMeas/4.0"]
            )
        else:
            self._model_info_op = CgmesFullModel(
                profile=[
                    "http://iec.ch/TC57/ns/CIM/Operation/4.0",
                    "http://iec.ch/TC57/ns/CIM/OperationMeas/4.0",
                ]
            )
            self._model_info_meas = None

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

        self._init_graphs_for_measurements()

        [
            self._datasource.insert_triples(self._model_info_op.to_triples(), pr)
            for pr in self._to_graph(Profile.OP)
        ]

        if self._model_info_meas is not None:
            [
                self._datasource.insert_triples(self._model_info_meas.to_triples(), pr)
                for pr in self._to_graph(Profile.MEAS)
            ]

    def _init_graphs_for_measurements(self):
        # determine profiles in OP FullModel
        profiles = [Profile.parse(p) for p in self._model_info_op.profile]
        # determine graph name for these profiles
        graph_name = self._datasource.named_graphs.determine_graph_name(
            [p.profile for p in profiles],
            [self._model_info_op.modeling_authority_set],
        )
        # add same graph name for above profiles
        for p in profiles:
            self._datasource.named_graphs.add(p, graph_name)

        # do the same for MEAS FullModel if it exists
        if self._model_info_meas is not None:
            profiles = [Profile.parse(p) for p in self._model_info_meas.profile]
            graph_name = self._datasource.named_graphs.determine_graph_name(
                [p.profile for p in profiles],
                [self._model_info_meas.modeling_authority_set],
            )
            for p in profiles:
                self._datasource.named_graphs.add(p, graph_name)

    def _to_graph(self, profile: Profile) -> list[Profile | str]:
        to_graph: list[Profile | str] = [profile]
        if not self._datasource.split_profiles:
            to_graph.append(self._datasource.named_graphs.default_graph)

        return to_graph
