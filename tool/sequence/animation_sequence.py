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
import ifcopenshell
import ifcopenshell.util.date
import ifcopenshell.util.sequence
from datetime import datetime, timedelta
from dateutil import parser
import bonsai.tool as tool
from bonsai.bim.module.sequence import data as _seq_data
from . import props_sequence
from . import utils_sequence
from . import colortype_sequence
from . import visuals_sequence
from . import task_sequence

# Referencias globales para handlers
_live_color_update_handler = None
_live_update_timer = None
_last_frame = -1


def get_start_date():
    """Devuelve la fecha de inicio configurada (visualisation_start) o None.
    Parseo robusto: ISO-8601 primero (YYYY-MM-DD), luego dateutil con yearfirst=True.
    """
    props = props_sequence.get_work_schedule_props()
    s = getattr(props, "visualisation_start", None)
    if not s or s == "-":
        return None
    try:
        from datetime import datetime as _dt
        if isinstance(s, str):
            try:
                if "T" in s or " " in s:
                    s2 = s.replace(" ", "T")
                    dt = _dt.fromisoformat(s2[:19])
                else:
                    dt = _dt.fromisoformat(s[:10])
                return dt.replace(microsecond=0)
            except Exception:
                pass
        if isinstance(s, (_dt, )):
            return s.replace(microsecond=0)
    except Exception:
        pass
    try:
        from dateutil import parser
        return parser.parse(s, yearfirst=True).replace(microsecond=0)
    except Exception:
        return None


def get_finish_date():
    """Devuelve la fecha de fin configurada (visualisation_finish) o None.
    Parseo robusto: ISO-8601 primero, luego dateutil con yearfirst=True.
    """
    props = props_sequence.get_work_schedule_props()
    s = getattr(props, "visualisation_finish", None)
    if not s or s == "-":
        return None
    try:
        from datetime import datetime as _dt
        if isinstance(s, str):
            try:
                if "T" in s or " " in s:
                    s2 = s.replace(" ", "T")
                    dt = _dt.fromisoformat(s2[:19])
                else:
                    dt = _dt.fromisoformat(s[:10])
                return dt.replace(microsecond=0)
            except Exception:
                pass
        if isinstance(s, (_dt, )):
            return s.replace(microsecond=0)
    except Exception:
        pass
    try:
        from dateutil import parser
        return parser.parse(s, yearfirst=True).replace(microsecond=0)
    except Exception:
        return None


def clear_objects_animation(include_blender_objects: bool = True, *, clear_texts: bool = True, clear_bars: bool = True, reset_timeline: bool = True, reset_colors_and_visibility: bool = True):
    """Cleans the 4D animation selectively and robustly."""
    visuals_sequence._unregister_frame_change_handler()

    if clear_texts:
        coll = bpy.data.collections.get("Schedule_Display_Texts")
        if coll:
            for obj in list(coll.objects): bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(coll)
    if clear_bars:
        visuals_sequence.clear_task_bars()

    if include_blender_objects:
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                if obj.animation_data: obj.animation_data_clear()
                if reset_colors_and_visibility:
                    obj.hide_viewport = False
                    obj.hide_render = False
                    obj.color = (0.8, 0.8, 0.8, 1.0)
    if reset_timeline:
        bpy.context.scene.frame_current = bpy.context.scene.frame_start


def get_start_date() -> datetime | None:
    """Devuelve la fecha de inicio configurada (visualisation_start) o None."""
    s = getattr(props_sequence.get_work_schedule_props(), "visualisation_start", None)
    if not s or s == "-": return None
    try:
        return parser.parse(str(s), yearfirst=True, dayfirst=False, fuzzy=True).replace(microsecond=0)
    except Exception:
        try:
            return parser.parse(str(s), yearfirst=True, dayfirst=True, fuzzy=True).replace(microsecond=0)
        except Exception:
            return None


def get_finish_date() -> datetime | None:
    """Devuelve la fecha de fin configurada (visualisation_finish) o None."""
    s = getattr(props_sequence.get_work_schedule_props(), "visualisation_finish", None)
    if not s or s == "-": return None
    try:
        return parser.parse(str(s), yearfirst=True, dayfirst=False, fuzzy=True).replace(microsecond=0)
    except Exception:
        try:
            return parser.parse(str(s), yearfirst=True, dayfirst=True, fuzzy=True).replace(microsecond=0)
        except Exception:
            return None


