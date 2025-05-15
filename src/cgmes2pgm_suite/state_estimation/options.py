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
class PgmCalculationParameters:
    """Parameters for the PGM calculation.

    Attributes:
        threads (int): Number of threads to use for the calculation.
            -1 means no threading, 0 means use all available threads.
        max_iter (int): Maximum number of iterations for the calculation.
        error_tolerance (float): Tolerance for the error in the calculation.
        bad_data_tolerance (int): Tolerance for bad data in the calculation.
    """

    threads: int = -1
    max_iterations: int = 100
    error_tolerance: float = 1e-6
    bad_data_tolerance: int = 3


@dataclass
class StesOptions:
    """Options for the state estimation process.

    Attributes:
        pgm_parameters (PgmCalculationParameters): Parameters for the PGM calculation.
        compute_islands_separately (bool): Whether to compute islands separately.
            The state estimation will be performed for each existing source in the network.
            All other sources will be set to zero.
        compute_only_subnets (list): List of subnets to compute.
            Names of the subnets to compute.
        reconnect_branches (bool): Whether to reconnect branches.
            If the network has been split, trying to reconnect branches
            until State Estimation diverges.
    """

    pgm_parameters: PgmCalculationParameters = field(
        default_factory=PgmCalculationParameters
    )
    compute_islands_separately: bool = False
    compute_only_subnets: list = field(default_factory=list)
    reconnect_branches: bool = False
