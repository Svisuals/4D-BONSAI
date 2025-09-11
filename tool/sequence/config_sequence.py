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
import ifcopenshell.api
import ifcopenshell.util.sequence
import bonsai.tool as tool
from . import props_sequence
from . import colortype_sequence
from . import task_sequence
from . import utils_sequence

try:
    from ...operators.schedule_task_operators import snapshot_all_ui_state, restore_all_ui_state
except ImportError:
    def snapshot_all_ui_state(context): pass
    def restore_all_ui_state(context): pass

try:
    from ...prop.animation import UnifiedColorTypeManager
except ImportError:
    class UnifiedColorTypeManager:
        @staticmethod
        def _read_sets_json(context): return {}
        @staticmethod
        def _write_sets_json(context, data): pass


def _force_complete_task_snapshot(context, work_schedule):
    """
    Fuerza una captura completa de TODAS las tareas del cronograma especificado.
    """
    def get_all_tasks_recursive(tasks):
        all_tasks = []
        for task in tasks:
            all_tasks.append(task)
            nested = ifcopenshell.util.sequence.get_nested_tasks(task)
            if nested:
                all_tasks.extend(get_all_tasks_recursive(nested))
        return all_tasks

    root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
    all_schedule_tasks = get_all_tasks_recursive(root_tasks)
    
    cache_key = "_task_colortype_snapshot_cache_json"
    cache_raw = context.scene.get(cache_key, "{}")
    cache_data = json.loads(cache_raw) if cache_raw else {}
    
    tasks_added_to_cache = 0
    for task in all_schedule_tasks:
        tid = str(task.id())
        if tid != "0" and tid not in cache_data:
            cache_data[tid] = {"active": False, "selected_active_colortype": "", "animation_color_schemes": "", "groups": []}
            tasks_added_to_cache += 1
    
    if tasks_added_to_cache > 0:
        context.scene[cache_key] = json.dumps(cache_data)


def _sync_source_animation_color_schemes(context):
    """
    Sincroniza el campo animation_color_schemes en tareas que tienen grupo activo.
    """
    try:
        from ...prop.animation import safe_set_animation_color_schemes
        tprops = props_sequence.get_task_tree_props()
        for task in getattr(tprops, 'tasks', []):
            if getattr(task, 'use_active_colortype_group', False):
                current_schemes = getattr(task, 'animation_color_schemes', '')
                selected_colortype = ''
                for choice in getattr(task, 'colortype_group_choices', []):
                    if getattr(choice, 'enabled', False) and getattr(choice, 'group_name', '') != 'DEFAULT':
                        selected_colortype = getattr(choice, 'selected_colortype', '')
                        if selected_colortype: break
                if selected_colortype and selected_colortype != current_schemes:
                    safe_set_animation_color_schemes(task, selected_colortype)
    except Exception as e:
        print(f"❌ Copy3D SYNC Error: {e}")


def _force_fresh_snapshot_from_ui(context):
    """
    Fuerza un snapshot fresco basado en el estado actual de la UI.
    """
    tprops = props_sequence.get_task_tree_props()
    ws_props = props_sequence.get_work_schedule_props()
    ws = tool.Ifc.get().by_id(ws_props.active_work_schedule_id)
    if not tprops or not hasattr(tprops, 'tasks') or not ws: return

    fresh_snapshot = {}
    for task in tprops.tasks:
        tid = str(getattr(task, 'ifc_definition_id', 0))
        if not tid or tid == '0': continue
        groups_data = []
        for choice in getattr(task, 'colortype_group_choices', []):
            groups_data.append({
                "group_name": getattr(choice, 'group_name', ''),
                "enabled": getattr(choice, 'enabled', False),
                "selected_value": getattr(choice, 'selected_colortype', ''),
            })
        fresh_snapshot[tid] = {
            "active": getattr(task, 'use_active_colortype_group', False),
            "selected_active_colortype": getattr(task, 'selected_colortype_in_active_group', ''),
            "animation_color_schemes": getattr(task, 'animation_color_schemes', ''),
            "groups": groups_data,
        }
    snap_key = f"_task_colortype_snapshot_json_WS_{ws.id()}"
    context.scene[snap_key] = json.dumps(fresh_snapshot)


