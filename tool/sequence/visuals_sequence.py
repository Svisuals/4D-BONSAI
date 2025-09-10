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
import mathutils
import ifcopenshell
import ifcopenshell.util.date
import bonsai.tool as tool
from . import props_sequence

# Global variable to hold the handler reference
_frame_change_handler = None


def add_text_animation_handler(settings):
    """Creates multiple animated text objects to display schedule information"""
    from datetime import timedelta

    collection_name = "Schedule_Display_Texts"
    if collection_name in bpy.data.collections:
        collection = bpy.data.collections[collection_name]
        for obj in list(collection.objects):
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                pass
    else:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    text_configs = [
        {"name": "Schedule_Date", "position": (0, 10, 5), "size": 1.2, "align": "CENTER", "color": (1, 1, 1, 1), "type": "date"},
        {"name": "Schedule_Week", "position": (0, 10, 4), "size": 1.0, "align": "CENTER", "color": (0.8, 0.8, 1, 1), "type": "week"},
        {"name": "Schedule_Day_Counter", "position": (0, 10, 3), "size": 0.8, "align": "CENTER", "color": (1, 1, 0.8, 1), "type": "day_counter"},
        {"name": "Schedule_Progress", "position": (0, 10, 2), "size": 1.0, "align": "CENTER", "color": (0.8, 1, 0.8, 1), "type": "progress"},
    ]
    created_texts = [_create_animated_text(config, settings, collection) for config in text_configs]

    try:
        if bpy.context.scene.camera and "4D_Animation_Camera" in bpy.context.scene.camera.name:
            camera_props = props_sequence.get_animation_props().camera_orbit
            if not getattr(camera_props, "enable_text_hud", False):
                camera_props.enable_text_hud = True
                def setup_hud_deferred():
                    try: bpy.ops.bim.setup_text_hud()
                    except Exception as e: print(f"Deferred HUD setup failed: {e}")
                bpy.app.timers.register(setup_hud_deferred, first_interval=0.3)
            else:
                def update_hud_deferred():
                    try: bpy.ops.bim.update_text_hud_positions()
                    except Exception as e: print(f"HUD position update failed: {e}")
                bpy.app.timers.register(update_hud_deferred, first_interval=0.1)
    except Exception as e:
        print(f"Error in auto-HUD setup: {e}")
    
    _register_multi_text_handler(settings)

    try:
        if settings and settings.get("start") and settings.get("finish"):
            bpy.ops.bim.enable_schedule_hud()
    except Exception as e:
        print(f"⚠️ Auto-setup of GPU HUD failed: {e}")
    
    return created_texts


def _create_animated_text(config, settings, collection):
    from datetime import datetime as _dt
    text_curve = bpy.data.curves.new(name=config["name"], type='FONT')
    text_curve.size = config["size"]
    text_curve.align_x = config["align"]
    text_curve.align_y = 'CENTER'
    text_curve["text_type"] = config["type"]
    try:
        start = settings.get("start")
        finish = settings.get("finish")
        start_frame = int(settings.get("start_frame", 1))
        total_frames = int(settings.get("total_frames", 250))
        start_iso = start.isoformat() if hasattr(start, "isoformat") else str(start)
        finish_iso = finish.isoformat() if hasattr(finish, "isoformat") else str(finish)
        text_curve["animation_settings"] = {
            "start_frame": start_frame,
            "total_frames": total_frames,
            "start_date": start_iso,
            "finish_date": finish_iso,
        }
    except Exception:
        pass

    text_obj = bpy.data.objects.new(name=config["name"], object_data=text_curve)
    collection.objects.link(text_obj)
    text_obj.location = config["position"]
    _setup_text_material_colored(text_obj, config["color"], config["name"])
    _animate_text_by_type(text_obj, config["type"], settings)
    return text_obj


def _setup_text_material_colored(text_obj, color, mat_name_suffix):
    mat_name = f"Schedule_Text_Mat_{mat_name_suffix}"
    mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = tuple(list(color[:3]) + [1.0])
        bsdf.inputs["Emission"].default_value = tuple(list(color[:3]) + [1.0])
        bsdf.inputs["Emission Strength"].default_value = 1.5
    if text_obj.data.materials: text_obj.data.materials[0] = mat
    else: text_obj.data.materials.append(mat)


