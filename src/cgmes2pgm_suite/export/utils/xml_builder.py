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

from dataclasses import dataclass, field


@dataclass
class CimXmlObject:
    """
    Represents an object within an RDF/XML file.

    Attributes:
        iri (str): The identifier (IRI) for the object.
        type_ (str): The type of the object, used as the XML tag.
        attributes (list[tuple[str, str]]): List of (name, value) attribute pairs.
        references (list[tuple[str, str]]): List of (name, iri) reference pairs.
    """

    iri: str
    type_: str
    attributes: list[tuple[str, str]] = field(default_factory=list)
    references: list[tuple[str, str]] = field(default_factory=list)

    def add_attribute(self, name: str, value: str):
        """
        Adds an attribute to the object.

        Args:
            name (str): The name of the attribute / predicate
            value (str): The value of the attribute
        """

        self.attributes.append((name, value))

    def add_reference(self, name: str, iri: str):
        """
        Adds a reference to another object.

        Args:
            name (str): The name of the reference / predicate
            iri (str): The reference of the referenced object
        Raises:
            ValueError: If the UUID format is invalid.
        """
        self.references.append((name, iri))

    def build(self) -> str:
        """
        Builds the RDF/XML representation of the object.
        Returns:
            str: The RDF/XML representation of the object.
        """
        header_indent = " " * 2
        header = f'{header_indent}<{self.type_} rdf:about="{self.iri}">'
        trailer = f"{header_indent}</{self.type_}>"

        content = self._build_content()
        content_str = "\n".join(content)

        return f"{header}\n{content_str}\n{trailer}"

    def _build_content(self) -> list[str]:
        result = []

        indent = " " * 4
        for name, attribute in self.attributes:
            result.append(f"{indent}<{name}>{attribute}</{name}>")

        for name, ref in self.references:
            result.append(f'{indent}<{name} rdf:resource="{ref}"/>')

        return result

    def set_type(self, type_: str):
        self.type_ = type_


class CimXmlBuilder:
    """
    Creates an CIM/XML file based on IEC 61970-552 standard.

    Attributes:
        path (str): The path to the CIM/XML file to be created
        namespaces (dict[str, str]): A dictionary of namespaces to be used in the CIM/XML file

    """

    def __init__(self, path: str, namespaces: dict[str, str]):
        self.path = path
        self.namespaces = namespaces
        self.file = None

    def __enter__(self):
        self.file = open(self.path, "w", encoding="utf-8")
        self._write_rdf_header()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        if not self.file:
            return

        self._write_rdf_footer()
        self.file.close()

    def add_object(self, obj: CimXmlObject):
        """
        Adds an object to the RDF/XML file.

        Args:
            obj (RdfXmlObject): The object to be added.
        """
        if not self.file:
            raise ValueError("File is not open. Use 'with' statement to open the file.")

        self.file.write(obj.build() + "\n")

    def _write_rdf_header(self):
        if not self.file:
            return

        self.file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.file.write("<rdf:RDF\n")
        for prefix, uri in self.namespaces.items():
            self.file.write(f'    xmlns:{prefix}="{uri}"\n')
        self.file.write(">\n")

    def _write_rdf_footer(self):
        if self.file:
            self.file.write("</rdf:RDF>\n")
