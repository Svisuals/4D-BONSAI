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
    import bonsai.tool as tool

def add_task_column(sequence: type[tool.Sequence], column_type: str, name: str, data_type: str) -> None:
    sequence.add_task_column(column_type, name, data_type)
    work_schedule = sequence.get_active_work_schedule()
    if work_schedule:
        sequence.load_task_tree(work_schedule)
        sequence.load_task_properties()


def remove_task_column(sequence: type[tool.Sequence], name: str) -> None:
    sequence.remove_task_column(name)


def set_task_sort_column(sequence: type[tool.Sequence], column: str) -> None:
    sequence.set_task_sort_column(column)
    work_schedule = sequence.get_active_work_schedule()
    if work_schedule:
        sequence.load_task_tree(work_schedule)
        sequence.load_task_properties()

def setup_default_task_columns(sequence: type[tool.Sequence]) -> None:
    sequence.setup_default_task_columns()



