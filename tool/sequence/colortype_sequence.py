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
            print(f"Error copying ColorType config: {e}")

def _process_task_status_cached(task, status_cache=None):
    """Process task status with caching for performance"""
    if not task:
        return None
    
    task_id = task.id()
    
    # Use cache if provided
    if status_cache and task_id in status_cache:
        return status_cache[task_id]
    
    try:
        status = getattr(task, 'Status', 'Unknown')
        
        # Cache the result if cache provided
        if status_cache is not None:
            status_cache[task_id] = status
        
        return status
        
    except Exception as e:
        print(f"Error processing task status: {e}")
        return "Unknown"

def _process_task_with_ColorTypes(task, colortype_data):
    """Process task with ColorType data integration"""
    if not task or not colortype_data:
        return False
    
    try:
        task_id = task.id()
        
        # Get task ColorType configuration
        task_colortype = colortype_data.get(str(task_id), {})
        
        if not task_colortype:
            return False
        
        # Process ColorType groups
        colortype_groups = task_colortype.get('ColorType_groups', '')
        use_active_group = task_colortype.get('use_active_colortype_group', False)
        
        if use_active_group or colortype_groups:
            # Apply ColorType configuration to task
            from . import props_sequence
            tprops = props_sequence.get_task_tree_props()
            
            # Find task in UI and update ColorType settings
            for ui_task in tprops.tasks:
                if ui_task.ifc_definition_id == task_id:
                    if hasattr(ui_task, 'use_active_colortype_group'):
                        ui_task.use_active_colortype_group = use_active_group
                    if hasattr(ui_task, 'ColorType_groups'):
                        ui_task.ColorType_groups = colortype_groups
                    break
            
            print(f"Applied ColorType to task {task.Name}: groups='{colortype_groups}', active={use_active_group}")
            return True
        
        return False
        
    except Exception as e:
        print(f"Error processing task ColorTypes: {e}")
        return False

def _task_has_consider_start_ColorType(task):
    """Check if task has consider start ColorType configuration"""
    if not task:
        return False
    
    try:
        from . import props_sequence
        tprops = props_sequence.get_task_tree_props()
        
        # Find task in UI properties
        for ui_task in tprops.tasks:
            if ui_task.ifc_definition_id == task.id():
                # Check for consider start ColorType
                colortype_groups = getattr(ui_task, 'ColorType_groups', '')
                if 'consider_start' in colortype_groups.lower():
                    return True
                
                # Check group choices for consider start
                group_choices = getattr(ui_task, 'colortype_group_choices', [])
                for choice in group_choices:
                    if hasattr(choice, 'group_name'):
                        if 'consider_start' in choice.group_name.lower():
                            return True
                break
        
        return False
        
    except Exception as e:
        print(f"Error checking consider start ColorType: {e}")
        return False


def _apply_color_to_object_simple(obj, color):
    """Simple color application to object"""
    if not obj or not color:
        return
    
    try:
        # Create or get material
        mat_name = f"4D_Color_{obj.name}"
        if mat_name in bpy.data.materials:
            mat = bpy.data.materials[mat_name]
        else:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs[0].default_value = (*color[:3], 1.0)  # RGB + Alpha
        
        # Apply material to object
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
            
    except Exception as e:
        print(f"❌ Simple color application error: {e}")


def _apply_ColorType_to_object(obj, colortype_data):
    """Apply ColorType configuration to object with full feature support"""
    if not obj or not colortype_data:
        return
    
    try:
        # Get ColorType settings
        color = colortype_data.get('color', (1.0, 1.0, 1.0, 1.0))
        transparency = colortype_data.get('transparency', 1.0)
        
        # Create ColorType material
        mat_name = f"4D_ColorType_{obj.name}"
        if mat_name in bpy.data.materials:
            mat = bpy.data.materials[mat_name]
        else:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            
            # Setup material nodes
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs[0].default_value = color  # Base Color
                bsdf.inputs[21].default_value = 1.0 - transparency  # Alpha
                
                if transparency < 1.0:
                    mat.blend_method = 'BLEND'
                    mat.show_transparent_back = True
        
        # Apply material
        if obj.data and hasattr(obj.data, 'materials'):
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
                
        # Store ColorType metadata
        obj['4d_colortype_applied'] = True
        obj['4d_colortype_data'] = str(colortype_data)
        
    except Exception as e:
        print(f"❌ ColorType application error: {e}")


def activate_variance_color_mode():
    """Activate variance color mode for schedule analysis"""
    try:
        props = props_sequence.get_work_schedule_props()
        props.use_variance_colors = True
        
        # Set up variance color tracking
        if not hasattr(bpy.app, '_4d_variance_mode'):
            bpy.app._4d_variance_mode = True
            
        # Trigger UI refresh
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
                
        print("✅ Variance color mode activated")
        
    except Exception as e:
        print(f"❌ Variance color mode activation error: {e}")


def deactivate_variance_color_mode():
    """Deactivate variance color mode"""
    try:
        props = props_sequence.get_work_schedule_props()
        props.use_variance_colors = False
        
        # Clear variance tracking
        if hasattr(bpy.app, '_4d_variance_mode'):
            bpy.app._4d_variance_mode = False
            
        # Restore original colors
        _restore_original_object_colors()
        
        print("✅ Variance color mode deactivated")
        
    except Exception as e:
        print(f"❌ Variance color mode deactivation error: {e}")


