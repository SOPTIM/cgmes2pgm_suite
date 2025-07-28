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
import sys
from dataclasses import dataclass
from pathlib import Path

from cgmes2pgm_converter.common import (
    CgmesDataset,
    ConverterOptions,
)

from cgmes2pgm_suite.measurement_simulation import MeasurementSimulationConfiguration
from cgmes2pgm_suite.state_estimation import (
    StesOptions,
)


@dataclass
class Steps:
    """Steps to be executed in the application.
    Attributes:
        upload_xml_files (bool): Whether to upload XML files.
            Default is False.
        measurement_simulation (bool): Whether to run the measurement simulation.
            Default is False.
        stes (bool): Whether to run the state estimation.
            Default is True.
    """

    upload_xml_files: bool = False
    measurement_simulation: bool = False
    stes: bool = True


@dataclass
class LoggingConfiguration:
    """Configuration for logging.

    Attributes:
        file (str): Path to the log file. If empty, logs will be printed to stdout.
        level (str): Logging level (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR').
        format (str): Logging format string.
    """

    file: str = ""
    level: str = "INFO"
    format: str = "%(levelname)-8s :: %(message)s"

    def configure_logging(self):
        """Configures the logging based on the provided level and format."""

        # Reset logging configuration
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.handlers.clear()

        if self.file.strip() != "":
            self._log_to_file()
            return

        logging.basicConfig(
            level=self.level,
            format=self.format,
            stream=sys.stdout,
        )

    def _log_to_file(self):
        output_folder = Path(self.file).parent
        os.makedirs(output_folder, exist_ok=True)

        logging.basicConfig(
            filename=self.file,
            level=logging.getLevelName(self.level),
            format=self.format,
        )

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.getLevelName(self.level))
        stdout_handler.setFormatter(logging.Formatter(self.format))
        logging.getLogger().addHandler(stdout_handler)


@dataclass
class SuiteConfiguration:
    """
    Configuration to run cgmes2pgm_suite as an application.

    Attributes:
        dataset (CgmesDataset): Dataset configuration.
        converter_options (ConverterOptions): Converter options configuration.
        stes_options (StesOptions): State estimation options configuration.
        steps (Steps): Steps configuration.
        measurement_simulation (MeasurementSimulationConfiguration):
            Measurement simulation configuration.
        output_folder (str): Output folder for results.
        xml_file_location (str): Directory of the XML files to import (optional).
            All xml files in this directory will be imported.
            Import needs to be enabled in the steps configuration.
    """

    dataset: CgmesDataset
    converter_options: ConverterOptions
    stes_options: StesOptions
    steps: Steps
    measurement_simulation: MeasurementSimulationConfiguration
    logging_config: LoggingConfiguration
    output_folder: str
    xml_file_location: str = ""
