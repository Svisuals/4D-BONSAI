# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2020, 2021 Dion Moult <dion@thinkmoult.com>
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

# pyright: reportAttributeAccessIssue=false

import bpy

from . import ui, prop
from . import operators


classes = (
    
# Property groups from prop.py
    prop.WorkPlan,
    prop.BIMWorkPlanProperties,
    prop.TaskcolortypeGroupChoice,
    prop.Task,
    prop.TaskResource,
    prop.TaskProduct,
    prop.IFCStatus,
    prop.BIMStatusProperties,
    # --- Filter Property Groups ---
    prop.TaskFilterRule,
    prop.BIMTaskFilterProperties,
    prop.SavedFilterSet,

    prop.BIMWorkScheduleProperties,
    prop.BIMTaskTreeProperties,
    prop.BIMTaskTypeColor,
    prop.AnimationColorSchemes,
    prop.AnimationColorTypeGroupItem,
    prop.BIMAnimationProperties,
    prop.WorkCalendar,
    prop.RecurrenceComponent,
    prop.BIMWorkCalendarProperties,
    prop.DatePickerProperties,
    prop.BIMDateTextProperties,

    # UI Panels & Lists from ui.py
    ui.BIM_PT_work_plans,
    ui.BIM_PT_work_schedules,
    ui.BIM_PT_task_icom,
    ui.BIM_PT_animation_tools,
    ui.BIM_PT_work_calendars,
    ui.BIM_PT_variance_analysis,
    ui.BIM_PT_status,
    ui.BIM_UL_task_columns,
    ui.BIM_UL_task_filters,
    ui.BIM_UL_saved_filter_sets,
    ui.BIM_UL_task_inputs,
    ui.BIM_UL_task_resources,
    ui.BIM_UL_task_outputs,
    ui.BIM_UL_tasks,
    ui.BIM_UL_animation_group_stack,
    ui.BIM_PT_4D_Tools,
    ui.BIM_UL_animation_colors,
    ui.BIM_UL_product_input_tasks,
    ui.BIM_UL_product_output_tasks,
    ui.BIM_PT_animation_color_schemes,
)

# --- Optional registration: ClearAnimationAdvanced (guarded) ---
try:
    _ADV = operator.ClearAnimationAdvanced
except Exception:
    _ADV = None
if _ADV:
    try:
        classes = tuple(list(classes) + [_ADV])
    except Exception:
        pass
# --- end optional registration ---



def menu_func_export(self, context):
    self.layout.operator(operator.ExportP6.bl_idname, text="P6 (.xml)")
    self.layout.operator(operator.ExportMSP.bl_idname, text="Microsoft Project (.xml)")


def menu_func_import(self, context):
    self.layout.operator(operator.ImportWorkScheduleCSV.bl_idname, text="Work Schedule (.csv)")
    self.layout.operator(operator.ImportP6.bl_idname, text="P6 (.xml)")
    self.layout.operator(operator.ImportP6XER.bl_idname, text="P6 (.xer)")
    self.layout.operator(operator.ImportPP.bl_idname, text="Powerproject (.pp)")
    self.layout.operator(operator.ImportMSP.bl_idname, text="Microsoft Project (.xml)")


def register():
    # Register operators from operators module
    operators.register()
    
    # Register all classes for this module
    try:
        for cls in classes:
            try:
                bpy.utils.register_class(cls)
            except Exception as e:
                print(f"Bonsai: Failed to register class {cls.__name__}: {e}")
    except Exception as e:
        print(f"Bonsai: Failed during class registration loop: {e}")


    # --- NEW: register camera orbit property group and test operators ---
    try:
        bpy.utils.register_class(prop.BIMCameraOrbitProperties)
    except Exception:
        pass
    try:
        bpy.utils.register_class(operator.ResetCameraSettings)
    except Exception:
        pass


    # --- NEW: dynamically attach camera_orbit pointer after classes are registered ---
    try:
        if not hasattr(prop.BIMAnimationProperties, 'camera_orbit'):
            prop.BIMAnimationProperties.camera_orbit = bpy.props.PointerProperty(type=prop.BIMCameraOrbitProperties)
    except Exception as _e:
        print("camera_orbit dynamic attach failed:", _e)
    bpy.types.Scene.show_saved_ColorTypes_section = bpy.props.BoolProperty(name="Show Saved ColorTypes", default=True)
    bpy.types.Scene.BIMWorkPlanProperties = bpy.props.PointerProperty(type=prop.BIMWorkPlanProperties)
    bpy.types.Scene.BIMWorkScheduleProperties = bpy.props.PointerProperty(type=prop.BIMWorkScheduleProperties)
    bpy.types.Scene.BIMTaskTreeProperties = bpy.props.PointerProperty(type=prop.BIMTaskTreeProperties)
    bpy.types.Scene.BIMWorkCalendarProperties = bpy.props.PointerProperty(type=prop.BIMWorkCalendarProperties)
    bpy.types.Scene.BIMStatusProperties = bpy.props.PointerProperty(type=prop.BIMStatusProperties)
    bpy.types.Scene.BIMAnimationProperties = bpy.props.PointerProperty(type=prop.BIMAnimationProperties)
    bpy.types.Scene.DatePickerProperties = bpy.props.PointerProperty(type=prop.DatePickerProperties)
    bpy.types.TextCurve.BIMDateTextProperties = bpy.props.PointerProperty(type=prop.BIMDateTextProperties)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