def _animate_text_by_type(text_obj, text_type, settings):
    from datetime import timedelta, datetime as _dt
    from dateutil import parser as _parser

    start_date = settings.get("start")
    finish_date = settings.get("finish")
    start_frame = int(settings.get("start_frame", 1))
    total_frames = int(settings.get("total_frames", 250))

    if isinstance(start_date, str): start_date = _dt.fromisoformat(start_date.replace(' ', 'T')[:19]) if '-' in start_date else _parser.parse(start_date, yearfirst=True)
    if isinstance(finish_date, str): finish_date = _dt.fromisoformat(finish_date.replace(' ', 'T')[:19]) if '-' in finish_date else _parser.parse(finish_date, yearfirst=True)
    
    duration = finish_date - start_date
    step_days = 7 if duration.days > 365 else (3 if duration.days > 90 else 1)
    current_date = start_date
    while current_date <= finish_date:
        progress = (current_date - start_date).total_seconds() / duration.total_seconds() if duration.total_seconds() > 0 else 0.0
        frame = start_frame + (progress * total_frames)
        content_map = {
            "date": _format_date(current_date),
            "week": _format_week(current_date, start_date),
            "day_counter": _format_day_counter(current_date, start_date, finish_date),
            "progress": _format_progress(current_date, start_date, finish_date),
        }
        text_obj.data.body = content_map.get(text_type, "")
        try:
            text_obj.data.keyframe_insert(data_path="body", frame=int(frame))
        except Exception: pass
        current_date += timedelta(days=step_days)
        if current_date > finish_date and current_date - timedelta(days=step_days) < finish_date:
            current_date = finish_date


def _format_date(current_date):
    return current_date.strftime("%d/%m/%Y")


def _format_week(current_date, start_date):
    from .animation_sequence import get_schedule_date_range
    try:
        sch_start, _ = get_schedule_date_range()
        if sch_start:
            delta_days = (current_date.date() - sch_start.date()).days
            return f"Week {max(1, (delta_days // 7) + 1) if delta_days >= 0 else 0}"
    except Exception: pass
    return f"Week {(current_date - start_date).days // 7 + 1}"


def _format_day_counter(current_date, start_date, finish_date):
    from .animation_sequence import get_schedule_date_range
    try:
        sch_start, _ = get_schedule_date_range()
        if sch_start:
            delta_days = (current_date.date() - sch_start.date()).days
            return f"Day {max(1, delta_days + 1) if delta_days >= 0 else 0}"
    except Exception: pass
    return f"Day {(current_date - start_date).days + 1}"


def _format_progress(current_date, start_date, finish_date):
    from .animation_sequence import get_schedule_date_range
    try:
        sch_start, sch_finish = get_schedule_date_range()
        if sch_start and sch_finish:
            cd_d, fss_d, fse_d = current_date.date(), sch_start.date(), sch_finish.date()
            if cd_d < fss_d: progress_pct = 0
            elif cd_d >= fse_d: progress_pct = 100
            else:
                total_days = (fse_d - fss_d).days
                progress_pct = round(((cd_d - fss_d).days / total_days) * 100) if total_days > 0 else 100
            return f"Progress: {max(0, min(100, progress_pct))}%"
    except Exception: pass
    total = (finish_date - start_date).days
    progress = ((current_date - start_date).days / total) * 100.0 if total > 0 else 100.0
    return f"Progress: {progress:.0f}%"


