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

import pytest
from cgmes2pgm_converter import CgmesToPgmConverter
from cgmes2pgm_converter.common import Profile

from cgmes2pgm_suite.config import MeasurementSimulationConfigReader
from cgmes2pgm_suite.export import GraphToXMLExport, TextExport
from cgmes2pgm_suite.measurement_simulation import (
    MeasurementBuilder,
)
from cgmes2pgm_suite.rdf_store import RdfXmlImport

from .util.data import setup_dataset


@pytest.mark.usefixtures("cwd_to_tests_dir")
@pytest.mark.parametrize("dataset_path", ["./data/conformity/MiniGrid"])
def test_measurement_consistency(fuseki_server, dataset_path):
    """Test to check if reading measurements from the default graph and from named graphs
    results in the same output.
    """

    out_dir = "out/test_measurementsim_reimport"

    dataset = setup_dataset(
        name="test_reimport_measurement",
        fuseki_server=fuseki_server,
        data_path=dataset_path,
        cim_namespace="http://iec.ch/TC57/CIM100#",
    )

    _create_measurements(dataset)

    converter = CgmesToPgmConverter(dataset)
    input_data_named, extra_info_named = converter.convert()

    # Export simulated measurements
    move_meas_to_default(out_dir, dataset)

    converter = CgmesToPgmConverter(dataset)
    input_data_default, extra_info_default = converter.convert()

    # Export files for comparison
    os.makedirs(out_dir, exist_ok=True)
    exporter = TextExport(
        path=f"{out_dir}/input_data_default.txt",
        data=input_data_default,
        extra_info=extra_info_default,
    )
    exporter.export()

    exporter = TextExport(
        path=f"{out_dir}/input_data_named.txt",
        data=input_data_named,
        extra_info=extra_info_named,
    )
    exporter.export()

    with open(f"{out_dir}/input_data_named.txt", encoding="utf-8") as f:
        content_named = f.read()
    with open(f"{out_dir}/input_data_default.txt", encoding="utf-8") as f:
        content_default = f.read()

    assert (
        content_named == content_default
    ), "Input data differs after re-import (see out directory for differences)."


def move_meas_to_default(out_dir, dataset):
    exporter = GraphToXMLExport(
        dataset=dataset,
        source_graph=dataset.graphs[Profile.OP],
        target_path=f"{out_dir}/op.xml",
    )
    exporter.export()

    exporter = GraphToXMLExport(
        dataset=dataset,
        source_graph=dataset.graphs[Profile.MEAS],
        target_path=f"{out_dir}/meas.xml",
    )
    exporter.export()

    # Re-import the measurements into default graph
    importer = RdfXmlImport(dataset, target_graph="default")
    importer.import_file(f"{out_dir}/op.xml")
    importer.import_file(f"{out_dir}/meas.xml")

    # Unset Graphs to read measurements from default graph
    dataset.graphs.pop(Profile.OP, None)
    dataset.graphs.pop(Profile.MEAS, None)


def _create_measurements(dataset):
    dataset.graphs[Profile.OP] = f"{dataset.base_url}/op"
    dataset.graphs[Profile.MEAS] = f"{dataset.base_url}/meas"

    # Run Measurement Simulation
    reader = MeasurementSimulationConfigReader(config_path="./configs/meas_ranges.yaml")
    measurement_builder = MeasurementBuilder(dataset, reader.read())
    measurement_builder.build_from_sv()
