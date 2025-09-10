# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>
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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..prop import (
        BIMAnimationProperties,
        BIMStatusProperties,
        BIMTaskTreeProperties,
        BIMWorkCalendarProperties,
        BIMWorkPlanProperties,
        BIMWorkScheduleProperties,
    )


def get_work_schedule_props():
    assert (scene := bpy.context.scene)
    return scene.BIMWorkScheduleProperties 

def get_task_tree_props():
    assert (scene := bpy.context.scene)
    return scene.BIMTaskTreeProperties  

def get_animation_props():
    assert (scene := bpy.context.scene)
    return scene.BIMAnimationProperties  

def get_status_props():
    assert (scene := bpy.context.scene)
    return scene.BIMStatusProperties  

def get_work_plan_props():
    assert (scene := bpy.context.scene)
    return scene.BIMWorkPlanProperties  

def get_work_calendar_props():
    assert (scene := bpy.context.scene)
    return scene.BIMWorkCalendarProperties  





