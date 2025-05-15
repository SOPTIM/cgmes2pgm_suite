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

from io import StringIO

from cgmes2pgm_converter.common import AbstractCgmesIdMapping, CgmesDataset


class MeasurementExport:

    _query_meas_v_in_eq = """
        SELECT ?eq ?eq_name ?eq_type ?tn ?term ?u ?stes_u ?sigma_u ?name ?meas_u ?nom_u ?sv_u
        WHERE {
            ?meas_u cim:Measurement.measurementType "LineToLineVoltage";
                    cim:IdentifiedObject.name ?name;
                    cim:Measurement.PowerSystemResource ?eq;
                    cim:Measurement.Terminal ?term.

            ?eq a ?eq_type;
                cim:IdentifiedObject.name ?eq_name.

            ?_measVal_scada cim:AnalogValue.Analog ?meas_u;
                            cim:MeasurementValue.MeasurementValueSource/cim:IdentifiedObject.name "SCADA";
                            cim:AnalogValue.value ?u.

            OPTIONAL {
                ?_measVal_est cim:AnalogValue.Analog ?meas_u;
                              cim:MeasurementValue.MeasurementValueSource/cim:IdentifiedObject.name "Estimated";
                              cim:AnalogValue.value ?stes_u.

                OPTIONAL {
                    ?_measVal_est cim:MeasurementValue.sensorAccuracy ?sigma_u.
                }
            }

            ?term cim:Terminal.TopologicalNode ?tn;
                  cim:Terminal.ConductingEquipment ?eq.

            ?tn cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?nom_u.

            ?sv cim:SvVoltage.TopologicalNode ?tn;
                cim:SvVoltage.v ?sv_u.

            $TOPO_ISLAND
            #?topoIsland # cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?tn
        }
        ORDER BY ?tn
    """

    _query_meas_pqi_in_eq = """
        SELECT
            ?eq
            ?tn
            ?nomv
            ?term
            ?value
            ?stes_value
            ?sigma
            ?name
            ?meas
            ?pfi
            ?sv_p
            ?sv_q
        WHERE {
            # "ThreePhaseActivePower", "ThreePhaseReactivePower" or "LineCurrent"
            ?meas cim:Measurement.measurementType $MEASUREMENT_TYPE;
                        cim:IdentifiedObject.name ?name;
                        cim:Measurement.Terminal ?term.

            OPTIONAL {?meas cim:Analog.positiveFlowIn ?pfi.}

            ?_measVal_scada cim:AnalogValue.Analog ?meas;
                            cim:MeasurementValue.MeasurementValueSource/cim:IdentifiedObject.name "SCADA";
                            cim:AnalogValue.value ?value.

            OPTIONAL {
                ?_measVal_est cim:AnalogValue.Analog ?meas;
                              cim:MeasurementValue.MeasurementValueSource/cim:IdentifiedObject.name "Estimated";
                              cim:AnalogValue.value ?stes_value.

                OPTIONAL {
                    ?_measVal_est cim:MeasurementValue.sensorAccuracy ?sigma.
                }
            }

            OPTIONAL {
                ?sv cim:SvPowerFlow.Terminal ?term;
                cim:SvPowerFlow.p ?sv_p;
                cim:SvPowerFlow.q ?sv_q.
            }

            ?term cim:Terminal.TopologicalNode ?tn;
                cim:Terminal.ConductingEquipment ?eq.

            ?tn cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?nomv.

            $TOPO_ISLAND
            #?topoIsland # cim:IdentifiedObject.name "TODO";
            #        cim:TopologicalIsland.TopologicalNodes ?tn.

        }
        ORDER BY ?term
    """

    def __init__(
        self,
        datasource: CgmesDataset,
        id_mapping: AbstractCgmesIdMapping,
        extra_info: dict,
        meas_path: str,
    ):
        self.datasource = datasource
        self._id_mapping = id_mapping
        self._extra_info = extra_info
        self._meas_path = meas_path

    def write(self):
        args = {"$TOPO_ISLAND": self._at_topo_island_node("?tn")}
        q_v = self.datasource.format_query(self._query_meas_v_in_eq, args)
        res_v = self.datasource.query(q_v)
        meas_by_node = {}
        self._join_measurements_by_node(res_v, meas_by_node)

        args["$MEASUREMENT_TYPE"] = '"ThreePhaseActivePower"'
        q_p = self.datasource.format_query(self._query_meas_pqi_in_eq, args)
        res_p = self.datasource.query(q_p)

        args["$MEASUREMENT_TYPE"] = '"ThreePhaseReactivePower"'
        q_q = self.datasource.format_query(self._query_meas_pqi_in_eq, args)
        res_q = self.datasource.query(q_q)

        args["$MEASUREMENT_TYPE"] = '"LineCurrent"'
        q_i = self.datasource.format_query(self._query_meas_pqi_in_eq, args)
        res_i = self.datasource.query(q_i)

        meas_by_term = {}
        self._join_measurements_by_terminal(
            res_p, meas_by_term, "ThreePhaseActivePower"
        )
        self._join_measurements_by_terminal(
            res_q, meas_by_term, "ThreePhaseReactivePower"
        )

        self._join_measurements_by_terminal(res_i, meas_by_term, "LineCurrent")

        self._print_voltage_measurements(meas_by_node)
        self._print_measurements(meas_by_term)

    def _join_measurements_by_node(self, res_v, meas_by_node: dict):
        for idx in range(res_v.shape[0]):
            node = res_v["tn"][idx]
            val = meas_by_node.setdefault(node, {})
            self.set(val, "tn", res_v["tn"][idx])
            self.append(
                val,
                "LineToLineVoltage",
                {
                    "eq": res_v["eq"][idx],
                    "eqName": res_v["eq_name"][idx],
                    "eqType": res_v["eq_type"][idx],
                    "name": res_v["name"][idx],
                    "meas": res_v["meas_u"][idx],
                    "value": res_v["u"][idx],
                    "stesValue": res_v["stes_u"][idx],
                    "sigma": res_v["sigma_u"][idx],
                    "svValue": res_v["sv_u"][idx],
                },
            )

    def _join_measurements_by_terminal(
        self, res_p, meas_by_term: dict, measurement_type: str
    ):
        for idx in range(res_p.shape[0]):
            term = res_p["term"][idx]
            val = meas_by_term.setdefault(term, {})
            self.set(val, "eq", res_p["eq"][idx])
            self.set(val, "tn", res_p["tn"][idx])
            self.set(val, "nomv", res_p["nomv"][idx])
            sv_value = None
            positive_flow_in = None
            if measurement_type == "ThreePhaseActivePower":
                sv_value = res_p["sv_p"][idx]
                positive_flow_in = res_p["pfi"][idx]
            elif measurement_type == "ThreePhaseReactivePower":
                sv_value = res_p["sv_q"][idx]
                positive_flow_in = res_p["pfi"][idx]
            self.append(
                val,
                measurement_type,
                {
                    "name": res_p["name"][idx],
                    "meas": res_p["meas"][idx],
                    "value": res_p["value"][idx],
                    "stesValue": res_p["stes_value"][idx],
                    "sigma": res_p["sigma"][idx],
                    "svValue": sv_value,
                    "positiveFlowIn": positive_flow_in,
                },
            )

    def set(self, dic, key, val):
        old_val = dic.get(key)
        if old_val is None:
            dic[key] = val
        elif old_val != val:
            raise ValueError(f"Key {key} already set to {old_val}, cannot set to {val}")

    def append(self, dic, key, val):
        old_val = dic.get(key)
        if old_val is None:
            dic[key] = [val]
        else:
            dic[key].append(val)

    def _print_voltage_measurements(self, meas_by_node):
        if self._meas_path is None:
            return

        buffer = StringIO()
        for node, val in meas_by_node.items():
            node_name = self._id_mapping.get_name_from_cgmes(node)
            node_id = self._id_mapping.get_pgm_id(node)
            node_mrid = node.split("#")[-1]
            buffer.write(f"\n{node_name} ({node_id}/{node_mrid}):\n")

            meas_v = val.get("LineToLineVoltage")
            buffer.write("\t\tV measurements:\n")
            if len(meas_v) > 0:
                buffer.write(
                    f"\t\t\t{'SV Value':>32}: value = {meas_v[0]['svValue']:>8.3f}\n"
                )
                buffer.write(f"\t\t\t{'--------':>32}{'-' * 32}\n")
            for v in meas_v:
                eq = v["eq"]
                eq_name = v["eqName"]
                eq_type = v["eqType"].split("#")[-1]
                eq_mrid = eq.split("#")[-1]

                meas_delta, bad_meas = self._abs_delta(v["value"], v["svValue"])
                stes_delta, bad_stes = self._abs_delta(v["stesValue"], v["svValue"])

                eq_info = f"{eq_name} ({eq_mrid}) : {eq_type}"

                buffer.write(
                    f"\t\t\t{v['name']:>32}:  meas = {v['value']:>8.3f}, sigma = {v['sigma']:>6.3f}, |delta| = {meas_delta:>7.3f} {'***' if bad_meas else ''} {self._comp_labels("u", meas_delta):16} {eq_info}\n"
                )
                buffer.write(
                    f"\t\t\t{"":>32}   stes = {v['stesValue']:>8.3f}, {"":>14}  |delta| = {stes_delta:>7.3f} {'***' if bad_stes else ''} {self._comp_labels("v", stes_delta)}\n"
                )

        with open(self._meas_path, "w", encoding="utf-8") as file:
            file.write(buffer.getvalue())

    def _print_measurements(self, meas_by_term):

        if self._meas_path is None:
            return

        buffer = StringIO()

        meas_by_eq = {}
        for term, meas in meas_by_term.items():
            eq = meas["eq"]
            val = meas_by_eq.setdefault(eq, {})
            val[term] = meas

        for eq, val in meas_by_eq.items():
            eq_name = self._id_mapping.get_name_from_cgmes(eq)
            eq_id = self._id_mapping.get_pgm_id(eq)
            eq_info = self._extra_info[eq_id]
            eq_type = eq_info.get("_type")
            eq_mrid = eq.split("#")[-1]
            buffer.write(f"\n{eq_name} ({eq_id}/{eq_mrid}): {eq_type}\n")
            for v in val.values():
                tn = v["tn"]
                tn_id = self._id_mapping.get_pgm_id(tn)
                tn_mrid = tn.split("#")[-1]
                tn_name = self._id_mapping.get_name_from_cgmes(tn)
                buffer.write(f"\t{tn_name} ({tn_id}/{tn_mrid}):\n")
                meas_p = v.get("ThreePhaseActivePower")
                if meas_p is not None and len(meas_p) > 0:
                    self._print_flow_measurements("P measurements", meas_p, buffer)

                meas_q = v.get("ThreePhaseReactivePower")
                if meas_q is not None and len(meas_q) > 0:
                    self._print_flow_measurements("Q measurements", meas_q, buffer)

                meas_i = v.get("LineCurrent")
                if meas_i is not None and len(meas_i) > 0:
                    self._print_flow_measurements(
                        "I measurements",
                        meas_i,
                        buffer,
                        meas_p is None and meas_q is None,
                    )

        with open(self._meas_path, "a", encoding="utf-8") as file:
            file.write(buffer.getvalue())

    def _print_flow_measurements(self, title, meas, buffer, only_i: bool = False):
        buffer.write(f"\t\t{title}:\n")
        if len(meas) > 0:
            values = "no values"
            if meas[0]["svValue"] is not None:
                values = f"value = {meas[0]['svValue']:>8.3f}"
            buffer.write(f"\t\t\t{'SV Value':>32}: {values}\n")
            buffer.write(f"\t\t\t{'--------':>32}{'-' * 32}\n")

        for m in meas:
            pfi_factor = 1
            pfi_sign = "( )"
            if m["positiveFlowIn"] is not None:
                pfi = m["positiveFlowIn"]
                pfi_factor = 1 if pfi else -1
                pfi_sign = f"({"+" if pfi else '-'})"

            report_msg_meas = f"\t\t\t{m['name']:>32}:  meas = {m['value']:>8.3f} {pfi_sign}, sigma = {m['sigma']:>6.3f}"
            report_msg_stes = f"\t\t\t{       "":>32}   stes = {m['stesValue']:>8.3f} {pfi_sign}, {"":>14}"

            if m["svValue"] is not None:
                meas_delta, bad_meas = self._abs_delta(m["value"], m["svValue"])
                stes_delta, bad_stes = self._abs_delta(m["stesValue"], m["svValue"])

                # compute delta with applied powerFlowIn value, as this is the sensor value that will used in the calculation
                pfi_meas_delta, _ = self._abs_delta(
                    m["value"] * pfi_factor, m["svValue"]
                )
                pfi_stes_delta, _ = self._abs_delta(
                    m["stesValue"] * pfi_factor, m["svValue"]
                )

                report_msg_meas = f"{report_msg_meas}, |delta| = {meas_delta:>7.3f} {'***' if bad_meas else '   '} ||pfi_delta|| = {pfi_meas_delta:>7.3f} {self._comp_labels("m", pfi_meas_delta)}"
                report_msg_stes = f"{report_msg_stes}  |delta| = {stes_delta:>7.3f} {'***' if bad_stes else '   '} ||pfi_delta|| = {pfi_stes_delta:>7.3f} {self._comp_labels("e", pfi_stes_delta)}"

            buffer.write(f"{report_msg_meas}\n")
            buffer.write(f"{report_msg_stes}\n")

        if only_i:
            buffer.write("\t\t\t --------------- ONLY I ---------------\n")

    def _comp_labels(self, prefix, delta):
        """Return a string of labels to make larger deltas easier to search for in the output file"""
        comp = [1, 2, 5, 10, 20, 30, 40, 50, 100]
        return " ".join([self._comp_label(prefix, delta, c) for c in comp])

    def _comp_label(self, prefix, delta, comp_value):
        return f"[{prefix}>{comp_value}] " if delta > comp_value else ""

    def _abs_delta(self, value, sv_value):
        delta = abs(value - sv_value)
        abs_delta = abs(abs(value) - abs(sv_value))
        bad_delta = delta > abs_delta
        return delta, bad_delta

    def _at_topo_island_node(self, node1, node2=None):
        options = self.datasource.converter_options
        if options.only_topo_island is True or options.topo_island_name is not None:
            stmt = "?topoIsland "
            if options.topo_island_name is not None:
                stmt += f'cim:IdentifiedObject.name "{options.topo_island_name}"; '

            stmt += "cim:TopologicalIsland.TopologicalNodes " + node1
            if node2 is not None:
                stmt += "; cim:TopologicalIsland.TopologicalNodes " + node2

            stmt += "."
            return stmt
        return ""
