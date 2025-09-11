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


def add_work_plan(ifc: type[tool.Ifc]) -> ifcopenshell.entity_instance:
    return ifc.run("sequence.add_work_plan")


def remove_work_plan(ifc: type[tool.Ifc], work_plan: ifcopenshell.entity_instance) -> None:
    ifc.run("sequence.remove_work_plan", work_plan=work_plan)


def enable_editing_work_plan(sequence: type[tool.Sequence], work_plan: ifcopenshell.entity_instance) -> None:
    sequence.load_work_plan_attributes(work_plan)
    sequence.enable_editing_work_plan(work_plan)


def disable_editing_work_plan(sequence: type[tool.Sequence]) -> None:
    sequence.disable_editing_work_plan()


def edit_work_plan(ifc: type[tool.Ifc], sequence: type[tool.Sequence], work_plan: ifcopenshell.entity_instance) -> None:
    attributes = sequence.get_work_plan_attributes()
    ifc.run("sequence.edit_work_plan", work_plan=work_plan, attributes=attributes)
    sequence.disable_editing_work_plan()