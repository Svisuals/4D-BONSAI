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


def remove_work_calendar(ifc: type[tool.Ifc], work_calendar: ifcopenshell.entity_instance) -> None:
    ifc.run("sequence.remove_work_calendar", work_calendar=work_calendar)


def add_work_calendar(ifc: type[tool.Ifc]) -> ifcopenshell.entity_instance:
    return ifc.run("sequence.add_work_calendar")


def edit_work_calendar(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], work_calendar: ifcopenshell.entity_instance
) -> None:
    attributes = sequence.get_work_calendar_attributes()
    ifc.run("sequence.edit_work_calendar", work_calendar=work_calendar, attributes=attributes)
    sequence.disable_editing_work_calendar()
    sequence.load_task_properties()


def enable_editing_work_calendar(sequence: type[tool.Sequence], work_calendar: ifcopenshell.entity_instance) -> None:
    sequence.load_work_calendar_attributes(work_calendar)
    sequence.enable_editing_work_calendar(work_calendar)


def disable_editing_work_calendar(sequence: type[tool.Sequence]) -> None:
    sequence.disable_editing_work_calendar()


def enable_editing_work_calendar_times(
    sequence: type[tool.Sequence], work_calendar: ifcopenshell.entity_instance
) -> None:
    sequence.enable_editing_work_calendar_times(work_calendar)


def add_work_time(
    ifc: type[tool.Ifc], work_calendar: ifcopenshell.entity_instance, time_type: ifcopenshell.entity_instance
) -> ifcopenshell.entity_instance:
    return ifc.run("sequence.add_work_time", work_calendar=work_calendar, time_type=time_type)


def enable_editing_work_time(sequence: type[tool.Sequence], work_time: ifcopenshell.entity_instance) -> None:
    sequence.load_work_time_attributes(work_time)
    sequence.enable_editing_work_time(work_time)


def disable_editing_work_time(sequence: type[tool.Sequence]) -> None:
    sequence.disable_editing_work_time()


def remove_work_time(ifc: type[tool.Ifc], work_time=None) -> None:
    ifc.run("sequence.remove_work_time", work_time=work_time)


def edit_work_time(ifc: type[tool.Ifc], sequence: type[tool.Sequence]) -> None:
    work_time = sequence.get_active_work_time()
    ifc.run("sequence.edit_work_time", work_time=work_time, attributes=sequence.get_work_time_attributes())
    recurrence_pattern = work_time.RecurrencePattern
    if recurrence_pattern:
        ifc.run(
            "sequence.edit_recurrence_pattern",
            recurrence_pattern=recurrence_pattern,
            attributes=sequence.get_recurrence_pattern_attributes(recurrence_pattern),
        )
    sequence.disable_editing_work_time()


def assign_recurrence_pattern(
    ifc: type[tool.Ifc], work_time: ifcopenshell.entity_instance, recurrence_type: ifcopenshell.entity_instance
) -> ifcopenshell.entity_instance:
    return ifc.run("sequence.assign_recurrence_pattern", parent=work_time, recurrence_type=recurrence_type)


def unassign_recurrence_pattern(ifc: type[tool.Ifc], recurrence_pattern: ifcopenshell.entity_instance) -> None:
    ifc.run("sequence.unassign_recurrence_pattern", recurrence_pattern=recurrence_pattern)


def add_time_period(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], recurrence_pattern: ifcopenshell.entity_instance
) -> None:
    start_time, end_time = sequence.get_recurrence_pattern_times()
    ifc.run("sequence.add_time_period", recurrence_pattern=recurrence_pattern, start_time=start_time, end_time=end_time)
    sequence.reset_time_period()


def remove_time_period(ifc: type[tool.Ifc], time_period: ifcopenshell.entity_instance) -> None:
    ifc.run("sequence.remove_time_period", time_period=time_period)


def enable_editing_task_calendar(sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> None:
    sequence.enable_editing_task_calendar(task)


def edit_task_calendar(
    ifc: type[tool.Ifc],
    sequence: type[tool.Sequence],
    task: ifcopenshell.entity_instance,
    work_calendar: ifcopenshell.entity_instance,
) -> None:
    ifc.run("control.assign_control", relating_control=work_calendar, related_object=task)
    ifc.run("sequence.cascade_schedule", task=task)
    sequence.load_task_properties()


def remove_task_calendar(
    ifc: type[tool.Ifc],
    sequence: type[tool.Sequence],
    task: ifcopenshell.entity_instance,
    work_calendar: ifcopenshell.entity_instance,
) -> None:
    ifc.run("control.unassign_control", relating_control=work_calendar, related_object=task)
    ifc.run("sequence.cascade_schedule", task=task)
    sequence.load_task_properties()

