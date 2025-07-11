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
from rdflib import Graph


class RDFXmlParser:
    """
    A simple parser for RDF/XML files that extracts triples and returns them
    as a list of tuples (subject, predicate, object).
    Attributes:
        dataset (CgmesDataset): The dataset to which the parsed triples will be added.
        target_graph (str): The name of the target graph or its uri where the triples will be inserted.
    """

    def __init__(self, dataset: CgmesDataset, target_graph: str = "default"):
        self.dataset = dataset
        self.target_graph = target_graph
        self._graph = Graph()

    def parse_file(self, file_path: str):
        self._add_file(file_path)
        self._add_triples()

    def parse_files(self, file_paths: list):
        for path in file_paths:
            self._add_file(path)
        self._add_triples()

    def _add_file(self, file_path: str):
        self._graph.parse(
            file_path, format="xml", publicID=self.dataset.base_url + "/data"
        )

    def _add_triples(self):
        triples = []
        for s, p, o in self._graph:
            triples.append(self._format_tuple((str(s), str(p), str(o))))

        self.dataset.insert_triples(
            triples=triples,
            profile=self.target_graph,
        )
        self._graph = Graph()

    def _format_tuple(self, triple: tuple[str, str, str]):
        triple_list = list(triple)
        for i, item in enumerate(triple_list):
            if item.startswith("http:") or item.startswith("urn:"):
                triple_list[i] = f"<{item}>"
            else:
                triple_list[i] = f'"{item}"'

        return tuple(triple_list)
