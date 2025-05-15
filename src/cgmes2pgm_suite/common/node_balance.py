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

import math
from typing import Literal

from cgmes2pgm_converter.common import Topology
from power_grid_model import ComponentType


class ContainerData:
    def __init__(self, name, mrid) -> None:
        self.name = str(name)
        self.mrid = str(mrid)
        self.load_pq = complex(0, 0)
        self.gen_pq = complex(0, 0)
        self.source_pq = complex(0, 0)
        self.shunt_pq = complex(0, 0)
        self.total_pq = complex(0, 0)
        self.total_pq_est = complex(0, 0)
        self.control_pq = complex(0, 0)
        self.control_pq_est = complex(0, 0)

    def add_child_pq(self, child: "ContainerData"):
        self.load_pq += child.load_pq
        self.gen_pq += child.gen_pq
        self.source_pq += child.source_pq
        self.shunt_pq += child.shunt_pq
        self.total_pq += child.total_pq
        self.total_pq_est += child.total_pq_est
        self.control_pq += child.control_pq
        self.control_pq_est += child.control_pq_est

    def get_num_nodes(self) -> int:
        return 0


class NodeData(ContainerData):
    def __init__(self, name, mrid, data) -> None:
        super().__init__(name, mrid)
        self.data = data
        self.branch_pq = complex(0, 0)

    def get_num_nodes(self):
        return 1


class VoltageLevelData(ContainerData):
    def __init__(self, name, mrid) -> None:
        super().__init__(name, mrid)
        self.nodes: list[NodeData] = []

    def add_node(self, node: NodeData):
        self.nodes.append(node)

    def get_num_nodes(self):
        return len(self.nodes)


class SubstationData(ContainerData):
    def __init__(self, name, mrid) -> None:
        super().__init__(name, mrid)
        self.voltage_levels: dict[str, VoltageLevelData] = {}

    def add_voltage_level(self, vl: VoltageLevelData):
        self.voltage_levels[vl.mrid] = vl

    def get_voltage_level(self, mrid):
        return self.voltage_levels.get(mrid)

    def get_num_nodes(self):
        return sum(vl.get_num_nodes() for vl in self.voltage_levels.values())


class SubnetData(ContainerData):
    def __init__(self, name) -> None:
        super().__init__(name, name)
        self.substations: dict[str, SubstationData] = {}

    def add_substation(self, sub: SubstationData):
        self.substations[sub.mrid] = sub

    def get_substation(self, mrid):
        return self.substations.get(mrid)

    def get_num_nodes(self):
        return sum(sub.get_num_nodes() for sub in self.substations.values())


class NetworkData(ContainerData):
    def __init__(self) -> None:
        super().__init__("Network", "nan")
        self.subnets: list[SubnetData] = []

    def get_num_nodes(self):
        return sum(sub.get_num_nodes() for sub in self.subnets)


