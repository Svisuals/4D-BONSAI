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

def enable_editing_task_sequence(sequence: type[tool.Sequence]) -> None:
    sequence.enable_editing_task_sequence()
    sequence.load_task_properties()


def enable_editing_sequence_attributes(
    sequence: type[tool.Sequence], rel_sequence: ifcopenshell.entity_instance
) -> None:
    sequence.enable_editing_rel_sequence_attributes(rel_sequence)
    sequence.load_rel_sequence_attributes(rel_sequence)


def enable_editing_sequence_lag_time(
    sequence: type[tool.Sequence], rel_sequence: ifcopenshell.entity_instance, lag_time: ifcopenshell.entity_instance
) -> None:
    sequence.load_lag_time_attributes(lag_time)
    sequence.enable_editing_sequence_lag_time(rel_sequence)


def unassign_lag_time(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], rel_sequence: ifcopenshell.entity_instance
) -> None:
    ifc.run("sequence.unassign_lag_time", rel_sequence=rel_sequence)
    sequence.load_task_properties()


def assign_lag_time(ifc: type[tool.Ifc], rel_sequence: ifcopenshell.entity_instance) -> None:
    ifc.run("sequence.assign_lag_time", rel_sequence=rel_sequence, lag_value="P1D")


def edit_sequence_attributes(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], rel_sequence: ifcopenshell.entity_instance
) -> None:
    attributes = sequence.get_rel_sequence_attributes()
    ifc.run("sequence.edit_sequence", rel_sequence=rel_sequence, attributes=attributes)
    sequence.disable_editing_rel_sequence()
    sequence.load_task_properties()


def edit_sequence_lag_time(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], lag_time: ifcopenshell.entity_instance
) -> None:
    attributes = sequence.get_lag_time_attributes()
    ifc.run("sequence.edit_lag_time", lag_time=lag_time, attributes=attributes)
    sequence.disable_editing_rel_sequence()
    sequence.load_task_properties()


def disable_editing_rel_sequence(sequence: type[tool.Sequence]) -> None:
    sequence.disable_editing_rel_sequence()
