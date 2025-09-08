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

from cgmes2pgm_converter.common import CgmesDataset
from rdflib import Graph

TEMP_BASE_URI = "http://temp.temp/data"


class RdfXmlImport:
    """
    A simple parser for RDF/XML files that extracts triples and uploads them to a given dataset.

    Example:
        ```
        <rdf:Description rdf:about="#_1234">
            <cim:IdentifiedObject.name>Example</cim:IdentifiedObject.name>
        </rdf:Description>
        ```
        Is inserted as:
            ```
            <urn:uuid:1234> cim:IdentifiedObject.name "Example" .
            ```

        Using "http://example.org/data#_" as base IRI:
            ```
            <http://example.org/data#_1234> cim:IdentifiedObject.name "Example" .
            ```

    Attributes:
        dataset (CgmesDataset): The dataset to which the parsed triples will be added.
        target_graph (str): The name of the target graph or its uri where the triples will be inserted.
        base_iri (str): The base IRI to use for the triples. Defaults to "urn:uuid:".
            URIs can  be used as well, e.g. "http://example.org/data#_".
    """

    def __init__(
        self,
        dataset: CgmesDataset,
        target_graph: str = "default",
        base_iri: str = "urn:uuid:",
    ):
        self.dataset = dataset
        self.target_graph = target_graph
        self.base_iri = base_iri
        self._graph = Graph()

    def import_file(self, file_path: str):
        self._add_file(file_path)
        self._add_triples()

    def import_files(self, file_paths: list):
        for path in file_paths:
            self._add_file(path)
        self._add_triples()

    def import_directory(self, directory: str):
        """
        Imports all RDF/XML files from a given directory.
        Args:
            directory (str): The path to the directory containing RDF/XML files.
        """
        if not os.path.isdir(directory):
            raise ValueError(f"The provided path '{directory}' is not a directory.")

        files = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if f.lower().endswith(".xml")
        ]

        self.import_files(files)

    def _add_file(self, file_path: str):

        # The parser does not work with urn:uuid: as publicID.
        # As a Workaround the publicID is set to a temporary URI.
        # Which is then replaced in the _format_tuple method.
        self._graph.parse(file_path, format="xml", publicID=TEMP_BASE_URI)

    def _add_triples(self):
        triples = []
        for s, p, o in self._graph:
            triples.append(self._format_triple((str(s), str(p), str(o))))

        self.dataset.insert_triples(
            triples=triples,
            profile=self.target_graph,
        )
        self._graph = Graph()

    def _format_triple(self, triple: tuple[str, str, str]):
        triple_list = list(triple)
        base_iri = (
            self.base_iri + "#" if self.base_iri != "urn:uuid:" else self.base_iri
        )
        for i, item in enumerate(triple_list):

            if item.startswith(f"{TEMP_BASE_URI}#_"):
                item = item.replace(f"{TEMP_BASE_URI}#_", base_iri)

            if item.startswith("urn:uuid:") and base_iri != "urn:uuid:":
                item = item.replace("urn:uuid:", base_iri)

            if item.startswith("http:") or item.startswith("urn:uuid:"):
                item = f"<{item}>"
            else:
                item = f'"{item.strip()}"'

            # String literals may have inner quotation marks that need to be escaped, e.g.:
            # - "2" -> "2"
            # - "this "is" important"  -> "this \"is\" important"
            if i == 2 and item.startswith('"') and item.endswith('"'):
                item = '"' + item[1:-1].replace('"', '\\"') + '"'

            triple_list[i] = item

        return tuple(triple_list)
