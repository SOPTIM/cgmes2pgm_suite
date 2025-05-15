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

from dataclasses import dataclass

import numpy as np


class RandomNumberGenerator:
    _seed = None
    _rng = None

    @staticmethod
    def set_seed(seed: int):
        RandomNumberGenerator._seed = seed
        RandomNumberGenerator._rng = np.random.default_rng(seed)

    @staticmethod
    def get_rng():
        if RandomNumberGenerator._rng is None:
            RandomNumberGenerator._rng = np.random.default_rng()
        return RandomNumberGenerator._rng


@dataclass
class MeasurementRange:
    min_value: float
    max_value: float
    accuracy: float
    sigma: float

    def _get_sigma(self) -> float:
        if self.sigma is not None:
            return self.sigma

        # Based on CGMES: Accuracy is relative to the max value of the range
        max_abs = np.maximum(np.abs(self.max_value), np.abs(self.min_value))
        return np.abs((1 - self.accuracy) * max_abs / 3)

    def distort_measurement(self, value: float) -> float:
        return float(RandomNumberGenerator.get_rng().normal(value, self._get_sigma()))


class MeasurementRangeSet:
    """
    Defines a sigma or an accuracy for a given range of values.
    """

    def __init__(
        self,
        ranges: list[MeasurementRange],
        default_range: MeasurementRange,
        apply_range=True,
        zero_threshold=0,
    ):
        self.ranges = ranges
        self.default_range = default_range

        self.ranges.sort(key=lambda x: x.min_value)
        self.apply_range = apply_range
        self.zero_threshold = zero_threshold

    @staticmethod
    def from_yaml(data):
        if data is None:
            return None

        apply_range = True
        zero_threshold = 0

        meas = data.get("Measurement")
        if meas is not None:
            apply_range = meas["applyRange"]
            zero_threshold = meas["zeroThreshold"]

        ranges = []
        for range_data in data.get("Discrete", []):
            ranges.append(
                MeasurementRange(
                    range_data["Min"],
                    range_data["Max"],
                    range_data.get("Accuracy"),
                    range_data.get("Sigma"),
                )
            )

        default_range = MeasurementRange(
            data["Default"]["Min"],
            data["Default"]["Max"],
            data["Default"].get("Accuracy"),
            data["Default"].get("Sigma"),
        )

        return MeasurementRangeSet(ranges, default_range, apply_range, zero_threshold)

    def get_by_value(self, value: float) -> MeasurementRange:

        for r in self.ranges:
            if r.min_value <= value < r.max_value:
                return r

        return MeasurementRange(
            value * self.default_range.min_value,
            value * self.default_range.max_value,
            self.default_range.accuracy,
            self.default_range.sigma,
        )

    def distort_measurement(self, meas_range: MeasurementRange, value: float) -> float:
        """Use given range object to distort the given value. If application of range is disabled,
        then the value will be returned unmodified, i.e. the SV value will be returned. Values (abs)
        below the configured threshold (zeroThreshold) will not be distorted.
        """
        if not self.apply_range:
            return value  # return original (sv) value

        if abs(value) < self.zero_threshold:
            return 0

        return meas_range.distort_measurement(value)


def build_ranges_from_dict(
    cfg: dict,
) -> tuple[MeasurementRangeSet, MeasurementRangeSet]:

    RandomNumberGenerator.set_seed(cfg["Seed"])

    power_ranges = MeasurementRangeSet.from_yaml(cfg.get("PowerRangesByNominalVoltage"))
    voltage_ranges = MeasurementRangeSet.from_yaml(
        cfg.get("VoltageRangesByNominalVoltage")
    )

    return voltage_ranges, power_ranges