def export_schedule_configuration(work_schedule):
    """Gathers all relevant configuration from a work schedule."""
    ifc_file = tool.Ifc.get()
    context = bpy.context

    def get_all_tasks_recursive(tasks):
        all_tasks = []
        for task in tasks:
            all_tasks.append(task)
            nested = ifcopenshell.util.sequence.get_nested_tasks(task)
            if nested: all_tasks.extend(get_all_tasks_recursive(nested))
        return all_tasks

    all_tasks_in_schedule = get_all_tasks_recursive(ifcopenshell.util.sequence.get_root_tasks(work_schedule))
    if not all_tasks_in_schedule: return {}

    specific_key = f"_task_colortype_snapshot_json_WS_{work_schedule.id()}"
    generic_key = "_task_colortype_snapshot_json"
    snapshot_raw = context.scene.get(specific_key) or context.scene.get(generic_key)
    task_ColorType_snapshot = json.loads(snapshot_raw) if snapshot_raw else {}
    task_ColorType_snapshot = _clean_ColorType_snapshot_data(task_ColorType_snapshot)

    ColorType_groups_data = UnifiedColorTypeManager._read_sets_json(bpy.context)
    
    task_configs = []
    for task in all_tasks_in_schedule:
        task_id = getattr(task, "Identification", None)
        if not task_id: continue
        
        inputs = ifcopenshell.util.sequence.get_task_inputs(task, is_deep=False)
        outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
        resources = ifcopenshell.util.sequence.get_task_resources(task, is_deep=False)
        
        snap_data = task_ColorType_snapshot.get(str(task.id()), {})
        choices = []
        for g_data in snap_data.get("groups", []):
            choices.append({
                "group_name": g_data.get("group_name", ""),
                "enabled": g_data.get("enabled", False),
                "selected_ColorType": g_data.get("selected_ColorType") or g_data.get("selected_value") or g_data.get("selected_colortype") or "",
            })
        
        task_configs.append({
            "task_identification": task_id,
            "predefined_type": getattr(task, "PredefinedType", None),
            "inputs": [p.GlobalId for p in inputs if hasattr(p, 'GlobalId')],
            "outputs": [p.GlobalId for p in outputs if hasattr(p, 'GlobalId')],
            "resources": [r.GlobalId for r in resources if hasattr(r, 'GlobalId')],
            "ColorType_assignments": {
                "use_active_ColorType_group": snap_data.get("active", False),
                "selected_ColorType_in_active_group": snap_data.get("selected_active_ColorType", ""),
                "animation_color_schemes": snap_data.get("animation_color_schemes", ""),
                "choices": choices,
            }
        })

    anim_props = props_sequence.get_animation_props()
    return {
        "version": "1.3",
        "schedule_name": work_schedule.Name,
        "ColorType_groups": ColorType_groups_data,
        "ui_settings": {
            "task_ColorType_group_selector": getattr(anim_props, "task_ColorType_group_selector", ""),
            "animation_group_stack": [{"group": g.group, "enabled": g.enabled} for g in anim_props.animation_group_stack]
        },
        "task_configurations": task_configs,
    }


