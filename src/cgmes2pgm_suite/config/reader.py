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
import os
import re
import sys
from dataclasses import dataclass

import yaml
from cgmes2pgm_converter.common import (
    BranchMeasurements,
    CgmesDataset,
    ConverterOptions,
    DefaultSigma,
    IncompleteMeasurements,
    MeasSub,
    MeasurementSubstitutionOptions,
    NetworkSplittingOptions,
    PassiveNodeOptions,
    Profile,
    QFromIOptions,
    SshSubstitutionOptions,
    UMeasurementSubstitutionOptions,
)

from cgmes2pgm_suite.measurement_simulation import build_ranges_from_dict
from cgmes2pgm_suite.state_estimation import (
    PgmCalculationParameters,
    StesOptions,
)

LOG_FORMAT = "%(levelname)-8s :: %(message)s"


@dataclass
class Steps:
    """Steps to be executed in the application.
    Attributes:
        measurement_simulation (bool): Whether to run the measurement simulation.
        stes (bool): Whether to run the state estimation.
    """

    measurement_simulation: bool = False
    stes: bool = True


class ConfigReader:
    """
    A class to read and parse configuration files.

    Attributes:
        dataset (CgmesDataset): Dataset configuration.
        converter_options (ConverterOptions): Converter options configuration.
        stes_options (StesOptions): State estimation options configuration.
        steps (Steps): Steps configuration.
        measurement_simulation (dict): Measurement simulation configuration.
    """

    def __init__(self, path: str):
        """
        Initialize the ConfigReader with the path to the configuration file.

        :param path: Path to the configuration file.
        """

        self.dataset: CgmesDataset = None
        self.converter_options: ConverterOptions = None
        self.stes_options: StesOptions = None
        self.steps: Steps = None
        self.output_folder: str = None
        self._measurement_simulation_path: str = None

        self._path = path
        self._config: dict = None

    def read(self):
        """Reads the configuration file and initializes the dataset and converter options."""
        with open(self._path, "r", encoding="UTF-8") as file:
            self._config = yaml.safe_load(file)

        self._eval_environment_variables()

        self.output_folder = self._config.get("OutputFolder", "")
        self.dataset = self._read_dataset()
        self.converter_options = self._read_converter_options()
        self.stes_options = self._read_stes_parameter()

        self.steps = self._construct_from_dict(
            Steps,
            self._config.get("Steps", {}),
        )

        ranges_path = self._config.get("MeasurementSimulation", {}).get("Ranges", None)
        if ranges_path is None:
            self._measurement_simulation_path = None
        elif os.path.isabs(ranges_path):
            self._measurement_simulation_path = ranges_path
        else:
            self._measurement_simulation_path = os.path.join(
                os.path.dirname(self._path), ranges_path
            )

    def configure_logging(self):
        """Configures the logging settings for the application."""

        if not self._config:
            self.read()

        # Reset logging configuration
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.handlers.clear()

        logging_config = self._config.get("Logging", None)
        level = logging_config.get("Level", "INFO") if logging_config else "INFO"

        if logging_config and "File" in logging_config:
            file_name = logging_config.get("File", "log.txt")
            os.makedirs(self.output_folder, exist_ok=True)
            logging.basicConfig(
                filename=os.path.join(self.output_folder, file_name),
                level=logging.getLevelName(level),
                format=LOG_FORMAT,
            )

            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setLevel(logging.getLevelName(level))
            stdout_handler.setFormatter(logging.Formatter(LOG_FORMAT))

            logging.getLogger().addHandler(stdout_handler)
        else:
            logging.basicConfig(
                level=logging.getLevelName(level),
                format="%(levelname)-8s :: %(message)s",
                stream=sys.stdout,
            )

    def get_measurement_simulation_ranges(self):
        """
        Returns the measurement simulation ranges.
        """
        if not self._measurement_simulation_path:
            self.read()

        with open(self._measurement_simulation_path, "r", encoding="UTF-8") as file:
            return build_ranges_from_dict(yaml.safe_load(file))

    def _eval_environment_variables(self):
        # allow base_url to be set via environment variable or command line argument
        base_url_env = os.environ.get("BASE_URL")
        if base_url_env:
            self._config["DataSource"]["BaseUrl"] = base_url_env

        # allow base_out to be set via environment variable
        base_out_env = os.environ.get("BASE_OUT")
        if base_out_env:
            self._config["BaseOut"] = base_out_env

        # if base_out is set, prepend it to the output folder
        # (make it overridable from docker compose)
        base_out = self._config.get("BaseOut")
        if base_out:
            self._config["OutputFolder"] = base_out + "/" + self._config["OutputFolder"]

    def _read_dataset(self) -> CgmesDataset:
        source_data = self._config["DataSource"]
        graph_data: dict = source_data.get("Graphs", None)

        base_url = source_data["BaseUrl"]
        if source_data.get("Dataset"):
            if not base_url.endswith("/"):
                base_url += "/"
            base_url += source_data["Dataset"]

        graphs = (
            {
                Profile.OP: base_url + graph_data.get("OP"),
                Profile.MEAS: base_url + graph_data.get("MEAS"),
            }
            if graph_data
            else None
        )

        return CgmesDataset(
            base_url=base_url,
            cim_namespace=source_data["CIM-Namespace"],
            graphs=graphs,
        )

    def _read_converter_options(self) -> ConverterOptions:
        converter_options = self._config.get("Converter", {})

        return ConverterOptions(
            only_topo_island=converter_options.get("onlyTopoIsland", False),
            topo_island_name=converter_options.get("topoIslandName", None),
            sources_from_sv=converter_options.get("sourcesFromSV", False),
            network_splitting=self._read_network_splitting_options(),
            measurement_substitution=self._read_substitution_options(),
        )

    def _read_stes_parameter(self):
        stes_config = self._config.get("Stes", {})

        pgm_parameters = self._construct_from_dict(
            PgmCalculationParameters,
            stes_config.get("PgmCalculationParameters", {}),
        )
        compute_islands_separately = stes_config.get("ComputeIslandsSeparately", False)
        compute_only_subnets = stes_config.get("ComputeOnlySubnets", [])
        reconnect_branches = stes_config.get("ReconnectBranches", False)

        return StesOptions(
            pgm_parameters=pgm_parameters,
            compute_islands_separately=compute_islands_separately,
            compute_only_subnets=compute_only_subnets,
            reconnect_branches=reconnect_branches,
        )

    def _read_network_splitting_options(self):
        converter_options = self._config.get("Converter", {})
        splitting = converter_options.get("NetworkSplitting", {})
        split_branches = self._choose_profile(splitting.get("Branches", None))
        split_substations = self._choose_profile(splitting.get("Substations", None))
        return NetworkSplittingOptions(
            enable=splitting.get("Enable", False),
            add_sources=splitting.get("AddSources", False),
            cut_branches=split_branches,
            cut_substations=split_substations,
        )

    def _read_substitution_options(self):
        converter_options = self._config.get("Converter", {})
        substitution_config = converter_options.get("MeasurementSubstitution", {})

        branch_config = substitution_config.get("BranchMeasurements", {})
        branch_measurements = BranchMeasurements(
            mirror=self._construct_from_dict(
                MeasSub,
                branch_config.get("MirrorMeasurements", {}),
            ),
            zero_cut_branch=self._construct_from_dict(
                MeasSub,
                branch_config.get("ZeroMissingMeasurements", {}),
            ),
            zero_cut_source=self._construct_from_dict(
                MeasSub,
                branch_config.get("ZeroReplacementSources", {}),
            ),
        )

        incomplete_config = substitution_config.get("IncompleteMeasurements", {})
        incomplete_measurements = IncompleteMeasurements(
            use_ssh=self._construct_from_dict(
                MeasSub,
                incomplete_config.get("UseSSHValues", {}),
            ),
            use_balance=self._construct_from_dict(
                MeasSub,
                incomplete_config.get("UseBalanceValues", {}),
            ),
        )

        return MeasurementSubstitutionOptions(
            default_sigma_pq=self._construct_from_dict(
                DefaultSigma,
                substitution_config.get("PowerFlowSigma", {}),
            ),
            use_nominal_voltages=self._construct_from_dict(
                UMeasurementSubstitutionOptions,
                substitution_config.get("UseNominalVoltages", {}),
            ),
            use_ssh=self._construct_from_dict(
                SshSubstitutionOptions,
                substitution_config.get("UseSSHValues", {}),
            ),
            passive_nodes=self._construct_from_dict(
                PassiveNodeOptions,
                substitution_config.get("PassiveNodes", {}),
            ),
            imeas_used_for_qcalc=self._construct_from_dict(
                QFromIOptions,
                substitution_config.get("ImeasUsedForQCalc", {}),
            ),
            branch_measurements=branch_measurements,
            incomplete_measurements=incomplete_measurements,
        )

    def _choose_profile(self, data):
        """
        Chooses a configuration profile.
        E. g.:
        ```
        data: {
            active: "two"
            one: ["1", "2", "3"]
            two: ["4", "5", "6"]
        }
        # returns ["4", "5", "6"]
        ```
        """
        if data is None:
            return None

        active = data.get("active")

        if not isinstance(active, (str, int)):
            raise ValueError("Invalid profile selection")
        if active:
            return data.get(active, None)

        return None

    def _dict_to_snake_case(self, params: dict):

        def to_snake_case(exp):
            return re.sub(r"(?<!^)(?=[A-Z])", "_", exp).lower()

        return {to_snake_case(k): v for k, v in params.items()}

    def _construct_from_dict(self, cls, params: dict):
        """
        Constructs an object from a dictionary.

        Converts attribute names to snake_case.
        E. g.: ApplianceType -> appliance_type
        """
        return cls(**self._dict_to_snake_case(params)) if params else cls()
