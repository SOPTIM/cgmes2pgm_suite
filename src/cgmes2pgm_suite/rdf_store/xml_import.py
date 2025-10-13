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
from typing import IO

from cgmes2pgm_converter.common import CgmesDataset, Profile
from rdflib import Graph, Namespace
from rdflib.parser import InputSource, create_input_source

from cgmes2pgm_suite.common.cgmes_classes import CgmesFullModel

TEMP_BASE_URI = "http://temp.temp/data"

md = Namespace("http://iec.ch/TC57/61970-552/ModelDescription/1#")
rdf = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")


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
        split_profiles (bool): If True, triples will be inserted into different graphs based on their profile.
            If False, all triples will be inserted into the target_graph. Defaults to False.
    """

    def __init__(
        self,
        dataset: CgmesDataset,
        target_graph: str = "default",
        base_iri: str = "urn:uuid:",
        split_profiles: bool = False,
    ):
        self.dataset = dataset
        self.target_graph = target_graph
        self.base_iri = base_iri
        self.split_profiles = split_profiles
        self._graph = Graph()

    def import_file(
        self,
        file_path: str,
        update_cim_namespace: bool = True,
        upload_graph: bool = True,
    ) -> list[CgmesFullModel]:
        """
        Imports an RDF/XML file.
        Args:
            file_path (str): The path to the RDF/XML file.
            update_cim_namespace (bool): If True, updates the CIM namespace in the imported graphs.
                Defaults to True.
            upload_graph (bool): If True, uploads the imported graphs to the dataset. Defaults to True.
        Returns:
            list[CgmesFullModel]: A list of CgmesFullModel instances found in the imported file.
        """

        input_source = create_input_source(
            file_path, format="xml", publicID=TEMP_BASE_URI
        )
        input_source.setSystemId(file_path)
        self._add_file(input_source)

        fm = self.read_full_model()

        if update_cim_namespace:
            self.update_cim_namespace()

        if upload_graph:
            self.upload_graph(to_profile_graph=self.split_profiles, full_models=fm)

        return fm

    def import_file_bytes(
        self,
        file_path: str,
        file: IO[bytes],
        update_cim_namespace: bool = True,
        upload_graph: bool = True,
    ) -> list[CgmesFullModel]:
        """
        Imports an RDF/XML file from a binary stream.
        Args:
            file_path (str): The path to the RDF/XML file (used for logging or error messages).
            file (IO[bytes]): A binary stream containing the RDF/XML data.
            update_cim_namespace (bool): If True, updates the CIM namespace in the imported graphs.
                Defaults to True.
            upload_graph (bool): If True, uploads the imported graphs to the dataset. Defaults to True.
        Returns:
            list[CgmesFullModel]: A list of CgmesFullModel instances found in the imported file.
        """
        input_source = create_input_source(
            source=file,
            format="xml",
            publicID=TEMP_BASE_URI,
        )
        input_source.setSystemId(file_path)
        self._add_file(input_source)

        fm = self.read_full_model()

        if update_cim_namespace:
            self.update_cim_namespace()

        if upload_graph:
            self.upload_graph(to_profile_graph=self.split_profiles, full_models=fm)
        return fm

    def _add_file(self, input: InputSource):
        # The parser does not work with urn:uuid: as publicID.
        # As a Workaround the publicID is set to a temporary URI.
        # Which is then replaced in the _format_tuple method.
        self._graph.parse(input, format="xml", publicID=TEMP_BASE_URI)

    def _add_triples(self, target_graph: Profile | str, reset_graph: bool = True):
        triples = []
        for s, p, o in self._graph:
            triples.append(self._format_triple((str(s), str(p), str(o))))

        self.dataset.insert_triples(
            triples=triples,
            profile=target_graph,
        )
        if reset_graph:
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

    def read_full_model(self):
        """
        Reads FullModel instances from the parsed RDF data.
        Returns:
            list[CgmesFullModel]: A list of CgmesFullModel instances found in the RDF data.
        """
        full_models: list[CgmesFullModel] = []
        for full_model in self._graph.subjects(
            predicate=rdf["type"], object=md["FullModel"]
        ):
            # for profile_node in importer._graph.subjects(predicate=md["FullModel"]):
            profile_dict: dict[str, str] = {
                # "rdfId": str(full_model),
            }

            profs = []
            # Get all properties for this profile node
            for p, o in self._graph.predicate_objects(subject=full_model):
                if p == md["Model.profile"]:
                    profs.append(str(o))
                else:
                    profile_dict[str(p)] = str(o)

            _full_model = CgmesFullModel(
                profile=profs,
                iri=str(full_model),
                description=profile_dict.get(str(md["Model.description"]), "Model"),
                modeling_authority_set=profile_dict.get(
                    str(md["Model.modelingAuthoritySet"]), "UNKNOWN"
                ),
                scenario_time=profile_dict.get(
                    str(md["Model.scenarioTime"]), "UNKNOWN"
                ),
            )
            full_models.append(_full_model)

        return full_models

    def update_cim_namespace(self):
        """
        Updates the CIM namespace in the dataset based on the parsed RDF data.
        Returns:
            bool: True if the CIM namespace was updated, False otherwise.
        """
        cim_namespace = dict(self._graph.namespaces()).get("cim", None)

        if cim_namespace is not None:
            if cim_namespace is None:
                raise ValueError("No CIM namespace defined in the RDF data.")

            new_cim_namespace = str(cim_namespace)
            return self.dataset.update_cim_namespace(new_cim_namespace)
        return False

    def upload_graph(
        self,
        to_profile_graph=False,
        full_models: list[CgmesFullModel] | None = None,
        drop_before_upload: bool = True,
        update_profiles: bool = True,  # TODO: check that profiles exists? prevent logging warnings of existing graph names !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    ) -> None:
        """
        Upload the parsed triples to the dataset.
        Args:
            to_profile_graph (bool): If True, triples will be inserted into different graphs based on their profile.
                If False, all triples will be inserted into the target_graph. Defaults to False.
            full_models (list[CgmesFullModel] | None): List of CgmesFullModel instances to determine profiles.
                If None, the method will attempt to read FullModel instances from the parsed RDF data.
                Defaults to None.
            drop_before_upload (bool): If True, the target graph will be dropped before uploading new triples.
                Defaults to True.
        Returns:
            None
        """
        fm = full_models if full_models is not None else self.read_full_model()
        if len(fm) == 0:
            logging.warning("Skipping graphs without full models.")
            return

        profiles = set()
        mass = set()
        for m in fm:
            mass.add(m.modeling_authority_set)
            profiles.update(m.profile)

        # get known profiles
        mas_profiles = [Profile.parse(p) for p in profiles]
        mas_profiles = [p for p in mas_profiles if p != Profile.UNKNOWN]

        if len(mas_profiles) == 0:
            unknown = [p for p in profiles if Profile.parse(p) == Profile.UNKNOWN]
            logging.warning(
                f"Skipping unknown profile in the RDF data: {", ".join(unknown)}"
            )
            return

        profiles_str = ", ".join([str(p) for p in mas_profiles])

        if not to_profile_graph:
            if drop_before_upload:
                self.dataset.drop_graph(self.target_graph)

            logging.info(f"Uploading profile(s) {profiles_str} to default graph.")
            self._add_triples(self.target_graph)
        else:

            # determine one graph_name for all profiles in all FullModels
            graph_name = self.dataset.named_graphs.determine_graph_name(
                mas_profiles, list(mass)
            )

            for p in mas_profiles:
                self.dataset.named_graphs.add(p, graph_name)

            if drop_before_upload:
                self.dataset.drop_graph(graph_name)

            logging.info(f"Uploading profile(s) {profiles_str} to graph: {graph_name}")
            self._add_triples(graph_name, reset_graph=True)
