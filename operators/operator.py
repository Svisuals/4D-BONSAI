import bpy
import json
import calendar
from mathutils import Matrix
from datetime import datetime
from dateutil import relativedelta
import bonsai.tool as tool


try:
    from .prop import update_filter_column
    from . import prop
    from .ui import calculate_visible_columns_count
except Exception:
    try:
        from bonsai.bim.module.sequence.prop import update_filter_column
        import bonsai.bim.module.sequence.prop as prop
        from bonsai.bim.module.sequence.ui import calculate_visible_columns_count
    except Exception:
        def update_filter_column(*args, **kwargs):
            pass
        def calculate_visible_columns_count(context):
            return 3  # Safe fallback
        # Fallback for safe assignment function
        class PropFallback:
            @staticmethod
            def safe_set_selected_colortype_in_active_group(task_obj, value, skip_validation=False):
                try:
                    setattr(task_obj, "selected_colortype_in_active_group", value)
                except Exception as e:
                    print(f"❌ Fallback safe_set failed: {e}")
        prop = PropFallback()


# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2020, 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>
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

# pyright: reportUnnecessaryTypeIgnoreComment=error

import os


import bpy
import json
import time
import calendar
import isodate
import bonsai.core.sequence as core
import bonsai.bim.module.sequence.helper as helper
from .animation_operators import _clear_previous_animation, _get_animation_settings, _compute_product_frames, _ensure_default_group
try:
    from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
except Exception:
    UnifiedColorTypeManager = None  # optional
try:
    from bonsai.bim.module.sequence.prop import TaskcolortypeGroupChoice
except Exception:
    TaskcolortypeGroupChoice = None  # optional

import ifcopenshell.util.sequence
import ifcopenshell.util.selector
from datetime import datetime
from dateutil import parser, relativedelta
from bpy_extras.io_utils import ImportHelper, ExportHelper

# === Local handler to keep schedule texts in sync with the chosen date range ===
_LOCAL_TEXT_HANDLER = None

def _parse_dt_any(v):
    """Parse 'YYYY-MM-DD' or ISO-like strings to datetime (no external deps)."""
    try:
        # Accept datetime/date objects
        if hasattr(v, 'year') and hasattr(v, 'month') and hasattr(v, 'day'):
            from datetime import datetime as _dt
            # If it's already datetime-like, normalize to datetime
            if hasattr(v, 'hour'):
                return v
            return _dt(v.year, v.month, v.day)
        s = str(v).strip()
        if not s:
            return None
        from datetime import datetime as _dt
        # Full datetime
        try:
            return _dt.fromisoformat(s.replace('Z',''))
        except Exception:
            pass
        # Date-only
        try:
            return _dt.fromisoformat(s.split('T')[0])
        except Exception:
            return None
    except Exception:
        return None

# REMOVED: Duplicate calculate_schedule_metrics function - using unified version below

def _ensure_local_text_settings_on_obj(_obj, _settings):
    """Attach or refresh minimal settings on text data so the handler maps frame→date correctly."""
    try:
        data = getattr(_obj, 'data', None)
        if not data:
            return
        aset = dict(data.get('animation_settings', {}))
        def _get(k, default=None):
            if isinstance(_settings, dict):
                return _settings.get(k, default)
            return getattr(_settings, k, default)

        scene = bpy.context.scene
        new_vals = {
            'start_frame': int(_get('start_frame', getattr(scene, 'frame_start', 1) or 1)),
            'total_frames': int(_get('total_frames', max(1, int(getattr(scene, 'frame_end', 250)) - int(getattr(scene, 'frame_start', 1))))),
            'start_date': _get('start', None),
            'finish_date': _get('finish', None),
            'schedule_start': _get('schedule_start', None),
            'schedule_finish': _get('schedule_finish', None),
            'schedule_name': _get('schedule_name', None),
        }
        changed = False
        for k, v in new_vals.items():
            if aset.get(k) != v and v is not None:
                aset[k] = v
                changed = True
        if changed:
            data['animation_settings'] = aset

        # Ensure text_type is defined for the handler
        if not data.get('text_type'):
            n = (getattr(_obj, 'name', '') or '').lower()
            if 'schedule_name' in n:
                data['text_type'] = 'schedule_name'
            elif 'date' in n:
                data['text_type'] = 'date'
            elif 'week' in n:
                data['text_type'] = 'week'
            elif 'day' in n:
                data['text_type'] = 'day_counter'
            elif 'progress' in n:
                data['text_type'] = 'progress'
    except Exception:
        pass