def import_schedule_configuration(data):
    """Applies a saved schedule configuration to the current IFC file."""
    ifc_file = tool.Ifc.get()
    ws_props = props_sequence.get_work_schedule_props()
    work_schedule = tool.Ifc.get().by_id(ws_props.active_work_schedule_id)
    if not work_schedule: return

    if "ColorType_groups" in data:
        UnifiedColorTypeManager._write_sets_json(bpy.context, data["ColorType_groups"])

    if "ui_settings" in data:
        anim_props = props_sequence.get_animation_props()
        anim_props.task_ColorType_group_selector = data["ui_settings"].get("task_ColorType_group_selector", "")
        anim_props.animation_group_stack.clear()
        for item_data in data["ui_settings"].get("animation_group_stack", []):
            item = anim_props.animation_group_stack.add()
            item.group = item_data.get("group", "")
            item.enabled = bool(item_data.get("enabled", False))

    guid_map = {p.GlobalId: p.id() for p in ifc_file.by_type("IfcProduct") if hasattr(p, 'GlobalId')}
    guid_map.update({r.GlobalId: r.id() for r in ifc_file.by_type("IfcResource") if hasattr(r, 'GlobalId')})
    task_id_map = {t.Identification: t for t in ifc_file.by_type("IfcTask") if getattr(t, 'Identification', None)}
    
    assignments_to_restore = {}
    for task_config in data.get("task_configurations", []):
        task_id = task_config.get("task_identification")
        task = task_id_map.get(task_id)
        if not task: continue

        # Update task data and relationships
        ifcopenshell.api.run("sequence.edit_task", ifc_file, task=task, attributes={"PredefinedType": task_config.get("predefined_type")})
        for prod in ifcopenshell.util.sequence.get_task_outputs(task): ifcopenshell.api.run("sequence.unassign_product", ifc_file, relating_product=prod, related_object=task)
        for prod in ifcopenshell.util.sequence.get_task_inputs(task): ifcopenshell.api.run("sequence.unassign_process", ifc_file, relating_process=task, related_object=prod)
        for res in ifcopenshell.util.sequence.get_task_resources(task): ifcopenshell.api.run("sequence.unassign_process", ifc_file, relating_process=task, related_object=res)
        
        input_ids = [guid_map[g] for g in task_config.get("inputs", []) if g in guid_map]
        output_ids = [guid_map[g] for g in task_config.get("outputs", []) if g in guid_map]
        resource_ids = [guid_map[g] for g in task_config.get("resources", []) if g in guid_map]
        
        if input_ids: ifcopenshell.api.run("sequence.assign_process", ifc_file, relating_process=task, products=[ifc_file.by_id(i) for i in input_ids])
        if output_ids:
            for pid in output_ids: ifcopenshell.api.run("sequence.assign_product", ifc_file, relating_product=ifc_file.by_id(pid), related_object=task)
        if resource_ids: ifcopenshell.api.run("sequence.assign_process", ifc_file, relating_process=task, resources=[ifc_file.by_id(i) for i in resource_ids])

        if "ColorType_assignments" in task_config:
            pa = task_config["ColorType_assignments"]
            groups = [{"group_name": c.get("group_name"), "enabled": c.get("enabled"), "selected_value": c.get("selected_ColorType")} for c in pa.get("choices", [])]
            assignments_to_restore[str(task.id())] = {
                "active": pa.get("use_active_ColorType_group"),
                "selected_active_ColorType": pa.get("selected_ColorType_in_active_group"),
                "animation_color_schemes": pa.get("animation_color_schemes", ""),
                "groups": groups
            }
    
    if assignments_to_restore:
        snap_key = f"_task_colortype_snapshot_json_WS_{work_schedule.id()}"
        bpy.context.scene[snap_key] = json.dumps(assignments_to_restore)


def _clean_ColorType_snapshot_data(snapshot_data):
    """Clean ColorType snapshot data by removing invalid enum values."""
    if not isinstance(snapshot_data, dict): return {}
    cleaned_data = {}
    for task_id, task_data in snapshot_data.items():
        if not isinstance(task_data, dict): continue
        cleaned_task_data = {"active": bool(task_data.get("active", False)), "groups": []}
        selected_active = task_data.get("selected_active_ColorType", "")
        problem_values = ["0", 0, None, "", "None", "null"]
        if selected_active and str(selected_active).strip() not in problem_values:
            cleaned_task_data["selected_active_ColorType"] = str(selected_active).strip()
        else:
             cleaned_task_data["selected_active_ColorType"] = ""
        
        for group_data in task_data.get("groups", []):
            if isinstance(group_data, dict) and group_data.get("group_name"):
                selected_value = group_data.get("selected_value", "")
                if selected_value in problem_values:
                    selected_value = ""
                cleaned_task_data["groups"].append({
                    "group_name": str(group_data["group_name"]),
                    "enabled": bool(group_data.get("enabled", False)),
                    "selected_value": str(selected_value).strip() if selected_value else ""
                })
        cleaned_data[task_id] = cleaned_task_data
    return cleaned_data


