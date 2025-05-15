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

import copy
import logging
from io import StringIO
from typing import Iterable, Literal

import numpy as np
from cgmes2pgm_converter.common import Timer, Topology
from power_grid_model import ComponentType

from cgmes2pgm_suite.common import (
    ContainerData,
    NetworkData,
    NodeBalance,
    NodeData,
    SubnetData,
    SubstationData,
    VoltageLevelData,
)


class ContainerRow:
    def __init__(self, data: ContainerData, name=None):
        self.name = data.name if name is None else name
        self.p_total = data.total_pq.real
        self.q_total = data.total_pq.imag
        self.p_est_total = data.total_pq_est.real
        self.q_est_total = data.total_pq_est.imag
        self.p_load = data.load_pq.real
        self.q_load = data.load_pq.imag
        self.p_gen = data.gen_pq.real + data.source_pq.real
        self.q_gen = data.gen_pq.imag + data.source_pq.imag
        self.p_shunt = data.shunt_pq.real
        self.q_shunt = data.shunt_pq.imag
        self.p_control = data.control_pq.real
        self.q_control = data.control_pq.imag
        self.p_est_control = data.control_pq_est.real
        self.q_est_control = data.control_pq_est.imag
        self.num_nodes = data.get_num_nodes()

    @staticmethod
    def header_str(name_len):
        form = (
            format(name_len)
            + "{:>10} {:>10} {:>14} {:>14} {:>12} {:>12} {:>14} {:>14} {:>16} {:>16} {:>6}"
        )
        return form.format(
            "Name",
            "p [MW]",
            "q [MVar]",
            "p_load [MW]",
            "q_load [MVar]",
            "p_gen [MW]",
            "q_gen [MVar]",
            "p_shunt [MW]",
            "q_shunt [MVar]",
            "p_control [MW]",
            "q_control [MVar]",
            "nodes",
        )

    def to_string(self, name_len, prefix=""):
        return (
            prefix
            + format_str(self.name, name_len)
            + format_num(self.p_total, 10, 1 / 1e6)
            + format_num(self.q_total, 10, 1 / 1e6)
            + format_num(self.p_load, 14, 1 / 1e6)
            + format_num(self.q_load, 14, 1 / 1e6)
            + format_num(self.p_gen, 12, 1 / 1e6)
            + format_num(self.q_gen, 12, 1 / 1e6)
            + format_num(self.p_shunt, 14, 1 / 1e6)
            + format_num(self.q_shunt, 14, 1 / 1e6)
            + format_num(self.p_control, 16, 1 / 1e6)
            + format_num(self.q_control, 16, 1 / 1e6)
            + format_int(self.num_nodes, 6)
        )

    @staticmethod
    def result_header_str(name_len):
        form = (
            format(name_len)
            + "{:>10} {:>10} {:>12} {:>12} {:>14} {:>14} {:>16} {:>16} {:>6}"
        )
        return form.format(
            "Name",
            "p [MW]",
            "q [MVar]",
            "p_est [MW]",
            "q_est [MVar]",
            "p_diff [MW]",
            "q_diff [MVar]",
            "p_control [MW]",
            "q_control [MVar]",
            "nodes",
        )

    def to_result_string(self, name_len, prefix=""):
        return (
            prefix
            + format_str(self.name, name_len)
            + format_num(self.p_total, 10, 1 / 1e6)
            + format_num(self.q_total, 10, 1 / 1e6)
            + format_num(self.p_est_total, 12, 1 / 1e6)
            + format_num(self.q_est_total, 12, 1 / 1e6)
            + format_num(self.p_total - self.p_est_total, 14, 1 / 1e6)
            + format_num(self.q_total - self.q_est_total, 14, 1 / 1e6)
            + format_num(self.p_est_control, 16, 1 / 1e6)
            + format_num(self.q_est_control, 16, 1 / 1e6)
        )