class NodeBalance:

    def __init__(self, topology: Topology):
        self._topology = topology
        self._network = self._create_network_tree_from_topology()
        self._calc_node_balance(self._network)

    def get_network(self) -> NetworkData:
        return self._network

    def _mrid_short(self, mrid: str):
        if isinstance(mrid, str):
            ## cut off the url prefix
            return mrid.split("#")[-1]

        return str(mrid)

    def _create_network_tree_from_topology(self):

        topo_nodes = self._topology.get_nodes()

        nodes_by_subnet: dict[str, SubnetData] = {}

        for topo_node in topo_nodes:
            vl_id: str = topo_node["_extra"]["_containerMrid"]
            vl_id = self._mrid_short(vl_id)

            sub_id = topo_node["_extra"]["_substationMrid"]
            sub_id = self._mrid_short(sub_id)

            node_name = topo_node["_extra"]["_name"]
            vl_name = self._str_default(
                topo_node["_extra"]["_container"], node_name + "*"
            )
            substation_name = self._str_default(
                topo_node["_extra"]["_substation"], vl_name + "*"
            )

            subnet_name = topo_node.get("_subnet")
            subnet_name = subnet_name if subnet_name is not None else "nan"

            subnet = nodes_by_subnet.get(subnet_name)
            if subnet is None:
                subnet = SubnetData(subnet_name)
                nodes_by_subnet[subnet_name] = subnet

            substation = subnet.get_substation(sub_id)
            if substation is None:
                substation = SubstationData(substation_name, self._mrid_short(sub_id))
                subnet.add_substation(substation)

            voltage_level = substation.get_voltage_level(vl_id)
            if voltage_level is None:
                voltage_level = VoltageLevelData(vl_name, self._mrid_short(vl_id))
                substation.add_voltage_level(voltage_level)

            node = NodeData(
                node_name,
                self._mrid_short(topo_node["_extra"]["_mrid"]),
                topo_node,
            )
            voltage_level.add_node(node)

        network = NetworkData()
        network.subnets += sorted(
            nodes_by_subnet.values(), key=lambda x: x.get_num_nodes(), reverse=True
        )

        return network

    def _str_default(self, value, default_value):
        if value is not None and not (isinstance(value, float) and math.isnan(value)):
            return value

        return default_value

    def _calc_node_balance(self, network: NetworkData):
        for subnet in network.subnets:
            for sub in subnet.substations.values():
                for vl in sub.voltage_levels.values():
                    for vl_node in vl.nodes:
                        topo_node = vl_node.data
                        node_id = topo_node[ComponentType.node]["id"]

                        branch_pq, branch_pq_est = self._add_branches(
                            topo_node, node_id
                        )
                        vl_node.branch_pq = branch_pq

                        gen_pq, gen_pq_est = self._add_appliances(
                            topo_node, ComponentType.sym_gen
                        )
                        vl_node.gen_pq = gen_pq

                        source_pq, source_pq_est = self._add_appliances(
                            topo_node, ComponentType.source
                        )
                        vl_node.source_pq = source_pq

                        load_pq, load_pq_est = self._add_appliances(
                            topo_node, ComponentType.sym_load
                        )
                        vl_node.load_pq = load_pq

                        shunt_pq, shunt_pq_est = self._add_appliances(
                            topo_node, ComponentType.shunt
                        )
                        vl_node.shunt_pq = shunt_pq

                        vl_node.total_pq = (
                            vl_node.gen_pq
                            + vl_node.source_pq
                            + vl_node.load_pq
                            + vl_node.shunt_pq
                        )
                        vl_node.total_pq_est = (
                            gen_pq_est + source_pq_est + load_pq_est + shunt_pq_est
                        )
                        vl_node.control_pq = vl_node.total_pq + vl_node.branch_pq
                        vl_node.control_pq_est = vl_node.total_pq_est + branch_pq_est

                        vl.add_child_pq(vl_node)

                    sub.add_child_pq(vl)

                subnet.add_child_pq(sub)

            network.add_child_pq(subnet)

    def _add_branches(self, node_topo, node_id) -> tuple[complex, complex]:
        branches = node_topo.get("_branches")
        sum_p = 0
        sum_q = 0
        sum_p_est = 0
        sum_q_est = 0
        if branches is not None:
            for line_id in branches:
                br = self._topology[line_id]

                line = br.get(ComponentType.line)
                genb = br.get(ComponentType.generic_branch)
                tr2w = br.get(ComponentType.transformer)
                tr3w = br.get(ComponentType.three_winding_transformer)

                side = "to"  # default for links

                p_to = 0.0
                q_to = 0.0

                status = 0

                if line is not None:
                    sensor, side = self.get_sensor_for_branch2(
                        node_id, br, ComponentType.line
                    )
                    p_to = sensor["p_measured"] if sensor is not None else 0
                    q_to = sensor["q_measured"] if sensor is not None else 0
                    status = line["to_status"] and line["from_status"]

                if genb is not None:
                    sensor, side = self.get_sensor_for_branch2(
                        node_id, br, ComponentType.generic_branch
                    )
                    p_to = sensor["p_measured"] if sensor is not None else 0
                    q_to = sensor["q_measured"] if sensor is not None else 0
                    status = genb["to_status"] and genb["from_status"]

                if tr2w is not None:
                    sensor, side = self.get_sensor_for_branch2(
                        node_id, br, ComponentType.transformer
                    )
                    p_to = sensor["p_measured"] if sensor is not None else 0
                    q_to = sensor["q_measured"] if sensor is not None else 0
                    status = tr2w["to_status"] and tr2w["from_status"]

                if tr3w is not None:
                    sensor, side = self.get_sensor_for_branch3(node_id, br)
                    p_to = sensor["p_measured"] if sensor is not None else 0
                    q_to = sensor["q_measured"] if sensor is not None else 0
                    status = (
                        tr3w["status_1"] and tr3w["status_2"]
                    )  # and tr3w["status_3"]

                if not status:
                    continue

                sum_p += p_to
                sum_q += q_to

                est = br.get("_result")
                if est is not None:
                    p_est = est["p_" + side]
                    q_est = est["q_" + side]
                    sum_p_est += p_est
                    sum_q_est += q_est

        return complex(sum_p, sum_q), complex(sum_p_est, sum_q_est)

    def _add_appliances(
        self,
        node_topo,
        component_type: Literal[
            ComponentType.sym_gen,
            ComponentType.sym_load,
            ComponentType.source,
            ComponentType.shunt,
        ],
    ) -> tuple[complex, complex]:
        factor = -1 if component_type in ["sym_gen", "source"] else 1
        appliances = node_topo.get(component_type)
        sum_p = 0
        sum_q = 0
        sum_p_est = 0
        sum_q_est = 0
        if appliances is not None:
            for appl_id in appliances:
                appl = self._topology[appl_id]
                p, q = self.sensor_value2(appl, "_sensor_p", "p_measured", "q_measured")

                # generations are negated in the input data
                sum_p += p * factor
                sum_q += q * factor

                est = appl.get("_result")
                if est is not None:
                    p_est = est["p"]
                    q_est = est["q"]
                    sum_p_est += p_est * factor
                    sum_q_est += q_est * factor

        return complex(sum_p, sum_q), complex(sum_p_est, sum_q_est)

    def sensor_value2(self, data, sensor_name, value_name, value_name2):
        sensor = data.get(sensor_name)
        if sensor is None:
            return 0, 0

        return sensor[value_name], sensor[value_name2]

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