def _clean_and_update_ColorType_snapshot_for_schedule(work_schedule):
    """Limpia los datos de perfiles corruptos del cronograma dado."""
    snapshot_key = f"_task_colortype_snapshot_json_WS_{work_schedule.id()}"
    snapshot_raw = bpy.context.scene.get(snapshot_key)
    if snapshot_raw:
        try:
            snapshot_data = json.loads(snapshot_raw)
            cleaned_data = _clean_ColorType_snapshot_data(snapshot_data)
            bpy.context.scene[snapshot_key] = json.dumps(cleaned_data)
        except Exception: pass


def copy_3d_configuration(source_schedule):
    """Copy configuration from source schedule to all other schedules with matching task indicators."""
    ifc_file = tool.Ifc.get()
    if not ifc_file: return {"success": False, "error": "No IFC file loaded"}

    _force_complete_task_snapshot(bpy.context, source_schedule)
    _sync_source_animation_color_schemes(bpy.context)
    _force_fresh_snapshot_from_ui(bpy.context)
    snapshot_all_ui_state(bpy.context)
    config_data = export_schedule_configuration(source_schedule)
    restore_all_ui_state(bpy.context) # Restore UI immediately

    if not config_data or not config_data.get("task_configurations"):
        return {"success": False, "error": "No configuration data to copy"}

    all_schedules = [ws for ws in ifc_file.by_type("IfcWorkSchedule") if ws.id() != source_schedule.id()]
    copied_schedules, total_task_matches = 0, 0

    for target_schedule in all_schedules:
        # Switch active schedule to apply changes
        props_sequence.get_work_schedule_props().active_work_schedule_id = target_schedule.id()
        
        import_schedule_configuration(config_data) # Apply config to new active schedule
        
        # Count matches for reporting
        source_ids = {tc['task_identification'] for tc in config_data['task_configurations']}
        target_ids = {t.Identification for t in ifc_file.by_type("IfcTask") if getattr(t, 'Identification', None) and ifcopenshell.util.sequence.get_task_work_schedule(t) == target_schedule}
        matches = len(source_ids.intersection(target_ids))
        if matches > 0:
            copied_schedules += 1
            total_task_matches += matches
            
    # Restore original active schedule
    props_sequence.get_work_schedule_props().active_work_schedule_id = source_schedule.id()
    
    return {"success": True, "copied_schedules": copied_schedules, "task_matches": total_task_matches}


def sync_3d_elements(work_schedule, property_set_name):
    """Sync IFC elements to tasks based on property set values matching task indicators."""
    ifc_file = tool.Ifc.get()
    if not ifc_file: return {"success": False, "error": "No IFC file loaded"}

    def get_all_tasks_recursive(tasks):
        all_tasks = []
        for task in tasks:
            all_tasks.append(task)
            nested = ifcopenshell.util.sequence.get_nested_tasks(task)
            if nested: all_tasks.extend(get_all_tasks_recursive(nested))
        return all_tasks
    
    all_tasks = get_all_tasks_recursive(ifcopenshell.util.sequence.get_root_tasks(work_schedule))
    task_indicators = {t.Identification: t for t in all_tasks if getattr(t, "Identification", None)}
    if not task_indicators: return {"success": False, "error": "No task identifications found"}

    matched_elements, processed_tasks = 0, 0
    for element in ifc_file.by_type("IfcProduct"):
        if not hasattr(element, 'GlobalId'): continue
        psets = ifcopenshell.util.element.get_psets(element)
        if property_set_name in psets:
            for prop_name, prop_value in psets[property_set_name].items():
                matching_task = task_indicators.get(str(prop_value))
                if matching_task:
                    ifcopenshell.api.run("sequence.assign_product", ifc_file, relating_product=element, related_object=matching_task)
                    matched_elements += 1
                    break

    for task in task_indicators.values():
        if ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False):
            processed_tasks += 1

    _clean_and_update_ColorType_snapshot_for_schedule(work_schedule)
    return {"success": True, "matched_elements": matched_elements, "processed_tasks": processed_tasks}

