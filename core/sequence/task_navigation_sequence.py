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
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    import ifcopenshell
    import bonsai.tool as tool


def expand_task(sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> None:
    sequence.expand_task(task)
    work_schedule = sequence.get_active_work_schedule()
    sequence.load_task_tree(work_schedule)
    sequence.load_task_properties()


def expand_all_tasks(sequence: type[tool.Sequence]) -> None:
    sequence.expand_all_tasks()
    work_schedule = sequence.get_active_work_schedule()
    sequence.load_task_tree(work_schedule)
    sequence.load_task_properties()


def contract_task(sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> None:
    sequence.contract_task(task)
    work_schedule = sequence.get_active_work_schedule()
    sequence.load_task_tree(work_schedule)
    sequence.load_task_properties()


def contract_all_tasks(sequence: type[tool.Sequence]) -> None:
    sequence.contract_all_tasks()
    work_schedule = sequence.get_active_work_schedule()
    sequence.load_task_tree(work_schedule)
    sequence.load_task_properties()


def go_to_task(sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> Union[None, str]:
    work_schedule = sequence.get_work_schedule(task)
    is_work_schedule_active = sequence.is_work_schedule_active(work_schedule)
    if is_work_schedule_active:
        sequence.go_to_task(task)
    else:
        return "Work schedule is not active"


def reorder_task_nesting(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], task: ifcopenshell.entity_instance, new_index: int
) -> Union[None, str]:
    is_sorting_enabled = sequence.is_sorting_enabled()
    is_sort_reversed = sequence.is_sort_reversed()
    if is_sorting_enabled or is_sort_reversed:
        return "Remove manual sorting"
    else:
        ifc.run("nest.reorder_nesting", item=task, new_index=new_index)
        work_schedule = sequence.get_active_work_schedule()
        sequence.load_task_tree(work_schedule)
        sequence.load_task_properties()