def _local_schedule_texts_update_handler(scene, depsgraph):
    '''Update schedule text objects each frame. Week/Day/Progress use the same robust logic as HUD Schedule.'''
    print("🎬 3D Text Handler: Starting update...")
    try:

        coll = bpy.data.collections.get("Schedule_Display_Texts")
        if not coll:
            print("⚠️ 3D Text Handler: No 'Schedule_Display_Texts' collection found")
            return
        
        print(f"📝 3D Text Handler: Found collection with {len(coll.objects)} objects")
        
        # CHECK FOR SNAPSHOT MODE
        snapshot_mode = False
        snapshot_date = None
        
        # Check if there's a snapshot date stored in scene properties
        if hasattr(scene, 'BIMWorkPlanProperties'):
            ws_props = tool.Sequence.get_work_schedule_props()
            snapshot_date_str = getattr(ws_props, "visualisation_start", None)
            
            # Check if we're in snapshot mode (same start and finish date, or specific snapshot flag)
            finish_date_str = getattr(ws_props, "visualisation_finish", None)
            
            if (snapshot_date_str and snapshot_date_str != "-" and 
                ((finish_date_str and finish_date_str == snapshot_date_str) or 
                 scene.get("is_snapshot_mode", False))):
                
                try:
                    snapshot_date = tool.Sequence.parse_isodate_datetime(snapshot_date_str)
                    if snapshot_date:
                        snapshot_mode = True
                        print(f"📸 3D Text Handler: SNAPSHOT MODE detected for date {snapshot_date.strftime('%Y-%m-%d')}")
                except Exception as e:
                    print(f"⚠️ 3D Text Handler: Error parsing snapshot date: {e}")
        
        if snapshot_mode and snapshot_date:
            # SNAPSHOT MODE: Use fixed date, ignore frame-based calculation
            cur_dt = snapshot_date
            print(f"📸 Using snapshot date: {cur_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            # ANIMATION MODE: Use frame-based calculation as before
            cur_frame = int(scene.frame_current)
            for obj in list(coll.objects):
                cdata = getattr(obj, "data", None)
                if not cdata:
                    continue
                meta = dict(cdata.get("animation_settings", {})) or {}
                start_frame = int(meta.get("start_frame", scene.frame_start))
                total_frames = int(meta.get("total_frames", max(1, scene.frame_end - scene.frame_start)))
                if total_frames <= 0:
                    total_frames = 1
                # Normalized progress along the configured WINDOW
                prog = (cur_frame - start_frame) / float(total_frames)
                prog = max(0.0, min(1.0, prog))

                # Window dates for mapping frame -> current date
                wnd_start = _parse_dt_any(meta.get("start_date"))
                wnd_finish = _parse_dt_any(meta.get("finish_date"))
                cur_dt = None
                if wnd_start and wnd_finish:
                    try:
                        delta_w = (wnd_finish - wnd_start)
                        cur_dt = wnd_start + prog * delta_w
                    except Exception:
                        cur_dt = wnd_start
                        
                # Process this object with its calculated cur_dt
                _update_single_3d_text_object(obj, cdata, cur_dt)
                
            return  # Early return for animation mode
        
        # SNAPSHOT MODE: Process all objects with the same snapshot date
        for obj in list(coll.objects):
            cdata = getattr(obj, "data", None)
            if not cdata:
                continue
            _update_single_3d_text_object(obj, cdata, cur_dt)
            
    except Exception as e:
        print(f"❌ 3D Text Handler error: {e}")
        import traceback
        traceback.print_exc()

def _update_single_3d_text_object(obj, cdata, cur_dt):
    """Update a single 3D text object with the given current date"""
    try:
        
        # --- ROBUST METHOD TO GET FULL SCHEDULE RANGE (like Viewport HUD) ---
        sch_start, sch_finish = None, None
        try:
            active_schedule = tool.Sequence.get_active_work_schedule()
            if active_schedule:
                sch_start, sch_finish = tool.Sequence.get_schedule_date_range()
                if not (sch_start and sch_finish):
                    # Fallback to task-based date extraction
                    import ifcopenshell.util.sequence
                    tasks = ifcopenshell.util.sequence.get_root_tasks(active_schedule)
                    if tasks:
                        all_dates = []
                        for task in tasks:
                            task_time = getattr(task, 'TaskTime', None)
                            if task_time:
                                start = getattr(task_time, 'ScheduleStart', None)
                                finish = getattr(task_time, 'ScheduleFinish', None)
                                if start: all_dates.append(start)
                                if finish: all_dates.append(finish)
                        
                        if all_dates:
                            datetime_dates = [dt for dt in (_parse_dt_any(d) for d in all_dates) if dt]
                            if datetime_dates:
                                sch_start = min(datetime_dates)
                                sch_finish = max(datetime_dates)
        except Exception as e:
            print(f"Bonsai WARNING: Could not get full schedule range for 3D texts: {e}")
        
        # DEBUG: Log what we got
        if sch_start and sch_finish:
            print(f"📊 3D Texts: Using schedule range {sch_start.strftime('%Y-%m-%d')} → {sch_finish.strftime('%Y-%m-%d')}")
        else:
            print(f"⚠️ 3D Texts: No schedule range available (sch_start={sch_start}, sch_finish={sch_finish})")

        ttype = (cdata.get("text_type") or "").lower()

        if ttype == "schedule_name":
            try:
                # For schedule_name, we need to get the meta from the object
                meta = dict(cdata.get("animation_settings", {})) or {}
                schedule_name = meta.get("schedule_name", "No Schedule")
                cdata.body = f"Schedule: {schedule_name}"
            except Exception:
                cdata.body = "Schedule: --"
        elif ttype == "date":
            if cur_dt:
                try:
                    cdata.body = cur_dt.strftime("%d/%m/%Y")
                except Exception:
                    cdata.body = str(cur_dt).split("T")[0]

        elif ttype == "week":
            try:
                print(f"🔍 Week text: cur_dt={cur_dt}, sch_start={sch_start}, sch_finish={sch_finish}")
                if cur_dt and sch_start and sch_finish:
                    # Use the same robust logic as HUD Schedule
                    cd_d = cur_dt.date()
                    fss_d = sch_start.date() 
                    fse_d = sch_finish.date()
                    delta_days = (cd_d - fss_d).days
                    
                    if cd_d < fss_d:
                        week_number = 0
                    else:
                        week_number = max(1, (delta_days // 7) + 1)
                    
                    print(f"📊 Week calculation: current={cd_d}, start={fss_d}, delta_days={delta_days}, week={week_number}")
                    cdata.body = f"Week {week_number}"
                else:
                    print(f"⚠️ Week text: Missing data, showing fallback")
                    cdata.body = "Week --"
            except Exception as e:
                print(f"❌ Week text error: {e}")
                cdata.body = "Week --"

        elif ttype == "day_counter":
            try:
                print(f"🔍 Day text: cur_dt={cur_dt}, sch_start={sch_start}, sch_finish={sch_finish}")
                if cur_dt and sch_start and sch_finish:
                    # Use the same robust logic as HUD Schedule
                    cd_d = cur_dt.date()
                    fss_d = sch_start.date()
                    delta_days = (cd_d - fss_d).days
                    
                    if cd_d < fss_d:
                        day_from_schedule = 0
                    else:
                        day_from_schedule = max(1, delta_days + 1)
                    
                    print(f"📊 Day calculation: current={cd_d}, start={fss_d}, delta_days={delta_days}, day={day_from_schedule}")
                    cdata.body = f"Day {day_from_schedule}"
                else:
                    print(f"⚠️ Day text: Missing data, showing fallback")
                    cdata.body = "Day --"
            except Exception as e:
                print(f"❌ Day text error: {e}")
                cdata.body = "Day --"

        elif ttype == "progress":
            try:
                print(f"🔍 Progress text: cur_dt={cur_dt}, sch_start={sch_start}, sch_finish={sch_finish}")
                if cur_dt and sch_start and sch_finish:
                    # Use the same robust logic as HUD Schedule
                    cd_d = cur_dt.date()
                    fss_d = sch_start.date()
                    fse_d = sch_finish.date()
                    
                    if cd_d < fss_d:
                        progress_pct = 0
                    elif cd_d >= fse_d:
                        progress_pct = 100
                    else:
                        total_schedule_days = (fse_d - fss_d).days
                        if total_schedule_days <= 0:
                            progress_pct = 100
                        else:
                            delta_days = (cd_d - fss_d).days
                            progress_pct = (delta_days / total_schedule_days) * 100
                            progress_pct = round(progress_pct)
                            progress_pct = max(0, min(100, progress_pct))
                    
                    print(f"📊 Progress calculation: current={cd_d}, start={fss_d}, end={fse_d}, progress={progress_pct}%")
                    cdata.body = f"Progress: {progress_pct}%"
                else:
                    # Fallback: show percentage based on time
                    print(f"⚠️ Progress text: Missing schedule data, showing fallback")
                    cdata.body = "Progress: --%"
            except Exception as e:
                print(f"❌ Progress text error: {e}")
                cdata.body = "Progress: --%"
                
    except Exception as e:
        print(f"❌ Error updating 3D text object: {e}")
    except Exception:
        pass

def _local_unregister_text_handler():
    global _LOCAL_TEXT_HANDLER
    try:

        if _LOCAL_TEXT_HANDLER and _LOCAL_TEXT_HANDLER in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.remove(_LOCAL_TEXT_HANDLER)
    except Exception:
        pass

def _local_register_text_handler(settings=None):
    """Register fallback handler once, attach settings to known text objects if passed."""
    global _LOCAL_TEXT_HANDLER
    try:
        _local_unregister_text_handler()
    except Exception:
        pass
    try:

        coll = bpy.data.collections.get("Schedule_Display_Texts")
        if coll and settings is not None:
            for obj in list(coll.objects):
                _ensure_local_text_settings_on_obj(obj, settings)
    except Exception:
        pass
    _LOCAL_TEXT_HANDLER = _local_schedule_texts_update_handler
    try:
        if _LOCAL_TEXT_HANDLER not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(_LOCAL_TEXT_HANDLER)
        # Immediate refresh
        _LOCAL_TEXT_HANDLER(bpy.context.scene, None)
    except Exception:
        pass

def _unified_register_text_handler(settings=None):
    ok = False
    try:
        if hasattr(tool.Sequence, "_register_multi_text_handler"):
            tool.Sequence._register_multi_text_handler(settings)
            ok = True
    except Exception:
        ok = False
    if not ok:
        _local_register_text_handler(settings)

def _infer_schedule_date_range(work_schedule):
    '''Infer earliest start and latest finish across tasks of the given work_schedule.'''
    try:
        import ifcopenshell
    except Exception:
        return None, None
    try:
        tasks = []
        try:
            if getattr(work_schedule, "Controls", None):
                for rel in work_schedule.Controls:
                    for ob in getattr(rel, "RelatedObjects", []) or []:
                        if hasattr(ob, "is_a") and ob.is_a("IfcTask"):
                            tasks.append(ob)
        except Exception:
            pass
        if not tasks:
            try:
                file = work_schedule.wrapped_data.file
                tasks = [t for t in file.by_type("IfcTask")]
            except Exception:
                tasks = []
        earliest = None
        latest = None
        for t in tasks:
            tt = getattr(t, "TaskTime", None) or getattr(t, "Time", None)
            if not tt:
                continue
            start_raw = None
            finish_raw = None
            for k in ("ActualStart","ScheduleStart","EarlyStart","LateStart","StartTime","Start"):
                if hasattr(tt, k) and getattr(tt, k):
                    start_raw = getattr(tt, k); break
            for k in ("ActualFinish","ScheduleFinish","EarlyFinish","LateFinish","FinishTime","Finish"):
                if hasattr(tt, k) and getattr(tt, k):
                    finish_raw = getattr(tt, k); break
            s = _parse_dt_any(start_raw)
            f = _parse_dt_any(finish_raw)
            if s:
                earliest = s if earliest is None else min(earliest, s)
            if f:
                latest = f if latest is None else max(latest, f)
        return earliest, latest
    except Exception:
        return None, None

from typing import get_args, TYPE_CHECKING, assert_never

# --- Lazy Enum items providers to avoid circular import with bonsai.tool ---

# ---- Unified Animation Bridges ----


class ContractTask(bpy.types.Operator):
    bl_idname = "bim.contract_task"
    bl_label = "Contract Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        
        

        snapshot_all_ui_state(context)

        core.contract_task(tool.Sequence, task=tool.Ifc.get().by_id(self.task))

        return {'FINISHED'}


        restore_all_ui_state(context)

class RemoveTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.remove_task"
    bl_label = "Remove Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        
        

        snapshot_all_ui_state(context)

        core.remove_task(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))


        
        try:

            ws = tool.Sequence.get_active_work_schedule()

            if ws:

                tool.Sequence.load_task_tree(ws)

                tool.Sequence.load_task_properties()

        except Exception:

            pass

        restore_all_ui_state(context)

class EnableEditingTaskTime(bpy.types.Operator, tool.Ifc.Operator):
    # IFC operator is needed because operator is adding a new task time to IFC
    # if it doesn't exist.
    bl_idname = "bim.enable_editing_task_time"
    bl_label = "Enable Editing Task Time"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.enable_editing_task_time(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))

class EditTaskTime(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_task_time"
    bl_label = "Edit Task Time"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        core.edit_task_time(
            tool.Ifc,
            tool.Sequence,
            tool.Resource,
            task_time=tool.Ifc.get().by_id(props.active_task_time_id),
        )

class EnableEditingTask(bpy.types.Operator):
    bl_idname = "bim.enable_editing_task_attributes"
    bl_label = "Enable Editing Task Attributes"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_task_attributes(tool.Sequence, task=tool.Ifc.get().by_id(self.task))
        return {"FINISHED"}

class DisableEditingTask(bpy.types.Operator):
    bl_idname = "bim.disable_editing_task"
    bl_label = "Disable Editing Task"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # USAR EL MISMO PATRÓN QUE LOS FILTROS (que funciona correctamente):
        snapshot_all_ui_state(context)  # >>> 1. Guardar estado ANTES de cancelar
        
        # >>> 2. Ejecutar la operación de cancelar
        core.disable_editing_task(tool.Sequence)
        
        return {"FINISHED"}

class EditTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_task"
    bl_label = "Edit Task"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        core.edit_task(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(props.active_task_id))

class CopyTaskAttribute(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.copy_task_attribute"
    bl_label = "Copy Task Attribute"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def _execute(self, context):
        core.copy_task_attribute(tool.Ifc, tool.Sequence, attribute_name=self.name)

class AddTimePeriod(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_time_period"
    bl_label = "Add Time Period"
    bl_options = {"REGISTER", "UNDO"}
    recurrence_pattern: bpy.props.IntProperty()

    def _execute(self, context):
        core.add_time_period(tool.Ifc, tool.Sequence, recurrence_pattern=tool.Ifc.get().by_id(self.recurrence_pattern))

class RemoveTimePeriod(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.remove_time_period"
    bl_label = "Remove Time Period"
    bl_options = {"REGISTER", "UNDO"}
    time_period: bpy.props.IntProperty()

    def _execute(self, context):
        core.remove_time_period(tool.Ifc, time_period=tool.Ifc.get().by_id(self.time_period))

class EnableEditingTaskCalendar(bpy.types.Operator):
    bl_idname = "bim.enable_editing_task_calendar"
    bl_label = "Enable Editing Task Calendar"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_task_calendar(tool.Sequence, task=tool.Ifc.get().by_id(self.task))
        return {"FINISHED"}

class DisableEditingTaskTime(bpy.types.Operator):
    bl_idname = "bim.disable_editing_task_time"
    bl_label = "Disable Editing Task Time"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.disable_editing_task_time(tool.Sequence)
        return {"FINISHED"}

class CalculateTaskDuration(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.calculate_task_duration"
    bl_label = "Calculate Task Duration"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        
        
        snapshot_all_ui_state(context)

        core.calculate_task_duration(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))


        restore_all_ui_state(context)

class ExpandAllTasks(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.expand_all_tasks"
    bl_label = "Expands All Tasks"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Finds the related Task"
    product_type: bpy.props.StringProperty()

    def _execute(self, context):
        
        

        snapshot_all_ui_state(context)

        core.expand_all_tasks(tool.Sequence)


        restore_all_ui_state(context)

class ContractAllTasks(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.contract_all_tasks"
    bl_label = "Expands All Tasks"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Finds the related Task"
    product_type: bpy.props.StringProperty()

    def _execute(self, context):
        
        

        snapshot_all_ui_state(context)

        core.contract_all_tasks(tool.Sequence)

        restore_all_ui_state(context)


class CopyTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.duplicate_task"
    bl_label = "Copy Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        
        

        snapshot_all_ui_state(context)

        core.duplicate_task(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))


        
        try:

            ws = tool.Sequence.get_active_work_schedule()

            if ws:

                tool.Sequence.load_task_tree(ws)

                tool.Sequence.load_task_properties()

        except Exception:

            pass

        restore_all_ui_state(context)

class GoToTask(bpy.types.Operator):
    bl_idname = "bim.go_to_task"
    bl_label = "Highlight Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        r = core.go_to_task(tool.Sequence, task=tool.Ifc.get().by_id(self.task))
        if isinstance(r, str):
            self.report({"WARNING"}, r)
        return {"FINISHED"}



class ReorderTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.reorder_task_nesting"
    bl_label = "Reorder Nesting"
    bl_options = {"REGISTER", "UNDO"}
    new_index: bpy.props.IntProperty()
    task: bpy.props.IntProperty()

    def _execute(self, context):
        
        

        snapshot_all_ui_state(context)

        r = core.reorder_task_nesting(

            tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task), new_index=self.new_index

        )

        if isinstance(r, str):

            self.report({"WARNING"}, r)


        
        try:

            ws = tool.Sequence.get_active_work_schedule()

            if ws:

                tool.Sequence.load_task_tree(ws)

                tool.Sequence.load_task_properties()

        except Exception:

            pass

        restore_all_ui_state(context)

class ClearPreviousAnimation(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.clear_previous_animation"
    bl_label = "Reset Animation"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        # CORRECCIÓN: Detener la animación si se está reproduciendo
        try:
            if bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel(restore_frame=False)
        except Exception as e:
            print(f"Could not stop animation: {e}")

        # CORRECCIÓN: Limpieza completa de la animación previa
        try:
            _clear_previous_animation(context)
            
            # Limpiar el grupo de perfil activo en HUD Legend
            try:
                anim_props = tool.Sequence.get_animation_props()
                if anim_props and hasattr(anim_props, 'camera_orbit'):
                    camera_props = anim_props.camera_orbit
                    
                    # Obtener todos los perfiles activos para ocultarlos
                    if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                        all_colortype_names = []
                        for group_item in anim_props.animation_group_stack:
                            group_name = group_item.group
                            from .prop import UnifiedColorTypeManager
                            group_colortypes = UnifiedColorTypeManager.get_group_colortypes(bpy.context, group_name)
                            if group_colortypes:
                                all_colortype_names.extend(group_colortypes.keys())
                        
                        # Ocultar todos los perfiles poniendo sus nombres en legend_hud_visible_colortypes
                        if all_colortype_names:
                            hidden_colortypes_str = ','.join(set(all_colortype_names))  # usar set() para eliminar duplicados
                            camera_props.legend_hud_visible_colortypes = hidden_colortypes_str
                            print(f"🧹 Hidden colortypes in HUD Legend: {hidden_colortypes_str}")
                    
                    # Limpiar selected_colortypes por si acaso
                    if hasattr(camera_props, 'legend_hud_selected_colortypes'):
                        camera_props.legend_hud_selected_colortypes = set()
                    
                    # Invalidar caché del legend HUD
                    from bonsai.bim.module.sequence.hud_overlay import invalidate_legend_hud_cache
                    invalidate_legend_hud_cache()
                    print("🧹 Active colortype group cleared from HUD Legend")
            except Exception as legend_e:
                print(f"⚠️ Could not clear colortype group: {legend_e}")
            
            self.report({'INFO'}, "Previous animation cleared.")
            context.scene.frame_set(context.scene.frame_start)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to clear previous animation: {e}")
            return {"CANCELLED"}

    # CORRECCIÓN: Este método 'execute' AHORA ESTÁ DENTRO de la clase.
    def execute(self, context):
        # Llama a su propia lógica de limpieza (_execute).
        return self._execute(context)


class ClearPreviousSnapshot(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.clear_previous_snapshot"
    bl_label = "Reset Snapshot"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        print(f"🔄 Reset animation started")
        
        # CORRECCIÓN: Detener la animación si se está reproduciendo
        try:
            if bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel(restore_frame=False)
                print(f"✅ Animation playback stopped")
        except Exception as e:
            print(f"❌ Could not stop animation: {e}")

        # CORRECCIÓN: Limpieza completa de snapshot previo
        try:
            # CRITICAL: Resetear todos los objetos a estado original (usar función existente)
            print(f"🔄 Clearing previous animation...")
            _clear_previous_animation(context)
            print(f"✅ Previous animation cleared")
            
            # Limpiar datos temporales de snapshot
            if hasattr(bpy.context.scene, 'snapshot_data'):
                del bpy.context.scene.snapshot_data
            
            # Limpiar el grupo de perfil activo en HUD Legend
            try:
                anim_props = tool.Sequence.get_animation_props()
                if anim_props and hasattr(anim_props, 'camera_orbit'):
                    camera_props = anim_props.camera_orbit
                    
                    # Obtener todos los perfiles activos para ocultarlos
                    if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                        all_colortype_names = []
                        for group_item in anim_props.animation_group_stack:
                            group_name = group_item.group
                            from .prop import UnifiedColorTypeManager
                            group_colortypes = UnifiedColorTypeManager.get_group_colortypes(bpy.context, group_name)
                            if group_colortypes:
                                all_colortype_names.extend(group_colortypes.keys())
                        
                        # Ocultar todos los perfiles poniendo sus nombres en legend_hud_visible_colortypes
                        if all_colortype_names:
                            hidden_colortypes_str = ','.join(set(all_colortype_names))  # usar set() para eliminar duplicados
                            camera_props.legend_hud_visible_colortypes = hidden_colortypes_str
                            print(f"🧹 Hidden colortypes in HUD Legend: {hidden_colortypes_str}")
                    
                    # Limpiar selected_colortypes por si acaso
                    if hasattr(camera_props, 'legend_hud_selected_colortypes'):
                        camera_props.legend_hud_selected_colortypes = set()
                    
                    # Invalidar caché del legend HUD
                    from bonsai.bim.module.sequence.hud_overlay import invalidate_legend_hud_cache
                    invalidate_legend_hud_cache()
                    print("🧹 Active colortype group cleared from HUD Legend")
            except Exception as legend_e:
                print(f"⚠️ Could not clear colortype group: {legend_e}")
            
            # --- SNAPSHOT 3D TEXTS RESTORATION ---
            # Clear snapshot mode and restore previous state
            if "is_snapshot_mode" in context.scene:
                del context.scene["is_snapshot_mode"]
                print("📸 Snapshot mode deactivated for 3D texts")
            _restore_3d_texts_state()
            
            self.report({'INFO'}, "Snapshot reset completed")
        except Exception as e:
            print(f"Error during snapshot reset: {e}")
            self.report({'WARNING'}, f"Snapshot reset completed with warnings: {e}")
        
        return {'FINISHED'}
    
    # CORRECCIÓN: Este método 'execute' AHORA ESTÁ DENTRO de la clase.
    def execute(self, context):
        # Llama a su propia lógica de limpieza (_execute).
        return self._execute(context)


# >>> INICIO DEL CÓDIGO A AÑADIR <<<
# ===================================================================
# (old helpers removed)


# >>> ELIMINA LOS HELPERS ANTERIORES Y PEGA ESTE BLOQUE COMPLETO <<<
# ===================================================================
# === MECANISMO CENTRALIZADO DE PERSISTENCIA DEL ESTADO DE LA UI ===
# ===================================================================

def snapshot_all_ui_state(context):
    """
    (SNAPSHOT) Captura el estado completo de la UI de perfiles y lo guarda
    en propiedades temporales de la escena. También mantiene un caché
    persistente para soportar alternancias de filtros (filtrar -> desfiltrar)
    sin perder datos de tareas ocultas.
    """
    import json
    try:
        # 1. Snapshot de la configuración de perfiles por tarea
        tprops = tool.Sequence.get_task_tree_props()
        task_snap = {}
        
        # NUEVO: También capturar datos de todas las tareas del cronograma activo 
        # para evitar pérdida de datos cuando se aplican/quitan filtros
        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                import ifcopenshell.util.sequence
                
                def get_all_tasks_recursive(tasks):
                    """Recursivamente obtiene todas las tareas y subtareas."""
                    all_tasks = []
                    for task in tasks:
                        all_tasks.append(task)
                        nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                        if nested:
                            all_tasks.extend(get_all_tasks_recursive(nested))
                    return all_tasks
                
                root_tasks = ifcopenshell.util.sequence.get_root_tasks(ws)
                all_tasks = get_all_tasks_recursive(root_tasks)
                
                # Crear snapshot de todas las tareas, no solo las visibles
                task_id_to_ui_data = {str(getattr(t, "ifc_definition_id", 0)): t for t in getattr(tprops, "tasks", [])}
                
                for task in all_tasks:
                    tid = str(task.id())
                    if tid == "0":
                        continue
                    
                    # Si la tarea está visible en la UI, usar sus datos actuales
                    if tid in task_id_to_ui_data:
                        t = task_id_to_ui_data[tid]
                        groups_list = []
                        for g in getattr(t, "colortype_group_choices", []):
                            sel_attr = None
                            for cand in ("selected_colortype", "selected", "active_colortype", "colortype"):
                                if hasattr(g, cand):
                                    sel_attr = cand
                                    break
                            groups_list.append({
                                "group_name": getattr(g, "group_name", ""),
                                "enabled": bool(getattr(g, "enabled", False)),
                                "selected_value": getattr(g, sel_attr, "") if sel_attr else "",
                                "selected_attr": sel_attr or "",
                            })
                        task_snap[tid] = {
                            "active": bool(getattr(t, "use_active_colortype_group", False)),
                            "selected_active_colortype": getattr(t, "selected_colortype_in_active_group", ""),
                            "animation_color_schemes": getattr(t, "animation_color_schemes", ""),
                            "groups": groups_list,
                        }
                    else:
                        # Si la tarea no está visible (filtrada), preservar datos del caché
                        cache_key = "_task_colortype_snapshot_cache_json"
                        cache_raw = context.scene.get(cache_key)
                        if cache_raw:
                            try:
                                cached_data = json.loads(cache_raw)
                                if tid in cached_data:
                                    task_snap[tid] = cached_data[tid]
                                else:
                                    # Crear entrada vacía para tareas sin datos previos
                                    task_snap[tid] = {
                                        "active": False,
                                        "selected_active_colortype": "",
                                        "animation_color_schemes": "",
                                        "groups": [],
                                    }
                            except Exception:
                                task_snap[tid] = {
                                    "active": False,
                                    "selected_active_colortype": "",
                                    "animation_color_schemes": "",
                                    "groups": [],
                                }
                        else:
                            task_snap[tid] = {
                                "active": False,
                                "selected_active_colortype": "",
                                "animation_color_schemes": "",
                                "groups": [],
                            }
        except Exception as e:
            print(f"Bonsai WARNING: Error capturando todas las tareas: {e}")
            # Fallback al método original solo con tareas visibles
            for t in getattr(tprops, "tasks", []):
                tid = str(getattr(t, "ifc_definition_id", 0))
                if tid == "0":
                    continue
                groups_list = []
                for g in getattr(t, "colortype_group_choices", []):
                    sel_attr = None
                    for cand in ("selected_colortype", "selected", "active_colortype", "colortype"):
                        if hasattr(g, cand):
                            sel_attr = cand
                            break
                    groups_list.append({
                        "group_name": getattr(g, "group_name", ""),
                        "enabled": bool(getattr(g, "enabled", False)),
                        "selected_value": getattr(g, sel_attr, "") if sel_attr else "",
                        "selected_attr": sel_attr or "",
                    })
                task_snap[tid] = {
                    "active": bool(getattr(t, "use_active_colortype_group", False)),
                    "selected_active_colortype": getattr(t, "selected_colortype_in_active_group", ""),
                    "animation_color_schemes": getattr(t, "animation_color_schemes", ""),
                    "groups": groups_list,
                }

        # Detectar el WorkSchedule activo para acotar el caché
        try:
            ws_props = tool.Sequence.get_work_schedule_props()
            ws_id = int(getattr(ws_props, "active_work_schedule_id", 0))
        except Exception:
            try:
                ws = tool.Sequence.get_active_work_schedule()
                ws_id = int(getattr(ws, "id", 0) or getattr(ws, "GlobalId", 0) or 0)
            except Exception:
                ws_id = 0

        # Resetear caché si cambió el WS activo
        cache_ws_key = "_task_colortype_snapshot_cache_ws_id"
        cache_key = "_task_colortype_snapshot_cache_json"
        prior_ws = context.scene.get(cache_ws_key)
        if prior_ws is None or int(prior_ws) != ws_id:
            context.scene[cache_key] = "{}"
            context.scene[cache_ws_key] = str(ws_id)

        # Guardar snapshot efímero (ciclo actual) - AMBAS CLAVES para compatibilidad
        snap_key_specific = f"_task_colortype_snapshot_json_WS_{ws_id}"
        snap_key_generic = "_task_colortype_snapshot_json"
        
        # Guardar en clave específica (para Copy 3D)
        context.scene[snap_key_specific] = json.dumps(task_snap)
        print(f"💾 DEBUG SNAPSHOT: Guardado en clave {snap_key_specific} - {len(task_snap)} tareas")
        
        # TAMBIÉN guardar en clave genérica (para sistema normal)
        context.scene[snap_key_generic] = json.dumps(task_snap)

        # Actualizar caché persistente (merge)
        merged = {}
        cache_raw = context.scene.get(cache_key)
        if cache_raw:
            try:
                merged = json.loads(cache_raw) or {}
            except Exception:
                merged = {}
        merged.update(task_snap)
        context.scene[cache_key] = json.dumps(merged)

        # 2. Snapshot de los selectores de grupo y el stack de animación
        anim_props = tool.Sequence.get_animation_props()
        anim_snap = {
            "ColorType_groups": getattr(anim_props, "ColorType_groups", "DEFAULT"),
            "task_colortype_group_selector": getattr(anim_props, "task_colortype_group_selector", ""),
            "animation_group_stack": [
                {"group": getattr(item, "group", ""), "enabled": bool(getattr(item, "enabled", False))}
                for item in getattr(anim_props, "animation_group_stack", [])
            ],
        }
        context.scene["_anim_state_snapshot_json"] = json.dumps(anim_snap)
        # 3. Snapshot de selección/índice activo del árbol de tareas
        try:
            wprops = tool.Sequence.get_work_schedule_props()
            tprops = tool.Sequence.get_task_tree_props()
            active_idx = int(getattr(wprops, 'active_task_index', -1))
            active_id = int(getattr(wprops, 'active_task_id', 0))
            selected_ids = []
            for t in getattr(tprops, 'tasks', []):
                tid = int(getattr(t, 'ifc_definition_id', 0))
                sel = False
                for cand in ('is_selected','selected'):
                    if hasattr(t, cand) and bool(getattr(t, cand)):
                        sel = True
                        break
                if sel:
                    selected_ids.append(tid)
            sel_snap = {'active_index': active_idx, 'active_id': active_id, 'selected_ids': selected_ids}
            context.scene['_task_selection_snapshot_json'] = json.dumps(sel_snap)
        except Exception:
            pass


    except Exception as e:
        print(f"Bonsai WARNING: No se pudo crear el snapshot de la UI: {e}")

def restore_animation_group_settings(context):
    """Restore only animation group stack and selectors, not individual task colortype assignments"""
    import json
    try:
        # Restore animation group settings from snapshot
        anim_snap_raw = context.scene.get("_anim_state_snapshot_json")
        if anim_snap_raw:
            try:
                anim_snap = json.loads(anim_snap_raw) or {}
                anim_props = tool.Sequence.get_animation_props()
                
                # Restore group selectors
                try:
                    anim_props.ColorType_groups = anim_snap.get("ColorType_groups", "DEFAULT")
                    anim_props.task_colortype_group_selector = anim_snap.get("task_colortype_group_selector", "")
                except Exception as e:
                    print(f"Warning: Could not restore group selectors: {e}")
                
                # Restore animation group stack
                try:
                    anim_props.animation_group_stack.clear()
                    for item_data in anim_snap.get("animation_group_stack", []):
                        item = anim_props.animation_group_stack.add()
                        item.group = item_data.get("group", "")
                        if hasattr(item, "enabled"):
                            item.enabled = bool(item_data.get("enabled", False))
                    print(f"[DEBUG] Restored {len(anim_snap.get('animation_group_stack', []))} animation group stack items")
                except Exception as e:
                    print(f"Warning: Could not restore animation group stack: {e}")
                    
            except Exception as e:
                print(f"Warning: Could not parse animation snapshot: {e}")
    except Exception as e:
        print(f"Error in restore_animation_group_settings: {e}")

def restore_all_ui_state(context):
    """
    (RESTAURACIÓN) Restaura el estado completo de la UI de perfiles desde
    las propiedades temporales de la escena. Usa un caché persistente para
    cubrir tareas que no estaban visibles en el snapshot efímero (p.ej. al
    desactivar filtros).
    """
    import json
    try:
        # Detectar cronograma activo para usar claves específicas
        try:
            ws_props = tool.Sequence.get_work_schedule_props()
            ws_id = int(getattr(ws_props, "active_work_schedule_id", 0))
        except Exception:
            try:
                ws = tool.Sequence.get_active_work_schedule()
                ws_id = int(getattr(ws, "id", 0) or getattr(ws, "GlobalId", 0) or 0)
            except Exception:
                ws_id = 0
                
        # 1. Restaurar configuración de perfiles en las tareas - ESPECÍFICO POR CRONOGRAMA
        snap_key_specific = f"_task_colortype_snapshot_json_WS_{ws_id}"
        cache_key = "_task_colortype_snapshot_cache_json"

        # Union: cache ∪ snapshot (snapshot tiene prioridad)
        union = {}
        cache_raw = context.scene.get(cache_key)
        if cache_raw:
            try:
                union.update(json.loads(cache_raw) or {})
            except Exception:
                pass
        snap_raw = context.scene.get(snap_key_specific)
        if snap_raw:
            try:
                snap_data = json.loads(snap_raw) or {}
                union.update(snap_data)
                print(f"📥 DEBUG RESTORE: Cargando de clave {snap_key_specific} - {len(snap_data)} tareas")
            except Exception:
                pass
        else:
            print(f"❌ DEBUG RESTORE: No se encontró clave {snap_key_specific}")

        if union:
            tprops = tool.Sequence.get_task_tree_props()
            task_map = {str(getattr(t, "ifc_definition_id", 0)): t for t in getattr(tprops, "tasks", [])}

            for tid, cfg in union.items():
                t = task_map.get(str(tid))
                if not t:
                    continue
                # Estado principal de la tarea
                try:
                    t.use_active_colortype_group = cfg.get("active", False)
                    
                    # VALIDACIÓN AGRESIVA: Evitar valores problemáticos en selected_colortype_in_active_group
                    selected_active_colortype = cfg.get("selected_active_colortype", "")
                    problematic_values = ["0", 0, None, "", "None", "null", "undefined"]
                    
                    if selected_active_colortype in problematic_values:
                        selected_active_colortype = ""
                    else:
                        # Validación adicional para strings problemáticos
                        selected_active_str = str(selected_active_colortype).strip()
                        if selected_active_str in [str(v) for v in problematic_values]:
                            selected_active_colortype = ""
                    
                    prop.safe_set_selected_colortype_in_active_group(t, selected_active_colortype, skip_validation=True)
                    
                    # RESTAURAR CAMPO PRINCIPAL animation_color_schemes
                    animation_color_schemes = cfg.get("animation_color_schemes", "")
                    task_is_active = cfg.get("active", False)
                    
                    # Si la tarea NO tiene grupo activo, usar el valor capturado de animation_color_schemes
                    if not task_is_active and animation_color_schemes:
                        print(f"🎨 DEBUG RESTORE: Task {tid} - Setting animation_color_schemes from snapshot: '{animation_color_schemes}'")
                        prop.safe_set_animation_color_schemes(t, animation_color_schemes)
                    elif not task_is_active:
                        print(f"🎨 DEBUG RESTORE: Task {tid} - No animation_color_schemes value, using fallback")
                        prop.safe_set_animation_color_schemes(t, "")
                    else:
                        # Si la tarea SÍ tiene grupo activo, sincronizar animation_color_schemes con el valor del grupo
                        if selected_active_colortype:
                            print(f"🔄 DEBUG RESTORE: Task {tid} - Syncing animation_color_schemes with active group value: '{selected_active_colortype}'")
                            prop.safe_set_animation_color_schemes(t, selected_active_colortype)
                        else:
                            print(f"🔄 DEBUG RESTORE: Task {tid} - Has active group but no selected colortype, using snapshot value: '{animation_color_schemes}'")
                            prop.safe_set_animation_color_schemes(t, animation_color_schemes)
                    
                    print(f"🔧 DEBUG RESTORE: Task {tid} - active={cfg.get('active')}, selected_colortype='{selected_active_colortype}'")
                except Exception as e:
                    print(f"❌ DEBUG RESTORE: Error setting colortype for task {tid}: {e}")
                # Grupos de la tarea
                try:
                    t.colortype_group_choices.clear()
                    for g_data in cfg.get("groups", []):
                        item = t.colortype_group_choices.add()
                        item.group_name = g_data.get("group_name", "")
                        # Detectar atributo de selección del item en tiempo de ejecución
                        sel_attr = None
                        for cand in ("selected_colortype", "selected", "active_colortype", "colortype"):
                            if hasattr(item, cand):
                                sel_attr = cand
                                break
                        if hasattr(item, "enabled"):
                            item.enabled = bool(g_data.get("enabled", False))
                        # Escribir el valor usando el atributo correcto
                        val = g_data.get("selected_value", "")
                        
                        # VALIDACIÓN CONSERVADORA: Solo evitar valores claramente problemáticos
                        # pero preservar ColorTypes válidos como 'Color Type 1', 'Color Type 2', etc.
                        truly_problematic_values = ["0", 0, None, "None", "null", "undefined"]
                        if val in truly_problematic_values:
                            val = ""
                        elif val == "":
                            # String vacío es válido (significa sin selección)
                            pass
                        else:
                            # Preservar todos los demás valores como strings válidos
                            val = str(val).strip() if val else ""
                        
                        if sel_attr and val is not None:
                            try:
                                # DEBUGGING DETALLADO: Mostrar exactamente qué se está intentando asignar
                                print(f"🔍 DEEP DEBUG RESTORE: Task {tid} group '{g_data.get('group_name')}'")
                                print(f"  - Raw selected_value from data: '{g_data.get('selected_value', 'NOT_FOUND')}'")
                                print(f"  - Cleaned val: '{val}' (type: {type(val)})")
                                print(f"  - Target attribute: {sel_attr}")
                                print(f"  - Item has attribute {sel_attr}: {hasattr(item, sel_attr)}")
                                
                                # Verificar qué tipo de enum/items espera el atributo
                                if hasattr(item, sel_attr):
                                    prop_def = getattr(type(item), sel_attr, None)
                                    if hasattr(prop_def, 'keywords') and 'items' in prop_def.keywords:
                                        print(f"  - Attribute {sel_attr} expects items function")
                                    
                                # Intentar la asignación
                                setattr(item, sel_attr, val)
                                
                                # Verificar qué se asignó realmente
                                actual_val = getattr(item, sel_attr, 'FAILED_TO_READ')
                                print(f"  - Successfully set {sel_attr}='{val}'")
                                print(f"  - Actual value after assignment: '{actual_val}'")
                                print(f"  - Assignment successful: {val == actual_val}")
                                
                            except Exception as e:
                                print(f"❌ DEBUG RESTORE: Error setting {sel_attr} for task {tid} group {g_data.get('group_name')}: {e}")
                                print(f"  - Failed value: '{val}' (type: {type(val)})")
                                print(f"  - Error type: {type(e).__name__}")
                                
                                # Si falla con el valor, intentar con string vacío
                                try:
                                    setattr(item, sel_attr, "")
                                    print(f"  - Fallback to empty string successful")
                                except Exception as fallback_e:
                                    print(f"  - Even fallback failed: {fallback_e}")
                                    pass
                except Exception:
                    pass

        
        # Aplicar snapshot de selección/índice activo
        try:
            import json as _json
            sel_raw = context.scene.get('_task_selection_snapshot_json')
            if sel_raw:
                sel = _json.loads(sel_raw)
                wprops = tool.Sequence.get_work_schedule_props()
                tprops = tool.Sequence.get_task_tree_props()
                # Mapear por ID primero para robustez
                id_to_index = {}
                for idx, t in enumerate(getattr(tprops, 'tasks', [])):
                    id_to_index[int(getattr(t, 'ifc_definition_id', 0))] = idx
                # Restaurar active_task_index preferentemente por ID
                aidx = sel.get('active_index', -1)
                aid = sel.get('active_id', 0)
                if aid and aid in id_to_index:
                    wprops.active_task_index = id_to_index[aid]
                elif isinstance(aidx, int) and 0 <= aidx < len(getattr(tprops, 'tasks', [])):
                    wprops.active_task_index = aidx
                # Restaurar selección múltiple
                sel_ids = set(int(x) for x in sel.get('selected_ids', []) if isinstance(x, (int, str)))
                for t in getattr(tprops, 'tasks', []):
                    tid = int(getattr(t, 'ifc_definition_id', 0))
                    for cand in ('is_selected','selected'):
                        if hasattr(t, cand):
                            setattr(t, cand, tid in sel_ids)
                            break
        except Exception:
            pass

        # 4. Restaurar atributos de la tarea activa (si se estaba editando)
        try:
            if '_task_attributes_snapshot_json' in context.scene:
                wprops = tool.Sequence.get_work_schedule_props()
                # Solo restaurar si seguimos editando la misma tarea
                if wprops and wprops.active_task_id and wprops.editing_task_type == "ATTRIBUTES":
                    
                    import json
                    attributes_snapshot = json.loads(context.scene['_task_attributes_snapshot_json'])
                    
                    # Aplicar los valores guardados a la colección de atributos actual
                    for attr in wprops.task_attributes:
                        if attr.name in attributes_snapshot and hasattr(attr, 'set_value'):
                            attr.set_value(attributes_snapshot[attr.name])

                # Limpiar el snapshot después de usarlo
                del context.scene['_task_attributes_snapshot_json']
        except Exception:
            pass
# 2. Restaurar selectores de grupo y stack de animación (efímero basta)
        anim_snap_raw = context.scene.get("_anim_state_snapshot_json")
        if anim_snap_raw:
            try:
                anim_snap = json.loads(anim_snap_raw) or {}
                anim_props = tool.Sequence.get_animation_props()
                try:
                    anim_props.ColorType_groups = anim_snap.get("ColorType_groups", "DEFAULT")
                    anim_props.task_colortype_group_selector = anim_snap.get("task_colortype_group_selector", "")
                except Exception:
                    pass
                try:
                    anim_props.animation_group_stack.clear()
                    for item_data in anim_snap.get("animation_group_stack", []):
                        item = anim_props.animation_group_stack.add()
                        item.group = item_data.get("group", "")
                        if hasattr(item, "enabled"):
                            item.enabled = bool(item_data.get("enabled", False))
                except Exception:
                    pass
            except Exception:
                pass

        # Sincronizar el grupo activo con el backend JSON tras restaurar
        try:
            tool.Sequence.sync_active_group_to_json()
        except Exception:
            pass

    except Exception as e:
        print(f"Bonsai WARNING: No se pudo restaurar el estado de la UI: {e}")
    finally:
        try:
            if '_task_selection_snapshot_json' in context.scene:
                del context.scene['_task_selection_snapshot_json']
        except Exception:
            pass

        # Limpiar snapshots efímeros; conservamos el caché para el ciclo de ida/vuelta de filtros
        try:
            # --- CORRECCIÓN: Limpiar SOLO el snapshot del cronograma actual ---
            # Esto evita que se borre el snapshot del cronograma anterior
            # antes de que se pueda usar al volver a cambiar.
            ws_props = tool.Sequence.get_work_schedule_props()
            ws_id = int(getattr(ws_props, "active_work_schedule_id", 0))
            if ws_id != 0:
                snap_key_specific = f"_task_colortype_snapshot_json_WS_{ws_id}"
                if snap_key_specific in context.scene:
                    del context.scene[snap_key_specific]
            # Limpiar también la clave genérica antigua por si acaso
            if "_task_colortype_snapshot_json" in context.scene:
                del context.scene["_task_colortype_snapshot_json"]
        except Exception:
            pass
        try:
            if "_anim_state_snapshot_json" in context.scene:
                del context.scene["_anim_state_snapshot_json"]
        except Exception:
            pass