def _register_multi_text_handler(settings):
    global _frame_change_handler
    from datetime import datetime as _dt
    _unregister_frame_change_handler()

    def update_all_schedule_texts(scene):
        coll = bpy.data.collections.get("Schedule_Display_Texts")
        if not coll: return
        current_frame = int(scene.frame_current)
        for text_obj in list(coll.objects):
            anim_settings = text_obj.data.get("animation_settings")
            if not anim_settings: continue
            start_frame = int(anim_settings.get("start_frame", 1))
            total_frames = int(anim_settings.get("total_frames", 1))
            progress = (current_frame - start_frame) / float(total_frames or 1)
            progress = max(0.0, min(1.0, progress))
            try:
                start_date = _dt.fromisoformat(anim_settings.get("start_date"))
                finish_date = _dt.fromisoformat(anim_settings.get("finish_date"))
            except Exception: continue
            current_date = start_date + ((finish_date - start_date) * progress)
            ttype = text_obj.data.get("text_type", "date")
            content_map = {
                "date": _format_date(current_date),
                "week": _format_week(current_date, start_date),
                "day_counter": _format_day_counter(current_date, start_date, finish_date),
                "progress": _format_progress(current_date, start_date, finish_date),
            }
            text_obj.data.body = content_map.get(ttype, "")

    bpy.app.handlers.frame_change_post.append(update_all_schedule_texts)
    _frame_change_handler = update_all_schedule_texts


def _unregister_frame_change_handler():
    global _frame_change_handler
    if _frame_change_handler and _frame_change_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_frame_change_handler)
    _frame_change_handler = None


def get_task_bar_list() -> list[int]:
    """Obtiene la lista de IDs de tareas que deben mostrar barra visual."""
    props = props_sequence.get_work_schedule_props()
    try:
        task_bars = json.loads(props.task_bars)
        return task_bars if isinstance(task_bars, list) else []
    except Exception:
        return []


def add_task_bar(task_id: int) -> None:
    """Agrega una tarea a la lista de barras visuales."""
    props = props_sequence.get_work_schedule_props()
    task_bars = get_task_bar_list()
    if task_id not in task_bars:
        task_bars.append(task_id)
        props.task_bars = json.dumps(task_bars)


def remove_task_bar(task_id: int) -> None:
    """Remueve una tarea de la lista de barras visuales."""
    props = props_sequence.get_work_schedule_props()
    task_bars = get_task_bar_list()
    if task_id in task_bars:
        task_bars.remove(task_id)
        props.task_bars = json.dumps(task_bars)


def get_animation_bar_tasks() -> list:
    """Obtiene las tareas IFC que tienen barras visuales habilitadas."""
    task_ids = get_task_bar_list()
    tasks = []
    ifc_file = tool.Ifc.get()
    if ifc_file:
        for task_id in task_ids:
            try:
                task = ifc_file.by_id(task_id)
                if task and utils_sequence.validate_task_object(task, "get_animation_bar_tasks"):
                    tasks.append(task)
            except Exception as e:
                print(f"⚠️ Error getting task {task_id}: {e}")
    return tasks


def refresh_task_bars() -> None:
    """Actualiza la visualización de las barras de tareas en el viewport."""
    tasks = get_animation_bar_tasks()
    if not tasks:
        if "Bar Visual" in bpy.data.collections:
            collection = bpy.data.collections["Bar Visual"]
            for obj in list(collection.objects):
                bpy.data.objects.remove(obj)
        return
    create_bars(tasks)


def clear_task_bars() -> None:
    """Limpia y elimina todas las barras de tareas 3D y resetea el estado en la UI."""
    props = props_sequence.get_work_schedule_props()
    props.task_bars = "[]"
    tprops = props_sequence.get_task_tree_props()
    for task in getattr(tprops, "tasks", []):
        if getattr(task, "has_bar_visual", False):
            task.has_bar_visual = False
    collection = bpy.data.collections.get("Bar Visual")
    if collection:
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)