# --- Seed DEFAULT Animation Color Schemes group if none exists, and select it ---
try:
    import json
    scn = bpy.context.scene
    key = "BIM_AnimationColorSchemesSets"
    raw = scn.get(key, "{}")
    data = {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        data = {}
    # If the DEFAULT group doesn't exist or is empty, create it with full data.
    # This is more robust than just checking if `data` is empty.
    if not isinstance(data, dict) or not data.get("DEFAULT"):
        color_map = {
            "CONSTRUCTION": {"start": [1,1,1,0], "active": [0,1,0,1], "end": [0.3,1,0.3,1]},
            "INSTALLATION": {"start": [1,1,1,0], "active": [0,0.8,0.5,1], "end": [0.3,0.8,0.5,1]},
            "DEMOLITION": {"start": [1,1,1,1], "active": [1,0,0,1], "end": [0,0,0,0], "hide": True},
            "REMOVAL": {"start": [1,1,1,1], "active": [1,0.3,0,1], "end": [0,0,0,0], "hide": True},
            "DISPOSAL": {"start": [1,1,1,1], "active": [0.8,0,0.2,1], "end": [0,0,0,0], "hide": True},
            "DISMANTLE": {"start": [1,1,1,1], "active": [1,0.5,0,1], "end": [0,0,0,0], "hide": True},
            "OPERATION": {"start": [1,1,1,1], "active": [0,0.5,1,1], "end": [1,1,1,1]},
            "MAINTENANCE": {"start": [1,1,1,1], "active": [0.3,0.6,1,1], "end": [1,1,1,1]},
            "ATTENDANCE": {"start": [1,1,1,1], "active": [0.5,0.5,1,1], "end": [1,1,1,1]},
            "RENOVATION": {"start": [1,1,1,1], "active": [0.5,0,1,1], "end": [0.9,0.9,0.9,1]},
            "LOGISTIC": {"start": [1,1,1,1], "active": [1,1,0,1], "end": [1,0.8,0.3,1]},
            "MOVE": {"start": [1,1,1,1], "active": [1,0.8,0,1], "end": [0.8,0.6,0,1]},
            "NOTDEFINED": {"start": [0.7,0.7,0.7,1], "active": [0.5,0.5,0.5,1], "end": [0.3,0.3,0.3,1]},
        }
        default_colortypes = []
        for name, colors in color_map.items():
            # Create the full profile data structure
            profile = {
                "name": name, "start_color": colors["start"], "in_progress_color": colors["active"], "end_color": colors["end"],
                "consider_start": False, "consider_active": True, "consider_end": True,
                "use_start_original_color": False, "use_active_original_color": False,
                "use_end_original_color": not colors.get("hide", False),
                "start_transparency": 0.0, "active_start_transparency": 0.0, "active_finish_transparency": 0.0,
                "active_transparency_interpol": 1.0, "end_transparency": 0.0,
                "hide_at_end": colors.get("hide", False)
            }
            default_colortypes.append(profile)
        data["DEFAULT"] = {"ColorTypes": default_colortypes}
        scn[key] = json.dumps(data)
    # try to select DEFAULT in the UI
    try:
        scn.BIMAnimationProperties.ColorType_groups = "DEFAULT"
    except Exception:
        pass
except Exception:
    pass


def unregister():
    # Unregister operators from operators module first
    operators.unregister()
    
    # Unregister classes in reverse order
    try:
        for cls in reversed(classes):
            try:
                bpy.utils.unregister_class(cls)
            except Exception as e:
                print(f"Bonsai: Failed to unregister class {cls.__name__}: {e}")
    except Exception as e:
        print(f"Bonsai: Failed during class unregistration loop: {e}")

    # --- NEW: remove dynamic camera_orbit pointer ---
    try:
        if hasattr(prop.BIMAnimationProperties, 'camera_orbit'):
            delattr(prop.BIMAnimationProperties, 'camera_orbit')
    except Exception:
        pass
    # --- NEW: unregister test operators and camera orbit PG ---
    try:
        bpy.utils.unregister_class(operator.ResetCameraSettings)
    except Exception:
        pass
    try:
        bpy.utils.unregister_class(prop.BIMCameraOrbitProperties)
    except Exception:
        pass

    if hasattr(bpy.types.Scene, 'show_saved_ColorTypes_section'):
        del bpy.types.Scene.show_saved_ColorTypes_section
    if hasattr(bpy.types.Scene, 'BIMWorkPlanProperties'):
        del bpy.types.Scene.BIMWorkPlanProperties
    if hasattr(bpy.types.Scene, 'BIMWorkScheduleProperties'):
        del bpy.types.Scene.BIMWorkScheduleProperties
    if hasattr(bpy.types.Scene, 'BIMTaskTreeProperties'):
        del bpy.types.Scene.BIMTaskTreeProperties
    if hasattr(bpy.types.Scene, 'BIMWorkCalendarProperties'):
        del bpy.types.Scene.BIMWorkCalendarProperties
    if hasattr(bpy.types.Scene, 'BIMStatusProperties'):
        del bpy.types.Scene.BIMStatusProperties
    if hasattr(bpy.types.Scene, 'DatePickerProperties'):
        del bpy.types.Scene.DatePickerProperties
    if hasattr(bpy.types.Scene, 'BIMAnimationProperties'):
        del bpy.types.Scene.BIMAnimationProperties
    if hasattr(bpy.types.TextCurve, 'BIMDateTextProperties'):
        del bpy.types.TextCurve.BIMDateTextProperties
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)