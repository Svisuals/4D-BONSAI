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
import json
import bonsai.tool as tool
from . import props_sequence

try:
    from ..prop.animation import UnifiedColorTypeManager, get_user_created_groups_enum
except ImportError:
    # Fallback si la estructura cambia o para pruebas
    class UnifiedColorTypeManager:
        @staticmethod
        def _read_sets_json(context): return {}
        @staticmethod
        def _write_sets_json(context, data): pass
        @staticmethod
        def get_all_groups(context): return []
        @staticmethod
        def get_user_created_groups(context): return []
        @staticmethod
        def ensure_default_group(context): pass
    def get_user_created_groups_enum(self, context): return [("NONE", "None", "")]


def load_ColorType_group_data(group_name):
    """Loads data from a specific profile group"""
    scene = bpy.context.scene
    raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        return data.get(group_name, {})
    except Exception:
        return {}


def get_all_ColorType_groups():
    """Gets all available profile groups"""
    return UnifiedColorTypeManager.get_all_groups(bpy.context)


def get_custom_ColorType_groups():
    """Gets only custom groups (without DEFAULT)"""
    return UnifiedColorTypeManager.get_user_created_groups(bpy.context)


def has_animation_colors():
    return bpy.context.scene.BIMAnimationProperties.task_output_colors


def load_default_animation_color_scheme():
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
    props = props_sequence.get_animation_props()
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


def create_default_ColorType_group():
    """
    Automatically creates the DEFAULT group with profiles for each PredefinedType.
    """
    scene = bpy.context.scene
    key = "BIM_AnimationColorSchemesSets"
    raw = scene.get(key, "{}")
    try:
        data = json.loads(raw) if isinstance(raw, str) else {}
    except Exception:
        data = {}
    if "DEFAULT" not in data:
        default_ColorTypes = {
            "CONSTRUCTION": {"start": [1, 1, 1, 0], "active": [0, 1, 0, 1], "end": [0.3, 1, 0.3, 1]},
            "INSTALLATION": {"start": [1, 1, 1, 0], "active": [0, 1, 0, 1], "end": [0.3, 0.8, 0.5, 1]},
            "DEMOLITION": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
            "REMOVAL": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
            "DISPOSAL": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
            "DISMANTLE": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
            "OPERATION": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
            "MAINTENANCE": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
            "ATTENDANCE": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
            "RENOVATION": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [0.9, 0.9, 0.9, 1]},
            "LOGISTIC": {"start": [1, 1, 1, 1], "active": [1, 1, 0, 1], "end": [1, 0.8, 0.3, 1]},
            "MOVE": {"start": [1, 1, 1, 1], "active": [1, 1, 0, 1], "end": [0.8, 0.6, 0, 1]},
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
                "end_transparency": 0.0,
                "hide_at_end": disappears
            })
        data["DEFAULT"] = {"ColorTypes": ColorTypes}
        scene[key] = json.dumps(data)


def get_assigned_ColorType_for_task(task, animation_props, active_group_name=None):
    """Gets the profile for a task GIVEN a specific active group."""
    if not active_group_name:
        try:
            for it in getattr(animation_props, 'animation_group_stack', []):
                if getattr(it, 'enabled', False) and getattr(it, 'group', None):
                    active_group_name = it.group
                    break
            if not active_group_name:
                active_group_name = getattr(animation_props, 'ColorType_groups', "DEFAULT")
        except Exception:
            active_group_name = "DEFAULT"

    task_id_str = str(task.id())
    task_config = None
    try:
        cache_raw = bpy.context.scene.get("_task_colortype_snapshot_cache_json")
        if cache_raw:
            task_config = json.loads(cache_raw).get(task_id_str)
    except Exception:
        task_config = None

    if task_config:
        for choice in task_config.get("groups", []):
            if choice.get("group_name") == active_group_name and choice.get("enabled", False):
                selected_value = choice.get("selected_value") or choice.get("selected_colortype")
                if selected_value:
                    ColorType = load_ColorType_from_group(active_group_name, selected_value)
                    if ColorType:
                        return ColorType

    task_predefined_type = getattr(task, "PredefinedType", "NOTDEFINED") or "NOTDEFINED"
    ColorType = load_ColorType_from_group(active_group_name, task_predefined_type)
    if ColorType:
        return ColorType

    if active_group_name != "DEFAULT":
        default_profile = load_ColorType_from_group("DEFAULT", task_predefined_type)
        if default_profile:
            return default_profile

    return load_ColorType_from_group("DEFAULT", "NOTDEFINED")


def load_ColorType_from_group(group_name, ColorType_name):
    group_data = load_ColorType_group_data(group_name)
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


def sync_active_group_to_json():
    """Sincroniza los perfiles del grupo activo de la UI al JSON de la escena"""
    anim_props = props_sequence.get_animation_props()
    active_group = getattr(anim_props, "ColorType_groups", None)
    if not active_group or active_group == "DEFAULT":
        return

    raw = bpy.context.scene.get("BIM_AnimationColorSchemesSets", "{}")
    data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    ColorTypes_data = []
    for ColorType in getattr(anim_props, "ColorTypes", []):
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
            "hide_at_end": bool(getattr(ColorType, "hide_at_end", False)),
        })
    data[active_group] = {"ColorTypes": ColorTypes_data}
    bpy.context.scene["BIM_AnimationColorSchemesSets"] = json.dumps(data)


