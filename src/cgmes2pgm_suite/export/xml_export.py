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

import re

import pandas as pd
from cgmes2pgm_converter.common import CgmesDataset

from .utils import CimXmlBuilder, CimXmlObject

DEFAULT_TYPE = "rdf:Description"


class GraphToXMLExport:
    """
    A class to export a CGMES dataset graph to an CIM/XML file based on IEC 61970-552:2016.
    The urn:uuid:<uuid> format is used for all elements, as recommended for an Edition 2 producer.

    """

    def __init__(
        self,
        dataset: CgmesDataset,
        source_graph: str,
        target_path: str,
    ):
        """
        Args:
            dataset (CgmesDataset): The dataset to be converted to XML
            source_graph (str): The name of the source graph to be exported
            target_path (str): The path where the XML file will be saved
        """
        self.dataset = dataset
        self.source_graph = source_graph
        self.target_path = target_path

    def export(self):
        """
        Exports the dataset to an XML file.
        This method retrieves the graph from the dataset and writes it to an XML file at the specified target path.
        """
        with CimXmlBuilder(
            path=self.target_path, namespaces=self.dataset.get_prefixes()
        ) as file_builder:
            triples = self._get_all_triples()
            grouped = triples.groupby("s")
            model_header_subject = self._get_model_header()
            subjects = list(grouped.groups.keys())

            ordered_subjects = [model_header_subject] + [
                s for s in subjects if s != model_header_subject
            ]

            for subject in ordered_subjects:
                predicates_objects = grouped.get_group(subject)
                rdf_object = self._build_rdf_object(str(subject), predicates_objects)
                file_builder.add_object(rdf_object)

    def _build_rdf_object(
        self, subject: str, predicates_objects: pd.DataFrame
    ) -> CimXmlObject:
        mrid = self._to_urn(subject)
        rdf_object = CimXmlObject(iri=mrid, type_=DEFAULT_TYPE)
        for _, row in predicates_objects.iterrows():
            self._add_tuple_to_object(rdf_object, row)
        return rdf_object

    def _add_tuple_to_object(self, rdf_object: CimXmlObject, row: pd.Series):
        predicate = self.apply_prefix(row["p"])
        obj = row["o"]

        if predicate == "rdf:type":
            if rdf_object.type_ != DEFAULT_TYPE:
                raise ValueError(
                    f"Found multiple rdf:type definitions for {rdf_object.iri}. "
                )
            rdf_object.set_type(self.apply_prefix(obj))

        elif row["isIRI"]:
            obj_uuid = self._to_urn(str(obj))
            rdf_object.add_reference(name=predicate, iri=obj_uuid)

        else:
            rdf_object.add_attribute(name=predicate, value=str(obj))

    def _get_all_triples(self) -> pd.DataFrame:

        query_named = f"""
        SELECT ?s ?p ?o (isIRI(?o) as ?isIRI)
        FROM <{self.source_graph}>
        WHERE {{
            ?s ?p ?o .
        }}
        """
        query_default = """
        SELECT ?s ?p ?o (isIRI(?o) as ?isIRI)
        WHERE {{
            ?s ?p ?o .
        }}
        """

        if self.source_graph == "default":
            query = query_default
        else:
            query = query_named
        return self.dataset.query(query, add_prefixes=False)

    def apply_prefix(self, predicate: str) -> str:

        # predicate may be full uri, replace with prefix if available
        for prefix, uri in self.dataset.get_prefixes().items():
            if predicate.startswith(uri):
                return f"{prefix}:{predicate[len(uri):]}"

        # if no prefix found, return the full uri
        return predicate

    def _to_urn(self, iri: str) -> str:
        """
        Try to convert urls to urn:uuid format.
        Only convert urls within the same dataset.
        e.g. localhost:3030/dataset/data#_<uuid> -> urn:uuid:<uuid>
        """

        if iri.startswith(self.dataset.base_url):
            # Extract the UUID from the IRI
            # The IRI is expected to be in the format: <dataset_base_url><some_path>#_<uuid>
            match = re.search(r"#_(.+)$", iri)
            if match:
                uuid = match.group(1)
                return f"urn:uuid:{uuid}"

        return iri

    def _get_model_header(self) -> str:
        """Returns IRI of the model header (FullModel)"""

        query_default = """
        SELECT DISTINCT ?s
            WHERE {
                VALUES ?_type {md:FullModel dm:DifferenceModel}
                ?s a ?_type .
            }
        """

        query_named = f"""
        SELECT DISTINCT ?s
            FROM <{self.source_graph}>
            WHERE {{
                VALUES ?_type {{md:FullModel dm:DifferenceModel}}
                ?s a ?_type .
            }}
        """

        if self.source_graph == "default":
            query = query_default
        else:
            query = query_named

        result = self.dataset.query(query)

        if result.empty:
            raise ValueError(
                "Graph does not contain a Modelheader required for rdfxml file"
            )

        if len(result) > 1:
            raise ValueError(
                "RDF/XML export requires exactly one Modelheader (FullModel or DifferenceModel)"
            )

        return result.iloc[0]["s"]
