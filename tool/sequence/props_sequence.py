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




import bpy
import ifcopenshell
from typing import TYPE_CHECKING, Union
import bonsai.tool as tool

if TYPE_CHECKING:
    from bonsai.bim.module.sequence.prop import (
        BIMAnimationProperties,
        BIMStatusProperties,
        BIMTaskTreeProperties,
        BIMWorkCalendarProperties,
        BIMWorkPlanProperties,
        BIMWorkScheduleProperties,
    )

class PropsSequence:
    """Contiene métodos para acceder a las propiedades de Blender relacionadas con la secuencia."""


    @classmethod
    def get_work_schedule_props(cls) -> "BIMWorkScheduleProperties":
        assert (scene := bpy.context.scene)
        return scene.BIMWorkScheduleProperties  # pyright: ignore[reportAttributeAccessIssue]
    @classmethod
    def get_task_tree_props(cls) -> "BIMTaskTreeProperties":
        assert (scene := bpy.context.scene)
        return scene.BIMTaskTreeProperties  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def get_animation_props(cls) -> "BIMAnimationProperties":
        assert (scene := bpy.context.scene)
        return scene.BIMAnimationProperties  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def get_status_props(cls) -> "BIMStatusProperties":
        assert (scene := bpy.context.scene)
        return scene.BIMStatusProperties  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def get_work_plan_props(cls) -> "BIMWorkPlanProperties":
        assert (scene := bpy.context.scene)
        return scene.BIMWorkPlanProperties  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def get_work_calendar_props(cls) -> "BIMWorkCalendarProperties":
        assert (scene := bpy.context.scene)
        return scene.BIMWorkCalendarProperties  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def get_active_work_schedule(cls) -> Union[ifcopenshell.entity_instance, None]:
        props = cls.get_work_schedule_props()
        if not props.active_work_schedule_id:
            return None
        return tool.Ifc.get().by_id(props.active_work_schedule_id)

    @classmethod
    def get_active_task(cls) -> ifcopenshell.entity_instance:
        props = cls.get_work_schedule_props()
        return tool.Ifc.get().by_id(props.active_task_id)

    @classmethod
    def get_active_work_time(cls) -> ifcopenshell.entity_instance:
        props = cls.get_work_calendar_props()
        return tool.Ifc.get().by_id(props.active_work_time_id)











    