def create_bars(tasks):
    from .animation_sequence import get_schedule_date_range
    full_bar_thickness, size, vertical_spacing = 0.2, 1.0, 3.5
    vertical_increment, size_to_duration_ratio, margin = 0, 1 / 30, 0.2

    if not tasks: return
    valid_tasks = [t for t in tasks if utils_sequence.validate_task_object(t, "create_bars")]
    if not valid_tasks: return

    def process_task_data(task, settings):
        if not utils_sequence.validate_task_object(task, "process_task_data"): return None
        try:
            task_start_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
            finish_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
        except Exception: return None
        if not (task_start_date and finish_date): return None
        try:
            schedule_start, schedule_finish = settings["viz_start"], settings["viz_finish"]
            schedule_duration = schedule_finish - schedule_start
            if schedule_duration.total_seconds() <= 0: return None
            total_frames = settings["end_frame"] - settings["start_frame"]
            task_start_progress = (task_start_date - schedule_start).total_seconds() / schedule_duration.total_seconds()
            task_finish_progress = (finish_date - schedule_start).total_seconds() / schedule_duration.total_seconds()
            task_start_frame = max(settings["start_frame"], min(settings["end_frame"], round(settings["start_frame"] + (task_start_progress * total_frames))))
            task_finish_frame = max(settings["start_frame"], min(settings["end_frame"], round(settings["start_frame"] + (task_finish_progress * total_frames))))
            return {"name": getattr(task, "Name", "Unnamed"), "start_date": task_start_date, "finish_date": finish_date, "start_frame": task_start_frame, "finish_frame": task_finish_frame}
        except Exception: return None

    def create_task_bar_data(tasks, vertical_increment, collection):
        schedule_start, schedule_finish = get_schedule_date_range()
        if not (schedule_start and schedule_finish): return None
        settings = {"viz_start": schedule_start, "viz_finish": schedule_finish, "start_frame": bpy.context.scene.frame_start, "end_frame": bpy.context.scene.frame_end}
        material_progress, material_full = get_animation_materials()
        empty = bpy.data.objects.new("collection_origin", None)
        link_collection(empty, collection)
        for task in tasks:
            task_data = process_task_data(task, settings)
            if task_data:
                position_shift = task_data["start_frame"] * size_to_duration_ratio
                bar_size = (task_data["finish_frame"] - task_data["start_frame"]) * size_to_duration_ratio
                anim_props = props_sequence.get_animation_props()
                add_bar(material=material_progress, vertical_increment=vertical_increment, collection=collection, parent=empty, task=task_data, scale=True, color=tuple(anim_props.color_progress) + (1.0,), shift_x=position_shift, name=task_data["name"] + "/Progress Bar")
                bar2 = add_bar(material=material_full, vertical_increment=vertical_increment, parent=empty, collection=collection, task=task_data, color=tuple(anim_props.color_full) + (1.0,), shift_x=position_shift, name=task_data["name"] + "/Full Bar")
                bar2.color = tuple(anim_props.color_full) + (1.0,)
                bar2.scale = (full_bar_thickness, bar_size, 1)
                shift_object(bar2, y=((size + full_bar_thickness) / 2))
                start_text = add_text(task_data["start_date"].strftime("%d/%m/%y"), 0, "RIGHT", vertical_increment, parent=empty, collection=collection)
                start_text.name = task_data["name"] + "/Start Date"
                shift_object(start_text, x=position_shift - margin, y=-(size + full_bar_thickness))
                task_text = add_text(task_data["name"], 0, "RIGHT", vertical_increment, parent=empty, collection=collection)
                task_text.name = task_data["name"] + "/Task Name"
                shift_object(task_text, x=position_shift, y=0.2)
                finish_text = add_text(task_data["finish_date"].strftime("%d/%m/%y"), bar_size, "LEFT", vertical_increment, parent=empty, collection=collection)
                finish_text.name = task_data["name"] + "/Finish Date"
                shift_object(finish_text, x=position_shift + margin, y=-(size + full_bar_thickness))
            vertical_increment += vertical_spacing
        return empty.select_set(True) if empty else None

    def set_material(name, r, g, b):
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        tool.Blender.get_material_node(material, "BSDF_PRINCIPLED").inputs[0].default_value = (r, g, b, 1.0)
        return material

    def get_animation_materials():
        material_progress = bpy.data.materials.get("color_progress") or set_material("color_progress", 0.0, 1.0, 0.0)
        material_full = bpy.data.materials.get("color_full") or set_material("color_full", 1.0, 0.0, 0.0)
        return material_progress, material_full

    def animate_scale(bar, task):
        bar.scale = (1, size_to_duration_ratio, 1)
        bar.keyframe_insert(data_path="scale", frame=task["start_frame"])
        bar.scale = (1, (task["finish_frame"] - task["start_frame"]) * size_to_duration_ratio, 1)
        bar.keyframe_insert(data_path="scale", frame=task["finish_frame"])

    def animate_color(bar, task, color):
        bar.keyframe_insert(data_path="color", frame=task["start_frame"])
        bar.color = color
        bar.keyframe_insert(data_path="color", frame=task["start_frame"] + 1)

    def place_bar(bar, vertical_increment):
        for vertex in bar.data.vertices: vertex.co[1] += 0.5
        bar.rotation_euler[2] = -1.5708
        shift_object(bar, y=-vertical_increment)

    def shift_object(obj, x=0.0, y=0.0, z=0.0):
        inv = obj.matrix_world.copy()
        inv.invert()
        obj.location += mathutils.Vector((x, y, z)) @ inv

    def link_collection(obj, collection):
        if collection:
            collection.objects.link(obj)
            if obj.name in bpy.context.scene.collection.objects:
                bpy.context.scene.collection.objects.unlink(obj)
        return obj

    def create_plane(material, collection, vertical_increment):
        vert, fac = [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (-0.5, 0.5, 0.0), (0.5, 0.5, 0.0)], [(0, 1, 3, 2)]
        mesh = bpy.data.meshes.new("PL")
        mesh.from_pydata(vert, [], fac)
        obj = bpy.data.objects.new("PL", mesh)
        obj.data.materials.append(material)
        place_bar(obj, vertical_increment)
        link_collection(obj, collection)
        return obj

    def add_text(text, x_position, align, vertical_increment, parent=None, collection=None):
        data = bpy.data.curves.new(type="FONT", name="Timeline")
        data.align_x, data.align_y, data.body = align, "CENTER", text
        obj = bpy.data.objects.new(name="Unnamed", object_data=data)
        link_collection(obj, collection)
        shift_object(obj, x=x_position, y=-(vertical_increment - 1))
        if parent: obj.parent = parent
        return obj

    def add_bar(material, vertical_increment, parent=None, collection=None, task=None, color=False, scale=False, shift_x=None, name=None):
        plane = create_plane(material, collection, vertical_increment)
        if parent: plane.parent = parent
        if color: animate_color(plane, task, color)
        if scale: animate_scale(plane, task)
        if shift_x: shift_object(plane, x=shift_x)
        if name: plane.name = name
        return plane

    collection = bpy.data.collections.get("Bar Visual")
    if collection:
        for obj in list(collection.objects): bpy.data.objects.remove(obj)
    else:
        collection = bpy.data.collections.new("Bar Visual")
        bpy.context.scene.collection.children.link(collection)