def export_schedule_configuration(work_schedule):
    """Export schedule configuration to a data structure"""
    import json
    
    if not work_schedule:
        return {}
    
    config = {
        'schedule_id': work_schedule.id(),
        'schedule_name': work_schedule.Name or '',
        'description': getattr(work_schedule, 'Description', '') or '',
        'creation_date': getattr(work_schedule, 'CreationDate', '') or '',
        'tasks': [],
        'color_schemes': {},
        'animation_settings': {}
    }
    
    # Get all tasks from schedule
    if hasattr(work_schedule, 'Controls') and work_schedule.Controls:
        for rel in work_schedule.Controls:
            for task in rel.RelatedObjects:
                if task.is_a('IfcTask'):
                    task_data = {
                        'id': task.id(),
                        'name': task.Name or '',
                        'identification': getattr(task, 'Identification', '') or '',
                        'description': getattr(task, 'Description', '') or ''
                    }
                    
                    # Add task time if available
                    task_time = getattr(task, 'TaskTime', None)
                    if task_time:
                        task_data['schedule_start'] = getattr(task_time, 'ScheduleStart', '')
                        task_data['schedule_finish'] = getattr(task_time, 'ScheduleFinish', '')
                        task_data['schedule_duration'] = getattr(task_time, 'ScheduleDuration', '')
                    
                    config['tasks'].append(task_data)
    
    # Get color schemes
    import bpy
    scene = bpy.context.scene
    color_schemes_raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
    try:
        config['color_schemes'] = json.loads(color_schemes_raw) if isinstance(color_schemes_raw, str) else color_schemes_raw
    except:
        config['color_schemes'] = {}
    
    return config

def import_schedule_configuration(data):
    """Import schedule configuration from data structure"""
    import bpy
    import json
    
    if not data or not isinstance(data, dict):
        return False
    
    # Import color schemes
    if 'color_schemes' in data:
        scene = bpy.context.scene
        scene["BIM_AnimationColorSchemesSets"] = json.dumps(data['color_schemes'])
    
    # Import animation settings if available
    if 'animation_settings' in data:
        from . import props_sequence
        anim_props = props_sequence.get_animation_props()
        
        # Update animation properties with imported settings
        for key, value in data['animation_settings'].items():
            if hasattr(anim_props, key):
                setattr(anim_props, key, value)
    
    return True

def clear_objects_animation(obj_names_list, animation_start_frame, animation_end_frame):
    """Clear animation from specified objects"""
    import bpy
    
    if not obj_names_list:
        return
    
    for obj_name in obj_names_list:
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue
        
        # Clear keyframes in the specified frame range
        if obj.animation_data and obj.animation_data.action:
            for fcurve in obj.animation_data.action.fcurves:
                keyframes_to_remove = []
                for keyframe in fcurve.keyframe_points:
                    if animation_start_frame <= keyframe.co[0] <= animation_end_frame:
                        keyframes_to_remove.append(keyframe)
                
                for keyframe in keyframes_to_remove:
                    fcurve.keyframe_points.remove(keyframe)

def generate_gantt_browser_chart(work_schedule, output_file="gantt_chart.html"):
    """Generate a Gantt chart for browser viewing"""
    if not work_schedule:
        return None
    
    # This would generate an HTML file with Gantt chart
    # For now, return the basic structure
    return {
        'schedule_name': work_schedule.Name or 'Unnamed Schedule',
        'schedule_id': work_schedule.id(),
        'chart_type': 'gantt',
        'output_file': output_file
    }
















