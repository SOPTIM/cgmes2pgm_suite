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


from cgmes2pgm_converter.common import CgmesDataset

from cgmes2pgm_suite.rdf_store import FusekiServer, RdfXmlDirectoryImport


def setup_dataset(
    name, fuseki_server: FusekiServer, data_path: str, cim_namespace: str
) -> CgmesDataset:
    """Setup a Fuseki dataset and import RDF/XML data."""

    if not fuseki_server.dataset_exists(name):
        fuseki_server.create_dataset(name)

    dataset_url = f"{fuseki_server.url}/{name}"
    dataset = CgmesDataset(
        base_url=dataset_url,
        cim_namespace=cim_namespace,
    )

    importer = RdfXmlDirectoryImport(
        dataset, target_graph="default", split_profiles=False
    )
    importer.import_directory(data_path)

    return dataset
