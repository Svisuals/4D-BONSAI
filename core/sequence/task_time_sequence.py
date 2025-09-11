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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ifcopenshell
    import bonsai.tool as tool


def enable_editing_task_time(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], task: ifcopenshell.entity_instance
) -> None:
    task_time = sequence.get_task_time(task)
    if task_time is None:
        task_time = ifc.run("sequence.add_task_time", task=task)
    sequence.load_task_time_attributes(task_time)
    sequence.enable_editing_task_time(task)


def edit_task_time(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], resource, task_time: ifcopenshell.entity_instance
) -> None:
    attributes = sequence.get_task_time_attributes()
    # TODO: nasty loop goes on when calendar props are messed up
    ifc.run("sequence.edit_task_time", task_time=task_time, attributes=attributes)
    task = sequence.get_active_task()
    sequence.load_task_properties(task=task)
    sequence.disable_editing_task_time()
    resource.load_resource_properties()


def disable_editing_task_time(sequence: type[tool.Sequence]) -> None:
    sequence.disable_editing_task_time()


def calculate_task_duration(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], task: ifcopenshell.entity_instance
) -> None:
    ifc.run("sequence.calculate_task_duration", task=task)
    work_schedule = sequence.get_active_work_schedule()
    if work_schedule:
        sequence.load_task_tree(work_schedule)
        sequence.load_task_properties()