def add_task_bar(task_id: int) -> None:
    """Add a task to the visual timeline bar"""
    props = props_sequence.get_task_tree_props()
    
    # Check if task bar already exists
    for bar in props.task_bars:
        if bar.task_id == task_id:
            return  # Already exists
    
    # Add new task bar
    new_bar = props.task_bars.add()
    new_bar.task_id = task_id
    
    # Refresh the visual representation
    refresh_task_bars()

def remove_task_bar(task_id: int) -> None:
    """Remove a task from the visual timeline bar"""
    props = props_sequence.get_task_tree_props()
    
    # Find and remove the task bar
    for i, bar in enumerate(props.task_bars):
        if bar.task_id == task_id:
            props.task_bars.remove(i)
            break
    
    # Refresh the visual representation
    refresh_task_bars()

def refresh_task_bars() -> None:
    """Refresh the visual representation of task bars"""
    props = props_sequence.get_task_tree_props()
    
    # Get current task bar list
    task_ids = [bar.task_id for bar in props.task_bars]
    
    if not task_ids:
        clear_task_bars()
        return
    
    # Get tasks from IDs
    import bonsai.tool as tool
    ifc = tool.Ifc.get()
    tasks = []
    
    for task_id in task_ids:
        task = ifc.by_id(task_id)
        if task:
            tasks.append(task)
    
    # Recreate bars with current tasks
    if tasks:
        create_bars(tasks)

def clear_task_bars() -> None:
    """Clear all task bars from the visual timeline"""
    # Clear task bars collection
    collection = bpy.data.collections.get("Bar Visual")
    if collection:
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    
    # Clear properties
    props = props_sequence.get_task_tree_props()
    props.task_bars.clear()

