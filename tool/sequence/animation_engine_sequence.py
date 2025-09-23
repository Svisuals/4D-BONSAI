# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021, 2022 Dion Moult <dion@thinkmoult.com>, Yassine Oualid <yassine@sigmadimensions.com>, Federico Eraso <feraso@svisuals.net
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
import bpy
import json
import mathutils
import ifcopenshell
import bonsai.tool as tool
from typing import Any, Union
from .props_sequence import PropsSequence
from .color_management_sequence import ColorManagementSequence
from .date_utils_sequence import DateUtilsSequence
from .task_icom_sequence import TaskIcomSequence

class AnimationEngineSequence(ColorManagementSequence, DateUtilsSequence, TaskIcomSequence):
    """Mixin class for the core 4D animation engine."""

    @classmethod
    def set_object_shading(cls):
        area = tool.Blender.get_view3d_area()
        if area:
            space = area.spaces.active
            if space and space.type == 'VIEW_3D':
                space.shading.color_type = "OBJECT"

    @classmethod
    def get_animation_settings(cls):
        """Get animation settings using visualization dates."""
        def calculate_total_frames(fps):
            if props.speed_types == "FRAME_SPEED":
                return calculate_using_frames(
                    start,
                    finish,
                    props.speed_animation_frames,
                    ifcopenshell.util.date.parse_duration(props.speed_real_duration),
                )
            elif props.speed_types == "DURATION_SPEED":
                return calculate_using_duration(
                    start,
                    finish,
                    props.speed_animation_frames,
                    ifcopenshell.util.date.parse_duration(props.speed_real_duration),
                )
            elif props.speed_types == "MULTIPLIER_SPEED":
                return calculate_using_multiplier(
                    start, finish, props.speed_animation_frames, props.speed_multiplier
                )
            else:
                return {"start_frame": int(scene.frame_start), "end_frame": int(scene.frame_end)}

        def calculate_using_frames(start, finish, frames, duration):
            return {"start_frame": int(scene.frame_start), "total_frames": int(frames), "speed": 1.0}

        def calculate_using_duration(start, finish, frames, duration):
            if not (start and finish):
                return {"start_frame": int(scene.frame_start), "end_frame": int(scene.frame_end)}
            schedule_duration = (finish - start).total_seconds()
            real_duration = duration.total_seconds() if duration else schedule_duration
            if real_duration == 0:
                fps_multiplier = 1.0
            else:
                fps_multiplier = schedule_duration / real_duration
            return {
                "start_frame": int(scene.frame_start),
                "total_frames": int(frames),
                "speed": fps_multiplier,
            }

        def calculate_using_multiplier(start, finish, frames, multiplier):
            return {"start_frame": int(scene.frame_start), "total_frames": int(frames), "speed": multiplier}

        scene = bpy.context.scene
        props = cls.get_animation_props()

        start, finish = cls.get_visualization_date_range()

        if not (start and finish):
            print("❌ WARNING: No animation dates configured. Using schedule dates as fallback.")
            start, finish = cls.get_schedule_date_range()
            if not (start and finish):
                print("❌ ERROR: No dates available for animation")
                return None

        if start and finish:
            print(f"🎯 Animation usando fechas de visualización:")
            print(f"   Start: {start.strftime('%Y-%m-%d')}")
            print(f"   Finish: {finish.strftime('%Y-%m-%d')}")

        fps = bpy.context.scene.render.fps
        total_frames_data = calculate_total_frames(fps)

        return {
            "start": start,
            "finish": finish,
            "total_frames": total_frames_data.get("total_frames", scene.frame_end - scene.frame_start),
            "start_frame": total_frames_data.get("start_frame", scene.frame_start),
            "speed": total_frames_data.get("speed", 1.0),
            "include_relation_space": props.include_relation_space,
            "related_element_color": props.related_element_color,
            "is_editing": props.is_editing,
            "exclude_color": props.exclude_color,
            "include_diff": props.include_diff,
            "diff_new_colour": props.diff_new_colour,
            "diff_modified_colour": props.diff_modified_colour,
            "diff_deleted_colour": props.diff_deleted_colour,
            "schedule_start": None,
            "schedule_finish": None,
        }

    @classmethod
    def get_task_for_product(cls, product):
        """Obtiene la tarea asociada a un producto IFC."""
        element = tool.Ifc.get_entity(product) if hasattr(product, 'name') else product
        if not element:
            return None

        assignments = getattr(element, 'HasAssignments', [])
        for assignment in assignments:
            if assignment.is_a('IfcRelAssignsToProcess'):
                relating_process = assignment.RelatingProcess
                if relating_process and relating_process.is_a('IfcTask'):
                    return relating_process

        return None