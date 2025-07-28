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
from cgmes2pgm_converter.common import Profile, Timer, Topology
from power_grid_model_io.converters import PgmJsonConverter

from cgmes2pgm_suite.common import NodeBalance
from cgmes2pgm_suite.config import SuiteConfigReader, SuiteConfiguration
from cgmes2pgm_suite.export import (
    GraphToXMLExport,
    NodeBalanceExport,
    ResultTextExport,
    StesResultExcelExport,
    SvProfileBuilder,
    TextExport,
)
from cgmes2pgm_suite.measurement_simulation import MeasurementBuilder
from cgmes2pgm_suite.rdf_store import FusekiDockerContainer, FusekiServer, RdfXmlImport
from cgmes2pgm_suite.state_estimation import (
    StateEstimationResult,
    StateEstimationWrapper,
)


def main():
    config = _read_config(_get_config_path())

    fuseki_container = FusekiDockerContainer()
    if config.steps.own_fuseki_container:
        fuseki_container.start(keep_existing_container=True)

    _run(config)

    if config.steps.own_fuseki_container:
        fuseki_container.stop()
        fuseki_container.remove()


def _run(config) -> StateEstimationResult | list[StateEstimationResult] | None:

    _ensure_fuseki_dataset(config)
    if config.steps.upload_xml_files:
        _upload_files(config)

    if config.steps.measurement_simulation:
        builder = MeasurementBuilder(config.dataset, config.measurement_simulation)
        builder.build_from_sv()
        _export_measurement_simulation(config)

    extra_info, input_data = _convert_cgmes(config.dataset, config.converter_options)

    if not config.steps.stes:
        return None

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

    return results


def _ensure_fuseki_dataset(config):
    fuseki = FusekiServer("http://localhost:3030")

    if not fuseki.ping():
        raise RuntimeError("Fuseki server is not running or not reachable.")

    if not fuseki.dataset_exists(config.name):
        fuseki.create_dataset(config.name)

    if not fuseki.dataset_exists(config.name):
        raise RuntimeError(
            f"Could not create dataset '{config.name}' on Fuseki server at {fuseki.url}"
        )


def _get_config_path() -> str:
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
    return args.config


def _read_config(config_path) -> SuiteConfiguration:

    reader = SuiteConfigReader(config_path)
    config = reader.read()
    config.logging_config.configure_logging()

    return config


def _upload_files(config: SuiteConfiguration):
    with Timer("Importing XML files", loglevel=logging.INFO):
        graph = "default"

        config.dataset.drop_graph(graph)
        importer = RdfXmlImport(dataset=config.dataset, target_graph=graph)

        directory = config.xml_file_location
        if not os.path.isdir(directory):
            raise ValueError(f"The provided path '{directory}' is not a directory.")

        importer.import_directory(directory)


def _convert_cgmes(ds, options):

    with Timer("Conversion", loglevel=logging.INFO):
        converter = CgmesToPgmConverter(ds, options=options)
        input_data, extra_info = converter.convert()

    return extra_info, input_data


def _export_measurement_simulation(config: SuiteConfiguration):
    op_graph = config.dataset.graphs[Profile.OP]
    meas_graph = config.dataset.graphs[Profile.MEAS]
    rdfxml_export = GraphToXMLExport(
        config.dataset,
        source_graph=op_graph,
        target_path=os.path.join(config.output_folder, "op.xml"),
    )
    rdfxml_export.export()

    if op_graph == meas_graph:
        logging.info("OP and MEAS graph are the same, op profile contains meas-profile")
        return

    rdfxml_export = GraphToXMLExport(
        config.dataset,
        source_graph=meas_graph,
        target_path=os.path.join(config.output_folder, "meas.xml"),
    )
    rdfxml_export.export()


def _export_run(
    result: StateEstimationResult, output_folder: str, config: SuiteConfiguration
):
    os.makedirs(output_folder, exist_ok=True)

    logging.info("Exporting run %s", result.run_name)

    _export_converted_model(result, output_folder)
    if result.converged:
        _export_result_data(result, output_folder, config)


def _export_runs(
    results: list[StateEstimationResult], output_folder: str, config: SuiteConfiguration
):
    for result in results:
        _export_run(
            result,
            os.path.join(output_folder, _sanitize_dir_name(result.run_name)),
            config,
        )


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
    result: StateEstimationResult, output_folder: str, config: SuiteConfiguration
):

    if not result.result_data:
        return

    topo = Topology(result.input_data, result.extra_info, result.result_data)
    noba = NodeBalance(topo)

    noba_export = NodeBalanceExport(noba, topo, result=True)
    noba_export.print_node_balance(
        os.path.join(output_folder, "node_balance_result.txt"),
    )

    exporter = ResultTextExport(os.path.join(output_folder, "pgm_result.txt"), result)
    exporter.export()

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

    if Profile.SV not in config.dataset.graphs:
        logging.warning("No SV profile url defined, skipping SV profile export")
        return

    target_graph = config.dataset.graphs[Profile.SV]
    sv_profile_builder = SvProfileBuilder(
        config.dataset,
        result,
        target_graph=target_graph,
    )
    sv_profile_builder.build(True)

    rdfxml_export = GraphToXMLExport(
        config.dataset,
        source_graph=target_graph,
        target_path=os.path.join(output_folder, "pgm_sv.xml"),
    )
    rdfxml_export.export()


INVALID_CHARS = ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]


def _sanitize_dir_name(name: str) -> str:
    for char in INVALID_CHARS:
        name = name.replace(char, "_")
    return name