def is_bonsai_camera(obj) -> bool:
    """Check if object is a Bonsai camera (animation or snapshot)"""
    if not obj or obj.type != 'CAMERA':
        return False
    
    # Check for animation camera markers
    if obj.get('is_4d_camera') or obj.get('is_animation_camera'):
        return True
    
    # Check for snapshot camera markers
    if obj.get('is_snapshot_camera'):
        return True
    
    # Check by name patterns
    if any(pattern in obj.name for pattern in ['4D_Animation_Camera', 'Snapshot_Camera']):
        return True
    
    return False

def is_bonsai_animation_camera(obj) -> bool:
    """Check if object is specifically a Bonsai animation camera"""
    if not obj or obj.type != 'CAMERA':
        return False
    
    if obj.get('camera_context') == 'animation':
        return True
    
    if obj.get('is_4d_camera') or obj.get('is_animation_camera'):
        return True
    
    if '4D_Animation_Camera' in obj.name and 'Snapshot' not in obj.name:
        return True
    
    return False

def is_bonsai_snapshot_camera(obj) -> bool:
    """Check if object is specifically a Bonsai snapshot camera"""
    if not obj or obj.type != 'CAMERA':
        return False
    
    if obj.get('camera_context') == 'snapshot':
        return True
    
    if obj.get('is_snapshot_camera'):
        return True
    
    if 'Snapshot_Camera' in obj.name:
        return True
    
    return False

