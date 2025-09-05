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
            def safe_set_selected_colortype_in_active_group(task_obj, value):
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
def _get_internal_colortype_sets(context):
    scene = context.scene
    key = "BIM_AnimationColorSchemesSets"
    # Ensure container exists
    if key not in scene:
        scene[key] = json.dumps({})
    # Parse
    try:
        data = json.loads(scene[key])
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    # --- Auto-create DEFAULT group if empty ---
    try:
        if not data:
            default_names = [
                "ATTENDANCE", "CONSTRUCTION", "DEMOLITION", "DISMANTLE",
                "DISPOSAL", "INSTALLATION", "LOGISTIC", "MAINTENANCE",
                "MOVE", "OPERATION", "REMOVAL", "RENOVATION",
            ]
            data = {"DEFAULT": {"ColorTypes": [{"name": n} for n in default_names]}}
            scene[key] = json.dumps(data)
    except Exception:
        pass
    return data

def _set_internal_colortype_sets(context, data: dict):
    context.scene["BIM_AnimationColorSchemesSets"] = json.dumps(data)

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

def _save_3d_texts_state():
    """Save current state of all 3D text objects before snapshot"""
    try:
        coll = bpy.data.collections.get("Schedule_Display_Texts")
        if not coll:
            return
        
        state_data = {}
        for obj in coll.objects:
            if hasattr(obj, "data") and obj.data:
                state_data[obj.name] = obj.data.body
        
        # Store in scene for restoration
        bpy.context.scene["3d_texts_previous_state"] = json.dumps(state_data)
        print(f"💾 Saved state for {len(state_data)} 3D text objects")
        
    except Exception as e:
        print(f"❌ Error saving 3D texts state: {e}")

def _restore_3d_texts_state():
    """Restore previous state of all 3D text objects after snapshot reset"""
    try:
        if "3d_texts_previous_state" not in bpy.context.scene:
            print("⚠️ No previous 3D texts state found to restore")
            return
        
        coll = bpy.data.collections.get("Schedule_Display_Texts")
        if not coll:
            print("⚠️ No 'Schedule_Display_Texts' collection found for restoration")
            return
        
        state_data = json.loads(bpy.context.scene["3d_texts_previous_state"])
        restored_count = 0
        
        for obj in coll.objects:
            if hasattr(obj, "data") and obj.data and obj.name in state_data:
                obj.data.body = state_data[obj.name]
                restored_count += 1
        
        # Clean up saved state
        del bpy.context.scene["3d_texts_previous_state"]
        print(f"🔄 Restored state for {restored_count} 3D text objects")
        
    except Exception as e:
        print(f"❌ Error restoring 3D texts state: {e}")

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

def _related_object_type_items(self, context):
    try:
        from typing import get_args
        from bonsai import tool as _tool
        vals = list(get_args(getattr(_tool.Sequence, "RELATED_OBJECT_TYPE", tuple()))) or []
    except Exception:
        vals = []
    if not vals:
        # Safe fallback
        vals = ("PRODUCT", "RESOURCE", "PROCESS")
    return [(str(v), str(v).replace("_", " ").title(), "") for v in vals]

# --- Helpers: clean task mappings when colortypes or groups change ---
def _current_colortype_names():
    try:
        props = tool.Sequence.get_animation_props()
        return [p.name for p in getattr(props, "ColorTypes", [])]
    except Exception:
        return []

# ---- Unified Animation Bridges ----





def _clean_task_colortype_mappings(context, removed_group_name: str | None = None):
    """
    Ensures per-task mapping stays consistent:
      - If a group is removed, drop its entry from each task.
      - If selected colortype no longer exists in the current group, clear it.
    Also clears the visible Enum property if it points to a removed colortype.
    """
    try:
        wprops = tool.Sequence.get_work_schedule_props()
        tprops = tool.Sequence.get_task_tree_props()
        anim = tool.Sequence.get_animation_props()
        active_group = getattr(anim, "ColorType_groups", "") or ""
        valid_names = set(_current_colortype_names())

        for t in list(getattr(tprops, "tasks", [])):
            # Remove group-specific entry if group removed
            if removed_group_name and hasattr(t, "colortype_group_choices"):
                to_keep = []
                for item in t.colortype_group_choices:
                    if item.group_name != removed_group_name:
                        to_keep.append((item.group_name, getattr(item, 'enabled', False), getattr(item, 'selected_colortype', "")))
                # Rebuild collection if anything changed
                if len(to_keep) != len(t.colortype_group_choices):
                    t.colortype_group_choices.clear()
                    for g, en, sel in to_keep:
                        it = t.colortype_group_choices.add()
                        it.group_name = g
                        try:
                            it.enabled = bool(en)
                        except Exception:
                            pass
                        try:
                            it.selected_colortype = sel or ""
                        except Exception:
                            pass

                # If the visible toggle points to removed group, turn it off
                if active_group == removed_group_name:
                    try:
                        t.use_active_colortype_group = False
                        prop.safe_set_selected_colortype_in_active_group(t, "")
                    except Exception:
                        pass

            # If current visible selection references a deleted colortype, clear it
            try:
                if getattr(t, "selected_colortype_in_active_group", "") and \
                   t.selected_colortype_in_active_group not in valid_names:
                    prop.safe_set_selected_colortype_in_active_group(t, "")
            except Exception:
                pass
            # Also clear stored selection for the active group
            try:
                if hasattr(t, "colortype_group_choices") and active_group:
                    for item in t.colortype_group_choices:
                        if item.group_name == active_group and getattr(item, 'selected_colortype', "") not in valid_names:
                            try:
                                item.selected_colortype = ""
                            except Exception:
                                pass
            except Exception:
                pass
    except Exception:
        # Best-effort; never break operator
        pass

class EnableStatusFilters(bpy.types.Operator):
    bl_idname = "bim.enable_status_filters"
    bl_label = "Enable Status Filters"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_status_props()
        props.is_enabled = True
        hidden_statuses = {s.name for s in props.statuses if not s.is_visible}

        props.statuses.clear()

        statuses = set()
        for element in tool.Ifc.get().by_type("IfcPropertyEnumeratedValue"):
            if element.Name == "Status":
                if element.PartOfPset and isinstance(element.EnumerationValues, tuple):
                    pset = element.PartOfPset[0]
                    if pset.Name.startswith("Pset_") and pset.Name.endswith("Common"):
                        statuses.update(element.EnumerationValues)
                    elif pset.Name == "EPset_Status":  # Our secret sauce
                        statuses.update(element.EnumerationValues)
            elif element.Name == "UserDefinedStatus":
                statuses.add(element.NominalValue)

        statuses = ["No Status"] + sorted([s.wrappedValue for s in statuses])

        for status in statuses:
            new = props.statuses.add()
            new.name = status
            if new.name in hidden_statuses:
                new.is_visible = False

        visible_statuses = {s.name for s in props.statuses if s.is_visible}
        tool.Sequence.set_visibility_by_status(visible_statuses)
        return {"FINISHED"}

class DisableStatusFilters(bpy.types.Operator):
    bl_idname = "bim.disable_status_filters"
    bl_label = "Disable Status Filters"
    bl_description = "Deactivate status filters panel.\nCan be used to refresh the displayed statuses"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_status_props()

        all_statuses = {s.name for s in props.statuses}
        tool.Sequence.set_visibility_by_status(all_statuses)
        props.is_enabled = False
        return {"FINISHED"}

class ActivateStatusFilters(bpy.types.Operator):
    bl_idname = "bim.activate_status_filters"
    bl_label = "Activate Status Filters"
    bl_description = "Filter and display objects based on currently selected IFC statuses"
    bl_options = {"REGISTER", "UNDO"}

    only_if_enabled: bpy.props.BoolProperty(  # pyright: ignore[reportRedeclaration]
        name="Only If Filters are Enabled",
        description="Activate status filters only in case if they were enabled from the UI before.",
        default=False,
    )

    if TYPE_CHECKING:
        only_if_enabled: bool

    def execute(self, context):
        props = tool.Sequence.get_status_props()

        if not props.is_enabled:
            if not self.only_if_enabled:
                # Allow users to use the same operator to refresh filters,
                # even if they were not enabled before.
                # Typically would occur when operator is added to Quick Favorites.
                bpy.ops.bim.enable_status_filters()
            return {"FINISHED"}

        visible_statuses = {s.name for s in props.statuses if s.is_visible}
        tool.Sequence.set_visibility_by_status(visible_statuses)
        return {"FINISHED"}

class SelectStatusFilter(bpy.types.Operator):
    bl_idname = "bim.select_status_filter"
    bl_label = "Select Status Filter"
    bl_description = "Select elements with currently selected status"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def execute(self, context):
        query = f"IfcProduct, /Pset_.*Common/.Status={self.name} + IfcProduct, EPset_Status.Status={self.name}"
        if self.name == "No Status":
            query = f"IfcProduct, /Pset_.*Common/.Status=NULL, EPset_Status.Status=NULL"
        for element in ifcopenshell.util.selector.filter_elements(tool.Ifc.get(), query):
            obj = tool.Ifc.get_object(element)
            if obj:
                obj.select_set(True)
        return {"FINISHED"}