def get_visualization_date_range():
    """Obtiene el rango de fechas de visualización configurado en la UI."""
    return get_start_date(), get_finish_date()


def get_schedule_date_range(work_schedule=None):
    """Obtiene el rango de fechas REAL del cronograma activo."""
    if not work_schedule:
        work_schedule = tool.Ifc.get().by_id(props_sequence.get_work_schedule_props().active_work_schedule_id)
    if not work_schedule: return None, None
    
    # El uso de 'cls' aquí es para llamar a un método de la clase principal, así que lo mantenemos como tool.Sequence
    schedule_start, schedule_finish = tool.Sequence.guess_date_range(work_schedule)
    return schedule_start, schedule_finish


def guess_date_range(work_schedule: ifcopenshell.entity_instance) -> tuple:
    """Guesses the date range for a work schedule."""
    if not work_schedule: return None, None
    def get_all_tasks_from_schedule(schedule):
        all_tasks = []
        def recurse(tasks):
            for task in tasks:
                all_tasks.append(task)
                nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                if nested: recurse(nested)
        recurse(ifcopenshell.util.sequence.get_root_tasks(schedule))
        return all_tasks
    all_schedule_tasks = get_all_tasks_from_schedule(work_schedule)
    if not all_schedule_tasks: return None, None

    date_source = getattr(props_sequence.get_work_schedule_props(), "date_source_type", "SCHEDULE")
    start_attr, finish_attr = f"{date_source.capitalize()}Start", f"{date_source.capitalize()}Finish"
    all_starts, all_finishes = [], []
    for task in all_schedule_tasks:
        start_date = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
        if start_date: all_starts.append(start_date)
        finish_date = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
        if finish_date: all_finishes.append(finish_date)
    
    if not all_starts or not all_finishes: return None, None
    return min(all_starts), max(all_finishes)


def get_animation_settings():
    """Asegura que use las fechas de visualización configuradas."""
    props = props_sequence.get_work_schedule_props()
    start, finish = get_start_date(), get_finish_date()

    if not (start and finish):
        ws = tool.Ifc.get().by_id(props.active_work_schedule_id)
        if ws: start, finish = guess_date_range(ws)
    if not (start and finish): return None
    
    if finish <= start: finish = start + timedelta(days=1)
    
    start_frame = int(getattr(bpy.context.scene, 'frame_start', 1) or 1)
    fps = int(getattr(bpy.context.scene.render, 'fps', 24) or 24)

    def calculate_total_frames(fps):
        if props.speed_types == "FRAME_SPEED":
            return ((finish - start) / ifcopenshell.util.date.parse_duration(props.speed_real_duration)) * props.speed_animation_frames
        elif props.speed_types == "DURATION_SPEED":
            animation_duration = ifcopenshell.util.date.parse_duration(props.speed_animation_duration)
            real_duration = ifcopenshell.util.date.parse_duration(props.speed_real_duration)
            multiplier = real_duration / animation_duration
            return ((finish - start) / multiplier).total_seconds() * fps
        elif props.speed_types == "MULTIPLIER_SPEED":
            return ((finish - start) / props.speed_multiplier).total_seconds() * fps
        return 250
    
    total_frames = int(round(calculate_total_frames(fps)))
    return { "start": start, "finish": finish, "duration": finish - start, "start_frame": start_frame, "total_frames": total_frames }


def process_construction_state(work_schedule, date, viz_start=None, viz_finish=None, date_source="SCHEDULE"):
    """Procesa estados considerando el rango de visualización configurado."""
    states = {"TO_BUILD": set(), "IN_CONSTRUCTION": set(), "COMPLETED": set(), "TO_DEMOLISH": set(), "IN_DEMOLITION": set(), "DEMOLISHED": set()}
    for rel in work_schedule.Controls or []:
        for related_object in rel.RelatedObjects:
            if related_object.is_a("IfcTask"):
                process_task_status(related_object, date, states, viz_start, viz_finish, date_source=date_source)
    return states