def _get_best_ColorType_for_task(task, anim_props):
    """Determines the most appropriate profile for a task."""
    try:
        agn = None
        for it in getattr(anim_props, 'animation_group_stack', []):
            if getattr(it, 'enabled', False) and getattr(it, 'group', None):
                agn = it.group
                break
        agn = agn or 'DEFAULT'
        ColorType = get_assigned_ColorType_for_task(task, anim_props, agn)
        if ColorType:
            return ColorType
    except Exception:
        pass
    predefined_type = task.PredefinedType or "NOTDEFINED"
    prof = load_ColorType_from_group("DEFAULT", predefined_type)
    if prof:
        return prof
    return load_ColorType_from_group("DEFAULT", "NOTDEFINED")


def add_group_to_animation_stack():
    """Add a new group to the animation group stack"""
    anim_props = props_sequence.get_animation_props()
    item = anim_props.animation_group_stack.add()
    item.group = "DEFAULT"
    item.enabled = True
    anim_props.animation_group_stack_index = len(anim_props.animation_group_stack) - 1


def remove_group_from_animation_stack():
    """Remove the selected group from the animation group stack"""
    anim_props = props_sequence.get_animation_props()
    idx = anim_props.animation_group_stack_index
    if 0 <= idx < len(anim_props.animation_group_stack):
        anim_props.animation_group_stack.remove(idx)
        if anim_props.animation_group_stack_index >= len(anim_props.animation_group_stack):
            anim_props.animation_group_stack_index = len(anim_props.animation_group_stack) - 1


def move_group_in_animation_stack(direction):
    """Move the selected group up or down in the animation group stack"""
    anim_props = props_sequence.get_animation_props()
    idx = anim_props.animation_group_stack_index
    stack_len = len(anim_props.animation_group_stack)
    if not (0 <= idx < stack_len): return

    new_idx = idx - 1 if direction == "UP" and idx > 0 else idx + 1 if direction == "DOWN" and idx < stack_len - 1 else idx

def register_live_color_update_handler():
    """Register the live color update handler for real-time updates"""
    from . import animation_sequence
    try:
        animation_sequence.register_live_color_update_handler()
    except Exception as e:
        print(f"Error registering live color update handler: {e}")

def unregister_live_color_update_handler():
    """Unregister the live color update handler"""
    from . import animation_sequence
    try:
        animation_sequence.unregister_live_color_update_handler()
    except Exception as e:
        print(f"Error unregistering live color update handler: {e}")

def get_product_frames_with_ColorTypes(work_schedule, settings):
    """Get product frames enhanced with ColorType information"""
    from . import animation_sequence
    
    # Get basic product frames from animation module
    product_frames = animation_sequence.get_animation_product_frames(work_schedule, settings)
    
    # Enhance with ColorType information
    enhanced_frames = {}
    
    for product_id, frames in product_frames.items():
        enhanced_frames[product_id] = []
        
        for frame in frames:
            enhanced_frame = frame.copy()
            
            # Add ColorType information based on task
            try:
                task = frame.get('task')
                if task:
                    from . import props_sequence
                    animation_props = props_sequence.get_animation_props()
                    color_type = get_assigned_ColorType_for_task(task, animation_props)
                    enhanced_frame['color_type'] = color_type
                else:
                    enhanced_frame['color_type'] = None
            except Exception as e:
                print(f"Error getting ColorType for task: {e}")
                enhanced_frame['color_type'] = None
            
            enhanced_frames[product_id].append(enhanced_frame)
    
    return enhanced_frames
    if new_idx == idx: return

    anim_props.animation_group_stack.move(idx, new_idx)
    anim_props.animation_group_stack_index = new_idx


def copy_task_colortype_config():
    """Copy ColorType configuration from the active task to selected tasks."""
    tprops = props_sequence.get_task_tree_props()
    ws_props = props_sequence.get_work_schedule_props()
    if not tprops or not tprops.tasks or ws_props.active_task_index >= len(tprops.tasks): return

    source_task = tprops.tasks[ws_props.active_task_index]
    selected_tasks = [task for task in tprops.tasks if getattr(task, 'is_selected', False)]
    if not selected_tasks: return

    for target_task in selected_tasks:
        if target_task.ifc_definition_id == source_task.ifc_definition_id: continue
        try:
            target_task.use_active_colortype_group = getattr(source_task, 'use_active_colortype_group', False)
            target_task.selected_colortype_in_active_group = getattr(source_task, 'selected_colortype_in_active_group', "")
            if hasattr(target_task, 'animation_color_schemes'):
                target_task.animation_color_schemes = source_task.animation_color_schemes

            target_task.colortype_group_choices.clear()
            for source_group in source_task.colortype_group_choices:
                target_group = target_task.colortype_group_choices.add()
                target_group.group_name = source_group.group_name
                target_group.enabled = source_group.enabled
                for attr in ("selected_colortype", "selected", "active_colortype", "colortype"):
                    if hasattr(source_group, attr) and hasattr(target_group, attr):
                        setattr(target_group, attr, getattr(source_group, attr))
                        break
        except Exception as e:
            print(f"Error copying to task {target_task.ifc_definition_id}: {e}")