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
from cgmes2pgm_suite.common.cgmes_classes import CGMES2PGM_MAS
from cgmes2pgm_suite.config import SuiteConfigReader, SuiteConfiguration
from cgmes2pgm_suite.export import (
    GraphToXMLExport,
    NodeBalanceExport,
    ResultTextExport,
    StesResultExcelExport,
    SvProfileBuilder,
    TextExport,
)
from cgmes2pgm_suite.export.iri_export import extra_info_with_clean_iris
from cgmes2pgm_suite.measurement_simulation import MeasurementBuilder
from cgmes2pgm_suite.rdf_store import (
    FusekiDockerContainer,
    FusekiServer,
    RdfXmlDirectoryImport,
)
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


def _run(
    config: SuiteConfiguration,
) -> StateEstimationResult | list[StateEstimationResult] | None:

    _ensure_fuseki_dataset(config)
    if config.steps.upload_xml_files:
        _upload_files(config)
    else:
        # determine what data is located in which graph
        config.dataset.populate_named_graph_mapping()

    if config.steps.measurement_simulation:
        # put OP and MEAS profile into same graph
        separate_models = False
        builder = MeasurementBuilder(
            config.dataset,
            config.measurement_simulation,
            separate_models=separate_models,
        )
        builder.build_from_sv()
        _export_measurement_simulation(config, separate_models)

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
        for res in results:
            print(f"-----\n{res.run_name}:")
            print(res)
        _export_runs(results, config.output_folder, config)

    return results


def _ensure_fuseki_dataset(config: SuiteConfiguration):
    fuseki = FusekiServer("http://localhost:3030")

    if not fuseki.ping():
        raise RuntimeError("Fuseki server is not running or not reachable.")

    if config.steps.upload_xml_files:
        # If we upload files, we want to start with a clean dataset
        fuseki.delete_dataset(config.name)
        pass

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
        importer = RdfXmlDirectoryImport(
            dataset=config.dataset,
            target_graph=graph,
            base_iri=config.dataset.base_url,
            split_profiles=config.dataset.split_profiles,
        )

        directory = config.xml_file_location
        if not os.path.isdir(directory):
            raise ValueError(f"The provided path '{directory}' is not a directory.")

        importer.import_directory(directory)


def _convert_cgmes(ds, options):

    with Timer("Conversion", loglevel=logging.INFO):
        converter = CgmesToPgmConverter(ds, options=options)
        input_data, extra_info = converter.convert()

    return extra_info, input_data


def _export_measurement_simulation(config: SuiteConfiguration, separate_models: bool):

    rdfxml_export = GraphToXMLExport(
        config.dataset,
        source_graph=Profile.OP,
        target_path=os.path.join(config.output_folder, "op.xml"),
    )
    rdfxml_export.export()

    # if OP and MEAS are not build separately, then they are in the same graph (name)
    # and exporting both separately is not needed
    if not separate_models:
        logging.info("OP and MEAS graph are the same, op profile contains meas-profile")
        return

    rdfxml_export = GraphToXMLExport(
        config.dataset,
        source_graph=Profile.MEAS,
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

    clean_extra_info = extra_info_with_clean_iris(result.extra_info)

    topo = Topology(result.input_data, clean_extra_info, result.result_data)
    noba = NodeBalance(topo)
    noba_export = NodeBalanceExport(noba, topo)
    noba_export.print_node_balance(
        os.path.join(output_folder, "node_balance.txt"),
    )

    exporter = PgmJsonConverter(
        destination_file=os.path.join(output_folder, "pgm.json"),
    )
    exporter.save(data=result.input_data, extra_info=clean_extra_info)

    exporter = TextExport(
        os.path.join(output_folder, "pgm.txt"),
        result.input_data,
        clean_extra_info,
        False,
    )
    exporter.export()


def _export_result_data(
    result: StateEstimationResult, output_folder: str, config: SuiteConfiguration
):

    if not result.result_data:
        return

    clean_extra_info = extra_info_with_clean_iris(result.extra_info)

    topo = Topology(result.input_data, clean_extra_info, result.result_data)
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
        clean_extra_info,
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

    sv_target_graph = config.dataset.named_graphs.determine_graph_name(
        [Profile.SV], [CGMES2PGM_MAS]
    )

    sv_profile_builder = SvProfileBuilder(
        config.dataset,
        result,
        target_graph=sv_target_graph,
    )
    sv_profile_builder.build(True)

    rdfxml_export = GraphToXMLExport(
        config.dataset,
        source_graph=sv_target_graph,
        target_path=os.path.join(output_folder, "pgm_sv.xml"),
    )
    rdfxml_export.export()


INVALID_CHARS = ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]


def _sanitize_dir_name(name: str) -> str:
    for char in INVALID_CHARS:
        name = name.replace(char, "_")
    return name
