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

import argparse
import logging
import os
import sys

from cgmes2pgm_converter import CgmesToPgmConverter
from cgmes2pgm_converter.common import Timer, Topology
from power_grid_model_io.converters import PgmJsonConverter

from cgmes2pgm_suite.common import NodeBalance
from cgmes2pgm_suite.config import ConfigReader
from cgmes2pgm_suite.export import (
    NodeBalanceExport,
    ResultTextExport,
    StesResultExcelExport,
    TextExport,
)
from cgmes2pgm_suite.measurement_simulation import MeasurementBuilder
from cgmes2pgm_suite.state_estimation import (
    StateEstimationResult,
    StateEstimationWrapper,
)


def main():
    config = _read_args()

    if config.steps.measurement_simulation:
        v_ranges, pq_ranges = config.get_measurement_simulation_ranges()
        builder = MeasurementBuilder(config.dataset, v_ranges, pq_ranges)
        builder.build_from_sv()

    extra_info, input_data = _convert_cgmes(config.dataset, config.converter_options)

    if config.steps.stes:
        state_estimation = StateEstimationWrapper(
            input_data,
            extra_info,
            config.stes_options,
        )
        results = state_estimation.run()

        if isinstance(results, StateEstimationResult):
            print(results)
            _export_run(results, config.output_folder, config)
        else:  # List of results
            _export_runs(results, config.output_folder, config)


def _read_args() -> ConfigReader:
    parser = argparse.ArgumentParser(description="Convert CGMES to PGM")
    parser.add_argument(
        "--config",
        type=str,
        help=".yaml file containing the configuration",
        required=True,
    )
    args = parser.parse_args()

    # File exists
    if not os.path.exists(args.config):
        logging.error("--config: file not found")
        sys.exit(1)
    if not os.path.isfile(args.config):
        logging.error("--config: path is not a file")
        sys.exit(1)

    config = ConfigReader(args.config)
    config.read()
    config.configure_logging()

    return config


def _convert_cgmes(ds, options):

    with Timer("Conversion", loglevel=logging.INFO):
        converter = CgmesToPgmConverter(ds, options=options)
        input_data, extra_info = converter.convert()

    return extra_info, input_data


def _export_run(
    result: StateEstimationResult, output_folder: str, config: ConfigReader
):
    os.makedirs(output_folder, exist_ok=True)

    logging.info("Exporting run %s", result.run_name)

    _export_converted_model(result, output_folder)
    if result.converged:
        _export_result_data(result, output_folder, config)


def _export_runs(
    results: list[StateEstimationResult], output_folder: str, config: ConfigReader
):
    for result in results:
        _export_run(result, os.path.join(output_folder, result.run_name), config)


def _export_converted_model(result: StateEstimationResult, output_folder: str):

    topo = Topology(result.input_data, result.extra_info, result.result_data)
    noba = NodeBalance(topo)
    noba_export = NodeBalanceExport(noba, topo)
    noba_export.print_node_balance(
        os.path.join(output_folder, "node_balance.txt"),
    )

    exporter = PgmJsonConverter(
        destination_file=os.path.join(output_folder, "pgm.json"),
    )
    exporter.save(data=result.input_data, extra_info=result.extra_info)

    exporter = TextExport(
        os.path.join(output_folder, "pgm.txt"),
        result.input_data,
        result.extra_info,
        False,
    )
    exporter.export()


def _export_result_data(
    result: StateEstimationResult, output_folder: str, config: ConfigReader
):

    topo = Topology(result.input_data, result.extra_info, result.result_data)
    noba = NodeBalance(topo)

    noba_export = NodeBalanceExport(noba, topo, result=True)
    noba_export.print_node_balance(
        os.path.join(output_folder, "node_balance_result.txt"),
    )

    exporter = ResultTextExport(os.path.join(output_folder, "pgm_result.txt"), result)

    exporter = TextExport(
        os.path.join(output_folder, "pgm_result_full.txt"),
        result.result_data,
        result.extra_info,
        True,
    )
    exporter.export()

    exporter = StesResultExcelExport(
        os.path.join(output_folder, "pgm_result.xlsx"),
        result,
        config.dataset,
        sv_comparison=True,
    )
    exporter.export()
