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

from cgmes2pgm_suite.common.cgmes_classes import CgmesFullModel
from cgmes2pgm_suite.rdf_store.xml_import import RdfXmlImport
from cgmes2pgm_suite.rdf_store.xml_zip_import import RdfXmlZipImport

TEMP_BASE_URI = "http://temp.temp/data"


class RdfXmlDirectoryImport:
    """
    A class to handle the import of RDF/XML files from a directory.
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

    def import_directory(self, directory: str) -> list[CgmesFullModel]:
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
            if f.lower().endswith(".xml") or f.lower().endswith(".zip")
        ]

        fm: list[CgmesFullModel] = []

        if self.split_profiles:
            for file in files:
                xml_importers: list[RdfXmlImport] = []
                if file.lower().endswith(".zip"):
                    importer = self._importer_zip(self.split_profiles)
                    xml_importers += importer.import_zip(
                        file, update_cim_namespace=False, upload_graph=False
                    )

                elif file.lower().endswith(".xml"):
                    importer = self._importer_xml(self.split_profiles)
                    importer.import_file(
                        file, upload_graph=False, update_cim_namespace=False
                    )
                    xml_importers.append(importer)

                fm += self._upload_files(xml_importers, drop_before_upload=True)
        else:
            importer_xml = self._importer_xml(self.split_profiles)
            importer_zip = self._importer_zip(self.split_profiles)
            fm: list[CgmesFullModel] = []
            for file in files:
                xml_importers: list[RdfXmlImport] = []
                if file.lower().endswith(".zip"):
                    xml_importers += importer_zip.import_zip(
                        file, update_cim_namespace=False, upload_graph=False
                    )
                elif file.lower().endswith(".xml"):
                    importer_xml.import_file(
                        file, update_cim_namespace=False, upload_graph=False
                    )
                    xml_importers.append(importer_xml)

                fm += self._upload_files(xml_importers)

        return fm

    def _upload_files(
        self, importers: list[RdfXmlImport], drop_before_upload: bool = False
    ):
        fms: list[CgmesFullModel] = []
        updated = False
        for imp in importers:
            if not updated:
                updated = imp.update_cim_namespace()

            fm = imp.read_full_model()
            imp.upload_graph(
                to_profile_graph=self.split_profiles,
                full_models=fm,
                drop_before_upload=drop_before_upload,
            )
            fms += fm

        return fms

    def _importer_xml(self, split_profiles: bool):
        return RdfXmlImport(
            dataset=self.dataset,
            target_graph=self.target_graph,
            base_iri=self.base_iri,
            split_profiles=split_profiles,
        )

    def _importer_zip(self, split_profiles: bool):
        return RdfXmlZipImport(
            dataset=self.dataset,
            target_graph=self.target_graph,
            base_iri=self.base_iri,
            split_profiles=split_profiles,
        )
