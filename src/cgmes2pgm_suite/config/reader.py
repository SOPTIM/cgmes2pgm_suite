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

import os
import re

import yaml
from cgmes2pgm_converter.common import (
    BranchMeasurements,
    CgmesDataset,
    ConverterOptions,
    DefaultSigma,
    IncompleteMeasurements,
    LinkAsShortLineOptions,
    MeasSub,
    MeasurementSubstitutionOptions,
    NetworkSplittingOptions,
    PassiveNodeOptions,
    QFromIOptions,
    SshSubstitutionOptions,
    UMeasurementSubstitutionOptions,
)

from cgmes2pgm_suite.measurement_simulation import (
    MeasurementRangeSet,
    MeasurementSimulationConfiguration,
)
from cgmes2pgm_suite.state_estimation import (
    PgmCalculationParameters,
    StesOptions,
)

from .config import LoggingConfiguration, Steps, SuiteConfiguration

LOG_FORMAT = "%(levelname)-8s :: %(message)s"


class SuiteConfigReader:
    """
    Class to read and parse configuration files.
    """

    def __init__(self, path: str):
        """
        Initialize the ConfigReader with the path to the configuration file.

        Args:
            path (str): Path to the configuration file.

        Raises:
            ValueError: If the configuration file is empty or not found.
        """

        self._path = path
        self._config: dict = {}

    def read(self) -> SuiteConfiguration:
        """Reads the configuration file and initializes the dataset and converter options."""
        with open(self._path, "r", encoding="UTF-8") as file:
            self._config = yaml.safe_load(file)

        if not self._config:
            raise ValueError(f"Configuration file {self._path} is empty or not found.")

        self._eval_environment_variables()

        steps = self._construct_from_dict(
            Steps,
            self._config.get("Steps", {}),
        )

        return SuiteConfiguration(
            name=self._config.get("Name", "dataset_name"),
            dataset=self._read_dataset(),
            converter_options=self._read_converter_options(),
            stes_options=self._read_stes_parameter(),
            steps=steps,
            measurement_simulation=self.get_measurement_simulation_ranges(),
            logging_config=self.get_logging_config(),
            output_folder=self._config.get("OutputFolder", ""),
            xml_file_location=self._config.get("XmlFileLocation", ""),
        )

    def get_logging_config(self) -> LoggingConfiguration:
        """Configures the logging settings for the application."""

        output_folder = self._config.get("OutputFolder", "")
        logging_config = self._config.get("Logging", {})
        level = logging_config.get("Level", "INFO")
        log_file = logging_config.get("File", "log.txt")

        if not os.path.isabs(log_file):
            log_file = os.path.join(output_folder, log_file)

        logging_config = LoggingConfiguration(
            file=log_file,
            level=level,
        )

        return logging_config

    def get_measurement_simulation_ranges(self):
        """
        Returns the measurement simulation ranges.
        """
        measurement_simulation_path = self._config.get("MeasurementSimulation", {}).get(
            "Ranges", None
        )
        if measurement_simulation_path and not os.path.isabs(
            measurement_simulation_path
        ):
            measurement_simulation_path = os.path.join(
                os.path.dirname(self._path), measurement_simulation_path
            )

        return MeasurementSimulationConfigReader(measurement_simulation_path).read()

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

        base_url = source_data["BaseUrl"]
        if source_data.get("Dataset"):
            if not base_url.endswith("/"):
                base_url += "/"
            base_url += source_data["Dataset"]

        split_profiles = source_data.get("SplitProfiles", True)

        return CgmesDataset(
            base_url=base_url,
            cim_namespace=source_data["CIM-Namespace"],
            split_profiles=split_profiles,
        )

    def _read_converter_options(self) -> ConverterOptions:
        converter_options = self._config.get("Converter", {})

        return ConverterOptions(
            only_topo_island=converter_options.get("onlyTopoIsland", False),
            topo_island_name=converter_options.get("topoIslandName", None),
            sources_from_sv=converter_options.get("sourcesFromSV", False),
            network_splitting=self._read_network_splitting_options(),
            measurement_substitution=self._read_substitution_options(),
            link_as_short_line=self._read_link_options(),
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

    def _read_link_options(self):
        converter_options = self._config.get("Converter", {})
        link_as_short_line_config = converter_options.get("LinkAsShortLine", {})

        return LinkAsShortLineOptions(
            enable=link_as_short_line_config.get("Enable", False),
            r=link_as_short_line_config.get("R", 0.01),
            x=link_as_short_line_config.get("X", 0.01),
            sigma_factor=link_as_short_line_config.get("SigmaFactor", 10),
        )

    def _read_substitution_options(self):
        converter_options = self._config.get("Converter", {})
        substitution_config = converter_options.get("MeasurementSubstitutions", {})

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


class MeasurementSimulationConfigReader:
    """
    Reads and parses a measurement simulation configuration file.
    """

    def __init__(self, config_path: str):
        """
        Args:
            config_path (str): Path to the measurement simulation configuration YAML file.
        """
        self.config_path = config_path

    def read(self) -> MeasurementSimulationConfiguration:
        """
        Reads the measurement simulation configuration file and returns a configuration object.

        Returns:
            MeasurementSimulationConfiguration: The parsed configuration.

        Raises:
            ValueError: If required fields are missing.
        """
        with open(self.config_path, "r", encoding="UTF-8") as file:
            cfg = yaml.safe_load(file)

        dict_pq = cfg.get("PowerRangesByNominalVoltage", None)
        dict_voltage = cfg.get("VoltageRangesByNominalVoltage", None)

        if dict_pq is None or dict_voltage is None:
            raise ValueError(
                "Configuration must contain 'PowerRangesByNominalVoltage' and 'VoltageRangesByNominalVoltage'."
            )

        return MeasurementSimulationConfiguration(
            seed=cfg["Seed"],
            power_ranges=MeasurementRangeSet.from_dict(dict_pq),
            voltage_ranges=MeasurementRangeSet.from_dict(dict_voltage),
        )
