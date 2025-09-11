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
import ifcopenshell.util.date
import ifcopenshell.util.sequence
from datetime import datetime, timedelta
from dateutil import parser
import bonsai.tool as tool
# Note: SequenceData import removed as it's not used in this file
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
    schedule_start, schedule_finish = guess_date_range(work_schedule)
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

def get_animation_bar_types():
    """Get available animation bar types for UI"""
    return [
        ('PROGRESS', 'Progress Bars', 'Show task progress bars'),
        ('FULL', 'Full Bars', 'Show full task duration bars'),
        ('BOTH', 'Both', 'Show both progress and full bars'),
    ]

def refresh_animation_color_scheme():
    """Refresh the animation color scheme"""
    props = props_sequence.get_animation_props()
    
    # Update color scheme based on current settings
    if props.color_scheme == 'DEFAULT':
        props.color_progress = (0.0, 1.0, 0.0)  # Green
        props.color_full = (1.0, 0.0, 0.0)      # Red
    elif props.color_scheme == 'HIGH_CONTRAST':
        props.color_progress = (0.0, 0.0, 1.0)  # Blue  
        props.color_full = (1.0, 1.0, 0.0)      # Yellow
    elif props.color_scheme == 'MONOCHROME':
        props.color_progress = (0.3, 0.3, 0.3)  # Dark gray
        props.color_full = (0.7, 0.7, 0.7)      # Light gray

def get_animation_color_scheme():
    """Get current animation color scheme"""
    props = props_sequence.get_animation_props()
    return {
        'scheme': getattr(props, 'color_scheme', 'DEFAULT'),
        'progress_color': tuple(getattr(props, 'color_progress', (0.0, 1.0, 0.0))),
        'full_color': tuple(getattr(props, 'color_full', (1.0, 0.0, 0.0))),
    }

def _create_empty_pivot_orbit():
    """Create empty pivot for orbit camera animation"""
    import bpy
    import mathutils
    
    # Create empty at scene center
    pivot = bpy.data.objects.new("4D_Orbit_Pivot", None)
    pivot.empty_display_type = 'SPHERE'
    pivot.empty_display_size = 2.0
    
    # Set location to scene center or selected objects center
    if bpy.context.selected_objects:
        # Calculate center of selected objects
        locations = [obj.location for obj in bpy.context.selected_objects]
        center = mathutils.Vector((0, 0, 0))
        for loc in locations:
            center += mathutils.Vector(loc)
        center /= len(locations)
        pivot.location = center
    else:
        pivot.location = (0, 0, 0)
    
    # Link to scene
    bpy.context.scene.collection.objects.link(pivot)
    
    return pivot

def _create_follow_path_orbit(path_points):
    """Create follow path orbit animation"""
    import bpy
    import bmesh
    
    # Create curve from path points
    curve_data = bpy.data.curves.new('4D_Orbit_Path', 'CURVE')
    curve_data.dimensions = '3D'
    curve_obj = bpy.data.objects.new('4D_Orbit_Path', curve_data)
    
    # Create spline
    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(len(path_points) - 1)
    
    # Set points
    for i, point in enumerate(path_points):
        spline.bezier_points[i].co = point
        spline.bezier_points[i].handle_left_type = 'AUTO'
        spline.bezier_points[i].handle_right_type = 'AUTO'
    
    # Make cyclic for orbit
    spline.use_cyclic_u = True
    
    # Link to scene
    bpy.context.scene.collection.objects.link(curve_obj)
    
    return curve_obj

def _create_keyframe_orbit(camera, pivot, radius=10, frames=250):
    """Create keyframe-based orbit animation"""
    import bpy
    import mathutils
    import math
    
    if not camera or not pivot:
        return False
    
    try:
        # Clear existing animation
        if camera.animation_data:
            camera.animation_data_clear()
        
        # Set initial position
        start_frame = bpy.context.scene.frame_start
        end_frame = start_frame + frames
        
        # Create circular orbit keyframes
        for frame in range(start_frame, end_frame + 1, 10):
            bpy.context.scene.frame_set(frame)
            
            # Calculate orbit position
            angle = 2 * math.pi * (frame - start_frame) / frames
            x = pivot.location.x + radius * math.cos(angle)
            y = pivot.location.y + radius * math.sin(angle)
            z = pivot.location.z + 5  # Slightly elevated
            
            # Set camera location
            camera.location = (x, y, z)
            camera.keyframe_insert(data_path="location")
            
            # Look at pivot
            direction = mathutils.Vector(pivot.location) - mathutils.Vector(camera.location)
            camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
            camera.keyframe_insert(data_path="rotation_euler")
        
        # Set interpolation to linear for smooth motion
        if camera.animation_data and camera.animation_data.action:
            for fcurve in camera.animation_data.action.fcurves:
                for keyframe in fcurve.keyframe_points:
                    keyframe.interpolation = 'LINEAR'
        
        print(f"\u2705 Created orbit animation for {camera.name}")
        return True
        
    except Exception as e:
        print(f"\u274c Error creating orbit animation: {e}")
        return False

