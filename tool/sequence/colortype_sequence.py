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
import json
import ifcopenshell
from typing import Optional

from .props_sequence import PropsSequence
import bonsai.tool as tool

# Importación segura de la dependencia principal para la gestión de grupos de colores
try:
    from bonsai.bim.module.sequence.prop.animation import UnifiedColorTypeManager
except ImportError:
    class UnifiedColorTypeManager:
        @staticmethod
        def get_all_groups(context): return {}
        @staticmethod
        def get_user_created_groups(context): return {}
        
          
class ColorTypeSequence(PropsSequence):
    """Manejo de perfiles de color (ColorTypes) y su asignación a tareas."""

    @classmethod
    def load_ColorType_group_data(cls, group_name):
        """Loads data from a specific profile group"""
        import bpy, json
        scene = bpy.context.scene
        raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
            return data.get(group_name, {})
        except Exception:
            return {}

    @classmethod
    def get_all_ColorType_groups(cls):
        """Gets all available profile groups"""
        import bpy
        return UnifiedColorTypeManager.get_all_groups(bpy.context)

    @classmethod
    def get_custom_ColorType_groups(cls):
        """Gets only custom groups (without DEFAULT)"""
        import bpy
        return UnifiedColorTypeManager.get_user_created_groups(bpy.context)

    @classmethod
    def has_animation_colors(cls):
        return bpy.context.scene.BIMAnimationProperties.task_output_colors

    @classmethod
    def load_default_animation_color_scheme(cls):
        def _to_rgba(col):
            try:
                if isinstance(col, (list, tuple)):
                    if len(col) >= 4:
                        return (float(col[0]), float(col[1]), float(col[2]), float(col[3]))
                    if len(col) == 3:
                        return (float(col[0]), float(col[1]), float(col[2]), 1.0)
            except Exception:
                pass
            return (1.0, 0.0, 0.0, 1.0)

        groups = {
            "CREATION": {"PredefinedType": ["CONSTRUCTION", "INSTALLATION"], "Color": (0.0, 1.0, 0.0)},
            "OPERATION": {"PredefinedType": ["ATTENDANCE", "MAINTENANCE", "OPERATION", "RENOVATION"], "Color": (0.0, 0.0, 1.0)},
            "MOVEMENT_TO": {"PredefinedType": ["LOGISTIC", "MOVE"], "Color": (1.0, 1.0, 0.0)},
            "DESTRUCTION": {"PredefinedType": ["DEMOLITION", "DISMANTLE", "DISPOSAL", "REMOVAL"], "Color": (1.0, 0.0, 0.0)},
            "MOVEMENT_FROM": {"PredefinedType": ["LOGISTIC", "MOVE"], "Color": (1.0, 0.5, 0.0)},
            "USERDEFINED": {"PredefinedType": ["USERDEFINED", "NOTDEFINED"], "Color": (0.2, 0.2, 0.2)},
        }

        props = cls.get_animation_props()
        props.task_output_colors.clear()
        props.task_input_colors.clear()

        for group, data in groups.items():
            for predefined_type in data["PredefinedType"]:
                if group in ["CREATION", "OPERATION", "MOVEMENT_TO"]:
                    item = props.task_output_colors.add()
                elif group in ["MOVEMENT_FROM"]:
                    item = props.task_input_colors.add()
                elif group in ["USERDEFINED", "DESTRUCTION"]:
                    item = props.task_input_colors.add()
                    item2 = props.task_output_colors.add()
                    item2.name = predefined_type
                    item2.color = _to_rgba(data["Color"])
                item.name = predefined_type
                item.color = _to_rgba(data["Color"])

    @classmethod
    def create_default_ColorType_group(cls):
            """
            Automatically creates the DEFAULT group with profiles for each PredefinedType.
            This group is used when the user has not configured any profiles.
            """
            import json
            scene = bpy.context.scene
            key = "BIM_AnimationColorSchemesSets"
            raw = scene.get(key, "{}")
            try:
                data = json.loads(raw) if isinstance(raw, str) else {}
            except Exception:
                data = {}
            if "DEFAULT" not in data:
                default_ColorTypes = {
                    # Green Group (Construction)
                    "CONSTRUCTION": {"start": [1, 1, 1, 0], "active": [0, 1, 0, 1], "end": [0.3, 1, 0.3, 1]},
                    "INSTALLATION": {"start": [1, 1, 1, 0], "active": [0, 1, 0, 1], "end": [0.3, 0.8, 0.5, 1]},

                    # Red Group (Demolition)
                    "DEMOLITION": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
                    "REMOVAL": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
                    "DISPOSAL": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
                    "DISMANTLE": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},

                    # Blue Group (Operation / Maintenance)
                    "OPERATION": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
                    "MAINTENANCE": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
                    "ATTENDANCE": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
                    "RENOVATION": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [0.9, 0.9, 0.9, 1]},

                    # Yellow Group (Logistics)
                    "LOGISTIC": {"start": [1, 1, 1, 1], "active": [1, 1, 0, 1], "end": [1, 0.8, 0.3, 1]},
                    "MOVE": {"start": [1, 1, 1, 1], "active": [1, 1, 0, 1], "end": [0.8, 0.6, 0, 1]},
                    
                    # Gray Group (Undefined / Others)
                    "NOTDEFINED": {"start": [0.7, 0.7, 0.7, 1], "active": [0.5, 0.5, 0.5, 1], "end": [0.3, 0.3, 0.3, 1]},
                    "USERDEFINED": {"start": [0.7, 0.7, 0.7, 1], "active": [0.5, 0.5, 0.5, 1], "end": [0.3, 0.3, 0.3, 1]}
                }
                ColorTypes = []
                for name, colors in default_ColorTypes.items():
                    disappears = name in ["DEMOLITION", "REMOVAL", "DISPOSAL", "DISMANTLE"]
                    ColorTypes.append({
                        "name": name,
                        "consider_start": True,
                        "consider_active": True,
                        "consider_end": True,
                        "start_color": colors["start"],
                        "in_progress_color": colors["active"],
                        "end_color": colors["end"],
                        "use_start_original_color": False,
                        "use_active_original_color": False,
                        "use_end_original_color": not disappears,
                        "start_transparency": 0.0,
                        "active_start_transparency": 0.0,
                        "active_finish_transparency": 0.0,
                        "active_transparency_interpol": 1.0,
                        "end_transparency": 0.0
                    })
                data["DEFAULT"] = {"ColorTypes": ColorTypes}
                scene[key] = json.dumps(data)


    @classmethod
    def get_assigned_ColorType_for_task(cls, task: ifcopenshell.entity_instance, animation_props, active_group_name: Optional[str] = None):
        """Gets the profile for a task GIVEN a specific active group."""
        # Resolve active group if not provided
        if not active_group_name:
            try:
                ag = None
                for it in getattr(animation_props, 'animation_group_stack', []):
                    if getattr(it, 'enabled', False) and getattr(it, 'group', None):
                        ag = it.group
                        break
                if not ag:
                    ag = getattr(animation_props, 'ColorType_groups', None)
                active_group_name = ag or "DEFAULT"
            except Exception:
                active_group_name = "DEFAULT"

        # NEW: Get task configuration from the persistent cache instead of the UI list.
        # This makes the function independent of the current UI filters.
        import bpy, json
        context = bpy.context
        task_id_str = str(task.id())
        task_config = None
        
        try:
            cache_key = "_task_colortype_snapshot_cache_json"
            cache_raw = context.scene.get(cache_key)
            if cache_raw:
                cached_data = json.loads(cache_raw)
                task_config = cached_data.get(task_id_str)
        except Exception as e:
            print(f"Bonsai WARNING: Could not read task config cache: {e}")
            task_config = None

        # 1) Specific assignment by group in the task
        if task_config:
            for choice in task_config.get("groups", []):
                is_enabled = choice.get("enabled", False)
                group_name = choice.get("group_name")
                selected_value = choice.get("selected_value") or choice.get("selected_colortype")
                if group_name == active_group_name and is_enabled and selected_value:
                    ColorType = cls.load_ColorType_from_group(active_group_name, selected_value)
                    if ColorType:
                        return ColorType

        task_predefined_type = getattr(task, "PredefinedType", "NOTDEFINED") or "NOTDEFINED"

        # 2) PredefinedType in active group
        ColorType = cls.load_ColorType_from_group(active_group_name, task_predefined_type)
        if ColorType:
            return ColorType

        # If the active group wasn't DEFAULT and we didn't find a profile,
        # explicitly fall back to the DEFAULT group. This is more predictable.
        if active_group_name != "DEFAULT":
            default_profile = cls.load_ColorType_from_group("DEFAULT", task_predefined_type)
            if default_profile:
                return default_profile

        # As an absolute last resort (which should not be reached), return the "NOTDEFINED" profile.
        return cls.load_ColorType_from_group("DEFAULT", "NOTDEFINED")



    @classmethod
    def load_ColorType_from_group(cls, group_name, ColorType_name):
        import bpy, json
        scene = bpy.context.scene
        raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            data = {}
        group_data = data.get(group_name, {})
        for prof_data in group_data.get("ColorTypes", []):
            if prof_data.get("name") == ColorType_name:
                return type('AnimationColorSchemes', (object,), {
                    'name': prof_data.get("name", ""),
                    'consider_start': prof_data.get("consider_start", True),
                    'consider_active': prof_data.get("consider_active", True),
                    'consider_end': prof_data.get("consider_end", True),
                    'start_color': prof_data.get("start_color", [1,1,1,1]),
                    'in_progress_color': prof_data.get("in_progress_color", [1,1,0,1]),
                    'end_color': prof_data.get("end_color", [0,1,0,1]),
                    'use_start_original_color': prof_data.get("use_start_original_color", False),
                    'use_active_original_color': prof_data.get("use_active_original_color", False),
                    'use_end_original_color': prof_data.get("use_end_original_color", True),
                    'start_transparency': prof_data.get("start_transparency", 0.0),
                    'active_start_transparency': prof_data.get("active_start_transparency", 0.0),
                    'active_finish_transparency': prof_data.get("active_finish_transparency", 0.0),
                    'active_transparency_interpol': prof_data.get("active_transparency_interpol", 1.0),
                    'end_transparency': prof_data.get("end_transparency", 0.0),
                    'hide_at_end': bool(prof_data.get("hide_at_end", prof_data.get("name") in {"DEMOLITION","REMOVAL","DISPOSAL","DISMANTLE"})),
                })()
        return None


    @classmethod
    def sync_active_group_to_json(cls):
        """Sincroniza los perfiles del grupo activo de la UI al JSON de la escena"""
        import bpy, json
        scene = bpy.context.scene
        anim_props = cls.get_animation_props()
        active_group = getattr(anim_props, "ColorType_groups", None)
        if not active_group:
            return

       
        if active_group == "DEFAULT":
            # El grupo DEFAULT es de solo lectura y se gestiona automáticamente.
            # Esto previene que perfiles personalizados se guarden en él por error.
            print("Bonsai INFO: The 'DEFAULT' group is read-only and cannot be modified from the UI.")
            return

        raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            data = {}
        ColorTypes_data = []
        for ColorType in getattr(anim_props, "ColorTypes", []):
            try:
                ColorTypes_data.append({
                    "name": ColorType.name,
                    "consider_start": bool(getattr(ColorType, "consider_start", True)),
                    "consider_active": bool(getattr(ColorType, "consider_active", True)),
                    "consider_end": bool(getattr(ColorType, "consider_end", True)),
                    "start_color": list(getattr(ColorType, "start_color", [1,1,1,1])),
                    "in_progress_color": list(getattr(ColorType, "in_progress_color", [1,1,0,1])),
                    "end_color": list(getattr(ColorType, "end_color", [0,1,0,1])),
                    "use_start_original_color": bool(getattr(ColorType, "use_start_original_color", False)),
                    "use_active_original_color": bool(getattr(ColorType, "use_active_original_color", False)),
                    "use_end_original_color": bool(getattr(ColorType, "use_end_original_color", True)),
                    "start_transparency": float(getattr(ColorType, "start_transparency", 0.0)),
                    "active_start_transparency": float(getattr(ColorType, "active_start_transparency", 0.0)),
                    "active_finish_transparency": float(getattr(ColorType, "active_finish_transparency", 0.0)),
                    "active_transparency_interpol": float(getattr(ColorType, "active_transparency_interpol", 1.0)),
                    "end_transparency": float(getattr(ColorType, "end_transparency", 0.0)),
                    "hide_at_end": bool(getattr(ColorType, "hide_at_end", getattr(ColorType, "name", "") in {"DEMOLITION","REMOVAL","DISPOSAL","DISMANTLE"})),
                })
            except Exception:
                pass
        data[active_group] = {"ColorTypes": ColorTypes_data}
        scene["BIM_AnimationColorSchemesSets"] = json.dumps(data)


    @classmethod
    def _get_best_ColorType_for_task(cls, task, anim_props):
            """Determina el perfil más apropiado para una tarea considerando la pila de grupos y elección por tarea."""
            """Determines the most appropriate profile for a task considering the group stack and choice per task."""
            try:
                # Determine the active group (first enabled group in the stack) or DEFAULT
                agn = None
                for it in getattr(anim_props, 'animation_group_stack', []):
                    if getattr(it, 'enabled', False) and getattr(it, 'group', None):
                        agn = it.group
                        break
                if not agn:
                    agn = 'DEFAULT'
                ColorType = cls.get_assigned_ColorType_for_task(task, anim_props, agn)
                if ColorType:
                    return ColorType
            except Exception:
                pass
            predefined_type = task.PredefinedType or "NOTDEFINED"
            # Try in DEFAULT
            try:
                prof = cls.load_ColorType_from_group("DEFAULT", predefined_type)
                if prof:
                    return prof
            except Exception:
                pass
            # Fallback to the NOTDEFINED profile from the DEFAULT group.
            return cls.load_ColorType_from_group("DEFAULT", "NOTDEFINED")

    @classmethod
    def _task_has_consider_start_ColorType(cls, task):
        """Helper to check if a task's resolved ColorType has consider_start=True."""
        try:
            # Re-use existing logic to find the best ColorType for the task
            anim_props = cls.get_animation_props()
            ColorType = cls._get_best_ColorType_for_task(task, anim_props)
            return getattr(ColorType, 'consider_start', False)
        except Exception as e:
            print(f"⚠️ Error in _task_has_consider_start_ColorType for task {getattr(task, 'Name', 'N/A')}: {e}")
            return False

    @classmethod
    def _apply_ColorType_to_object(cls, obj, frame_data, ColorType, original_color, settings):
            for state_name, (start_f, end_f) in frame_data["states"].items():
                if end_f < start_f:
                    continue
                if state_name == "before_start":
                    state = "start"
                elif state_name == "active":
                    state = "in_progress"
                elif state_name == "after_end":
                    state = "end"
                else:
                    continue
                if state == "start" and not getattr(ColorType, 'consider_start', True):
                    if frame_data.get("relationship") == "output":
                        obj.hide_viewport = True
                        obj.hide_render = True
                        obj.keyframe_insert(data_path="hide_viewport", frame=start_f)
                        obj.keyframe_insert(data_path="hide_render", frame=start_f)
                    return
                elif state == "in_progress" and not getattr(ColorType, 'consider_active', True):
                    return
                elif state == "end" and not getattr(ColorType, 'consider_end', True):
                    return
                cls.apply_state_appearance(obj, ColorType, state, start_f, end_f, original_color, frame_data)
                # Transparency: fade during active stretch
                try:
                    if state == 'in_progress':
                        vals0 = _seq_data.interpolate_ColorType_values(ColorType, 'in_progress', 0.0)
                        vals1 = _seq_data.interpolate_ColorType_values(ColorType, 'in_progress', 1.0)
                        a0 = float(vals0.get('alpha', obj.color[3] if len(obj.color) >= 4 else 1.0))
                        a1 = float(vals1.get('alpha', a0))
                        # Keyframes at the beginning and end of the active stretch
                        c = list(obj.color)
                        if len(c) < 4:
                            c = [c[0], c[1], c[2], 1.0]
                        c[3] = a0
                        obj.color = c
                        obj.keyframe_insert(data_path='color', frame=int(start_f))
                        c[3] = a1
                        obj.color = c
                        obj.keyframe_insert(data_path='color', frame=int(end_f))
                except Exception:
                    pass



