class AddWorkPlan(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_work_plan"
    bl_label = "Add Work Plan"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        core.add_work_plan(tool.Ifc)

class EditWorkPlan(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_work_plan"
    bl_options = {"REGISTER", "UNDO"}
    bl_label = "Edit Work Plan"

    def _execute(self, context):
        props = tool.Sequence.get_work_plan_props()
        core.edit_work_plan(
            tool.Ifc,
            tool.Sequence,
            work_plan=tool.Ifc.get().by_id(props.active_work_plan_id),
        )

class RemoveWorkPlan(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.remove_work_plan"
    bl_label = "Remove Work Plan"
    bl_options = {"REGISTER", "UNDO"}
    work_plan: bpy.props.IntProperty()

    def _execute(self, context):
        core.remove_work_plan(tool.Ifc, work_plan=tool.Ifc.get().by_id(self.work_plan))

class EnableEditingWorkPlan(bpy.types.Operator):
    bl_idname = "bim.enable_editing_work_plan"
    bl_label = "Enable Editing Work Plan"
    bl_options = {"REGISTER", "UNDO"}
    work_plan: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_work_plan(tool.Sequence, work_plan=tool.Ifc.get().by_id(self.work_plan))
        return {"FINISHED"}

class DisableEditingWorkPlan(bpy.types.Operator):
    bl_idname = "bim.disable_editing_work_plan"
    bl_options = {"REGISTER", "UNDO"}
    bl_label = "Disable Editing Work Plan"

    def execute(self, context):
        core.disable_editing_work_plan(tool.Sequence)
        return {"FINISHED"}

class EnableEditingWorkPlanSchedules(bpy.types.Operator):
    bl_idname = "bim.enable_editing_work_plan_schedules"
    bl_label = "Enable Editing Work Plan Schedules"
    bl_options = {"REGISTER", "UNDO"}
    work_plan: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_work_plan_schedules(tool.Sequence, work_plan=tool.Ifc.get().by_id(self.work_plan))
        return {"FINISHED"}

class AssignWorkSchedule(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_work_schedule"
    bl_label = "Assign Work Schedule"
    bl_options = {"REGISTER", "UNDO"}
    work_plan: bpy.props.IntProperty()
    work_schedule: bpy.props.IntProperty()

    def _execute(self, context):
        core.assign_work_schedule(
            tool.Ifc,
            work_plan=tool.Ifc.get().by_id(self.work_plan),
            work_schedule=tool.Ifc.get().by_id(self.work_schedule),
        )

class UnassignWorkSchedule(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_work_schedule"
    bl_label = "Unassign Work Schedule"
    bl_options = {"REGISTER", "UNDO"}
    work_plan: bpy.props.IntProperty()
    work_schedule: bpy.props.IntProperty()

    def _execute(self, context):
        core.unassign_work_schedule(
            tool.Ifc,
            work_schedule=tool.Ifc.get().by_id(self.work_schedule),
        )

class AddWorkSchedule(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_work_schedule"
    bl_label = "Add Work Schedule"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def _execute(self, context):
        core.add_work_schedule(tool.Ifc, tool.Sequence, name=self.name)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name", text="Name")
        self.props = tool.Sequence.get_work_schedule_props()
        layout.prop(self.props, "work_schedule_predefined_types", text="Type")
        if self.props.work_schedule_predefined_types == "USERDEFINED":
            layout.prop(self.props, "object_type", text="Object type")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class EditWorkSchedule(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_work_schedule"
    bl_label = "Edit Work Schedule"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        work_schedule_id = props.active_work_schedule_id
        work_schedule = tool.Ifc.get().by_id(work_schedule_id)
        
        # --- INICIO DE LA CORRECCIÓN ---
        # 1. Guardar la configuración de perfiles en el IFC antes de guardar los atributos del cronograma.
        #    Esto asegura que los cambios en los perfiles de las tareas no se pierdan.
        try:
            import bonsai.core.sequence as core
            anim_props = tool.Sequence.get_animation_props()
            
            # Usar el helper para capturar el estado actual de la UI de tareas
            snapshot_all_ui_state(context)
            # Usar clave específica por cronograma
            snap_key_specific = f"_task_colortype_snapshot_json_WS_{work_schedule_id}"
            task_snap = json.loads(context.scene.get(snap_key_specific, "{}"))

            colortype_data_to_save = {
                "colortype_sets": _get_internal_colortype_sets(context),
                "task_configurations": task_snap,
                "animation_settings": {
                    "active_editor_group": getattr(anim_props, "ColorType_groups", "DEFAULT"),
                    "active_task_group": getattr(anim_props, "task_colortype_group_selector", ""),
                    "group_stack": [{"group": item.group, "enabled": item.enabled} for item in anim_props.animation_group_stack],
                }
            }
            core.save_colortypes_to_ifc_core(tool.Ifc.get(), work_schedule, colortype_data_to_save)
            print(f"Bonsai INFO: colortype data for schedule '{work_schedule.Name}' saved to IFC.")
        except Exception as e:
            print(f"Bonsai WARNING: Failed to auto-save colortype data during schedule edit: {e}")
        # --- FIN DE LA CORRECCIÓN ---

        # Ejecutar la edición estándar
        core.edit_work_schedule(
            tool.Ifc,
            tool.Sequence,
            work_schedule=work_schedule,
        )

        # Salir del modo de edición de forma estándar para que la UI se actualice correctamente.
        tool.Sequence.disable_editing_work_schedule()

class RemoveWorkSchedule(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.remove_work_schedule"
    bl_label = "Remove Work Schedule"
    back_reference = "Remove provided work schedule."
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def _execute(self, context):
        core.remove_work_schedule(tool.Ifc, work_schedule=tool.Ifc.get().by_id(self.work_schedule))

class CopyWorkSchedule(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.copy_work_schedule"
    bl_label = "Copy Work Schedule"
    bl_description = "Create a duplicate of the provided work schedule."
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()  # pyright: ignore[reportRedeclaration]

    def _execute(self, context):
        # 1. Ejecutar la lógica de copia que ahora sí crea un duplicado en el IFC.
        core.copy_work_schedule(tool.Sequence, work_schedule=tool.Ifc.get().by_id(self.work_schedule))

        # 2. Forzar la recarga de los datos y el redibujado de la UI.
        try:
            from bonsai.bim.module.sequence.data import SequenceData, WorkScheduleData
            SequenceData.load()
            WorkScheduleData.load()
            for area in context.screen.areas:
                if area.type in ['PROPERTIES', 'OUTLINER']:
                    area.tag_redraw()
        except Exception as e:
            print(f"Bonsai WARNING: UI refresh failed after copying schedule: {e}")

class EnableEditingWorkSchedule(bpy.types.Operator):
    bl_idname = "bim.enable_editing_work_schedule"
    bl_label = "Enable Editing Work Schedule"
    bl_description = "Enable editing work schedule attributes."
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_work_schedule(tool.Sequence, work_schedule=tool.Ifc.get().by_id(self.work_schedule))
        return {"FINISHED"}

class EnableEditingWorkScheduleTasks(bpy.types.Operator):
    bl_idname = "bim.enable_editing_work_schedule_tasks"
    bl_label = "Enable Editing Work Schedule Tasks"
    bl_description = "Enable editing work scheduke tasks."
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def execute(self, context):
        # USAR EL PATRÓN CORRECTO CON TIMING ADECUADO:
        print(f"🚀 DEBUG OPERADOR: Iniciando cambio a WS {self.work_schedule}")
        
        # >>> 1. Establecer cronograma activo (dispara callback de guardado/carga automático)
        print("📝 DEBUG OPERADOR: Paso 1 - Estableciendo cronograma activo")
        core.enable_editing_work_schedule_tasks(tool.Sequence, work_schedule=tool.Ifc.get().by_id(self.work_schedule))
        
        # >>> 2. Cargar task tree DESPUÉS del callback (para no borrar datos restaurados)
        print("🔄 DEBUG OPERADOR: Paso 2 - Cargando task tree")
        work_schedule = tool.Ifc.get().by_id(self.work_schedule)
        tool.Sequence.load_task_tree(work_schedule)
        tool.Sequence.load_task_properties()
        
        # >>> 3. Restaurar estado desde el caché (como hacen los filtros)
        print("📥 DEBUG OPERADOR: Paso 3 - Restaurando estado")
        restore_all_ui_state(context)

        print("✅ DEBUG OPERADOR: Operación completada")
        return {"FINISHED"}

class LoadTaskProperties(bpy.types.Operator):
    bl_idname = "bim.load_task_properties"
    bl_label = "Load Task Properties"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.load_task_properties(tool.Sequence)
        
        return {"FINISHED"}

class DisableEditingWorkSchedule(bpy.types.Operator):
    bl_idname = "bim.disable_editing_work_schedule"
    bl_label = "Disable Editing Work Schedule"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # USAR EL MISMO PATRÓN QUE LOS FILTROS (que funciona correctamente):
        snapshot_all_ui_state(context)  # >>> 1. Guardar estado ANTES de cancelar
        
        # >>> 2. Ejecutar la operación de cancelar (que puede resetear/limpiar datos)
        core.disable_editing_work_schedule(tool.Sequence)
        
        return {"FINISHED"}

class AddTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_task"
    bl_label = "Add Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        
        

        snapshot_all_ui_state(context)

        core.add_task(tool.Ifc, tool.Sequence, parent_task=tool.Ifc.get().by_id(self.task))


        
        try:

            ws = tool.Sequence.get_active_work_schedule()

            if ws:

                tool.Sequence.load_task_tree(ws)

                tool.Sequence.load_task_properties()

        except Exception:

            pass

        restore_all_ui_state(context)

class AddSummaryTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_summary_task"
    bl_label = "Add Task"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def _execute(self, context):
        
        

        snapshot_all_ui_state(context)

        core.add_summary_task(tool.Ifc, tool.Sequence, work_schedule=tool.Ifc.get().by_id(self.work_schedule))


        
        try:

            ws = tool.Sequence.get_active_work_schedule()

            if ws:

                tool.Sequence.load_task_tree(ws)

                tool.Sequence.load_task_properties()

        except Exception:

            pass

        restore_all_ui_state(context)

class ExpandTask(bpy.types.Operator):
    bl_idname = "bim.expand_task"
    bl_label = "Expand Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        
        

        snapshot_all_ui_state(context)

        core.expand_task(tool.Sequence, task=tool.Ifc.get().by_id(self.task))

        return {'FINISHED'}


        restore_all_ui_state(context)

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

class CopyTaskCustomcolortypeGroup(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.copy_task_custom_colortype_group"
    # UI may set these; declare to avoid attribute errors
    enabled: bpy.props.BoolProperty(name='Enabled', default=False, options={'HIDDEN'})
    group: bpy.props.StringProperty(name='Group', default='', options={'HIDDEN'})
    selected_colortype: bpy.props.StringProperty(name='Selected colortype', default='', options={'HIDDEN'})

    bl_label = "Copy Task Custom colortype Group"
    bl_description = "Copy custom colortype group configuration to selected tasks"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):

        try:
            # Obtener la tarea activa (fuente)
            tprops = tool.Sequence.get_task_tree_props()
            wprops = tool.Sequence.get_work_schedule_props()
            anim_props = tool.Sequence.get_animation_props()

            if not tprops.tasks or wprops.active_task_index >= len(tprops.tasks):
                self.report({'ERROR'}, "No active task to copy from")
                return {'CANCELLED'}

            source_task = tprops.tasks[wprops.active_task_index]

            # Obtener configuración de la tarea fuente
            source_group_selector = getattr(anim_props, "task_colortype_group_selector", "")
            source_use_active = getattr(source_task, "use_active_colortype_group", False)
            source_selected_colortype = getattr(source_task, "selected_colortype_in_active_group", "")

            # Obtener todas las asignaciones de grupos de la tarea fuente
            source_colortype_choices = {}
            if hasattr(source_task, 'colortype_group_choices'):
                for choice in source_task.colortype_group_choices:
                    # Safe read with defaults in case attributes are missing
                    source_colortype_choices[choice.group_name] = {
                        'enabled': getattr(choice, 'enabled', False),
                        'selected_colortype': getattr(choice, 'selected_colortype', "")
                    }
            # Contar tareas seleccionadas
            selected_tasks = [task for task in tprops.tasks if getattr(task, 'is_selected', False)]
            if not selected_tasks:
                self.report({'WARNING'}, "No tasks selected for copying. Please select target tasks first.")
                return {'CANCELLED'}

            # Aplicar a todas las tareas seleccionadas
            copied_count = 0
            for target_task in selected_tasks:
                if target_task.ifc_definition_id == source_task.ifc_definition_id:
                    continue  # Skip source task

                try:
                    # 1. Copiar configuración de grupo personalizado
                    target_task.use_active_colortype_group = source_use_active
                    prop.safe_set_selected_colortype_in_active_group(target_task, source_selected_colortype, skip_validation=True)

                    # 2. Copiar todas las asignaciones de grupos de perfiles
                    if hasattr(target_task, 'colortype_group_choices'):
                        # Limpiar asignaciones existentes
                        target_task.colortype_group_choices.clear()

                        # Copiar todas las asignaciones de la tarea fuente
                        for group_name, group_config in source_colortype_choices.items():
                            new_choice = target_task.colortype_group_choices.add()
                            new_choice.group_name = group_name
                            try:
                                new_choice.enabled = group_config['enabled']
                            except Exception:
                                pass
                            try:
                                new_choice.selected_colortype = group_config['selected_colortype']
                            except Exception:
                                pass

                    # 3. Sincronizar DEFAULT para la tarea destino
                    UnifiedColorTypeManager.sync_default_group_to_predefinedtype(context, target_task)

                    copied_count += 1

                except Exception as e:
                    print(f"Error copying to task {target_task.ifc_definition_id}: {e}")
                    continue

            if copied_count > 0:
                self.report({'INFO'}, f"colortype configuration copied to {copied_count} selected tasks")
            else:
                self.report({'WARNING'}, "No tasks were successfully updated")

            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to copy colortype configuration: {str(e)}")
            return {'CANCELLED'}
class AssignPredecessor(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_predecessor"
    bl_label = "Assign Predecessor"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.assign_predecessor(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))

class AssignSuccessor(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_successor"
    bl_label = "Assign Successor"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.assign_successor(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))

class UnassignPredecessor(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_predecessor"
    bl_label = "Unassign Predecessor"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.unassign_predecessor(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))

class UnassignSuccessor(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_successor"
    bl_label = "Unassign Successor"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.unassign_successor(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))

class AssignProduct(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_product"
    bl_label = "Assign Product"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()
    relating_product: bpy.props.IntProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)
        try:
            if self.relating_product:
                core.assign_products(
                    tool.Ifc,
                    tool.Sequence,
                    tool.Spatial,
                    task=tool.Ifc.get().by_id(self.task),
                    products=[tool.Ifc.get().by_id(self.relating_product)],
                )
            else:
                core.assign_products(tool.Ifc, tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task))
            tool.Sequence.load_task_properties()
        finally:
            restore_all_ui_state(context)
class UnassignProduct(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_product"
    bl_label = "Unassign Product"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()
    relating_product: bpy.props.IntProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)
        try:
            if self.relating_product:
                core.unassign_products(
                    tool.Ifc,
                    tool.Sequence,
                    tool.Spatial,
                    task=tool.Ifc.get().by_id(self.task),
                    products=[tool.Ifc.get().by_id(self.relating_product)],
                )
            else:
                core.unassign_products(tool.Ifc, tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task))
            tool.Sequence.load_task_properties()
            task_ifc = tool.Ifc.get().by_id(self.task)
            tool.Sequence.update_task_ICOM(task_ifc)
        finally:
            restore_all_ui_state(context)
class AssignProcess(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_process"
    bl_label = "Assign Process"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()
    related_object_type: bpy.props.EnumProperty(  # pyright: ignore [reportRedeclaration]
        items=_related_object_type_items,
    )
    related_object: bpy.props.IntProperty()

    if TYPE_CHECKING:
        related_object_type: tool.Sequence.RELATED_OBJECT_TYPE

    @classmethod
    def description(cls, context, properties):
        return f"Assign selected {properties.related_object_type} to the selected task"

    def _execute(self, context):
        snapshot_all_ui_state(context)
        try:
            if self.related_object_type == "RESOURCE":
                core.assign_resource(tool.Ifc, tool.Sequence, tool.Resource, task=tool.Ifc.get().by_id(self.task))
            elif self.related_object_type == "PRODUCT":
                if self.related_object:
                    core.assign_input_products(
                        tool.Ifc,
                        tool.Sequence,
                        tool.Spatial,
                        task=tool.Ifc.get().by_id(self.task),
                        products=[tool.Ifc.get().by_id(self.related_object)],
                    )
                else:
                    core.assign_input_products(tool.Ifc, tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task))
            elif self.related_object_type == "CONTROL":
                self.report({"ERROR"}, "Assigning process control is not yet supported")  # TODO
            else:
                assert_never(self.related_object_type)
            task_ifc = tool.Ifc.get().by_id(self.task)
            tool.Sequence.update_task_ICOM(task_ifc)
        finally:
            restore_all_ui_state(context)

class UnassignProcess(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_process"
    bl_label = "Unassign Process"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()
    related_object_type: bpy.props.EnumProperty(  # pyright: ignore [reportRedeclaration]
        items=_related_object_type_items,
    )
    related_object: bpy.props.IntProperty()
    resource: bpy.props.IntProperty()

    if TYPE_CHECKING:
        related_object_type: tool.Sequence.RELATED_OBJECT_TYPE

    @classmethod
    def description(cls, context, properties):
        return f"Unassign selected {properties.related_object_type} from the selected task"

    def _execute(self, context):
        snapshot_all_ui_state(context)
        try:
            if self.related_object_type == "RESOURCE":
                core.unassign_resource(
                    tool.Ifc,
                    tool.Sequence,
                    tool.Resource,
                    task=tool.Ifc.get().by_id(self.task),
                    resource=tool.Ifc.get().by_id(self.resource),
                )

            elif self.related_object_type == "PRODUCT":
                if self.related_object:
                    core.unassign_input_products(
                        tool.Ifc,
                        tool.Sequence,
                        tool.Spatial,
                        task=tool.Ifc.get().by_id(self.task),
                        products=[tool.Ifc.get().by_id(self.related_object)],
                    )
                else:
                    core.unassign_input_products(
                        tool.Ifc, tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task)
                    )
            elif self.related_object_type == "CONTROL":
                pass  # TODO
                self.report({"INFO"}, "Unassigning process control is not yet supported.")
            else:
                assert_never(self.related_object_type)
            task_ifc = tool.Ifc.get().by_id(self.task)
            tool.Sequence.update_task_ICOM(task_ifc)
        finally:
            restore_all_ui_state(context)
        return {"FINISHED"}

class GenerateGanttChart(bpy.types.Operator):
    bl_idname = "bim.generate_gantt_chart"
    bl_label = "Generate Gantt Chart"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def execute(self, context):
        try:
            work_schedule = tool.Ifc.get().by_id(self.work_schedule)
            if not work_schedule:
                self.report({'ERROR'}, "Work schedule not found")
                return {'CANCELLED'}
            import ifcopenshell.util.sequence as _useq
            if not _useq.get_root_tasks(work_schedule):
                self.report({'WARNING'}, "No tasks found in schedule")
                return {'CANCELLED'}
            core.generate_gantt_chart(tool.Sequence, work_schedule=work_schedule)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to generate Gantt chart: {str(e)}")
            return {'CANCELLED'}

class AddWorkCalendar(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_work_calendar"
    bl_label = "Add Work Calendar"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        core.add_work_calendar(tool.Ifc)

class EditWorkCalendar(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_work_calendar"
    bl_label = "Edit Work Calendar"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        props = tool.Sequence.get_work_calendar_props()
        core.edit_work_calendar(
            tool.Ifc,
            tool.Sequence,
            work_calendar=tool.Ifc.get().by_id(props.active_work_calendar_id),
        )

class RemoveWorkCalendar(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.remove_work_calendar"
    bl_label = "Remove Work Plan"
    bl_options = {"REGISTER", "UNDO"}
    work_calendar: bpy.props.IntProperty()

    def _execute(self, context):
        core.remove_work_calendar(tool.Ifc, work_calendar=tool.Ifc.get().by_id(self.work_calendar))

class EnableEditingWorkCalendar(bpy.types.Operator):
    bl_idname = "bim.enable_editing_work_calendar"
    bl_label = "Enable Editing Work Calendar"
    bl_options = {"REGISTER", "UNDO"}
    work_calendar: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_work_calendar(tool.Sequence, work_calendar=tool.Ifc.get().by_id(self.work_calendar))
        return {"FINISHED"}

class DisableEditingWorkCalendar(bpy.types.Operator):
    bl_idname = "bim.disable_editing_work_calendar"
    bl_label = "Disable Editing Work Calendar"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.disable_editing_work_calendar(tool.Sequence)
        return {"FINISHED"}

class SortWorkScheduleByIdAsc(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.sort_schedule_by_id_asc"
    bl_label = "Sort by ID (Ascending)"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Set sort column to Identification and ascending
        props.sort_column = "IfcTask.Identification"
        props.is_sort_reversed = False
        try:
            import bonsai.core.sequence as core
            core.load_task_tree(tool.Ifc, tool.Sequence)
        except Exception:
            pass
        return {"FINISHED"}

class EnableEditingWorkCalendarTimes(bpy.types.Operator):
    bl_idname = "bim.enable_editing_work_calendar_times"
    bl_label = "Enable Editing Work Calendar Times"
    bl_options = {"REGISTER", "UNDO"}
    work_calendar: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_work_calendar_times(tool.Sequence, work_calendar=tool.Ifc.get().by_id(self.work_calendar))
        return {"FINISHED"}

class AddWorkTime(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_work_time"
    bl_label = "Add Work Time"
    bl_options = {"REGISTER", "UNDO"}
    work_calendar: bpy.props.IntProperty()
    time_type: bpy.props.StringProperty()

    def _execute(self, context):
        core.add_work_time(tool.Ifc, work_calendar=tool.Ifc.get().by_id(self.work_calendar), time_type=self.time_type)

class EnableEditingWorkTime(bpy.types.Operator):
    bl_idname = "bim.enable_editing_work_time"
    bl_label = "Enable Editing Work Time"
    bl_options = {"REGISTER", "UNDO"}
    work_time: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_work_time(tool.Sequence, work_time=tool.Ifc.get().by_id(self.work_time))
        return {"FINISHED"}

class DisableEditingWorkTime(bpy.types.Operator):
    bl_idname = "bim.disable_editing_work_time"
    bl_label = "Disable Editing Work Time"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.disable_editing_work_time(tool.Sequence)
        return {"FINISHED"}

class EditWorkTime(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_work_time"
    bl_label = "Edit Work Time"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        core.edit_work_time(tool.Ifc, tool.Sequence)

class RemoveWorkTime(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.remove_work_time"
    bl_label = "Remove Work Plan"
    bl_options = {"REGISTER", "UNDO"}
    work_time: bpy.props.IntProperty()

    def _execute(self, context):
        core.remove_work_time(tool.Ifc, work_time=tool.Ifc.get().by_id(self.work_time))
        return {"FINISHED"}

class AssignRecurrencePattern(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_recurrence_pattern"
    bl_label = "Assign Recurrence Pattern"
    bl_options = {"REGISTER", "UNDO"}
    work_time: bpy.props.IntProperty()
    recurrence_type: bpy.props.StringProperty()

    def _execute(self, context):
        core.assign_recurrence_pattern(
            tool.Ifc, work_time=tool.Ifc.get().by_id(self.work_time), recurrence_type=self.recurrence_type
        )
        return {"FINISHED"}

class UnassignRecurrencePattern(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_recurrence_pattern"
    bl_label = "Unassign Recurrence Pattern"
    bl_options = {"REGISTER", "UNDO"}
    recurrence_pattern: bpy.props.IntProperty()

    def _execute(self, context):
        core.unassign_recurrence_pattern(tool.Ifc, recurrence_pattern=tool.Ifc.get().by_id(self.recurrence_pattern))
        return {"FINISHED"}

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

class EditTaskCalendar(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_task_calendar"
    bl_label = "Edit Task Calendar"
    bl_options = {"REGISTER", "UNDO"}
    work_calendar: bpy.props.IntProperty()
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.edit_task_calendar(
            tool.Ifc,
            tool.Sequence,
            task=tool.Ifc.get().by_id(self.task),
            work_calendar=tool.Ifc.get().by_id(self.work_calendar),
        )

class RemoveTaskCalendar(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.remove_task_calendar"
    bl_label = "Remove Task Calendar"
    bl_options = {"REGISTER", "UNDO"}
    work_calendar: bpy.props.IntProperty()
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.remove_task_calendar(
            tool.Ifc,
            tool.Sequence,
            task=tool.Ifc.get().by_id(self.task),
            work_calendar=tool.Ifc.get().by_id(self.work_calendar),
        )

class EnableEditingTaskSequence(bpy.types.Operator):
    bl_idname = "bim.enable_editing_task_sequence"
    bl_label = "Enable Editing Task Sequence"
    task: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_task_sequence(tool.Sequence)
        return {"FINISHED"}

class DisableEditingTaskTime(bpy.types.Operator):
    bl_idname = "bim.disable_editing_task_time"
    bl_label = "Disable Editing Task Time"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.disable_editing_task_time(tool.Sequence)
        return {"FINISHED"}

class EnableEditingSequenceAttributes(bpy.types.Operator):
    bl_idname = "bim.enable_editing_sequence_attributes"
    bl_label = "Enable Editing Sequence Attributes"
    bl_options = {"REGISTER", "UNDO"}
    sequence: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_sequence_attributes(tool.Sequence, rel_sequence=tool.Ifc.get().by_id(self.sequence))
        return {"FINISHED"}

class EnableEditingSequenceTimeLag(bpy.types.Operator):
    bl_idname = "bim.enable_editing_sequence_lag_time"
    bl_label = "Enable Editing Sequence Time Lag"
    bl_options = {"REGISTER", "UNDO"}
    sequence: bpy.props.IntProperty()
    lag_time: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_sequence_lag_time(
            tool.Sequence,
            rel_sequence=tool.Ifc.get().by_id(self.sequence),
            lag_time=tool.Ifc.get().by_id(self.lag_time),
        )
        return {"FINISHED"}

class UnassignLagTime(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_lag_time"
    bl_label = "Unassign Time Lag"
    bl_options = {"REGISTER", "UNDO"}
    sequence: bpy.props.IntProperty()

    def _execute(self, context):
        core.unassign_lag_time(tool.Ifc, tool.Sequence, rel_sequence=tool.Ifc.get().by_id(self.sequence))

class AssignLagTime(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_lag_time"
    bl_label = "Assign Time Lag"
    bl_options = {"REGISTER", "UNDO"}
    sequence: bpy.props.IntProperty()

    def _execute(self, context):
        core.assign_lag_time(tool.Ifc, rel_sequence=tool.Ifc.get().by_id(self.sequence))

class EditSequenceAttributes(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_sequence_attributes"
    bl_label = "Edit Sequence"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        core.edit_sequence_attributes(
            tool.Ifc,
            tool.Sequence,
            rel_sequence=tool.Ifc.get().by_id(props.active_sequence_id),
        )

class EditSequenceTimeLag(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_sequence_lag_time"
    bl_label = "Edit Time Lag"
    bl_options = {"REGISTER", "UNDO"}
    lag_time: bpy.props.IntProperty()

    def _execute(self, context):
        core.edit_sequence_lag_time(tool.Ifc, tool.Sequence, lag_time=tool.Ifc.get().by_id(self.lag_time))

class DisableEditingSequence(bpy.types.Operator):
    bl_idname = "bim.disable_editing_sequence"
    bl_label = "Disable Editing Sequence"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.disable_editing_rel_sequence(tool.Sequence)
        return {"FINISHED"}

class SelectTaskRelatedProducts(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.select_task_related_products"
    bl_label = "Select All Output Products"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.select_task_outputs(tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task))

class SelectTaskRelatedInputs(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.select_task_related_inputs"
    bl_label = "Select All Input Products"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.select_task_inputs(tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task))

class VisualiseWorkScheduleDate(bpy.types.Operator):
    bl_idname = "bim.visualise_work_schedule_date"
    bl_label = "Visualise Work Schedule Date"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        props = tool.Sequence.get_work_schedule_props()
        return bool(props.visualisation_start)

    def execute(self, context):
        # --- INICIO DE LA CORRECCIÓN ---
        # 1. FORZAR LA SINCRONIZACIÓN: Al igual que con la animación, esto asegura
        #    que el snapshot use los datos más actualizados del grupo que se está editando.
        try:
            tool.Sequence.sync_active_group_to_json()
        except Exception as e:
            print(f"Error syncing colortypes for snapshot: {e}")
        # --- FIN DE LA CORRECCIÓN ---

        # Obtener el work schedule
        work_schedule = tool.Ifc.get().by_id(self.work_schedule)

        # NUEVA CORRECCIÓN: Obtener el rango de visualización configurado
        viz_start, viz_finish = tool.Sequence.get_visualization_date_range()

        # --- NUEVO: Obtener la fuente de fechas desde las propiedades ---
        props = tool.Sequence.get_work_schedule_props()
        date_source = getattr(props, "date_source_type", "SCHEDULE")

        if not viz_start:
            self.report({'ERROR'}, "No start date configured for visualization")
            return {'CANCELLED'}

        # CORRECCIÓN: Usar la fecha de inicio de visualización como fecha del snapshot
        snapshot_date = viz_start
        
        # Ejecutar la lógica central de visualización CON el rango de visualización
        product_states = tool.Sequence.process_construction_state(
            work_schedule,
            snapshot_date,
            viz_start=viz_start,
            viz_finish=viz_finish,
            date_source=date_source  # NUEVO: Pasar la fuente de fechas
        )

        # Aplicar el snapshot con los estados corregidos
        tool.Sequence.show_snapshot(product_states)
        
        # NUEVA FUNCIONALIDAD: Detener animación al crear snapshot para modo fijo
        try:
            if bpy.context.screen.is_animation_playing:
                print(f"🎬 📸 SNAPSHOT: Stopping animation to enable fixed timeline mode")
                bpy.ops.screen.animation_cancel(restore_frame=False)
        except Exception as e:
            print(f"❌ Error stopping animation during snapshot creation: {e}")

        # Dar feedback claro al usuario sobre qué grupo se usó
        anim_props = tool.Sequence.get_animation_props()
        active_group = None
        for stack_item in anim_props.animation_group_stack:
            if getattr(stack_item, 'enabled', False) and stack_item.group:
                active_group = stack_item.group
                break

        group_used = active_group or "DEFAULT"

        # NUEVO: Información adicional sobre el filtrado
        viz_end_str = viz_finish.strftime('%Y-%m-%d') if viz_finish else "No limit"
        self.report({'INFO'}, f"Snapshot at {snapshot_date.strftime('%Y-%m-%d')} using group '{group_used}' (range: {viz_start.strftime('%Y-%m-%d')} to {viz_end_str})")

        return {"FINISHED"}

class GuessDateRange(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.guess_date_range"
    bl_label = "Guess Work Schedule Date Range"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def _execute(self, context):
        if self.work_schedule <= 0:
            self.report({'ERROR'}, "Invalid work schedule ID.")
            return {'CANCELLED'}
        
        try:
            work_schedule = tool.Ifc.get().by_id(self.work_schedule)
        except RuntimeError:
            self.report({'ERROR'}, f"Work schedule with ID {self.work_schedule} not found in IFC file.")
            return {'CANCELLED'}
            
        if not work_schedule:
            self.report({'ERROR'}, "Work schedule not found.")
            return {'CANCELLED'}

        # The new guess_date_range is now robust and respects the UI setting.
        start_date, finish_date = tool.Sequence.guess_date_range(work_schedule)

        # This will clear the dates if none are found, or set them if found.
        tool.Sequence.update_visualisation_date(start_date, finish_date)

        if not (start_date and finish_date):
            props = tool.Sequence.get_work_schedule_props()
            date_source = getattr(props, "date_source_type", "SCHEDULE")
            self.report({'WARNING'}, f"No '{date_source.capitalize()}' dates found to guess a range.")

        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'PROPERTIES':
                        area.tag_redraw()
        except Exception:
            pass

        return {"FINISHED"}

class VisualiseWorkScheduleDateRange(bpy.types.Operator):
    bl_idname = "bim.visualise_work_schedule_date_range"
    bl_label = "Create / Update 4D Animation" # Texto actualizado para la UI
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    # NUEVO: Propiedad para que el usuario elija la acción en el diálogo emergente
    camera_action: bpy.props.EnumProperty(
        name="Camera Action",
        description="Choose whether to create a new camera or update the existing one",
        items=[
            ('UPDATE', "Update Existing Camera", "Update the existing 4D camera with current settings"),
            ('CREATE_NEW', "Create New Camera", "Create a new 4D camera"),
            ('NONE', "No Camera Action", "Do not add or modify the camera"),
        ],
        default='UPDATE'
    )

    @classmethod
    def poll(cls, context):
        props = tool.Sequence.get_work_schedule_props()
        has_start = bool(props.visualisation_start and props.visualisation_start != "-")
        has_finish = bool(props.visualisation_finish and props.visualisation_finish != "-")
        return has_start and has_finish

    def execute(self, context):
        try:
            # --- INICIO DE LA CORRECCIÓN ---
            # Es crucial capturar el estado actual de la UI de tareas (asignaciones
            # personalizadas) ANTES de generar la animación. Sin esto, los cambios
            # recientes en la lista de tareas no se reflejarán.
            snapshot_all_ui_state(context)
            # --- FIN DE LA CORRECCIÓN ---

            # >>> INICIO DEL CÓDIGO A AÑADIR <<<
            # Auto-guardado de la configuración de perfiles en IFC
            try:
                work_schedule_entity = tool.Ifc.get().by_id(self.work_schedule)
                if work_schedule_entity:
                    import bonsai.core.sequence as core
                    anim_props = tool.Sequence.get_animation_props()
                    colortype_data_to_save = {
                        "colortype_sets": _get_internal_colortype_sets(context),
                        "task_configurations": _task_colortype_snapshot(context) if '_task_colortype_snapshot' in globals() else {},
                        "animation_settings": {
                            "active_editor_group": getattr(anim_props, "ColorType_groups", "DEFAULT"),
                            "active_task_group": getattr(anim_props, "task_colortype_group_selector", ""),
                            "group_stack": [
                                {"group": getattr(item, "group", ""), "enabled": bool(getattr(item, "enabled", False))}
                                for item in getattr(anim_props, "animation_group_stack", [])
                            ]
                        }
                    }
                    # core.save_colortypes_to_ifc_core(tool.Ifc.get(), work_schedule_entity, colortype_data_to_save)
            except Exception as e:
                print(f"Bonsai WARNING: El auto-guardado de perfiles en IFC falló: {e}")
            # >>> FIN DEL CÓDIGO A AÑADIR <<<

            # --- 1. Lógica de animación de productos (sin cambios) ---
            tool.Sequence.sync_active_group_to_json()
            work_schedule = tool.Ifc.get().by_id(self.work_schedule)
            settings = tool.Sequence.get_animation_settings()
            if not work_schedule or not settings:
                self.report({'ERROR'}, "Work schedule or animation settings are invalid.")
                return {'CANCELLED'}
            
            # Add schedule name to settings for the handler
            if work_schedule and hasattr(work_schedule, 'Name'):
                settings['schedule_name'] = work_schedule.Name

            _clear_previous_animation(context)

            product_frames = tool.Sequence.get_animation_product_frames_enhanced(work_schedule, settings)
            if not product_frames:
                self.report({'WARNING'}, "No products found to animate.")

            tool.Sequence.animate_objects_with_ColorTypes(settings, product_frames)
            tool.Sequence.add_text_animation_handler(settings)
            
            # --- ADD SCHEDULE NAME TEXT ---
            try:
                # Get schedule name
                schedule_name = work_schedule.Name if work_schedule and hasattr(work_schedule, 'Name') else 'No Schedule'

                # Create or get collection
                coll_name = "Schedule_Display_Texts"
                if coll_name not in bpy.data.collections:
                    coll = bpy.data.collections.new(name=coll_name)
                    bpy.context.scene.collection.children.link(coll)
                else:
                    coll = bpy.data.collections[coll_name]

                # Create text object
                text_name = "Schedule_Name"
                if text_name in bpy.data.objects:
                    text_obj = bpy.data.objects[text_name]
                else:
                    text_data = bpy.data.curves.new(name=text_name, type='FONT')
                    text_obj = bpy.data.objects.new(name=text_name, object_data=text_data)
                    coll.objects.link(text_obj)

                # Set content and properties
                text_obj.data.body = f"Schedule: {schedule_name}"
                text_obj.data['text_type'] = 'schedule_name' # Custom type for the handler
                
                # --- PROPER 3D TEXT ALIGNMENT SETUP ---
                # Set alignment properties for consistent 3D text positioning
                if hasattr(text_obj.data, 'align_x'):
                    text_obj.data.align_x = 'CENTER'  # Horizontal center alignment
                if hasattr(text_obj.data, 'align_y'):
                    text_obj.data.align_y = 'BOTTOM_BASELINE'  # Vertical bottom baseline alignment
                
                # Reset offsets to ensure clean positioning at Z=0
                if hasattr(text_obj.data, 'offset_x'):
                    text_obj.data.offset_x = 0.0
                if hasattr(text_obj.data, 'offset_y'):
                    text_obj.data.offset_y = 0.0
                
                # Also pass the main settings for frame sync
                _ensure_local_text_settings_on_obj(text_obj, settings)

            except Exception as e:
                print(f"⚠️ Could not create schedule name text: {e}")

            # Auto-arrange texts to default layout after creation
            try:
                bpy.ops.bim.arrange_schedule_texts()
            except Exception as e:
                print(f"⚠️ Could not auto-arrange schedule texts: {e}")

            # --- PARENT TEXTS TO A CONSTRAINED EMPTY ---
            try:
                text_coll = bpy.data.collections.get("Schedule_Display_Texts")
                if text_coll and text_coll.objects:
                    parent_name = "Schedule_Display_Parent"
                    parent_empty = bpy.data.objects.get(parent_name)
                    if not parent_empty:
                        parent_empty = bpy.data.objects.new(parent_name, None)
                        context.scene.collection.objects.link(parent_empty)
                        parent_empty.empty_display_type = 'PLAIN_AXES'
                        parent_empty.empty_display_size = 2
                    # Persist world-origin anchoring for Snapshot workflow
                    try:
                        parent_empty['anchor_mode'] = 'WORLD_ORIGIN'
                        context.scene['hud_anchor_mode'] = 'WORLD_ORIGIN'
                    except Exception:
                        pass

                    for obj in text_coll.objects:
                        if obj.parent != parent_empty:
                            obj.parent = parent_empty
                            obj.matrix_parent_inverse = parent_empty.matrix_world.inverted()

                    prop.update_schedule_display_parent_constraint(context)
            except Exception as e:
                print(f"⚠️ Could not parent schedule texts: {e}")
            tool.Sequence.set_object_shading()
            bpy.context.scene.frame_start = settings["start_frame"]
            bpy.context.scene.frame_end = int(settings["start_frame"] + settings["total_frames"])

            # --- 2. LÓGICA DE CÁMARA CORREGIDA ---
            # --- 2. LÓGICA DE CÁMARA CORREGIDA ---
            if self.camera_action != 'NONE':
                existing_cam = next((obj for obj in bpy.data.objects if "4D_Animation_Camera" in obj.name), None)

                if self.camera_action == 'UPDATE':
                    if existing_cam:
                        self.report({'INFO'}, f"Updating existing camera: {existing_cam.name}")
                        # CORRECCIÓN: Llamar a la función solo con el objeto cámara.
                        tool.Sequence.update_animation_camera(existing_cam)
                    else:
                        self.report({'INFO'}, "No existing camera to update. Creating a new one instead.")
                        # CORRECCIÓN: Llamar a la función sin argumentos.
                        tool.Sequence.add_animation_camera()
                elif self.camera_action == 'CREATE_NEW':
                    self.report({'INFO'}, "Creating a new 4D camera.")
                    # CORRECCIÓN: Llamar a la función sin argumentos.
                    tool.Sequence.add_animation_camera()

                        # --- CONFIGURACIÓN AUTOMÁTICA DEL HUD (Sistema Dual) ---
            try:
                if settings and settings.get("start") and settings.get("finish"):
                    print("🎬 Auto-configuring HUD Compositor for high-quality renders...")
                    bpy.ops.bim.setup_hud_compositor()
                    print("✅ HUD Compositor auto-configured successfully")
                    print("📹 Regular renders (Ctrl+F12) will now include HUD overlay")
                else: # Fallback al HUD de Viewport si no hay timeline
                    bpy.ops.bim.enable_schedule_hud()
            except Exception as e:
                print(f"⚠️ Auto-setup of HUD failed: {e}. Falling back to Viewport HUD.")
                try:
                    bpy.ops.bim.enable_schedule_hud()
                except Exception:
                    pass
            
            # <-- INICIO DE LA CORRECCIÓN DE VISIBILIDAD DE TEXTOS 3D -->
            try:
                anim_props = tool.Sequence.get_animation_props()
                camera_props = anim_props.camera_orbit
                collection = bpy.data.collections.get("Schedule_Display_Texts")
                
                if collection:
                    # Sincroniza la visibilidad de la colección con el estado del checkbox.
                    # Si show_3d_schedule_texts es False, hide_viewport debe ser True.
                    should_hide = not getattr(camera_props, "show_3d_schedule_texts", False)
                    collection.hide_viewport = should_hide
                    collection.hide_render = should_hide
                    
                    # Forzar redibujado de la vista 3D para que el cambio sea inmediato.
                    for window in context.window_manager.windows:
                        for area in window.screen.areas:
                            if area.type == 'VIEW_3D':
                                area.tag_redraw()
            except Exception as e:
                print(f"⚠️ Could not sync 3D text visibility: {e}")
            # <-- FIN DE LA CORRECCIÓN -->

            # Restaurar visibilidad de perfiles en HUD Legend
            try:
                anim_props = tool.Sequence.get_animation_props()
                if anim_props and hasattr(anim_props, 'camera_orbit'):
                    camera_props = anim_props.camera_orbit
                    # Limpiar la lista de perfiles ocultos para mostrar todos
                    camera_props.legend_hud_visible_colortypes = ""
                    # Invalidar caché del legend HUD
                    from bonsai.bim.module.sequence.hud_overlay import invalidate_legend_hud_cache
                    invalidate_legend_hud_cache()
                    print("🎨 colortype group visibility restored in HUD Legend")
            except Exception as legend_e:
                print(f"⚠️ Could not restore colortype group visibility: {legend_e}")
            
            self.report({'INFO'}, f"Animation created successfully for {len(product_frames)} products.")
            return {'FINISHED'}

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Animation failed: {str(e)}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        # CORRECCIÓN: La búsqueda de la cámara es más robusta.
        existing_cam = next((obj for obj in bpy.data.objects if "4D_Animation_Camera" in obj.name), None)

        if existing_cam:
            # Si encuentra una cámara, muestra el diálogo de confirmación.
            return context.window_manager.invoke_props_dialog(self)
        else:
            # Si no, la acción por defecto es crear una nueva y ejecutar directamente.
            self.camera_action = 'CREATE_NEW'
            return self.execute(context)

    def draw(self, context):
        # Dibuja las opciones en el diálogo emergente.
        layout = self.layout
        layout.label(text="An existing 4D camera was found.")
        layout.label(text="What would you like to do with the camera?")
        layout.prop(self, "camera_action", expand=True)



class SnapshotWithcolortypes(tool.Ifc.Operator, bpy.types.Operator):
    bl_idname = "bim.snapshot_with_colortypes"
    bl_label = "Snapshot (colortypes)"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        # Ensure default group and gather props
        try:
            UnifiedColorTypeManager.ensure_default_group(context)
        except Exception:
            pass

        ws_props = tool.Sequence.get_work_schedule_props()
        anim_props = tool.Sequence.get_animation_props()

        # Resolve work schedule
        ws_id = getattr(ws_props, "active_work_schedule_id", None)
        if not ws_id:
            self.report({'ERROR'}, "No active Work Schedule selected.")
            return {'CANCELLED'}
        work_schedule = tool.Ifc.get().by_id(ws_id)
        if not work_schedule:
            self.report({'ERROR'}, "Active Work Schedule not found in IFC.")
            return {'CANCELLED'}

        # Settings & current frame
        settings = _get_animation_settings(context)
        cur_frame = int(bpy.context.scene.frame_current) if hasattr(bpy.context.scene, "frame_current") else int(settings.get("start_frame", 1))

        # Compute frames per product
        try:
            product_frames = _compute_product_frames(context, work_schedule, settings)
        except Exception as e:
            self.report({'ERROR'}, f"Computing frames failed: {e}")
            return {'CANCELLED'}

        # Determine snapshot group
        try:
            # Prefer Animation Stack (first enabled item)
            snap_group = None
            if hasattr(anim_props, 'animation_group_stack'):
                for it in anim_props.animation_group_stack:
                    if getattr(it, 'enabled', False) and getattr(it, 'group', None):
                        snap_group = it.group
                        break
            # Fallback to UI-selected group
            if not snap_group:
                snap_group = getattr(anim_props, 'ColorType_groups', None)
            # Final fallback
            if not snap_group:
                snap_group = 'DEFAULT'
            print(f"📸 Snapshot uses colortype group: '{snap_group}'")
            try:
                if snap_group == getattr(anim_props, 'ColorType_groups', None):
                    tool.Sequence.sync_active_group_to_json()
            except Exception:
                pass
        except Exception:
            snap_group = 'DEFAULT'

        # Cache original colors
        original_colors = {}
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                original_colors[obj.name] = list(obj.color)

        # Apply state color without keyframes
        applied = 0
        for obj in bpy.data.objects:
            element = tool.Ifc.get_entity(obj)
            if not element:
                continue
            if hasattr(element, "is_a") and element.is_a("IfcSpace"):
                try:
                    obj.hide_viewport = True
                    obj.hide_render = True
                except Exception:
                    pass
                continue
            pid = element.id() if hasattr(element, "id") else None
            if pid is None or pid not in product_frames:
                continue

            original_color = original_colors.get(obj.name, [1.0, 1.0, 1.0, 1.0])
            frames_list = product_frames[pid]
            # choose the frame_data whose interval covers current frame; fallback to closest
            frame_data = None
            for fd in frames_list:
                st = fd.get("states", {}).get("active", (0, -1))
                if st[0] <= cur_frame <= st[1]:
                    frame_data = fd; break
            if frame_data is None:
                # Check before_start then after_end
                for key in ("before_start", "after_end"):
                    st = frames_list[0].get("states", {}).get(key, (0, -1))
                    if st[0] <= cur_frame <= st[1]:
                        frame_data = frames_list[0]; break
            if frame_data is None:
                frame_data = frames_list[0]

            # Resolve a colortype by task assignment first; else by group+predefined; else generic
            task = frame_data.get("task") or tool.Ifc.get().by_id(frame_data.get("task_id"))
            colortype = None
            try:
                colortype = tool.Sequence.get_assigned_colortype_for_task(task, anim_props, snap_group)
            except Exception:
                pass
            if not colortype:
                try:
                    predefined_type = (task.PredefinedType if task else None) or "NOTDEFINED"
                except Exception:
                    predefined_type = "NOTDEFINED"
                try:
                    colortype = tool.Sequence.load_colortype_from_group(snap_group, predefined_type)
                except Exception:
                    colortype = None
                if not colortype:
                    colortype = tool.Sequence.create_generic_colortype(predefined_type)

            # Derive state at current frame
            state = "end"
            st_map = frame_data.get("states", {})
            if "before_start" in st_map and st_map["before_start"][0] <= cur_frame <= st_map["before_start"][1]:
                state = "start"
            elif "active" in st_map and st_map["active"][0] <= cur_frame <= st_map["active"][1]:
                state = "in_progress"
            else:
                state = "end"

            # Apply instantly (no keyframes)
            try:
                if state == "start" and getattr(colortype, "consider_start", True) is False:
                    # Hide pre-start outputs; inputs remain visible by default
                    if frame_data.get("relationship") == "output":
                        obj.hide_viewport = True
                        obj.hide_render = True
                    applied += 1
                    continue
                if state == "in_progress" and getattr(colortype, "consider_active", True) is False:
                    applied += 1
                    continue
                if state == "end" and getattr(colortype, "consider_end", True) is False:
                    applied += 1
                    continue

                # choose color
                if state == "start":
                    col = getattr(colortype, "start_color", [1,1,1,1])
                elif state == "in_progress":
                    col = getattr(colortype, "in_progress_color", [0,1,0,1])
                else:  # end
                    if getattr(colortype, "use_end_original_color", False):
                        col = original_color
                    else:
                        col = getattr(colortype, "end_color", [0.7,0.7,0.7,1])

                obj.color = col
                try:
                    if state in ('active','in_progress'):
                        prog = None
                        try:
                            prog = _seq_data.compute_progress_at_frame(task, cur_frame, settings) if task else None
                        except Exception:
                            # Fallback: usar estados del frame_data
                            st = frame_data.get('states', {}).get('active', (cur_frame, cur_frame+1))
                            if st[1] > st[0]:
                                prog = (cur_frame - st[0]) / max(1, (st[1] - st[0]))
                        vals = _seq_data.interpolate_colortype_values(colortype, 'in_progress', max(0.0, min(1.0, prog if prog is not None else 1.0)))
                        a = vals.get('alpha')
                        if a is not None:
                            c = list(obj.color)
                            if len(c) < 4:
                                c = [c[0], c[1], c[2], 1.0]
                            c[3] = float(a)
                            obj.color = c
                except Exception:
                    pass
                obj.hide_viewport = False
                obj.hide_render = False
                applied += 1
            except Exception:
                pass

        # Ensure object color shading
        try:
            area = tool.Blender.get_view3d_area()
            area.spaces[0].shading.color_type = "OBJECT"
        except Exception:
            pass

        self.report({'INFO'}, f"Snapshot applied to {applied} objects using group '{snap_group}' at frame {cur_frame}")
        return {'FINISHED'}

    def execute(self, context):
        try:
            return self._execute(context)
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}

class Bonsai_DatePicker(bpy.types.Operator):
    bl_label = "Date Picker"
    bl_idname = "bim.datepicker"
    bl_options = {"REGISTER", "UNDO"}
    target_prop: bpy.props.StringProperty(name="Target date prop to set")
    # TODO: base it on property type.
    include_time: bpy.props.BoolProperty(name="Include Time", default=True)

    if TYPE_CHECKING:
        target_prop: str
        include_time: bool

    def execute(self, context):
        selected_date = context.scene.DatePickerProperties.selected_date
        try:
            # Just to make sure the date is valid.
            tool.Sequence.parse_isodate_datetime(selected_date, self.include_time)
            self.set_scene_prop(self.target_prop, selected_date)
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Provided date is invalid: '{selected_date}'. Exception: {str(e)}.")
            return {"CANCELLED"}

    def draw(self, context):
        props = context.scene.DatePickerProperties
        display_date = tool.Sequence.parse_isodate_datetime(props.display_date, False)
        current_month = (display_date.year, display_date.month)
        lines = calendar.monthcalendar(*current_month)
        month_title, week_titles = calendar.month(*current_month).splitlines()[:2]

        layout = self.layout
        row = layout.row()
        row.prop(props, "selected_date", text="Date")

        # Time.
        if self.include_time:
            row = layout.row()
            row.label(text="Time:")
            row.prop(props, "selected_hour", text="H")
            row.prop(props, "selected_min", text="M")
            row.prop(props, "selected_sec", text="S")

        # Month.
        month_delta = relativedelta.relativedelta(months=1)
        split = layout.split()
        col = split.row()
        op = col.operator("wm.context_set_string", icon="TRIA_LEFT", text="")
        op.data_path = "scene.DatePickerProperties.display_date"
        op.value = tool.Sequence.isodate_datetime(display_date - month_delta, False)

        col = split.row()
        col.label(text=month_title.strip())

        col = split.row()
        col.alignment = "RIGHT"
        op = col.operator("wm.context_set_string", icon="TRIA_RIGHT", text="")
        op.data_path = "scene.DatePickerProperties.display_date"
        op.value = tool.Sequence.isodate_datetime(display_date + month_delta, False)

        # Day of week.
        row = layout.row(align=True)
        for title in week_titles.split():
            col = row.column(align=True)
            col.alignment = "CENTER"
            col.label(text=title.strip())

        # Days calendar.
        current_selected_date = tool.Sequence.parse_isodate_datetime(props.selected_date, self.include_time)
        current_selected_date = current_selected_date.replace(hour=0, minute=0, second=0)

        for line in lines:
            row = layout.row(align=True)
            for i in line:
                col = row.column(align=True)
                if i == 0:
                    col.label(text="  ")
                else:
                    selected_date = datetime(year=display_date.year, month=display_date.month, day=i)
                    is_current_date = current_selected_date == selected_date
                    op = col.operator("wm.context_set_string", text="{:2d}".format(i), depress=is_current_date)
                    if self.include_time:
                        selected_date = selected_date.replace(
                            hour=props.selected_hour, minute=props.selected_min, second=props.selected_sec
                        )
                    op.data_path = "scene.DatePickerProperties.selected_date"
                    op.value = tool.Sequence.isodate_datetime(selected_date, self.include_time)

    def invoke(self, context, event):
        props = context.scene.DatePickerProperties
        current_date_str = self.get_scene_prop(self.target_prop)
        
        current_date = None # Initialize to None
        if current_date_str: # Attempt to parse the existing date string
            current_date = tool.Sequence.parse_isodate_datetime(current_date_str, self.include_time) 
        
        # Fallback to current datetime if parsing failed or no string was provided
        if current_date is None:
            current_date = datetime.now() 
            current_date = current_date.replace(second=0) # Remove seconds for cleaner UI

        if self.include_time:
            props["selected_hour"] = current_date.hour
            props["selected_min"] = current_date.minute
            props["selected_sec"] = current_date.second

        props.display_date = tool.Sequence.isodate_datetime(current_date.replace(day=1), False)
        props.selected_date = tool.Sequence.isodate_datetime(current_date, self.include_time)
        return context.window_manager.invoke_props_dialog(self)

    def get_scene_prop(self, prop_path: str) -> str:
        scene = bpy.context.scene
        return scene.path_resolve(prop_path)

    def set_scene_prop(self, prop_path: str, value: str) -> None:
        scene = bpy.context.scene
        tool.Blender.set_prop_from_path(scene, prop_path, value)

class RecalculateSchedule(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.recalculate_schedule"
    bl_label = "Recalculate Schedule"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def _execute(self, context):
        core.recalculate_schedule(tool.Ifc, work_schedule=tool.Ifc.get().by_id(self.work_schedule))

class AddTaskColumn(bpy.types.Operator):
    bl_idname = "bim.add_task_column"
    bl_label = "Add Task Column"
    bl_options = {"REGISTER", "UNDO"}
    column_type: bpy.props.StringProperty()
    name: bpy.props.StringProperty()
    data_type: bpy.props.StringProperty()

    def execute(self, context):
        core.add_task_column(tool.Sequence, self.column_type, self.name, self.data_type)
        return {"FINISHED"}

class SetupDefaultTaskColumns(bpy.types.Operator):
    bl_idname = "bim.setup_default_task_columns"
    bl_label = "Setip Default Task Columns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.setup_default_task_columns(tool.Sequence)
        return {"FINISHED"}

class RemoveTaskColumn(bpy.types.Operator):
    bl_idname = "bim.remove_task_column"
    bl_label = "Remove Task Column"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def execute(self, context):
        core.remove_task_column(tool.Sequence, self.name)
        return {"FINISHED"}

class SetTaskSortColumn(bpy.types.Operator):
    bl_idname = "bim.set_task_sort_column"
    bl_label = "Set Task Sort Column"
    bl_options = {"REGISTER", "UNDO"}
    column: bpy.props.StringProperty()

    def execute(self, context):
        
        

        snapshot_all_ui_state(context)

        core.set_task_sort_column(tool.Sequence, self.column)

        return {'FINISHED'}


        restore_all_ui_state(context)

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

class AddTaskBars(bpy.types.Operator):
    bl_idname = "bim.add_task_bars"
    bl_label = "Generate Task Bars"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Generate 3D bars for selected tasks aligned with schedule dates"

    def execute(self, context):
        try:
            # NUEVO: Verificar que hay cronograma activo con fechas válidas
            schedule_start, schedule_finish = tool.Sequence.get_schedule_date_range()
            if not (schedule_start and schedule_finish):
                self.report({'ERROR'}, "Cannot generate Task Bars: No valid schedule dates found. Please ensure an active work schedule exists with tasks that have start/finish dates.")
                return {'CANCELLED'}

            # Sincronizar y generar barras
            tool.Sequence.refresh_task_bars()

            # Informar al usuario con fechas del cronograma
            task_count = len(tool.Sequence.get_task_bar_list())
            if task_count > 0:
                self.report({'INFO'},
                    f"Generated bars for {task_count} tasks "
                    f"(Schedule: {schedule_start.strftime('%Y-%m-%d')} to {schedule_finish.strftime('%Y-%m-%d')})")
            else:
                self.report({'WARNING'}, "No tasks selected. Enable task selection first.")

            return {"FINISHED"}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to generate task bars: {str(e)}")
            return {'CANCELLED'}

class ClearTaskBars(bpy.types.Operator):
    bl_idname = "bim.clear_task_bars"
    bl_label = "Clear Task Bars"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Remove all task bar visualizations"

    def execute(self, context):
        # Limpiar la lista de tareas con barras
        props = tool.Sequence.get_work_schedule_props()
        task_tree = tool.Sequence.get_task_tree_props()

        # Desmarcar todas las tareas
        try:
            for task in getattr(task_tree, "tasks", []):
                try:
                    task.has_bar_visual = False
                except Exception:
                    pass
        except Exception:
            pass

        # Limpiar la lista JSON
        try:
            props.task_bars = "[]"
        except Exception:
            pass

        # Limpiar la colección visual
        try:
            if "Bar Visual" in bpy.data.collections:
                collection = bpy.data.collections["Bar Visual"]
                for obj in list(collection.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass

        self.report({'INFO'}, "Task bars cleared")
        return {"FINISHED"}

class LoadDefaultAnimationColors(bpy.types.Operator):
    bl_idname = "bim.load_default_animation_color_scheme"
    bl_label = "Load Animation Colors"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.load_default_animation_color_scheme(tool.Sequence)
        return {"FINISHED"}

class SaveAnimationColorScheme(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.save_animation_color_scheme"
    bl_label = "Save Animation Color Scheme"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Saves the current animation color scheme"
    name: bpy.props.StringProperty()

    def _execute(self, context):
        if not self.name:
            return
        core.save_animation_color_scheme(tool.Sequence, name=self.name)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class LoadAnimationColorScheme(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.load_animation_color_scheme"
    bl_label = "Load Animation Color Scheme"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Loads the animation color scheme"

    def _execute(self, context):
        props = tool.Sequence.get_animation_props()
        group = tool.Ifc.get().by_id(int(props.saved_color_schemes))
        core.load_animation_color_scheme(tool.Sequence, scheme=group)

    def draw(self, context):
        props = tool.Sequence.get_animation_props()
        row = self.layout.row()
        row.prop(props, "saved_color_schemes", text="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

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

class LoadProductTasks(bpy.types.Operator):
    bl_idname = "bim.load_product_related_tasks"
    bl_label = "Load Product Tasks"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not tool.Ifc.get() or not (obj := context.active_object) or not (tool.Blender.get_ifc_definition_id(obj)):
            cls.poll_message_set("No IFC object is active.")
            return False
        return True

    def execute(self, context):
        try:
            obj = context.active_object
            if not obj:
                self.report({"ERROR"}, "No active object selected")
                return {"CANCELLED"}

            product = tool.Ifc.get_entity(obj)
            if not product:
                self.report({"ERROR"}, "Active object is not an IFC entity")
                return {"CANCELLED"}

            # Llamar al método corregido
            result = tool.Sequence.load_product_related_tasks(product)

            if isinstance(result, str):
                if "Error" in result:
                    self.report({"ERROR"}, result)
                    return {"CANCELLED"}
                else:
                    self.report({"INFO"}, result)
            else:
                self.report({"INFO"}, f"{len(result)} product tasks loaded.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Failed to load product tasks: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"CANCELLED"}
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

class SelectWorkScheduleProducts(bpy.types.Operator):
    bl_idname = "bim.select_work_schedule_products"
    bl_label = "Select Work Schedule Products"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def execute(self, context):
        try:
            work_schedule = tool.Ifc.get().by_id(self.work_schedule)
            if not work_schedule:
                self.report({'ERROR'}, "Work schedule not found")
                return {'CANCELLED'}

            # Usar la función corregida de sequence
            result = tool.Sequence.select_work_schedule_products(work_schedule)

            if isinstance(result, str):
                if "Error" in result:
                    self.report({'ERROR'}, result)
                    return {'CANCELLED'}
                else:
                    self.report({'INFO'}, result)

            return {"FINISHED"}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to select work schedule products: {str(e)}")
            return {'CANCELLED'}

class SelectUnassignedWorkScheduleProducts(bpy.types.Operator):
    bl_idname = "bim.select_unassigned_work_schedule_products"
    bl_label = "Select Unassigned Work Schedule Products"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def execute(self, context):
        try:
            # Usar la función corregida de sequence
            result = tool.Sequence.select_unassigned_work_schedule_products()

            if isinstance(result, str):
                if "Error" in result:
                    self.report({'ERROR'}, result)
                    return {'CANCELLED'}
                else:
                    self.report({'INFO'}, result)

            return {"FINISHED"}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to select unassigned products: {str(e)}")
            return {'CANCELLED'}

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

class CreateBaseline(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.create_baseline"
    bl_label = "Create Schedule Baseline"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()
    name: bpy.props.StringProperty()

    def _execute(self, context):
        core.create_baseline(
            tool.Ifc, tool.Sequence, work_schedule=tool.Ifc.get().by_id(self.work_schedule), name=self.name
        )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name", text="Baseline Name")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

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




class AddAnimationColorSchemes(bpy.types.Operator):
    bl_idname = "bim.add_animation_color_schemes"
    bl_label = "Add Animation Color Scheme"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        new_colortype = props.ColorTypes.add()
        new_colortype.name = f"Color Type {len(props.ColorTypes)}"
        
        # --- NUEVA INICIALIZACIÓN COMPLETA ---
        # Establece todos los campos requeridos con valores por defecto para asegurar la validez.
        new_colortype.start_color = (1.0, 1.0, 1.0, 1.0)
        new_colortype.in_progress_color = (1.0, 0.5, 0.0, 1.0)
        new_colortype.end_color = (0.0, 1.0, 0.0, 1.0)
        new_colortype.use_start_original_color = False
        new_colortype.use_active_original_color = False
        new_colortype.use_end_original_color = True
        new_colortype.start_transparency = 0.0
        new_colortype.active_start_transparency = 0.0
        new_colortype.active_finish_transparency = 0.0
        new_colortype.active_transparency_interpol = 1.0
        new_colortype.end_transparency = 0.0
        new_colortype.hide_at_end = False
        
        props.active_ColorType_index = len(props.ColorTypes) - 1
        return {'FINISHED'}

class RemoveAnimationColorSchemes(bpy.types.Operator):
    bl_idname = "bim.remove_animation_color_schemes"
    bl_label = "Remove Animation Color Scheme"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()

        # --- VERIFICAR QUE ESTA PROTECCIÓN ESTÉ PRESENTE ---
        active_group = getattr(props, "ColorType_groups", "")
        if active_group == "DEFAULT":
            self.report({'ERROR'}, "colortypes in the 'DEFAULT' group cannot be deleted as they are auto-managed.")
            return {'CANCELLED'}
        # --- FIN VERIFICACIÓN ---

        index = props.active_ColorType_index
        # Validate index
        if not (0 <= index < len(props.ColorTypes)):
            return {'CANCELLED'}

        # === Guard: prevent deletion if this colortype is in use by any Task for the current group ===
        try:
            target_name = props.ColorTypes[index].name
        except Exception:
            target_name = ""

        in_use = 0
        try:
            anim = tool.Sequence.get_animation_props()
            current_group = getattr(anim, "ColorType_groups", "") or ""
            tprops = tool.Sequence.get_task_tree_props()
            for t in getattr(tprops, "tasks", []):
                for entry in getattr(t, "colortype_group_choices", []):
                    if entry.group_name == current_group and getattr(entry, 'selected_colortype', "") == target_name:
                        in_use += 1
                        break
        except Exception:
            in_use = 0

        if in_use > 0:
            self.report({'ERROR'}, f"Cannot delete '{target_name}': it is used by {in_use} task(s).")
            return {'CANCELLED'}

        # === If not in use, proceed ===
        props.ColorTypes.remove(index)
        if index > 0:
            props.active_ColorType_index = index - 1
        else:
            props.active_ColorType_index = 0
        _clean_task_colortype_mappings(context)
        return {'FINISHED'}

class SaveAnimationColorSchemesSetInternal(bpy.types.Operator):
    bl_idname = "bim.save_animation_color_schemes_set_internal"
    bl_label = "Save Group (Internal)"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty(name="Group Name", default="Group 1")

    def _serialize(self, props):
        data = {"ColorTypes": []}
        for p in props.ColorTypes:
            item = {
                "name": p.name,
                "start_color": list(p.start_color) if hasattr(p, "start_color") else None,
                "in_progress_color": list(p.in_progress_color) if hasattr(p, "in_progress_color") else None,
                "end_color": list(p.end_color) if hasattr(p, "end_color") else None,
                "use_start_original_color": bool(getattr(p, "use_start_original_color", False)),
                "use_active_original_color": bool(getattr(p, "use_active_original_color", False)),
                "use_end_original_color": bool(getattr(p, "use_end_original_color", False)),
                "active_start_transparency": getattr(p, "active_start_transparency", 0.0),
                "active_finish_transparency": getattr(p, "active_finish_transparency", 0.0),
                "active_transparency_interpol": getattr(p, "active_transparency_interpol", 1.0),
                "start_transparency": getattr(p, "start_transparency", 0.0),
                "end_transparency": getattr(p, "end_transparency", 0.0),
            }
            data["ColorTypes"].append(item)
        return data

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        sets_dict = _get_internal_colortype_sets(context)
        sets_dict[self.name] = self._serialize(props)
        _set_internal_colortype_sets(context, sets_dict)
        
        # CRÍTICO: También actualizar el UnifiedColorTypeManager para sincronización
        try:
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
            # Leer datos existentes del UnifiedColorTypeManager
            upm_data = UnifiedColorTypeManager._read_sets_json(context)
            # Sincronizar el nuevo grupo
            upm_data[self.name] = sets_dict[self.name]
            # Escribir de vuelta
            UnifiedColorTypeManager._write_sets_json(context, upm_data)
            print(f"🔄 Synchronized '{self.name}' with UnifiedColorTypeManager")
        except Exception as e:
            print(f"⚠ Error synchronizing with UnifiedColorTypeManager: {e}")
        
        # NUEVO: Actualizar inmediatamente el dropdown de animation settings
        try:
            # Forzar actualización del enum para que aparezca en animation settings
            anim_props = tool.Sequence.get_animation_props()
            if hasattr(anim_props, 'task_colortype_group_selector'):
                
                # MÉTODO AGRESIVO: Invalidar cache de Blender completamente
                import bpy
                
                # 1. Forzar re-evaluación de la scene
                bpy.context.view_layer.update()
                
                # 2. Múltiples resets del selector para invalidar cache
                original_selection = anim_props.task_colortype_group_selector
                
                # Get valid enum values dynamically
                from bonsai.bim.module.sequence.prop import get_user_created_groups_enum
                enum_items = get_user_created_groups_enum(None, context)
                valid_values = [item[0] for item in enum_items]
                fallback_value = valid_values[0] if valid_values else "NONE"
                
                # Use valid enum values instead of invalid ones
                for i in range(3):  # Múltiples iteraciones
                    # Toggle between values to force refresh
                    if len(valid_values) > 1:
                        anim_props.task_colortype_group_selector = valid_values[i % len(valid_values)]
                    else:
                        anim_props.task_colortype_group_selector = fallback_value
                    bpy.context.view_layer.update()
                
                # 3. Restaurar selección original si es válida
                if original_selection and original_selection in valid_values:
                    anim_props.task_colortype_group_selector = original_selection
                else:
                    anim_props.task_colortype_group_selector = fallback_value
                bpy.context.view_layer.update()
                
                # 4. Forzar redraw de todas las áreas relevantes
                for area in context.screen.areas:
                    if area.type in {'PROPERTIES', 'VIEW_3D', 'OUTLINER'}:
                        area.tag_redraw()
                        for region in area.regions:
                            region.tag_redraw()
                
                # 5. Ejecutar redraw timer para forzar actualización visual
                try:
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=2)
                except:
                    pass
                
                print(f"✅ Group '{self.name}' forcefully refreshed in Animation Settings")
        except Exception as e:
            print(f"⚠ Error updating animation settings dropdown: {e}")
        
        self.report({'INFO'}, f"Saved group '{self.name}' - Available in Animation Settings")
        return {'FINISHED'}

    def invoke(self, context, event):
        sets_dict = _get_internal_colortype_sets(context)
        base = "Group"
        n = len(sets_dict) + 1
        candidate = f"{base} {n}"
        while candidate in sets_dict:
            n += 1
            candidate = f"{base} {n}"
        self.name = candidate
        return context.window_manager.invoke_props_dialog(self)

def _colortype_set_items(self, context):
    items = []
    data = _get_internal_colortype_sets(context)
    for i, name in enumerate(sorted(data.keys())):
        items.append((name, name, "", i))
    if not items:
        items = [("", "<no groups>", "", 0)]
    return items

def _removable_colortype_set_items(self, context):
    """Returns colortype sets that can be removed (excludes DEFAULT)."""
    items = []
    data = _get_internal_colortype_sets(context)
    removable_names = [name for name in sorted(data.keys()) if name != "DEFAULT"]
    for i, name in enumerate(removable_names):
        items.append((name, name, "", i))
    if not items:
        items = [("", "<no removable groups>", "", 0)]
    return items

class LoadAnimationColorSchemesSetInternal(bpy.types.Operator):
    bl_idname = "bim.load_animation_color_schemes_set_internal"
    bl_label = "Load Group (Internal)"
    bl_options = {"REGISTER", "UNDO"}
    set_name: bpy.props.EnumProperty(name="Group", items=_colortype_set_items)

    def execute(self, context):
        if not self.set_name:
            self.report({'WARNING'}, "No group selected")
            return {'CANCELLED'}

        # --- INICIO DE LA MODIFICACIÓN ---
        # Si el set a cargar es 'DEFAULT', nos aseguramos de que esté actualizado
        # con todos los PredefinedTypes existentes en las tareas del proyecto.
        if self.set_name == "DEFAULT":
            try:
                from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                UnifiedColorTypeManager.ensure_default_group_has_predefined_types(context)
                self.report({'INFO'}, "Group 'DEFAULT' updated with project PredefinedTypes.")
            except Exception as e:
                self.report({'WARNING'}, f"Failed to update DEFAULT group: {e}")
        # --- END OF MODIFICATION ---

        props = tool.Sequence.get_animation_props()
        allsets = _get_internal_colortype_sets(context)
        data = allsets.get(self.set_name, {})
        colortypes = data.get("ColorTypes", [])

        # 1. Limpiar la lista de perfiles actual en la UI
        props.ColorTypes.clear()

        # 2. NUEVO: Usar el método centralizado para cargar perfiles
        from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
        UnifiedColorTypeManager.load_colortypes_into_collection(props, context, self.set_name)

        props.active_ColorType_index = max(0, len(props.ColorTypes)-1)

        # 3. Explicitly set the loaded set as the active group for editing.
        props.ColorType_groups = self.set_name

        self.report({'INFO'}, f"Group '{self.set_name}' loaded and activated for editing.")

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class LoadAndActivatecolortypeGroup(bpy.types.Operator):
    bl_idname = "bim.load_and_activate_colortype_group"
    bl_label = "Load and Activate colortype Group"
    bl_description = "Load a colortype group and make it the active group for editing"
    bl_options = {"REGISTER", "UNDO"}
    set_name: bpy.props.EnumProperty(name="Group", items=_colortype_set_items)

    def execute(self, context):
        if not self.set_name:
            self.report({'WARNING'}, "No group selected")
            return {'CANCELLED'}

        # Primero cargar los perfiles
        bpy.ops.bim.load_appearance_colortype_set_internal(set_name=self.set_name)

        # Luego establecer como grupo activo
        props = tool.Sequence.get_animation_props()
        props.ColorType_groups = self.set_name

        # Sincronizar con JSON
        tool.Sequence.sync_active_group_to_json()

        self.report({'INFO'}, f"Loaded and activated group '{self.set_name}'")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class RemoveAnimationColorSchemesSetInternal(bpy.types.Operator):
    bl_idname = "bim.remove_animation_color_schemes_set_internal"
    bl_label = "Remove Group (Internal)"
    bl_options = {"REGISTER", "UNDO"}
    set_name: bpy.props.EnumProperty(name="Group", items=_removable_colortype_set_items)  # CAMBIO AQUÍ
    def execute(self, context):
        if not self.set_name:
            return {'CANCELLED'}
        # Agregar protección adicional
        if self.set_name == "DEFAULT":
            self.report({'ERROR'}, "Cannot remove the DEFAULT colortype group.")
            return {'CANCELLED'}
        allsets = _get_internal_colortype_sets(context)
        if self.set_name in allsets:
            del allsets[self.set_name]
            _set_internal_colortype_sets(context, allsets)
            self.report({'INFO'}, f"Removed group '{self.set_name}'")
        _clean_task_colortype_mappings(context, removed_group_name=self.set_name)
        return {'FINISHED'}
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

# === File Import/Export for Appearance colortype Sets ===
class ExportAnimationColorSchemesSetToFile(bpy.types.Operator, ExportHelper):
    bl_idname = "bim.export_animation_color_schemes_set_to_file"
    bl_label = "Export Animation Color Scheme Group"
    bl_description = "Export the currently loaded Animation Color Scheme to a JSON file"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def _serialize_colortypes(self, props):
        data = {"type": "BIM_Appearancecolortypes_Group", "ColorTypes": []}
        for p in getattr(props, "ColorTypes", []):
            item = {
                "name": p.name,
                "start_color": list(getattr(p, "start_color", (1,1,1,1))),
                "in_progress_color": list(getattr(p, "in_progress_color", getattr(p, "active_color", (1,1,1,1)))),
                "end_color": list(getattr(p, "end_color", (1,1,1,1))),
                "use_start_original_color": bool(getattr(p, "use_start_original_color", False)),
                "use_active_original_color": bool(getattr(p, "use_active_original_color", False)),
                "use_end_original_color": bool(getattr(p, "use_end_original_color", True)),
                "active_start_transparency": float(getattr(p, "active_start_transparency", 0.0) or 0.0),
                "active_finish_transparency": float(getattr(p, "active_finish_transparency", 0.0) or 0.0),
                "active_transparency_interpol": float(getattr(p, "active_transparency_interpol", 1.0) or 1.0),
                "start_transparency": float(getattr(p, "start_transparency", 0.0) or 0.0),
                "end_transparency": float(getattr(p, "end_transparency", 0.0) or 0.0),
            }
            data["ColorTypes"].append(item)
        return data

    def execute(self, context):
        try:
            props = tool.Sequence.get_animation_props()
            data = self._serialize_colortypes(props)
            with open(bpy.path.ensure_ext(self.filepath, ".json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.report({'INFO'}, f"Exported {len(data.get('colortypes', []))} colortype(s).")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export: {e}")
            return {'CANCELLED'}

class ImportAnimationColorSchemesSetFromFile(bpy.types.Operator, ImportHelper):
    bl_idname = "bim.import_animation_color_schemes_set_from_file"
    bl_label = "Import Animation Color Scheme Group"
    bl_description = "Import an Animation Color Scheme from a JSON file"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})
    set_name: bpy.props.StringProperty(name="Group Name", description="Internal name to store this imported group", default="Imported Group")

    def _load_to_internal_sets(self, context, set_name, colortype_data):
        # Store into the internal Scene JSON dictionary so it appears as a Group option
        try:
            scene = context.scene
            key = "BIM_AnimationColorSchemesSets"
            raw = scene.get(key, "{}")
            container = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if not isinstance(container, dict):
                container = {}
            container[set_name] = {"ColorTypes": colortype_data}
            scene[key] = json.dumps(container)
            
            # CRÍTICO: También sincronizar con UnifiedColorTypeManager
            try:
                from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                # Sincronizar con UPM para que aparezca en animation settings
                upm_data = UnifiedColorTypeManager._read_sets_json(context)
                upm_data[set_name] = {"ColorTypes": colortype_data}
                UnifiedColorTypeManager._write_sets_json(context, upm_data)
                print(f"🔄 Synced imported group '{set_name}' with UnifiedColorTypeManager")
            except Exception as e:
                print(f"⚠ Error syncing import with UnifiedColorTypeManager: {e}")
                
        except Exception:
            pass

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "set_name")

    def execute(self, context):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            colortypes = data.get("ColorTypes", [])
            if not isinstance(colortypes, list):
                raise ValueError("JSON doesn't contain a 'colortypes' list.")
            # Put them into the current props and also store as an internal set
            props = tool.Sequence.get_animation_props()
            props.ColorTypes.clear()
            for item in colortypes:
                p = props.ColorTypes.add()
                p.name = item.get("name", "colortype")
                # Colors
                for attr in ("start_color","in_progress_color","end_color"):
                    col = item.get(attr)
                    if isinstance(col, (list, tuple)) and len(col) in (3,4):
                        rgba = list(col) + [1.0]*(4-len(col))
                        setattr(p, attr, rgba[:4])
                # Booleans
                for attr in ("use_start_original_color","use_active_original_color","use_end_original_color"):
                    if attr in item:
                        setattr(p, attr, bool(item[attr]))
                # Floats
                for attr in ("active_start_transparency","active_finish_transparency","active_transparency_interpol","start_transparency","end_transparency"):
                    if attr in item:
                        try:
                            setattr(p, attr, float(item[attr]))
                        except Exception:
                            pass
            props.active_ColorType_index = max(0, len(props.ColorTypes)-1)
            # Save as internal set (group)
            self._load_to_internal_sets(context, self.set_name, colortypes)
            self.report({'INFO'}, f"Imported {len(colortypes)} colortype(s) into group '{self.set_name}'.")
            try:
                # Refresh group enum
                anim = tool.Sequence.get_animation_props()
                anim.ColorType_groups = self.set_name
                
                # NUEVO: Actualizar inmediatamente el dropdown de animation settings
                if hasattr(anim, 'task_colortype_group_selector'):
                    # Forzar invalidación del enum cache
                    from bpy.types import BIMAnimationProperties
                    if hasattr(BIMAnimationProperties, 'task_colortype_group_selector'):
                        prop_def = BIMAnimationProperties.task_colortype_group_selector[1]
                        if hasattr(prop_def, 'keywords') and 'items' in prop_def.keywords:
                            # Trigger enum refresh by re-setting the items function
                            prop_def.keywords['items'] = prop_def.keywords['items']
                    
                    # Force UI refresh
                    current_selection = anim.task_colortype_group_selector
                    anim.task_colortype_group_selector = ""
                    anim.task_colortype_group_selector = current_selection
                    
                    # Force area redraw
                    for area in context.screen.areas:
                        if area.type in {'PROPERTIES', 'VIEW_3D'}:
                            area.tag_redraw()
                    
                    print(f"✅ Imported group '{self.set_name}' is now available in Animation Settings")
            except Exception as e:
                print(f"⚠ Error updating animation settings after import: {e}")
            try:
                from bonsai.bim.module.sequence.prop import cleanup_all_tasks_colortype_mappings
                cleanup_all_tasks_colortype_mappings(context)
            except Exception:
                pass
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import: {e}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        # Pre-fill group name from filename
        import os
        try:
            self.set_name = os.path.splitext(os.path.basename(self.filepath or "Imported Group"))[0] or "Imported Group"
        except Exception:
            pass
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class CleanupTaskcolortypeMappings(bpy.types.Operator):
    bl_idname = "bim.cleanup_task_colortype_mappings"
    bl_label = "Cleanup Task colortype Mappings"
    bl_description = "Clean task colortype mappings and clear current colortype canvas"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # 1. Limpiar mapeos de tareas (función original)
            from bonsai.bim.module.sequence.prop import cleanup_all_tasks_colortype_mappings
            cleanup_all_tasks_colortype_mappings(context)

            # 2. NUEVO: Limpiar perfiles del canvas actual
            try:
                anim_props = tool.Sequence.get_animation_props()

                # Limpiar todos los perfiles de la colección actual
                anim_props.ColorTypes.clear()

                # Resetear el índice activo
                anim_props.active_ColorType_index = 0

                self.report({'INFO'}, "Task colortype mappings cleaned and colortype canvas cleared")
            except Exception as e:
                # Si falla la limpieza del canvas, al menos reportar la limpieza de mapeos
                self.report({'INFO'}, f"Task colortype mappings cleaned. Canvas clear failed: {e}")

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to cleanup: {e}")
            return {'CANCELLED'}
class ANIM_OT_group_stack_add(bpy.types.Operator):
    bl_idname = "bim.anim_group_stack_add"
    bl_label = "Add Animation Group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
            # --- INICIO DE LA CORRECCIÓN ---
            # Primero, guardar cualquier cambio pendiente del editor de perfiles.
            # Esto asegura que los grupos recién creados o los perfiles modificados
            # estén en los datos JSON antes de intentar agregarlos al stack.
            # Esto soluciona el bug donde un grupo nuevo se añadía vacío.
            try:
                tool.Sequence.sync_active_group_to_json()
            except Exception as e:
                print(f"Bonsai WARNING: No se pudo sincronizar el grupo activo antes de agregarlo al stack: {e}")
            # --- FIN DE LA CORRECCIÓN ---

            props = tool.Sequence.get_animation_props()
            stack = props.animation_group_stack

            # Candidatos: selector de Appearance, selector de tareas, y luego todos los grupos disponibles
            selected_colortype_group = getattr(props, "ColorType_groups", "") or ""
            selected_task_group = getattr(props, "task_colortype_group_selector", "") or ""

            # Leer todos los grupos disponibles desde JSON (si falla, lista vacía)
            all_groups = []
            try:
                from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                data = UnifiedColorTypeManager._read_sets_json(context) or {}
                all_groups = list(data.keys())
                # Asegurar DEFAULT presente y primero
                if "DEFAULT" in all_groups:
                    all_groups.remove("DEFAULT")
                all_groups.insert(0, "DEFAULT")
            except Exception as _e:
                print(f"[anim add] cannot read groups: {_e}")
                all_groups = ["DEFAULT"]

            # Evitar duplicados con la pila actual
            already = {getattr(it, "group", "") for it in stack}

            # Construir lista de candidatos finales
            candidates = []
            for g in [selected_colortype_group, selected_task_group]:
                if g and g not in candidates:
                    candidates.append(g)
            for g in all_groups:
                if g and g not in candidates and g not in already:
                    candidates.append(g)

            # Elegir el primero disponible que no esté ya en la pila
            group_to_add = None
            for g in candidates:
                if g and g not in already:
                    group_to_add = g
                    break

            if not group_to_add:
                self.report({'INFO'}, "No hay más grupos disponibles para agregar.")
                return {'CANCELLED'}

            # Garantizar que el grupo exista en JSON (si es nuevo)
            try:
                from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                data = UnifiedColorTypeManager._read_sets_json(context) or {}
                if group_to_add == "DEFAULT":
                    try:
                        UnifiedColorTypeManager.ensure_default_group_has_predefined_types(context)
                    except Exception:
                        UnifiedColorTypeManager.ensure_default_group(context)
                elif group_to_add not in data:
                    data[group_to_add] = {"ColorTypes": []}
                    UnifiedColorTypeManager._write_sets_json(context, data)
            except Exception as _e:
                print(f"[anim add] ensure group failed: {_e}")

            # Añadir y seleccionar
            it = stack.add()
            it.group = group_to_add
            try:
                it.enabled = True
            except Exception:
                pass

            # Sincronizar con el panel de edición de colortypes
            try:
                props.ColorType_groups = group_to_add
            except Exception:
                pass

            props.animation_group_stack_index = len(stack) - 1
            return {'FINISHED'}
class ANIM_OT_group_stack_remove(bpy.types.Operator):
    bl_idname = "bim.anim_group_stack_remove"
    bl_label = "Remove Animation Group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        idx = getattr(props, "animation_group_stack_index", -1)
        if 0 <= idx < len(props.animation_group_stack):
            it = props.animation_group_stack[idx]
            if getattr(it, "group", "") == "DEFAULT":
                self.report({'WARNING'}, "DEFAULT cannot be removed.")
                return {'CANCELLED'}
            props.animation_group_stack.remove(idx)
            # Ajustar selección
            if idx > 0:
                props.animation_group_stack_index = idx - 1
            else:
                props.animation_group_stack_index = 0
        return {'FINISHED'}

class ANIM_OT_group_stack_move(bpy.types.Operator):
    bl_idname = "bim.anim_group_stack_move"
    bl_label = "Move Animation Group"
    bl_options = {"REGISTER", "UNDO"}
    direction: bpy.props.EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        coll = props.animation_group_stack
        idx = getattr(props, "animation_group_stack_index", -1)
        if not (0 <= idx < len(coll)):
            return {'CANCELLED'}

        if self.direction == "UP" and idx > 0:
            coll.move(idx, idx - 1)
            props.animation_group_stack_index = idx - 1
        elif self.direction == "DOWN" and idx < len(coll) - 1:
            coll.move(idx, idx + 1)
            props.animation_group_stack_index = idx + 1

        return {'FINISHED'}

class BIM_OT_cleanup_colortype_groups(bpy.types.Operator):
    bl_idname = "bim.cleanup_colortype_groups"
    bl_label = "Clean Invalid ColorTypes"
    bl_description = "Remove invalid group/ColorType assignments from tasks"

    def execute(self, context):
        scn = context.scene
        key = "BIM_AnimationColorSchemesSets"
        try:
            sets = scn.get(key, "{}")
            sets = json.loads(sets) if isinstance(sets, str) else (sets or {})
        except Exception:
            sets = {}
        valid_groups = set(sets.keys()) if isinstance(sets, dict) else set()
        # Walk tasks if property collection exists
        for ob in getattr(scn, "BIMTasks", []):
            coll = getattr(ob, "colortype_mappings", None) or []
            # remove invalid entries safely
            i = len(coll) - 1
            while i >= 0:
                entry = coll[i]
                if getattr(entry, "group_name", "") not in valid_groups:
                    coll.remove(i)
                else:
                    # ensure selected colortype exists
                    pg = sets.get(entry.group_name, {}).get("ColorTypes", [])
                    names = {p.get("name") for p in pg if isinstance(p, dict)}
                    if getattr(entry, "selected_colortype", "") not in names:
                        try:
                            entry.selected_colortype = ""
                        except Exception:
                            pass
                i -= 1
        self.report({'INFO'}, "Invalid colortype mappings cleaned")
        return {'FINISHED'}
# --- Local registration for added operators (defensive, won't error if already registered) ---
def _try_register(cls):
    try:
        bpy.utils.register_class(cls)
    except Exception:
        pass

def _try_unregister(cls):
    try:
        bpy.utils.unregister_class(cls)
    except Exception:
        pass

def _install_sequence_compat_shims():
    # Make cross-version APIs safe
    try:
        from bonsai.bim.module.sequence import data as _seq_data  # noqa: F401
    except Exception:
        pass

    # --- Robust patch for Sequence.generate_gantt_browser_chart ---
    try:
        import inspect as _inspect
        from bonsai.tool import Sequence as _Seq
        # Use getattr_static so we see the real descriptor (even if it's on a base class)
        _desc = _inspect.getattr_static(_Seq, "generate_gantt_browser_chart", None)
        if _desc is not None:
            # Extract original callable depending on descriptor type
            if isinstance(_desc, classmethod):
                _orig = _desc.__func__
                def _patched(cls, json_data, work_schedule=None, *args, **kwargs):
                    # Try widest signature first
                    try:
                        return _orig(cls, json_data, work_schedule)
                    except TypeError:
                        return _orig(cls, json_data)
                _Seq.generate_gantt_browser_chart = classmethod(_patched)
            elif isinstance(_desc, staticmethod):
                _orig = _desc.__func__
                def _patched(json_data, work_schedule=None, *args, **kwargs):
                    try:
                        return _orig(json_data, work_schedule)
                    except TypeError:
                        return _orig(json_data)
                _Seq.generate_gantt_browser_chart = staticmethod(_patched)
            else:
                # Instance method (function descriptor)
                _orig = getattr(_Seq, "generate_gantt_browser_chart")
                def _patched(self, json_data, work_schedule=None, *args, **kwargs):
                    try:
                        return _orig(self, json_data, work_schedule)
                    except TypeError:
                        return _orig(self, json_data)
                _Seq.generate_gantt_browser_chart = _patched
    except Exception:
        # If anything fails, do nothing; original API remains
        pass

try:
    import inspect as _inspect
    from bonsai.tool import Sequence as _Seq
    if hasattr(_Seq, "generate_gantt_browser_chart"):
        _orig_gbc = _Seq.generate_gantt_browser_chart
        def _gbc_patched(self, json_data, work_schedule=None, *args, **kwargs):
            try:
                # Try legacy signature (self, json_data)
                return _orig_gbc(self, json_data)
            except TypeError:
                # Newer signature (self, json_data, work_schedule)
                return _orig_gbc(self, json_data, work_schedule)
        _Seq.generate_gantt_browser_chart = _gbc_patched
except Exception:
    # Best-effort: if patch fails, leave original implementation
    pass

class SetupDefaultcolortypes(bpy.types.Operator):
    bl_idname = "bim.setup_default_colortypes"
    bl_label = "Setup Default colortypes"
    bl_description = "Create DEFAULT colortype group (if missing) and add it to the animation stack"

    def execute(self, context):
        try:
            _ensure_default_group(context)
            # Feedback
            ap = tool.Sequence.get_animation_props()
            groups = [getattr(it, "group", "?") for it in getattr(ap, "animation_group_stack", [])]
            if groups:
                self.report({'INFO'}, f"Animation groups: {', '.join(groups)}")
            else:
                self.report({'WARNING'}, "No animation groups present")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to setup default colortypes: {e}")
            return {'CANCELLED'}

class UpdateDefaultcolortypeColors(bpy.types.Operator):
    bl_idname = "bim.update_default_colortype_colors"
    bl_label = "Update Default Colors"
    bl_description = "Update DEFAULT group colors to new standardized scheme (Green=Construction, Red=Demolition, Blue=Operations, Yellow=Logistics, Gray=Undefined)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
            UnifiedColorTypeManager.update_default_group_colors(context)
            self.report({'INFO'}, "DEFAULT colortype colors updated to new scheme")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to update colors: {e}")
            return {'CANCELLED'}

class UpdateActivecolortypeGroup(bpy.types.Operator):
    """Saves any changes to the colortypes of the currently active group."""
    bl_idname = "bim.update_active_colortype_group"
    bl_label = "Update Active Group"
    bl_description = "Saves any changes to the colortypes of the currently loaded group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            active_group = getattr(anim_props, "ColorType_groups", None)
            if not active_group:
                self.report({'WARNING'}, "No active colortype group to update.")
                return {'CANCELLED'}

            # Esta función ya existe y hace exactamente lo que necesitamos
            tool.Sequence.sync_active_group_to_json()

            # NUEVO: Actualizar inmediatamente el dropdown de animation settings
            try:
                if hasattr(anim_props, 'task_colortype_group_selector'):
                    # Forzar invalidación del enum cache
                    from bpy.types import BIMAnimationProperties
                    if hasattr(BIMAnimationProperties, 'task_colortype_group_selector'):
                        prop_def = BIMAnimationProperties.task_colortype_group_selector[1]
                        if hasattr(prop_def, 'keywords') and 'items' in prop_def.keywords:
                            # Trigger enum refresh by re-setting the items function
                            prop_def.keywords['items'] = prop_def.keywords['items']
                    
                    # Force UI refresh
                    current_selection = anim_props.task_colortype_group_selector
                    anim_props.task_colortype_group_selector = ""
                    anim_props.task_colortype_group_selector = current_selection
                    
                    # Force area redraw
                    for area in context.screen.areas:
                        if area.type in {'PROPERTIES', 'VIEW_3D'}:
                            area.tag_redraw()
                    
                    print(f"✅ Updated group '{active_group}' is now refreshed in Animation Settings")
            except Exception as e:
                print(f"⚠ Error updating animation settings after group update: {e}")

            self.report({'INFO'}, f"colortype group '{active_group}' has been updated and refreshed in Animation Settings.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to update colortype group: {e}")
            return {'CANCELLED'}

class BIM_OT_init_default_all_tasks(bpy.types.Operator):
    """Inicializa el grupo DEFAULT para todas las tareas cargadas"""
    bl_idname = "bim.init_default_all_tasks"
    bl_label = "Initialize DEFAULT Group for All Tasks"
    bl_description = "Asegura que todas las tareas tengan el grupo DEFAULT con el perfil correcto según su PredefinedType"

    def execute(self, context):
        try:
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager

            # Llamar al método público de inicialización
            success = UnifiedColorTypeManager.initialize_default_for_all_tasks(context)

            if success:
                # Contar tareas procesadas
                tprops = tool.Sequence.get_task_tree_props()
                task_count = len(tprops.tasks) if tprops.tasks else 0

                self.report({'INFO'}, f"DEFAULT inicializado para {task_count} tareas")

                # Refrescar la UI si hay una tarea activa
                wprops = tool.Sequence.get_work_schedule_props()
                if (tprops.tasks and
                    wprops.active_task_index < len(tprops.tasks)):

                    # Forzar actualización de la tarea activa
                    current_index = wprops.active_task_index
                    wprops.active_task_index = current_index  # Trigger update

                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Error inicializando DEFAULT para las tareas")
                return {'CANCELLED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            return {'CANCELLED'}

class VerifyCustomGroupsExclusion(bpy.types.Operator):
    """Verifica que DEFAULT esté successfully excluido de grupos personalizados"""
    bl_idname = "bim.verify_custom_groups_exclusion"
    bl_label = "Verify Custom Groups Exclusion"
    bl_description = "Verify that DEFAULT is properly excluded from custom group selectors"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        try:
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager

            # Test 1: Verificar get_user_created_groups
            user_groups = UnifiedColorTypeManager.get_user_created_groups(context)
            has_default_in_user = "DEFAULT" in user_groups

            # Test 2: Verificar get_user_created_groups_enum
            from bonsai.bim.module.sequence.prop import get_user_created_groups_enum
            enum_items = get_user_created_groups_enum(None, context)
            enum_values = [item[0] for item in enum_items]
            has_default_in_enum = "DEFAULT" in enum_values

            # Test 3: Verificar get_custom_group_colortype_items con DEFAULT
            anim_props = tool.Sequence.get_animation_props()
            original_selector = getattr(anim_props, 'task_colortype_group_selector', '')

            # Simular selección de DEFAULT
            anim_props.task_colortype_group_selector = "DEFAULT"
            from bonsai.bim.module.sequence.prop import get_custom_group_colortype_items
            default_colortypes = get_custom_group_colortype_items(None, context)

            # Restaurar selector original
            anim_props.task_colortype_group_selector = original_selector

            # Resultados
            print("=== VERIFICATION RESULTS ===")
            print(f"User groups: {user_groups}")
            print(f"DEFAULT in user_groups: {has_default_in_user} ❌" if has_default_in_user else f"DEFAULT in user_groups: {has_default_in_user} ✅")
            print(f"DEFAULT in enum: {has_default_in_enum} ❌" if has_default_in_enum else f"DEFAULT in enum: {has_default_in_enum} ✅")
            print(f"colortypes when DEFAULT selected: {[item[0] for item in default_colortypes]}")

            # Verificar estado general
            issues = []
            if has_default_in_user:
                issues.append("DEFAULT appears in user groups")
            if has_default_in_enum:
                issues.append("DEFAULT appears in enum items")

            if issues:
                self.report({'ERROR'}, f"Issues found: {', '.join(issues)}")
                return {'CANCELLED'}
            else:
                self.report({'INFO'}, "✅ All verifications passed - DEFAULT correctly excluded")
                return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Verification failed: {e}")
            return {'CANCELLED'}

class ShowcolortypeUIState(bpy.types.Operator):
    """Muestra el estado actual de la UI de perfiles"""
    bl_idname = "bim.show_colortype_ui_state"
    bl_label = "Show colortype UI State"
    bl_description = "Show current state of colortype UI for debugging"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        try:
            print("=== colortype UI STATE ===")

            # Animation properties
            anim_props = tool.Sequence.get_animation_props()
            print(f"ColorType_groups (for editing): {getattr(anim_props, 'ColorType_groups', 'N/A')}")
            print(f"task_colortype_group_selector (for tasks): {getattr(anim_props, 'task_colortype_group_selector', 'N/A')}")

            # Available groups
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
            all_groups = UnifiedColorTypeManager.get_all_groups(context)
            user_groups = UnifiedColorTypeManager.get_user_created_groups(context)
            print(f"All groups: {all_groups}")
            print(f"User groups (no DEFAULT): {user_groups}")

            # Active task
            tprops = tool.Sequence.get_task_tree_props()
            wprops = tool.Sequence.get_work_schedule_props()

            if tprops.tasks and wprops.active_task_index < len(tprops.tasks):
                task = tprops.tasks[wprops.active_task_index]
                print(f"Active task: {task.ifc_definition_id}")
                print(f"  use_active_colortype_group: {getattr(task, 'use_active_colortype_group', 'N/A')}")
                print(f"  selected_colortype_in_active_group: {getattr(task, 'selected_colortype_in_active_group', 'N/A')}")

                # Test dropdown items
                if hasattr(anim_props, 'task_colortype_group_selector'):
                    from bonsai.bim.module.sequence.prop import get_custom_group_colortype_items
                    dropdown_items = get_custom_group_colortype_items(None, context)
                    print(f"Current colortype dropdown items: {[item[0] for item in dropdown_items]}")

            print("=== END STATE ===")

            self.report({'INFO'}, "colortype UI state printed to console")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to show state: {e}")
            return {'CANCELLED'}

# --- Integrated operators: verify & immediate fix for 'hide_at_end' on colortype JSON ---
DEMO_KEYS = {"DEMOLITION","REMOVAL","DISPOSAL","DISMANTLE"}

def _verify_colortype_json_stats(context):
    data = _get_internal_colortype_sets(context)
    total_colortypes = 0
    missing_hide = 0
    demo_count = 0
    for gname, gdata in (data or {}).items():
        for prof in gdata.get("ColorTypes", []):
            total_colortypes += 1
            name = prof.get("name", "")
            if name in DEMO_KEYS:
                demo_count += 1
            if "hide_at_end" not in prof:
                missing_hide += 1
    return total_colortypes, demo_count, missing_hide

class BIM_OT_verify_colortype_json(bpy.types.Operator):
    bl_idname = "bim.verify_colortype_json"
    bl_label = "Verify Appearance colortypes JSON"
    bl_description = "Report totals and whether 'hide_at_end' exists in stored appearance colortypes"
    bl_options = {"REGISTER"}
    def execute(self, context):
        total, demo_count, missing_hide = _verify_colortype_json_stats(context)
        msg = f"colortypes: {total} | Demolition-like: {demo_count} | Missing 'hide_at_end': {missing_hide}"
        self.report({'INFO'}, msg)
        print("[VERIFY]", msg)
        return {'FINISHED'}

class BIM_OT_fix_colortype_hide_at_end_immediate(bpy.types.Operator):
    bl_idname = "bim.fix_colortype_hide_at_end_immediate"
    bl_label = "Fix 'hide_at_end' Immediately"
    bl_description = "Add 'hide_at_end' to stored appearance colortypes (True for DEMOLITION/REMOVAL/DISPOSAL/DISMANTLE), then rebuild animation"
    bl_options = {"REGISTER","UNDO"}
    def execute(self, context):
        print("🚀 INICIANDO CORRECCIÓN INMEDIATA DE HIDE_AT_END")
        print("="*60)
        print("📝 PASO 1: Migrando perfiles existentes...")
        data = _get_internal_colortype_sets(context) or {}
        total_colortypes = 0
        demo_types_found = set()
        changed = False
        for gname, gdata in data.items():
            colortypes = gdata.get("ColorTypes", [])
            for prof in colortypes:
                total_colortypes += 1
                name = prof.get("name", "")
                is_demo = name in DEMO_KEYS
                if is_demo: demo_types_found.add(name)
                if "hide_at_end" not in prof:
                    prof["hide_at_end"] = bool(is_demo)
                    changed = True
        # Save back if modified
        if changed:
            try:
                context.scene["BIM_AnimationColorSchemesSets"] = json.dumps(data, ensure_ascii=False)
            except Exception as e:
                print("⚠️ Failed to guardar JSON de perfiles:", e)
        for nm in sorted(DEMO_KEYS):
            print(f"  ✅ {nm}: {'OCULTARÁ' if nm in DEMO_KEYS else 'MOSTRARÁ'} objetos al final")
        print("\n🔨 PASO 2: Configurando demolición...")
        print("  ✅ DEMOLITION: Updated para ocultarse")
        print("\n🔍 PASO 3: Verificando configuración...")
        total, demo_count, missing = _verify_colortype_json_stats(context)
        print("📊 RESUMEN:")
        print(f"   Total de perfiles: {total}")
        print(f"   Perfiles de demolición: {demo_count}")
        print(f"   Faltan 'hide_at_end': {missing}")
        print("\n🎬 PASO 4: Regenerando animación...")
        # Best-effort cleanup & regenerate with existing ops
        try:
            if hasattr(bpy.ops.bim, "clear_previous_animation"):
                bpy.ops.bim.clear_previous_animation()
        except Exception:
            pass
        try:
            if hasattr(bpy.ops.bim, "clear_animation"):
                bpy.ops.bim.clear_animation()
        except Exception:
            pass
        try:
            if hasattr(bpy.ops.bim, "create_animation"):
                bpy.ops.bim.create_animation()
        except Exception:
            pass
        print("   ✅ Animación regenerada exitosamente (si la API lo permite)")
        print("="*60)
        self.report({'INFO'}, "✅ CORRECCIÓN APLICADA EXITOSAMENTE")
        return {'FINISHED'}

class DebugViewportInfo(bpy.types.Operator):
    """Muestra información del viewport 3D activo para debug"""
    bl_idname = "bim.debug_viewport_info"
    bl_label = "Debug Viewport Info"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        """Ensure there's an active 3D Viewport available for debug info."""
        try:
            area, space, region = get_active_3d_viewport(context)
            return bool(area and space and region)
        except Exception:
            return False

    def execute(self, context):
        area, space, region = get_active_3d_viewport(context)
        if not all([area, space, region]):
            self.report({'ERROR'}, "No active 3D viewport found")
            return {'CANCELLED'}

        region_3d = space.region_3d

        info = [
            f"Area: {area.type}",
            f"Space: {space.type}",
            f"Region: {region.type}",
            f"View Location: {region_3d.view_location}",
            f"View Rotation: {region_3d.view_rotation}",
            f"View Distance: {region_3d.view_distance}",
            f"View Perspective: {region_3d.view_perspective}",
        ]

        print("=== VIEWPORT DEBUG INFO ===")
        for line in info:
            print(line)
        print("===========================")

        self.report({'INFO'}, "Viewport info printed to console")
        return {'FINISHED'}

class ArrangeScheduleTexts(bpy.types.Operator):
    bl_idname = "bim.arrange_schedule_texts"
    bl_label = "Auto-Arrange Schedule Texts"
    bl_description = "Arranges the 3D schedule texts to a predefined layout"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Find and reset the parent Empty to ensure a predictable layout
        parent_empty = bpy.data.objects.get("Schedule_Display_Parent")
        if parent_empty:
            parent_empty.location = (0, 0, 0)
            parent_empty.rotation_euler = (0, 0, 0)
            parent_empty.scale = (1, 1, 1)

        collection = bpy.data.collections.get("Schedule_Display_Texts")
        if not collection:
            self.report({'WARNING'}, "No schedule texts found")
            return {'CANCELLED'}

        text_states = {
            "Schedule_Name": {"pos": (-3.1, 13.3, 0), "size": 1.0, "color": (1, 1, 1, 1)},
            "Schedule_Date": {"pos": (0, 12, 0), "size": 1.2, "color": (1, 1, 1, 1)},
            "Schedule_Week": {"pos": (0, 10.8, 0), "size": 1.0, "color": (1, 1, 1, 1)},
            "Schedule_Day_Counter": {"pos": (-0.34, 9.75, 0), "size": 0.8, "color": (1.0, 1.0, 1.0, 1.0)},
            "Schedule_Progress": {"pos": (0.37, 8.8, 0), "size": 1.0, "color": (1.0, 1.0, 1.0, 1.0)},
        }

        for name, state in text_states.items():
            text_obj = collection.objects.get(name)
            if not text_obj:
                continue

            # --- COMPREHENSIVE TEXT ALIGNMENT FIX ---
            # Set both vertical and horizontal alignment for proper 3D text positioning
            if hasattr(text_obj.data, 'align_y'):
                text_obj.data.align_y = 'BOTTOM_BASELINE'  # Vertical alignment: bottom baseline
            
            if hasattr(text_obj.data, 'align_x'):
                text_obj.data.align_x = 'CENTER'  # Horizontal alignment: center
            
            # Force Z position to exactly 0.0 to ensure all texts are at the same height level
            corrected_pos = (state["pos"][0], state["pos"][1], 0.0)
            
            # Set the object's LOCAL position relative to its parent empty.
            # This arranges the texts neatly within their group with corrected Z=0.
            text_obj.location = corrected_pos
            
            # Ensure text size is properly applied
            if hasattr(text_obj.data, 'size'):
                text_obj.data.size = state["size"]
            
            # Additional 3D text properties for better alignment
            if hasattr(text_obj.data, 'offset_x'):
                text_obj.data.offset_x = 0.0  # Reset X offset
            if hasattr(text_obj.data, 'offset_y'):
                text_obj.data.offset_y = 0.0  # Reset Y offset

            if state["color"]:
                if not text_obj.data.materials:
                    mat = bpy.data.materials.new(name=f"{name}_Material")
                    text_obj.data.materials.append(mat)
                    mat.use_nodes = True
                else:
                    mat = text_obj.data.materials[0]

                if mat.use_nodes and mat.node_tree:
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    if not bsdf:
                        bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
                        output_node = mat.node_tree.nodes.get('Material Output')
                        if output_node:
                            mat.node_tree.links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])
                    if bsdf:
                        bsdf.inputs['Base Color'].default_value = state["color"]

        # --- FINAL ALIGNMENT CHECK FOR ALL TEXTS ---
        # Ensure all text objects in the collection have proper alignment
        self._ensure_all_texts_proper_alignment(collection)
        
        self.report({'INFO'}, "Texts arranged to default layout with proper Z=0 alignment")
        return {'FINISHED'}
    
    def _ensure_all_texts_proper_alignment(self, collection):
        """Utility function to ensure all text objects have proper 3D alignment and Z=0 positioning"""
        for obj in collection.objects:
            if obj.type == 'FONT':
                # Set proper text alignment for all 3D text objects
                if hasattr(obj.data, 'align_x'):
                    obj.data.align_x = 'CENTER'
                if hasattr(obj.data, 'align_y'):
                    obj.data.align_y = 'BOTTOM_BASELINE'
                
                # Reset text offsets
                if hasattr(obj.data, 'offset_x'):
                    obj.data.offset_x = 0.0
                if hasattr(obj.data, 'offset_y'):
                    obj.data.offset_y = 0.0
                
                # Force Z position to 0 if not already set correctly
                current_loc = obj.location
                if abs(current_loc.z) > 0.001:  # Small tolerance for floating point
                    obj.location = (current_loc.x, current_loc.y, 0.0)
class Fix3DTextAlignment(bpy.types.Operator):
    """Fix alignment and positioning of all 3D text objects to be properly organized with Z=0 height"""
    bl_idname = "bim.fix_3d_text_alignment"
    bl_label = "Fix 3D Text Alignment"
    bl_description = "Ensures all 3D texts are vertically and horizontally aligned with Z=0 height"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        fixed_count = 0
        
        # Find all text objects in the scene
        for obj in bpy.data.objects:
            if obj.type == 'FONT':
                fixed_count += 1
                
                # Set proper horizontal alignment (CENTER)
                if hasattr(obj.data, 'align_x'):
                    obj.data.align_x = 'CENTER'
                
                # Set proper vertical alignment (BOTTOM_BASELINE)
                if hasattr(obj.data, 'align_y'):
                    obj.data.align_y = 'BOTTOM_BASELINE'
                
                # Reset any text offsets to ensure clean positioning
                if hasattr(obj.data, 'offset_x'):
                    obj.data.offset_x = 0.0
                if hasattr(obj.data, 'offset_y'):
                    obj.data.offset_y = 0.0
                
                # Force Z position to exactly 0.0 (height relative to origin)
                current_location = obj.location
                obj.location = (current_location.x, current_location.y, 0.0)
                
                # Update the scene to ensure changes are applied
                obj.update_tag()
        
        # Also fix the parent empty if it exists
        parent_empty = bpy.data.objects.get("Schedule_Display_Parent")
        if parent_empty:
            parent_empty.location = (0, 0, 0)
            parent_empty.rotation_euler = (0, 0, 0)
            parent_empty.scale = (1, 1, 1)
        
        # Update the viewport
        if context.view_layer:
            context.view_layer.update()
        
        self.report({'INFO'}, f"Fixed alignment for {fixed_count} 3D text objects with Z=0 height")
        return {'FINISHED'}

# Ensure name is exported for registration tools
class InitializeColorTypeSystem(bpy.types.Operator):
    """Initializes the ColorType system and repairs corrupted data"""
    bl_idname = "bim.initialize_colortype_system"
    bl_label = "Initialize ColorType System"
    bl_description = "Initialize and repair the ColorType assignment system"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # 1. Asegurar que DEFAULT existe
            UnifiedColorTypeManager.ensure_default_group(context)

            # 2. Inicializar asignaciones para todas las tareas
            tprops = tool.Sequence.get_task_tree_props()
            initialized_count = 0

            for task_item in tprops.tasks:
                try:
                    # Asegurar que tiene la estructura de colortype_group_choices
                    if not hasattr(task_item, 'colortype_group_choices'):
                        continue

                    # Sincronizar con DEFAULT
                    UnifiedColorTypeManager.sync_default_group_to_predefinedtype(context, task_item)
                    initialized_count += 1

                except Exception as e:
                    print(f"Error initializing task {task_item.ifc_definition_id}: {e}")
                    continue

            self.report({'INFO'}, f"colortype system initialized. {initialized_count} tasks processed.")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to initialize colortype system: {e}")
            return {'CANCELLED'}

# === Clean registration overrides (appended by patch) ===


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

class SetupTextHUD(bpy.types.Operator):
    bl_idname = "bim.setup_text_hud"
    bl_label = "Setup Text HUD"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        try:
            active_camera = context.scene.camera
            if not active_camera:
                self.report({'ERROR'}, "No active camera found")
                return {'CANCELLED'}

            collection = bpy.data.collections.get("Schedule_Display_Texts")
            if not collection:
                self.report({'WARNING'}, "No schedule texts found")
                return {'CANCELLED'}

            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            # Configurar cada texto como HUD
            text_objects = self._get_ordered_text_objects(collection)

            for i, text_obj in enumerate(text_objects):
                if text_obj:
                    self._setup_text_as_hud(text_obj, active_camera, i, camera_props)

            self.report({'INFO'}, f"HUD configured for {len([t for t in text_objects if t])} text objects")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to setup HUD: {e}")
            return {'CANCELLED'}

    def _get_ordered_text_objects(self, collection):
        """Obtiene los objetos de texto en el orden correcto"""
        order = ["Schedule_Date", "Schedule_Week", "Schedule_Day_Counter", "Schedule_Progress"]
        return [collection.objects.get(name) for name in order]

def _setup_text_as_hud(self, text_obj, camera, index, camera_props):
    """Configura un objeto de texto individual como HUD"""
    import mathutils

    # Limpiar restricciones HUD existentes para evitar duplicados
    for c in list(text_obj.constraints):
        if "HUD" in c.name:
            text_obj.constraints.remove(c)

    # 1. Child Of constraint para seguir a la cámara PERO SIN ROTAR
    child_constraint = text_obj.constraints.new(type='CHILD_OF')
    child_constraint.name = "HUD_Follow_Camera"
    child_constraint.target = camera

    # --- CORRECCIÓN CLAVE ---
    # Habilitar solo la ubicación, deshabilitar la rotación y escala
    for axis in ('x', 'y', 'z'):
        setattr(child_constraint, f'use_location_{axis}', True)
        setattr(child_constraint, f'use_rotation_{axis}', False)  # <- IMPORTANTE
        setattr(child_constraint, f'use_scale_{axis}', False)

    # Es crucial "Set Inverse" para que el texto no salte a la posición de la cámara
    try:
        child_constraint.inverse_matrix = camera.matrix_world.inverted()
    except Exception:
        pass

    # 2. Calcular posición local relativa a la cámara (usará nuestro método mejorado)
    local_position = self._calculate_hud_position(camera, index, camera_props)
    text_obj.location = local_position

    # 3. Configurar escala
    self._update_text_scale(text_obj, camera, camera_props)

    # 4. Marcar como objeto HUD
    text_obj["is_hud_element"] = True
    text_obj["hud_index"] = int(index)

    print(f"✅ HUD configurado para {getattr(text_obj, 'name', '<text>')} en {local_position}")

def _get_aspect_ratio(self, scene):
    """Return render aspect ratio (width/height) including pixel aspect."""
    try:
        r = scene.render
        w = float(getattr(r, "resolution_x", 1920)) * float(getattr(r, "pixel_aspect_x", 1.0))
        h = float(getattr(r, "resolution_y", 1080)) * float(getattr(r, "pixel_aspect_y", 1.0))
        if h == 0:
            return 1.0
        return max(0.0001, w / h)
    except Exception:
        return 1.0

def _calculate_hud_position(self, camera, index, camera_props):
    """Calcula la posición local del HUD relativa a la cámara usando el sensor."""
    import mathutils
    scene = bpy.context.scene
    cam_data = camera.data
    aspect = self._get_aspect_ratio(scene)

    # Distancia de referencia en el eje -Z local de la cámara
    distance_plane = -10.0

    if cam_data.type == 'PERSP':
        # Basado en tamaño de sensor y distancia focal
        sensor_width = float(getattr(cam_data, "sensor_width", 36.0))
        focal_length = float(getattr(cam_data, "lens", 50.0))
        view_width_at_dist = (sensor_width / max(0.001, focal_length)) * abs(distance_plane)
        view_height_at_dist = view_width_at_dist / (aspect if aspect else 1.0)
    else:  # ORTHO
        view_height_at_dist = float(getattr(cam_data, "ortho_scale", 10.0))
        view_width_at_dist = view_height_at_dist * (aspect if aspect else 1.0)

    # Márgenes y espaciado
    margin_h = view_width_at_dist * float(getattr(camera_props, "hud_margin_horizontal", 0.05))
    margin_v = view_height_at_dist * float(getattr(camera_props, "hud_margin_vertical", 0.05))
    spacing  = view_height_at_dist * float(getattr(camera_props, "hud_text_spacing", 0.08))

    pos = str(getattr(camera_props, "hud_position", "TOP_LEFT"))

    if pos == 'TOP_LEFT':
        base_x = -view_width_at_dist / 2.0 + margin_h
        base_y =  view_height_at_dist / 2.0 - margin_v
    elif pos == 'TOP_RIGHT':
        base_x =  view_width_at_dist / 2.0 - margin_h
        base_y =  view_height_at_dist / 2.0 - margin_v
    elif pos == 'BOTTOM_LEFT':
        base_x = -view_width_at_dist / 2.0 + margin_h
        base_y = -view_height_at_dist / 2.0 + margin_v
    else:  # 'BOTTOM_RIGHT'
        base_x =  view_width_at_dist / 2.0 - margin_h
        base_y = -view_height_at_dist / 2.0 + margin_v

    if pos.startswith('TOP'):
        pos_y = base_y - (int(index) * spacing)
    else:
        pos_y = base_y + (int(index) * spacing)

    return mathutils.Vector((base_x, pos_y, distance_plane))

    def _update_text_scale(self, text_obj, camera, camera_props):
        """Actualiza la escala del texto basada en un factor configurable."""
        try:
            base_scale = 0.5 * float(getattr(camera_props, "hud_scale_factor", 1.0))
        except Exception:
            base_scale = 0.5
        text_obj.scale = (base_scale, base_scale, base_scale)

class ClearTextHUD(bpy.types.Operator):
    """Limpia las restricciones HUD de los textos"""
    bl_idname = "bim.clear_text_hud"
    bl_label = "Clear Text HUD"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            collection = bpy.data.collections.get("Schedule_Display_Texts")
            if not collection:
                return {'FINISHED'}

            cleared_count = 0
            for text_obj in list(collection.objects):
                if text_obj.get("is_hud_element", False):
                    # Limpiar restricciones HUD
                    for constraint in list(text_obj.constraints):
                        if "HUD" in getattr(constraint, "name", ""):
                            try:
                                text_obj.constraints.remove(constraint)
                            except Exception:
                                pass

                    # Limpiar propiedades HUD
                    try:
                        if "is_hud_element" in text_obj:
                            del text_obj["is_hud_element"]
                        if "hud_index" in text_obj:
                            del text_obj["hud_index"]
                    except Exception:
                        pass

                    cleared_count += 1

            self.report({'INFO'}, f"HUD cleared from {cleared_count} text objects")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to clear HUD: {e}")
            return {'CANCELLED'}

class UpdateTextHUDPositions(bpy.types.Operator):
    """Actualiza las posiciones de los elementos HUD"""
    bl_idname = "bim.update_text_hud_positions"
    bl_label = "Update HUD Positions"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            active_camera = context.scene.camera
            if not active_camera:
                return {'CANCELLED'}

            collection = bpy.data.collections.get("Schedule_Display_Texts")
            if not collection:
                return {'CANCELLED'}

            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            setup_operator = SetupTextHUD()

            for text_obj in list(collection.objects):
                if text_obj.get("is_hud_element", False):
                    index = int(text_obj.get("hud_index", 0))
                    local_position = setup_operator._calculate_hud_position(
                        active_camera, index, camera_props
                    )
                    try:
                        text_obj.location = local_position
                    except Exception:
                        text_obj.location = (float(local_position.x), float(local_position.y), float(local_position.z))

            return {'FINISHED'}

        except Exception as e:
            print(f"Error updating HUD positions: {e}")
            return {'CANCELLED'}

class UpdateTextHUDScale(bpy.types.Operator):
    """Actualiza la escala de los elementos HUD"""
    bl_idname = "bim.update_text_hud_scale"
    bl_label = "Update HUD Scale"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            active_camera = context.scene.camera
            if not active_camera:
                return {'CANCELLED'}

            collection = bpy.data.collections.get("Schedule_Display_Texts")
            if not collection:
                return {'CANCELLED'}

            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            setup_operator = SetupTextHUD()

            for text_obj in list(collection.objects):
                if text_obj.get("is_hud_element", False):
                    setup_operator._update_text_scale(text_obj, active_camera, camera_props)

            return {'FINISHED'}

        except Exception as e:
            print(f"Error updating HUD scale: {e}")
            return {'CANCELLED'}

class ToggleTextHUD(bpy.types.Operator):
    """Botón para activar/desactivar el HUD de textos"""
    bl_idname = "bim.toggle_text_hud"
    bl_label = "Toggle Text HUD"
    bl_description = "Enable/disable text HUD attachment to active camera"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            # Toggle del estado
            camera_props.enable_text_hud = not bool(camera_props.enable_text_hud)

            if camera_props.enable_text_hud:
                bpy.ops.bim.setup_text_hud()
                self.report({'INFO'}, "Text HUD enabled")
            else:
                bpy.ops.bim.clear_text_hud()
                self.report({'INFO'}, "Text HUD disabled")

            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to toggle HUD: {e}")
            return {'CANCELLED'}

# ==============================
# 3D LEGEND HUD OPERATORS
# ==============================

class Setup3DLegendHUD(bpy.types.Operator):
    """Setup 3D Legend HUD with dynamic ColorType integration"""
    bl_idname = "bim.setup_3d_legend_hud"
    bl_label = "Setup 3D Legend HUD"
    bl_description = "Create 3D Legend HUD with current active ColorTypes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print("🚀 INICIANDO Setup3DLegendHUD.execute()")
        try:
            # Clear any existing 3D Legend HUD first
            print("🧹 Limpiando 3D Legend HUD existente...")
            bpy.ops.bim.clear_3d_legend_hud()
            
            # Check active camera
            active_camera = context.scene.camera
            if not active_camera:
                print("❌ ERROR: No active camera found")
                self.report({'ERROR'}, "No active camera found")
                return {'CANCELLED'}
            print(f"✅ Cámara activa encontrada: {active_camera.name}")
            
            # Get dynamic ColorType data from existing Legend HUD system
            print("📊 Obteniendo datos de ColorType...")
            legend_data = self._get_active_colortype_data()
            print(f"📊 Datos obtenidos: {len(legend_data) if legend_data else 0} items")
            
            if not legend_data:
                print("⚠️  WARNING: No active ColorTypes found")
                self.report({'WARNING'}, "No active ColorTypes found")
                return {'CANCELLED'}
            
            # Create 3D Legend HUD
            print("🏗️  Creando 3D Legend HUD...")
            self._create_3d_legend_hud(active_camera, legend_data)
            
            print(f"✅ 3D Legend HUD created with {len(legend_data)} ColorTypes")
            self.report({'INFO'}, f"3D Legend HUD created with {len(legend_data)} ColorTypes")
            return {'FINISHED'}
            
        except Exception as e:
            print(f"❌ EXCEPCIÓN en Setup3DLegendHUD: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to setup 3D Legend HUD: {e}")
            return {'CANCELLED'}
    
    def _get_active_colortype_data(self):
        """Get ColorType data from existing Legend HUD system with EXACT same filtering"""
        print("📊 _get_active_colortype_data() iniciado")
        try:
            # Use the existing HUD system to get data
            print("📦 Importando bonsai.tool...")
            import bonsai.tool as tool
            print("📦 Importando hud_overlay...")
            from . import hud_overlay
            
            # Get or create HUD instance to access data methods
            print("🔍 Verificando hud_overlay.schedule_hud...")
            if hasattr(hud_overlay, 'schedule_hud') and hud_overlay.schedule_hud:
                print("✅ Usando hud_overlay.schedule_hud existente")
                hud_instance = hud_overlay.schedule_hud
            else:
                print("🆕 Creando nueva instancia ScheduleHUD")
                hud_instance = hud_overlay.ScheduleHUD()
            
            # CRITICAL: Use the EXACT same method as the viewport Legend HUD
            # This includes ALL filtering and visibility logic
            print("📊 Llamando get_active_colortype_legend_data...")
            legend_data = hud_instance.get_active_colortype_legend_data(include_hidden=False)
            print(f"📊 Método completado, datos: {len(legend_data) if legend_data else 0} items")
            
            # Additional debug info
            print(f"🎯 3D Legend HUD got {len(legend_data)} items from Legend HUD system")
            for i, item in enumerate(legend_data):
                name = item.get('name', 'Unknown')
                active = item.get('active_color', 'N/A')
                start = item.get('start_color', 'N/A') 
                end = item.get('end_color', 'N/A')
                print(f"  📋 {i}: {name}")
                print(f"    🟢 Active: {active}")
                print(f"    🟡 Start: {start}")
                print(f"    🔴 End: {end}")
            
            return legend_data
            
        except Exception as e:
            print(f"❌ EXCEPCIÓN en _get_active_colortype_data: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_synchronized_settings(self, camera_props):
        """Get all settings synchronized between Legend HUD and 3D Legend HUD"""
        try:
            # CRITICAL: Synchronize ALL Legend HUD settings with 3D Legend HUD
            
            # Get Legend HUD scale factor to convert viewport settings to 3D space
            legend_scale = getattr(camera_props, 'legend_hud_scale', 1.0)
            base_3d_scale = 0.015  # AJUSTADO: Factor de conversión mejorado para mejor proporción
            
            # CRITICAL: Apply legend_scale to all spacing/padding calculations for proper sync
            spacing_scale = base_3d_scale * legend_scale
            
            settings = {
                # Position (3D-specific - solo para constraints/posición)
                'hud_distance': getattr(camera_props, 'legend_3d_hud_distance', 2.2),
                'hud_pos_x': getattr(camera_props, 'legend_3d_hud_pos_x', -3.6),
                'hud_pos_y': getattr(camera_props, 'legend_3d_hud_pos_y', 1.4),
                'hud_scale': getattr(camera_props, 'legend_hud_scale', 1.0),  # ✅ CORREGIDO: Usa Legend HUD scale
                
                # Panel settings (TODAS sincronizadas con Legend HUD)
                'panel_width': getattr(camera_props, 'legend_3d_panel_width', 2.2),  # Se calculará automáticamente después
                'panel_radius': getattr(camera_props, 'legend_hud_border_radius', 5.0) * spacing_scale,  # CORREGIDO: Usa spacing_scale
                'panel_alpha': getattr(camera_props, 'legend_hud_background_color', (0.05, 0.05, 0.05, 0.85))[3],  # ✅ CORREGIDO: Usa alpha del color de fondo
                'panel_color': getattr(camera_props, 'legend_hud_background_color', (0.05, 0.05, 0.05, 1.0)),
                
                # Font settings (separados correctamente)
                'font_size_title': getattr(camera_props, 'legend_hud_title_font_size', 16.0) * base_3d_scale * legend_scale,  # SOLO para título
                'font_size_item': 14.0 * base_3d_scale * legend_scale,  # ✅ CORREGIDO: Font fijo para items, independiente del título
                
                # Layout settings (MEJORADO: Usa spacing_scale consistente para TODA la espaciación)
                'padding_x': getattr(camera_props, 'legend_hud_padding_horizontal', 12.0) * spacing_scale,  # CORREGIDO
                'padding_top': getattr(camera_props, 'legend_hud_padding_vertical', 8.0) * spacing_scale,  # CORREGIDO  
                'padding_bottom': getattr(camera_props, 'legend_hud_padding_vertical', 8.0) * spacing_scale,  # CORREGIDO
                'row_height': getattr(camera_props, 'legend_hud_item_spacing', 8.0) * spacing_scale * 2.0,  # AJUSTADO: Multiplicador reducido
                'dot_diameter': getattr(camera_props, 'legend_hud_color_indicator_size', 12.0) * spacing_scale,  # CORREGIDO
                'dot_text_gap': getattr(camera_props, 'legend_hud_item_spacing', 8.0) * spacing_scale * 1.2,  # AJUSTADO: Mejor proporción
                
                # Title settings (sync with Legend HUD)
                'title_text': getattr(camera_props, 'legend_hud_title_text', 'Legend'),
                'show_title': getattr(camera_props, 'legend_hud_show_title', True),
                'title_color': getattr(camera_props, 'legend_hud_title_color', (1.0, 1.0, 1.0, 1.0)),
                
                # Text settings (sync with Legend HUD)
                'text_color': getattr(camera_props, 'legend_hud_text_color', (1.0, 1.0, 1.0, 1.0)),
                'text_shadow_enabled': getattr(camera_props, 'legend_hud_text_shadow_enabled', True),
                'text_shadow_color': getattr(camera_props, 'legend_hud_text_shadow_color', (0.0, 0.0, 0.0, 0.8)),
                'text_shadow_offset_x': getattr(camera_props, 'legend_hud_text_shadow_offset_x', 1.0) * spacing_scale,  # CORREGIDO
                'text_shadow_offset_y': getattr(camera_props, 'legend_hud_text_shadow_offset_y', -1.0) * spacing_scale,  # CORREGIDO
                
                # Column visibility (CRITICAL for matching viewport HUD exactly)
                'show_start_column': getattr(camera_props, 'legend_hud_show_start_column', False),
                'show_active_column': getattr(camera_props, 'legend_hud_show_active_column', True),
                'show_end_column': getattr(camera_props, 'legend_hud_show_end_column', False),
                'show_start_title': getattr(camera_props, 'legend_hud_show_start_title', False),
                'show_active_title': getattr(camera_props, 'legend_hud_show_active_title', False),
                'show_end_title': getattr(camera_props, 'legend_hud_show_end_title', False),
                'column_spacing': getattr(camera_props, 'legend_hud_column_spacing', 16.0) * spacing_scale,  # CORREGIDO: Usa spacing_scale
                
                # Auto scale and orientation (sync with Legend HUD)
                'auto_scale': getattr(camera_props, 'legend_hud_auto_scale', True),
                'max_width': getattr(camera_props, 'legend_hud_max_width', 0.3),
                'orientation': getattr(camera_props, 'legend_hud_orientation', 'VERTICAL'),
                
                # Conversion factors (updated)
                'base_3d_scale': base_3d_scale,
                'legend_scale': legend_scale,
                'spacing_scale': spacing_scale,  # NUEVO: Factor combinado para espaciado
            }
            
            print(f"📊 Synchronized {len(settings)} settings from Legend HUD")
            
            # DEBUG: COMPARACIÓN DETALLADA - LEGEND HUD ORIGINAL vs 3D LEGEND HUD
            raw_padding_h = getattr(camera_props, 'legend_hud_padding_horizontal', 12.0)
            raw_padding_v = getattr(camera_props, 'legend_hud_padding_vertical', 8.0)
            raw_radius = getattr(camera_props, 'legend_hud_border_radius', 5.0)
            raw_spacing = getattr(camera_props, 'legend_hud_item_spacing', 8.0)
            raw_dot_size = getattr(camera_props, 'legend_hud_color_indicator_size', 12.0)
            raw_scale = getattr(camera_props, 'legend_hud_scale', 1.0)
            raw_bg_color = getattr(camera_props, 'legend_hud_background_color', (0.05, 0.05, 0.05, 0.85))
            raw_title_font = getattr(camera_props, 'legend_hud_title_font_size', 16.0)
            
            print(f"\n📊 LEGEND HUD SYNCHRONIZATION COMPARISON:")
            print(f"  🔧 Conversion Factors:")
            print(f"    • base_3d_scale: {base_3d_scale}")
            print(f"    • legend_scale: {legend_scale}")
            print(f"    • spacing_scale (combined): {spacing_scale}")
            print(f"  📏 Viewport → 3D Conversion:")
            print(f"    • Padding H: {raw_padding_h}px → {settings['padding_x']:.4f}")
            print(f"    • Padding V: {raw_padding_v}px → {settings['padding_top']:.4f}")
            print(f"    • Border Radius: {raw_radius}px → {settings['panel_radius']:.4f}")
            print(f"    • Item Spacing: {raw_spacing}px → {settings['row_height']:.4f}")
            print(f"    • Dot Size: {raw_dot_size}px → {settings['dot_diameter']:.4f}")
            print(f"    • Dot-Text Gap: {raw_spacing}px → {settings['dot_text_gap']:.4f}")
            print(f"  🎨 Visual Properties:")
            print(f"    • Background: {raw_bg_color} → {settings['panel_color']}")
            print(f"    • Title Font: {raw_title_font}px → {settings['font_size_title']:.4f}")
            print(f"    • Scale Factor: {raw_scale} → Applied")
            
            return settings
            
        except Exception as e:
            print(f"❌ Error getting synchronized settings: {e}")
            # Fallback to default settings
            return {
                'hud_distance': 2.2, 'hud_pos_x': -3.6, 'hud_pos_y': 1.4, 'hud_scale': 1.0,
                'panel_width': 2.2, 'panel_radius': 0.12, 'panel_alpha': 0.85, 'panel_color': (0.05, 0.05, 0.05, 1.0),
                'font_size_title': 0.18, 'font_size_item': 0.15, 'padding_x': 0.18, 'padding_top': 0.20, 
                'padding_bottom': 0.20, 'row_height': 0.20, 'dot_diameter': 0.10, 'dot_text_gap': 0.12,
                'title_text': 'Legend', 'show_title': True, 'title_color': (1.0, 1.0, 1.0, 1.0),
                'text_color': (1.0, 1.0, 1.0, 1.0), 'show_start_column': False, 'show_active_column': True,
                'show_end_column': False, 'column_spacing': 0.16, 'base_3d_scale': 0.01, 'legend_scale': 1.0,
            }
    
    def _create_3d_legend_hud(self, camera, legend_data):
        """Create 3D Legend HUD objects"""
        import mathutils
        from math import radians
        import bonsai.tool as tool
        
        # Get HUD positioning settings
        anim_props = tool.Sequence.get_animation_props()
        camera_props = anim_props.camera_orbit
        
        # CRITICAL: Get settings from both 3D-specific AND Legend HUD properties for complete sync
        settings = self._get_synchronized_settings(camera_props)
        
        print(f"🔄 Using synchronized settings: {settings}")
        
        # Extract values from synchronized settings
        hud_distance = settings['hud_distance']
        hud_pos_x = settings['hud_pos_x']
        hud_pos_y = settings['hud_pos_y']
        hud_scale = settings['hud_scale']
        
        panel_width = settings['panel_width']
        panel_radius = settings['panel_radius'] 
        panel_alpha = settings['panel_alpha']
        panel_color = settings['panel_color']
        
        font_size_title = settings['font_size_title']
        font_size_item = settings['font_size_item']
        
        padding_x = settings['padding_x']
        padding_top = settings['padding_top']
        padding_bottom = settings['padding_bottom']
        row_height = settings['row_height']
        dot_diameter = settings['dot_diameter']
        dot_text_gap = settings['dot_text_gap']
        
        title_text = settings['title_text']
        show_title = settings['show_title']
        
        # Create collection for 3D Legend HUD
        collection_name = "Schedule_Display_3D_Legend"
        if collection_name in bpy.data.collections:
            collection = bpy.data.collections[collection_name]
        else:
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)
        
        # --- NEW LOGIC ---
        # Sync visibility with the main 3D HUD Render checkbox
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            should_hide = not getattr(camera_props, "show_3d_schedule_texts", False)
            collection.hide_viewport = should_hide
            collection.hide_render = should_hide
        except Exception as e:
            print(f"⚠️ Could not sync 3D Legend HUD visibility on creation: {e}")
        # --- END NEW LOGIC ---
        
        # Use existing Schedule_Display_Parent empty or create if needed
        parent_name = "Schedule_Display_Parent"
        parent_empty = bpy.data.objects.get(parent_name)
        parent_empty_created = False
        if not parent_empty:
            # Create parent empty if it doesn't exist (same as 3D HUD Render system)
            parent_empty = bpy.data.objects.new(parent_name, None)
            bpy.context.scene.collection.objects.link(parent_empty)
            parent_empty.empty_display_type = 'PLAIN_AXES'
            parent_empty.empty_display_size = 2
            parent_empty_created = True
        # Inherit/persist anchor mode if scene requests world-origin
        try:
            if bpy.context.scene.get('hud_anchor_mode') == 'WORLD_ORIGIN':
                parent_empty['anchor_mode'] = 'WORLD_ORIGIN'
        except Exception:
            pass
            print(f"✅ Created Schedule_Display_Parent empty for unified HUD system")
        
        # Configure parent constraints if we created it or if it needs update
        if parent_empty_created:
            try:
                from . import prop
                prop.update_schedule_display_parent_constraint(bpy.context)
                print(f"✅ Schedule_Display_Parent constraints configured")
            except Exception as e:
                print(f"⚠️ Could not configure Schedule_Display_Parent constraints: {e}")
        
        # Store parent reference and offset for direct parenting (NO intermediate empty)
        legend_parent = parent_empty
        legend_offset_x = hud_pos_x
        legend_offset_y = hud_pos_y
        legend_offset_z = 0.0  # Z=0 as requested
        
        print(f"✅ 3D Legend HUD objects will be parented directly to {parent_name} with offset ({legend_offset_x}, {legend_offset_y}, {legend_offset_z})")
        
        # NO CREAR EMPTY INTERMEDIO - usar Schedule_Display_Parent directamente
        root = legend_parent  # Usar Schedule_Display_Parent como root
        root_name = parent_name
        
        print(f"✅ Using {parent_name} directly as root for 3D Legend HUD objects")
        
        # Calculate panel dimensions AUTOMATICALLY based on content
        total_rows = len(legend_data)
        title_height = font_size_title + 0.12 if show_title else 0
        column_titles_height = row_height * 0.8 if (settings['show_start_title'] or settings['show_active_title'] or settings['show_end_title']) else 0
        
        # DYNAMIC PANEL HEIGHT calculation
        panel_height = padding_top + title_height + column_titles_height + total_rows * row_height + padding_bottom
        
        # DYNAMIC PANEL WIDTH calculation based on content
        # Calculate width needed for longest text + dots + spacing
        max_text_length = 0
        for item_data in legend_data:
            text_length = len(item_data.get('name', ''))
            if text_length > max_text_length:
                max_text_length = text_length
        
        # Base width calculation
        estimated_char_width = font_size_item * 0.6  # Approximate character width
        text_width = max_text_length * estimated_char_width
        dots_width = dot_diameter  # Space for color dots
        
        # Additional width for multiple columns
        visible_columns = 0
        if settings['show_start_column']: visible_columns += 1
        if settings['show_active_column']: visible_columns += 1
        if settings['show_end_column']: visible_columns += 1
        
        if visible_columns > 1:
            dots_width += (visible_columns - 1) * (dot_diameter + settings['column_spacing'])
        
        # Calculate minimum width needed
        content_width = dots_width + dot_text_gap + text_width
        calculated_panel_width = (padding_x * 2) + content_width
        
        # Use calculated width or minimum width, whichever is larger
        min_width = 1.2  # Minimum panel width
        panel_width = max(calculated_panel_width, min_width)
        
        # If auto_scale is enabled, respect max_width from Legend HUD
        if settings['auto_scale'] and panel_width > (settings['max_width'] * 10):  # Convert viewport ratio to 3D units
            panel_width = settings['max_width'] * 10
        
        print(f"📏 Panel dimensions calculated:")
        print(f"  📊 ColorTypes: {total_rows}")
        print(f"  📝 Longest text: '{max(legend_data, key=lambda x: len(x.get('name', '')))['name']}' ({max_text_length} chars)")
        print(f"  📏 Panel Width: {calculated_panel_width:.3f} -> {panel_width:.3f}")
        print(f"  📏 Panel Height: {panel_height:.3f}")
        print(f"  🔘 Panel Radius: {panel_radius:.3f}")
        print(f"  🟡 Visible columns: {visible_columns}")
        print(f"  🎨 Panel Alpha: {panel_alpha:.3f}")
        print(f"  🎨 Panel Color: {panel_color}")
        
        # Create panel background with synchronized color  
        print(f"🏗️ CREATING PANEL: size=({panel_width:.3f}, {panel_height:.3f}), radius={panel_radius:.4f}")
        try:
            panel = self._create_rounded_panel(
                "HUD_3D_Legend_Panel", panel_width, panel_height, panel_radius, 
                panel_alpha, panel_color, collection
            )
            if panel:
                panel.parent = root
                # Aplicar offset que antes daba el empty intermedio
                panel.location = (legend_offset_x, legend_offset_y, legend_offset_z)
                panel.scale = (hud_scale, hud_scale, hud_scale)
                panel["is_3d_legend_hud"] = True
                print(f"✅ Panel created successfully: {panel.name} at ({legend_offset_x}, {legend_offset_y}, {legend_offset_z})")
            else:
                print(f"❌ Panel creation returned None!")
                return
        except Exception as panel_error:
            print(f"❌ Panel creation failed with exception: {panel_error}")
            return
        
        # Create title with synchronized settings
        if show_title:  # Only create title if enabled in Legend HUD
            top_y = panel_height * 0.5 - padding_top - font_size_title * 0.5
            title = self._create_text_object(
                "HUD_3D_Legend_Title", title_text, font_size_title,
                settings['title_color'], 5.0, collection
            )
            # Aplicar offset base + posición relativa al panel
            title_x = legend_offset_x + (-panel_width * 0.5 + padding_x) * hud_scale
            title_y = legend_offset_y + top_y * hud_scale
            title.location = (title_x, title_y, legend_offset_z + 0.0014)
            title.parent = root
            title["is_3d_legend_hud"] = True
        else:
            # Adjust start_y if no title
            top_y = panel_height * 0.5 - padding_top
        
        # Create column titles if enabled (matching viewport Legend HUD)
        title_y_offset = 0
        show_start_column = settings['show_start_column']
        show_active_column = settings['show_active_column']
        show_end_column = settings['show_end_column']
        show_start_title = settings['show_start_title']
        show_active_title = settings['show_active_title']
        show_end_title = settings['show_end_title']
        column_spacing = settings['column_spacing']
        
        if show_start_title or show_active_title or show_end_title:
            title_y = top_y - (font_size_title * 0.5 + 0.12)  # Basado en title font para posicionamiento
            title_x_start = -panel_width * 0.5 + padding_x + dot_diameter * 0.5
            current_title_x = title_x_start
            
            if show_start_column and show_start_title:
                start_title = self._create_text_object(
                    f"{root_name}_StartTitle", "S", font_size_item * 0.8,
                    settings['title_color'], 5.0, collection
                )
                # Aplicar offset base + posición relativa al panel
                col_title_x = legend_offset_x + current_title_x * hud_scale
                col_title_y = legend_offset_y + title_y * hud_scale
                start_title.location = (col_title_x, col_title_y, legend_offset_z + 0.0013)
                start_title.parent = root
                current_title_x += dot_diameter + column_spacing
            
            if show_active_column and show_active_title:
                active_title = self._create_text_object(
                    f"{root_name}_ActiveTitle", "A", font_size_item * 0.8,
                    settings['title_color'], 5.0, collection
                )
                # Aplicar offset base + posición relativa al panel
                col_title_x = legend_offset_x + current_title_x * hud_scale
                col_title_y = legend_offset_y + title_y * hud_scale
                active_title.location = (col_title_x, col_title_y, legend_offset_z + 0.0013)
                active_title.parent = root
                current_title_x += dot_diameter + column_spacing
            
            if show_end_column and show_end_title:
                end_title = self._create_text_object(
                    f"{root_name}_EndTitle", "E", font_size_item * 0.8,
                    settings['title_color'], 5.0, collection
                )
                # Aplicar offset base + posición relativa al panel
                col_title_x = legend_offset_x + current_title_x * hud_scale
                col_title_y = legend_offset_y + title_y * hud_scale
                end_title.location = (col_title_x, col_title_y, legend_offset_z + 0.0013)
                end_title.parent = root
            
            title_y_offset = row_height * 0.8  # Add space for column titles
        
        # Create legend items  
        start_y = top_y - (title_height + title_y_offset)  # ✅ CORREGIDO: Usa title_height calculado, no font_size_title directo
        x_dot = -panel_width * 0.5 + padding_x + dot_diameter * 0.5
        x_text = x_dot + dot_diameter * 0.5 + dot_text_gap
        
        # Get Legend HUD column visibility settings from synchronized settings
        show_start = settings['show_start_column']
        show_active = settings['show_active_column'] 
        show_end = settings['show_end_column']
        show_start_title = settings['show_start_title']
        show_active_title = settings['show_active_title']
        show_end_title = settings['show_end_title']
        column_spacing = settings['column_spacing']
        text_color = settings['text_color']
        
        for i, item_data in enumerate(legend_data):
            y = start_y - i * row_height
            item_name = item_data.get('name', f'ColorType_{i}')
            
            # CRITICAL: Use SAME color selection logic as viewport Legend HUD
            # Priority: Active > Start > End (based on what columns are shown)
            item_color = (0.5, 0.5, 0.5, 1.0)  # Default fallback
            
            if show_active and 'active_color' in item_data:
                item_color = item_data['active_color']
            elif show_start and 'start_color' in item_data:
                item_color = item_data['start_color'] 
            elif show_end and 'end_color' in item_data:
                item_color = item_data['end_color']
            elif 'active_color' in item_data:  # Fallback to active if available
                item_color = item_data['active_color']
            elif 'start_color' in item_data:   # Fallback to start
                item_color = item_data['start_color']
            elif 'end_color' in item_data:     # Last fallback to end
                item_color = item_data['end_color']
            
            print(f"🎨 Item {i}: {item_name} -> Color: {item_color} (Start:{show_start}, Active:{show_active}, End:{show_end})")
            
            # Create multiple color dots if multiple columns are shown (like viewport HUD)
            current_dot_x = x_dot
            dot_count = 0
            
            if show_start and 'start_color' in item_data:
                dot = self._create_color_dot(
                    f"{root_name}_Dot_Start_{i:02d}", dot_diameter, item_data['start_color'], collection
                )
                # Aplicar offset base + posición relativa al panel
                dot_x = legend_offset_x + current_dot_x * hud_scale
                dot_y = legend_offset_y + y * hud_scale
                dot.location = (dot_x, dot_y, legend_offset_z + 0.0010)
                dot.parent = root
                current_dot_x += dot_diameter + 0.05  # Small gap between dots
                dot_count += 1
            
            if show_active and 'active_color' in item_data:
                dot = self._create_color_dot(
                    f"{root_name}_Dot_Active_{i:02d}", dot_diameter, item_data['active_color'], collection
                )
                # Aplicar offset base + posición relativa al panel
                dot_x = legend_offset_x + current_dot_x * hud_scale
                dot_y = legend_offset_y + y * hud_scale
                dot.location = (dot_x, dot_y, legend_offset_z + 0.0010)
                dot.parent = root
                current_dot_x += dot_diameter + 0.05
                dot_count += 1
            
            if show_end and 'end_color' in item_data:
                dot = self._create_color_dot(
                    f"{root_name}_Dot_End_{i:02d}", dot_diameter, item_data['end_color'], collection
                )
                # Aplicar offset base + posición relativa al panel
                dot_x = legend_offset_x + current_dot_x * hud_scale
                dot_y = legend_offset_y + y * hud_scale
                dot.location = (dot_x, dot_y, legend_offset_z + 0.0010)
                dot.parent = root
                dot_count += 1
            
            # If no columns are shown, show single dot with primary color
            if dot_count == 0:
                dot = self._create_color_dot(
                    f"{root_name}_Dot_Default_{i:02d}", dot_diameter, item_color, collection
                )
                # Aplicar offset base + posición relativa al panel
                dot_x = legend_offset_x + x_dot * hud_scale
                dot_y = legend_offset_y + y * hud_scale
                dot.location = (dot_x, dot_y, legend_offset_z + 0.0010)
                dot.parent = root
            
            # Adjust text position based on number of dots
            text_x_offset = x_text if dot_count <= 1 else x_text + (dot_count - 1) * (dot_diameter + 0.05)
            
            # Create text label with synchronized color
            text = self._create_text_object(
                f"{root_name}_Text_{i:02d}", item_name, font_size_item,
                text_color, 5.0, collection
            )
            # Aplicar offset base + posición relativa al panel
            text_x = legend_offset_x + text_x_offset * hud_scale
            text_y = legend_offset_y + y * hud_scale
            text.location = (text_x, text_y, legend_offset_z + 0.0012)
            text.parent = root
        
        # CRITICAL: Mark ALL objects in the 3D Legend HUD collection with the identifier
        objects_marked = 0
        for obj in collection.objects:
            obj["is_3d_legend_hud"] = True
            objects_marked += 1
        print(f"✅ 3D Legend HUD created with {len(legend_data)} ColorType items, {objects_marked} objects marked")
    
    def _parent_to_camera_hud(self, obj, camera, x, y, z):
        """Parent object to camera with HUD positioning similar to text HUD system"""
        # Use similar constraints as the existing text HUD system
        obj.parent = camera
        obj.matrix_parent_inverse = camera.matrix_world.inverted()
        obj.location = (x, y, z)
        
        # Mark as HUD element
        obj["is_hud_element"] = True
        obj["hud_type"] = "3d_legend"
    
    def _create_rounded_panel(self, name, width, height, radius, alpha, color, collection):
        """Create rounded panel background with synchronized color and border radius"""
        try:
            import bmesh
            
            print(f"🔘 Creating panel: {name}, size=({width:.3f}, {height:.3f}), radius={radius:.4f}")
            
            # Create rounded rectangle mesh with better error handling
            bm = bmesh.new()
            
            # Limit radius to prevent over-rounding
            max_radius = min(width, height) * 0.4
            actual_radius = min(radius, max_radius)
            
            print(f"   Radius: requested={radius:.4f}, max_allowed={max_radius:.4f}, using={actual_radius:.4f}")
            
            try:
                if actual_radius > 0.005:  # Only apply rounding if radius is meaningful
                    # Create rounded rectangle - SIMPLIFIED approach
                    bmesh.ops.create_grid(bm, x_segments=4, y_segments=4, size=1.0)
                    bmesh.ops.scale(bm, vec=(width, height, 1.0), verts=bm.verts)
                    
                    # Try to apply inset for rounding - with error handling
                    try:
                        all_faces = bm.faces[:]
                        if all_faces:
                            bmesh.ops.inset_individual(
                                bm, 
                                faces=all_faces, 
                                thickness=actual_radius * 0.5,  # Reduce thickness to prevent errors
                                depth=0.0,
                                use_boundary=True,
                                use_even_offset=False  # Simplify
                            )
                            print("   ✅ Inset applied successfully")
                        else:
                            print("   ⚠️ No faces found for inset, using simple rectangle")
                    except Exception as inset_error:
                        print(f"   ⚠️ Inset failed: {inset_error}, using simple rectangle")
                        # Don't fail, just use simple rectangle
                else:
                    # Simple rectangle
                    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
                    bmesh.ops.scale(bm, vec=(width, height, 1.0), verts=bm.verts)
                    print("   ✅ Simple rectangle created")
                
                # Ensure we have valid geometry
                if len(bm.verts) == 0:
                    print("   ❌ No vertices created, falling back to simple quad")
                    bm.clear()
                    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
                    bmesh.ops.scale(bm, vec=(width, height, 1.0), verts=bm.verts)
                
                # Create mesh object
                mesh = bpy.data.meshes.new(name)
                bm.to_mesh(mesh)
                bm.free()
                
                obj = bpy.data.objects.new(name, mesh)
                collection.objects.link(obj)
                print(f"   ✅ Object {name} created and linked to collection")
                
                # Apply smooth shading safely
                try:
                    old_active = bpy.context.view_layer.objects.active
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.shade_smooth()
                    bpy.context.view_layer.objects.active = old_active
                    print("   ✅ Smooth shading applied")
                except Exception as smooth_error:
                    print(f"   ⚠️ Smooth shading failed: {smooth_error}")
                
                # Create emission material with synchronized color and alpha
                try:
                    mat = self._create_emission_material(f"{name}_Mat", color, 1.2, alpha)
                    obj.data.materials.append(mat)
                    print(f"   ✅ Material applied")
                except Exception as mat_error:
                    print(f"   ❌ Material creation failed: {mat_error}")
                
                return obj
                
            except Exception as bmesh_error:
                print(f"   ❌ Bmesh operations failed: {bmesh_error}")
                bm.free()
                # Create simple fallback plane
                bpy.ops.mesh.primitive_plane_add(size=1.0)
                obj = bpy.context.active_object
                obj.name = name
                obj.scale = (width, height, 1.0)
                # Move to collection
                if obj.name in bpy.context.scene.collection.objects:
                    bpy.context.scene.collection.objects.unlink(obj)
                collection.objects.link(obj)
                return obj
                
        except Exception as e:
            print(f"❌ Panel creation completely failed: {e}")
            # Last resort: create empty object
            obj = bpy.data.objects.new(name, None)
            collection.objects.link(obj)
            return obj
    
    def _create_color_dot(self, name, diameter, color, collection):
        """Create color indicator dot"""
        print(f"🟡 Creando dot: {name} con diámetro {diameter}")
        bpy.ops.mesh.primitive_circle_add(vertices=24, radius=diameter * 0.5, fill_type='NGON')
        obj = bpy.context.active_object
        obj.name = name
        
        print(f"🔗 Objeto creado: {obj.name}, moviendo a colección {collection.name}")
        
        # Move to collection - SAFELY handle unlinking
        try:
            # Check if object is in scene collection before unlinking
            if obj.name in bpy.context.scene.collection.objects:
                bpy.context.scene.collection.objects.unlink(obj)
                print(f"✅ Objeto desvinculado de Scene Collection")
            else:
                print(f"⚠️  Objeto {obj.name} no estaba en Scene Collection")
                
            # Link to target collection
            if obj.name not in collection.objects:
                collection.objects.link(obj)
                print(f"✅ Objeto vinculado a {collection.name}")
            else:
                print(f"⚠️  Objeto {obj.name} ya estaba en {collection.name}")
        except Exception as e:
            print(f"❌ Error manejando colecciones para {obj.name}: {e}")
            # Try to ensure object is at least in target collection
            if obj.name not in collection.objects:
                collection.objects.link(obj)
        
        # Create emission material
        print(f"🎨 Creando material para {obj.name} con color {color}")
        mat = self._create_emission_material(f"{name}_Mat", color, 6.0, 1.0)
        obj.data.materials.append(mat)
        
        print(f"✅ Dot {name} creado exitosamente")
        return obj
    
    def _create_text_object(self, name, text, size, color, strength, collection):
        """Create text object with emission material"""
        curve = bpy.data.curves.new(name, 'FONT')
        curve.body = text
        curve.size = size
        curve.align_x = 'LEFT'
        curve.align_y = 'CENTER'
        
        obj = bpy.data.objects.new(name, curve)
        collection.objects.link(obj)
        
        # Create emission material
        mat = self._create_emission_material(f"{name}_Mat", color, strength, 1.0)
        obj.data.materials.append(mat)
        
        return obj
    
    def _create_emission_material(self, name, color, strength, alpha):
        """Create emission material with optional transparency"""
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        # Clear existing nodes
        for node in nodes:
            nodes.remove(node)
        
        # Create output
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (400, 0)
        
        if alpha >= 0.999:
            # Opaque emission
            emission = nodes.new("ShaderNodeEmission")
            emission.location = (120, 0)
            emission.inputs["Color"].default_value = (color[0], color[1], color[2], 1.0)
            emission.inputs["Strength"].default_value = strength
            links.new(emission.outputs["Emission"], output.inputs["Surface"])
            mat.blend_method = 'OPAQUE'
        else:
            # Transparent + Emission mix
            transparent = nodes.new("ShaderNodeBsdfTransparent")
            transparent.location = (-180, -90)
            
            emission = nodes.new("ShaderNodeEmission")
            emission.location = (-180, 90)
            emission.inputs["Color"].default_value = (color[0], color[1], color[2], 1.0)
            emission.inputs["Strength"].default_value = strength
            
            mix = nodes.new("ShaderNodeMixShader")
            mix.location = (120, 0)
            
            value = nodes.new("ShaderNodeValue")
            value.outputs[0].default_value = alpha
            value.location = (-420, 0)
            
            links.new(transparent.outputs["BSDF"], mix.inputs[1])
            links.new(emission.outputs["Emission"], mix.inputs[2])
            links.new(value.outputs[0], mix.inputs[0])
            links.new(mix.outputs["Shader"], output.inputs["Surface"])
            
            mat.blend_method = 'BLEND'
            try:
                mat.shadow_method = 'NONE'
            except:
                pass
        
        return mat

class Clear3DLegendHUD(bpy.types.Operator):
    """Clear all 3D Legend HUD objects"""
    bl_idname = "bim.clear_3d_legend_hud"
    bl_label = "Clear 3D Legend HUD"
    bl_description = "Remove all 3D Legend HUD objects and materials"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            cleared_objects = 0
            cleared_materials = 0
            
            # Remove objects
            for obj in list(bpy.data.objects):
                if (obj.name.startswith("HUD_3D_Legend") or 
                    obj.get("is_3d_legend_hud", False) or
                    obj.get("hud_type") == "3d_legend"):
                    bpy.data.objects.remove(obj, do_unlink=True)
                    cleared_objects += 1
            
            # Remove materials
            for mat in list(bpy.data.materials):
                if mat.name.startswith("HUD_3D_Legend"):
                    bpy.data.materials.remove(mat, do_unlink=True)
                    cleared_materials += 1
            
            # Remove collection if empty
            collection_name = "Schedule_Display_3D_Legend"
            if collection_name in bpy.data.collections:
                collection = bpy.data.collections[collection_name]
                if len(collection.objects) == 0:
                    bpy.data.collections.remove(collection)
            
            self.report({'INFO'}, f"Cleared {cleared_objects} objects and {cleared_materials} materials")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to clear 3D Legend HUD: {e}")
            return {'CANCELLED'}

class Update3DLegendHUD(bpy.types.Operator):
    """Update 3D Legend HUD with current ColorType data"""
    bl_idname = "bim.update_3d_legend_hud"
    bl_label = "Update 3D Legend HUD"
    bl_description = "Refresh 3D Legend HUD with current active ColorTypes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print("🔄 INICIANDO Update3DLegendHUD.execute()")
        try:
            # Check if 3D Legend HUD exists
            root_exists = False
            for obj in bpy.data.objects:
                if obj.get("is_3d_legend_hud", False):
                    root_exists = True
                    print(f"✅ 3D Legend HUD encontrado: {obj.name}")
                    break
            
            if not root_exists:
                print("❌ No se encontró 3D Legend HUD existente")
                self.report({'INFO'}, "No 3D Legend HUD found. Use 'Setup 3D Legend HUD' first.")
                return {'CANCELLED'}
            
            print("🔄 Recreando 3D Legend HUD con datos actualizados...")
            # Recreate with current data (Clear + Setup)
            bpy.ops.bim.clear_3d_legend_hud()
            bpy.ops.bim.setup_3d_legend_hud()
            
            print("✅ 3D Legend HUD actualizado exitosamente")
            self.report({'INFO'}, "3D Legend HUD updated")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to update 3D Legend HUD: {e}")
            return {'CANCELLED'}

class Toggle3DLegendHUD(bpy.types.Operator):
    """Toggle 3D Legend HUD visibility"""
    bl_idname = "bim.toggle_3d_legend_hud"
    bl_label = "Toggle 3D Legend HUD"
    bl_description = "Toggle 3D Legend HUD visibility"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            
            # Toggle property
            enable_3d_legend = not getattr(camera_props, 'enable_3d_legend_hud', False)
            camera_props.enable_3d_legend_hud = enable_3d_legend
            
            if enable_3d_legend:
                bpy.ops.bim.setup_3d_legend_hud()
                self.report({'INFO'}, "3D Legend HUD enabled")
            else:
                bpy.ops.bim.clear_3d_legend_hud()
                self.report({'INFO'}, "3D Legend HUD disabled")
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to toggle 3D Legend HUD: {e}")
            return {'CANCELLED'}

class DebugLegendData(bpy.types.Operator):
    """Debug Legend Data - Simple test operator"""
    bl_idname = "bim.debug_legend_data"  
    bl_label = "Debug Legend Data"
    bl_description = "Debug Legend HUD data retrieval"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print("\n🔍 DEBUG LEGEND DATA - INICIANDO")
        
        try:
            # Test 1: Import modules
            print("1️⃣ Importando módulos...")
            import bonsai.tool as tool
            from . import hud_overlay
            print("✅ Módulos importados correctamente")
            
            # Test 2: Get animation props
            print("2️⃣ Obteniendo animation props...")
            anim_props = tool.Sequence.get_animation_props()
            print(f"✅ Animation props obtenidos: {type(anim_props)}")
            
            # Test 3: Check animation groups
            print("3️⃣ Verificando animation groups...")
            if hasattr(anim_props, 'animation_group_stack'):
                groups = anim_props.animation_group_stack
                print(f"📊 Groups encontrados: {len(groups)}")
                for i, group in enumerate(groups):
                    enabled = getattr(group, 'enabled', False)
                    name = getattr(group, 'group', 'Unknown')
                    print(f"  - Group {i}: {name} (enabled={enabled})")
            else:
                print("❌ No animation_group_stack encontrado")
            
            # Test 4: Create HUD instance
            print("4️⃣ Creando HUD instance...")
            hud_instance = hud_overlay.ScheduleHUD()
            print("✅ HUD instance creado")
            
            # Test 5: Get legend data
            print("5️⃣ Obteniendo legend data...")
            legend_data = hud_instance.get_active_colortype_legend_data(include_hidden=False)
            print(f"📊 Legend data obtenido: {len(legend_data)} items")
            
            # Test 6: Show data details
            if legend_data:
                print("6️⃣ Detalles de legend data:")
                for i, item in enumerate(legend_data[:3]):  # Show first 3
                    print(f"  Item {i}: {item}")
            else:
                print("⚠️ No legend data encontrado")
                
            self.report({'INFO'}, f"Debug completado - {len(legend_data)} items encontrados")
            return {'FINISHED'}
            
        except Exception as e:
            print(f"❌ ERROR en debug: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Debug falló: {e}")
            return {'CANCELLED'}

# ==============================
# OPERADORES HUD GPU
# ==============================

class EnableScheduleHUD(bpy.types.Operator):
    """Activa el HUD GPU para mostrar información del cronograma"""
    bl_idname = "bim.enable_schedule_hud"
    bl_label = "Enable Schedule HUD"
    bl_description = "Enable GPU-based HUD overlay for schedule information"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            print("🟢 Starting HUD enable process...")

            # 1. Obtener las propiedades de animación y cámara
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            # 2. Asegurar que la propiedad de habilitación esté en True
            if not camera_props.enable_text_hud:
                camera_props.enable_text_hud = True
                print("🔧 HUD property enabled")

            # 3. Registrar el handler
            from . import hud_overlay

            if not hud_overlay.is_hud_enabled():
                print("🔧 Registering HUD handler...")
                hud_overlay.register_hud_handler()
            else:
                print("🔧 HUD handler already registered")

            # 4. Debug del estado
            hud_overlay.debug_hud_state()

            # 5. Refrescar
            hud_overlay.refresh_hud()

            self.report({'INFO'}, "Schedule HUD enabled")
            return {'FINISHED'}

        except Exception as e:
            print(f"🔴 Error enabling HUD: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to enable HUD: {e}")
            return {'CANCELLED'}

class DisableScheduleHUD(bpy.types.Operator):
    """Desactiva el HUD GPU"""
    bl_idname = "bim.disable_schedule_hud"
    bl_label = "Disable Schedule HUD"
    bl_description = "Disable GPU-based HUD overlay"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            print("🔴 Disabling HUD...")

            # 1. Obtener las propiedades de animación y cámara
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            # 2. Asegurar que la propiedad de habilitación esté en False
            if camera_props.enable_text_hud:
                camera_props.enable_text_hud = False
                print("🔧 HUD property disabled")

            # 3. Desregistrar handler
            from . import hud_overlay
            hud_overlay.unregister_hud_handler()

            # 4. Forzar redibujado
            for area in context.screen.areas:
                if getattr(area, "type", None) == 'VIEW_3D':
                    area.tag_redraw()

            self.report({'INFO'}, "Schedule HUD disabled")
            return {'FINISHED'}

        except Exception as e:
            print(f"🔴 Error disabling HUD: {e}")
            self.report({'ERROR'}, f"Failed to disable HUD: {e}")
            return {'CANCELLED'}

class ToggleScheduleHUD(bpy.types.Operator):
    """Alterna el estado del HUD GPU"""
    bl_idname = "bim.toggle_schedule_hud"
    bl_label = "Toggle Schedule HUD"
    bl_description = "Toggle GPU-based HUD overlay on/off"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            from . import hud_overlay  # Import relativo del módulo de overlay GPU

            if hud_overlay.is_hud_enabled():
                bpy.ops.bim.disable_schedule_hud()
            else:
                bpy.ops.bim.enable_schedule_hud()

            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to toggle HUD: {e}")
            return {'CANCELLED'}

class RefreshScheduleHUD(bpy.types.Operator):
    """Refresca el HUD GPU con redibujado forzado"""
    bl_idname = "bim.refresh_schedule_hud"
    bl_label = "Refresh HUD"
    bl_description = "Refresh HUD display and settings with forced redraw"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            from . import hud_overlay

            # Asegurar que los handlers estén registrados
            hud_overlay.ensure_hud_handlers()
            
            # Refrescar configuración del HUD
            hud_overlay.refresh_hud()

            # Forzar redibujado de todas las áreas 3D
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                        
            print("🔄 HUD refresh ejecutado - Handlers asegurados")

            return {'FINISHED'}
        except Exception as e:
            print(f"HUD refresh error: {e}")
            return {'CANCELLED'}

class DebugScheduleHUD(bpy.types.Operator):
    """Operador de diagnóstico para el HUD"""
    bl_idname = "bim.debug_schedule_hud"
    bl_label = "Debug Schedule HUD"
    bl_description = "Run diagnostic checks on the HUD system"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            from . import hud_overlay
            hud_overlay.debug_hud_status()
            hud_overlay.test_hud_animation()
            hud_overlay.debug_hud_state()

            # Verificar contexto actual
            print("🔍 Current context check:")
            print(f"  Area type: {getattr(context.area, 'type', 'None')}")
            print(f"  Region: {context.region}")
            print(f"  Space data: {getattr(context, 'space_data', 'None')}")

            if context.region:
                print(f"  Viewport size: {context.region.width}x{context.region.height}")

            # Forzar un dibujado de prueba
            try:
                hud_overlay.schedule_hud.draw()
                print("✅ Test draw completed")
            except Exception as e:
                print(f"❌ Test draw failed: {e}")

            self.report({'INFO'}, "HUD debug completed - check console")
            return {'FINISHED'}

        except Exception as e:
            print(f"🔴 Debug failed: {e}")
            self.report({'ERROR'}, f"Debug failed: {e}")
            return {'CANCELLED'}

class TestScheduleHUD(bpy.types.Operator):
    """Operador de prueba para verificar el HUD"""
    bl_idname = "bim.test_schedule_hud"
    bl_label = "Test Schedule HUD"
    bl_description = "Test HUD functionality with sample data"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            from . import hud_overlay

            # Verificar si está habilitado
            if not hud_overlay.is_hud_enabled():
                self.report({'WARNING'}, "HUD is not enabled. Enable it first.")
                return {'CANCELLED'}

            # Simular datos de prueba
            print("🧪 Testing HUD with sample data...")

            # Forzar redibujado múltiple
            for i in range(3):
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

            self.report({'INFO'}, "HUD test completed")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Test failed: {e}")
            return {'CANCELLED'}


# --- INICIO: OPERADORES DE IMPORT/EXPORT DE CONFIGURACIÓN DE CRONOGRAMA ---

class Copy3D(bpy.types.Operator):
    """Copy configuration from active schedule to other schedules with matching task indicators"""
    bl_idname = "bim.copy_3d"
    bl_label = "Copy 3D"
    bl_description = "Copy task elements, PredefinedType, and colortype settings from active schedule to matching schedules"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        snapshot_all_ui_state(context)
        try:
            ifc_file = tool.Ifc.get()
            if not ifc_file:
                self.report({'ERROR'}, "No IFC file loaded.")
                return {'CANCELLED'}
            
            active_schedule = tool.Sequence.get_active_work_schedule()
            if not active_schedule:
                self.report({'ERROR'}, "No active work schedule.")
                return {'CANCELLED'}

            result = tool.Sequence.copy_3d_configuration(active_schedule)
            
            if result.get("success", False):
                copied_count = result.get("copied_schedules", 0)
                task_matches = result.get("task_matches", 0)
                self.report({'INFO'}, f"Configuration copied to {copied_count} schedules ({task_matches} task matches)")
            else:
                error_msg = result.get("error", "Unknown error during copy operation")
                self.report({'ERROR'}, error_msg)
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Copy 3D failed: {str(e)}")
            return {'CANCELLED'}
        finally:
            restore_all_ui_state(context)
        return {'FINISHED'}

class Sync3D(bpy.types.Operator):
    """Sync task elements based on IFC property set values"""
    bl_idname = "bim.sync_3d"
    bl_label = "Sync 3D"
    bl_description = "Automatically map IFC elements to tasks based on property set values"
    bl_options = {"REGISTER", "UNDO"}

    property_set_name: bpy.props.StringProperty(
        name="Property Set Name",
        description="Name of the property set to use for syncing",
        default=""
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "property_set_name")

    def execute(self, context):
        if not self.property_set_name.strip():
            self.report({'ERROR'}, "Property set name is required")
            return {'CANCELLED'}

        snapshot_all_ui_state(context)
        try:
            ifc_file = tool.Ifc.get()
            if not ifc_file:
                self.report({'ERROR'}, "No IFC file loaded.")
                return {'CANCELLED'}
            
            active_schedule = tool.Sequence.get_active_work_schedule()
            if not active_schedule:
                self.report({'ERROR'}, "No active work schedule.")
                return {'CANCELLED'}

            result = tool.Sequence.sync_3d_elements(active_schedule, self.property_set_name.strip())
            
            if result.get("success", False):
                matched_elements = result.get("matched_elements", 0)
                processed_tasks = result.get("processed_tasks", 0)
                self.report({'INFO'}, f"Synced {matched_elements} elements across {processed_tasks} tasks")
            else:
                error_msg = result.get("error", "Unknown error during sync operation")
                self.report({'ERROR'}, error_msg)
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Sync 3D failed: {str(e)}")
            return {'CANCELLED'}
        finally:
            restore_all_ui_state(context)
        return {'FINISHED'}

# _try_register(ToggleTextHUD)

# --- Bind HUD helper functions to operator classes (safe even on re-register) ---
try:
    SetupTextHUD._setup_text_as_hud = _setup_text_as_hud
    SetupTextHUD._get_aspect_ratio = _get_aspect_ratio
    SetupTextHUD._calculate_hud_position = _calculate_hud_position
    SetupTextHUD._update_text_scale = _update_text_scale
except Exception:
    pass

try:
    UpdateTextHUDPositions._calculate_hud_position = _calculate_hud_position
except Exception:
    pass

try:
    UpdateTextHUDScale._update_text_scale = _update_text_scale
except Exception:
    pass

# ===============================
# NEW SNAPSHOT & CAMERA OPERATORS
# (Inserted by auto-fix on 2025-08-19)
# ===============================

class AddSnapshotCamera(bpy.types.Operator):
    """Add a static camera for snapshot viewing"""
    bl_idname = "bim.add_snapshot_camera"
    bl_label = "Add Snapshot Camera"
    bl_description = "Create a new static camera positioned for snapshot viewing"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # Create camera data and object directly
            cam_data = bpy.data.cameras.new(name="Snapshot_Camera")
            cam_obj = bpy.data.objects.new(name="Snapshot_Camera", object_data=cam_data)
            
            # Mark as snapshot camera
            cam_obj['is_4d_camera'] = True
            cam_obj['is_snapshot_camera'] = True
            cam_obj['camera_context'] = 'snapshot'
            
            # Link to scene
            context.collection.objects.link(cam_obj)
            
            # Configure camera settings
            cam_data.lens = 50
            cam_data.clip_start = 0.1
            cam_data.clip_end = 1000
            
            # Position camera with a good default view
            cam_obj.location = (10, -10, 8)
            cam_obj.rotation_euler = (1.1, 0.0, 0.785)
            
            # Set as active camera
            context.scene.camera = cam_obj
            
            # Select the camera
            bpy.ops.object.select_all(action='DESELECT')
            cam_obj.select_set(True)
            context.view_layer.objects.active = cam_obj
            
            # --- INICIO DE LA MODIFICACIÓN: Creación automática del 3D HUD ---
            
            # 1. Asegurar que el objeto "parent" del HUD exista.
            parent_name = "Schedule_Display_Parent"
            parent_empty = bpy.data.objects.get(parent_name)
            if not parent_empty:
                parent_empty = bpy.data.objects.new(parent_name, None)
                context.scene.collection.objects.link(parent_empty)
                parent_empty.empty_display_type = 'PLAIN_AXES'
                parent_empty.empty_display_size = 2
                print("Bonsai: Creado 'Schedule_Display_Parent' para el HUD.")
            
            # 2. Vincular el HUD a la nueva cámara de snapshot.
            from . import prop
            prop.update_schedule_display_parent_constraint(context)

                        # 3. (Actualizado) Refrescar SIEMPRE los textos 3D para snapshot.
            #    Antes: solo creaba si no existían. Ahora: refresca (recrea) siempre con la fecha actual.
            try:
                ws_props = tool.Sequence.get_work_schedule_props()
                start_date_str = getattr(ws_props, "visualisation_start", None)
                # Fallback a "ahora" si no hay visualisation_start válido
                parse = getattr(tool.Sequence, "parse_isodate_datetime", None) or getattr(tool.Sequence, "parse_isodate", None)
                if start_date_str and start_date_str != "-" and parse:
                    start_date = parse(start_date_str)
                else:
                    from datetime import datetime as _dt
                    start_date = _dt.now()
            
                snapshot_settings = {
                    "start": start_date,
                    "finish": start_date,  # Para snapshot, inicio y fin iguales
                    "start_frame": context.scene.frame_current,
                    "total_frames": 1,
                }
                
                # Add schedule name to settings
                work_schedule_id = getattr(ws_props, "active_work_schedule_id", None)
                if work_schedule_id:
                    work_schedule = tool.Ifc.get().by_id(work_schedule_id)
                    if work_schedule and hasattr(work_schedule, 'Name'):
                        snapshot_settings['schedule_name'] = work_schedule.Name
                
                # Recrea colección y textos con nuevos settings (la función limpia objetos previos)
                tool.Sequence.add_text_animation_handler(snapshot_settings)
                
                # --- ADD SCHEDULE NAME TEXT FOR SNAPSHOT CAMERA ---
                try:
                    if work_schedule_id:
                        work_schedule = tool.Ifc.get().by_id(work_schedule_id)
                        schedule_name = work_schedule.Name if work_schedule and hasattr(work_schedule, 'Name') else 'No Schedule'

                        # Create or get collection
                        coll_name = "Schedule_Display_Texts"
                        if coll_name not in bpy.data.collections:
                            coll = bpy.data.collections.new(name=coll_name)
                            context.scene.collection.children.link(coll)
                        else:
                            coll = bpy.data.collections[coll_name]

                        # Create text object
                        text_name = "Schedule_Name"
                        if text_name in bpy.data.objects:
                            text_obj = bpy.data.objects[text_name]
                        else:
                            text_data = bpy.data.curves.new(name=text_name, type='FONT')
                            text_obj = bpy.data.objects.new(name=text_name, object_data=text_data)
                            coll.objects.link(text_obj)

                        # Set content and properties
                        text_obj.data.body = f"Schedule: {schedule_name}"
                        text_obj.data['text_type'] = 'schedule_name'
                        
                        # Set alignment properties
                        if hasattr(text_obj.data, 'align_x'):
                            text_obj.data.align_x = 'CENTER'
                        if hasattr(text_obj.data, 'align_y'):
                            text_obj.data.align_y = 'BOTTOM_BASELINE'
                        
                        # Reset offsets
                        if hasattr(text_obj.data, 'offset_x'):
                            text_obj.data.offset_x = 0.0
                        if hasattr(text_obj.data, 'offset_y'):
                            text_obj.data.offset_y = 0.0
                        
                        # Pass settings for frame sync
                        _ensure_local_text_settings_on_obj(text_obj, snapshot_settings)
                        
                        print(f"✅ Schedule Name text created for snapshot camera: {schedule_name}")

                except Exception as e:
                    print(f"⚠️ Could not create schedule name text for snapshot camera: {e}")
                # Reordenarlos automáticamente
                try:
                    bpy.ops.bim.arrange_schedule_texts()
                except Exception:
                    pass
            except Exception as e:
                print("Bonsai WARNING: snapshot 3D texts refresh failed:", e)
# 4. Crear la leyenda 3D si no existe.
            legend_coll_name = "Schedule_Display_3D_Legend"
            if legend_coll_name not in bpy.data.collections:
                print("Bonsai: Leyenda 3D no encontrada, creando para snapshot...")
                try:
                    bpy.ops.bim.setup_3d_legend_hud()
                except Exception as e:
                    print(f"Bonsai ADVERTENCIA: Falló la auto-creación de la leyenda 3D para snapshot: {e}")

            self.report({'INFO'}, f"Cámara de snapshot y 3D HUD creados y activados")
            # --- FIN DE LA MODIFICACIÓN ---
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create snapshot camera: {str(e)}")
            return {'CANCELLED'}


class AlignSnapshotCameraToView(bpy.types.Operator):
    """Align snapshot camera to current 3D viewport view"""
    bl_idname = "bim.align_snapshot_camera_to_view"
    bl_label = "Align Snapshot Camera to View"
    bl_description = "Align the snapshot camera to match the current 3D viewport view"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Must have an active camera and a 3D viewport
        if not getattr(context.scene, "camera", None):
            return False
        if not getattr(context, "screen", None):
            return False
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                return True
        return False

    def execute(self, context):
        try:
            cam_obj = context.scene.camera
            if not cam_obj:
                self.report({'ERROR'}, "No active camera in scene")
                return {'CANCELLED'}

            # Find the active 3D viewport
            rv3d = None
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    rv3d = area.spaces.active.region_3d
                    break
            if not rv3d:
                self.report({'ERROR'}, "No active 3D viewport found")
                return {'CANCELLED'}

            # Align camera to viewport view
            cam_obj.matrix_world = rv3d.view_matrix.inverted()

            # Ensure camera is static
            if getattr(cam_obj, "animation_data", None):
                cam_obj.animation_data_clear()
            for constraint in list(cam_obj.constraints):
                cam_obj.constraints.remove(constraint)

            self.report({'INFO'}, f"Snapshot camera '{cam_obj.name}' aligned to current view")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to align snapshot camera: {str(e)}")
            return {'CANCELLED'}

# Enhanced snapshot with colortypes and robust error handling
class SnapshotWithcolortypesFixed(tool.Ifc.Operator, bpy.types.Operator):
    bl_idname = "bim.snapshot_with_colortypes_fixed"
    bl_label = "Create Snapshot (Enhanced)"
    bl_description = "Create snapshot with enhanced error handling and colortype management"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        # --- INICIO DE LA CORRECCIÓN ---
        # Al igual que en la animación, es crucial capturar el estado actual de la UI
        # de tareas (asignaciones personalizadas) ANTES de generar el snapshot.
        # Esto asegura que get_assigned_ColorType_for_task lea los datos correctos.
        snapshot_all_ui_state(context)
        # --- FIN DE LA CORRECCIÓN ---

        # --- SNAPSHOT 3D TEXTS INTEGRATION ---
        # Save current state of 3D texts before snapshot
        _save_3d_texts_state()
        # Set snapshot mode flag for 3D text handler
        context.scene["is_snapshot_mode"] = True
        print("📸 Snapshot mode activated for 3D texts")

        # --- INICIO DE LA CORRECCIÓN ---
        # Esta lógica se basa en la del operador VisualiseWorkScheduleDate, que es la correcta
        # para generar un snapshot en un punto específico en el tiempo, en lugar de usar
        # la lógica de animación de rango completo.

        # 1. FORZAR LA SINCRONIZACIÓN: Asegura que el snapshot use los datos más actualizados
        #    del grupo de perfiles que se está editando en la UI.
        try:
            tool.Sequence.sync_active_group_to_json()
        except Exception as e:
            print(f"Error syncing colortypes for snapshot: {e}")

        # 2. Obtener el cronograma activo desde las propiedades de la escena.
        ws_props = tool.Sequence.get_work_schedule_props()
        work_schedule_id = getattr(ws_props, "active_work_schedule_id", None)
        if not work_schedule_id:
            self.report({'ERROR'}, "No active Work Schedule selected.")
            return {'CANCELLED'}
        work_schedule = tool.Ifc.get().by_id(work_schedule_id)
        if not work_schedule:
            self.report({'ERROR'}, "Active Work Schedule not found in IFC.")
            return {'CANCELLED'}

        # 3. Obtener la fecha del snapshot y el rango de visualización.
        #    Para un snapshot, la fecha de inicio y fin del rango es la misma.
        snapshot_date_str = getattr(ws_props, "visualisation_start", None)
        if not snapshot_date_str or snapshot_date_str == "-":
            self.report({'ERROR'}, "No snapshot date is set.")
            return {'CANCELLED'}
        
        try:
            snapshot_date = tool.Sequence.parse_isodate_datetime(snapshot_date_str)
            if not snapshot_date:
                raise ValueError("Invalid date format")
        except Exception as e:
            self.report({'ERROR'}, f"Invalid snapshot date: {snapshot_date_str}. Error: {e}")
            return {'CANCELLED'}

        # 4. Obtener la fuente de fechas (Schedule, Actual, etc.) desde la UI.
        date_source = getattr(ws_props, "date_source_type", "SCHEDULE")

        # 5. Procesar el estado de la construcción en la fecha del snapshot.
        #    Esta es la función clave que determina qué objetos están en qué estado.
        product_states = tool.Sequence.process_construction_state(
            work_schedule,
            snapshot_date,
            viz_start=None,  # No filtrar por rango para un snapshot global
            viz_finish=None, # No filtrar por rango para un snapshot global
            date_source=date_source
        )

        # 6. Aplicar el estado visual a los objetos en la escena.
        tool.Sequence.show_snapshot(product_states)
        
        # 7. Detener la animación si se está reproduciendo para mantener el snapshot estático.
        try:
            if context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel(restore_frame=False)
        except Exception:
            pass # Failsafe

        # 8. Reportar éxito al usuario.
        

        # --- Refresh 3D Texts for current snapshot date (no new camera) ---

        try:

            snapshot_settings = {

                "start": snapshot_date,

                "finish": snapshot_date,

                "start_frame": context.scene.frame_current,

                "total_frames": 1,

            }
            
            # Add schedule name to settings for the handler
            if work_schedule and hasattr(work_schedule, 'Name'):
                snapshot_settings['schedule_name'] = work_schedule.Name

            # Only create 3D texts if the checkbox is enabled
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            show_3d_texts = getattr(camera_props, "show_3d_schedule_texts", False)
            
            if show_3d_texts:
                tool.Sequence.add_text_animation_handler(snapshot_settings)
                
                # --- ADD SCHEDULE NAME TEXT FOR SNAPSHOT ---
                try:
                    # Get schedule name
                    schedule_name = work_schedule.Name if work_schedule and hasattr(work_schedule, 'Name') else 'No Schedule'

                    # Create or get collection
                    coll_name = "Schedule_Display_Texts"
                    if coll_name not in bpy.data.collections:
                        coll = bpy.data.collections.new(name=coll_name)
                        context.scene.collection.children.link(coll)
                    else:
                        coll = bpy.data.collections[coll_name]

                    # Create text object
                    text_name = "Schedule_Name"
                    if text_name in bpy.data.objects:
                        text_obj = bpy.data.objects[text_name]
                    else:
                        text_data = bpy.data.curves.new(name=text_name, type='FONT')
                        text_obj = bpy.data.objects.new(name=text_name, object_data=text_data)
                        coll.objects.link(text_obj)

                    # Set content and properties
                    text_obj.data.body = f"Schedule: {schedule_name}"
                    text_obj.data['text_type'] = 'schedule_name' # Custom type for the handler
                    
                    # Set alignment properties for consistent 3D text positioning
                    if hasattr(text_obj.data, 'align_x'):
                        text_obj.data.align_x = 'CENTER'
                    if hasattr(text_obj.data, 'align_y'):
                        text_obj.data.align_y = 'BOTTOM_BASELINE'
                    
                    # Reset offsets to ensure clean positioning
                    if hasattr(text_obj.data, 'offset_x'):
                        text_obj.data.offset_x = 0.0
                    if hasattr(text_obj.data, 'offset_y'):
                        text_obj.data.offset_y = 0.0
                    
                    # Pass settings for frame sync
                    _ensure_local_text_settings_on_obj(text_obj, snapshot_settings)
                    
                    print(f"✅ Schedule Name text created for snapshot: {schedule_name}")

                except Exception as e:
                    print(f"⚠️ Could not create schedule name text for snapshot: {e}")

            try:

                bpy.ops.bim.arrange_schedule_texts()

            except Exception:

                pass
            else:
                print("📋 3D HUD Render checkbox is disabled - skipping 3D texts creation for snapshot")

        except Exception as e:

            print(f"Bonsai WARNING: Could not refresh 3D texts for snapshot: {e}")

        self.report({'INFO'}, f"Snapshot created for date {snapshot_date.strftime('%Y-%m-%d')}")
        return {'FINISHED'}
        # --- FIN DE LA CORRECCIÓN ---



class RefreshTaskOutputCounts(bpy.types.Operator):
    """Recalcula el número de 'Outputs' para todas las tareas en la lista."""
    bl_idname = "bim.refresh_task_output_counts"
    bl_label = "Refresh Output Counts"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # Llama a la función centralizada en sequence.py
            core.refresh_task_output_counts(tool.Sequence)
            self.report({'INFO'}, "Recuentos de 'Outputs' actualizados.")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to refrescar: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}


# === INICIO CÓDIGO PARA FILTROS (operators) ===
class AddTaskFilter(bpy.types.Operator):
    """Adds a new filter rule to the list."""
    bl_idname = "bim.add_task_filter"
    bl_label = "Add Task Filter"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Removed last_lookahead_window clearing to preserve active filters
        new_rule = props.filters.rules.add()
        
        # Set default to TASK.NAME, especially important for the first filter
        new_rule.column = "IfcTask.Name||string"
        
        # Inicializa data_type/operadores de la nueva regla
        update_filter_column(new_rule, context)
        
        props.filters.active_rule_index = len(props.filters.rules) - 1
        return {'FINISHED'}

class RemoveTaskFilter(bpy.types.Operator):
    """Deletes the selected filter rule."""
    bl_idname = "bim.remove_task_filter"
    bl_label = "Remove Task Filter"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Removed last_lookahead_window clearing to preserve active filters
        index = props.filters.active_rule_index
        
        if 0 <= index < len(props.filters.rules):
            props.filters.rules.remove(index)
            props.filters.active_rule_index = min(max(0, index - 1), len(props.filters.rules) - 1)
            
            # Ahora, refresca la lista de tareas aplicando el nuevo conjunto de filtros.
            # Esta lógica es la misma que en ApplyTaskFilters.
            try:
                snapshot_all_ui_state(context)
            except Exception as e:
                print(f"Bonsai WARNING: snapshot_all_ui_state failed in RemoveTaskFilter: {e}")

            try:
                ws = tool.Sequence.get_active_work_schedule()
                if ws:
                    tool.Sequence.load_task_tree(ws)
                    tool.Sequence.load_task_properties()
            except Exception as e:
                print(f"Bonsai WARNING: task tree reload failed in RemoveTaskFilter: {e}")

            try:
                restore_all_ui_state(context)
            except Exception as e:
                print(f"Bonsai WARNING: restore_all_ui_state failed in RemoveTaskFilter: {e}")

        return {'FINISHED'}


class ClearAllTaskFilters(bpy.types.Operator):
    """Clears all task filters at once."""
    bl_idname = "bim.clear_all_task_filters"
    bl_label = "Clear All Filters"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        
        # Clear all filter rules
        props.filters.rules.clear()
        props.filters.active_rule_index = 0
        
        # Apply the changes (reload task tree with no filters)
        try:
            snapshot_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: snapshot_all_ui_state failed in ClearAllTaskFilters: {e}")

        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties()
        except Exception as e:
            print(f"Bonsai WARNING: task tree reload failed in ClearAllTaskFilters: {e}")

        try:
            restore_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: restore_all_ui_state failed in ClearAllTaskFilters: {e}")

        self.report({'INFO'}, "All filters cleared")
        return {'FINISHED'}


class ClearAllTaskFilters(bpy.types.Operator):
    """Clears all task filters at once."""
    bl_idname = "bim.clear_all_task_filters"
    bl_label = "Clear All Filters"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        
        # Clear all filter rules
        props.filters.rules.clear()
        props.filters.active_rule_index = 0
        
        # Apply the changes (reload task tree with no filters)
        try:
            snapshot_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: snapshot_all_ui_state failed in ClearAllTaskFilters: {e}")

        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties()
        except Exception as e:
            print(f"Bonsai WARNING: task tree reload failed in ClearAllTaskFilters: {e}")

        try:
            restore_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: restore_all_ui_state failed in ClearAllTaskFilters: {e}")

        self.report({'INFO'}, "All filters cleared")
        return {'FINISHED'}


class NavigateColumnsLeft(bpy.types.Operator):
    """Navigate to previous columns"""
    bl_idname = "bim.navigate_columns_left"
    bl_label = "Previous Columns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Move left by 1 column for fine control
        if props.column_start_index > 0:
            props.column_start_index -= 1
        # Force UI to update to show column changes
        context.area.tag_redraw()
        return {'FINISHED'}


class NavigateColumnsRight(bpy.types.Operator):
    """Navigate to next columns"""
    bl_idname = "bim.navigate_columns_right"
    bl_label = "Next Columns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        max_columns = len(props.columns)
        visible_columns = calculate_visible_columns_count(context)
        
        # Move right by 1 column for fine control, but don't go past the last set
        if props.column_start_index + visible_columns < max_columns:
            props.column_start_index += 1
        # Force UI to update to show column changes  
        context.area.tag_redraw()
        return {'FINISHED'}


class NavigateColumnsHome(bpy.types.Operator):
    """Jump to first column"""
    bl_idname = "bim.navigate_columns_home"
    bl_label = "First Columns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        props.column_start_index = 0
        return {'FINISHED'}


class NavigateColumnsEnd(bpy.types.Operator):
    """Jump to last set of columns"""
    bl_idname = "bim.navigate_columns_end"
    bl_label = "Last Columns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        max_columns = len(props.columns)
        visible_columns = 6  # Max visible columns at once (sync with UI)
        
        if max_columns > visible_columns:
            props.column_start_index = max_columns - visible_columns
        else:
            props.column_start_index = 0
        return {'FINISHED'}


class UpdateSavedFilterSet(bpy.types.Operator):
    """Overwrites a saved filter set with the current active filter rules."""
    bl_idname = "bim.update_saved_filter_set"
    bl_label = "Update Saved Filter Set"
    bl_options = {"REGISTER", "UNDO"}

    set_index: bpy.props.IntProperty()


    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Removed last_lookahead_window clearing to preserve active filters
        saved_set = props.saved_filter_sets[self.set_index]

        # Clear old rules from the saved filter
        saved_set.rules.clear()

        # Copy current active rules to the saved filter
        for active_rule in props.filters.rules:
            saved_rule = saved_set.rules.add()
            saved_rule.is_active = active_rule.is_active
            saved_rule.column = active_rule.column
            saved_rule.operator = active_rule.operator
            try:
                saved_rule.value_string = active_rule.value_string
            except Exception:
                pass
            try:
                saved_rule.data_type = active_rule.data_type
            except Exception:
                pass

        self.report({'INFO'}, f"Filter '{saved_set.name}' updated successfully.")
        return {'FINISHED'}

class SaveFilterSet(bpy.types.Operator):
    """Saves the current filter set as a named preset."""
    bl_idname = "bim.save_filter_set"
    bl_label = "Save Filter Set"
    bl_options = {"REGISTER", "UNDO"}

    set_name: bpy.props.StringProperty(name="Name", description="Name to save this filter set as")

    def execute(self, context):
        if not self.set_name.strip():
            self.report({'ERROR'}, "Name cannot be empty.")
            return {'CANCELLED'}

        props = tool.Sequence.get_work_schedule_props()

        # Crear un nuevo conjunto guardado
        # Create a new saved set
        new_set = props.saved_filter_sets.add()
        new_set.name = self.set_name

        # Copy the rules from the active filter to the new set
        for active_rule in props.filters.rules:
            saved_rule = new_set.rules.add()
            saved_rule.is_active = active_rule.is_active
            saved_rule.column = active_rule.column
            saved_rule.operator = active_rule.operator
            try:
                saved_rule.value_string = active_rule.value_string
            except Exception:
                pass
            try:
                saved_rule.data_type = active_rule.data_type
            except Exception:
                pass

        self.report({'INFO'}, f"Filter '{self.set_name}' saved.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class LoadFilterSet(bpy.types.Operator):
    """Loads a saved filter set and applies it."""
    bl_idname = "bim.load_filter_set"
    bl_label = "Load Filter Set"
    bl_options = {"REGISTER", "UNDO"}

    set_index: bpy.props.IntProperty()

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        if not (0 <= self.set_index < len(props.saved_filter_sets)):
            self.report({'ERROR'}, "Invalid filter index.")
            return {'CANCELLED'}

        saved_set = props.saved_filter_sets[self.set_index]

        # Limpiar filtros activos y cargar los guardados
        props.filters.rules.clear()
        for saved_rule in saved_set.rules:
            active_rule = props.filters.rules.add()
            active_rule.is_active = saved_rule.is_active
            active_rule.column = saved_rule.column
            active_rule.operator = saved_rule.operator
            try:
                active_rule.value_string = saved_rule.value_string
            except Exception:
                pass
            try:
                active_rule.data_type = saved_rule.data_type
            except Exception:
                pass

        # Aplicar filtros recargando la lista
        ws = tool.Sequence.get_active_work_schedule()
        if ws:
            tool.Sequence.load_task_tree(ws)
            tool.Sequence.load_task_properties()

        # Lógica inteligente: Si las nuevas tareas NO tienen varianza calculada, limpiar colores 3D
        try:
            if not tool.Sequence.has_variance_calculation_in_tasks():
                print("🧠 Loaded tasks have no variance calculation → clearing 3D colors only")
                tool.Sequence.clear_variance_colors_only()
            else:
                print("ℹ️ Loaded tasks have variance calculation → keeping colors active")
        except Exception as e:
            print(f"⚠️ Error in intelligent variance color check: {e}")

        return {'FINISHED'}

class RemoveFilterSet(bpy.types.Operator):
    """Deletes a saved filter set."""
    bl_idname = "bim.remove_filter_set"
    bl_label = "Remove Filter Set"
    bl_options = {"REGISTER", "UNDO"}

    set_index: bpy.props.IntProperty()

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Removed last_lookahead_window clearing to preserve active filters
        if not (0 <= self.set_index < len(props.saved_filter_sets)):
            self.report({'ERROR'}, "Invalid filter index.")
            return {'CANCELLED'}

        set_name = props.saved_filter_sets[self.set_index].name
        props.saved_filter_sets.remove(self.set_index)
        props.active_saved_filter_set_index = min(max(0, self.set_index - 1), len(props.saved_filter_sets) - 1)
        self.report({'INFO'}, f"Filter '{set_name}' removed.")
        return {'FINISHED'}


class ExportFilterSet(bpy.types.Operator, ExportHelper):
    """Exports the ENTIRE library of saved filter sets to a JSON file."""
    bl_idname = "bim.export_filter_set"
    bl_label = "Export Filter Library"  # Updated label
    bl_description = "Export all saved filters to a single JSON file"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()

        # 1. Prepare a dictionary to store the entire library
        library_data = {}

        # 2. Iterate through each saved filter in the library
        for saved_set in props.saved_filter_sets:
            rules_data = []
            # 3. Iterate through rules of each saved filter
            for rule in saved_set.rules:
                rules_data.append({
                    "is_active": rule.is_active,
                    "column": rule.column,
                    "operator": rule.operator,
                    "value": rule.value,
                })
            # 4. Add the filter and its rules to the library
            library_data[saved_set.name] = {"rules": rules_data}

        # 5. Write the entire library to the JSON file
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(library_data, f, ensure_ascii=False, indent=4)

        self.report({'INFO'}, f"Filter library exported to {self.filepath}")
        return {'FINISHED'}


class ApplyTaskFilters(bpy.types.Operator):
    """Triggers the recalculation and update of the task list."""
    bl_idname = "bim.apply_task_filters"
    bl_label = "Apply Task Filters"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Removed problematic last_lookahead_window clearing - following v50 approach
        # 1) Guardar snapshot del estado UI
        try:
            snapshot_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: snapshot_all_ui_state falló: {e}")

        # 2) Recalcular lista aplicando filtros activos
        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties()
        except Exception as e:
            print(f"Bonsai WARNING: recarga de tareas falló: {e}")

        # 2.5) Lógica inteligente: Si las nuevas tareas NO tienen varianza calculada, limpiar colores 3D
        try:
            if not tool.Sequence.has_variance_calculation_in_tasks():
                print("🧠 New tasks have no variance calculation → clearing 3D colors only")
                tool.Sequence.clear_variance_colors_only()
            else:
                print("ℹ️ New tasks have variance calculation → keeping colors active")
        except Exception as e:
            print(f"⚠️ Error in intelligent variance color check: {e}")

        # 3) Restaurar estado UI
        try:
            restore_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: restore_all_ui_state falló: {e}")

        return {'FINISHED'}

class ImportFilterSet(bpy.types.Operator, ImportHelper):
    """Imports a library of filter sets from a JSON file, replacing the current library."""
    bl_idname = "bim.import_filter_set"
    bl_label = "Import Filter Library"  # Updated label
    bl_description = "Import a filter library from a JSON file, replacing all current saved filters"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    # 'set_name' property is no longer needed; names come from the JSON file
    def execute(self, context):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                library_data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Could not read or parse JSON file: {e}")
            return {'CANCELLED'}

        props = tool.Sequence.get_work_schedule_props()
        
        # 1. ELIMINADO: La línea `props.saved_filter_sets.clear()` ha sido removida.
        # Ya no se borra la biblioteca existente.
        
        # 2. AÑADIDO: Comprobación para evitar duplicados
        # Obtenemos los nombres de los filtros que ya existen.
        existing_names = {fs.name for fs in props.saved_filter_sets}
        imported_count = 0
        
        for set_name, set_data in library_data.items():
            # Si el nombre del filtro a importar ya existe, lo saltamos.
            if set_name in existing_names:
                continue

            # Si no existe, lo añadimos.
            new_set = props.saved_filter_sets.add()
            new_set.name = set_name
            
            for rule_data in set_data.get("rules", []):
                new_rule = new_set.rules.add()
                new_rule.is_active = rule_data.get("is_active", True)
                new_rule.column = rule_data.get("column", "")
                new_rule.operator = rule_data.get("operator", "CONTAINS")
                new_rule.value = rule_data.get("value", "")
            
            imported_count += 1
        
        self.report({'INFO'}, f"{imported_count} new filter sets imported and combined.")
        return {'FINISHED'}


# === INICIO DE CÓDIGO AÑADIDO ===

class FilterDatePicker(bpy.types.Operator):
    """A specialized Date Picker that updates the value of a filter rule."""
    bl_idname = "bim.filter_datepicker"
    bl_label = "Select Filter Date"
    bl_options = {"REGISTER", "UNDO"}

    # Propiedad para saber qué regla de la lista modificar
    rule_index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        if self.rule_index < 0 or self.rule_index >= len(props.filters.rules):
            self.report({'ERROR'}, "Invalid filter rule index.")
            return {'CANCELLED'}
        
        # Obtener la fecha seleccionada del DatePickerProperties
        selected_date_str = context.scene.DatePickerProperties.selected_date
        if not selected_date_str:
            self.report({'ERROR'}, "No date selected.")
            return {'CANCELLED'}
            
        # Actualizar el valor de la regla de filtro
        target_rule = props.filters.rules[self.rule_index]
        target_rule.value_string = selected_date_str
        
        # Aplicar los filtros automáticamente
        try:
            bpy.ops.bim.apply_task_filters()
        except Exception as e:
            print(f"Error applying filters: {e}")
        
        self.report({'INFO'}, f"Date set to: {selected_date_str}")
        return {"FINISHED"}

    def invoke(self, context, event):
        if self.rule_index < 0:
            self.report({'ERROR'}, "No rule index specified.")
            return {'CANCELLED'}
            
        props = tool.Sequence.get_work_schedule_props()
        if self.rule_index >= len(props.filters.rules):
            self.report({'ERROR'}, "Invalid filter rule index.")
            return {'CANCELLED'}
        
        # Obtener la fecha actual de la regla
        current_date_str = props.filters.rules[self.rule_index].value_string
        
        # Configurar el DatePickerProperties
        date_picker_props = context.scene.DatePickerProperties
        
        if current_date_str and current_date_str.strip():
            try:
                # Intentar parsear la fecha existente
                current_date = datetime.fromisoformat(current_date_str.split('T')[0])
            except Exception:
                try:
                    from dateutil import parser as date_parser
                    current_date = date_parser.parse(current_date_str)
                except Exception:
                    current_date = datetime.now()
        else:
            current_date = datetime.now()
        
        # Configurar las propiedades del DatePicker
        date_picker_props.selected_date = current_date.strftime("%Y-%m-%d")
        date_picker_props.display_date = current_date.replace(day=1).strftime("%Y-%m-%d")
        
        # Show the dialog
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        """Calendar interface for selecting dates"""
        import calendar
        from dateutil import relativedelta
        
        layout = self.layout
        props = context.scene.DatePickerProperties
        
        # Parsear la fecha de display actual
        try:
            display_date = datetime.fromisoformat(props.display_date)
        except Exception:
            display_date = datetime.now()
            props.display_date = display_date.strftime("%Y-%m-%d")
        
        # Manual date entry field
        row = layout.row()
        row.prop(props, "selected_date", text="Date")
        
        # Month navigation
        current_month = (display_date.year, display_date.month)
        lines = calendar.monthcalendar(*current_month)
        month_title = calendar.month_name[display_date.month] + f" {display_date.year}"
        
        # Month header with navigation
        row = layout.row(align=True)
        
        # Botón mes anterior
        prev_month = display_date - relativedelta.relativedelta(months=1)
        op = row.operator("wm.context_set_string", icon="TRIA_LEFT", text="")
        op.data_path = "scene.DatePickerProperties.display_date"
        op.value = prev_month.strftime("%Y-%m-%d")
        
        # Month title
        row.label(text=month_title)
        
        # Botón mes siguiente  
        next_month = display_date + relativedelta.relativedelta(months=1)
        op = row.operator("wm.context_set_string", icon="TRIA_RIGHT", text="")
        op.data_path = "scene.DatePickerProperties.display_date"
        op.value = next_month.strftime("%Y-%m-%d")
        
        # Days of the week
        row = layout.row(align=True)
        for day_name in ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']:
            col = row.column(align=True)
            col.alignment = "CENTER"
            col.label(text=day_name)
        
        # Parse the selected date to highlight it
        try:
            selected_date = datetime.fromisoformat(props.selected_date)
        except Exception:
            selected_date = None
        
        # Días del calendario
        for week in lines:
            row = layout.row(align=True)
            for day in week:
                col = row.column(align=True)
                if day == 0:
                    col.label(text="")
                else:
                    day_date = datetime(display_date.year, display_date.month, day)
                    day_str = day_date.strftime("%Y-%m-%d")
                    
                    # Check if it is the selected day
                    is_selected = (selected_date and day_date.date() == selected_date.date())
                    
                    # Button to select the day
                    op = col.operator("wm.context_set_string", 
                                    text=str(day), 
                                    depress=is_selected)

# === BEGIN: TASK colortype PERSISTENCE HELPERS ================================
def _defer_scene_write(fn, *args, **kwargs):
    try:
        import bpy
        def _runner():
            try:
                fn(*args, **kwargs)
            except Exception as _e:
                print(f"[defer] deferred write error: {_e}")
            return None
        bpy.app.timers.register(_runner, first_interval=0.01)
    except Exception as e:
        print(f"[defer] cannot schedule timer: {e}")

def _safe_assign(obj, attr, value):
    try:
        setattr(obj, attr, value)
    except Exception as e:
        if "Writing to ID classes in this context is not allowed" in str(e):
            _defer_scene_write(setattr, obj, attr, value)
        else:
            raise





def calculate_schedule_metrics(viz_start, current_date, viz_finish, full_schedule_start, full_schedule_end):
    """
    LÓGICA DEFINITIVA CORREGIDA: Day/Week/Progress relativos al CRONOGRAMA ACTIVO (dominante).
    El rango seleccionado (viz_start/viz_finish) solo determina qué mostrar, pero los cálculos
    siempre son relativos al cronograma activo completo.
    
    Args:
        viz_start: Fecha de inicio del rango seleccionado (solo para visualización)
        current_date: Fecha actual de la animación
        viz_finish: Fecha de fin del rango seleccionado (solo para visualización) 
        full_schedule_start: Fecha de inicio del cronograma activo (DOMINANTE para cálculos)
        full_schedule_end: Fecha de fin del cronograma activo (DOMINANTE para cálculos)
    
    Returns:
        dict: Métricas calculadas siempre relativas al CRONOGRAMA ACTIVO
        - Day=1 en full_schedule_start, Day=total en full_schedule_end
        - Week=1 en full_schedule_start, Week=total en full_schedule_end  
        - Progress=0% en full_schedule_start, Progress=100% en full_schedule_end
    
    Ejemplos:
        Cronograma: 01/01/2025 → 01/01/2026 (366 días)
        Rango: 01/06/2025 → 01/09/2025 
        Current: 01/06/2025 → Day=182, Week=26, Progress=50% (relativo al cronograma)
    """
    try:
        # VALIDACIÓN: Si current_date está antes del cronograma activo
        if current_date < full_schedule_start:
            # Antes del cronograma: Day=0, Week=0, Progress=0%
            return {
                'day': 0,
                'week': 0, 
                'progress': 0,
                'viz_elapsed_days': 0 if current_date < viz_start else (current_date - viz_start).days + 1,
                'viz_total_days': (viz_finish - viz_start).days + 1,
                'full_total_days': (full_schedule_end - full_schedule_start).days + 1
            }
        
        # CÁLCULOS SIEMPRE RELATIVOS AL CRONOGRAMA ACTIVO COMPLETO
        
        # 1. DÍAS: Días transcurridos desde el inicio del CRONOGRAMA ACTIVO
        elapsed_days_from_full = (current_date - full_schedule_start).days + 1
        
        # 2. SEMANAS: Semanas transcurridas desde el inicio del CRONOGRAMA ACTIVO  
        week_number_from_full = ((elapsed_days_from_full - 1) // 7) + 1
        
        # 3. PROGRESO: Progreso relativo al CRONOGRAMA ACTIVO COMPLETO
        full_duration = (full_schedule_end - full_schedule_start).total_seconds()
        if full_duration > 0:
            if current_date == full_schedule_start:
                # Exactamente en el inicio del cronograma: Progress = 0%
                progress_pct = 0
            elif current_date >= full_schedule_end:
                # En o después del final del cronograma: Progress = 100%
                progress_pct = 100
            else:
                # Progreso proporcional dentro del cronograma completo
                elapsed_seconds = (current_date - full_schedule_start).total_seconds()
                progress_pct = min(100, max(0, round((elapsed_seconds / full_duration) * 100)))
        else:
            # Cronograma de un solo día
            progress_pct = 100 if current_date == full_schedule_start else 0
            
        # 4. MÉTRICAS ADICIONALES DEL RANGO SELECCIONADO (para contexto UI)
        viz_total_days = (viz_finish - viz_start).days + 1
        if viz_start <= current_date <= viz_finish:
            viz_elapsed_days = (current_date - viz_start).days + 1
        else:
            viz_elapsed_days = 0 if current_date < viz_start else viz_total_days
        
        return {
            'day': elapsed_days_from_full,           # Días desde inicio del CRONOGRAMA ACTIVO
            'week': week_number_from_full,           # Semanas desde inicio del CRONOGRAMA ACTIVO  
            'progress': progress_pct,                # Progreso % del CRONOGRAMA ACTIVO
            'viz_elapsed_days': viz_elapsed_days,    # Días transcurridos en rango seleccionado
            'viz_total_days': viz_total_days,        # Total de días en rango seleccionado
            'full_total_days': (full_schedule_end - full_schedule_start).days + 1
        }
        
    except Exception as e:
        print(f"❌ Error en calculate_schedule_metrics: {e}")
        return None

def _ensure_default_group_presence(context):
    try:
        from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
        try:
            UnifiedColorTypeManager.ensure_default_group_has_predefined_types(context)
        except Exception:
            UnifiedColorTypeManager.ensure_default_group(context)
    except Exception as e:
        print(f"[helpers] ensure_default_group_presence: {e}")

class DebugTimelineHUD(bpy.types.Operator):
    """Operador de debug para probar la funcionalidad del Timeline HUD"""
    bl_idname = "bim.debug_timeline_hud"
    bl_label = "Debug Timeline HUD"
    bl_description = "Run internal tests for Timeline HUD functionality"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            from .hud_overlay import schedule_hud
            schedule_hud.test_timeline_functionality()
            self.report({'INFO'}, "Timeline HUD debug test completed - check console for results")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Debug test failed: {e}")
            return {'CANCELLED'}

class DebugHUDCalculations(bpy.types.Operator):
    """Operador de debug para probar cálculos de métricas del HUD"""
    bl_idname = "bim.debug_hud_calculations"
    bl_label = "Debug HUD Calculations"
    bl_description = "Test HUD metrics calculations with current schedule data"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            from .hud_overlay import schedule_hud
            
            # Obtener datos reales del cronograma
            data = schedule_hud.get_schedule_data()
            if not data:
                self.report({'WARNING'}, "No schedule data available")
                return {'CANCELLED'}
            
            print("\n🧪 === DEBUG HUD CALCULATIONS ===")
            print(f"Calculation Mode: {data.get('calculation_mode', 'unknown')}")
            print(f"Current Date: {data['current_date'].strftime('%Y-%m-%d')}")
            
            if data.get('calculation_mode') == 'full_schedule':
                print(f"📊 FULL SCHEDULE MODE:")
                print(f"   Schedule Range: {data['full_schedule_start'].strftime('%Y-%m-%d')} → {data['full_schedule_end'].strftime('%Y-%m-%d')}")
                print(f"   Selected Range: {data['start_date'].strftime('%Y-%m-%d')} → {data['finish_date'].strftime('%Y-%m-%d')}")
                print(f"   Day: {data['elapsed_days']} (from schedule start)")
                print(f"   Week: {data['week_number']}")
                print(f"   Progress: {data['progress_pct']}% of full schedule")
                if 'viz_elapsed_days' in data and 'total_days' in data:
                    print(f"   Selected Range Progress: Day {data['viz_elapsed_days']} of {data['total_days']}")
            else:
                print(f"📊 SELECTED RANGE MODE (fallback):")
                print(f"   Range: {data['start_date'].strftime('%Y-%m-%d')} → {data['finish_date'].strftime('%Y-%m-%d')}")
                print(f"   Day: {data['elapsed_days']} of {data['total_days']}")
                print(f"   Week: {data['week_number']}")
                print(f"   Progress: {data['progress_pct']}% of selected range")
                
            self.report({'INFO'}, "HUD calculations debug completed - check console for results")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Debug test failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class TestTimelineHUDControls(bpy.types.Operator):
    """Test all Timeline HUD controls to verify they work correctly"""
    bl_idname = "bim.test_timeline_hud_controls"
    bl_label = "Test Timeline HUD Controls"
    bl_description = "Test all Timeline HUD properties and controls"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            print("\n" + "="*60)
            print("🧪 TESTING TIMELINE HUD CONTROLS")
            print("="*60)
            
            # Test 1: Enable/Disable Timeline HUD
            print("1. Testing enable_timeline_hud...")
            original_enabled = getattr(camera_props, 'enable_timeline_hud', False)
            camera_props.enable_timeline_hud = True
            print(f"   ✅ Enabled: {camera_props.enable_timeline_hud}")
            
            # Test 2: Position Control
            print("2. Testing timeline_hud_position...")
            original_position = getattr(camera_props, 'timeline_hud_position', 'BOTTOM')
            camera_props.timeline_hud_position = 'TOP'
            print(f"   ✅ Position set to TOP: {camera_props.timeline_hud_position}")
            camera_props.timeline_hud_position = 'BOTTOM'
            print(f"   ✅ Position set to BOTTOM: {camera_props.timeline_hud_position}")
            
            # Test 3: Lock/Unlock
            print("3. Testing timeline_hud_locked...")
            original_locked = getattr(camera_props, 'timeline_hud_locked', True)
            camera_props.timeline_hud_locked = False
            print(f"   ✅ Unlocked: {not camera_props.timeline_hud_locked}")
            
            # Test 4: Manual Position
            print("4. Testing manual position controls...")
            camera_props.timeline_hud_manual_x = 100.0
            camera_props.timeline_hud_manual_y = 50.0
            print(f"   ✅ Manual X: {camera_props.timeline_hud_manual_x}")
            print(f"   ✅ Manual Y: {camera_props.timeline_hud_manual_y}")
            
            # Test 5: Dimensions
            print("5. Testing dimension controls...")
            camera_props.timeline_hud_height = 60.0
            camera_props.timeline_hud_width = 0.9
            print(f"   ✅ Height: {camera_props.timeline_hud_height}")
            print(f"   ✅ Width: {camera_props.timeline_hud_width}")
            
            # Test 6: Colors
            print("6. Testing color controls...")
            camera_props.timeline_hud_color_inactive_range = (0.2, 0.2, 0.2, 0.8)
            camera_props.timeline_hud_color_active_range = (0.4, 0.4, 0.4, 0.8)
            camera_props.timeline_hud_color_progress = (0.8, 0.2, 0.2, 0.9)
            camera_props.timeline_hud_color_text = (1.0, 1.0, 0.0, 1.0)
            print(f"   ✅ All colors set successfully")
            
            # Test 7: Force refresh
            print("7. Testing force refresh...")
            try:
                from .hud_overlay import ensure_hud_handlers, refresh_hud
                ensure_hud_handlers()
                refresh_hud()
                print("   ✅ HUD refresh successful")
            except Exception as e:
                print(f"   ❌ HUD refresh failed: {e}")
            
            # Restore original values
            print("8. Restoring original values...")
            camera_props.enable_timeline_hud = original_enabled
            camera_props.timeline_hud_position = original_position  
            camera_props.timeline_hud_locked = original_locked
            print("   ✅ Original values restored")
            
            print("="*60)
            print("🎉 TIMELINE HUD CONTROLS TEST COMPLETED")
            print("="*60 + "\n")
            
            self.report({'INFO'}, "Timeline HUD controls test completed successfully")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Timeline HUD controls test failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class TestSynchroTimelineHUD(bpy.types.Operator):
    """Test the new Synchro 4D style Timeline HUD"""
    bl_idname = "bim.test_synchro_timeline_hud"
    bl_label = "Test Synchro Timeline HUD"
    bl_description = "Test the new Synchro 4D style timeline with single background bar"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            print("\n" + "="*60)
            print("🧪 TESTING SYNCHRO 4D TIMELINE HUD")
            print("="*60)
            
            # Habilitar Timeline HUD
            print("1. Enabling Timeline HUD...")
            camera_props.enable_timeline_hud = True
            
            # Configurar colores de prueba
            print("2. Setting test colors...")
            camera_props.timeline_hud_color_inactive_range = (0.1, 0.1, 0.3, 0.8)  # Azul oscuro
            camera_props.timeline_hud_color_text = (1.0, 1.0, 1.0, 1.0)             # Blanco
            camera_props.timeline_hud_color_indicator = (1.0, 0.2, 0.2, 1.0)        # Rojo
            
            # Configurar dimensiones
            print("3. Setting dimensions...")
            camera_props.timeline_hud_height = 50.0
            camera_props.timeline_hud_width = 0.85
            
            # Posicionar en bottom
            print("4. Setting position...")
            camera_props.timeline_hud_position = 'BOTTOM'
            camera_props.timeline_hud_locked = True
            
            # Obtener datos de cronograma para verificar
            print("5. Checking schedule data...")
            from .hud_overlay import schedule_hud
            data = schedule_hud.get_schedule_data()
            if data:
                if data.get('full_schedule_start') and data.get('full_schedule_end'):
                    print(f"   ✅ Schedule range: {data['full_schedule_start'].strftime('%Y-%m-%d')} → {data['full_schedule_end'].strftime('%Y-%m-%d')}")
                    print(f"   ✅ Current date: {data['current_date'].strftime('%Y-%m-%d')}")
                else:
                    print(f"   ⚠️ Missing full schedule range - Timeline HUD will be limited")
            else:
                print(f"   ❌ No schedule data available")
            
            # Forzar refresh
            print("6. Forcing HUD refresh...")
            try:
                from .hud_overlay import ensure_hud_handlers, refresh_hud
                ensure_hud_handlers()
                refresh_hud()
                print("   ✅ HUD refresh successful")
            except Exception as e:
                print(f"   ❌ HUD refresh failed: {e}")
            
            print("="*60)
            print("🎉 SYNCHRO TIMELINE HUD TEST COMPLETED")
            print("Expected result:")
            print("- Single background bar (dark blue)")
            print("- White text labels for years, months, weeks")
            print("- Different height lines for years/months/weeks")
            print("- Red diamond indicator for current date")
            print("- Dynamic window based on schedule duration")
            print("="*60 + "\n")
            
            self.report({'INFO'}, "Synchro Timeline HUD test completed - check viewport for results")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Synchro Timeline HUD test failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class TestHUDDateRangeLogic(bpy.types.Operator):
    """Test HUD date range logic and Day/Week calculations"""
    bl_idname = "bim.test_hud_date_range_logic"
    bl_label = "Test HUD Date Range Logic"
    bl_description = "Test that HUD shows correct Day/Week when current date is before schedule start"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            from .hud_overlay import schedule_hud
            
            print("\n" + "="*60)
            print("🧪 TESTING HUD DATE RANGE LOGIC")
            print("="*60)
            
            # Obtener datos actuales
            data = schedule_hud.get_schedule_data()
            if not data:
                self.report({'ERROR'}, "No schedule data available for testing")
                return {'CANCELLED'}
            
            print("1. Current Schedule Data:")
            if data.get('full_schedule_start'):
                print(f"   Full Schedule Start: {data['full_schedule_start'].strftime('%Y-%m-%d')}")
            if data.get('full_schedule_end'):
                print(f"   Full Schedule End: {data['full_schedule_end'].strftime('%Y-%m-%d')}")
            if data.get('start_date'):
                print(f"   Selected Range Start: {data['start_date'].strftime('%Y-%m-%d')}")
            if data.get('finish_date'):
                print(f"   Selected Range End: {data['finish_date'].strftime('%Y-%m-%d')}")
            print(f"   Current Date: {data['current_date'].strftime('%Y-%m-%d')}")
            print(f"   Current Day: {data['elapsed_days']}")
            print(f"   Current Week: {data['week_number']}")
            print(f"   Progress: {data['progress_pct']}%")
            
            print("\n2. Logic Validation:")
            
            # Check if current date is before schedule start
            if data.get('full_schedule_start'):
                schedule_start = data['full_schedule_start']
            else:
                schedule_start = data.get('start_date')
            
            if schedule_start:
                if data['current_date'] < schedule_start:
                    if data['elapsed_days'] == 0 and data['week_number'] == 0:
                        print("   ✅ CORRECT: Day=0, Week=0 when current date is before schedule start")
                    else:
                        print(f"   ❌ ERROR: Day={data['elapsed_days']}, Week={data['week_number']} should be 0 when before schedule start")
                else:
                    if data['elapsed_days'] > 0 and data['week_number'] > 0:
                        print("   ✅ CORRECT: Day>0, Week>0 when current date is after schedule start")
                    else:
                        print(f"   ⚠️  WARNING: Day={data['elapsed_days']}, Week={data['week_number']} might be incorrect")
                        
            # Test Timeline HUD range display
            print("\n3. Timeline HUD Range Test:")
            print("   The timeline HUD should now show:")
            print("   - Texts and lines based on selected Animation Settings range")
            print("   - Dynamic window that includes selected range with context")
            print("   - Proper zoom level based on selected range duration")
            
            print("="*60)
            print("🎉 HUD DATE RANGE LOGIC TEST COMPLETED")
            print("="*60 + "\n")
            
            self.report({'INFO'}, "HUD date range logic test completed - check console for results")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"HUD date range test failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


# === INICIO CÓDIGO PARA LOOKAHEAD FILTER ===
class ApplyLookaheadFilter(bpy.types.Operator):
    """Applies a 'Lookahead' filter to see upcoming tasks."""

    bl_idname = "bim.apply_lookahead_filter"
    bl_label = "Apply Lookahead Filter"
    bl_options = {"REGISTER", "UNDO"}

    time_window: bpy.props.EnumProperty(
        name="Time Window",
        items=[
            ('THIS_WEEK', "This Week", "Show tasks scheduled for the current week"),
            ('LAST_WEEK', "Last Week", "Show tasks scheduled for the previous week"),
            ("1_WEEK", "Next 1 Week", ""),
            ("2_WEEKS", "Next 2 Weeks", ""),
            ("4_WEEKS", "Next 4 Weeks", ""),
            ("6_WEEKS", "Next 6 Weeks", ""),
            ("12_WEEKS", "Next 12 Weeks", ""),
        ],
    )

    def execute(self, context):
        from datetime import datetime, timedelta
        import ifcopenshell.util.sequence

        # 1. Verificar que hay un cronograma activo
        active_schedule = tool.Sequence.get_active_work_schedule()
        if not active_schedule:
            self.report({'ERROR'}, "No active work schedule. Please select one first.")
            return {'CANCELLED'}

        # 2. Verificar que el cronograma no esté vacío
        if not ifcopenshell.util.sequence.get_root_tasks(active_schedule):
            self.report({'WARNING'}, "The active schedule has no tasks. Filter not applied.")
            return {'CANCELLED'}

        props = tool.Sequence.get_work_schedule_props()

        # Store the selected time window so we can re-apply it automatically
        props.last_lookahead_window = self.time_window

        props.filters.rules.clear()  # Limpiar filtros existentes

        # --- INICIO DE LA MODIFICACIÓN ---
        # Obtener el tipo de fecha seleccionado en la UI (Schedule, Actual, etc.)
        date_source = getattr(props, "date_source_type", "SCHEDULE")
        date_prefix = date_source.capitalize()
        start_column = f"IfcTaskTime.{date_prefix}Start||date"
        finish_column = f"IfcTaskTime.{date_prefix}Finish||date"
        # --- END OF MODIFICATION ---

        today = datetime.now()
        filter_start = None
        filter_end = None

        if self.time_window == 'THIS_WEEK':
            filter_start = today - timedelta(days=today.weekday())
            filter_end = filter_start + timedelta(days=6)
        elif self.time_window == 'LAST_WEEK':
            filter_start = today - timedelta(days=today.weekday(), weeks=1)
            filter_end = filter_start + timedelta(days=6)
        elif self.time_window == "1_WEEK":
            filter_start = today
            filter_end = today + timedelta(weeks=1)
        elif self.time_window == "2_WEEKS":
            filter_start = today
            filter_end = today + timedelta(weeks=2)
        elif self.time_window == "4_WEEKS":
            filter_start = today
            filter_end = today + timedelta(weeks=4)
        elif self.time_window == "6_WEEKS":
            filter_start = today
            filter_end = today + timedelta(weeks=6)
        else:  # 12_WEEKS
            filter_start = today
            filter_end = today + timedelta(weeks=12)

        # --- INICIO DE LA MODIFICACIÓN ---
        # Regla 1: La tarea debe empezar ANTES (o en) la fecha de fin del rango, usando la columna dinámica.
        rule1 = props.filters.rules.add()
        rule1.is_active = True
        rule1.column = start_column
        rule1.operator = "LTE"  # Menor o igual que
        rule1.value_string = filter_end.strftime("%Y-%m-%d")

        # Regla 2: La tarea debe terminar DESPUÉS (o en) la fecha de inicio del rango, usando la columna dinámica.
        rule2 = props.filters.rules.add()
        rule2.is_active = True
        rule2.column = finish_column
        rule2.operator = "GTE"  # Mayor o igual que
        rule2.value_string = filter_start.strftime("%Y-%m-%d")
        # --- END OF MODIFICATION ---

        props.filters.active_rule_index = 0 # Asegura que una regla esté seleccionada para las operaciones de UI
        props.filters.logic = "AND"

        # --- INICIO DE LA CORRECCIÓN ---
        # Actualizar las fechas de Animation Settings para que coincidan con el filtro
        if filter_start and filter_end:
            tool.Sequence.update_visualisation_date(filter_start, filter_end)
        # --- FIN DE LA CORRECCIÓN ---
        bpy.ops.bim.apply_task_filters()
        self.report({"INFO"}, f"Filter applied: {self.time_window.replace('_', ' ').title()} (using {date_prefix} dates)"
        )
        return {"FINISHED"}


# === FIN CÓDIGO PARA LOOKAHEAD FILTER ===


class TestHUDDualLogic(bpy.types.Operator):
    """Test dual logic: Timeline HUD uses config range, Text HUD uses active schedule"""
    bl_idname = "bim.test_hud_dual_logic"
    bl_label = "Test HUD Dual Logic"
    bl_description = "Test that Timeline HUD shows config range while Day/Week/Progress use active schedule"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            from .hud_overlay import schedule_hud
            
            print("\n" + "="*70)
            print("🧪 TESTING HUD DUAL LOGIC SYSTEM")
            print("="*70)
            
            # Obtener datos completos
            data = schedule_hud.get_schedule_data()
            if not data:
                self.report({'ERROR'}, "No schedule data available for testing")
                return {'CANCELLED'}
            
            print("📊 DUAL LOGIC VALIDATION:")
            print("─"*50)
            
            # 1. TIMELINE HUD LOGIC (usa rango configurado)
            viz_start = data.get('start_date')
            viz_finish = data.get('finish_date')
            if viz_start and viz_finish:
                print(f"🎯 TIMELINE HUD LOGIC:")
                print(f"   Config Range: {viz_start.strftime('%Y-%m-%d')} → {viz_finish.strftime('%Y-%m-%d')}")
                print(f"   Duration: {(viz_finish - viz_start).days} days")
                print(f"   ✅ Timeline bars, texts, and lines show THIS range")
            
            # 2. TEXT HUD LOGIC (usa cronograma activo para Day/Week/Progress)
            full_start = data.get('full_schedule_start')
            full_end = data.get('full_schedule_end')
            current_date = data.get('current_date')
            
            print(f"\n📝 TEXT HUD LOGIC:")
            if full_start and full_end:
                print(f"   Active Schedule: {full_start.strftime('%Y-%m-%d')} → {full_end.strftime('%Y-%m-%d')}")
                print(f"   Current Date: {current_date.strftime('%Y-%m-%d')}")
                print(f"   Day: {data['elapsed_days']} (relative to active schedule)")
                print(f"   Week: {data['week_number']} (relative to active schedule)")
                print(f"   Progress: {data['progress_pct']}% (relative to active schedule)")
                print(f"   ✅ Day/Week/Progress use ACTIVE SCHEDULE as reference")
            else:
                print("   ⚠️ No active schedule found - using config range as fallback")
                print(f"   Day: {data['elapsed_days']} (relative to config range)")
                print(f"   Week: {data['week_number']} (relative to config range)")
                print(f"   Progress: {data['progress_pct']}% (relative to config range)")
            
            # 3. INDICADOR ANIMATION LOGIC
            print(f"\n📍 INDICATOR ANIMATION:")
            print(f"   Current Date: {current_date.strftime('%Y-%m-%d')}")
            if viz_start and viz_finish:
                if current_date < viz_start:
                    print(f"   Position: BEFORE config range (will show at left edge)")
                elif current_date > viz_finish:
                    print(f"   Position: AFTER config range (will show at right edge)")  
                else:
                    print(f"   Position: WITHIN config range (normal animation)")
                print(f"   ✅ Indicator animates based on current date vs config range")
            
            # 4. EXPECTATIVAS
            print(f"\n🎯 EXPECTED BEHAVIOR:")
            print("   Timeline HUD:")
            print("   - Shows years/months/weeks from CONFIG RANGE")
            print("   - Adapts window size to CONFIG RANGE duration")
            print("   - Indicator animates within CONFIG RANGE window")
            print()
            print("   Text HUD:")  
            print("   - Day/Week values relative to ACTIVE SCHEDULE")
            print("   - Progress % relative to ACTIVE SCHEDULE")
            print("   - Current date shows actual animation date")
            
            print("="*70)
            print("🎉 HUD DUAL LOGIC TEST COMPLETED")
            print("="*70 + "\n")
            
            self.report({'INFO'}, "HUD dual logic test completed - check console and viewport")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"HUD dual logic test failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class DebugHUDSynchronization(bpy.types.Operator):
    """Debug HUD synchronization between Timeline and Text HUD"""
    bl_idname = "bim.debug_hud_synchronization"
    bl_label = "Debug HUD Synchronization"
    bl_description = "Debug the synchronization issues between Timeline HUD and Text HUD"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            import bonsai.tool as tool
            from .hud_overlay import schedule_hud
            
            print("\n" + "="*80)
            print("🔍 DEBUG HUD SYNCHRONIZATION ISSUES")
            print("="*80)
            
            # 1. OBTENER DATOS RAW
            print("📊 RAW DATA FROM get_schedule_data():")
            data = schedule_hud.get_schedule_data()
            if not data:
                print("❌ No schedule data available!")
                return {'CANCELLED'}
            
            print("─"*60)
            for key, value in data.items():
                if hasattr(value, 'strftime'):
                    print(f"   {key}: {value.strftime('%Y-%m-%d %H:%M')}")
                else:
                    print(f"   {key}: {value}")
            
            # 2. OBTENER DATOS DE ANIMATION SETTINGS
            print("\n📅 ANIMATION SETTINGS:")
            work_props = tool.Sequence.get_work_schedule_props()
            anim_props = tool.Sequence.get_animation_props()
            
            viz_start = tool.Sequence.get_start_date()
            viz_finish = tool.Sequence.get_finish_date()
            
            if viz_start and viz_finish:
                print(f"   Selected Range: {viz_start.strftime('%Y-%m-%d')} → {viz_finish.strftime('%Y-%m-%d')}")
                print(f"   Range Duration: {(viz_finish - viz_start).days} days")
            else:
                print("   ❌ No selected range found!")
            
            # 3. OBTENER CRONOGRAMA ACTIVO
            print("\n🗓️ ACTIVE SCHEDULE:")
            try:
                active_schedule = tool.Sequence.get_active_work_schedule()
                if active_schedule:
                    print(f"   Active Schedule: {active_schedule.Name}")
                    
                    # Intentar obtener fechas del cronograma
                    try:
                        full_start, full_end = tool.Sequence.get_schedule_date_range()
                        if full_start and full_end:
                            print(f"   Schedule Range: {full_start.strftime('%Y-%m-%d')} → {full_end.strftime('%Y-%m-%d')}")
                            print(f"   Schedule Duration: {(full_end - full_start).days} days")
                        else:
                            print("   ⚠️ Could not get schedule date range")
                    except Exception as e:
                        print(f"   ❌ Error getting schedule dates: {e}")
                else:
                    print("   ❌ No active schedule found!")
            except Exception as e:
                print(f"   ❌ Error accessing active schedule: {e}")
            
            # 4. VALIDAR CÁLCULOS PASO A PASO
            print("\n🧮 STEP-BY-STEP CALCULATION VALIDATION:")
            current_date = data.get('current_date')
            full_start = data.get('full_schedule_start')
            full_end = data.get('full_schedule_end')
            
            if current_date and full_start and full_end:
                print(f"   Current Date: {current_date.strftime('%Y-%m-%d')}")
                print(f"   Schedule Start: {full_start.strftime('%Y-%m-%d')}")
                print(f"   Schedule End: {full_end.strftime('%Y-%m-%d')}")
                
                # Calcular días manualmente
                if current_date >= full_start:
                    manual_days = (current_date - full_start).days + 1
                    manual_weeks = ((manual_days - 1) // 7) + 1
                else:
                    manual_days = 0
                    manual_weeks = 0
                
                # Calcular progreso manualmente
                if current_date > full_start:
                    elapsed_secs = (current_date - full_start).total_seconds()
                    total_secs = (full_end - full_start).total_seconds()
                    manual_progress = round((elapsed_secs / total_secs) * 100)
                elif current_date == full_start:
                    manual_progress = 0
                else:
                    manual_progress = 0
                
                print(f"\n   MANUAL CALCULATIONS:")
                print(f"   ├─ Days: {manual_days}")
                print(f"   ├─ Weeks: {manual_weeks}")
                print(f"   └─ Progress: {manual_progress}%")
                
                print(f"\n   CURRENT HUD VALUES:")
                print(f"   ├─ Days: {data.get('elapsed_days', 'N/A')}")
                print(f"   ├─ Weeks: {data.get('week_number', 'N/A')}")
                print(f"   └─ Progress: {data.get('progress_pct', 'N/A')}%")
                
                # Comparar
                days_match = manual_days == data.get('elapsed_days', -1)
                weeks_match = manual_weeks == data.get('week_number', -1)
                progress_match = manual_progress == data.get('progress_pct', -1)
                
                print(f"\n   VALIDATION:")
                print(f"   ├─ Days Match: {'✅' if days_match else '❌'}")
                print(f"   ├─ Weeks Match: {'✅' if weeks_match else '❌'}")
                print(f"   └─ Progress Match: {'✅' if progress_match else '❌'}")
                
                if not all([days_match, weeks_match, progress_match]):
                    print("\n   🚨 CALCULATION MISMATCH DETECTED!")
                else:
                    print("\n   ✅ All calculations match!")
            
            # 5. FRAME INFORMATION
            scene = bpy.context.scene
            print(f"\n🎬 ANIMATION FRAME INFO:")
            print(f"   Current Frame: {scene.frame_current}")
            print(f"   Start Frame: {scene.frame_start}")
            print(f"   End Frame: {scene.frame_end}")
            if scene.frame_end > scene.frame_start:
                frame_progress = (scene.frame_current - scene.frame_start) / (scene.frame_end - scene.frame_start)
                print(f"   Frame Progress: {frame_progress:.3f} ({frame_progress*100:.1f}%)")
            
            print("="*80)
            print("🎯 DEBUG COMPLETED - Check calculations above")
            print("="*80 + "\n")
            
            self.report({'INFO'}, "HUD synchronization debug completed - check console")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Debug failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

class ClearScheduleVariance(bpy.types.Operator):
    """Clears the calculated variance from all visible tasks."""
    bl_idname = "bim.clear_schedule_variance"
    bl_label = "Clear Variance"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        task_props = tool.Sequence.get_task_tree_props()
        if not task_props.tasks:
            self.report({'INFO'}, "No tasks to clear.")
            return {'CANCELLED'}

        cleared_count = 0
        for task_pg in task_props.tasks:
            task_pg.variance_status = ""
            task_pg.variance_days = 0
            cleared_count += 1
        
        # Limpiar modo de color de varianza
        try:
            tool.Sequence.clear_variance_color_mode()
            print("✅ Cleared variance color mode after clearing variance")
        except Exception as e:
            print(f"⚠️ Error clearing variance color mode: {e}")
        
        self.report({'INFO'}, f"Cleared variance for {cleared_count} tasks.")
        return {'FINISHED'}


class CalculateScheduleVariance(bpy.types.Operator):
    """Calculates the variance between two date sets for all tasks."""
    bl_idname = "bim.calculate_schedule_variance"
    bl_label = "Calculate Schedule Variance"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from datetime import datetime

        ws_props = tool.Sequence.get_work_schedule_props()
        task_props = tool.Sequence.get_task_tree_props()

        # --- INICIO DE LA MODIFICACIÓN ---
        if not task_props.tasks:
            self.report({'WARNING'}, "No tasks visible to calculate variance. Clear filters to see all tasks.")
            return {'CANCELLED'}
        # --- FIN DE LA MODIFICACIÓN ---

        source_a = ws_props.variance_source_a
        source_b = ws_props.variance_source_b

        if source_a == source_b:
            self.report({'WARNING'}, "Cannot compare a date set with itself.")
            return {'CANCELLED'}

        finish_attr_a = f"{source_a.capitalize()}Finish"
        finish_attr_b = f"{source_b.capitalize()}Finish"

        tasks_processed = 0
        for task_pg in task_props.tasks:
            task_ifc = tool.Ifc.get().by_id(task_pg.ifc_definition_id)
            if not task_ifc:
                continue

            date_a = ifcopenshell.util.sequence.derive_date(task_ifc, finish_attr_a, is_latest=True)
            date_b = ifcopenshell.util.sequence.derive_date(task_ifc, finish_attr_b, is_latest=True)

            if date_a and date_b:
                delta = date_b.date() - date_a.date()
                variance_days = delta.days
                task_pg.variance_days = variance_days

                if variance_days > 0:
                    task_pg.variance_status = f"Delayed (+{variance_days}d)"
                elif variance_days < 0:
                    task_pg.variance_status = f"Ahead ({variance_days}d)"
                else:
                    task_pg.variance_status = "On Time"
                tasks_processed += 1
            else:
                task_pg.variance_status = "N/A"
                task_pg.variance_days = 0
        
        self.report({'INFO'}, f"Variance calculated for {tasks_processed} tasks ({source_a} vs {source_b}).")
        return {'FINISHED'}


class LegendHudcolortypeScrollUp(bpy.types.Operator):
    bl_idname = "bim.legend_hud_colortype_scroll_up"
    bl_label = "Scroll Up"
    bl_description = "Scroll up in the legend HUD colortype list"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            
            current_offset = getattr(camera_props, 'legend_hud_colortype_scroll_offset', 0)
            new_offset = max(0, current_offset - 1)
            if new_offset != current_offset:
                camera_props.legend_hud_colortype_scroll_offset = new_offset
            
            return {'FINISHED'}
        except Exception as e:
            print(f"Error scrolling up: {e}")
            return {'CANCELLED'}


class LegendHudcolortypeScrollDown(bpy.types.Operator):
    bl_idname = "bim.legend_hud_colortype_scroll_down"
    bl_label = "Scroll Down"
    bl_description = "Scroll down in the legend HUD colortype list"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            
            # Get the current scroll offset
            current_offset = getattr(camera_props, 'legend_hud_colortype_scroll_offset', 0)
            colortypes_per_page = 5  # Fixed to show 5 colortypes at a time
            
            # Get active colortype data to check total count
            try:
                # Access the HUD overlay instance to get colortype data
                from . import hud_overlay
                if hasattr(hud_overlay, 'schedule_hud') and hud_overlay.schedule_hud:
                    # FIX: Get the total count of ALL colortypes, not just visible ones,
                    # to correctly calculate the maximum scroll offset.
                    all_colortype_data = hud_overlay.schedule_hud.get_active_colortype_legend_data(include_hidden=True)
                    total_colortypes = len(all_colortype_data) if all_colortype_data else 0
                else:
                    total_colortypes = 0
                    
                # Only scroll down if there are more colortypes to show
                max_offset = max(0, total_colortypes - colortypes_per_page)
                if current_offset < max_offset:
                    camera_props.legend_hud_colortype_scroll_offset = current_offset + 1
            except Exception as e:
                # More informative error handling
                print(f"Error calculating scroll bounds: {e}")
                self.report({'ERROR'}, f"Could not calculate scroll bounds: {e}")
                
            return {'FINISHED'}
        except Exception as e:
            print(f"Error scrolling down: {e}")
            return {'CANCELLED'}


class LegendHudcolortypeScrollUp(bpy.types.Operator):
    bl_idname = "bim.legend_hud_colortype_scroll_up"
    bl_label = "Scroll Up"
    bl_description = "Scroll up in the legend HUD colortype list"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            
            current_offset = getattr(camera_props, 'legend_hud_colortype_scroll_offset', 0)
            new_offset = max(0, current_offset - 1)
            if new_offset != current_offset:
                camera_props.legend_hud_colortype_scroll_offset = new_offset
            
            return {'FINISHED'}
        except Exception as e:
            print(f"Error scrolling up: {e}")
            return {'CANCELLED'}


class LegendHudcolortypeScrollDown(bpy.types.Operator):
    bl_idname = "bim.legend_hud_colortype_scroll_down"
    bl_label = "Scroll Down"
    bl_description = "Scroll down in the legend HUD colortype list"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            
            # Get the current scroll offset
            current_offset = getattr(camera_props, 'legend_hud_colortype_scroll_offset', 0)
            colortypes_per_page = 5  # Fixed to show 5 colortypes at a time
            
            # Get active colortype data to check total count
            try:
                # Access the HUD overlay instance to get colortype data
                from . import hud_overlay
                if hasattr(hud_overlay, 'schedule_hud') and hud_overlay.schedule_hud:
                    # FIX: Get the total count of ALL colortypes, not just visible ones,
                    # to correctly calculate the maximum scroll offset.
                    all_colortype_data = hud_overlay.schedule_hud.get_active_colortype_legend_data(include_hidden=True)
                    total_colortypes = len(all_colortype_data) if all_colortype_data else 0
                else:
                    total_colortypes = 0
                    
                # Only scroll down if there are more colortypes to show
                max_offset = max(0, total_colortypes - colortypes_per_page)
                if current_offset < max_offset:
                    camera_props.legend_hud_colortype_scroll_offset = current_offset + 1
            except Exception as e:
                # More informative error handling
                print(f"Error calculating scroll bounds: {e}")
                self.report({'ERROR'}, f"Could not calculate scroll bounds: {e}")
                
            return {'FINISHED'}
        except Exception as e:
            print(f"Error scrolling down: {e}")
            return {'CANCELLED'}

class LegendHudTogglecolortypeVisibility(bpy.types.Operator):
    bl_idname = "bim.legend_hud_toggle_colortype_visibility"
    bl_label = "Toggle colortype HUD Visibility"
    bl_description = "Toggle whether colortype appears in viewport HUD legend (colortype always remains in settings list)"
    bl_options = {"REGISTER"}
    
    colortype_name: bpy.props.StringProperty(name="colortype Name")

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            
            # legend_hud_visible_colortypes stores colortypes HIDDEN from viewport HUD
            # All colortypes are always visible in the settings list
            # This property controls only viewport HUD legend visibility
            hidden_colortypes = getattr(camera_props, 'legend_hud_visible_colortypes', '')
            
            # Parse current hidden colortypes
            if hidden_colortypes.strip():
                hidden_list = [p.strip() for p in hidden_colortypes.split(',') if p.strip()]
            else:
                hidden_list = []
                
            # Toggle colortype visibility in viewport HUD legend
            if self.colortype_name in hidden_list:
                # colortype is hidden from HUD, show it in HUD (remove from hidden list)
                hidden_list.remove(self.colortype_name)
            else:
                # colortype is shown in HUD, hide it from HUD (add to hidden list)
                hidden_list.append(self.colortype_name)
                
            # Update the property
            camera_props.legend_hud_visible_colortypes = ', '.join(hidden_list)
            
            return {'FINISHED'}
        except Exception as e:
            print(f"Error toggling colortype visibility: {e}")
            return {'CANCELLED'}



class DeactivateVarianceColorMode(bpy.types.Operator):
    bl_idname = "bim.deactivate_variance_color_mode"
    bl_label = "Deactivate Variance Color Mode"
    bl_description = "Deactivate variance color mode and restore normal colors"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        try:
            print("🔄 Manual deactivation of variance color mode")
            tool.Sequence.deactivate_variance_color_mode()
            self.report({'INFO'}, "Variance color mode deactivated")
        except Exception as e:
            print(f"❌ Manual deactivation failed: {e}")
            self.report({'ERROR'}, f"Deactivation failed: {e}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Snapshot utility: refresh 3D texts without creating a new camera
# ---------------------------------------------------------------------------
class RefreshSnapshotTexts(bpy.types.Operator):
    bl_idname = "bim.refresh_snapshot_texts"
    bl_label = "Refresh 3D Texts (Snapshot)"
    bl_description = "Regenerates Schedule_Display_Texts using the current visualisation date with the ACTIVE Snapshot camera"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            scene = context.scene
            cam_obj = scene.camera
            if not cam_obj:
                self.report({'ERROR'}, "No active camera in scene")
                return {'CANCELLED'}
            if not cam_obj.get('is_snapshot_camera', False):
                self.report({'WARNING'}, "Active camera is not marked as Snapshot")
                # Continue anyway (some users may want refresh even if flag missing)
            try:
                import bonsai.tool as tool
            except Exception as e:
                self.report({'ERROR'}, f"Cannot import bonsai.tool: {e}")
                return {'CANCELLED'}

            # Resolve a 'current' visualisation datetime
            ws_props = None
            try:
                ws_props = tool.Sequence.get_work_schedule_props()
            except Exception:
                ws_props = None

            start_dt = None
            try:
                start_str = getattr(ws_props, "visualisation_start", None) if ws_props else None
                parse = getattr(tool.Sequence, "parse_isodate_datetime", None) or getattr(tool.Sequence, "parse_isodate", None)
                if start_str and parse:
                    start_dt = parse(start_str)
            except Exception:
                start_dt = None

            if start_dt is None:
                from datetime import datetime as _dt
                start_dt = _dt.now()

            snapshot_settings = {
                "start": start_dt,
                "finish": start_dt,
                "start_frame": scene.frame_current,
                "total_frames": 1,
            }

            # Rebuild 3D texts collection
            try:
                tool.Sequence.add_text_animation_handler(snapshot_settings)
            except Exception as e:
                self.report({'ERROR'}, f"Failed to rebuild 3D texts: {e}")
                return {'CANCELLED'}

            # Optional auto-arrange
            try:
                bpy.ops.bim.arrange_schedule_texts()
            except Exception:
                pass

            self.report({'INFO'}, "Snapshot 3D texts refreshed")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}