def _create_animated_text(text_content, location, frames_duration=50):
    """Create animated text object"""
    import bpy
    
    # Create text object
    text_data = bpy.data.curves.new(name="4D_AnimText", type='FONT')
    text_data.body = text_content
    text_data.size = 2.0
    text_obj = bpy.data.objects.new("4D_AnimText", text_data)
    
    # Set location
    text_obj.location = location
    
    # Link to scene
    bpy.context.scene.collection.objects.link(text_obj)
    
    # Animate appearance
    current_frame = bpy.context.scene.frame_current
    
    # Start invisible
    text_obj.hide_viewport = True
    text_obj.keyframe_insert(data_path="hide_viewport", frame=current_frame)
    
    # Become visible
    text_obj.hide_viewport = False
    text_obj.keyframe_insert(data_path="hide_viewport", frame=current_frame + 1)
    
    # Fade out
    text_obj.hide_viewport = True
    text_obj.keyframe_insert(data_path="hide_viewport", frame=current_frame + frames_duration)
    
    return text_obj

def _animate_text_by_type(text_obj, animation_type='FADE'):
    """Animate text object with different animation types"""
    import bpy
    
    if not text_obj:
        return False
    
    current_frame = bpy.context.scene.frame_current
    
    try:
        if animation_type == 'FADE':
            # Simple fade in/out
            text_obj.color = (1, 1, 1, 0)  # Transparent
            text_obj.keyframe_insert(data_path="color", frame=current_frame)
            
            text_obj.color = (1, 1, 1, 1)  # Opaque
            text_obj.keyframe_insert(data_path="color", frame=current_frame + 10)
            
            text_obj.color = (1, 1, 1, 0)  # Transparent
            text_obj.keyframe_insert(data_path="color", frame=current_frame + 40)
            
        elif animation_type == 'SCALE':
            # Scale animation
            text_obj.scale = (0.1, 0.1, 0.1)
            text_obj.keyframe_insert(data_path="scale", frame=current_frame)
            
            text_obj.scale = (1.2, 1.2, 1.2)
            text_obj.keyframe_insert(data_path="scale", frame=current_frame + 10)
            
            text_obj.scale = (1.0, 1.0, 1.0)
            text_obj.keyframe_insert(data_path="scale", frame=current_frame + 20)
            
        return True
        
    except Exception as e:
        print(f"Error animating text: {e}")
        return False

def add_product_frame_enhanced(product, start_frame, finish_frame):
    """Enhanced version of add_product_frame with additional features"""
    import bpy
    import bonsai.tool as tool
    
    obj = tool.Ifc.get_object(product)
    if not obj:
        return False
    
    try:
        # Enhanced frame addition with better interpolation
        obj.hide_viewport = True
        obj.hide_render = True
        obj.keyframe_insert(data_path="hide_viewport", frame=start_frame - 1)
        obj.keyframe_insert(data_path="hide_render", frame=start_frame - 1)
        
        # Show object during active period
        obj.hide_viewport = False
        obj.hide_render = False
        obj.keyframe_insert(data_path="hide_viewport", frame=start_frame)
        obj.keyframe_insert(data_path="hide_render", frame=start_frame)
        obj.keyframe_insert(data_path="hide_viewport", frame=finish_frame)
        obj.keyframe_insert(data_path="hide_render", frame=finish_frame)
        
        # Hide after completion
        obj.hide_viewport = True
        obj.hide_render = True
        obj.keyframe_insert(data_path="hide_viewport", frame=finish_frame + 1)
        obj.keyframe_insert(data_path="hide_render", frame=finish_frame + 1)
        
        # Set interpolation to constant
        if obj.animation_data and obj.animation_data.action:
            for fcurve in obj.animation_data.action.fcurves:
                if fcurve.data_path in ["hide_viewport", "hide_render"]:
                    for keyframe in fcurve.keyframe_points:
                        keyframe.interpolation = 'CONSTANT'
        
        return True
        
    except Exception as e:
        print(f"Error in enhanced product frame: {e}")
        return False

