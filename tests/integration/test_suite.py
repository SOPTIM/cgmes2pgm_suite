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


import glob
import os
import shutil
from pathlib import Path

import pytest
from cgmes2pgm_converter.common import CgmesDataset

from cgmes2pgm_suite.app import _read_config, _run
from cgmes2pgm_suite.state_estimation import StateEstimationResult

# Test Passes if J < E(J) + SIGMA_J * SIGMA_THRESHOLD
SIGMA_THRESHOLD = 3


def _get_config_files():
    """Discover all YAML config files in the config directory."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs"))

    config_files = [
        os.path.relpath(path, base_dir)
        for path in glob.glob(os.path.join(base_dir, "**", "*.yaml"), recursive=True)
        if "meas_ranges" not in path
    ]
    return [
        (
            os.path.join(base_dir, rel_path),
            os.path.basename(rel_path).replace(".yaml", ""),
        )
        for rel_path in config_files
    ]


@pytest.mark.parametrize("config_path, config_name", _get_config_files())
@pytest.mark.integration
def test_full_suite(config_path, config_name, fuseki_server):

    assert os.path.isfile(config_path), f"Missing file: {config_path}"

    config_dir = os.path.dirname(config_path)
    original_dir = os.getcwd()

    try:
        os.chdir(config_dir)
        config = _read_config(config_path)

        if not _xml_files_exist(config.xml_file_location):
            pytest.skip(f"No XML files found in {config.xml_file_location}")

        _reset_output_dir(config.output_folder)
        _setup_fuseki_dataset(fuseki_server, config, config_name)

        result = _run(config)

        _validate_state_estimation(result, config, config_name)

    finally:
        os.chdir(original_dir)


def _xml_files_exist(directory) -> bool:
    """Check if any XML files exist in the given directory."""

    if not os.path.isdir(directory):
        return False

    return any(
        f.lower().endswith(".xml")
        for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
    )


def _check_result(
    result: StateEstimationResult, config_name: str, threshold=SIGMA_THRESHOLD
):
    """Ensure the state estimation result meets convergence and accuracy criteria."""
    assert result.converged, f"Convergence failed for {config_name}: {result}"

    delta = (result.j - result.e_j) / result.sigma_j

    # if j << e_j, test still passes (results better than expected)
    assert delta < threshold, f"High delta for {config_name}: {delta:.2f}"


def _reset_output_dir(output_dir: str):
    p = Path(output_dir)
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=False, exist_ok=False)


def _setup_fuseki_dataset(fuseki, config, config_name):
    """Create dataset in Fuseki and update config."""
    fuseki.create_dataset(config_name)
    config.dataset = CgmesDataset(
        base_url=f"{fuseki.url}/{config_name}",
        cim_namespace=config.dataset.cim_namespace,
        split_profiles=config.dataset.split_profiles,
    )


def _validate_state_estimation(result, config, config_name):
    """Validate state estimation result and check convergence."""
    if not getattr(config.steps, "stes", False):
        pytest.skip(f"STES step not enabled in {config_name}")

    assert result is not None, f"Got None result from {config_name}"

    tolorance = config.stes_options.pgm_parameters.bad_data_tolerance

    results = result if isinstance(result, list) else [result]
    for res in results:
        _check_result(res, config_name, tolorance)
