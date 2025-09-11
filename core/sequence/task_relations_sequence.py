# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>, 2025 Federico Eraso <feraso@svisuals.net>
#
# This file is part of Bonsai.	
#
# Bonsai is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Bonsai is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai.  If not, see <http://www.gnu.org/licenses/>.


from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    import ifcopenshell
    import bonsai.tool as tool


def assign_predecessor(ifc: type[tool.Ifc], sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> None:
    predecessor_task = sequence.get_highlighted_task()
    ifc.run("sequence.assign_sequence", relating_process=task, related_process=predecessor_task)
    sequence.load_task_properties()


def unassign_predecessor(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], task: ifcopenshell.entity_instance
) -> None:
    predecessor_task = sequence.get_highlighted_task()
    ifc.run("sequence.unassign_sequence", relating_process=task, related_process=predecessor_task)
    sequence.load_task_properties()


def assign_successor(ifc: type[tool.Ifc], sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> None:
    successor_task = sequence.get_highlighted_task()
    ifc.run("sequence.assign_sequence", relating_process=successor_task, related_process=task)
    sequence.load_task_properties()


def unassign_successor(ifc: type[tool.Ifc], sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> None:
    successor_task = sequence.get_highlighted_task()
    ifc.run("sequence.unassign_sequence", relating_process=successor_task, related_process=task)
    sequence.load_task_properties()


def assign_products(
    ifc: type[tool.Ifc],
    sequence: type[tool.Sequence],
    spatial: type[tool.Spatial],
    task: ifcopenshell.entity_instance,
    products: Optional[list[ifcopenshell.entity_instance]] = None,
) -> None:
    for product in products or spatial.get_selected_products() or []:
        ifc.run("sequence.assign_product", relating_product=product, related_object=task)
    outputs = sequence.get_task_outputs(task)
    sequence.load_task_outputs(outputs)


def unassign_products(
    ifc: type[tool.Ifc],
    sequence: type[tool.Sequence],
    spatial: type[tool.Spatial],
    task: ifcopenshell.entity_instance,
    products: Optional[list[ifcopenshell.entity_instance]] = None,
) -> None:
    for product in products or spatial.get_selected_products() or []:
        ifc.run("sequence.unassign_product", relating_product=product, related_object=task)
    outputs = sequence.get_task_outputs(task)
    sequence.load_task_outputs(outputs)


def assign_input_products(
    ifc: type[tool.Ifc],
    sequence: type[tool.Sequence],
    spatial: type[tool.Spatial],
    task: ifcopenshell.entity_instance,
    products: Optional[list[ifcopenshell.entity_instance]] = None,
) -> None:
    for product in products or spatial.get_selected_products() or []:
        ifc.run("sequence.assign_process", relating_process=task, related_object=product)
    inputs = sequence.get_task_inputs(task)
    sequence.load_task_inputs(inputs)


def unassign_input_products(
    ifc: type[tool.Ifc],
    sequence: type[tool.Sequence],
    spatial: type[tool.Spatial],
    task: ifcopenshell.entity_instance,
    products: Optional[list[ifcopenshell.entity_instance]] = None,
) -> None:
    for product in products or spatial.get_selected_products() or []:
        ifc.run("sequence.unassign_process", relating_process=task, related_object=product)
    inputs = sequence.get_task_inputs(task)
    sequence.load_task_inputs(inputs)


def assign_resource(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], resource_tool, task: ifcopenshell.entity_instance
) -> None:
    resource = resource_tool.get_highlighted_resource()
    sub_resource = ifc.run(
        "resource.add_resource",
        parent_resource=resource,
        ifc_class=resource.is_a(),
        name="{}/{}".format(resource.Name or "Unnamed", task.Name or ""),
    )
    ifc.run("sequence.assign_process", relating_process=task, related_object=sub_resource)
    sequence.load_task_resources(task)
    resource_tool.load_resources()


def unassign_resource(
    ifc: type[tool.Ifc],
    sequence: type[tool.Sequence],
    resource_tool,
    task: ifcopenshell.entity_instance,
    resource: ifcopenshell.entity_instance,
) -> None:
    ifc.run("sequence.unassign_process", relating_process=task, related_object=resource)
    ifc.run("resource.remove_resource", resource=resource)
    sequence.load_task_resources(task)
    resource_tool.load_resources()

def select_task_outputs(
    sequence: type[tool.Sequence], spatial: type[tool.Spatial], task: ifcopenshell.entity_instance
) -> None:
    spatial.select_products(products=sequence.get_task_outputs(task))


def select_task_inputs(
    sequence: type[tool.Sequence], spatial: type[tool.Spatial], task: ifcopenshell.entity_instance
) -> None:
    spatial.select_products(products=sequence.get_task_inputs(task))

def load_product_related_tasks(
    sequence: type[tool.Sequence], product: ifcopenshell.entity_instance
) -> Union[list[ifcopenshell.entity_instance], str]:
    filter_by_schedule = sequence.is_filter_by_active_schedule()
    if filter_by_schedule:
        work_schedule = sequence.get_active_work_schedule()
        if work_schedule:
            task_inputs, task_ouputs = sequence.get_tasks_for_product(product, work_schedule)
        else:
            return "No active work schedule."
    else:
        task_inputs, task_ouputs = sequence.get_tasks_for_product(product)
    sequence.load_product_related_tasks(task_inputs, task_ouputs)
    return task_inputs + task_ouputs