def add_product_frame_full_range(product, task):
    """Add product frame for full task range with sophisticated timing"""
    import bpy
    import bonsai.tool as tool
    import ifcopenshell.util.sequence
    
    obj = tool.Ifc.get_object(product)
    if not obj or not task:
        return False
    
    try:
        # Get task timing
        task_start_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
        task_finish_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
        
        if not (task_start_date and task_finish_date):
            return False
        
        # Calculate frames based on full date range
        from . import utils_sequence
        schedule_start, schedule_finish = utils_sequence.get_schedule_date_range()
        
        if not (schedule_start and schedule_finish):
            return False
        
        total_duration = (schedule_finish - schedule_start).total_seconds()
        task_start_progress = (task_start_date - schedule_start).total_seconds() / total_duration
        task_finish_progress = (task_finish_date - schedule_start).total_seconds() / total_duration
        
        start_frame = int(bpy.context.scene.frame_start + task_start_progress * (bpy.context.scene.frame_end - bpy.context.scene.frame_start))
        finish_frame = int(bpy.context.scene.frame_start + task_finish_progress * (bpy.context.scene.frame_end - bpy.context.scene.frame_start))
        
        return add_product_frame_enhanced(product, start_frame, finish_frame)
        
    except Exception as e:
        print(f"Error in full range product frame: {e}")
        return False

def apply_visibility_animation():
    """Apply visibility animation to all scheduled products"""
    import bpy
    import bonsai.tool as tool
    import ifcopenshell.util.sequence
    
    try:
        ifc = tool.Ifc.get()
        if not ifc:
            return False
        
        # Get active work schedule
        from . import props_sequence
        props = props_sequence.get_work_schedule_props()
        if not props.active_work_schedule_id:
            return False
        
        work_schedule = ifc.by_id(props.active_work_schedule_id)
        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
        
        processed_count = 0
        
        def process_tasks_recursive(tasks):
            nonlocal processed_count
            for task in tasks:
                task_outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
                for output in task_outputs:
                    if add_product_frame_full_range(output, task):
                        processed_count += 1
                
                nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                if nested_tasks:
                    process_tasks_recursive(nested_tasks)
        
        process_tasks_recursive(root_tasks)
        
        print(f"Applied visibility animation to {processed_count} products")
        return processed_count > 0
        
    except Exception as e:
        print(f"Error applying visibility animation: {e}")
        return False

def calculate_using_duration(task):
    """Calculate frames using task duration"""
    import ifcopenshell.util.sequence
    import ifcopenshell.util.date
    import bpy
    
    try:
        task_time = task.TaskTime if task else None
        if not task_time or not task_time.ScheduleDuration:
            return None, None
        
        # Parse duration
        duration_str = task_time.ScheduleDuration
        duration = ifcopenshell.util.date.ifc2datetime(duration_str)
        
        if not duration:
            return None, None
        
        # Convert duration to frames (assuming 1 day = 30 frames)
        duration_days = duration.days + duration.seconds / 86400.0
        duration_frames = int(duration_days * 30)
        
        # Get start date
        task_start_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
        if not task_start_date:
            return None, None
        
        # Calculate frame position
        from . import utils_sequence
        schedule_start, schedule_finish = utils_sequence.get_schedule_date_range()
        if not (schedule_start and schedule_finish):
            return None, None
        
        total_duration = (schedule_finish - schedule_start).total_seconds()
        start_progress = (task_start_date - schedule_start).total_seconds() / total_duration
        
        total_frames = bpy.context.scene.frame_end - bpy.context.scene.frame_start
        start_frame = int(bpy.context.scene.frame_start + start_progress * total_frames)
        finish_frame = start_frame + duration_frames
        
        return start_frame, finish_frame
        
    except Exception as e:
        print(f"Error calculating duration frames: {e}")
        return None, None

def calculate_using_frames(start_frame, duration_frames):
    """Calculate using explicit frame values"""
    import bpy
    
    try:
        # Validate frame range
        start_frame = max(bpy.context.scene.frame_start, min(bpy.context.scene.frame_end, start_frame))
        finish_frame = max(bpy.context.scene.frame_start, min(bpy.context.scene.frame_end, start_frame + duration_frames))
        
        return start_frame, finish_frame
        
    except Exception as e:
        print(f"Error calculating explicit frames: {e}")
        return None, None

