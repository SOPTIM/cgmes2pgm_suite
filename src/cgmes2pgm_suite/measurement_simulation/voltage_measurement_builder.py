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

import pandas as pd
from cgmes2pgm_converter.common import (
    CIM_ID_OBJ,
    CIM_MEAS,
    CgmesDataset,
    MeasurementValueSource,
    Profile,
)

from .meas_ranges import MeasurementRangeSet


# pylint: disable=too-few-public-methods
class VoltageMeasurementBuilder:
    """
    Creates Measurement objects based on SV-Profile
    """

    def __init__(
        self,
        datasource: CgmesDataset,
        v_ranges: MeasurementRangeSet,
        sources: dict[MeasurementValueSource, str],
    ):
        self._datasource = datasource
        self._sv_voltage_to_meas: dict = {}
        self._v_ranges = v_ranges
        self._sources = sources

    def build_from_sv(self):
        sv = self._get_sv_voltages()
        self._create_voltage_meas(sv)
        self._create_voltage_meas_vals(sv)

    def _get_sv_voltages(self):
        query = """
        SELECT ?tn
            (SAMPLE(?_name) as ?name)
            (SAMPLE(?_nomV) as ?nomV)
            (SAMPLE(?_u) as ?u)
            (SAMPLE(?_angle) as ?angle)
            (SAMPLE(?_term) as ?term)
            (SAMPLE(?_eq) as ?eq)
            (SAMPLE(?_sv) as ?sv)
        WHERE {
            ?_sv cim:SvVoltage.v ?_u;
                    cim:SvVoltage.angle ?_angle;
                    cim:SvVoltage.TopologicalNode ?tn.

            ?_term cim:Terminal.TopologicalNode ?tn;
                    cim:Terminal.ConductingEquipment ?_eq.

            ?tn cim:IdentifiedObject.name ?_name;
                cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?_nomV.
        }
        GROUP BY ?tn
        ORDER BY ?tn
        """

        res = self._datasource.query(query)

        return res

    def _create_voltage_meas(self, sv: pd.DataFrame):

        meas = pd.DataFrame()

        meas[f"{CIM_MEAS}.Terminal"] = "<" + sv["term"] + ">"
        meas[f"{CIM_MEAS}.PowerSystemResource"] = "<" + sv["tn"] + ">"

        meas[f"{CIM_MEAS}.measurementType"] = '"Voltage"'
        meas[f"{CIM_MEAS}.unitSymbol"] = (
            f"<{self._datasource.cim_namespace}UnitSymbol.V>"
        )
        meas[f"{CIM_MEAS}.unitMultiplier"] = (
            f"<{self._datasource.cim_namespace}UnitMultiplier.k>"
        )

        meas[f"{CIM_ID_OBJ}.name"] = (
            '"' + sv["name"].astype(str) + ' Voltage Measurement"'
        )
        meas[f"{CIM_ID_OBJ}.mRID"] = [f'"{uuid.uuid4()}"' for _ in range(len(meas))]
        self._sv_voltage_to_meas = dict(zip(sv["sv"], meas[f"{CIM_ID_OBJ}.mRID"]))

        meas["rdf:type"] = f"<{self._datasource.cim_namespace}Analog>"

        ranges = [self._v_ranges.get_by_value(v) for v in sv["nomV"]]

        meas["cim:Analog.minValue"] = [r.min_value for r in ranges]
        meas["cim:Analog.maxValue"] = [r.max_value for r in ranges]

        self._datasource.insert_df(meas, Profile.OP)

    def _create_voltage_meas_vals(self, sv: pd.DataFrame):

        vals_op = pd.DataFrame()
        vals_meas = pd.DataFrame()

        vals_op[f"{CIM_ID_OBJ}.mRID"] = [f'"{uuid.uuid4()}"' for _ in range(len(sv))]
        vals_meas[f"{CIM_ID_OBJ}.mRID"] = vals_op[f"{CIM_ID_OBJ}.mRID"]

        # OP-Profile
        vals_op[f"{CIM_ID_OBJ}.name"] = (
            '"' + sv["name"].astype(str) + ' Voltage Measurement Value"'
        )
        vals_op["rdf:type"] = f"<{self._datasource.cim_namespace}AnalogValue>"
        analogs = [self._sv_voltage_to_meas[sv] for sv in sv["sv"]]
        vals_op["cim:AnalogValue.Analog"] = [
            self._datasource.mrid_to_uri(analog) for analog in analogs
        ]

        vals_op["cim:AnalogValue.MeasurementValueSource"] = self._sources[
            MeasurementValueSource.SCADA
        ]

        ranges = [self._v_ranges.get_by_value(v) for v in sv["nomV"]]
        vals_op["cim:MeasurementValue.sensorSigma"] = [r.sigma for r in ranges]

        vals_meas["cim:AnalogValue.value"] = [
            self._v_ranges.distort_measurement(r, u) for r, u in zip(ranges, sv["u"])
        ]

        # replace 0 with 0.0001
        vals_meas["cim:AnalogValue.value"] = vals_meas["cim:AnalogValue.value"]

        # Meas-Profile
        vals_meas["cim:MeasurementValue.timeStamp"] = '"2021-01-01T00:00:00Z"'

        self._datasource.insert_df(vals_op, Profile.OP)
        self._datasource.insert_df(vals_meas, Profile.MEAS, include_mrid=False)