class NodeRow:
    def __init__(self):
        self.oid = None
        self.sid = None
        self.u_meas = None
        self.u_est = None
        self.p_est = None
        self.q_est = None

    @staticmethod
    def header_str():
        form = "{:>6} {:>6} {:>10}"
        return form.format(
            "oid",
            "sid",
            "u [kV]",
        )

    def to_string(self):
        return (
            format_str(self.oid, 6)
            + format_str(self.sid, 6)
            + format_num(self.u_meas, 10, 1 / 1e3)
        )

    @staticmethod
    def result_header_str():
        form = "{:>6} {:>6} {:>10} {:>10} {:>12} {:>12}"
        return form.format(
            "oid",
            "sid",
            "u [kV]",
            "u_est [kV]",
            "p_est [MW]",
            "q_est [MVar]",
        )

    def to_result_string(self):
        return (
            format_str(self.oid, 6)
            + format_str(self.sid, 6)
            + format_num(self.u_meas, 10, 1 / 1e3)
            + format_num(self.u_est, 10, 1 / 1e3)
            + format_num(self.p_est, 12, 1 / 1e6)
            + format_num(self.q_est, 12, 1 / 1e6)
        )


class EquipmentRow:
    def __init__(self):
        self.type: str | None = None
        self.name: str | None = None
        self.status: int | None = None
        self.oid: str | None = None  # object id
        self.sid: str | None = None  # sensor id
        self.p_total: float = 0.0
        self.q_total: float = 0.0
        self.p_total_est: float = 0.0
        self.q_total_est: float = 0.0
        self.to_node: str | None = None
        self.to_node_oid: str | None = None
        self.to_node_u: float | None = None
        self.to_node_u_est: float | None = None
        self.p_gen: float | None = None
        self.q_gen: float | None = None
        self.p_load: float | None = None
        self.q_load: float | None = None
        self.p_shunt: float | None = None
        self.q_shunt: float | None = None
        self.p_control: float | None = None
        self.q_control: float | None = None
        self.p_control_est: float | None = None
        self.q_control_est: float | None = None

    @staticmethod
    def header_str(name_len, type_len):
        form = (
            format(type_len)
            + format(name_len)
            + "{:>2} {:>6} {:>6} "
            + format(name_len)
            + "{:>6} {:>10} {:>10} {:>10} {:>14} {:>14} {:>12} {:>12} {:>14} {:>14} {:>16} {:>16}"
        )
        return form.format(
            "Type",
            "Name",
            "on",
            "oid",
            "sid",
            "to_node",
            "to_oid",
            "u [kV]",
            "p [MW]",
            "q [MVar]",
            "p_load [MW]",
            "q_load [MVar]",
            "p_gen [MW]",
            "q_gen [MVar]",
            "p_shunt [MW]",
            "q_shunt [MVar]",
            "p_control [MW]",
            "q_control [MVar]",
        )

    def to_string(self, name_len, type_len):
        return (
            format_str(self.type, type_len)
            + format_str(self.name, name_len)
            + format_int(self.status, 2)
            + format_str(self.oid, 6)
            + format_str(self.sid, 6)
            + format_str(self.to_node, name_len)
            + format_str(self.to_node_oid, 6)
            + format_num(self.to_node_u, 10, 1 / 1e3)
            + format_num(self.p_total, 10, 1 / 1e6)
            + format_num(self.q_total, 10, 1 / 1e6)
            + format_num(self.p_load, 14, 1 / 1e6)
            + format_num(self.q_load, 14, 1 / 1e6)
            + format_num(self.p_gen, 12, 1 / 1e6)
            + format_num(self.q_gen, 12, 1 / 1e6)
            + format_num(self.p_shunt, 14, 1 / 1e6)
            + format_num(self.q_shunt, 14, 1 / 1e6)
            + format_num(self.p_control, 16, 1 / 1e6)
            + format_num(self.q_control, 16, 1 / 1e6)
        )

    @staticmethod
    def result_header_str(name_len, type_len):
        form = (
            format(type_len)
            + format(name_len)
            + "{:>2} {:>6} {:>6} "
            + format(name_len)
            + "{:>6} {:>10} {:>10} {:>10} {:>12} {:>12} {:>14} {:>14} {:>16} {:>16}"
        )
        return form.format(
            "Type",
            "Name",
            "on",
            "oid",
            "sid",
            "to_node",
            "to_oid",
            "u [kV]",
            "p [MW]",
            "q [MVar]",
            "p_est [MW]",
            "q_est [MVar]",
            "p_diff [MW]",
            "q_diff [MVar]",
            "p_control [MW]",
            "q_control [MVar]",
        )

    def to_result_string(self, name_len, type_len):
        return (
            format_str(self.type, type_len)
            + format_str(self.name, name_len)
            + format_int(self.status, 2)
            + format_str(self.oid, 6)
            + format_str(self.sid, 6)
            + format_str(self.to_node, name_len)
            + format_str(self.to_node_oid, 6)
            + format_num(self.to_node_u, 10, 1 / 1e3)
            + format_num(self.p_total, 10, 1 / 1e6)
            + format_num(self.q_total, 10, 1 / 1e6)
            + format_num(self.p_total_est, 12, 1 / 1e6)
            + format_num(self.q_total_est, 12, 1 / 1e6)
            + format_num(self.p_total - self.p_total_est, 14, 1 / 1e6)
            + format_num(self.q_total - self.q_total_est, 14, 1 / 1e6)
            + format_num(self.p_control_est, 16, 1 / 1e6)
            + format_num(self.q_control_est, 16, 1 / 1e6)
        )