def process_task_status(task, date, states, viz_start=None, viz_finish=None, date_source="SCHEDULE"):
    """Procesa el estado de una tarea considerando el rango de visualización."""
    for rel in task.IsNestedBy or []:
        for related_object in rel.RelatedObjects:
            process_task_status(related_object, date, states, viz_start, viz_finish, date_source=date_source)

    start_attr, finish_attr = f"{date_source.capitalize()}Start", f"{date_source.capitalize()}Finish"
    start = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
    finish = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
    if not start or not finish: return

    outputs = task_sequence.get_task_outputs(task) or []
    inputs = task_sequence.get_task_inputs(task) or []
    
    if viz_finish and start > viz_finish: return
    if viz_start and finish < viz_start:
        for output in outputs: states["COMPLETED"].add(tool.Ifc.get_object(output))
        for input_item in inputs: states["DEMOLISHED"].add(tool.Ifc.get_object(input_item))
        return
    
    if date < start:
        for output in outputs: states["TO_BUILD"].add(tool.Ifc.get_object(output))
        for input_item in inputs: states["TO_DEMOLISH"].add(tool.Ifc.get_object(input_item))
    elif date <= finish:
        for output in outputs: states["IN_CONSTRUCTION"].add(tool.Ifc.get_object(output))
        for input_item in inputs: states["IN_DEMOLITION"].add(tool.Ifc.get_object(input_item))
    else:
        for output in outputs: states["COMPLETED"].add(tool.Ifc.get_object(output))
        for input_item in inputs: states["DEMOLISHED"].add(tool.Ifc.get_object(input_item))


def show_snapshot(product_states):
    """Muestra un snapshot visual de todos los objetos IFC en la fecha especificada."""
    for obj in bpy.data.objects:
        if obj.animation_data: obj.animation_data_clear()

    ws_props = props_sequence.get_work_schedule_props()
    snapshot_date_str = getattr(ws_props, "visualisation_start", None)
    if not snapshot_date_str or snapshot_date_str == "-": return
    snapshot_date = utils_sequence.parse_isodate_datetime(snapshot_date_str)
    date_source = getattr(ws_props, "date_source_type", "SCHEDULE")
    
    anim_props = props_sequence.get_animation_props()
    active_group_name = next((item.group for item in anim_props.animation_group_stack if item.enabled and item.group), "DEFAULT")

    for obj in bpy.data.objects:
        element = tool.Ifc.get_entity(obj)
        if not element or not obj.type == 'MESH': continue
        task = utils_sequence.get_task_for_product(element)
        if not task:
            obj.hide_viewport = obj.hide_render = True
            continue

        start_attr, finish_attr = f"{date_source.capitalize()}Start", f"{date_source.capitalize()}Finish"
        task_start = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
        task_finish = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
        if not task_start or not task_finish:
            obj.hide_viewport = obj.hide_render = True
            continue

        state = "start" if snapshot_date < task_start else "in_progress" if task_start <= snapshot_date <= task_finish else "end"
        ColorType = colortype_sequence.get_assigned_ColorType_for_task(task, anim_props, active_group_name)
        is_demolition = (getattr(task, "PredefinedType", "") or "").upper() in {"DEMOLITION", "REMOVAL", "DISPOSAL", "DISMANTLE"}
        
        if is_demolition: obj.hide_viewport = state == "end"
        else: obj.hide_viewport = state == "start"
        
        if not obj.hide_viewport:
            original_color = list(obj.color)
            color_to_apply = original_color
            if state == "start" and not getattr(ColorType, 'use_start_original_color', False): color_to_apply = list(ColorType.start_color)
            elif state == "in_progress" and not getattr(ColorType, 'use_active_original_color', False): color_to_apply = list(ColorType.in_progress_color)
            elif state == "end":
                if getattr(ColorType, 'hide_at_end', False): obj.hide_viewport = True
                elif not getattr(ColorType, 'use_end_original_color', True): color_to_apply = list(ColorType.end_color)
            if not obj.hide_viewport: obj.color = color_to_apply
        obj.hide_render = obj.hide_viewport
    set_object_shading()


def set_object_shading():
    area = tool.Blender.get_view3d_area()
    if area:
        space = area.spaces.active
        if space and space.type == 'VIEW_3D':
            space.shading.color_type = "OBJECT"


