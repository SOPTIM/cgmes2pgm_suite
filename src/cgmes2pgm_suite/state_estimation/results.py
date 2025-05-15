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

import numpy as np
import pandas as pd
from cgmes2pgm_converter.common import SymPowerType, VoltageMeasType
from power_grid_model import ComponentType
from power_grid_model_io.data_types import ExtraInfo

from .options import PgmCalculationParameters


class StateEstimationResult:
    """
    Class to store the results of the state estimation

    Attributes:
        run_name (str): Name of the stes-run
        input_data (dict): Input data for the state estimation
        extra_info (dict): Extra information about the input data
        result_data (dict): Result data of the state estimation
        data (dict): Merged input and result data
        params (PgmCalculationParameters): Parameters for the state estimation
        n_meas (int): Number of measurements including substituted measurements
        n_meas_actual (int): Number of measurements excluding substituted measurements
        n_statevars (int): Number of state variables
        converged (bool): True if the state estimation converged
        j (float): Value of the objective function
            `J = sum((residual / sigma) ** 2)`
        e_j (float): Expected value of the objective function.
            J is chi-squared distributed with `n_meas_actual - n_statevars` degrees of freedom.
            `E(J) = n_meas_actual - n_statevars`
        sigma_j (float): Standard deviation of the objective function
            `sigma_j = sqrt(2 * E(J))`
        redundancy (float): Redundancy of the provided measurements
            `Redundancy = n_meas_actual / n_statevars`
    """

    def __init__(
        self,
        run_name: str,
        input_data: dict[str, np.ndarray],
        extra_info: ExtraInfo,
        result_data: dict[str, np.ndarray] | None,
        params: PgmCalculationParameters,
    ):

        self.run_name = run_name
        self.input_data = input_data
        self.result_data = result_data
        self.converged = result_data is not None
        self.data = (
            self._merge_data(input_data, result_data) if result_data else input_data
        )
        self.extra_info = extra_info
        self.params = params

        self.n_meas = (
            input_data[ComponentType.sym_power_sensor].shape[0] * 2
            + input_data[ComponentType.sym_voltage_sensor].shape[0]
            + 0
        )
        self.n_meas_actual = self._calc_n_meas_actual()
        self.n_statevars = input_data[ComponentType.node].shape[0] * 2 - 1
        self.j = self._calc_j() if self.converged else 0.0
        self.e_j = self._calc_e_j()
        self.sigma_j = np.sqrt(2 * self.e_j)
        self.redundancy = self.n_meas_actual / self.n_statevars

    def __str__(self):
        divider = "---------------------------------------------"

        minus_three_sigma = self.e_j - 3 * self.sigma_j
        plus_three_sigma = self.e_j + 3 * self.sigma_j
        return (
            f"{divider}\n"
            f"State Estimation Results\n"
            f"{divider}\n"
            f"Run name            {self.run_name}\n"
            f"Converged           {self.converged}\n"
            f"{divider}\n"
            f"J                    {self.j:.2f}\n"
            f"E(J)                 {self.e_j:.2f}\n"
            f"E(J) ± 3σ           [{minus_three_sigma:.2f}; {plus_three_sigma:.2f}]\n"
            f"Redundancy           {self.redundancy:.2f}\n"
            f"{divider}\n"
            f"Bad measurements U   {len(self.get_bad_measurements_u())}\n"
            f"Bad measurements P   {len(self.get_bad_measurements_p())}\n"
            f"Bad measurements Q   {len(self.get_bad_measurements_q())}\n"
            f"{divider}\n"
        )

    def _calc_n_meas_actual(self) -> int:
        n = 0

        # Voltage measurements
        for sensor_id in self.input_data[ComponentType.sym_voltage_sensor]["id"]:
            if self.extra_info[sensor_id]["_type"] == VoltageMeasType.FIELD:
                n += 1

        # Power measurements
        for sensor_id in self.input_data[ComponentType.sym_power_sensor]["id"]:
            t = self.extra_info[sensor_id]["_type"]
            if t == SymPowerType.FIELD:
                n += 2
            elif t in SymPowerType.just_p_replaced() | SymPowerType.just_q_replaced():
                n += 1

        return n

    def _calc_j(self) -> float:

        def calc_rel_deviation(residual, sigma):
            return (residual / sigma) ** 2

        j = 0.0

        # Voltage measurements
        for i, sensor_id in enumerate(
            self.result_data[ComponentType.sym_voltage_sensor]["id"]
        ):
            if self.extra_info[sensor_id]["_type"] == VoltageMeasType.FIELD:
                j += calc_rel_deviation(
                    self.result_data[ComponentType.sym_voltage_sensor]["u_residual"][i],
                    self.input_data[ComponentType.sym_voltage_sensor]["u_sigma"][i],
                )

        for i, sensor_id in enumerate(
            self.result_data[ComponentType.sym_power_sensor]["id"]
        ):
            t = self.extra_info[sensor_id]["_type"]

            # Active power measurements
            if t in (SymPowerType.just_q_replaced() | {SymPowerType.FIELD}):
                j += calc_rel_deviation(
                    self.result_data[ComponentType.sym_power_sensor]["p_residual"][i],
                    self.input_data[ComponentType.sym_power_sensor]["p_sigma"][i],
                )

            # Reactive power measurements
            if t in (SymPowerType.just_p_replaced() | {SymPowerType.FIELD}):
                j += calc_rel_deviation(
                    self.result_data[ComponentType.sym_power_sensor]["q_residual"][i],
                    self.input_data[ComponentType.sym_power_sensor]["q_sigma"][i],
                )

        return j

    def _calc_e_j(self) -> float:
        return self.n_meas_actual - self.n_statevars

    def get_bad_measurements_u(self):
        """Creates a list of voltage measurements, that are considered as bad data:

        `|u_residual| > bad_data_tolerance * u_sigma`

        `bad_data_tolerance` is a parameter in PgmCalculationParameters

        Returns:
            list: List of sensor IDs
        """

        if not self.converged:
            return []

        bad_measurements = []
        for i, sensor_id in enumerate(
            self.result_data[ComponentType.sym_voltage_sensor]["id"]
        ):
            if self.extra_info[sensor_id]["_type"] != VoltageMeasType.FIELD:
                continue

            if self._is_bad_measurement(
                self.result_data[ComponentType.sym_voltage_sensor]["u_residual"][i],
                self.input_data[ComponentType.sym_voltage_sensor]["u_sigma"][i],
            ):
                bad_measurements.append(sensor_id)

        return bad_measurements

    def get_bad_measurements_p(self):
        """Creates a list of power measurements, that are considered as bad data:

        `|p_residual| > bad_data_tolerance * p_sigma`

        `bad_data_tolerance` is a parameter in PgmCalculationParameters

        Returns:
            list: List of sensor IDs
        """

        if not self.converged:
            return []

        bad_measurements = []
        for i, sensor_id in enumerate(
            self.result_data[ComponentType.sym_power_sensor]["id"]
        ):
            t = self.extra_info[sensor_id]["_type"]

            if t not in (SymPowerType.just_q_replaced() | {SymPowerType.FIELD}):
                continue

            if self._is_bad_measurement(
                self.result_data[ComponentType.sym_power_sensor]["p_residual"][i],
                self.input_data[ComponentType.sym_power_sensor]["p_sigma"][i],
            ):

                bad_measurements.append(sensor_id)

        return bad_measurements

    def get_bad_measurements_q(self):
        """Creates a list of power measurements, that are considered as bad data:

        `|q_residual| > bad_data_tolerance * q_sigma`

        `bad_data_tolerance` is a parameter in PgmCalculationParameters

        Returns:
            list: List of sensor IDs
        """

        if not self.converged:
            return []

        bad_measurements = []
        for i, sensor_id in enumerate(
            self.result_data[ComponentType.sym_power_sensor]["id"]
        ):
            t = self.extra_info[sensor_id]["_type"]
            if t not in (SymPowerType.just_p_replaced() | {SymPowerType.FIELD}):
                continue

            if self._is_bad_measurement(
                self.result_data[ComponentType.sym_power_sensor]["q_residual"][i],
                self.input_data[ComponentType.sym_power_sensor]["q_sigma"][i],
            ):
                bad_measurements.append(sensor_id)

        return bad_measurements

    def _is_bad_measurement(
        self, residual: np.ndarray, sigma: np.ndarray
    ) -> np.ndarray:
        return np.abs(residual) > self.params.bad_data_tolerance * sigma

    def _merge_data(
        self,
        input_data: dict[str, np.ndarray],
        result_data: dict[str, np.ndarray],
    ) -> dict[str, pd.DataFrame]:
        data = {}
        for key, value in input_data.items():
            data[key] = pd.DataFrame(value)

        for key, value in result_data.items():
            data[key] = data[key].join(
                pd.DataFrame(value).set_index("id"),
                on="id",
                how="left",
                validate="1:1",
                rsuffix="_result",
            )

        return data
