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

import logging
from typing import Callable

import numpy as np
from cgmes2pgm_converter.common import Topology
from power_grid_model import ComponentType


def connect_branch(topo_branch, topo, connect=True):
    extra = topo_branch.get("_extra")
    src1_id = extra.get("source1")
    src2_id = extra.get("source2")

    expected_branch_status = not connect
    expected_source_status = connect

    new_branch_status = not expected_branch_status
    new_source_status = not expected_source_status

    if src1_id is None or src2_id is None:
        return False

    pgm_branch = topo_branch.get(ComponentType.line)
    if pgm_branch is None:
        pgm_branch = topo_branch[ComponentType.generic_branch]

    pgm_src1 = topo[src1_id].get(ComponentType.source)
    pgm_src2 = topo[src2_id].get(ComponentType.source)

    if not pgm_src1 or not pgm_src2:
        logging.warning(
            "\tDid not find sources %s, %s that replaced the branch %s",
            src1_id,
            src2_id,
            extra["_name"],
        )
        logging.warning(
            "\t Set NetworkSplittingOptions.add_sources=True during conversion"
        )
        return False

    branch_can_change = (
        pgm_branch["from_status"] == expected_branch_status
        and pgm_branch["to_status"] == expected_branch_status
    )

    srcs_can_change = (
        pgm_src1["status"] == expected_source_status
        and pgm_src2["status"] == expected_source_status
    )

    if not branch_can_change or not srcs_can_change:
        logging.warning(
            "\tBranch '%s' or sources %s, %s cannot change status",
            extra["_name"],
            src1_id,
            src2_id,
        )
        return False

    pgm_branch["from_status"] = new_branch_status
    pgm_branch["to_status"] = new_branch_status

    pgm_src1["status"] = new_source_status
    pgm_src2["status"] = new_source_status

    return True


def extract_subnet_from_input_data(
    input_data, extra_info, subnet
) -> dict[ComponentType, np.ndarray]:
    topo = Topology(input_data, extra_info)

    new_data = {}
    new_data[ComponentType.node] = filter_ndarray(
        input_data[ComponentType.node], is_node_in_subnet, topo, "id", subnet
    )
    new_data[ComponentType.line] = filter_ndarray(
        input_data[ComponentType.line], is_branch_in_subnet, topo, "id", subnet
    )
    new_data[ComponentType.generic_branch] = filter_ndarray(
        input_data[ComponentType.generic_branch],
        is_branch_in_subnet,
        topo,
        "id",
        subnet,
    )

    new_data[ComponentType.link] = filter_ndarray(
        input_data[ComponentType.link], is_branch_in_subnet, topo, "id", subnet
    )

    new_data[ComponentType.transformer] = filter_ndarray(
        input_data[ComponentType.transformer], is_branch_in_subnet, topo, "id", subnet
    )

    new_data[ComponentType.three_winding_transformer] = filter_ndarray(
        input_data[ComponentType.three_winding_transformer],
        is_three_winding_transformer_in_subnet,
        topo,
        "id",
        subnet,
    )

    new_data[ComponentType.sym_load] = filter_ndarray(
        input_data[ComponentType.sym_load], is_appliance_in_subnet, topo, "id", subnet
    )

    new_data[ComponentType.sym_gen] = filter_ndarray(
        input_data[ComponentType.sym_gen], is_appliance_in_subnet, topo, "id", subnet
    )

    new_data[ComponentType.source] = filter_ndarray(
        input_data[ComponentType.source], is_appliance_in_subnet, topo, "id", subnet
    )

    new_data[ComponentType.shunt] = filter_ndarray(
        input_data[ComponentType.shunt], is_appliance_in_subnet, topo, "id", subnet
    )

    new_data[ComponentType.sym_voltage_sensor] = filter_ndarray(
        input_data[ComponentType.sym_voltage_sensor],
        is_voltage_sensor_in_subnet,
        topo,
        "measured_object",
        subnet,
    )

    new_data[ComponentType.sym_power_sensor] = filter_ndarray(
        input_data[ComponentType.sym_power_sensor],
        is_power_sensor_in_subnet,
        topo,
        "measured_object",
        subnet,
    )

    return new_data


def filter_ndarray(
    lines: np.ndarray,
    filter_fn: Callable[[Topology, str, str], bool],
    topo: Topology,
    key: str,
    subnet: str,
):
    return lines[[filter_fn(topo, x[key], subnet) for x in lines]]


def is_node_in_subnet(topo, node_id, subnet):
    return topo.get_topology()[node_id]["_subnet"] == subnet


def is_branch_in_subnet(topo, branch_id, subnet):
    topo_branch = topo.get_topology()[branch_id]
    branch = topo_branch.get(ComponentType.line)
    if branch is None:
        branch = topo_branch.get(ComponentType.generic_branch)
    if branch is None:
        branch = topo_branch.get(ComponentType.link)
    if branch is None:
        branch = topo_branch.get(ComponentType.transformer)

    if branch is None:
        return False

    from_node_id = branch["from_node"]
    to_node_id = branch["to_node"]

    from_node_in_subnet = is_node_in_subnet(topo, from_node_id, subnet)
    to_node_in_subnet = is_node_in_subnet(topo, to_node_id, subnet)
    return from_node_in_subnet and to_node_in_subnet


def is_three_winding_transformer_in_subnet(topo, trafo_id, subnet):
    topo_trafo = topo.get_topology()[trafo_id]
    trafo = topo_trafo.get(ComponentType.three_winding_transformer)
    if trafo is None:
        return False

    node1_id = trafo["node_1"]
    node2_id = trafo["node_2"]
    node3_id = trafo["node_3"]

    node1_in_subnet = is_node_in_subnet(topo, node1_id, subnet)
    node2_in_subnet = is_node_in_subnet(topo, node2_id, subnet)
    node3_in_subnet = is_node_in_subnet(topo, node3_id, subnet)

    return node1_in_subnet and node2_in_subnet and node3_in_subnet


def is_appliance_in_subnet(topo, appliance_id, subnet):
    topo_appl = topo.get_topology()[appliance_id]
    appl = topo_appl.get(ComponentType.sym_load)
    if appl is None:
        appl = topo_appl.get(ComponentType.sym_gen)
    if appl is None:
        appl = topo_appl.get(ComponentType.source)
    if appl is None:
        appl = topo_appl.get(ComponentType.shunt)
    if appl is None:
        return False

    node_id = appl["node"]

    node_in_subnet = is_node_in_subnet(topo, node_id, subnet)
    return node_in_subnet


def is_voltage_sensor_in_subnet(topo, meas_id, subnet):
    return is_node_in_subnet(topo, meas_id, subnet)


def is_power_sensor_in_subnet(topo, meas_id, subnet):
    return is_branch_in_subnet(topo, meas_id, subnet) or is_appliance_in_subnet(
        topo, meas_id, subnet
    )