def get_animation_product_frames_enhanced(work_schedule, settings):
    animation_start = int(settings["start_frame"])
    animation_end = int(settings["start_frame"] + settings["total_frames"])
    viz_start, viz_finish, viz_duration = settings["start"], settings["finish"], settings["duration"]
    product_frames = {}
    date_source = getattr(props_sequence.get_work_schedule_props(), "date_source_type", "SCHEDULE")
    start_date_type, finish_date_type = f"{date_source.capitalize()}Start", f"{date_source.capitalize()}Finish"

    def add_product_frame(product_id, task, start_date, finish_date, start_frame, finish_frame, relationship):
        s_vis = max(animation_start, int(start_frame))
        f_vis = min(animation_end, int(finish_frame))
        states = {
            "before_start": (animation_start, s_vis - 1),
            "active": (s_vis, f_vis),
            "after_end": (f_vis + 1, animation_end),
        }
        product_frames.setdefault(product_id, []).append({
            "task": task, "task_id": task.id(), "type": getattr(task, "PredefinedType", "NOTDEFINED"),
            "relationship": relationship, "start_date": start_date, "finish_date": finish_date,
            "STARTED": int(start_frame), "COMPLETED": int(finish_frame),
            "start_frame": s_vis, "finish_frame": f_vis, "states": states,
        })

    def preprocess_task(task):
        for subtask in ifcopenshell.util.sequence.get_nested_tasks(task): preprocess_task(subtask)
        task_start = ifcopenshell.util.sequence.derive_date(task, start_date_type, is_earliest=True)
        task_finish = ifcopenshell.util.sequence.derive_date(task, finish_date_type, is_latest=True)
        if not task_start or not task_finish or task_start > viz_finish: return

        progress_start = (task_start - viz_start).total_seconds() / viz_duration.total_seconds() if viz_duration.total_seconds() > 0 else 0.0
        progress_finish = (task_finish - viz_start).total_seconds() / viz_duration.total_seconds() if viz_duration.total_seconds() > 0 else 1.0
        sf = int(round(settings["start_frame"] + (progress_start * settings["total_frames"])))
        ff = int(round(settings["start_frame"] + (progress_finish * settings["total_frames"])))

        for output in task_sequence.get_task_outputs(task): add_product_frame(output.id(), task, task_start, task_finish, sf, ff, "output")
        for input_prod in task_sequence.get_task_inputs(task): add_product_frame(input_prod.id(), task, task_start, task_finish, sf, ff, "input")

    for root_task in ifcopenshell.util.sequence.get_root_tasks(work_schedule):
        preprocess_task(root_task)
    return product_frames


def animate_objects_with_ColorTypes(settings, product_frames):
    animation_props = props_sequence.get_animation_props()
    active_group_name = next((item.group for item in getattr(animation_props, "animation_group_stack", []) if item.enabled and item.group), "DEFAULT")
    original_colors = {obj.name: list(obj.color) for obj in bpy.data.objects if obj.type == 'MESH'}
    
    for obj in bpy.data.objects:
        element = tool.Ifc.get_entity(obj)
        if not element or element.id() not in product_frames:
            if element and element.is_a("IfcSpace"): obj.hide_viewport = True
            continue
        
        obj.hide_viewport = obj.hide_render = True
        obj.keyframe_insert(data_path="hide_viewport", frame=0)
        obj.keyframe_insert(data_path="hide_render", frame=0)

        if animation_props.enable_live_color_updates:
            continue

        original_color = original_colors.get(obj.name, [1.0, 1.0, 1.0, 1.0])
        for frame_data in product_frames[element.id()]:
            task = frame_data.get("task") or tool.Ifc.get().by_id(frame_data.get("task_id"))
            ColorType = colortype_sequence.get_assigned_ColorType_for_task(task, animation_props, active_group_name)
            apply_ColorType_animation(obj, frame_data, ColorType, original_color, settings)

    if animation_props.enable_live_color_updates:
        serializable_frames = {}
        for pid, frame_data_list in product_frames.items():
            serializable_list = []
            for item in frame_data_list:
                serializable_item = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in item.items() if k != 'task'}
                if 'task' in item and hasattr(item['task'], 'id'): serializable_item['task_id'] = item['task'].id()
                serializable_list.append(serializable_item)
            serializable_frames[str(pid)] = serializable_list
        bpy.context.scene['BIM_LiveUpdateProductFrames'] = {"product_frames": serializable_frames, "original_colors": original_colors}
        register_live_color_update_handler()

    set_object_shading()
    bpy.context.scene.frame_start = settings["start_frame"]
    bpy.context.scene.frame_end = int(settings["start_frame"] + settings["total_frames"] + 1)