def calculate_using_multiplier(base_start, base_duration, multiplier):
    """Calculate frames using a multiplier"""
    try:
        adjusted_duration = int(base_duration * multiplier)
        return calculate_using_frames(base_start, adjusted_duration)
        
    except Exception as e:
        print(f"Error calculating multiplier frames: {e}")
        return None, None

def debug_ColorType_application():
    """Debug ColorType application process"""
    import bpy
    import bonsai.tool as tool
    
    try:
        # Get active work schedule
        from . import props_sequence
        props = props_sequence.get_work_schedule_props()
        if not props.active_work_schedule_id:
            print("❌ No active work schedule for ColorType debug")
            return False
        
        work_schedule = tool.Ifc.get().by_id(props.active_work_schedule_id)
        print(f"🔍 ColorType Debug for schedule: {work_schedule.Name}")
        
        # Check task properties
        tprops = props_sequence.get_task_tree_props()
        if not tprops or not hasattr(tprops, 'tasks'):
            print("❌ No task properties available")
            return False
        
        colortype_tasks = 0
        total_tasks = 0
        
        for task in tprops.tasks:
            total_tasks += 1
            use_active = getattr(task, 'use_active_colortype_group', False)
            colortype_groups = getattr(task, 'ColorType_groups', '')
            
            if use_active or colortype_groups:
                colortype_tasks += 1
                print(f"  Task {task.name}: active={use_active}, groups='{colortype_groups}'")
        
        print(f"🎨 ColorType Summary: {colortype_tasks}/{total_tasks} tasks have ColorType configuration")
        return colortype_tasks > 0
        
    except Exception as e:
        print(f"❌ ColorType debug error: {e}")
        return False


def add_product_frame_full_range(product, start_frame, finish_frame):
    """Add product frame with full range visibility support"""
    obj = tool.Ifc.get_object(product)
    if not obj:
        return
    
    # Set full range visibility
    obj.hide_viewport = False
    obj.keyframe_insert(data_path="hide_viewport", frame=start_frame)
    obj.keyframe_insert(data_path="hide_viewport", frame=finish_frame)
    
    # Add render visibility keyframes
    obj.hide_render = False
    obj.keyframe_insert(data_path="hide_render", frame=start_frame)
    obj.keyframe_insert(data_path="hide_render", frame=finish_frame)
    
    # Mark object as animated for 4D
    obj['is_4d_animated'] = True
    obj['4d_start_frame'] = start_frame
    obj['4d_finish_frame'] = finish_frame


def calculate_using_frames(task, frames_per_day=30):
    """Calculate task timing using frame-based approach"""
    if not task:
        return None, None
    
    # Get task timing from IFC
    start_time = ifcopenshell.util.sequence.get_start_time(task)
    finish_time = ifcopenshell.util.sequence.get_finish_time(task)
    
    if not start_time or not finish_time:
        return None, None
    
    # Convert to frames (assuming frames_per_day = 30)
    start_frame = 1  # Default start
    duration_days = (finish_time - start_time).days if hasattr(finish_time - start_time, 'days') else 1
    finish_frame = start_frame + (duration_days * frames_per_day)
    
    return start_frame, finish_frame


def calculate_using_multiplier(task, multiplier=1.0):
    """Calculate task timing using a multiplier for speed adjustment"""
    start_frame, finish_frame = calculate_using_frames(task)
    
    if start_frame is None or finish_frame is None:
        return None, None
    
    # Apply multiplier to duration
    duration = finish_frame - start_frame
    new_duration = int(duration * multiplier)
    
    return start_frame, start_frame + new_duration


