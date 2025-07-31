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
from collections.abc import Iterator
from pathlib import Path

import pytest

from cgmes2pgm_suite.rdf_store import FusekiDockerContainer, FusekiServer


@pytest.fixture(scope="module")
def fuseki_server() -> Iterator[FusekiServer]:
    """Fixture to provide a Fuseki server instance."""

    fuseki_container = FusekiDockerContainer()
    fuseki_container.start(keep_existing_container=False)

    fuseki_url = "http://localhost:3030"
    server = FusekiServer(fuseki_url)

    if not server.ping():
        pytest.fail(f"Fuseki server at {fuseki_url} is not reachable.")

    yield server

    # Runs after all tests in the session
    fuseki_container.stop()
    fuseki_container.remove()


@pytest.fixture(scope="function")
def cwd_to_tests_dir() -> Iterator[None]:
    """Fixture to change the current working directory to /tests"""

    original_cwd = Path.cwd()
    test_root = Path(__file__).parent.parent

    # Change to test root directory
    os.chdir(test_root)

    yield

    # Change back to original working directory
    os.chdir(original_cwd)