def clear_variance_color_mode():
    """Clear all variance color data"""
    try:
        deactivate_variance_color_mode()
        clear_variance_colors_only()
        
        # Clear stored variance data
        if hasattr(bpy.app, '_4d_variance_data'):
            delattr(bpy.app, '_4d_variance_data')
            
    except Exception as e:
        print(f"❌ Variance color clearing error: {e}")


def clear_variance_colors_only():
    """Clear only variance colors, keep mode active"""
    try:
        # Remove variance materials
        for mat in bpy.data.materials:
            if mat.name.startswith("4D_Variance_"):
                bpy.data.materials.remove(mat)
                
        # Clear object variance metadata
        for obj in bpy.data.objects:
            if '4d_variance_color' in obj:
                del obj['4d_variance_color']
                
    except Exception as e:
        print(f"❌ Variance colors clearing error: {e}")


def _save_original_object_colors():
    """Save original object colors before applying variance colors"""
    try:
        if not hasattr(bpy.app, '_4d_original_colors'):
            bpy.app._4d_original_colors = {}
            
        for obj in bpy.data.objects:
            if obj.data and hasattr(obj.data, 'materials') and obj.data.materials:
                mat = obj.data.materials[0]
                if mat and mat.use_nodes:
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        original_color = list(bsdf.inputs[0].default_value)
                        bpy.app._4d_original_colors[obj.name] = {
                            'material_name': mat.name,
                            'color': original_color
                        }
                        
    except Exception as e:
        print(f"❌ Original color saving error: {e}")


def _restore_original_object_colors():
    """Restore original object colors"""
    try:
        if not hasattr(bpy.app, '_4d_original_colors'):
            return
            
        for obj_name, color_data in bpy.app._4d_original_colors.items():
            obj = bpy.data.objects.get(obj_name)
            if obj and obj.data and hasattr(obj.data, 'materials'):
                mat_name = color_data.get('material_name')
                if mat_name and mat_name in bpy.data.materials:
                    mat = bpy.data.materials[mat_name]
                    if mat.use_nodes:
                        bsdf = mat.node_tree.nodes.get("Principled BSDF")
                        if bsdf:
                            bsdf.inputs[0].default_value = color_data['color']
                            
    except Exception as e:
        print(f"❌ Original color restoration error: {e}")


def _get_variance_color_for_object_real(obj, task):
    """Get real variance color for object based on task status"""
    try:
        if not obj or not task:
            return (1.0, 1.0, 1.0, 1.0)  # Default white
        
        # Get task status and timing
        actual_start = ifcopenshell.util.sequence.get_actual_start(task)
        actual_finish = ifcopenshell.util.sequence.get_actual_finish(task) 
        planned_start = ifcopenshell.util.sequence.get_start_time(task)
        planned_finish = ifcopenshell.util.sequence.get_finish_time(task)
        
        if not planned_start or not planned_finish:
            return (0.7, 0.7, 0.7, 1.0)  # Gray for no planning data
        
        # Calculate variance
        if actual_start and actual_finish:
            # Task completed - check if on time
            if actual_finish <= planned_finish:
                return (0.0, 1.0, 0.0, 1.0)  # Green - on time
            else:
                return (1.0, 0.5, 0.0, 1.0)  # Orange - late completion
        elif actual_start:
            # Task in progress
            current_date = datetime.now()
            if current_date.date() > planned_finish.date():
                return (1.0, 0.0, 0.0, 1.0)  # Red - overdue
            else:
                return (0.0, 0.0, 1.0, 1.0)  # Blue - in progress
        else:
            # Task not started
            current_date = datetime.now()
            if current_date.date() > planned_start.date():
                return (1.0, 1.0, 0.0, 1.0)  # Yellow - delayed start
            else:
                return (0.8, 0.8, 0.8, 1.0)  # Light gray - not started
                
    except Exception as e:
        print(f"❌ Variance color calculation error: {e}")
        return (1.0, 1.0, 1.0, 1.0)


def _create_variance_colortype_group():
    """Create variance-specific ColorType group"""
    try:
        props = props_sequence.get_work_schedule_props()
        
        # Add variance group
        variance_group = props.colortype_groups.add()
        variance_group.name = "Variance Analysis"
        variance_group.description = "Automatic variance color analysis"
        variance_group.is_system_group = True
        
        # Add variance color types
        colors = [
            ("On Time", (0.0, 1.0, 0.0, 1.0), "Tasks completed on schedule"),
            ("Late", (1.0, 0.5, 0.0, 1.0), "Tasks completed late"),
            ("Overdue", (1.0, 0.0, 0.0, 1.0), "Tasks overdue"),
            ("In Progress", (0.0, 0.0, 1.0, 1.0), "Tasks currently in progress"),
            ("Delayed Start", (1.0, 1.0, 0.0, 1.0), "Tasks with delayed start"),
            ("Not Started", (0.8, 0.8, 0.8, 1.0), "Tasks not yet started")
        ]
        
        for name, color, desc in colors:
            colortype = variance_group.color_types.add()
            colortype.name = name
            colortype.color = color
            colortype.description = desc
            
        return variance_group
        
    except Exception as e:
        print(f"❌ Variance ColorType group creation error: {e}")
        return None