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


import importlib.resources as res
import logging
from enum import StrEnum
from importlib.resources.abc import Traversable
from time import sleep
from typing import cast

import docker
import requests
from docker.models.containers import Container


class FusekiDatasetType(StrEnum):
    MEM = "mem"
    TDB = "tdb"
    TDB1 = "tdb1"
    TDB2 = "tdb2"


class FusekiServer:
    """
    A class to configure and manage a Fuseki server.
    """

    def __init__(self, url: str):
        self.url = url

    def ping(self) -> bool:
        try:
            response = requests.get(f"{self.url}/$/ping", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def dataset_exists(self, dataset_name: str) -> bool:
        try:
            response = requests.get(f"{self.url}/$/datasets/{dataset_name}", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def create_dataset(
        self, dataset_name: str, db_type: FusekiDatasetType = FusekiDatasetType.MEM
    ) -> bool:
        payload = {"dbName": dataset_name, "dbType": db_type.value}
        try:
            response = requests.post(f"{self.url}/$/datasets", data=payload, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False


DOCKER_FILE_PATH = "resources/docker"
IMAGE_NAME = "fuseki-server"
CONTAINER_NAME = "fuseki_container"


class FusekiDockerContainer(FusekiServer):

    def __init__(self, port: int = 3030):
        self.port = port
        self.client = docker.from_env()
        self.container: Container | None = None
        super().__init__(f"http://localhost:{self.port}")

    def start(self, replace_existing_container: bool = False):
        if self.container is not None:
            raise RuntimeError("Container is already running.")

        images = self.client.images.list()
        image_names = [image.tags[0] for image in images if image.tags]
        if f"{IMAGE_NAME}:latest" not in image_names:
            logging.info("Building Fuseki Docker image...")
            self.build_image()

        if self.client.containers.list(filters={"name": CONTAINER_NAME}, all=True):
            if self._handle_existing_container(replace_existing_container):
                return

        logging.info("Starting Fuseki Docker container on port %d...", self.port)
        self.container = cast(
            Container,
            self.client.containers.run(
                image=IMAGE_NAME,
                name=CONTAINER_NAME,
                ports={"3030/tcp": self.port},
                detach=True,
            ),
        )
        self._wait_for_startup()

    def _handle_existing_container(self, replace_existing_container: bool) -> bool:
        existing_container = self.client.containers.get(CONTAINER_NAME)
        existing_container.stop()
        if replace_existing_container:
            logging.info("Stopping existing Fuseki container: %s", CONTAINER_NAME)
            self.container = existing_container
            self.container.start()
            self._wait_for_startup()
            return True
        existing_container.remove(force=True)
        return False

    def stop(self):
        if self.container is not None:
            self.container.stop()

    def remove(self):
        if self.container is not None:
            self.container.remove(force=True)
            self.container = None

    def build_image(self):
        if self.container is not None:
            raise RuntimeError("Container is already running. Stop it before building.")

        traversable = self.dockerfile_traversable()
        with res.as_file(traversable) as dockerfile_path:
            self.client.images.build(path=str(dockerfile_path), tag=IMAGE_NAME)

    def dockerfile_traversable(self) -> Traversable:
        """Get the absolute path to the Dockerfile."""
        return res.files("cgmes2pgm_suite").joinpath(DOCKER_FILE_PATH)

    def _wait_for_startup(self, timeout: int = 5):
        """Wait for the Fuseki server to start."""
        for _ in range(timeout):
            if self.ping():
                return
            sleep(1)

        raise RuntimeError(f"Fuseki server did not start within {timeout} seconds.")