def add_bar(task, start_frame, finish_frame):
    """Add animation bar for task timeline"""
    try:
        # Create bar object
        bpy.ops.mesh.primitive_cube_add(size=2)
        bar_obj = bpy.context.active_object
        bar_obj.name = f"TaskBar_{task.Name or task.id()}"
        
        # Scale and position bar
        duration = finish_frame - start_frame
        bar_obj.scale = (duration * 0.1, 0.1, 0.1)
        bar_obj.location = (start_frame * 0.1, 0, 0)
        
        # Add material
        mat = bpy.data.materials.new(name=f"TaskMat_{task.id()}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs[0].default_value = (0.2, 0.6, 1.0, 1.0)  # Blue
        
        bar_obj.data.materials.append(mat)
        bar_obj['task_id'] = task.id()
        
        return bar_obj
        
    except Exception as e:
        print(f"❌ Bar creation error: {e}")
        return None


def add_text(text_content, location=(0, 0, 0)):
    """Add 3D text object"""
    try:
        # Create text object
        bpy.ops.object.text_add(location=location)
        text_obj = bpy.context.active_object
        text_obj.data.body = str(text_content)
        
        # Configure text properties
        text_obj.data.size = 0.5
        text_obj.data.extrude = 0.1
        
        return text_obj
        
    except Exception as e:
        print(f"❌ Text creation error: {e}")
        return None


def animate_color(obj, start_color, end_color, start_frame, end_frame):
    """Animate object color transition"""
    try:
        if not obj or not obj.data or not obj.data.materials:
            return
            
        mat = obj.data.materials[0]
        if not mat.use_nodes:
            return
            
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if not bsdf:
            return
        
        # Set start color
        bsdf.inputs[0].default_value = start_color
        bsdf.inputs[0].keyframe_insert(data_path="default_value", frame=start_frame)
        
        # Set end color
        bsdf.inputs[0].default_value = end_color
        bsdf.inputs[0].keyframe_insert(data_path="default_value", frame=end_frame)
        
    except Exception as e:
        print(f"❌ Color animation error: {e}")


def animate_scale(obj, start_scale, end_scale, start_frame, end_frame):
    """Animate object scale transition"""
    try:
        if not obj:
            return
            
        # Set start scale
        obj.scale = start_scale
        obj.keyframe_insert(data_path="scale", frame=start_frame)
        
        # Set end scale
        obj.scale = end_scale
        obj.keyframe_insert(data_path="scale", frame=end_frame)
        
    except Exception as e:
        print(f"❌ Scale animation error: {e}")


def create_plane(location=(0, 0, 0), size=2.0):
    """Create a plane object"""
    try:
        bpy.ops.mesh.primitive_plane_add(location=location, size=size)
        plane = bpy.context.active_object
        return plane
    except Exception as e:
        print(f"❌ Plane creation error: {e}")
        return None


def create_task_bar_data(task):
    """Create task bar data structure"""
    try:
        start_time = ifcopenshell.util.sequence.get_start_time(task)
        finish_time = ifcopenshell.util.sequence.get_finish_time(task)
        
        if not start_time or not finish_time:
            return None
            
        return {
            'task_id': task.id(),
            'task_name': task.Name or f"Task {task.id()}",
            'start_time': start_time,
            'finish_time': finish_time,
            'duration': (finish_time - start_time).days if hasattr(finish_time - start_time, 'days') else 1,
            'status': getattr(task, 'TaskStatus', 'NOTSTARTED')
        }
        
    except Exception as e:
        print(f"❌ Task bar data creation error: {e}")
        return None


def place_bar(bar_data, y_position=0):
    """Place task bar in 3D space"""
    try:
        if not bar_data:
            return
            
        # Calculate position based on time
        start_frame = 1  # Default start
        duration_frames = bar_data['duration'] * 30  # 30 frames per day
        
        # Create or get bar object
        bar_name = f"Bar_{bar_data['task_id']}"
        if bar_name in bpy.data.objects:
            bar_obj = bpy.data.objects[bar_name]
        else:
            bar_obj = add_bar(bar_data, start_frame, start_frame + duration_frames)
            if bar_obj:
                bar_obj.name = bar_name
        
        if bar_obj:
            bar_obj.location.y = y_position
            
    except Exception as e:
        print(f"❌ Bar placement error: {e}")


def set_material(obj, material_name):
    """Set material for object"""
    try:
        if not obj:
            return
            
        mat = bpy.data.materials.get(material_name)
        if not mat:
            mat = bpy.data.materials.new(name=material_name)
            mat.use_nodes = True
            
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
            
    except Exception as e:
        print(f"❌ Material setting error: {e}")


def shift_object(obj, offset):
    """Shift object by offset vector"""
    try:
        if obj and hasattr(offset, '__len__') and len(offset) >= 3:
            obj.location.x += offset[0]
            obj.location.y += offset[1] 
            obj.location.z += offset[2]
    except Exception as e:
        print(f"❌ Object shifting error: {e}")


def get_animation_materials():
    """Get all materials used for animation"""
    try:
        animation_materials = []
        for mat in bpy.data.materials:
            if mat.name.startswith("4D_") or '4d_' in mat.name.lower():
                animation_materials.append(mat)
        return animation_materials
    except Exception as e:
        print(f"❌ Animation materials retrieval error: {e}")
        return []
