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


import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _format_current_time() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(sep="T")
        .replace("+00:00", "Z")
    )


@dataclass
class CgmesFullModel:
    """Represents the Model Header of an CGMES Profile.

    Attributes:
        profile (str): Profile Type (URN/URI)
            e. g. http://entsoe.eu/CIM/StateVariables/4/1
        iri (str): A unique identifier for the model. Typically an URN starting with "urn:uuid:"
        description (str): Description of the model (free text)
        version (int): Version of the model
        modeling_authority_set (str): The authority that created the model
        dependent_on (list[str]): FullModel URN/URIs of the dependent profiles
        scenario_time (str): The time of the scenario in ISO 8601 format
        created (str): The creation time of the model in ISO 8601 format
    """

    profile: list[str]
    iri: str = field(default_factory=lambda: f"urn:uuid:{uuid.uuid4()}")
    description: str = "Model"
    version: int = 1
    modeling_authority_set: str = "CGMES2PGM"
    dependent_on: list[str] = field(default_factory=list)
    scenario_time: str = field(default_factory=_format_current_time)
    created: str = field(default_factory=_format_current_time)

    def to_triples(self) -> list[tuple[str, str, str]]:
        """
        Convert the CgmesFullModel instance to RDF triples.

        Returns:
            list[tuple[str, str, str]]: A list of RDF triples representing the model
        """

        prefix = "md:Model."
        type_ = "<http://iec.ch/TC57/61970-552/ModelDescription/1#FullModel>"

        formatted_iri = f"<{self.iri}>"

        triples = [
            (formatted_iri, "rdf:type", type_),
            (formatted_iri, f"{prefix}scenarioTime", f'"{self.scenario_time}"'),
            (formatted_iri, f"{prefix}created", f'"{self.created}"'),
            (formatted_iri, f"{prefix}description", f'"{self.description}"'),
            (formatted_iri, f"{prefix}version", f'"{self.version}"'),
            *[
                (formatted_iri, f"{prefix}profile", f'"{profile}"')
                for profile in self.profile
            ],
            (
                formatted_iri,
                f"{prefix}modelingAuthoritySet",
                f'"{self.modeling_authority_set}"',
            ),
        ]
        for uri in self.dependent_on:
            triples.append((formatted_iri, f"{prefix}dependentOn", f"<{uri}>"))
        return triples