def create_bars(tasks):
    """Create visual task bars for the timeline"""
    import bpy
    import mathutils
    from datetime import datetime
    import ifcopenshell.util.sequence
    import ifcopenshell.util.date
    from . import props_sequence
    from . import utils_sequence
    
    full_bar_thickness = 0.2
    size = 1.0
    vertical_spacing = 3.5
    vertical_increment = 0
    size_to_duration_ratio = 1 / 30
    margin = 0.2

    # Validation: Filter invalid tasks before any use
    if tasks:
        valid_tasks = []
        for task in tasks:
            if validate_task_object(task, "create_bars"):
                valid_tasks.append(task)
            else:
                print(f"⚠️ Skipping invalid task in create_bars: {task}")
        if not valid_tasks:
            print("⚠️ Warning: No valid tasks found for bar creation")
            return
        tasks = valid_tasks
    else:
        print("⚠️ Warning: No tasks provided to create_bars")
        return

    def process_task_data(task, settings):
        """Process individual task data for bar creation"""
        if not validate_task_object(task, "process_task_data"):
            return None

        try:
            task_start_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
            finish_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
        except Exception as e:
            print(f"⚠️ Error deriving dates for task {getattr(task, 'Name', 'Unknown')}: {e}")
            return None

        if not (task_start_date and finish_date):
            print(f"⚠️ Warning: Task {getattr(task, 'Name', 'Unknown')} has no valid dates")
            return None

        try:
            # Use the schedule dates for calculations
            schedule_start = settings["viz_start"]
            schedule_finish = settings["viz_finish"]
            schedule_duration = schedule_finish - schedule_start

            if schedule_duration.total_seconds() <= 0:
                print(f"⚠️ Invalid schedule duration: {schedule_duration}")
                return None

            total_frames = settings["end_frame"] - settings["start_frame"]

            # Calculate task position within the full schedule
            task_start_progress = (task_start_date - schedule_start).total_seconds() / schedule_duration.total_seconds()
            task_finish_progress = (finish_date - schedule_start).total_seconds() / schedule_duration.total_seconds()

            # Convert to frames
            task_start_frame = round(settings["start_frame"] + (task_start_progress * total_frames))
            task_finish_frame = round(settings["start_frame"] + (task_finish_progress * total_frames))

            # Validate that frames are in valid range
            task_start_frame = max(settings["start_frame"], min(settings["end_frame"], task_start_frame))
            task_finish_frame = max(settings["start_frame"], min(settings["end_frame"], task_finish_frame))

            return {
                "name": getattr(task, "Name", "Unnamed"),
                "start_date": task_start_date,
                "finish_date": finish_date,
                "start_frame": task_start_frame,
                "finish_frame": task_finish_frame,
            }
        except Exception as e:
            print(f"⚠️ Error calculating frames for task {getattr(task, 'Name', 'Unknown')}: {e}")
            return None

    def create_task_bar_data(tasks, vertical_increment, collection):
        """Create the actual bar data and objects"""
        # Use active schedule dates
        from . import utils_sequence
        schedule_start, schedule_finish = utils_sequence.get_schedule_date_range()

        if not (schedule_start and schedule_finish):
            print("❌ Cannot create Task Bars: schedule dates not available")
            return None

        settings = {
            "viz_start": schedule_start,
            "viz_finish": schedule_finish,
            "start_frame": bpy.context.scene.frame_start,
            "end_frame": bpy.context.scene.frame_end,
        }

        print(f"🎯 Task Bars using schedule dates:")
        print(f"   Schedule Start: {schedule_start.strftime('%Y-%m-%d')}")
        print(f"   Schedule Finish: {schedule_finish.strftime('%Y-%m-%d')}")
        print(f"   Timeline: frames {settings['start_frame']} to {settings['end_frame']}")

        material_progress, material_full = get_animation_materials()
        empty = bpy.data.objects.new("collection_origin", None)
        link_collection(empty, collection)

        for task in tasks:
            task_data = process_task_data(task, settings)
            if task_data:
                position_shift = task_data["start_frame"] * size_to_duration_ratio
                bar_size = (task_data["finish_frame"] - task_data["start_frame"]) * size_to_duration_ratio

                anim_props = props_sequence.get_animation_props()
                color_progress = anim_props.color_progress
                bar = add_bar(
                    material=material_progress,
                    vertical_increment=vertical_increment,
                    collection=collection,
                    parent=empty,
                    task=task_data,
                    scale=True,
                    color=(color_progress[0], color_progress[1], color_progress[2], 1.0),
                    shift_x=position_shift,
                    name=task_data["name"] + "/Progress Bar",
                )

                color_full = anim_props.color_full
                bar2 = add_bar(
                    material=material_full,
                    vertical_increment=vertical_increment,
                    parent=empty,
                    collection=collection,
                    task=task_data,
                    color=(color_full[0], color_full[1], color_full[2], 1.0),
                    shift_x=position_shift,
                    name=task_data["name"] + "/Full Bar",
                )
                bar2.color = (color_full[0], color_full[1], color_full[2], 1.0)

                bar2.scale = (full_bar_thickness, bar_size, 1)
                shift_object(bar2, y=((size + full_bar_thickness) / 2))

                start_text = add_text(
                    task_data["start_date"].strftime("%d/%m/%y"),
                    0,
                    "RIGHT",
                    vertical_increment,
                    parent=empty,
                    collection=collection,
                )
                start_text.name = task_data["name"] + "/Start Date"
                shift_object(start_text, x=position_shift - margin, y=-(size + full_bar_thickness))

                task_text = add_text(
                    task_data["name"],
                    0,
                    "RIGHT",
                    vertical_increment,
                    parent=empty,
                    collection=collection,
                )
                task_text.name = task_data["name"] + "/Task Name"
                shift_object(task_text, x=position_shift, y=0.2)

                finish_text = add_text(
                    task_data["finish_date"].strftime("%d/%m/%y"),
                    bar_size,
                    "LEFT",
                    vertical_increment,
                    parent=empty,
                    collection=collection,
                )
                finish_text.name = task_data["name"] + "/Finish Date"
                shift_object(finish_text, x=position_shift + margin, y=-(size + full_bar_thickness))

            vertical_increment += vertical_spacing

        return empty.select_set(True) if empty else None

    # Get or create collection
    collection = bpy.data.collections.get("Bar Visual")
    if not collection:
        collection = bpy.data.collections.new("Bar Visual")
        bpy.context.scene.collection.children.link(collection)

    # Create bars
    create_task_bar_data(tasks, vertical_increment, collection)

def validate_task_object(task, context="general"):
    """Validate that a task object is valid for processing"""
    if not task:
        return False
    
    if not hasattr(task, 'is_a'):
        return False
        
    try:
        if not task.is_a('IfcTask'):
            return False
    except:
        return False
        
    return True