def format(length):
    return "{:>" + str(length) + "} "


def format_str(value: str | None, length: int):
    return ("{:>" + str(length) + "} ").format(value if value is not None else "-")


def format_num(value: float | None, length: int, multiplier: float = 1.0):
    if value is None or np.isnan(value):
        return ("{:>" + str(length) + "} ").format("-")

    val = value * multiplier
    val = val if abs(value) > 0.001 else 0
    return ("{:>" + str(length) + ".3f} ").format(val)


def format_int(value: int | None, length: int):
    if value is None or np.isnan(value):
        return ("{:>" + str(length) + "} ").format("-")

    return ("{:>" + str(length) + "} ").format(value)


class NodeBalanceExport:

    def __init__(
        self, node_balance: NodeBalance, topology: Topology, result: bool = False
    ):
        self._node_balance = node_balance
        self._result = result
        self._topology = topology.get_topology()

        self._max_container_name_length = 0

        eq_max, type_max = self._compute_max_equipment_name_length()
        self._max_equipment_name_length = eq_max
        self._max_equipment_type_length = type_max

        # precompute indent strings
        self._indent = [" " * indent for indent in range(0, 20)]

    def _mrid_short(self, mrid: str):
        if isinstance(mrid, str):
            return mrid.split("#")[-1]

        return mrid

    def print_node_balance(self, path: str):
        network = self._node_balance.get_network()
        self._max_container_name_length = self._compute_max_container_name_length(
            network
        )

        buffer = StringIO()
        with Timer("\tComputing node balance", loglevel=logging.DEBUG):
            self._print_node_balance(network, buffer)

        with Timer(f"\tWriting node balance to {path}", loglevel=logging.DEBUG):
            with open(path, "w", encoding="utf-8") as file:
                file.write(buffer.getvalue())

    def _compute_max_equipment_name_length(self):
        """Compute the maximum length of any equipment name in the topology.
        Iterate directly over the topology object, because equipment line
        lines or generations are stored only once. Iterating over the
        subtation-vl-node tree would result in looking at every branch twice.
        """
        eq_name_max_len = len("Substation-Sum")
        type_name_max_len = len("Type")

        for dat in self._topology.values():
            if dat.get(ComponentType.node) is None:
                eq_name = dat["_extra"]["_name"]
                type_name = dat["_extra"]["_type"]

                eq_name_max_len = max(eq_name_max_len, len(eq_name))
                type_name_max_len = max(type_name_max_len, len(type_name))

        return eq_name_max_len, type_name_max_len

    def _compute_max_container_name_length(self, network: NetworkData):
        """Compute the maximum length of the container name in the network.
        Iterate over the substation-vl-node tree, because it contains the
        relevant objects only once. Iterating over the topology object would
        result in processing voltage levels and substations multiple times, as
        they are referenced by multiple nodes.
        """
        max_len = len("Substation-Sum")

        for subnet in network.subnets:
            for sub in subnet.substations.values():
                max_len = max(max_len, len(sub.name))

                for vl in sub.voltage_levels.values():
                    max_len = max(max_len, len(vl.name))

                    for node in vl.nodes:
                        max_len = max(max_len, len(node.name))

        return max_len

    def _print_node_balance(self, network: NetworkData, file):
        self._print_summary(
            file, network, network.subnets, 0, "Total Network Balance", "Network"
        )

        for subnet in network.subnets:
            self._print_subnet_section(file, subnet, 0)

    def _print_subnet_section(self, file, subnet: SubnetData, indent: int):
        self._writeln(file, indent, f"==== Subnet: {subnet.name} ====", frontln=True)

        self._print_summary(
            file,
            subnet,
            subnet.substations.values(),
            indent + 2,
            "Summary",
            "Subnet-Sum",
        )

        for sub in subnet.substations.values():
            self._print_substation_section(file, sub, indent + 2)

    def _print_substation_section(self, file, sub: SubstationData, indent: int):
        self._writeln(
            file,
            indent,
            f"==== Substation : {sub.name} ({sub.mrid}) ====",
            frontln=True,
        )

        self._print_summary(
            file,
            sub,
            sub.voltage_levels.values(),
            indent + 2,
            "Summary",
            "Substation-Sum",
        )

        for vl in sub.voltage_levels.values():
            self._print_vl_section(file, vl, indent + 2)

    def _print_vl_section(self, file, vl: VoltageLevelData, indent: int):
        self._writeln(
            file,
            indent,
            f"==== Voltagelevel : {vl.name} ({vl.mrid}) ====",
            frontln=True,
        )

        self._print_summary(file, vl, vl.nodes, indent + 2, "Summary", "VL-Sum")

        for node in vl.nodes:
            self._print_node_section(file, node, indent + 2)

    def _print_node_section(self, file, node: NodeData, indent: int):
        self._writeln(
            file, indent, f"==== Node : {node.name} ({node.mrid}) ====", frontln=True
        )

        self._print_node(node, file, indent + 2)

        node_equipment = self._get_node_equipment(node)
        if len(node_equipment) > 0:
            self._print_node_equipment(node_equipment, file, indent + 2)

    def _print_node(self, node: NodeData, file, indent: int):
        node_result = node.data.get("_result")
        node_sensor_v = node.data.get("_sensor_v")
        v = node_sensor_v["u_measured"] if node_sensor_v is not None else np.nan

        row = NodeRow()
        row.oid = node.data[ComponentType.node]["id"]
        row.sid = node_sensor_v["id"] if node_sensor_v is not None else None
        row.u_meas = v

        if self._result:
            row.u_est = node_result["u"] if node_result is not None else np.nan
            row.p_est = node_result["p"] if node_result is not None else np.nan
            row.q_est = node_result["q"] if node_result is not None else np.nan

        get_header = NodeRow.result_header_str if self._result else NodeRow.header_str

        self._writeln(file, indent, get_header())
        self._writeln(file, indent, self.get_row_fn(row)())

        # BAD EXAMPLE: This is very very very slow and needs multiple seconds for a non-trivial network,
        #              whereas formatting manually needs less than a second
        # df = pd.DataFrame([{"oid": row.oid, "sid": row.sid, "u": row.u_meas, "u_est": row.u_est, "p_est": row.p_est, "q_est": row.q_est}])
        # df = convert_dataframe(df)
        # file.write(df.to_string(index=False))
        # file.write("\n")

    def _get_node_equipment(self, node: NodeData):
        node_topo = node.data
        node_id = node_topo[ComponentType.node]["id"]

        node_equipment = self._get_branch_rows(node_id, node_topo)
        node_equipment += self._get_appliance_rows(node_topo, "sym_gen")
        node_equipment += self._get_appliance_rows(node_topo, "source")
        node_equipment += self._get_appliance_rows(node_topo, "sym_load")
        node_equipment += self._get_appliance_rows(node_topo, "shunt")

        if len(node_equipment) > 1:
            node_eq = EquipmentRow()
            node_eq.type = ""
            node_eq.name = "Node-Sum"
            node_eq.p_total = node.total_pq.real
            node_eq.q_total = node.total_pq.imag
            node_eq.p_total_est = node.total_pq_est.real
            node_eq.q_total_est = node.total_pq_est.imag
            node_eq.p_load = node.load_pq.real
            node_eq.q_load = node.load_pq.imag
            node_eq.p_gen = node.gen_pq.real + node.source_pq.real
            node_eq.q_gen = node.gen_pq.imag + node.source_pq.imag
            node_eq.p_shunt = node.shunt_pq.real
            node_eq.q_shunt = node.shunt_pq.imag
            node_eq.p_control = node.control_pq.real
            node_eq.q_control = node.control_pq.imag
            node_eq.p_control_est = node.control_pq_est.real
            node_eq.q_control_est = node.control_pq_est.imag
            node_equipment.append(node_eq)

        return node_equipment

    def _print_node_equipment(self, equipment: list[EquipmentRow], file, indent: int):
        self._writeln(file, indent, "==== Equipment ====", frontln=True)

        get_header = (
            EquipmentRow.result_header_str if self._result else EquipmentRow.header_str
        )
        self._writeln(
            file,
            indent + 2,
            get_header(
                self._max_equipment_name_length, self._max_equipment_type_length
            ),
        )

        for row in equipment:
            self._writeln(
                file,
                indent + 2,
                self.get_row_fn(row)(
                    self._max_equipment_name_length, self._max_equipment_type_length
                ),
            )

    def _print_summary(
        self,
        file,
        data: ContainerData,
        subdata: Iterable[ContainerData],
        indent: int,
        summary_title: str,
        sum_label: str,
    ):
        self._writeln(file, indent, f"==== {summary_title} ====")

        result: list[ContainerRow] = []
        for station in subdata:
            result.append(ContainerRow(station))

        if len(result) > 1:
            result.append(ContainerRow(data, sum_label))

        get_header = (
            ContainerRow.result_header_str if self._result else ContainerRow.header_str
        )
        self._writeln(file, indent + 2, get_header(self._max_container_name_length))

        for row in result:
            self._writeln(
                file, indent + 2, self.get_row_fn(row)(self._max_container_name_length)
            )

    def _writeln(self, file, indent: int, string: str, frontln=False):
        if frontln:
            file.write("\n")
        file.write(self._indent[indent])
        file.write(string)
        file.write("\n")

    def get_row_fn(self, row):
        if self._result:
            return row.to_result_string

        return row.to_string

    def _get_branch_rows(self, node_id, node_topo) -> list[EquipmentRow]:
        result = []
        branches = node_topo.get("_branches")
        if branches is not None:
            for line_id in branches:
                br = self._topology[line_id]

                res = EquipmentRow()
                res.type = br["_extra"]["_type"]
                res.name = br["_extra"]["_name"]

                line = br.get(ComponentType.line)
                genb = br.get(ComponentType.generic_branch)
                tr2w = br.get(ComponentType.transformer)
                tr3w = br.get(ComponentType.three_winding_transformer)
                link = br.get(ComponentType.link)

                node2 = None
                node3 = None

                side = "to"  # default for links

                status = 0
                p_to = 0.0
                q_to = 0.0

                if line is not None:
                    res.oid = line["id"]
                    sensor, side = self.get_sensor_for_branch2(
                        node_id, br, ComponentType.line
                    )
                    p_to = sensor["p_measured"] if sensor is not None else np.nan
                    q_to = sensor["q_measured"] if sensor is not None else np.nan

                    node_id2, _ = self.other_node_id(
                        node_id, line["from_node"], line["to_node"]
                    )
                    node2 = self._topology[node_id2]
                    status = line["from_status"] and line["to_status"]

                if genb is not None:
                    res.oid = genb["id"]
                    sensor, side = self.get_sensor_for_branch2(
                        node_id, br, ComponentType.generic_branch
                    )
                    p_to = sensor["p_measured"] if sensor is not None else np.nan
                    q_to = sensor["q_measured"] if sensor is not None else np.nan

                    node_id2, _ = self.other_node_id(
                        node_id, genb["from_node"], genb["to_node"]
                    )
                    node2 = self._topology[node_id2]
                    status = genb["from_status"] and genb["to_status"]

                if tr2w is not None:
                    res.oid = tr2w["id"]
                    sensor, side = self.get_sensor_for_branch2(
                        node_id, br, ComponentType.transformer
                    )
                    p_to = sensor["p_measured"] if sensor is not None else np.nan
                    q_to = sensor["q_measured"] if sensor is not None else np.nan

                    node_id2, _ = self.other_node_id(
                        node_id, tr2w["from_node"], tr2w["to_node"]
                    )
                    node2 = self._topology[node_id2]
                    status = tr2w["from_status"] and tr2w["to_status"]

                if tr3w is not None:
                    res.oid = tr3w["id"]
                    sensor, side = self.get_sensor_for_branch3(node_id, br)
                    p_to = sensor["p_measured"] if sensor is not None else np.nan
                    q_to = sensor["q_measured"] if sensor is not None else np.nan

                    node_id2, node_id3 = self.other_node_id(
                        node_id, tr3w["node_1"], tr3w["node_2"], tr3w["node_3"]
                    )
                    node2 = self._topology[node_id2]
                    node3 = self._topology[node_id3]
                    status = tr3w["status_1"] and tr3w["status_2"] and tr3w["status_3"]

                if link is not None:
                    res.oid = link["id"]

                    p_to = 0.0
                    q_to = 0.0
                    node_id2, _ = self.other_node_id(
                        node_id, link["from_node"], link["to_node"]
                    )
                    node2 = self._topology[node_id2]
                    status = link["from_status"] and link["to_status"]
                    side = self.get_dir(node_id, br, ComponentType.link)

                res.status = status

                res.p_total = p_to if status else 0.0
                res.q_total = q_to if status else 0.0

                val_p = p_to
                if not np.isnan(p_to):
                    val_p = p_to / 1e6
                    val_p = 0.0 if abs(val_p) < 0.1 else val_p

                val_q = q_to
                if not np.isnan(q_to):
                    val_q = q_to / 1e6
                    val_q = 0.0 if abs(val_q) < 0.1 else val_q

                if node2 is not None:
                    node2_result = node2.get("_result")
                    res.to_node = node2["_extra"]["_name"]
                    res.to_node_oid = node_id2
                    if node2_result is None:
                        res.to_node_u = self.sensor_value(
                            node2, "_sensor_v", "u_measured"
                        )
                    else:
                        res.to_node_u = self.sensor_value(
                            node2, "_sensor_v", "u_measured"
                        )
                        res.to_node_u_est = node2_result["u"]

                if link is None:
                    sensor = br.get("_sensor_p_" + side)
                    if sensor is not None:
                        verify_oid = sensor["measured_object"]
                        if verify_oid != res.oid:
                            raise IndexError
                        res.sid = sensor["id"]

                est = br.get("_result")
                if est is not None:
                    res.p_total_est = est["p_" + side]
                    res.q_total_est = est["q_" + side]

                result.append(res)

                ## for a three winding transformer also append a row with references to the 3rd node
                if node3 is not None:
                    node3_result = node3.get("_result")
                    res3 = copy.deepcopy(res)
                    res3.to_node = node3["_extra"]["_name"]
                    res3.to_node_oid = node_id3
                    if node3_result is None:
                        res3.to_node_u = self.sensor_value(
                            node3, "_sensor_v", "u_measured"
                        )
                    else:
                        res3.to_node_u = self.sensor_value(
                            node3, "_sensor_v", "u_measured"
                        )
                        res3.to_node_u_est = node3_result["u"]
                    result.append(res3)

        return result

    def _get_appliance_rows(
        self,
        node_topo,
        component_name: Literal["sym_gen", "source", "sym_load", "shunt"],
    ) -> list[EquipmentRow]:
        factor = -1 if component_name in ["sym_gen", "source"] else 1
        result = []
        appliances = node_topo.get(component_name)
        if appliances is not None:
            for appl_id in appliances:
                appl = self._topology[appl_id]
                p, q = self.sensor_value2(appl, "_sensor_p", "p_measured", "q_measured")
                status = self._get_appliance_connection_status(appl)

                res = EquipmentRow()
                res.type = appl["_extra"]["_type"]
                res.name = appl["_extra"]["_name"]
                res.status = status
                sid, _ = self.sensor_value2(appl, "_sensor_p", "id", "measured_object")
                res.oid = appl_id
                if not np.isnan(sid):
                    res.sid = str(sid)

                if not status:
                    factor = 0

                res.p_total = p * factor
                res.q_total = q * factor

                match component_name:
                    case "sym_gen" | "source":
                        res.p_gen = p * factor
                        res.q_gen = q * factor
                    case "sym_load":
                        res.p_load = p * factor
                        res.q_load = q * factor
                    case "shunt":
                        res.p_shunt = p * factor
                        res.q_shunt = q * factor

                est = appl.get("_result")
                if est is not None:
                    res.p_total_est = est["p"] * factor
                    res.q_total_est = est["q"] * factor

                result.append(res)
        return result

    def _get_appliance_connection_status(self, appl):
        for component in [
            ComponentType.shunt,
            ComponentType.sym_gen,
            ComponentType.sym_load,
            ComponentType.source,
        ]:
            if appl.get(component) is not None:
                return appl[component]["status"]
        return 0

    def sensor_value(self, data, sensor_name, value_name):
        sensor = data.get(sensor_name)
        return sensor[value_name] if sensor is not None else np.nan

    def sensor_value2(self, data, sensor_name, value_name, value_name2):
        sensor = data.get(sensor_name)
        if sensor is None:
            return np.nan, np.nan

        return sensor[value_name], sensor[value_name2]

    def get_dir(
        self,
        node_id,
        ll,
        component_type: Literal[
            ComponentType.line,
            ComponentType.link,
            ComponentType.generic_branch,
            ComponentType.transformer,
        ],
    ):
        node1 = ll[component_type]["from_node"]
        node2 = ll[component_type]["to_node"]

        if node_id == node1:
            return "from"
        if node_id == node2:
            return "to"
        raise IndexError

    def get_sensor_for_branch2(
        self,
        node_id,
        ll,
        component_type: Literal[
            ComponentType.line, ComponentType.generic_branch, ComponentType.transformer
        ],
    ):
        node1 = ll[component_type]["from_node"]
        node2 = ll[component_type]["to_node"]
        if node_id == node1:
            return ll.get("_sensor_p_from"), "from"
        if node_id == node2:
            return ll.get("_sensor_p_to"), "to"
        raise IndexError

    def get_sensor_for_branch3(self, node_id, ll):
        node1 = ll[ComponentType.three_winding_transformer]["node_1"]
        node2 = ll[ComponentType.three_winding_transformer]["node_2"]
        node3 = ll[ComponentType.three_winding_transformer]["node_3"]
        if node1 == node_id:
            return ll.get("_sensor_p_1"), "1"
        if node2 == node_id:
            return ll.get("_sensor_p_2"), "2"
        if node3 == node_id:
            return ll.get("_sensor_p_3"), "3"
        raise IndexError

    def other_node_id(self, from_id, id1, id2, id3=None):
        if from_id == id1:
            return id2, id3
        if from_id == id2:
            return id1, id3
        return id1, id2