def apply_ColorType_animation(obj, frame_data, ColorType, original_color, settings):
    if obj.animation_data: obj.animation_data_clear()

    # START state
    start_f, end_f = frame_data["states"]["before_start"]
    is_construction_output = frame_data.get("relationship") == "output"
    hide_at_start = is_construction_output and not getattr(ColorType, 'consider_start', False)
    if end_f >= start_f:
        obj.hide_viewport = obj.hide_render = hide_at_start
        obj.keyframe_insert(data_path="hide_viewport", frame=start_f)
        obj.keyframe_insert(data_path="hide_render", frame=start_f)
        if not hide_at_start:
            color = original_color if getattr(ColorType, 'use_start_original_color', False) else list(ColorType.start_color)
            alpha = 1.0 - getattr(ColorType, 'start_transparency', 0.0)
            obj.color = tuple(color[:3]) + (alpha,)
            obj.keyframe_insert(data_path="color", frame=start_f)
        obj.keyframe_insert(data_path="hide_viewport", frame=end_f)
        obj.keyframe_insert(data_path="hide_render", frame=end_f)
        if not hide_at_start: obj.keyframe_insert(data_path="color", frame=end_f)

    # ACTIVE state
    start_f, end_f = frame_data["states"]["active"]
    if end_f >= start_f and getattr(ColorType, 'consider_active', True):
        obj.hide_viewport = obj.hide_render = False
        obj.keyframe_insert(data_path="hide_viewport", frame=start_f)
        obj.keyframe_insert(data_path="hide_render", frame=start_f)
        color = original_color if getattr(ColorType, 'use_active_original_color', False) else list(ColorType.in_progress_color)
        alpha_start = 1.0 - getattr(ColorType, 'active_start_transparency', 0.0)
        alpha_end = 1.0 - getattr(ColorType, 'active_finish_transparency', 0.0)
        obj.color = tuple(color[:3]) + (alpha_start,)
        obj.keyframe_insert(data_path="color", frame=start_f)
        if end_f > start_f:
            obj.color = tuple(color[:3]) + (alpha_end,)
            obj.keyframe_insert(data_path="color", frame=end_f)

    # END state
    start_f, end_f = frame_data["states"]["after_end"]
    if end_f >= start_f and getattr(ColorType, 'consider_end', True):
        hide_at_end = getattr(ColorType, 'hide_at_end', False)
        obj.hide_viewport = obj.hide_render = hide_at_end
        obj.keyframe_insert(data_path="hide_viewport", frame=start_f)
        obj.keyframe_insert(data_path="hide_render", frame=start_f)
        if not hide_at_end:
            color = original_color if getattr(ColorType, 'use_end_original_color', True) else list(ColorType.end_color)
            alpha = 1.0 - getattr(ColorType, 'end_transparency', 0.0)
            obj.color = tuple(color[:3]) + (alpha,)
            obj.keyframe_insert(data_path="color", frame=start_f)

    # Restore hidden state post-keyframing to avoid flashes
    obj.hide_viewport = obj.hide_render = True


def live_color_update_handler(scene, depsgraph=None):
    global _last_frame
    if bpy.context.scene.get('BIM_VarianceColorModeActive', False):
        from . import variance_sequence
        variance_sequence._variance_aware_color_update()
        return

    live_props = scene.get('BIM_LiveUpdateProductFrames')
    if not live_props: return
    product_frames = live_props.get("product_frames", {})
    original_colors = live_props.get("original_colors", {})
    current_frame = scene.frame_current
    anim_props = props_sequence.get_animation_props()
    active_group_name = next((item.group for item in getattr(anim_props, "animation_group_stack", []) if item.enabled and item.group), "DEFAULT")
    set_object_shading()

    for obj in bpy.data.objects:
        element = tool.Ifc.get_entity(obj)
        if not element: continue
        pid_str = str(element.id())
        if pid_str not in product_frames: continue
        
        current_frame_data, current_state_name = None, None
        for fd in product_frames[pid_str]:
            for state_name, (start_f, end_f) in fd["states"].items():
                if start_f <= current_frame <= end_f:
                    current_frame_data, current_state_name = fd, state_name
                    break
            if current_frame_data: break
        if not current_frame_data: continue

        task = tool.Ifc.get().by_id(current_frame_data.get("task_id")) if current_frame_data.get("task_id") else None
        if not task: continue
        ColorType = colortype_sequence.get_assigned_ColorType_for_task(task, anim_props, active_group_name)
        if not ColorType: continue
        
        state = {"before_start": "start", "active": "in_progress", "after_end": "end"}.get(current_state_name)
        if not state: continue

        hide = (state == "start" and not getattr(ColorType, 'consider_start', True) and current_frame_data.get("relationship") == "output") or \
               (state == "end" and getattr(ColorType, 'hide_at_end', False))
        obj.hide_viewport = obj.hide_render = hide
        if hide: continue

        original_color = original_colors.get(obj.name, [1.0, 1.0, 1.0, 1.0])
        if state == "start":
            color = original_color if getattr(ColorType, 'use_start_original_color', False) else list(ColorType.start_color)
            alpha = 1.0 - getattr(ColorType, 'start_transparency', 0.0)
        elif state == "in_progress":
            color = original_color if getattr(ColorType, 'use_active_original_color', False) else list(ColorType.in_progress_color)
            alpha = 1.0 - getattr(ColorType, 'active_start_transparency', 0.0) # Simplified for live
        else: # end
            color = original_color if getattr(ColorType, 'use_end_original_color', True) else list(ColorType.end_color)
            alpha = 1.0 - getattr(ColorType, 'end_transparency', 0.0)
        obj.color = tuple(color[:3]) + (alpha,)