def get_animation_materials():
    """Get or create animation materials"""
    import bpy
    import bonsai.tool as tool
    
    if "color_progress" in bpy.data.materials:
        material_progress = bpy.data.materials["color_progress"]
    else:
        material_progress = set_material("color_progress", 0.0, 1.0, 0.0)
    if "color_full" in bpy.data.materials:
        material_full = bpy.data.materials["color_full"]
    else:
        material_full = set_material("color_full", 1.0, 0.0, 0.0)
    return material_progress, material_full

def set_material(name, r, g, b):
    """Create a new material with specified color"""
    import bpy
    import bonsai.tool as tool
    
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tool.Blender.get_material_node(material, "BSDF_PRINCIPLED").inputs[0].default_value = (r, g, b, 1.0)
    return material

def add_bar(material, vertical_increment, collection, parent, task, scale=False, color=(1,1,1,1), shift_x=0, name="Bar"):
    """Add a bar object to the scene"""
    import bpy
    
    bar = create_plane(material, collection, vertical_increment)
    bar.name = name
    bar.parent = parent
    bar.color = color
    
    if scale:
        animate_scale(bar, task)
    else:
        animate_color(bar, task, color)
        
    place_bar(bar, vertical_increment)
    shift_object(bar, x=shift_x)
    
    return bar

def add_text(text, bar_size, align, vertical_increment, parent, collection):
    """Add text object to the scene"""
    import bpy
    
    text_data = bpy.data.curves.new(name="Text", type='FONT')
    text_data.body = text
    text_data.align_x = align
    text_obj = bpy.data.objects.new("Text", text_data)
    text_obj.parent = parent
    link_collection(text_obj, collection)
    
    return text_obj

def animate_scale(bar, task):
    """Animate the scale of a bar based on task timing"""
    size_to_duration_ratio = 1 / 30
    
    scale = (1, size_to_duration_ratio, 1)
    bar.scale = scale
    bar.keyframe_insert(data_path="scale", frame=task["start_frame"])
    
    scale2 = (1, (task["finish_frame"] - task["start_frame"]) * size_to_duration_ratio, 1)
    bar.scale = scale2
    bar.keyframe_insert(data_path="scale", frame=task["finish_frame"])

def animate_color(bar, task, color):
    """Animate the color of a bar based on task timing"""
    bar.keyframe_insert(data_path="color", frame=task["start_frame"])
    bar.color = color
    bar.keyframe_insert(data_path="color", frame=task["start_frame"] + 1)
    bar.color = color

def create_plane(material, collection, vertical_increment):
    """Create a plane mesh for bar visualization"""
    import bpy
    
    x = 0.5
    y = 0.5
    vert = [(-x, -y, 0.0), (x, -y, 0.0), (-x, y, 0.0), (x, y, 0.0)]
    faces = [(0, 1, 3, 2)]
    mesh = bpy.data.meshes.new("PL")
    mesh.from_pydata(vert, [], faces)
    obj = bpy.data.objects.new("PL", mesh)
    
    if material:
        obj.data.materials.append(material)
    
    link_collection(obj, collection)
    return obj

def place_bar(bar, vertical_increment):
    """Position a bar in the correct location"""
    import mathutils
    
    for vertex in bar.data.vertices:
        vertex.co[1] += 0.5
    bar.rotation_euler[2] = -1.5708
    shift_object(bar, y=-vertical_increment)

def shift_object(obj, x=0.0, y=0.0, z=0.0):
    """Shift an object by specified coordinates"""
    import mathutils
    
    vec = mathutils.Vector((x, y, z))
    inv = obj.matrix_world.copy()
    inv.invert()
    vec_rot = vec @ inv
    obj.location = obj.location + vec_rot

def link_collection(obj, collection):
    """Link object to a specific collection"""
    import bpy
    
    if collection:
        collection.objects.link(obj)
        if obj.name in bpy.context.scene.collection.objects.keys():
            bpy.context.scene.collection.objects.unlink(obj)
    return obj
    
    create_task_bar_data(valid_tasks, vertical_increment, collection)