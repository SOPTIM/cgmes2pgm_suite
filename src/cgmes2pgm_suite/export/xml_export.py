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

import pandas as pd
from cgmes2pgm_converter.common import CgmesDataset, Profile

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
        source_graph: Profile | str | list[str],
        target_path: str,
    ):
        """
        Args:
            dataset (CgmesDataset): The dataset to be converted to XML
            source_graph (Profile|str|list[str]): The name of the source graph to be exported
            target_path (str): The path where the XML file will be saved

        `source_graph` can be a Profile (in which case all graphs for the profile are used),
        a single graph IRI (str) or a list of graph IRIs (list[str]). In case of multiple graphs,
        all graphs are merged into one XML file. However, the export requires exactly one
        ModelHeader (FullModel or DifferenceModel) in the merged graphs. Therefore, if multiple graphs
        are provided, the ModelHeader is read only from the first graph in the list.
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

            # Get all FullModel triples
            full_model_triples = triples[
                triples["o"].str.contains("FullModel", na=False)
            ]
            full_model_ids = full_model_triples["s"].tolist()

            subjects = list(grouped.groups.keys())

            # use only the first FullModel if multiple are present, filter out the others
            ordered_subjects = [model_header_subject] + [
                s for s in subjects if s not in full_model_ids
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
            obj_uuid = self._to_urn(str(obj), is_reference=True)
            rdf_object.add_reference(name=predicate, iri=obj_uuid)

        else:
            rdf_object.add_attribute(name=predicate, value=str(obj))

    def _get_all_triples(self) -> pd.DataFrame:

        query_named = f"""
        SELECT ?s ?p ?o (isIRI(?o) as ?isIRI)
        WHERE {{
            VALUES ?g {{ $SOURCE_GRAPHS }}
            GRAPH ?g {{
                ?s ?p ?o .
            }}
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
            query = self._named_query(query_named)

        return self.dataset.query(query, add_prefixes=False)

    def apply_prefix(self, predicate: str) -> str:

        # predicate may be full uri, replace with prefix if available
        for prefix, uri in self.dataset.get_prefixes().items():
            if predicate.startswith(uri):
                return f"{prefix}:{predicate[len(uri):]}"

        # if no prefix found, return the full uri
        return predicate

    def _to_urn(self, iri: str, is_reference=False) -> str:
        """
        Replacing "{base_uri}#" with "urn:uuid:" would be nice, but only
        works if the UUID is valid, otherwise it potentially produces
        validation errors in other places, therefore remove the base_uri
        but keep the "#_" for references. If the IRI already has a urn:uuid
        format then keep it as is (assuming it is correct, or maybe was corrected
        elsewhere).
        Maybe later we can switch to mapping to urn:uuid again,
        e.g. localhost:3030/dataset/data#_<uuid> -> urn:uuid:<uuid>
        """

        if iri.startswith(self.dataset.base_url):
            return iri.replace(
                self.dataset.base_url + "#", "#_" if is_reference else ""
            )
        elif (
            iri.startswith("urn:uuid:")
            or iri.startswith("http")
            or iri.startswith("#_")
        ):
            # could be some other reference, e.g. 'http://iec.ch/TC57/CIM100#UnitSymbol.V' -> keep as is
            return iri
        else:
            return f"#_{iri}" if is_reference else iri

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
            WHERE {{
                VALUES ?g {{ $SOURCE_GRAPHS }}
                GRAPH ?g {{
                    VALUES ?_type {{md:FullModel dm:DifferenceModel}}
                    ?s a ?_type .
                }}
            }}
        """

        if self.source_graph == "default":
            query = query_default
        else:
            query = self._named_query(query_named, only_one_graph=True)

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

    def _named_query(self, query_named: str, only_one_graph: bool = False) -> str:
        args = {"$SOURCE_GRAPHS": ""}
        if isinstance(self.source_graph, list):
            sg = self.source_graph
            if only_one_graph and len(self.source_graph) > 1:
                sg = [self.source_graph[0]]
            args["$SOURCE_GRAPHS"] = " ".join(f"<{g}>" for g in sg)
        elif isinstance(self.source_graph, Profile):
            sg = self.dataset.named_graphs.get(self.source_graph)
            if only_one_graph and len(sg) > 1:
                sg = [list(sg)[0]]
            args["$SOURCE_GRAPHS"] = " ".join(f"<{g}>" for g in sg)
        elif isinstance(self.source_graph, str):
            args["$SOURCE_GRAPHS"] = f"<{self.source_graph}>"
        else:
            raise ValueError(
                f"Invalid source_graph type: {type(self.source_graph)}. Must be Profile, str or list of str."
            )
        return self.dataset.format_query(query_named, args)