def register_live_color_update_handler():
    global _live_color_update_handler
    if live_color_update_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(live_color_update_handler)
        _live_color_update_handler = live_color_update_handler
    start_live_update_timer()


def unregister_live_color_update_handler():
    global _live_color_update_handler
    stop_live_update_timer()
    if _live_color_update_handler and _live_color_update_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_live_color_update_handler)

def get_animation_product_frames(work_schedule, settings):
    """Get product frames for animation timeline - simpler version"""
    from . import task_sequence
    import ifcopenshell.util.sequence
    
    if not work_schedule or not settings:
        return {}
    
    product_frames = {}
    start_date = settings.get('start')
    finish_date = settings.get('finish')
    
    if not start_date or not finish_date:
        return {}
    
    # Get all root tasks and process them
    for root_task in ifcopenshell.util.sequence.get_root_tasks(work_schedule):
        _process_task_for_frames(root_task, product_frames, settings)
    
    return product_frames

def _process_task_for_frames(task, product_frames, settings):
    """Helper function to process a task and its nested tasks for animation frames"""
    from . import task_sequence
    import ifcopenshell.util.sequence
    
    # Process nested tasks first
    for subtask in ifcopenshell.util.sequence.get_nested_tasks(task):
        _process_task_for_frames(subtask, product_frames, settings)
    
    # Get task timing
    task_time = task_sequence.get_task_time(task)
    if not task_time:
        return
    
    task_start = getattr(task_time, 'ScheduleStart', None)
    task_finish = getattr(task_time, 'ScheduleFinish', None)
    
    if not task_start or not task_finish:
        return
    
    # Get task outputs and add to product frames
    outputs = task_sequence.get_task_outputs(task)
    for output in outputs:
        if output.id() not in product_frames:
            product_frames[output.id()] = []
        
        product_frames[output.id()].append({
            'task': task,
            'task_id': task.id(),
            'start_date': task_start,
            'finish_date': task_finish,
            'relationship': 'output'
        })

def get_task_for_product(product):
    """Get the task associated with a product"""
    import bonsai.tool as tool
    
    if not product:
        return None
    
    # Find tasks that have this product as output
    ifc = tool.Ifc.get()
    
    for rel in getattr(product, 'HasAssignments', []):
        if rel.is_a('IfcRelAssignsToProcess'):
            relating_process = rel.RelatingProcess
            if relating_process and relating_process.is_a('IfcTask'):
                return relating_process
    
    return None
    _live_color_update_handler = None
    if bpy.context.scene.get('BIM_LiveUpdateProductFrames'):
        del bpy.context.scene['BIM_LiveUpdateProductFrames']


def start_live_update_timer():
    global _live_update_timer, _last_frame
    if _live_update_timer: return
    def timer_callback():
        global _last_frame
        try:
            current_frame = bpy.context.scene.frame_current
            if current_frame != _last_frame:
                _last_frame = current_frame
                live_color_update_handler(bpy.context.scene)
            return 0.1
        except Exception:
            return None
    _live_update_timer = bpy.app.timers.register(timer_callback)


def stop_live_update_timer():
    global _live_update_timer
    if _live_update_timer:
        try: bpy.app.timers.unregister(_live_update_timer)
        except: pass
        _live_update_timer = None
