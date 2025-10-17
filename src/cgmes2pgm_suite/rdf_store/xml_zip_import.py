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

import zipfile
from typing import BinaryIO

from cgmes2pgm_converter.common import CgmesDataset

from cgmes2pgm_suite.rdf_store.xml_import import RdfXmlImport

TEMP_BASE_URI = "http://temp.temp/data"


class RdfXmlZipImport:
    """
    A class to handle the import of RDF/XML files from a ZIP archive.
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

    def import_zip(
        self,
        file: str,
        update_cim_namespace: bool = True,
        upload_graph: bool = True,
    ) -> list[RdfXmlImport]:
        """
        Imports RDF/XML files from a ZIP archive.
        Args:
            file (str): The path to the ZIP file containing RDF/XML files.
            update_cim_namespace (bool): If True, updates the CIM namespace in the imported graphs.
                Defaults to True.
            upload_graph (bool): If True, uploads the imported graphs to the dataset. Defaults to True.
        Returns:
            list[RdfXmlImport]: A list of RdfXmlImport instances used for the import.
        """

        importer = self._import(file)
        if update_cim_namespace:
            for imp in importer:
                updated = imp.update_cim_namespace()
                if updated:
                    break

        if upload_graph:
            for imp in importer:
                imp.upload_graph(to_profile_graph=self.split_profiles)

        return importer

    def import_zip_binary(
        self,
        zip_data: BinaryIO,
        filename: str,
        update_cim_namespace: bool = True,
        upload_graph: bool = True,
    ) -> list[RdfXmlImport]:
        """
        Imports RDF/XML files from a ZIP archive provided as binary data.
        Args:
            zip_data (BinaryIO): A binary stream containing the ZIP data.
            filename (str): The name of the ZIP file (used for logging or error messages).
            update_cim_namespace (bool): If True, updates the CIM namespace in the imported graphs.
                Defaults to True.
            upload_graph (bool): If True, uploads the imported graphs to the dataset. Defaults to True.
        Returns:
            list[RdfXmlImport]: A list of RdfXmlImport instances used for the import.
        """
        from io import BytesIO

        file_bytes = BytesIO(zip_data.read())

        importer = self._import(file_bytes)
        if update_cim_namespace:
            for imp in importer:
                updated = imp.update_cim_namespace()
                if updated:
                    break

        if upload_graph:
            for imp in importer:
                imp.upload_graph(to_profile_graph=self.split_profiles)

        return importer

    def _import(self, file: str | BinaryIO) -> list[RdfXmlImport]:
        importer_list: list[RdfXmlImport] = []

        if self.split_profiles:
            with zipfile.ZipFile(file) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".xml"):
                        # use separate importer for each file to avoid mixing graphs
                        importer = RdfXmlImport(
                            dataset=self.dataset,
                            target_graph=self.target_graph,
                            base_iri=self.base_iri,
                            split_profiles=True,
                        )
                        importer.import_file_bytes(
                            file=zf.open(name),
                            file_path=name,
                            upload_graph=False,
                            update_cim_namespace=False,
                        )
                        importer_list.append(importer)
        else:
            importer = RdfXmlImport(
                dataset=self.dataset,
                target_graph=self.target_graph,
                base_iri=self.base_iri,
                split_profiles=False,
            )
            with zipfile.ZipFile(file) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".xml"):
                        importer.import_file_bytes(
                            file=zf.open(name),
                            file_path=name,
                            upload_graph=False,
                            update_cim_namespace=False,
                        )
            importer_list.append(importer)

        return importer_list
