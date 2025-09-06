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

import bpy
from bonsai.bim.module.sequence import helper
import json
import isodate
import ifcopenshell.api
import ifcopenshell.api.sequence
import ifcopenshell.util.attribute
import ifcopenshell.util.date
import bonsai.tool as tool
import bonsai.core.sequence as core
from bonsai.bim.module.sequence.data import SequenceData, AnimationColorSchemeData, refresh as refresh_sequence_data
import bonsai.bim.module.resource.data
import bonsai.bim.module.pset.data
from mathutils import Color
from bonsai.bim.prop import Attribute, ISODuration
from dateutil import parser
from bpy.types import PropertyGroup
from bpy.props import (
    PointerProperty,
    StringProperty,
    EnumProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
    CollectionProperty,
)
from typing import TYPE_CHECKING, Literal, get_args, Optional, Dict, List, Set


def update_date_source_type(self, context):
    """
    CRITICAL: This function is called automatically when the user changes schedule type.
    We need to prevent interference with our custom sync operator.
    """
    try:
        # Check if this is being triggered by our custom sync operator
        if getattr(context.scene, '_synch_in_progress', False):
            print("🔄 update_date_source_type: Skipping - custom sync in progress")
            return
        
        # Check which synchronization approach to use
        import bonsai.tool as tool
        anim_props = tool.Sequence.get_animation_props()
        sync_enabled = getattr(anim_props, "auto_update_on_date_source_change", False)
        
        print(f"🔄 update_date_source_type: sync_enabled={sync_enabled}, new_type={self.date_source_type}")
        
        if sync_enabled:
            # SYNCHRONIZED MODE: Do nothing here - let our custom operator handle it
            print("🔗 update_date_source_type: Synchronized mode - skipping automatic updates")
            return
        else:
            # INDEPENDENT MODE: Use the old behavior for backwards compatibility
            print("📅 update_date_source_type: Independent mode - updating date range")
            
            # Store previous dates
            previous_start = self.visualisation_start
            previous_finish = self.visualisation_finish

            # Update date range for the new schedule type
            bpy.ops.bim.guess_date_range('INVOKE_DEFAULT', work_schedule=self.active_work_schedule_id)
            
            # Only call legacy sync if it exists and we're not in synchronized mode
            try:
                bpy.ops.bim.sync_animation_by_date(
                    'INVOKE_DEFAULT',
                    previous_start_date=previous_start,
                    previous_finish_date=previous_finish
                )
            except Exception as e:
                print(f"⚠️ update_date_source_type: Legacy sync failed: {e}")
                
    except Exception as e:
        print(f"❌ update_date_source_type: Error: {e}")
        import traceback
        traceback.print_exc()



def update_schedule_display_parent_constraint(context):
    """
    Finds the 'Schedule_Display_Parent' empty and updates its rotation and location constraints.
    Rotation and location can follow the active camera or custom targets.
    """
    import bpy
    import bonsai.tool as tool
    parent_name = "Schedule_Display_Parent"
    parent_empty = bpy.data.objects.get(parent_name)

    if not parent_empty:
        return

    # --- WORLD ORIGIN ANCHOR (Snapshot / Forced) ---
    # Respect persistent anchor mode even across resets.
    scene = getattr(context, 'scene', None)
    if scene is None:
        import bpy as _bpy
        scene = _bpy.context.scene

    force_world_origin = False
    try:
        # Explicit object-level override
        if parent_empty.get('anchor_mode') == 'WORLD_ORIGIN':
            force_world_origin = True
        # Scene-level persistence (survives object deletion/recreation)
        elif scene and scene.get('hud_anchor_mode') == 'WORLD_ORIGIN':
            force_world_origin = True
        else:
            # Heuristic: active camera is a snapshot camera
            active_cam = getattr(scene, 'camera', None)
            if active_cam and (active_cam.get('is_snapshot_camera') or
                               active_cam.get('camera_context') == 'snapshot' or
                               'Snapshot_Camera' in getattr(active_cam, 'name', '')):
                force_world_origin = True
    except Exception:
        pass

    if force_world_origin:
        # Clear constraints and pin to world origin
        try:
            parent_empty.constraints.clear()
        except Exception:
            try:
                for c in list(parent_empty.constraints):
                    parent_empty.constraints.remove(c)
            except Exception:
                pass
        try:
            parent_empty.location = (0.0, 0.0, 0.0)
            parent_empty.rotation_euler = (0.0, 0.0, 0.0)
            parent_empty.scale = (1.0, 1.0, 1.0)
        except Exception:
            pass
        # Persist intent
        try:
            parent_empty['anchor_mode'] = 'WORLD_ORIGIN'
            if scene is not None:
                scene['hud_anchor_mode'] = 'WORLD_ORIGIN'
        except Exception:
            pass
        return

    # Get camera orbit properties to check for custom targets
    try:
        anim_props = tool.Sequence.get_animation_props()
        camera_props = anim_props.camera_orbit
        
        # Rotation properties
        use_custom_rot_target = getattr(camera_props, 'use_custom_rotation_target', False)
        custom_rotation_target = getattr(camera_props, 'schedule_display_rotation_target', None)
        
        # Location properties
        use_custom_loc_target = getattr(camera_props, 'use_custom_location_target', False)
        custom_location_target = getattr(camera_props, 'schedule_display_location_target', None)
    except Exception:
        use_custom_rot_target = False
        custom_rotation_target = None
        use_custom_loc_target = False
        custom_location_target = None

    active_camera = getattr(context.scene, 'camera', None)

    # Determine the final targets
    rotation_target = custom_rotation_target if use_custom_rot_target and custom_rotation_target else active_camera
    location_target = custom_location_target if use_custom_loc_target and custom_location_target else active_camera

    # --- Clear existing constraints to ensure a clean state ---
    for c in list(parent_empty.constraints):
        parent_empty.constraints.remove(c)

    # Add rotation constraint
    if rotation_target:
        rot_constraint = parent_empty.constraints.new(type='COPY_ROTATION')
        rot_constraint.target = rotation_target
        print(f"✅ Constrained '{parent_name}' rotation to target '{rotation_target.name}'")
    else:
        print(f"⚠️ No rotation target for '{parent_name}'")

    # Add location constraint
    if location_target:
        loc_constraint = parent_empty.constraints.new(type='COPY_LOCATION')
        loc_constraint.target = location_target
        print(f"✅ Constrained '{parent_name}' location to target '{location_target.name}'")
    else:
        print(f"⚠️ No location target for '{parent_name}'")


def update_legend_3d_hud_constraint(context):
    """
    Finds the 'HUD_3D_Legend' empty and updates its rotation and location constraints.
    Rotation and location can follow the active camera or custom targets.
    """
    import bpy
    import bonsai.tool as tool
    
    hud_empty = None
    for obj in bpy.data.objects:
        if obj.get("is_3d_legend_hud", False):
            hud_empty = obj
            break

    if not hud_empty:
        return

    # --- WORLD ORIGIN ANCHOR (Snapshot / Forced) for Legend HUD ---
    scene = getattr(context, 'scene', None)
    if scene is None:
        import bpy as _bpy
        scene = _bpy.context.scene

    force_world_origin = False
    try:
        # Prefer object-level override if present
        if hud_empty.get('anchor_mode') == 'WORLD_ORIGIN':
            force_world_origin = True
        elif scene and scene.get('hud_anchor_mode') == 'WORLD_ORIGIN':
            force_world_origin = True
        else:
            active_cam = getattr(scene, 'camera', None)
            if active_cam and (active_cam.get('is_snapshot_camera') or
                               active_cam.get('camera_context') == 'snapshot' or
                               'Snapshot_Camera' in getattr(active_cam, 'name', '')):
                force_world_origin = True
    except Exception:
        pass

    if force_world_origin:
        try:
            hud_empty.constraints.clear()
        except Exception:
            try:
                for c in list(hud_empty.constraints):
                    hud_empty.constraints.remove(c)
            except Exception:
                pass
        try:
            hud_empty.location = (0.0, 0.0, 0.0)
            hud_empty.rotation_euler = (0.0, 0.0, 0.0)
            hud_empty.scale = (1.0, 1.0, 1.0)
        except Exception:
            pass
        try:
            hud_empty['anchor_mode'] = 'WORLD_ORIGIN'
            if scene is not None:
                scene['hud_anchor_mode'] = 'WORLD_ORIGIN'
        except Exception:
            pass
        return

    # Get camera orbit properties to check for custom targets
    try:
        anim_props = tool.Sequence.get_animation_props()
        camera_props = anim_props.camera_orbit
        
        # Rotation properties for 3D Legend HUD
        use_custom_rot_target = getattr(camera_props, 'legend_3d_hud_use_custom_rotation_target', False)
        custom_rotation_target = getattr(camera_props, 'legend_3d_hud_rotation_target', None)
        
        # Location properties for 3D Legend HUD
        use_custom_loc_target = getattr(camera_props, 'legend_3d_hud_use_custom_location_target', False)
        custom_location_target = getattr(camera_props, 'legend_3d_hud_location_target', None)
    except Exception:
        use_custom_rot_target = False
        custom_rotation_target = None
        use_custom_loc_target = False
        custom_location_target = None

    active_camera = getattr(context.scene, 'camera', None)

    # Determine the final targets
    rotation_target = custom_rotation_target if use_custom_rot_target and custom_rotation_target else active_camera
    location_target = custom_location_target if use_custom_loc_target and custom_location_target else active_camera

    # --- Clear existing constraints to ensure a clean state ---
    for c in list(hud_empty.constraints):
        hud_empty.constraints.remove(c)

    # Add rotation constraint
    if rotation_target:
        rot_constraint = hud_empty.constraints.new(type='COPY_ROTATION')
        rot_constraint.target = rotation_target
        print(f"✅ Constrained '{hud_empty.name}' rotation to target '{rotation_target.name}'")
    else:
        print(f"⚠️ No rotation target for '{hud_empty.name}'")

    # Add location constraint
    if location_target:
        loc_constraint = hud_empty.constraints.new(type='COPY_LOCATION')
        loc_constraint.target = location_target
        print(f"✅ Constrained '{hud_empty.name}' location to target '{location_target.name}'")
    else:
        print(f"⚠️ No location target for '{hud_empty.name}'")

# --- START OF CORRECTED CODE ---
def get_operator_items(self, context):
    """
    Genera dinámicamente la lista de operadores según el tipo de dato de la columna seleccionada.
    """
    data_type = getattr(self, 'data_type', 'string')

    common_ops = [
        ('EQUALS', "Equals", "The value is exactly the same"),
        ('NOT_EQUALS', "Does not equal", "The value is different"),
        ('EMPTY', "Is empty", "The field has no value"),
        ('NOT_EMPTY', "Is not empty", "The field has a value"),
    ]

    if data_type in ('integer', 'real', 'float'):
        return [
            ('GREATER', "Greater than", ">"),
            ('LESS', "Less than", "<"),
            ('GTE', "Greater or Equal", ">="),
            ('LTE', "Less or Equal", "<="),
        ] + common_ops
    elif data_type == 'date':
        return [
            ('GREATER', "After Date", "The date is after the specified one"),
            ('LESS', "Before Date", "The date is before the specified one"),
            ('GTE', "On or After Date", "The date is on or after the specified one"),
            ('LTE', "On or Before Date", "The date is on or before the specified one"),
        ] + common_ops
    elif data_type == 'boolean':
        return [
            ('EQUALS', "Is", "The value is true or false"),
            ('NOT_EQUALS', "Is not", "The value is the opposite"),
        ]
    else:  # string, enum, y otros por defecto
        return [
            ('CONTAINS', "Contains", "The text string is contained"),
            ('NOT_CONTAINS', "Does not contain", "The text string is not contained"),
        ] + common_ops

def update_filter_column(self, context):
    """
    Callback que se ejecuta al cambiar la columna del filtro.
    Identifica el tipo de dato y resetea los valores para evitar inconsistencias.
    Callback that runs when changing the filter column.
    It identifies the data type and resets the values to avoid inconsistencies.
    """
    try:
        # The identifier is now 'IfcTask.Name||string'. We extract the data type.
        parts = (self.column or "").split('||')
        if len(parts) == 2:
            self.data_type = parts[1]
        else:
            self.data_type = 'string' # Safe default type

        # Reset all value fields to start from scratch
        self.value_string = ""
        self.value_integer = 0
        self.value_float = 0.0
        self.value_boolean = False
    except Exception as e:
        self.data_type = 'string'
# --- END OF CORRECTED CODE ---

def update_variance_calculation(self, context):
    """Callback to automatically recalculate variance when date sources change."""
    import bpy
    def do_recalc():
        try:
            # Only run if the variance panel is actually visible
            ws_props = tool.Sequence.get_work_schedule_props()
            if ws_props.editing_type == "TASKS":
                bpy.ops.bim.calculate_schedule_variance()
        except Exception:
            # Failsafe if operator cannot be called
            pass
        return None  # Run timer only once
    # Use a timer to avoid issues with context during property updates
    if not bpy.app.timers.is_registered(do_recalc):
        bpy.app.timers.register(do_recalc, first_interval=0.05)


def update_task_checkbox_selection(self, context):
    """
    Callback que se ejecuta al marcar/desmarcar un checkbox.
    Utiliza un temporizador para ejecutar la lógica de selección 3D de forma segura.
    """
    def apply_selection():
        try:
            tool.Sequence.apply_selection_from_checkboxes()
        except Exception as e:
            print(f"Error in delayed checkbox selection update: {e}")
        return None  # The timer only runs once

    bpy.app.timers.register(apply_selection, first_interval=0.01)


def update_variance_color_mode(self, context):
    """
    Callback que se ejecuta al marcar/desmarcar el checkbox de modo color de varianza.
    Cada tarea funciona independientemente.
    """
    try:
        print(f"🔄 Variance checkbox changed for task {self.ifc_definition_id} ({self.name}): {self.is_variance_color_selected}")
        
        # Siempre actualizar colores inmediatamente, sin importar otros checkboxes
        print("🎨 Updating variance colors for individual task...")
        tool.Sequence.update_individual_variance_colors()
            
    except Exception as e:
        print(f"❌ Error in variance color mode update: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# UNIFIED COLORTYPE MANAGER - CLASE CENTRAL PARA GESTIONAR PERFILES
# ============================================================================
class UnifiedColorTypeManager:
    @staticmethod
    def ensure_default_group(context):
        """Asegura que el grupo DEFAULT existe con 13 perfiles predefinidos y propiedades completas.
        Solo crea el grupo DEFAULT si no existen grupos personalizados para evitar confusión.
        Ensures the DEFAULT group exists with 13 predefined profiles and full properties. Only creates the DEFAULT group if no custom groups exist to avoid confusion."""
        scene = context.scene
        key = "BIM_AnimationColorSchemesSets"
        raw = scene.get(key, "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        # Check if custom groups already exist
        user_groups = [g for g in data.keys() if g != "DEFAULT"]
        
        # Create DEFAULT if it does not exist AND there are no custom groups
        if "DEFAULT" not in data:
            if not user_groups:
                default_colortypes = [
                    {"name": "CONSTRUCTION", "start_color": [1,1,1,0], "in_progress_color": [0,1,0,1], "end_color": [0.3,1,0.3,1]},
                    {"name": "INSTALLATION", "start_color": [1,1,1,0], "in_progress_color": [0,0.8,0.5,1], "end_color": [0.3,0.8,0.5,1]},
                    {"name": "DEMOLITION", "start_color": [1,1,1,1], "in_progress_color": [1,0,0,1], "end_color": [0,0,0,0]},
                    {"name": "REMOVAL", "start_color": [1,1,1,1], "in_progress_color": [1,0.3,0,1], "end_color": [0,0,0,0]},
                    {"name": "DISPOSAL", "start_color": [1,1,1,1], "in_progress_color": [0.8,0,0.2,1], "end_color": [0,0,0,0]},
                    {"name": "DISMANTLE", "start_color": [1,1,1,1], "in_progress_color": [1,0.5,0,1], "end_color": [0,0,0,0]},
                    {"name": "OPERATION", "start_color": [1,1,1,1], "in_progress_color": [0,0.5,1,1], "end_color": [1,1,1,1]},
                    {"name": "MAINTENANCE", "start_color": [1,1,1,1], "in_progress_color": [0.3,0.6,1,1], "end_color": [1,1,1,1]},
                    {"name": "ATTENDANCE", "start_color": [1,1,1,1], "in_progress_color": [0.5,0.5,1,1], "end_color": [1,1,1,1]},
                    {"name": "RENOVATION", "start_color": [1,1,1,1], "in_progress_color": [0.5,0,1,1], "end_color": [0.9,0.9,0.9,1]},
                    {"name": "LOGISTIC", "start_color": [1,1,1,1], "in_progress_color": [1,1,0,1], "end_color": [1,0.8,0.3,1]},
                    {"name": "MOVE", "start_color": [1,1,1,1], "in_progress_color": [1,0.8,0,1], "end_color": [0.8,0.6,0,1]},
                    {"name": "NOTDEFINED", "start_color": [0.7,0.7,0.7,1], "in_progress_color": [0.5,0.5,0.5,1], "end_color": [0.3,0.3,0.3,1]},
                ]
                # Fill with complete fields
                for colortype in default_colortypes:
                    colortype.update({
                        "consider_start": False,
                        "consider_active": True,
                        "consider_end": True,
                        "use_start_original_color": False,
                        "use_active_original_color": False,
                        "use_end_original_color": colortype["name"] not in ["DEMOLITION", "REMOVAL", "DISPOSAL", "DISMANTLE"],
                        "start_transparency": 0.0,
                        "active_start_transparency": 0.0,
                        "active_finish_transparency": 0.0,
                        "active_transparency_interpol": 1.0,
                        "end_transparency": 0.0
                    })
                data["DEFAULT"] = {"ColorTypes": default_colortypes}
                scene[key] = json.dumps(data)
                print("✅ DEFAULT group created with 13 predefined colortypes")
            else:
                print("⚠️ Custom groups detected - DEFAULT group is not created automatically")
        
        # NEW: Ensure that DEFAULT has ALL the necessary profiles
        # ONLY if there are no custom groups (avoids confusion)
        if "DEFAULT" in data and not user_groups:
            existing_names = {p.get("name") for p in data["DEFAULT"].get("ColorTypes", [])}
            required_names = {
                "CONSTRUCTION", "INSTALLATION", "DEMOLITION", "REMOVAL", 
                "DISPOSAL", "DISMANTLE", "OPERATION", "MAINTENANCE", 
                "ATTENDANCE", "RENOVATION", "LOGISTIC", "MOVE", "NOTDEFINED"
            }
            
            # Add missing profiles
            for missing_name in required_names - existing_names:
                missing_colortype = UnifiedColorTypeManager._create_default_colortype_data(missing_name)
                data["DEFAULT"]["ColorTypes"].append(missing_colortype)
                print(f"✅ Added missing DEFAULT colortype: {missing_name}")
            
            # Guardar cambios si se añadieron perfiles
            if required_names - existing_names:
                scene[key] = json.dumps(data)
        
        return data
    
    @staticmethod
    def _read_sets_json(context):
        """Safely reads the profiles JSON from the scene."""
        import json
        try:
            scene = context.scene
            key = "BIM_AnimationColorSchemesSets"
            raw = scene.get(key, "{}")
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _write_sets_json(context, data):
        """Safely writes the ColorTypes JSON to the scene."""
        import json
        try:
            context.scene["BIM_AnimationColorSchemesSets"] = json.dumps(data)
        except Exception:
            pass

    @staticmethod
    def get_all_predefined_types(context) -> list:
        """Gets all PredefinedTypes from loaded tasks to ensure ColorTypes exist for them."""
        try:
            from bonsai.bim.module.sequence.data import SequenceData
            if not SequenceData.is_loaded:
                SequenceData.load()
            
            types = {"NOTDEFINED", "USERDEFINED"} # Always include these
            tasks_data = (SequenceData.data or {}).get("tasks", {})
            for task in tasks_data.values():
                if predef_type := task.get("PredefinedType"):
                    types.add(predef_type)
            return sorted(list(types))
        except Exception:
            # Fallback with common types if reading fails
            return [
                "ATTENDANCE", "CONSTRUCTION", "DEMOLITION", "DISMANTLE",
                "DISPOSAL", "INSTALLATION", "LOGISTIC", "MAINTENANCE",
                "MOVE", "OPERATION", "REMOVAL", "RENOVATION", "NOTDEFINED"
            ]

    @staticmethod
    def ensure_colortype_in_group(context, group_name: str, colortype_name: str):
        """Ensures that a specific ColorType exists within a group in the JSON."""
        if not group_name or not colortype_name:
            return
        data = UnifiedColorTypeManager._read_sets_json(context)
        group = data.setdefault(group_name, {"ColorTypes": []})

        existing_colortypes = {p.get("name") for p in group.get("ColorTypes", [])}

        if colortype_name not in existing_colortypes:
            # DEFAULT: Start disabled by default
            consider_start = False if (group_name == "DEFAULT") else True
            colortype_payload = {
                "name": colortype_name, 
                "start_color": [1,1,1,0], 
                "in_progress_color": [0,1,0,1], 
                "end_color": [0.7,0.7,0.7,1], 
                "use_end_original_color": True,
                # Campos completos para consistencia
                "consider_start": consider_start, 
                "consider_active": True, 
                "consider_end": True,
                "use_start_original_color": False, 
                "use_active_original_color": False,
                "start_transparency": 0.0, 
                "active_start_transparency": 0.0, 
                "active_finish_transparency": 0.0,
                "active_transparency_interpol": 1.0, 
                "end_transparency": 0.0
            }
            group["ColorTypes"].append(colortype_payload)
            UnifiedColorTypeManager._write_sets_json(context, data)
            print(f"✅ ColorType '{colortype_name}' added to group '{group_name}' ({len(existing_colortypes)} ColorTypes existed before)")
    @staticmethod

    def ensure_default_group_has_predefined_types(context):
        """Ensures that the DEFAULT group contains a ColorType for each existing PredefinedType."""
        all_types = UnifiedColorTypeManager.get_all_predefined_types(context)
        for p_type in all_types:
            UnifiedColorTypeManager.ensure_colortype_in_group(context, "DEFAULT", p_type)
    
    @staticmethod
    def ensure_default_group_has_all_predefined_types(context):
        """Ensures that the DEFAULT group contains ALL 13 predefined ColorTypes, regardless of tasks."""
        # Lista completa de todos los PredefinedTypes posibles (13 tipos)
        all_predefined_types = [
            "CONSTRUCTION", "INSTALLATION", "DEMOLITION", "REMOVAL",
            "DISPOSAL", "DISMANTLE", "OPERATION", "MAINTENANCE", 
            "ATTENDANCE", "RENOVATION", "LOGISTIC", "MOVE", "NOTDEFINED"
        ]
        
        for p_type in all_predefined_types:
            UnifiedColorTypeManager.ensure_colortype_in_group(context, "DEFAULT", p_type)
        
        print(f"✅ Ensured all {len(all_predefined_types)} predefined ColorTypes in DEFAULT group")

    @staticmethod
    def sync_default_group_to_predefinedtype(context, task_pg):
        """
        Key function: Synchronizes the DEFAULT entry of a task with its current PredefinedType.
        This function is responsible for updating the data that will be displayed in the UI.
        """
        if not task_pg: return
        
        # 1. Get the current PredefinedType of the task from the cached data.
        try:
            from bonsai.bim.module.sequence.data import SequenceData
            tid = getattr(task_pg, "ifc_definition_id", None)
            task_data = (SequenceData.data.get("tasks", {}) or {}).get(tid)
            predef_type = (task_data.get("PredefinedType") or "NOTDEFINED") if task_data else "NOTDEFINED"
        except Exception:
            predef_type = "NOTDEFINED"

        # 2. Make sure the profile for this type exists in the DEFAULT group.
        UnifiedColorTypeManager.ensure_colortype_in_group(context, "DEFAULT", predef_type)

        # 3. Update the 'DEFAULT' entry in the task's collection.
        try:
            coll = getattr(task_pg, "colortype_group_choices", None)
            if coll is None: return

            default_entry = next((item for item in coll if item.group_name == "DEFAULT"), None)

            if not default_entry:
                default_entry = coll.add()
                default_entry.group_name = "DEFAULT"
            
            # 4. Assign the profile and make sure it is enabled.
            default_entry.selected_colortype = predef_type
            default_entry.enabled = True # The DEFAULT group is always active.

        except Exception as e:
            print(f"❌ Error synchronizing DEFAULT for the task: {e}")

    @staticmethod
    def initialize_default_for_all_tasks(context) -> bool:
        """Recorre todas las tareas y asegura que su grupo DEFAULT estÃ© inicializado y sincronizado."""
        try:
            tprops = tool.Sequence.get_task_tree_props()
            if not tprops or not hasattr(tprops, 'tasks'):
                return False
            
            # First ensure that all necessary profiles exist.
            UnifiedColorTypeManager.ensure_default_group_has_predefined_types(context)

            for task in tprops.tasks:
                UnifiedColorTypeManager.sync_default_group_to_predefinedtype(context, task)
            
            print(f"✅ Sincronizados {len(tprops.tasks)} tareas con el perfil DEFAULT.")
            return True
        except Exception as e:
            print(f"❌ Error al inicializar perfiles DEFAULT para todas las tareas: {e}")
            return False

    @staticmethod
    def get_user_created_groups(context) -> list:
        """Returns a list of group names that are not 'DEFAULT'."""
        try:
            all_groups = list(UnifiedColorTypeManager._read_sets_json(context).keys())
            return sorted([g for g in all_groups if g != "DEFAULT"])
        except Exception:
            return []
            
    # Methods from the original implementation that are still needed and relevant
    @staticmethod
    def validate_colortype_data(colortype_data: dict) -> bool:
        """Validates the complete data structure of the colortype"""
        required_fields = ['name', 'start_color', 'in_progress_color', 'end_color']
        if not all(field in colortype_data for field in required_fields):
            return False
    
        # Validate colors
        for color_field in ['start_color', 'in_progress_color', 'end_color']:
            color = colortype_data.get(color_field)
            if not isinstance(color, (list, tuple)) or len(color) not in (3, 4):
                return False
    
        # Validate optional values
        optional_floats = [
            'start_transparency', 'active_start_transparency', 
            'active_finish_transparency', 'active_transparency_interpol', 
            'end_transparency'
        ]
        for field in optional_floats:
            if field in colortype_data:
                try:
                    val = float(colortype_data[field])
                    if not 0.0 <= val <= 1.0:
                        return False
                except (TypeError, ValueError):
                    return False
    
        return True

    @staticmethod
    def get_group_colortypes(context, group_name: str) -> Dict[str, dict]:
        """Gets colortypes from a specific group"""
        # --- START OF CORRECTION ---
        # For the DEFAULT group, always return the authoritative, hardcoded list of profiles.
        # This prevents inconsistencies from the JSON store and ensures the Legend HUD
        # and other components always have the complete, correct data.
        if group_name == "DEFAULT":
            default_order = [
                "CONSTRUCTION", "INSTALLATION", "DEMOLITION", "REMOVAL",
                "DISPOSAL", "DISMANTLE", "OPERATION", "MAINTENANCE",
                "ATTENDANCE", "RENOVATION", "LOGISTIC", "MOVE", "NOTDEFINED"
            ]
            colortypes = {}
            for name in default_order:
                colortypes[name] = UnifiedColorTypeManager._create_default_colortype_data(name)
            return colortypes
        # --- END OF CORRECTION ---

        try:
            data = UnifiedColorTypeManager._read_sets_json(context)
            if isinstance(data, dict) and group_name in data:
                colortypes = {}
                for colortype in data[group_name].get("ColorTypes", []):
                    if UnifiedColorTypeManager.validate_colortype_data(colortype):
                        colortypes[colortype["name"]] = colortype
                return colortypes
        except Exception:
            pass
        return {}
    
    @staticmethod
    def get_all_groups(context) -> list:
        """Returns a list of names of all groups."""
        try:
            return sorted(list(UnifiedColorTypeManager._read_sets_json(context).keys()))
        except Exception:
            return []

    @staticmethod
    def get_colortypes_from_specific_group(context, group_name: str) -> list:
        """Get colortype names from a specific group (for use in enums)"""
        try:
            colortypes_data = UnifiedColorTypeManager.get_group_colortypes(context, group_name)
            return sorted(list(colortypes_data.keys()))
        except Exception as e:
            print(f"❌ Error getting colortypes from group '{group_name}': {e}")
            return []

    @staticmethod
    def debug_colortype_state(context, task_id: int = None):
        """Debug helper to show profile status"""
        try:
            print("=== colortype DEBUG STATE ===")
            
            # Show all groups
            all_groups = UnifiedColorTypeManager.get_all_groups(context)
            user_groups = UnifiedColorTypeManager.get_user_created_groups(context)
            print(f"All groups: {all_groups}")
            print(f"User groups (no DEFAULT): {user_groups}")
            
            # Show animation props
            try:
                anim_props = tool.Sequence.get_animation_props()
                print(f"Active ColorType_groups: {getattr(anim_props, 'ColorType_groups', 'N/A')}")
                print(f"Task colortype selector: {getattr(anim_props, 'task_colortype_group_selector', 'N/A')}")
                print(f"Loaded ColorTypes count: {len(getattr(anim_props, 'ColorTypes', []))}")
                
                for i, p in enumerate(getattr(anim_props, 'ColorTypes', [])):
                    print(f"  [{i}] {getattr(p, 'name', 'NO_NAME')}")
            except Exception as e:
                print(f"Error getting anim props: {e}")
            
            # Show specific task data
            if task_id:
                try:
                    tprops = tool.Sequence.get_task_tree_props()
                    wprops = tool.Sequence.get_work_schedule_props()
                    if tprops.tasks and wprops.active_task_index < len(tprops.tasks):
                        task = tprops.tasks[wprops.active_task_index]
                        print(f"Task {task.ifc_definition_id} colortype mappings:")
                        for choice in getattr(task, 'colortype_group_choices', []):
                            print(f"  {choice.group_name} -> {choice.selected_colortype} (enabled: {choice.enabled})")
                        print(f"  use_active_colortype_group: {getattr(task, 'use_active_colortype_group', 'N/A')}")
                        print(f"  selected_colortype_in_active_group: {getattr(task, 'selected_colortype_in_active_group', 'N/A')}")
                except Exception as e:
                    print(f"Error getting task data: {e}")
            
            print("=== END DEBUG ===")
        except Exception as e:
            print(f"❌ Debug failed: {e}")


    @staticmethod
    def sync_task_colortypes(context, task, group_name: str):
        """Synchronizes task colortypes with the active group - eliminates duplication"""
        valid_colortypes = UnifiedColorTypeManager.get_group_colortypes(context, group_name)
    
        if hasattr(task, 'colortype_group_choices'):
            # Find or create an entry for the group
            entry = None
            for choice in task.colortype_group_choices:
                if choice.group_name == group_name:
                    entry = choice
                    break
        
            if not entry:
                entry = task.colortype_group_choices.add()
                entry.group_name = group_name
                entry.enabled = False
                entry.selected_colortype = ""
        
            # Validate selected colortype
            if entry.selected_colortype and entry.selected_colortype not in valid_colortypes:
                entry.selected_colortype = ""
        
            return entry
        return None

    @staticmethod
    def cleanup_invalid_mappings(context):
        """Cleans up all invalid colortype mappings"""
        valid_groups = set(UnifiedColorTypeManager._read_sets_json(context).keys())
    
        try:
            tprops = tool.Sequence.get_task_tree_props()
            for task in getattr(tprops, "tasks", []):
                if hasattr(task, 'colortype_group_choices'):
                    # Collect indices to remove
                    to_remove = []
                    for idx, choice in enumerate(task.colortype_group_choices):
                        if choice.group_name not in valid_groups:
                            to_remove.append(idx)
                        else:
                            # Validate colortype within the group
                            colortypes = UnifiedColorTypeManager.get_group_colortypes(context, choice.group_name)
                            if choice.selected_colortype and choice.selected_colortype not in colortypes:
                                choice.selected_colortype = ""
                
                    # Remove invalid entries
                    for offset, idx in enumerate(to_remove):
                        task.colortype_group_choices.remove(idx - offset)
        except Exception as e:
            print(f"Error cleaning invalid mappings: {e}")

    @staticmethod
    def load_colortypes_into_collection(props, context, group_name: str):
        """Loads colortypes from a group into the property collection"""
        
        # Guard to prevent unnecessary reloading if already correctly populated
        if group_name == "DEFAULT":
            default_order = [
                "CONSTRUCTION", "INSTALLATION", "DEMOLITION", "REMOVAL", 
                "DISPOSAL", "DISMANTLE", "OPERATION", "MAINTENANCE", 
                "ATTENDANCE", "RENOVATION", "LOGISTIC", "MOVE", "NOTDEFINED"
            ]
            
            # Check if collection is already correctly populated
            if (len(props.ColorTypes) == len(default_order) and 
                all(props.ColorTypes[i].name == default_order[i] for i in range(len(default_order)))):
                # Collection is already correctly populated, no need to reload
                return
        
        # CRITICAL CHANGE: For DEFAULT, ensure that ALL profiles exist
        # Always ensure DEFAULT profiles exist when DEFAULT group is specifically loaded
        if group_name == "DEFAULT":
            user_groups = UnifiedColorTypeManager.get_user_created_groups(context)
            # Always load DEFAULT profiles when explicitly loading DEFAULT group
            UnifiedColorTypeManager.ensure_default_group_has_predefined_types(context)
            if user_groups:
                print("⚠️ Custom groups detected - but DEFAULT group is being explicitly loaded with full profiles")
        
        colortypes_data = UnifiedColorTypeManager.get_group_colortypes(context, group_name)

        try:
            props.ColorTypes.clear()
            
            # NEW: For DEFAULT, ensure specific order and completeness
            if group_name == "DEFAULT":
                # Complete list in specific order
                default_order = [
                    "CONSTRUCTION", "INSTALLATION", "DEMOLITION", "REMOVAL", 
                    "DISPOSAL", "DISMANTLE", "OPERATION", "MAINTENANCE", 
                    "ATTENDANCE", "RENOVATION", "LOGISTIC", "MOVE", "NOTDEFINED"
                ]
                
                # Load in the specified order
                for colortype_name in default_order:
                    # ALWAYS use the hardcoded default data for the DEFAULT group to ensure correctness.
                    # This ignores any potentially incorrect data stored in the JSON.
                    colortype_data = UnifiedColorTypeManager._create_default_colortype_data(colortype_name)
                    p = props.ColorTypes.add()
                    p.name = colortype_name
                    UnifiedColorTypeManager._apply_colortype_data_to_property(p, colortype_data)
            else:
                # For custom groups, normal behavior
                for colortype_name, colortype_data in colortypes_data.items():
                    p = props.ColorTypes.add()
                    p.name = colortype_name
                    UnifiedColorTypeManager._apply_colortype_data_to_property(p, colortype_data)
        
            if props.ColorTypes:
                props.active_ColorType_index = 0
        except Exception as e:
            print(f"Error loading colortypes: {e}")

    @staticmethod
    def _create_default_colortype_data(colortype_name: str) -> dict:
        """Creates default colortype data for a given colortype name"""
        # Define specific colors for each type
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
        
        colors = color_map.get(colortype_name, color_map["NOTDEFINED"])
        
        return {
            "name": colortype_name,
            "start_color": colors["start"],
            "in_progress_color": colors["active"],
            "end_color": colors["end"],
            "consider_start": False,
            "consider_active": True,
            "consider_end": True,
            "use_start_original_color": False,
            "use_active_original_color": False,
            "use_end_original_color": not colors.get("hide", False),
            "start_transparency": 0.0,
            "active_start_transparency": 0.0,
            "active_finish_transparency": 0.0,
            "active_transparency_interpol": 1.0,
            "end_transparency": 0.0,
            "hide_at_end": colors.get("hide", False)
        }

    @staticmethod
    def _apply_colortype_data_to_property(property_obj, colortype_data: dict):
        """Applies colortype data to a property object with safe fallbacks"""
        try:
            # Colors with safe fallbacks
            for attr in ("start_color", "in_progress_color", "end_color"):
                col = colortype_data.get(attr, [1, 1, 1, 1])
                if isinstance(col, (list, tuple)) and len(col) >= 3:
                    rgba = list(col) + [1.0] * (4 - len(col))
                    setattr(property_obj, attr, rgba[:4])
                else:
                    setattr(property_obj, attr, [1.0, 1.0, 1.0, 1.0])
        
            # Booleans with fallbacks
            bool_attrs = {
                "use_start_original_color": False,
                "use_active_original_color": False, 
                "use_end_original_color": True,
                "consider_start": False,
                "consider_active": True,
                "consider_end": True,
                "hide_at_end": False
            }
            for attr, default in bool_attrs.items():
                if hasattr(property_obj, attr):
                    setattr(property_obj, attr, bool(colortype_data.get(attr, default)))
        
            # Transparencies with fallbacks
            float_attrs = {
                "active_start_transparency": 0.0,
                "active_finish_transparency": 0.0,
                "active_transparency_interpol": 1.0,
                "start_transparency": 0.0,
                "end_transparency": 0.0
            }
            for attr, default in float_attrs.items():
                if hasattr(property_obj, attr):
                    try:
                        val = float(colortype_data.get(attr, default))
                        setattr(property_obj, attr, max(0.0, min(1.0, val)))
                    except (TypeError, ValueError):
                        setattr(property_obj, attr, default)
                        
        except Exception as e:
            print(f"Error applying colortype data: {e}")

# ============================================================================
# CALLBACK FUNCTIONS - Improved with the new system
# ============================================================================

def getTaskColumns(self, context):
    if not SequenceData.is_loaded:
        SequenceData.load()
    return SequenceData.data["task_columns_enum"]


def getTaskTimeColumns(self, context):
    if not SequenceData.is_loaded:
        SequenceData.load()
    return SequenceData.data["task_time_columns_enum"]


def getWorkSchedules(self, context):
    if not SequenceData.is_loaded:
        SequenceData.load()
    return SequenceData.data["work_schedules_enum"]


def getWorkCalendars(self, context):
    if not SequenceData.is_loaded:
        SequenceData.load()
    return SequenceData.data["work_calendars_enum"]


def get_animation_color_schemes_items(self, context):
    """Gets colortype items for dropdown"""
    props = tool.Sequence.get_animation_props()
    items = []
    try:
        for i, p in enumerate(props.ColorTypes):
            name = p.name or f"colortype {i+1}"
            items.append((name, name, "", i))
    except Exception:
        pass
    if not items:
        items = [("", "<no colortypes>", "", 0)]
    return items


def get_custom_group_colortype_items(self, context):
    """
    Gets colortype items ONLY from the selected custom group (excludes DEFAULT).
    This version reads directly from the JSON and is more lenient to allow UI selection
    even if colortype data is incomplete.
    """
    items = []
    try:
        anim_props = tool.Sequence.get_animation_props()
        selected_group = getattr(anim_props, "task_colortype_group_selector", "")
        
        print(f"🔍 get_custom_group_colortype_items called for task {getattr(self, 'ifc_definition_id', 'unknown')}")
        print(f"🔍 selected_group: '{selected_group}'")
        
        if selected_group and selected_group != "DEFAULT":
            # Direct and flexible reading from JSON
            all_sets = UnifiedColorTypeManager._read_sets_json(context)
            group_data = all_sets.get(selected_group, {})
            colortypes_list = group_data.get("ColorTypes", [])
            
            colortype_names = []
            for colortype in colortypes_list:
                if isinstance(colortype, dict) and "name" in colortype:
                    # Ensure we only add valid non-numeric string names
                    name = str(colortype["name"])
                    if name and not name.isdigit():
                        colortype_names.append(name)
            
            # Always include an empty option first to prevent enum errors
            items.append(("", "<none>", "No colortype selected", 0))
            
            for i, name in enumerate(sorted(colortype_names)):
                items.append((name, name, f"colortype from {selected_group}", i + 1))
            
            print(f"🔍 Found {len(colortype_names)} colortypes: {colortype_names}")
        else:
            print(f"🔍 No valid group selected: '{selected_group}'")
    
    # --- START OF CORRECTION ---
    # If there are no profiles, ensure that at least the null option exists to avoid enum errors.
    except Exception as e:
        print(f"Error getting custom group colortypes: {e}")
        items.append(("", "<error loading colortypes>", "", 0))

    if not items:
        anim_props = tool.Sequence.get_animation_props()
        selected_group = getattr(anim_props, "task_colortype_group_selector", "")
        if not selected_group:
            items.append(("", "<select custom group first>", "", 0))
        elif selected_group == "DEFAULT":
            items.append(("", "<DEFAULT not allowed here>", "", 0))
        else:
            items.append(("", f"<no colortypes in {selected_group}>", "", 0))
    
    # Ensure that the null option is always present if there are no other items
    if not items:
        items.append(("", "<none>", "No colortypes available", 0))
    # --- END OF CORRECTION ---
    
    print(f"🔍 Final items returned: {[(item[0], item[1]) for item in items]}")
    
    # CRITICAL: Ensure empty option is ALWAYS first and present
    if not any(item[0] == "" for item in items):
        print("🚨 CRITICAL: No empty option found, forcing one")
        items.insert(0, ("", "<none>", "No colortype selected", 0))
    
    # Ensure the empty option is always first
    empty_item = None
    non_empty_items = []
    for item in items:
        if item[0] == "":
            empty_item = item
        else:
            non_empty_items.append(item)
    
    if empty_item:
        final_items = [empty_item] + non_empty_items
    else:
        final_items = [("", "<none>", "No colortype selected", 0)] + non_empty_items
    
    print(f"🔍 FINAL SORTED items: {[(item[0], item[1]) for item in final_items]}")
    return final_items

def update_active_work_schedule_id(self, context):
    """
    Callback que se ejecuta cuando cambia el cronograma activo.
    Guarda automáticamente los perfiles del cronograma anterior y carga los del nuevo.
    """
    try:
        import bonsai.tool as tool
        # DEBUG: Check that the callback is running
        current_ws_id = getattr(self, 'active_work_schedule_id', 0)
        previous_ws_id = getattr(context.scene, '_previous_work_schedule_id', 0)
        print(f"🔄 DEBUG: Callback ejecutado - Cambio de WS {previous_ws_id} → {current_ws_id}")
        
        # Avoid infinite loops during temporary changes
        if getattr(context.scene, '_updating_work_schedule_id', False):
            print("🔄 DEBUG: Saliendo por bucle infinito")
            return
            
        # Only process if the active schedule actually changed
        if current_ws_id == previous_ws_id:
            print("🔄 DEBUG: Saliendo - no hay cambio real")
            return  # No hay cambio real
            
        # Import the necessary functions from operator.py
        from .operators.schedule_task_operators import snapshot_all_ui_state
        
        # 1. Save profiles from the previous schedule (if there was one)
        if previous_ws_id != 0:
            try:
                print(f"💾 DEBUG: Guardando perfiles del WS {previous_ws_id}")
                
                # Mark that we are in the process of updating
                context.scene['_updating_work_schedule_id'] = True
                
                # Temporarily restore the previous ID to make a correct snapshot
                old_id = self.active_work_schedule_id
                self.active_work_schedule_id = previous_ws_id
                snapshot_all_ui_state(context)
                self.active_work_schedule_id = old_id
                
                print(f"✅ DEBUG: Perfiles del WS {previous_ws_id} guardados")
                
            except Exception as e:
                print(f"❌ DEBUG: Error guardando perfiles del WS {previous_ws_id}: {e}")
            finally:
                context.scene['_updating_work_schedule_id'] = False
        
        # 2. Update the previous ID in the context
        context.scene['_previous_work_schedule_id'] = current_ws_id
        print(f"🎯 DEBUG: Nuevo WS anterior establecido: {current_ws_id}")
        
        # Note: The restoration will be done in the operator AFTER load_task_tree
        print("ℹ️ Variance colors will remain active - use Clear Variance button to reset")
                
    except Exception as e:
        print(f"❌ DEBUG: Error en update_active_work_schedule_id: {e}")

def update_active_task_index(self, context):
    """
    Updates active task index, synchronizes colortypes,
    and selects associated 3D objects in the viewport (for single click).
    """
    task_ifc = tool.Sequence.get_highlighted_task()
    self.highlighted_task_id = task_ifc.id() if task_ifc else 0
    tool.Sequence.update_task_ICOM(task_ifc)
    bonsai.bim.module.pset.data.refresh()

    if self.editing_task_type == "SEQUENCE":
        tool.Sequence.load_task_properties()

    try:
        tprops = tool.Sequence.get_task_tree_props()
        if tprops.tasks and self.active_task_index < len(tprops.tasks):
            task_pg = tprops.tasks[self.active_task_index]
            try:
                # Solo sincronizar DEFAULT si no hay grupos personalizados
                user_groups = UnifiedColorTypeManager.get_user_created_groups(context)
                if not user_groups:
                    UnifiedColorTypeManager.sync_default_group_to_predefinedtype(context, task_pg)
                
                anim_props = tool.Sequence.get_animation_props()
                if anim_props.ColorType_groups:
                    UnifiedColorTypeManager.sync_task_colortypes(context, task_pg, anim_props.ColorType_groups)
            except NameError:
                # UnifiedColorTypeManager not available, skip colortype syncing
                pass
    except Exception as e:
        print(f"[ERROR] Error syncing colortypes in update_active_task_index: {e}")

    # --- START OF CORRECTED CODE ---
    # --- 3D SELECTION LOGIC FOR SINGLE CLICK ---
    if not task_ifc:
        try:
            bpy.ops.object.select_all(action='DESELECT')
        except RuntimeError:
            # Ocurre si no estamos en modo objeto, es seguro ignorarlo.
            pass
        # Early exit for update function - don't continue with 3D selection
        return

    try:
        outputs = tool.Sequence.get_task_outputs(task_ifc)
        
        # Deselect everything else first
        if bpy.context.view_layer.objects.active:
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

        if outputs:
            objects_to_select = [tool.Ifc.get_object(p) for p in outputs if tool.Ifc.get_object(p)]
            
            if objects_to_select:
                for obj in objects_to_select:
                    # <-- STEP 1: Make sure the object is visible and selectable
                    obj.hide_set(False)
                    obj.hide_select = False
                    
                    # <-- STEP 2: Select the object
                    obj.select_set(True)
                
                # <-- STEP 3: Set the first object as active
                context.view_layer.objects.active = objects_to_select[0]
                
                # <-- STEP 4: Center the 3D view on the selected objects
                bpy.ops.view3d.view_selected()
                
    except Exception as e:
        print(f"Error selecting 3D objects for task: {e}")
    # --- FIN DEL CÓDIGO CORREGIDO ---


def get_task_colortype_items(self, context):
    """Enum items function for task colortypes - separated from update function"""
    items = []
    try:
        anim_props = tool.Sequence.get_animation_props()
        selected_group = getattr(anim_props, "task_colortype_group_selector", "")
        
        print(f"🔍 Getting colortypes for custom group: '{selected_group}'")
        
        # CRÃ TICO: Solo mostrar perfiles si hay un grupo personalizado seleccionado
        if selected_group and selected_group != "DEFAULT":
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
            colortypes = UnifiedColorTypeManager.get_group_colortypes(context, selected_group)
            
            for i, name in enumerate(sorted(colortypes.keys())):
                items.append((name, name, f"colortype from {selected_group}", i))
            
            print(f"✅ Found {len(items)} colortypes in group '{selected_group}'")

    except Exception as e:
        print(f"❌ Error getting custom group colortypes: {e}")
        items = [("", "<error loading colortypes>", "", 0)]

    if not items:
        anim_props = tool.Sequence.get_animation_props()
        selected_group = getattr(anim_props, "task_colortype_group_selector", "")
        if not selected_group:
            items = [("", "<select custom group first>", "", 0)]
        elif selected_group == "DEFAULT":
            items = [("", "<DEFAULT not allowed here>", "", 0)]
        else:
            items = [("", f"<no colortypes in {selected_group}>", "", 0)]
            
    return items


def update_active_task_outputs(self, context):
    task = tool.Sequence.get_highlighted_task()
    outputs = tool.Sequence.get_task_outputs(task)
    tool.Sequence.load_task_outputs(outputs)


def update_active_task_resources(self, context):
    task = tool.Sequence.get_highlighted_task()
    resources = tool.Sequence.get_task_resources(task)
    tool.Sequence.load_task_resources(resources)


def update_active_task_inputs(self, context):
    task = tool.Sequence.get_highlighted_task()
    inputs = tool.Sequence.get_task_inputs(task)
    tool.Sequence.load_task_inputs(inputs)


def updateTaskName(self: "Task", context: bpy.types.Context) -> None:
    props = tool.Sequence.get_work_schedule_props()
    if not props.is_task_update_enabled or self.name == "Unnamed":
        return
    ifc_file = tool.Ifc.get()
    ifcopenshell.api.sequence.edit_task(
        ifc_file,
        task=ifc_file.by_id(self.ifc_definition_id),
        attributes={"Name": self.name},
    )
    SequenceData.load()
    if props.active_task_id == self.ifc_definition_id:
        attribute = props.task_attributes["Name"]
        attribute.string_value = self.name


def updateTaskIdentification(self: "Task", context: bpy.types.Context) -> None:
    props = tool.Sequence.get_work_schedule_props()
    if not props.is_task_update_enabled or self.identification == "XXX":
        return
    ifc_file = tool.Ifc.get()
    ifcopenshell.api.sequence.edit_task(
        ifc_file,
        task=ifc_file.by_id(self.ifc_definition_id),
        attributes={"Identification": self.identification},
    )
    SequenceData.load()
    if props.active_task_id == self.ifc_definition_id:
        attribute = props.task_attributes["Identification"]
        attribute.string_value = self.identification


def updateTaskTimeStart(self: "Task", context: bpy.types.Context) -> None:
    updateTaskTimeDateTime(self, context, "start", "Schedule")


def updateTaskTimeFinish(self: "Task", context: bpy.types.Context) -> None:
    updateTaskTimeDateTime(self, context, "finish", "Schedule")


def updateTaskTimeActualStart(self: "Task", context: bpy.types.Context) -> None:
    updateTaskTimeDateTime(self, context, "actual_start", "Actual")


def updateTaskTimeActualFinish(self: "Task", context: bpy.types.Context) -> None:
    updateTaskTimeDateTime(self, context, "actual_finish", "Actual")


def updateTaskTimeEarlyStart(self: "Task", context: bpy.types.Context) -> None:
    updateTaskTimeDateTime(self, context, "early_start", "Early")


def updateTaskTimeEarlyFinish(self: "Task", context: bpy.types.Context) -> None:
    updateTaskTimeDateTime(self, context, "early_finish", "Early")


def updateTaskTimeLateStart(self: "Task", context: bpy.types.Context) -> None:
    updateTaskTimeDateTime(self, context, "late_start", "Late")


def updateTaskTimeLateFinish(self: "Task", context: bpy.types.Context) -> None:
    updateTaskTimeDateTime(self, context, "late_finish", "Late")


def updateTaskTimeDateTime(
    self: "Task",
    context: bpy.types.Context,
    prop_name: str,
    ifc_date_type: Literal["Schedule", "Actual", "Early", "Late"],
) -> None:
    props = tool.Sequence.get_work_schedule_props()

    if not props.is_task_update_enabled:
        return

    prop_value = getattr(self, prop_name)

    if prop_value == "-":
        return

    ifc_file = tool.Ifc.get()

    try:
        dt_value = parser.isoparse(prop_value)
    except:
        try:
            dt_value = parser.parse(prop_value, dayfirst=True, fuzzy=True)
        except:
            setattr(self, prop_name, "-")
            return

    task = ifc_file.by_id(self.ifc_definition_id)
    if task.TaskTime:
        task_time = task.TaskTime
    else:
        task_time = ifcopenshell.api.sequence.add_task_time(ifc_file, task=task)
        SequenceData.load()

    ifc_attribute_name = "Schedule" + startfinish.capitalize()

    if SequenceData.data["task_times"][task_time.id()][ifc_attribute_name] == dt_value:
        canonical_value = canonicalise_time(dt_value)
        if prop_value != canonical_value:
            setattr(self, startfinish, canonical_value)
        return

    ifcopenshell.api.sequence.edit_task_time(
        ifc_file,
        task_time=task_time,
        attributes={ifc_attribute_name: dt_value},
    )
    SequenceData.load()
    bpy.ops.bim.load_task_properties()



def updateTaskDuration(self: "Task", context: bpy.types.Context) -> None:
    props = tool.Sequence.get_work_schedule_props()
    if not props.is_task_update_enabled:
        return

    if self.duration == "-":
        return

    duration = ifcopenshell.util.date.parse_duration(self.duration)
    if not duration:
        self.duration = "-"
        return

    ifc_file = tool.Ifc.get()
    task = ifc_file.by_id(self.ifc_definition_id)
    if task.TaskTime:
        task_time = task.TaskTime
    else:
        task_time = ifcopenshell.api.sequence.add_task_time(ifc_file, task=task)
    ifcopenshell.api.sequence.edit_task_time(
        ifc_file,
        task_time=task_time,
        attributes={"ScheduleDuration": duration},
    )
    core.load_task_properties(tool.Sequence)
    tool.Sequence.refresh_task_resources()


def updateTaskPredefinedType(self: "Task", context: bpy.types.Context) -> None:
    """Callback when PredefinedType changes - auto-syncs to DEFAULT group"""
    props = tool.Sequence.get_work_schedule_props()
    if not props.is_task_update_enabled:
        return
    try:
        # --- START OF CORRECTION ---
        # The IFC attribute editing logic is already handled by the attribute's callback.
        # This callback should only be concerned with UI synchronization.

        # 1. Get the new PredefinedType value directly from the task.
        #    This is more robust than searching the attribute collection.
        try:
            from bonsai.bim.module.sequence.data import SequenceData
            task_data = SequenceData.data["tasks"][self.ifc_definition_id]
            new_predefined_type = task_data.get("PredefinedType", "NOTDEFINED") or "NOTDEFINED"
        except Exception:
            # Fallback if data is not loaded
            new_predefined_type = "NOTDEFINED"

        # 2. Sincronizar el perfil DEFAULT de la tarea con este nuevo tipo.
        # Solo si no hay grupos personalizados
        user_groups = UnifiedColorTypeManager.get_user_created_groups(context)
        if not user_groups:
            UnifiedColorTypeManager.sync_default_group_to_predefinedtype(context, self)

        print(f"[AUTO-SYNC] Task {self.ifc_definition_id}: PredefinedType changed, DEFAULT colortype synced to '{new_predefined_type}'.")
    except Exception as e:
        # --- END OF CORRECTION ---
        print(f"[ERROR] updateTaskPredefinedType: {e}")


def get_schedule_predefined_types(self, context):
    if not SequenceData.is_loaded:
        SequenceData.load()
    return SequenceData.data["schedule_predefined_types_enum"]


def update_work_schedule_predefined_type(self: "BIMWorkScheduleProperties", context: bpy.types.Context) -> None:
    """Se ejecuta cuando cambia el tipo de cronograma - NO limpiar automáticamente"""
    try:
        print(f"🔄 Work schedule predefined type changed to: {self.work_schedule_predefined_types}")
        print("ℹ️ Variance colors will remain active - use Clear Variance button to reset")
            
    except Exception as e:
        print(f"⚠️ Error in update_work_schedule_predefined_type: {e}")


def update_visualisation_start(self: "BIMWorkScheduleProperties", context: bpy.types.Context) -> None:
    update_visualisation_start_finish(self, context, "visualisation_start")


def update_visualisation_finish(self: "BIMWorkScheduleProperties", context: bpy.types.Context) -> None:
    update_visualisation_start_finish(self, context, "visualisation_finish")


def update_visualisation_start_finish(
    self: "BIMWorkScheduleProperties",
    context: bpy.types.Context,
    startfinish: Literal["visualisation_start", "visualisation_finish"],
) -> None:
    startfinish_value = getattr(self, startfinish)
    try:
        startfinish_datetime = parser.isoparse(startfinish_value)
    except Exception:
        try:
            startfinish_datetime = parser.parse(startfinish_value, dayfirst=True, fuzzy=True)
        except Exception:
            # If parsing fails, set to "-" only if it's not already "-" to prevent infinite loop
            if startfinish_value != "-":
                setattr(self, startfinish, "-")
            return

    # Canonicalize using tool.Sequence.isodate_datetime to ensure consistent string format
    canonical_value_str = tool.Sequence.isodate_datetime(startfinish_datetime, include_time=True)
    if getattr(self, startfinish) != canonical_value_str:
        setattr(self, startfinish, canonical_value_str)


def update_color_full(self, context):
    """Updates full bar color"""
    material = bpy.data.materials.get("color_full")
    if material:
        props = tool.Sequence.get_animation_props()
        inputs = tool.Blender.get_material_node(material, "BSDF_PRINCIPLED").inputs
        color = inputs["Base Color"].default_value
        color[0] = props.color_full[0]
        color[1] = props.color_full[1]
        color[2] = props.color_full[2]
        try:
            inputs["Alpha"].default_value = (props.color_full[3] if len(props.color_full) > 3 else 1.0)
            material.blend_method = 'BLEND'
            material.shadow_method = 'HASHED'
        except Exception:
            pass


def update_color_progress(self, context):
    """Updates progress bar color"""
    material = bpy.data.materials.get("color_progress")
    if material:
        props = tool.Sequence.get_animation_props()
        inputs = tool.Blender.get_material_node(material, "BSDF_PRINCIPLED").inputs
        color = inputs["Base Color"].default_value
        color[0] = props.color_progress[0]
        color[1] = props.color_progress[1]
        color[2] = props.color_progress[2]
        try:
            inputs["Alpha"].default_value = (props.color_progress[3] if len(props.color_progress) > 3 else 1.0)
            material.blend_method = 'BLEND'
            material.shadow_method = 'HASHED'
        except Exception:
            pass


def update_sort_reversed(self: "BIMWorkScheduleProperties", context: bpy.types.Context) -> None:
    if self.active_work_schedule_id:
        core.load_task_tree(
            tool.Sequence,
            work_schedule=tool.Ifc.get().by_id(self.active_work_schedule_id),
        )


def update_filter_by_active_schedule(self: "BIMWorkScheduleProperties", context: bpy.types.Context) -> None:
    if obj := context.active_object:
        product = tool.Ifc.get_entity(obj)
        assert product
        core.load_product_related_tasks(tool.Sequence, product=product)


def switch_options(self, context):
    """Toggles between visualization and snapshot"""
    if self.should_show_visualisation_ui:
        self.should_show_snapshot_ui = False
    else:
        if not self.should_show_snapshot_ui:
            self.should_show_snapshot_ui = True


def switch_options2(self, context):
    """Toggles between snapshot and visualization"""
    if self.should_show_snapshot_ui:
        self.should_show_visualisation_ui = False
    else:
        if not self.should_show_visualisation_ui:
            self.should_show_visualisation_ui = True


def get_saved_color_schemes(self, context):
    """Gets saved color schemes (legacy - maintain for compatibility)"""
    if not AnimationColorSchemeData.is_loaded:
        AnimationColorSchemeData.load()
    return AnimationColorSchemeData.data.get("saved_color_schemes", [])


def get_internal_ColorType_sets_enum(self, context):
    """Gets enum of ALL available colortype groups, including DEFAULT."""
    from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
    try:
        # Get all groups directly from the source
        all_groups = sorted(list(UnifiedColorTypeManager._read_sets_json(context).keys()))
        
        if all_groups:
            # Ensure "DEFAULT" appears first for convenience
            if "DEFAULT" in all_groups:
                all_groups.remove("DEFAULT")
                all_groups.insert(0, "DEFAULT")
            return [(name, name, f"colortype group: {name}") for name in all_groups]
    except Exception:
        pass
    
    # Fallback - always have at least DEFAULT
    return [("DEFAULT", "DEFAULT", "Auto-managed default group")]



def get_all_groups_enum(self, context):
    """Enum para todos los grupos (incluyendo DEFAULT)."""
    try:
        groups = UnifiedColorTypeManager.get_all_groups(context)
        items = []
        for i, group in enumerate(sorted(groups)):
            desc = "Auto-managed colortypes by PredefinedType" if group == "DEFAULT" else "Custom colortype group"
            items.append((group, group, desc, i))
        return items if items else [("DEFAULT", "DEFAULT", "Auto-managed default group", 0)]
    except Exception:
        return [("DEFAULT", "DEFAULT", "Auto-managed default group", 0)]


def get_user_created_groups_enum(self, context):
    """Returns EnumProperty items for user-created groups, excluding 'DEFAULT'."""
    from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
    try:
        user_groups = UnifiedColorTypeManager.get_user_created_groups(context)
        if user_groups:
            return [(name, name, f"colortype group: {name}") for name in user_groups]
    except Exception:
        pass
    return [("NONE", "<no custom groups>", "Create custom groups in the Animation Color Schemes panel")]


def update_task_colortype_group_selector(self, context):
    """Update when custom group selector changes - ensures colortypes are loaded"""
    try:
        # 'self' is BIMAnimationProperties
        if self.task_colortype_group_selector and self.task_colortype_group_selector not in ("", "NONE"):
            print(f"📄 Custom group selected: {self.task_colortype_group_selector}")
            
            # Load profiles from this group into the UI to make them available
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
            UnifiedColorTypeManager.load_colortypes_into_collection(self, context, self.task_colortype_group_selector)
            
            # OPTIONALLY sync to ColorType_groups for editing if user wants
            # Only sync if user hasn't manually selected a different group for editing
            if not hasattr(self, '_ColorType_groups_manually_set') or not self._ColorType_groups_manually_set:
                self.ColorType_groups = self.task_colortype_group_selector
                print(f"🔄 Auto-synced ColorType_groups to '{self.task_colortype_group_selector}' for editing")
            
            # Actualizar enum para refrescar dropdown de perfiles
            try:
                tprops = tool.Sequence.get_task_tree_props()
                wprops = tool.Sequence.get_work_schedule_props()
                if tprops.tasks and wprops.active_task_index < len(tprops.tasks):
                    task = tprops.tasks[wprops.active_task_index]
                    # Synchronize profiles for the active task with the new group
                    UnifiedColorTypeManager.sync_task_colortypes(context, task, self.task_colortype_group_selector)
                    
                    # Force enum update to refresh profile dropdown
                    task.selected_colortype_in_active_group = task.selected_colortype_in_active_group
                    
                    print(f"✅ colortypes automatically loaded for group: {self.task_colortype_group_selector}")
            except Exception as e:
                print(f"⚠ Error syncing task colortypes: {e}")

    except Exception as e:
        print(f"❌ Error in update_task_colortype_group_selector: {e}")


def monitor_predefined_type_change(context):
    """Monitors changes in PredefinedType and auto-syncs DEFAULT"""
    try:
        tprops = tool.Sequence.get_task_tree_props()
        wprops = tool.Sequence.get_work_schedule_props()

        if not (tprops.tasks and wprops.active_task_index < len(tprops.tasks)):
            return

        task_pg = tprops.tasks[wprops.active_task_index]
        # Solo sincronizar DEFAULT si no hay grupos personalizados
        user_groups = UnifiedColorTypeManager.get_user_created_groups(context)
        if not user_groups:
            UnifiedColorTypeManager.sync_default_group_to_predefinedtype(context, task_pg)

    except Exception as e:
        print(f"[ERROR] monitor_predefined_type_change: {e}")


def update_ColorType_group(self, context):
    """Updates active colortype group - Improved with the new system"""
    
    # Mark that user manually changed ColorType_groups for editing
    self._ColorType_groups_manually_set = True
    print(f"🎯 User manually selected '{self.ColorType_groups}' for editing")
    
    # Sync to JSON first
    try:
        tool.Sequence.sync_active_group_to_json()
    except Exception as e:
        print(f"Error syncing colortypes on group change: {e}")

    # Clean up invalid mappings
    UnifiedColorTypeManager.cleanup_invalid_mappings(context)

    # Load colortypes of the selected group
    if self.ColorType_groups:
        UnifiedColorTypeManager.load_colortypes_into_collection(self, context, self.ColorType_groups)

    # Synchronize active task if it exists
    try:
        tprops = tool.Sequence.get_task_tree_props()
        wprops = tool.Sequence.get_work_schedule_props()
        if tprops.tasks and wprops.active_task_index < len(tprops.tasks):
            task = tprops.tasks[wprops.active_task_index]

            # Sync the active custom group colortype
            entry = UnifiedColorTypeManager.sync_task_colortypes(context, task, self.ColorType_groups)
            if entry and hasattr(task, 'selected_colortype_in_active_group'):
                # Get valid colortype names for the selected group to avoid enum errors
                valid_colortypes_dict = UnifiedColorTypeManager.get_group_colortypes(context, self.ColorType_groups)
                # --- START OF CORRECTION ---
                # Ensure that the list of valid profiles always includes a null option.
                valid_colortype_names = [""] + (list(valid_colortypes_dict.keys()) if valid_colortypes_dict else [])
                selected_colortype = entry.selected_colortype or ""
                
                # Only assign if it's a valid enum value or if no valid colortypes exist
                # Also allow empty string since we now include it as a valid option
                # But never assign numeric strings
                if selected_colortype and selected_colortype.isdigit():
                    print(f"⚠️ Prevented assignment of numeric enum value '{selected_colortype}', using empty string instead")
                    safe_set_selected_colortype_in_active_group(task, "")
                elif selected_colortype in valid_colortype_names:
                    safe_set_selected_colortype_in_active_group(task, selected_colortype)
                elif valid_colortype_names and len(valid_colortype_names) > 1:
                    # If there's an invalid selection but colortypes exist, select the first one
                    # (which is not the null option, if possible)
                    safe_set_selected_colortype_in_active_group(task, valid_colortype_names[1])
                else:
                    safe_set_selected_colortype_in_active_group(task, "")
                # --- FIN DE LA CORRECCIÓN ---
    except Exception as e:
        print(f"[ERROR] Error in update_colortype_group: {e}")


def updateAssignedResourceName(self, context):
    pass


def updateAssignedResourceUsage(self: "TaskResource", context: object) -> None:
    props = tool.Resource.get_resource_props()
    if not props.is_resource_update_enabled:
        return
    if not self.schedule_usage:
        return
    resource = tool.Ifc.get().by_id(self.ifc_definition_id)
    if resource.Usage and resource.Usage.ScheduleUsage == self.schedule_usage:
        return
    tool.Resource.run_edit_resource_time(resource, attributes={"ScheduleUsage": self.schedule_usage})
    tool.Sequence.load_task_properties()
    tool.Resource.load_resource_properties()
    tool.Sequence.refresh_task_resources()
    bonsai.bim.module.resource.data.refresh()
    refresh_sequence_data()
    bonsai.bim.module.pset.data.refresh()



def update_task_bar_list(self: "Task", context: bpy.types.Context) -> None:
    props = tool.Sequence.get_work_schedule_props()
    if not props.is_task_update_enabled:
        return
    
    # Agregar o remover de la lista
    if self.has_bar_visual:
        tool.Sequence.add_task_bar(self.ifc_definition_id)
    else:
        tool.Sequence.remove_task_bar(self.ifc_definition_id)
    
    # Actualizar visualización inmediatamente
    try:
        tool.Sequence.refresh_task_bars()
    except Exception as e:
        print(f"⚠️ Error refreshing task bars: {e}")



def update_use_active_colortype_group(self: "Task", context):
    """Updates usage of the active colortype group"""
    try:
        anim_props = tool.Sequence.get_animation_props()
        selected_group = getattr(anim_props, "task_colortype_group_selector", "")
        
        # CRÃ TICO: Usar el grupo seleccionado en task_colortype_group_selector, NO ColorType_groups
        if selected_group and selected_group != "DEFAULT":
            entry = UnifiedColorTypeManager.sync_task_colortypes(context, self, selected_group)
            if entry:
                entry.enabled = bool(self.use_active_colortype_group)
                print(f"📄 Task {self.ifc_definition_id}: Group {selected_group} enabled = {entry.enabled}")
    except Exception as e:
        print(f"❌ Error updating use_active_colortype_group: {e}")


def safe_set_animation_color_schemes(task_obj, value):
    """Safely sets the animation_color_schemes property with validation"""
    try:
        # Try to set the value directly first
        try:
            task_obj.animation_color_schemes = value
            print(f"✅ Successfully set animation_color_schemes to '{value}'")
            return
        except Exception as enum_error:
            # If the value is not valid for the current enum, try fallback options
            if "enum" in str(enum_error).lower():
                print(f"🔄 Value '{value}' not valid for animation_color_schemes enum, trying fallbacks...")
                
                # Get current valid items to find a fallback
                try:
                    valid_items = get_animation_color_schemes_items(task_obj, bpy.context)
                    valid_values = [item[0] for item in valid_items]
                    
                    # Try to use the first valid option (usually empty string)
                    if valid_values:
                        fallback_value = valid_values[0]
                        task_obj.animation_color_schemes = fallback_value
                        print(f"🔄 Used fallback value '{fallback_value}' instead of '{value}' for animation_color_schemes")
                    else:
                        print(f"⚠️ No valid enum options available for animation_color_schemes, skipping assignment")
                except Exception as fallback_error:
                    print(f"❌ Fallback assignment for animation_color_schemes also failed: {fallback_error}")
                    pass
            else:
                raise enum_error
        
    except Exception as e:
        print(f"❌ Error in safe_set_animation_color_schemes: {e}")
        try:
            # Final fallback - try empty string or first available option
            valid_items = get_animation_color_schemes_items(task_obj, bpy.context)
            if valid_items:
                fallback_value = valid_items[0][0]  # First valid option
                task_obj.animation_color_schemes = fallback_value
                print(f"🔄 Final fallback for animation_color_schemes: using '{fallback_value}'")
        except:
            print("❌ All fallback attempts failed for animation_color_schemes, skipping assignment")
            pass

def safe_set_selected_colortype_in_active_group(task_obj, value, skip_validation=False):
    """Safely sets the selected_colortype_in_active_group property with validation"""
    try:
        task_id = getattr(task_obj, 'ifc_definition_id', 'unknown')
        print(f"🔧 safe_set_selected_colortype_in_active_group called for task {task_id} with value='{value}' (type: {type(value)})")
        
        # Validate the value before assignment
        if value and (value.isdigit() or value == "0"):
            print(f"🚫 Prevented assignment of invalid enum value '{value}' to selected_colortype_in_active_group")
            value = ""
        
        # Skip validation during copy operations to allow setting values that might be valid later
        if not skip_validation:
            # Get context for validation
            context = bpy.context
            valid_items = get_custom_group_colortype_items(task_obj, context)
            valid_values = [item[0] for item in valid_items]
            
            if value and value not in valid_values:
                print(f"🚫 Value '{value}' not in valid enum options: {valid_values}, using empty string")
                value = ""
        
        # Safely set the property with fallback handling
        try:
            # Final validation just before assignment
            if str(value) in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'] or str(value).isdigit():
                print(f"🚫 CRITICAL: Blocking numeric value '{value}' just before setattr")
                value = ""
            
            print(f"🔧 About to setattr selected_colortype_in_active_group = '{value}'")
            setattr(task_obj, "selected_colortype_in_active_group", value)
            print(f"✅ Successfully set selected_colortype_in_active_group = '{value}'")
            
        except Exception as enum_error:
            print(f"❌ setattr failed with error: {enum_error}")
            # If the value is not valid for the current enum, try fallback options
            if "enum" in str(enum_error).lower():
                # Get current valid items to find a fallback
                try:
                    valid_items = get_custom_group_colortype_items(task_obj, bpy.context)
                    valid_values = [item[0] for item in valid_items]
                    
                    # Try to use the first valid option (usually empty string)
                    if valid_values:
                        fallback_value = valid_values[0]
                        print(f"🔄 Trying fallback value '{fallback_value}' instead of '{value}' for enum")
                        
                        # If empty string still fails, try the first non-empty ColorType
                        if fallback_value == "" and len(valid_values) > 1:
                            fallback_value = valid_values[1]  # First actual ColorType
                            print(f"🔄 Empty string failed, trying first ColorType: '{fallback_value}'")
                        
                        setattr(task_obj, "selected_colortype_in_active_group", fallback_value)
                        print(f"✅ Successfully set fallback value '{fallback_value}'")
                    else:
                        print(f"⚠️ No valid enum options available, skipping assignment")
                except Exception as fallback_error:
                    print(f"❌ Fallback assignment also failed: {fallback_error}")
                    # Last resort - don't assign anything
                    pass
            else:
                raise enum_error
        
    except Exception as e:
        print(f"❌ Error in safe_set_selected_colortype_in_active_group: {e}")
        # Try to get any valid fallback instead of forcing empty string
        try:
            valid_items = get_custom_group_colortype_items(task_obj, bpy.context)
            if valid_items:
                fallback_value = valid_items[0][0]  # First valid option
                setattr(task_obj, "selected_colortype_in_active_group", fallback_value)
                print(f"🔄 Final fallback: using '{fallback_value}'")
        except:
            print("❌ All fallback attempts failed, skipping assignment")
            pass

def update_selected_colortype_in_active_group(self: "Task", context):
    """Updates the selected colortype in the active group"""
    try:
        # Validate that the current value is not a numeric string or invalid
        current_value = self.selected_colortype_in_active_group
        
        # Get valid enum items to check against
        valid_items = get_custom_group_colortype_items(self, context)
        valid_values = [item[0] for item in valid_items]
        
        # Check for invalid values
        if current_value and (current_value.isdigit() or current_value not in valid_values):
            print(f"⚠️ Invalid enum value '{current_value}' detected for selected_colortype_in_active_group, resetting to empty")
            # Don't recursively call the update function - directly access the property
            self.__dict__["selected_colortype_in_active_group"] = ""
            return
        
        anim_props = tool.Sequence.get_animation_props()
        selected_group = getattr(anim_props, "task_colortype_group_selector", "")
        
        # CRÃ TICO: Usar el grupo seleccionado en task_colortype_group_selector, NO ColorType_groups
        if selected_group and selected_group != "DEFAULT":
            entry = UnifiedColorTypeManager.sync_task_colortypes(context, self, selected_group)
            if entry:
                entry.selected_colortype = self.selected_colortype_in_active_group
                print(f"📄 Task {self.ifc_definition_id}: Selected colortype = {entry.selected_colortype} in group {selected_group}")
    except Exception as e:
        print(f"❌ Error updating selected_colortype_in_active_group: {e}")


# ============================================================================
# PROPERTY GROUPS
# ============================================================================

# === Helper invoked by operator.py (safe no-op if nothing to clean) ==========================
def cleanup_all_tasks_colortype_mappings(context):
    """
    Best-effort cleanup to keep task→colortype mappings consistent.
    This is intentionally resilient: if the data structure isn't present or differs
    between Bonsai versions, it silently returns.
    """
    try:
        # Reuse our UPM persistence hooks; if no data, nothing to do
        data = UnifiedColorTypeManager._read_sets_json(context)
        if not isinstance(data, dict):
            return
        # Optionally prune obviously empty groups/entries if they appear as None/[]
        for gkey, gval in list(data.items()):
            if gval is None or gval == {}:
                del data[gkey]
                continue
            if isinstance(gval, dict):
                for pkey, plist in list(gval.items()):
                    if plist in (None, [], {}, "null"):
                        del gval[pkey]
        UnifiedColorTypeManager._write_sets_json(context, data)
    except Exception:
        # Do not raise; operators call this after user actions and must not crash
        pass


# === HUD CALLBACKS (GPU-based) ====================================
def update_gpu_hud_visibility(self, context):
    """
    Smart callback to register/unregister the main GPU HUD handler.
    The handler is active if ANY of the HUD components are enabled.
    """
    try:
        is_any_hud_enabled = (
            getattr(self, "enable_text_hud", False) or
            getattr(self, "enable_timeline_hud", False) or
            getattr(self, "enable_legend_hud", False) or
            getattr(self, "enable_3d_legend_hud", False)
        )

        from bonsai.bim.module.sequence import hud_overlay

        def deferred_update():
            try:
                if is_any_hud_enabled:
                    if not hud_overlay.is_hud_enabled():
                        hud_overlay.register_hud_handler()
                else:
                    if hud_overlay.is_hud_enabled():
                        hud_overlay.unregister_hud_handler()
                
                # Handle 3D Legend HUD toggle specifically
                enable_3d_legend = getattr(self, "enable_3d_legend_hud", False)
                if enable_3d_legend:
                    # Check if 3D Legend HUD exists, if not create it
                    hud_exists = any(obj.get("is_3d_legend_hud", False) for obj in bpy.data.objects)
                    if not hud_exists:
                        try:
                            bpy.ops.bim.setup_3d_legend_hud()
                            print("🟢 3D Legend HUD auto-created on enable")
                        except Exception as e:
                            print(f"⚠️ Failed to auto-create 3D Legend HUD: {e}")
                else:
                    # Clear 3D Legend HUD if it exists
                    hud_exists = any(obj.get("is_3d_legend_hud", False) for obj in bpy.data.objects)
                    if hud_exists:
                        try:
                            bpy.ops.bim.clear_3d_legend_hud()
                            print("🔴 3D Legend HUD auto-cleared on disable")
                        except Exception as e:
                            print(f"⚠️ Failed to auto-clear 3D Legend HUD: {e}")
                
                force_hud_refresh(self, context)
            except Exception as e:
                print(f"Deferred HUD update failed: {e}")
            return None
        if not bpy.app.timers.is_registered(deferred_update):
            bpy.app.timers.register(deferred_update, first_interval=0.05)
    except Exception as e:
        print(f"HUD visibility callback error: {e}")


def update_hud_gpu(self, context):
    """Callback to update GPU HUD"""
    try:
        if getattr(self, "enable_text_hud", False):
            def refresh_hud():
                try:
                    bpy.ops.bim.refresh_schedule_hud()
                except Exception:
                    pass
            bpy.app.timers.register(refresh_hud, first_interval=0.05)
    except Exception:
        pass

# Context-specific visibility update functions
def update_animation_camera_visibility(self, context):
    """Toggles the visibility of animation cameras and their related objects in the viewport."""
    try:
        # Find animation cameras using simple checks
        cameras_to_toggle = []
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA':
                # Check if it's an animation camera
                if (obj.get('is_animation_camera') or 
                    obj.get('camera_context') == 'animation' or 
                    ('4D_Animation_Camera' in obj.name and 'Snapshot' not in obj.name)):
                    cameras_to_toggle.append(obj)

        objects_to_toggle = []
        for cam_obj in cameras_to_toggle:
            objects_to_toggle.append(cam_obj)

            # Find associated path and target objects by name convention
            path_name = f"4D_OrbitPath_for_{cam_obj.name}"
            target_name = f"4D_OrbitTarget_for_{cam_obj.name}"

            path_obj = bpy.data.objects.get(path_name)
            if path_obj:
                objects_to_toggle.append(path_obj)

            target_obj = bpy.data.objects.get(target_name)
            if target_obj:
                objects_to_toggle.append(target_obj)

        for obj in objects_to_toggle:
            obj.hide_viewport = self.hide_all_animation_cameras
            obj.hide_render = self.hide_all_animation_cameras

        # Force redraw
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        print(f"Animation cameras visibility: {'Hidden' if self.hide_all_animation_cameras else 'Shown'} ({len(cameras_to_toggle)} cameras)")

    except Exception as e:
        print(f"Error toggling animation camera visibility: {e}")

def update_snapshot_camera_visibility(self, context):
    """Toggles the visibility of snapshot cameras and their related objects in the viewport."""
    try:
        # Find snapshot cameras using simple checks
        cameras_to_toggle = []
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA':
                # Check if it's a snapshot camera
                if (obj.get('is_snapshot_camera') or 
                    obj.get('camera_context') == 'snapshot' or 
                    'Snapshot_Camera' in obj.name):
                    cameras_to_toggle.append(obj)

        objects_to_toggle = []
        for cam_obj in cameras_to_toggle:
            objects_to_toggle.append(cam_obj)

            # Find associated target objects
            target_name = f"Snapshot_Target"
            target_obj = bpy.data.objects.get(target_name)
            if target_obj:
                objects_to_toggle.append(target_obj)

        for obj in objects_to_toggle:
            obj.hide_viewport = self.hide_all_snapshot_cameras
            obj.hide_render = self.hide_all_snapshot_cameras

        # Force redraw
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        print(f"Snapshot cameras visibility: {'Hidden' if self.hide_all_snapshot_cameras else 'Shown'} ({len(cameras_to_toggle)} cameras)")

    except Exception as e:
        print(f"Error toggling snapshot camera visibility: {e}")

def force_hud_refresh(self, context):
    """Improved callback that forces HUD update with delay"""
    try:
        def delayed_refresh():
            try:
                # Ensure handlers are registered
                import bonsai.bim.module.sequence.hud_overlay as hud_overlay
                
                # CRITICAL: Also update 3D Legend HUD when Legend HUD settings change
                try:
                    print(f"🔍 Checking if 3D Legend HUD should auto-update...")
                    enable_3d_legend = getattr(self, 'enable_3d_legend_hud', False)
                    print(f"  📋 enable_3d_legend_hud: {enable_3d_legend}")
                    
                    if enable_3d_legend:
                        # Check if 3D Legend HUD exists
                        hud_exists = any(obj.get("is_3d_legend_hud", False) for obj in bpy.data.objects)
                        print(f"  📋 3D Legend HUD exists in scene: {hud_exists}")
                        
                        if hud_exists:
                            print("🔄 AUTO-UPDATING 3D Legend HUD due to Legend HUD setting change")
                            bpy.ops.bim.update_3d_legend_hud()
                            print("✅ 3D Legend HUD auto-update completed")
                        else:
                            print("⚠️ 3D Legend HUD enabled but no 3D HUD found in scene")
                    else:
                        print("ℹ️ 3D Legend HUD not enabled, skipping auto-update")
                except Exception as e:
                    print(f"❌ Failed to auto-update 3D Legend HUD during refresh: {e}")
                    import traceback
                    traceback.print_exc()
                hud_overlay.ensure_hud_handlers()
                
                bpy.ops.bim.refresh_schedule_hud()
                
                # Force redraw of 3D viewports
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                        
            except Exception as e:
                print(f"⚠️ Delayed HUD refresh failed: {e}")
            return None  # Do not repeat
        
        # Register timer for delayed update
        bpy.app.timers.register(delayed_refresh, first_interval=0.1)
        
    except Exception as e:
        print(f"❌ Force HUD refresh failed: {e}")

# === END HUD CALLBACKS (GPU) ================================================

# === Camera & Orbit Properties - Definición estática ===

def update_active_animation_camera(self, context):
    """
    Callback para establecer la cámara de animación como activa en la escena.
    """
    camera_obj = self.active_animation_camera
    if not camera_obj:
        return

    def set_camera_deferred():
        try:
            if camera_obj and bpy.context.scene:
                bpy.context.scene.camera = camera_obj
                print(f"✅ Animation camera '{camera_obj.name}' set as active")
                
                # Forzar actualización de la UI
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
        except Exception as e:
            print(f"❌ Error setting animation camera: {e}")
        return None

    # Usar timer para evitar problemas de contexto
    bpy.app.timers.register(set_camera_deferred, first_interval=0.01)

def update_active_snapshot_camera(self, context):
    """
    Callback para establecer la cámara de snapshot como activa en la escena.
    """
    camera_obj = self.active_snapshot_camera
    if not camera_obj:
        return

    def set_camera_deferred():
        try:
            if camera_obj and bpy.context.scene:
                bpy.context.scene.camera = camera_obj
                print(f"✅ Snapshot camera '{camera_obj.name}' set as active")
                
                # Forzar actualización de la UI
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
        except Exception as e:
            print(f"❌ Error setting snapshot camera: {e}")
        return None

    # Usar timer para evitar problemas de contexto
    bpy.app.timers.register(set_camera_deferred, first_interval=0.01)

def update_active_4d_camera(self, context):
    """
    Callback legacy para establecer la cámara de la escena cuando cambia la cámara 4D activa.
    Usa un temporizador para evitar problemas de contexto al modificar `scene.camera`.
    """
    camera_name = self.active_4d_camera.name if self.active_4d_camera else None
    if not camera_name:
        return

    def set_camera_deferred():
        try:
            cam_obj = bpy.data.objects.get(camera_name)
            if cam_obj and bpy.context.scene:
                bpy.context.scene.camera = cam_obj
                # Forzar actualización de la UI para reflejar el cambio
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type in ('PROPERTIES', 'VIEW_3D'):
                            area.tag_redraw()
        except Exception as e:
            print(f"Error in deferred camera set: {e}")
        return None  # El temporizador se ejecuta solo una vez

    bpy.app.timers.register(set_camera_deferred)

def toggle_3d_text_visibility(self, context):
    """Shows/hides the 3D text collection AND the 3D Legend HUD collection."""
    should_hide = not self.show_3d_schedule_texts
    print(f"🔄 toggle_3d_text_visibility called: show_3d_schedule_texts={self.show_3d_schedule_texts}, should_hide={should_hide}")
    
    # Toggle visibility for "Schedule_Display_Texts"
    try:
        collection_texts = bpy.data.collections.get("Schedule_Display_Texts")
        if collection_texts:
            collection_texts.hide_viewport = should_hide
            collection_texts.hide_render = should_hide
            print(f"✅ Schedule_Display_Texts visibility set to hide={should_hide}")
        else:
            print("⚠️ Collection 'Schedule_Display_Texts' not found")
    except Exception as e:
        print(f"❌ Error toggling 3D text visibility: {e}")

    # Toggle visibility for "Schedule_Display_3D_Legend" (controlled by show_3d_schedule_texts)
    try:
        collection_legend = bpy.data.collections.get("Schedule_Display_3D_Legend")
        if collection_legend:
            collection_legend.hide_viewport = should_hide
            collection_legend.hide_render = should_hide
            
            # ADDITIONAL FIX: Also hide/show individual objects to ensure visibility
            objects_processed = 0
            for obj in collection_legend.objects:
                obj.hide_viewport = should_hide
                obj.hide_render = should_hide
                objects_processed += 1
            
            print(f"✅ Schedule_Display_3D_Legend collection & {objects_processed} objects visibility set to hide={should_hide}")
        else:
            print("⚠️ Collection 'Schedule_Display_3D_Legend' not found")
    except Exception as e:
        print(f"❌ Error toggling 3D Legend HUD visibility: {e}")
        
    # SEPARATE control for individual 3D Legend HUD objects (controlled by enable_3d_legend_hud)
    try:
        import bonsai.tool as tool
        anim_props = tool.Sequence.get_animation_props()
        camera_props = anim_props.camera_orbit
        legend_hud_enabled = getattr(camera_props, "enable_3d_legend_hud", False)
        
        # If 3D Legend HUD is disabled individually, hide all its objects regardless of show_3d_schedule_texts
        if not legend_hud_enabled:
            objects_hidden = 0
            for obj in bpy.data.objects:
                if obj.get("is_3d_legend_hud", False):
                    obj.hide_viewport = True
                    obj.hide_render = True
                    objects_hidden += 1
            if objects_hidden > 0:
                print(f"🔴 3D Legend HUD disabled: {objects_hidden} objects hidden individually")
        else:
            # If enabled, follow the main 3D HUD visibility setting
            objects_shown = 0
            for obj in bpy.data.objects:
                if obj.get("is_3d_legend_hud", False):
                    obj.hide_viewport = should_hide  # Follow main 3D HUD setting
                    obj.hide_render = should_hide
                    objects_shown += 1
            if objects_shown > 0:
                print(f"🟢 3D Legend HUD enabled: {objects_shown} objects follow main HUD visibility (hide={should_hide})")
                
    except Exception as e:
        print(f"❌ Error handling individual 3D Legend HUD visibility: {e}")

    # Force refresh of all 3D areas
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass

# --- START OF CORRECTED CODE ---
def get_all_task_columns_enum(self, context):
    """
    Genera una lista EnumProperty con TODAS las columnas filtrables,
    incluyendo el tipo de dato en el identificador para uso interno.
    """
    if not SequenceData.is_loaded:
        SequenceData.load()

    items = []
    # 1. Special columns (manually defined)
    # The format is: "InternalName||data_type", "UI Label", "Description"
    items.append(("Special.OutputsCount||integer", "Outputs 3D", "Number of elements assigned as task outputs."))
    
    items.append(("Special.VarianceStatus||string", "Variance Status", "Task variance status (Delayed, Ahead, On Time)"))
    items.append(("Special.VarianceDays||integer", "Variance (Days)", "Task variance in days"))
    # --- END OF MODIFICATION ---

    # 2. Columnas de IfcTask
    for name_type, label, desc in SequenceData.data.get("task_columns_enum", []):
        try:
            name, data_type = name_type.split('/')
            identifier = f"IfcTask.{name}||{data_type}"
            items.append((identifier, f"Task: {label}", desc))
        except Exception:
            continue

    # 3. Columnas de IfcTaskTime
    for name_type, label, desc in SequenceData.data.get("task_time_columns_enum", []):
        try:
            name, data_type = name_type.split('/')
            # We correct so that dates are treated as 'date'
            final_data_type = 'date' if any(s in label.lower() for s in ['date', 'start', 'finish']) else data_type
            identifier = f"IfcTaskTime.{name}||{final_data_type}"
            items.append((identifier, f"Time: {label}", desc))
        except Exception:
            continue

    return sorted(items, key=lambda x: x[1])
# --- END OF CORRECTED CODE ---


class BIMCameraOrbitProperties(PropertyGroup):
    # =====================
    # Camera settings
    # =====================
    camera_focal_mm: FloatProperty(
        name="Focal (mm)",
        default=35.0,
        min=1.0,
        max=300.0,
        description="Camera focal length in millimeters",
    )
    camera_clip_start: FloatProperty(
        name="Clip Start",
        default=0.1,
        min=0.0001,
        description="Camera near clipping distance",
    )
    camera_clip_end: FloatProperty(
        name="Clip End",
        default=10000.0,
        min=1.0,
        description="Camera far clipping distance",
    )

    # =====================
    # Orbit settings
    # =====================
    orbit_mode: EnumProperty(
        name="Orbit Mode",
        items=[
            ("NONE", "None (Static)", "The camera will not move or be animated."),
            ("CIRCLE_360", "Circle 360°", "The camera performs a full 360-degree circular orbit."),
            ("PINGPONG", "Ping-Pong", "The camera moves back and forth along a 180-degree arc."),
        ],
        default="CIRCLE_360",
    )
    orbit_radius_mode: EnumProperty(
        name="Radius Mode",
        items=[
            ("AUTO", "Auto (from bbox)", "Compute radius from WorkSchedule bbox"),
            ("MANUAL", "Manual", "Use manual radius value"),
        ],
        default="AUTO",
    )
    orbit_radius: FloatProperty(
        name="Radius (m)",
        default=10.0,
        min=0.01,
        description="Manual orbit radius in meters",
    )
    orbit_height: FloatProperty(
        name="Height (Z offset)",
        default=8.0,
        description="Height offset from target center",
    )
    orbit_start_angle_deg: FloatProperty(
        name="Start Angle (deg)",
        default=0.0,
        description="Starting angle in degrees",
    )
    orbit_direction: EnumProperty(
        name="Direction",
        items=[("CCW", "CCW", "Counter-clockwise"), ("CW", "CW", "Clockwise")],
        default="CCW",
    )

    # =====================
    # Look At settings
    # =====================
    look_at_mode: EnumProperty(
        name="Look At",
        items=[
            ("AUTO", "Auto (active WorkSchedule area)", "Use bbox center of active WorkSchedule"),
            ("OBJECT", "Object", "Select object/Empty as target"),
        ],
        default="AUTO",
    )
    look_at_object: PointerProperty(
        name="Target",
        type=bpy.types.Object,
        description="Target object for camera to look at",
    )

    # =====================
    # Path & Interpolation
    # =====================
    orbit_path_shape: EnumProperty(
        name="Path Shape",
        items=[
            ("CIRCLE", "Circle (Generated)", "The add-on creates a perfect circle"),
            ("CUSTOM", "Custom Path", "Use your own curve object as the path"),
        ],
        default="CIRCLE",
        description="Choose between a generated circle or a custom curve for the orbit path",
    )
    custom_orbit_path: PointerProperty(
        name="Custom Path",
        type=bpy.types.Object,
        description="Select a Curve object for the camera to follow",
        poll=lambda self, object: getattr(object, "type", None) == "CURVE",
    )
    interpolation_mode: EnumProperty(
        name="Interpolation",
        items=[
            ("LINEAR", "Linear (Constant Speed)", "Constant, mechanical speed"),
            ("BEZIER", "Bezier (Smooth)", "Smooth ease-in and ease-out for a natural feel"),
        ],
        default="LINEAR",
        description="Controls the smoothness and speed changes of the camera motion",
    )
    bezier_smoothness_factor: FloatProperty(
        name="Smoothness Factor",
        description="Controls the intensity of the ease-in/ease-out. Higher values create a more gradual transition",
        default=0.35,
        min=0.0,
        max=2.0,
        soft_min=0.0,
        soft_max=1.0,
    )

    # =====================
    # Animation settings
    # =====================
    orbit_path_method: EnumProperty(
        name="Path Method",
        items=[
            ("FOLLOW_PATH", "Follow Path (editable)", "Bezier circle + Follow Path"),
            ("KEYFRAMES", "Keyframes (lightweight)", "Animate location directly"),
        ],
        default="FOLLOW_PATH",
    )
    orbit_use_4d_duration: BoolProperty(
        name="Use 4D total frames",
        default=True,
        description="If enabled, orbit spans the whole 4D animation range",
    )
    orbit_duration_frames: FloatProperty(
        name="Orbit Duration (frames)",
        default=250.0,
        min=1.0,
        description="Custom orbit duration in frames",
    )

    # =====================
    # UI toggles
    # =====================
    show_camera_orbit_settings: BoolProperty(
        name="Camera & Orbit",
        default=False,
        description="Toggle Camera & Orbit settings visibility",
    )
    hide_orbit_path: BoolProperty(
        name="Hide Orbit Path",
        default=False,
        description="Hide the visible orbit path (Bezier Circle) in the viewport and render",
    )

    # =====================
    # 3D Texts
    # =====================
    show_3d_schedule_texts: BoolProperty(
        name="Show 3D HUD Render",
        description="Toggle visibility of the 3D objects used as a Heads-Up Display (HUD) for rendering",
        default=False,
        update=lambda self, context: toggle_3d_text_visibility(self, context),
    )

    # =====================
    # HUD (GPU) - Base
    # =====================
    enable_text_hud: BoolProperty(
        name="Enable Viewport HUD",
        description="Enable GPU-based HUD overlay for real-time schedule information in the viewport",
        default=False,
        update=update_gpu_hud_visibility,
    )
    expand_hud_settings: BoolProperty(
        name="Expand HUD Settings",
        description="Show/hide detailed HUD configuration options",
        default=False,
    )
    expand_schedule_hud: BoolProperty(
        name="Expand Schedule HUD",
        default=False,
        description="Show/hide Schedule HUD settings"
    )
    expand_timeline_hud: BoolProperty(
        name="Expand Timeline HUD",
        default=False,
        description="Show/hide Timeline HUD settings"
    )
    expand_legend_hud: BoolProperty(
        name="Expand Legend HUD",
        default=False,
        description="Show/hide Legend HUD settings"
    )
    expand_3d_hud_render: BoolProperty(
        name="Expand 3D HUD Render",
        default=False,
        description="Show/hide 3D HUD Render settings"
    )

    hud_show_date: BoolProperty(name="Date", default=True, update=update_hud_gpu)
    hud_show_week: BoolProperty(name="Week", default=True, update=update_hud_gpu)
    hud_show_day: BoolProperty(name="Day", default=False, update=update_hud_gpu)
    hud_show_progress: BoolProperty(name="Progress", default=False, update=update_hud_gpu)

    hud_position: EnumProperty(
        name="Position",
        items=[
            ("TOP_RIGHT", "Top Right", ""),
            ("TOP_LEFT", "Top Left", ""),
            ("BOTTOM_RIGHT", "Bottom Right", ""),
            ("BOTTOM_LEFT", "Bottom Left", ""),
        ],
        default="BOTTOM_LEFT",
        update=force_hud_refresh,
    )
    hud_scale_factor: FloatProperty(
        name="Scale",
        default=1.0,
        min=0.1,
        max=5.0,
        precision=2,
        update=force_hud_refresh,
    )
    hud_margin_horizontal: FloatProperty(
        name="H-Margin",
        default=0.05,
        min=0.0,
        max=0.3,
        precision=3,
        update=force_hud_refresh,
    )
    hud_margin_vertical: FloatProperty(
        name="V-Margin",
        default=0.05,
        min=0.0,
        max=0.3,
        precision=3,
        update=force_hud_refresh,
    )

    # Base colors (RGBA)
    hud_text_color: FloatVectorProperty(
        name="Text Color",
        subtype="COLOR",
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )
    hud_background_color: FloatVectorProperty(
        name="Background Color",
        subtype="COLOR",
        size=4,
        default=(0.09, 0.114, 0.102, 0.102),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )

    # =====================
    # HUD VISUAL ENHANCEMENTS
    # =====================
    # Spacing & alignment
    hud_text_spacing: FloatProperty(
        name="Line Spacing",
        description="Vertical spacing between HUD text lines",
        default=0.02,
        min=0.0,
        max=0.3,
        precision=3,
        update=force_hud_refresh,
    )
    hud_text_alignment: EnumProperty(
        name="Text Alignment",
        items=[
            ("LEFT", "Left", "Align text to the left"),
            ("CENTER", "Center", "Center align text"),
            ("RIGHT", "Right", "Align text to the right"),
        ],
        default="LEFT",
        update=force_hud_refresh,
    )

    # Panel padding
    hud_padding_horizontal: FloatProperty(
        name="H-Padding",
        description="Horizontal padding inside the HUD panel",
        default=10.0,
        min=0.0,
        max=50.0,
        update=force_hud_refresh,
    )
    hud_padding_vertical: FloatProperty(
        name="V-Padding",
        description="Vertical padding inside the HUD panel",
        default=8.0,
        min=0.0,
        max=50.0,
        update=force_hud_refresh,
    )

    # Borders
    hud_border_radius: FloatProperty(
        name="Border Radius",
        description="Corner rounding of the HUD background",
        default=20.0,
        min=0.0,
        max=50.0,
        update=force_hud_refresh,
    )
    hud_border_width: FloatProperty(
        name="Border Width",
        description="Width of the HUD border",
        default=0.0,
        min=0.0,
        max=5.0,
        update=force_hud_refresh,
    )
    hud_border_color: FloatVectorProperty(
        name="Border Color",
        subtype="COLOR",
        size=4,
        default=(1.0, 1.0, 1.0, 0.5),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )

    # Text shadow
    hud_text_shadow_enabled: BoolProperty(
        name="Text Shadow",
        description="Enable text shadow for better readability",
        default=True,
        update=force_hud_refresh,
    )
    hud_text_shadow_offset_x: FloatProperty(
        name="Shadow Offset X",
        description="Horizontal offset of text shadow",
        default=1.0,
        min=-10.0,
        max=10.0,
        update=force_hud_refresh,
    )
    hud_text_shadow_offset_y: FloatProperty(
        name="Shadow Offset Y",
        description="Vertical offset of text shadow",
        default=-1.0,
        min=-10.0,
        max=10.0,
        update=force_hud_refresh,
    )
    hud_text_shadow_color: FloatVectorProperty(
        name="Shadow Color",
        subtype="COLOR",
        size=4,
        default=(0.0, 0.0, 0.0, 0.8),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )

    # Background drop shadow
    hud_background_shadow_enabled: BoolProperty(
        name="Background Shadow",
        description="Enable drop shadow for the HUD background",
        default=False,
        update=force_hud_refresh,
    )
    hud_background_shadow_offset_x: FloatProperty(
        name="BG Shadow Offset X",
        default=3.0,
        min=-20.0,
        max=20.0,
        update=force_hud_refresh,
    )
    hud_background_shadow_offset_y: FloatProperty(
        name="BG Shadow Offset Y",
        default=-3.0,
        min=-20.0,
        max=20.0,
        update=force_hud_refresh,
    )
    hud_background_shadow_blur: FloatProperty(
        name="BG Shadow Blur",
        description="Blur radius of the background shadow",
        default=5.0,
        min=0.0,
        max=20.0,
        update=force_hud_refresh,
    )
    hud_background_shadow_color: FloatVectorProperty(
        name="BG Shadow Color",
        subtype="COLOR",
        size=4,
        default=(0.0, 0.0, 0.0, 0.6),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )

    # Typography
    hud_font_weight: EnumProperty(
        name="Font Weight",
        items=[
            ("NORMAL", "Normal", "Normal font weight"),
            ("BOLD", "Bold", "Bold font weight"),
        ],
        default="NORMAL",
        update=force_hud_refresh,
    )
    hud_letter_spacing: FloatProperty(
        name="Letter Spacing",
        description="Spacing between characters (tracking)",
        default=0.0,
        min=-2.0,
        max=5.0,
        precision=2,
        update=force_hud_refresh,
    )

    # Background gradient
    hud_background_gradient_enabled: BoolProperty(
        name="Background Gradient",
        description="Enable gradient background instead of solid color",
        default=False,
        update=force_hud_refresh,
    )
    hud_background_gradient_color: FloatVectorProperty(
        name="Gradient Color",
        subtype="COLOR",
        size=4,
        default=(0.1, 0.1, 0.1, 0.9),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )
    hud_gradient_direction: EnumProperty(
        name="Gradient Direction",
        items=[
            ("VERTICAL", "Vertical", "Top to bottom gradient"),
            ("HORIZONTAL", "Horizontal", "Left to right gradient"),
            ("DIAGONAL", "Diagonal", "Diagonal gradient"),
        ],
        default="VERTICAL",
        update=force_hud_refresh,
    )

# --- START OF CORRECTED CODE ---

    # ==========================================
    # === TIMELINE HUD (GPU) - PROPIEDADES NUEVAS ===
    # ==========================================
    enable_timeline_hud: BoolProperty(
        name="Enable Timeline HUD",
        description="Show a graphical timeline at the bottom/top of the viewport",
        default=False,
        update=update_gpu_hud_visibility,
    )
    timeline_hud_position: EnumProperty(
        name="Timeline Position",
        items=[
            ('BOTTOM', "Bottom", "Place the timeline at the bottom"),
            ('TOP', "Top", "Place the timeline at the top"),
        ],
        default='BOTTOM',
        update=force_hud_refresh,
    )
    timeline_hud_margin_vertical: FloatProperty(
        name="V-Margin",
        description="Vertical margin from the viewport edge, as a percentage of viewport height",
        default=0.05,
        min=0.0,
        max=0.45,
        subtype='FACTOR',
        precision=3,
        update=force_hud_refresh,
    )
    timeline_hud_margin_horizontal: FloatProperty(
        name="H-Margin",
        description="Horizontal offset from the center, as a percentage of viewport width. 0 is center.",
        default=0.055,
        min=-0.4,
        max=0.4,
        subtype='FACTOR',
        precision=3,
        update=force_hud_refresh,
    )
    timeline_hud_zoom_level: EnumProperty(
        name="Timeline Zoom",
        items=[
            ('MONTHS', "Months", "Show years and months"),
            ('WEEKS', "Weeks", "Show weeks and days"),
            ('DAYS', "Days", "Show individual days"),
        ],
        default='MONTHS',
        update=force_hud_refresh,
    )
    timeline_hud_height: FloatProperty(
        name="Height (px)",
        description="Height of the timeline bar in pixels",
        default=40.0,
        min=20.0,
        max=100.0,
        update=force_hud_refresh,
    )
    timeline_hud_color_inactive_range: FloatVectorProperty(
        name="Inactive Range Color",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(0.588, 0.953, 0.745, 0.1),
        update=force_hud_refresh,
    )
    timeline_hud_color_active_range: FloatVectorProperty(
        name="Active Range Color",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(0.588, 0.953, 0.745, 0.1),
        update=force_hud_refresh,
    )
    timeline_hud_color_progress: FloatVectorProperty(
        name="Progress Bar Color",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(0.122, 0.663, 0.976, 0.102),  # #1FA9F91A
        update=force_hud_refresh,
    )
    timeline_hud_color_text: FloatVectorProperty(
        name="Timeline Text Color",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(1.0, 1.0, 1.0, 1.0),
        update=force_hud_refresh,
    )
    timeline_hud_border_radius: FloatProperty(
        name="Timeline Border Radius",
        description="Round corner radius for timeline HUD",
        default=10.0, min=0.0, max=50.0,
        update=force_hud_refresh,
    )
    timeline_hud_show_progress_bar: BoolProperty(
        name="Show Progress Bar",
        description="Display progress bar in timeline HUD",
        default=True,
        update=force_hud_refresh,
    )

    # ==================== LEGEND HUD PROPERTIES ====================
    
    enable_legend_hud: BoolProperty(
        name="Enable Legend HUD",
        description="Display legend HUD with active animation colortypes and their colors",
        default=False,
        update=update_gpu_hud_visibility,
    )
    
    legend_hud_position: EnumProperty(
        name="Position",
        description="Screen position of the legend HUD",
        items=[
            ('TOP_LEFT', "Top Left", "Position at the top-left corner"),
            ('TOP_RIGHT', "Top Right", "Position at the top-right corner"),
            ('BOTTOM_LEFT', "Bottom Left", "Position at the bottom-left corner"),
            ('BOTTOM_RIGHT', "Bottom Right", "Position at the bottom-right corner"),
        ],
        default="TOP_LEFT",
        update=force_hud_refresh,
    )
    
    legend_hud_margin_horizontal: FloatProperty(
        name="Horizontal Margin",
        description="Horizontal margin from screen edges",
        default=0.05,
        min=0.0,
        max=0.5,
        step=1,
        precision=3,
        update=force_hud_refresh,
    )
    
    legend_hud_margin_vertical: FloatProperty(
        name="Vertical Margin",
        description="Vertical margin from screen edges",
        default=0.5,
        min=0.0,
        max=0.5,
        step=1,
        precision=3,
        update=force_hud_refresh,
    )
    
    legend_hud_orientation: EnumProperty(
        name="Orientation",
        description="Layout orientation of legend items",
        items=[
            ("VERTICAL", "Vertical", "Stack items vertically"),
            ("HORIZONTAL", "Horizontal", "Arrange items horizontally"),
        ],
        default="VERTICAL",
        update=force_hud_refresh,
    )
    
    legend_hud_scale: FloatProperty(
        name="Scale",
        description="Overall scale factor for legend HUD",
        default=1.0,
        min=0.1,
        max=3.0,
        step=1,
        precision=2,
        update=force_hud_refresh,
    )
    
    legend_hud_background_color: FloatVectorProperty(
        name="Background Color",
        description="Background color of legend HUD",
        default=(0.0, 0.0, 0.0, 0.8),
        min=0.0,
        max=1.0,
        size=4,
        subtype='COLOR',
        update=force_hud_refresh,
    )
    
    legend_hud_border_radius: FloatProperty(
        name="Border Radius",
        description="Corner rounding radius for legend background",
        default=5.0,
        min=0.0,
        max=50.0,
        step=1,
        precision=1,
        update=force_hud_refresh,
    )
    
    legend_hud_padding_horizontal: FloatProperty(
        name="Horizontal Padding",
        description="Horizontal padding inside legend background",
        default=12.0,
        min=0.0,
        max=50.0,
        step=1,
        precision=1,
        update=force_hud_refresh,
    )
    
    legend_hud_padding_vertical: FloatProperty(
        name="Vertical Padding",
        description="Vertical padding inside legend background",
        default=8.0,
        min=0.0,
        max=50.0,
        step=1,
        precision=1,
        update=force_hud_refresh,
    )
    
    legend_hud_item_spacing: FloatProperty(
        name="Item Spacing",
        description="Spacing between legend items",
        default=8.0,
        min=0.0,
        max=30.0,
        step=1,
        precision=1,
        update=force_hud_refresh,
    )
    
    legend_hud_text_color: FloatVectorProperty(
        name="Text Color",
        description="Color of legend text",
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        size=4,
        subtype='COLOR',
        update=force_hud_refresh,
    )
    
    legend_hud_show_title: BoolProperty(
        name="Show Title",
        description="Display title at the top of legend",
        default=True,
        update=force_hud_refresh,
    )
    
    legend_hud_title_text: StringProperty(
        name="Title Text",
        description="Text to display as legend title",
        default="Legend",
        update=force_hud_refresh,
    )
    
    legend_hud_title_color: FloatVectorProperty(
        name="Title Color",
        description="Color of legend title text",
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        size=4,
        subtype='COLOR',
        update=force_hud_refresh,
    )
    
    legend_hud_color_indicator_size: FloatProperty(
        name="Color Indicator Size",
        description="Size of color indicator squares",
        default=12.0,
        min=4.0,
        max=32.0,
        step=1,
        precision=1,
        update=force_hud_refresh,
    )
    
    legend_hud_text_shadow_enabled: BoolProperty(
        name="Text Shadow",
        description="Enable text shadow for better visibility",
        default=True,
        update=force_hud_refresh,
    )
    
    legend_hud_text_shadow_color: FloatVectorProperty(
        name="Shadow Color",
        description="Color of text shadow",
        default=(0.0, 0.0, 0.0, 0.8),
        min=0.0,
        max=1.0,
        size=4,
        subtype='COLOR',
        update=force_hud_refresh,
    )
    
    legend_hud_text_shadow_offset_x: FloatProperty(
        name="Shadow Offset X",
        description="Horizontal offset of text shadow",
        default=1.0,
        min=-10.0,
        max=10.0,
        step=1,
        precision=1,
        update=force_hud_refresh,
    )
    
    legend_hud_text_shadow_offset_y: FloatProperty(
        name="Shadow Offset Y",
        description="Vertical offset of text shadow",
        default=-1.0,
        min=-10.0,
        max=10.0,
        step=1,
        precision=1,
        update=force_hud_refresh,
    )
    
    legend_hud_auto_scale: BoolProperty(
        name="Auto Scale",
        description="Automatically scale legend to fit content",
        default=True,
        update=force_hud_refresh,
    )
    
    legend_hud_max_width: FloatProperty(
        name="Max Width",
        description="Maximum width as proportion of viewport width",
        default=0.3,
        min=0.1,
        max=0.8,
        step=1,
        precision=2,
        update=force_hud_refresh,
    )
    
    # ==================== LEGEND HUD COLOR COLUMNS ====================
    
    legend_hud_show_start_column: BoolProperty(
        name="Show Start Colors",
        description="Display start state colors column",
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_show_active_column: BoolProperty(
        name="Show Active Colors",
        description="Display active/in-progress state colors column",
        default=True,
        update=force_hud_refresh,
    )
    
    legend_hud_show_end_column: BoolProperty(
        name="Show End Colors",
        description="Display end/finished state colors column",
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_show_start_title: BoolProperty(
        name="Show 'Start' Title",
        description="Display 'Start' column title",
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_show_active_title: BoolProperty(
        name="Show 'Active' Title", 
        description="Display 'Active' column title",
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_show_end_title: BoolProperty(
        name="Show 'End' Title",
        description="Display 'End' column title", 
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_column_spacing: FloatProperty(
        name="Column Spacing",
        description="Spacing between color columns",
        default=16.0,
        min=4.0,
        max=50.0,
        step=1,
        precision=1,
        update=force_hud_refresh,
    )
    
    legend_hud_title_font_size: FloatProperty(
        name="Title Font Size",
        description="Font size for the legend title",
        default=16.0,
        min=8.0,
        max=48.0,
        step=1,
        precision=1,
        update=force_hud_refresh,
    )
    
    # ==================== colortype VISIBILITY SELECTION ====================
    
    legend_hud_visible_colortypes: StringProperty(
        name="Hidden colortypes",
        description="Comma-separated list of colortype names to hide in legend (all colortypes visible by default)",
        default="",
        update=force_hud_refresh,
    )
    
    # colortype list scroll properties
    legend_hud_colortype_scroll_offset: IntProperty(
        name="colortype List Scroll Offset",
        description="Current scroll position in the colortype list",
        default=0,
        min=0,
    )
    
    # ==================== 3D LEGEND HUD PROPERTIES ====================
    
    enable_3d_legend_hud: BoolProperty(
        name="Enable 3D Legend HUD",
        description="Display 3D Legend HUD with current active ColorTypes as 3D objects",
        default=False,
        update=update_gpu_hud_visibility,
    )
    
    expand_3d_legend_hud: BoolProperty(
        name="Expand 3D Legend HUD Settings",
        description="Show/hide 3D Legend HUD settings",
        default=False,
    )
    
    # Position and Layout
    legend_3d_hud_distance: FloatProperty(
        name="HUD Distance",
        description="Distance from camera in camera space",
        default=2.2,
        min=0.5,
        max=10.0,
        step=1,
        precision=2,
    )
    
    legend_3d_hud_pos_x: FloatProperty(
        name="HUD Position X",
        description="Horizontal position in camera space",
        default=-3.6,
        min=-10.0,
        max=10.0,
        step=1,
        precision=2,
    )
    
    legend_3d_hud_pos_y: FloatProperty(
        name="HUD Position Y", 
        description="Vertical position in camera space",
        default=1.4,
        min=-10.0,
        max=10.0,
        step=1,
        precision=2,
    )
    
    legend_3d_hud_scale: FloatProperty(
        name="HUD Scale",
        description="Overall scale of the 3D Legend HUD",
        default=1.0,
        min=0.1,
        max=5.0,
        step=1,
        precision=2,
    )
    
    # Panel Settings
    legend_3d_panel_width: FloatProperty(
        name="Panel Width",
        description="Width of the legend panel",
        default=2.2,
        min=0.5,
        max=10.0,
        step=1,
        precision=2,
    )
    
    legend_3d_panel_radius: FloatProperty(
        name="Panel Corner Radius",
        description="Corner radius for rounded panel",
        default=0.12,
        min=0.0,
        max=1.0,
        step=1,
        precision=3,
    )
    
    legend_3d_panel_alpha: FloatProperty(
        name="Panel Alpha",
        description="Panel background transparency",
        default=0.85,
        min=0.0,
        max=1.0,
        step=1,
        precision=2,
    )
    
    # Font Settings
    legend_3d_font_size_title: FloatProperty(
        name="Title Font Size",
        description="Font size for legend title",
        default=0.18,
        min=0.05,
        max=1.0,
        step=1,
        precision=3,
    )
    
    legend_3d_font_size_item: FloatProperty(
        name="Item Font Size",
        description="Font size for legend items",
        default=0.15,
        min=0.05,
        max=1.0,
        step=1,
        precision=3,
    )
    
    # Layout Settings
    legend_3d_padding_x: FloatProperty(
        name="Padding X",
        description="Horizontal padding inside panel",
        default=0.18,
        min=0.0,
        max=1.0,
        step=1,
        precision=3,
    )
    
    legend_3d_padding_top: FloatProperty(
        name="Padding Top",
        description="Top padding inside panel",
        default=0.20,
        min=0.0,
        max=1.0,
        step=1,
        precision=3,
    )
    
    legend_3d_padding_bottom: FloatProperty(
        name="Padding Bottom", 
        description="Bottom padding inside panel",
        default=0.20,
        min=0.0,
        max=1.0,
        step=1,
        precision=3,
    )
    
    legend_3d_row_height: FloatProperty(
        name="Row Height",
        description="Height of each legend item row",
        default=0.20,
        min=0.05,
        max=1.0,
        step=1,
        precision=3,
    )
    
    legend_3d_dot_diameter: FloatProperty(
        name="Color Dot Diameter",
        description="Diameter of color indicator dots",
        default=0.10,
        min=0.02,
        max=0.5,
        step=1,
        precision=3,
    )
    
    legend_3d_dot_text_gap: FloatProperty(
        name="Dot to Text Gap",
        description="Gap between color dot and text",
        default=0.12,
        min=0.01,
        max=0.5,
        step=1,
        precision=3,
    )
    
    legend_3d_title_text: StringProperty(
        name="Legend Title",
        description="Text to display as legend title",
        default="Legend",
    )
    
    timeline_hud_width: FloatProperty(
        name="Timeline Width",
        description="Width of the timeline HUD as percentage of viewport width",
        default=0.8, min=0.1, max=1.0, subtype='PERCENTAGE',
        update=force_hud_refresh,
    )
    timeline_hud_color_indicator: FloatVectorProperty(
        name="Current Date Indicator Color",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(1.0, 0.906, 0.204, 1.0),  # #FFE734FF
        update=force_hud_refresh,
    )
    
    # LOCK/UNLOCK controls for manual positioning
    text_hud_locked: BoolProperty(
        name="Lock Text HUD",
        description="When locked, text HUD position is automatic. When unlocked, allows manual positioning",
        default=True,
        update=force_hud_refresh,
    )
    # Manual positioning coordinates (stored when unlocked)
    text_hud_manual_x: FloatProperty(
        name="Manual X Position",
        description="Manual X position for text HUD when unlocked",
        default=0.0,
        update=force_hud_refresh,
    )
    text_hud_manual_y: FloatProperty(
        name="Manual Y Position", 
        description="Manual Y position for text HUD when unlocked",
        default=0.0,
        update=force_hud_refresh,
    )
    timeline_hud_manual_x: FloatProperty(
        name="Manual X Position",
        description="Manual X position for timeline HUD when unlocked", 
        default=0.0,
        update=force_hud_refresh,
    )
    timeline_hud_manual_y: FloatProperty(
        name="Manual Y Position",
        description="Manual Y position for timeline HUD when unlocked",
        default=0.0,
        update=force_hud_refresh,
    )

    # =====================
    # 4D Camera Management - Animation Context
    # =====================
    active_animation_camera: PointerProperty(
        name="Active Animation Camera",
        type=bpy.types.Object,
        description="Selecciona una cámara 4D existente para los Ajustes de Animación",
        poll=lambda self, obj: tool.Sequence.is_bonsai_animation_camera(obj), # <-- LÓGICA DE FILTRADO
        update=update_active_animation_camera,
    )
    hide_all_animation_cameras: BoolProperty(
        name="Hide All Animation Cameras",
        description="Alterna la visibilidad de todas las cámaras de animación 4D en la vista",
        default=False,
        update=update_animation_camera_visibility,
    )
    
    # =====================
    # 4D Camera Management - Snapshot Context  
    # =====================
    active_snapshot_camera: PointerProperty(
        name="Active Snapshot Camera",
        type=bpy.types.Object,
        description="Selecciona una cámara 4D existente para los Ajustes de Snapshot",
        poll=lambda self, obj: tool.Sequence.is_bonsai_snapshot_camera(obj), # <-- LÓGICA DE FILTRADO
        update=update_active_snapshot_camera,
    )
    hide_all_snapshot_cameras: BoolProperty(
        name="Hide All Snapshot Cameras",
        description="Alterna la visibilidad de todas las cámaras de snapshot 4D en la vista",
        default=False,
        update=update_snapshot_camera_visibility,
    )
    
    # Legacy property for backward compatibility - will be deprecated
    active_4d_camera: PointerProperty(
        name="Active 4D Camera (Legacy)",
        type=bpy.types.Object,
        description="Legacy camera selector - use context-specific selectors instead",
        poll=lambda self, obj: (obj and obj.type == 'CAMERA' and 
                               (obj.get('is_4d_camera') or 
                                '4D_Animation_Camera' in obj.name or 
                                'Snapshot_Camera' in obj.name)),
        update=update_active_4d_camera,
    )
    # --- NEW: Custom Rotation for 3D HUD Render Settings ---
    use_custom_rotation_target: BoolProperty(
        name="Use Custom Rotation Target",
        description="Override the default camera tracking and constrain the rotation of the 3D text group to a specific object",
        default=False,
        update=lambda self, context: update_schedule_display_parent_constraint(context)
    )
    schedule_display_rotation_target: PointerProperty(
        name="Rotation Target",
        type=bpy.types.Object,
        description="Object to which the 3D text group's rotation will be constrained",
        poll=lambda self, object: object.type in {'CAMERA', 'EMPTY'},
        update=lambda self, context: update_schedule_display_parent_constraint(context)
    )
    use_custom_location_target: BoolProperty(
        name="Use Custom Location Target",
        description="Override the default camera tracking and constrain the location of the 3D text group to a specific object",
        default=False,
        update=lambda self, context: update_schedule_display_parent_constraint(context)
    )
    schedule_display_location_target: PointerProperty(
        name="Location Target",
        type=bpy.types.Object,
        description="Object to which the 3D text group's location will be constrained",
        poll=lambda self, object: object.type in {'CAMERA', 'EMPTY'},
        update=lambda self, context: update_schedule_display_parent_constraint(context)
    )
    # --- NEW: Custom Rotation for 3D Legend HUD ---
    legend_3d_hud_use_custom_rotation_target: BoolProperty(
        name="Use Custom Rotation Target",
        description="Override the default camera tracking and constrain the rotation of the 3D Legend HUD to a specific object",
        default=False,
        update=lambda self, context: update_legend_3d_hud_constraint(context)
    )
    legend_3d_hud_rotation_target: PointerProperty(
        name="Rotation Target",
        type=bpy.types.Object,
        description="Object to which the 3D Legend HUD's rotation will be constrained",
        poll=lambda self, object: object.type in {'CAMERA', 'EMPTY'},
        update=lambda self, context: update_legend_3d_hud_constraint(context)
    )
    legend_3d_hud_use_custom_location_target: BoolProperty(
        name="Use Custom Location Target",
        description="Override the default camera tracking and constrain the location of the 3D Legend HUD to a specific object",
        default=False,
        update=lambda self, context: update_legend_3d_hud_constraint(context)
    )
    legend_3d_hud_location_target: PointerProperty(
        name="Location Target",
        type=bpy.types.Object,
        description="Object to which the 3D Legend HUD's location will be constrained",
        poll=lambda self, object: object.type in {'CAMERA', 'EMPTY'},
        update=lambda self, context: update_legend_3d_hud_constraint(context)
    )


class TaskFilterRule(PropertyGroup):
    """Define una regla de filtrado con soporte para múltiples tipos de datos."""
    is_active: BoolProperty(name="Active", default=True, description="Enable or disable this filter rule")

    column: EnumProperty(
        name="Column",
        description="The column to apply the filter on",
        items=get_all_task_columns_enum,
        update=update_filter_column
    )
    
    operator: EnumProperty(
        name="Operator",
        description="The comparison operation to perform",
        items=get_operator_items
    )
    
    # Propiedad interna para almacenar el tipo de dato actual
    data_type: StringProperty(name="Data Type", default='string')

    # Campos de valor específicos para cada tipo de dato
    value_string: StringProperty(name="Value", description="Value for text or date filters")
    value_integer: IntProperty(name="Value", description="Value for integer number filters")
    value_float: FloatProperty(name="Value", description="Value for decimal number filters")
    value_boolean: BoolProperty(name="Value", description="Value for true/false filters")
# --- END OF CORRECTED CODE ---


class BIMTaskFilterProperties(PropertyGroup):
    """Stores the complete configuration of the filter system."""
    rules: CollectionProperty(
        name="Filter Rules",
        type=TaskFilterRule,
    )
    active_rule_index: IntProperty(
        name="Active Filter Rule Index",
    )
    logic: EnumProperty(
        name="Filter Logic",
        description="How multiple filter rules are combined",
        items=[
            ('AND', "Match All (AND)", "Show tasks that meet ALL active rules"),
            ('OR', "Match Any (OR)", "Show tasks that meet AT LEAST ONE active rule"),
        ],
        default='AND',
    )
    show_filters: BoolProperty(
        name="Show Filters",
        description="Shows or hides the filter configuration panel",
        default=False,
    )
    # --- ADDED PROPERTY ---
    show_saved_filters: BoolProperty(
        name="Show Saved Filters",
        description="Shows or hides the saved filters panel",
        default=False,
    )

    def to_json_data(self):
        """Serializes the filter state to a Python dictionary."""
        rules_data = []
        for rule in self.rules:
            rules_data.append({
                "is_active": rule.is_active,
                "column": rule.column,
                "operator": rule.operator,
                "data_type": rule.data_type,
                "value_string": rule.value_string,
                "value_integer": rule.value_integer,
                "value_float": rule.value_float,
                "value_boolean": rule.value_boolean,
            })
        return {
            "rules": rules_data,
            "logic": self.logic,
            "show_filters": self.show_filters,
            "show_saved_filters": self.show_saved_filters,
            "active_rule_index": self.active_rule_index,
        }

    def from_json_data(self, data):
        """Restores the filter state from a Python dictionary."""
        self.rules.clear()
        self.logic = data.get("logic", "AND")
        self.show_filters = data.get("show_filters", False)
        self.show_saved_filters = data.get("show_saved_filters", False)
        for rule_data in data.get("rules", []):
            new_rule = self.rules.add()
            for key, value in rule_data.items():
                if hasattr(new_rule, key):
                    setattr(new_rule, key, value)
        self.active_rule_index = data.get("active_rule_index", 0)


class SavedFilterSet(PropertyGroup):
    """Almacena un conjunto de reglas de filtro con un nombre."""
    name: StringProperty(name="Set Name")
    rules: CollectionProperty(type=TaskFilterRule)
# === FIN CÓDIGO PARA GUARDAR/CARGAR FILTROS ===

class TaskcolortypeGroupChoice(PropertyGroup):
    """colortype group mapping for each task"""
    group_name: StringProperty(name="Group Name")
    enabled: BoolProperty(name="Enabled")
    selected_colortype: StringProperty(name="Selected colortype")
    if TYPE_CHECKING:
        group_name: str
        enabled: bool
        selected_colortype: str


class Task(PropertyGroup):
    """Task properties with improved colortype support"""
    # colortype mapping by group
    colortype_group_choices: CollectionProperty(name="colortype Group Choices", type=TaskcolortypeGroupChoice)
    use_active_colortype_group: BoolProperty(
        name="Use Active Group", 
        default=False, 
        update=update_use_active_colortype_group
    )
    selected_colortype_in_active_group: EnumProperty(
        name="colortype in Active Group",
        description="Select colortype within the active custom group (excludes DEFAULT)",
        items=get_custom_group_colortype_items, # ←  CAMBIO CRÍTICO AQUÍ 
        update=update_selected_colortype_in_active_group
    )
    
    # Basic task properties
    animation_color_schemes: EnumProperty(name="Animation Color Scheme", items=get_animation_color_schemes_items)
    name: StringProperty(name="Name", update=updateTaskName)
    identification: StringProperty(name="Identification", update=updateTaskIdentification)
    ifc_definition_id: IntProperty(name="IFC Definition ID")
    has_children: BoolProperty(name="Has Children")
    is_selected: BoolProperty(
        name="Is Selected",
        update=update_task_checkbox_selection
    )
    is_expanded: BoolProperty(name="Is Expanded")
    has_bar_visual: BoolProperty(name="Show Task Bar Animation", default=False, update=update_task_bar_list)
    level_index: IntProperty(name="Level Index")
    
    # Times
    duration: StringProperty(name="Duration", update=updateTaskDuration)
    start: StringProperty(name="Start", update=updateTaskTimeStart)
    finish: StringProperty(name="Finish", update=updateTaskTimeFinish)
    actual_start: StringProperty(name="Actual Start", update=updateTaskTimeActualStart)
    actual_finish: StringProperty(name="Actual Finish", update=updateTaskTimeActualFinish)
    early_start: StringProperty(name="Early Start", update=updateTaskTimeEarlyStart)
    early_finish: StringProperty(name="Early Finish", update=updateTaskTimeEarlyFinish)
    late_start: StringProperty(name="Late Start", update=updateTaskTimeLateStart)
    late_finish: StringProperty(name="Late Finish", update=updateTaskTimeLateFinish)
    calendar: StringProperty(name="Calendar")
    derived_start: StringProperty(name="Derived Start")
    derived_finish: StringProperty(name="Derived Finish")
    derived_actual_start: StringProperty(name="Derived Actual Start")
    derived_actual_finish: StringProperty(name="Derived Actual Finish")
    derived_early_start: StringProperty(name="Derived Early Start")
    derived_early_finish: StringProperty(name="Derived Early Finish")
    derived_late_start: StringProperty(name="Derived Late Start")
    derived_late_finish: StringProperty(name="Derived Late Finish")
    derived_duration: StringProperty(name="Derived Duration")
    derived_calendar: StringProperty(name="Derived Calendar")
    
    # Relationships
    is_predecessor: BoolProperty(name="Is Predecessor")
    is_successor: BoolProperty(name="Is Successor")
    # --- START: Variance Analysis Properties ---
    variance_status: StringProperty(
        name="Variance Status",
        description="Shows if the task is Ahead, Delayed, or On Time based on the last variance calculation"
    )
    variance_days: IntProperty(
        name="Variance (Days)",
        description="The difference in days between the two compared date sets (positive for delayed, negative for ahead)"
    )
    outputs_count: IntProperty(name="Outputs Count", description="Number of elements assigned as task outputs")
    
    # Variance color mode checkbox
    is_variance_color_selected: BoolProperty(
        name="Variance Color Mode",
        description="Select this task for variance color mode visualization",
        default=False,
        update=lambda self, context: update_variance_color_mode(self, context)
    )
    
    
    if TYPE_CHECKING:
        animation_color_schemes: str
        name: str
        identification: str
        ifc_definition_id: int
        has_children: bool
        is_selected: bool
        is_expanded: bool
        has_bar_visual: bool
        level_index: int
        duration: str
        start: str
        finish: str
        calendar: str
        derived_start: str
        derived_finish: str
        derived_duration: str
        derived_calendar: str
        actual_start: str
        actual_finish: str
        derived_actual_start: str
        derived_actual_finish: str
        early_start: str
        early_finish: str
        derived_early_start: str
        derived_early_finish: str
        late_start: str
        late_finish: str
        derived_late_start: str
        derived_late_finish: str
        is_predecessor: bool
        is_successor: bool
        outputs_count: int
        variance_status: str
        variance_days: int


def get_date_source_items(self, context):
    """Helper for EnumProperty items to select date sources."""
    return [
        ('SCHEDULE', "Schedule", "Use Schedule dates"),
        ('ACTUAL', "Actual", "Use Actual dates"),
        ('EARLY', "Early", "Use Early dates"),
        ('LATE', "Late", "Use Late dates"),
    ]


class WorkPlan(PropertyGroup):
    name: StringProperty(name="Name")
    ifc_definition_id: IntProperty(name="IFC Definition ID")
    if TYPE_CHECKING:
        name: str
        ifc_definition_id: int


class TaskResource(PropertyGroup):
    name: StringProperty(name="Name", update=updateAssignedResourceName)
    ifc_definition_id: IntProperty(name="IFC Definition ID")
    schedule_usage: FloatProperty(name="Schedule Usage", update=updateAssignedResourceUsage)
    if TYPE_CHECKING:
        name: str
        ifc_definition_id: int
        schedule_usage: float


class TaskProduct(PropertyGroup):
    name: StringProperty(name="Name")
    ifc_definition_id: IntProperty(name="IFC Definition ID")
    if TYPE_CHECKING:
        name: str
        ifc_definition_id: int


WorkPlanEditingType = Literal["-", "ATTRIBUTES", "SCHEDULES", "WORK_SCHEDULE", "TASKS", "WORKTIMES"]


class BIMWorkPlanProperties(PropertyGroup):
    work_plan_attributes: CollectionProperty(name="Work Plan Attributes", type=Attribute)
    editing_type: EnumProperty(
        items=[(i, i, "") for i in get_args(WorkPlanEditingType)],
    )
    work_plans: CollectionProperty(name="Work Plans", type=WorkPlan)
    active_work_plan_index: IntProperty(name="Active Work Plan Index")
    active_work_plan_id: IntProperty(name="Active Work Plan Id")
    work_schedules: EnumProperty(items=getWorkSchedules, name="Work Schedules")
    if TYPE_CHECKING:
        work_plan_attributes: bpy.types.bpy_prop_collection_idprop[Attribute]
        editing_type: WorkPlanEditingType
        work_plans: bpy.types.bpy_prop_collection_idprop[WorkPlan]
        active_work_plan_index: int
        active_work_plan_id: int
        work_schedules: str


class IFCStatus(PropertyGroup):
    name: StringProperty(name="Name")
    is_visible: BoolProperty(
        name="Is Visible", default=True, update=lambda x, y: (None, bpy.ops.bim.activate_status_filters())[0]
    )
    if TYPE_CHECKING:
        name: str
        is_visible: bool


class BIMStatusProperties(PropertyGroup):
    is_enabled: BoolProperty(name="Is Enabled")
    statuses: CollectionProperty(name="Statuses", type=IFCStatus)
    if TYPE_CHECKING:
        is_enabled: bool
        statuses: bpy.types.bpy_prop_collection_idprop[IFCStatus]


def update_date_source(self, context):
    """
    Callback when the date source changes. It updates the visualization dates,
    re-applies any active Lookahead filter, and syncs the timeline by date if requested.
    """
    import bpy # Es una buena práctica importar bpy dentro de las funciones de callback

    # --- NUEVO: Guardamos el estado ANTES de cualquier cambio ---
    previous_start = self.visualisation_start
    previous_finish = self.visualisation_finish
    # -----------------------------------------------------------
    
    props = tool.Sequence.get_work_schedule_props()
    current_lookahead = getattr(props, 'last_lookahead_window', '')

    # --- Tu lógica original para Lookahead ---
    if not current_lookahead:
        try:
            def guess_and_update_dates():
                work_schedule = tool.Sequence.get_active_work_schedule()
                if work_schedule:
                    start_date, finish_date = tool.Sequence.guess_date_range(work_schedule)
                    tool.Sequence.update_visualisation_date(start_date, finish_date)
                    print(f"📅 Updated visualization range (no Lookahead): {start_date} to {finish_date}")
                
                # --- NUEVO: Disparamos la sincronización DESPUÉS de actualizar las fechas ---
                if previous_start and previous_finish and "-" not in (previous_start, previous_finish):
                    bpy.ops.bim.sync_animation_by_date(
                        'INVOKE_DEFAULT',
                        previous_start_date=previous_start,
                        previous_finish_date=previous_finish
                    )
                return None
            bpy.app.timers.register(guess_and_update_dates)
        except Exception as e:
            print(f"Bonsai WARNING: Failed to schedule date range update: {e}")

    if current_lookahead:
        def reapply_filter():
            try:
                bpy.ops.bim.apply_lookahead_filter(time_window=current_lookahead)
                # --- NUEVO: Disparamos la sincronización DESPUÉS de actualizar las fechas ---
                if previous_start and previous_finish and "-" not in (previous_start, previous_finish):
                    bpy.ops.bim.sync_animation_by_date(
                        'INVOKE_DEFAULT',
                        previous_start_date=previous_start,
                        previous_finish_date=previous_finish
                    )
            except Exception as e:
                print(f"❌ Error re-applying lookahead filter: {e}")
            return None
        bpy.app.timers.register(reapply_filter, first_interval=0.05)
    
    # --- Tu lógica original para re-bake ---
    anim_props = tool.Sequence.get_animation_props()
    if getattr(anim_props, 'auto_update_on_date_source_change', False):
<<<<<<< HEAD

        if getattr(anim_props, 'is_animation_created', False):

            def re_bake_animation():
                try:
                    # MODIFICADO: Ahora llamamos a CreateAnimation directamente
                    # para poder pasarle el nuevo parámetro que evita el reinicio del fotograma.
                    bpy.ops.bim.create_animation(preserve_current_frame=True)
                except Exception as e:
                    print(f"❌ Error re-baking animation automatically: {e}")
                return None
        

=======
        def re_bake_animation():
            try:
                # MODIFICADO: Ahora llamamos a CreateAnimation directamente
                # para poder pasarle el nuevo parámetro que evita el reinicio del fotograma.
                bpy.ops.bim.create_animation(preserve_current_frame=True)
            except Exception as e:
                print(f"❌ Error re-baking animation automatically: {e}")
            return None
        bpy.app.timers.register(re_bake_animation, first_interval=0.2)
   


def update_date_source(self, context):
    """
    Callback when the date source changes. It updates the visualization dates,
    re-applies any active Lookahead filter, and syncs the timeline by date if requested.
    """
    import bpy # Es una buena práctica importar bpy dentro de las funciones de callback

    # --- NUEVO: Guardamos el estado ANTES de cualquier cambio ---
    previous_start = self.visualisation_start
    previous_finish = self.visualisation_finish
    # -----------------------------------------------------------
    
    props = tool.Sequence.get_work_schedule_props()
    current_lookahead = getattr(props, 'last_lookahead_window', '')

    # --- Tu lógica original para Lookahead ---
    if not current_lookahead:
        try:
            def guess_and_update_dates():
                work_schedule = tool.Sequence.get_active_work_schedule()
                if work_schedule:
                    start_date, finish_date = tool.Sequence.guess_date_range(work_schedule)
                    tool.Sequence.update_visualisation_date(start_date, finish_date)
                    print(f"📅 Updated visualization range (no Lookahead): {start_date} to {finish_date}")
                
                # --- NUEVO: Disparamos la sincronización DESPUÉS de actualizar las fechas ---
                if previous_start and previous_finish and "-" not in (previous_start, previous_finish):
                    bpy.ops.bim.sync_animation_by_date(
                        'INVOKE_DEFAULT',
                        previous_start_date=previous_start,
                        previous_finish_date=previous_finish
                    )
                return None
            bpy.app.timers.register(guess_and_update_dates)
        except Exception as e:
            print(f"Bonsai WARNING: Failed to schedule date range update: {e}")

    if current_lookahead:
        def reapply_filter():
            try:
                bpy.ops.bim.apply_lookahead_filter(time_window=current_lookahead)
                # --- NUEVO: Disparamos la sincronización DESPUÉS de actualizar las fechas ---
                if previous_start and previous_finish and "-" not in (previous_start, previous_finish):
                    bpy.ops.bim.sync_animation_by_date(
                        'INVOKE_DEFAULT',
                        previous_start_date=previous_start,
                        previous_finish_date=previous_finish
                    )
            except Exception as e:
                print(f"❌ Error re-applying lookahead filter: {e}")
            return None
        bpy.app.timers.register(reapply_filter, first_interval=0.05)
    
    # --- Tu lógica original para re-bake ---
    anim_props = tool.Sequence.get_animation_props()
    if getattr(anim_props, 'auto_update_on_date_source_change', False):
        def re_bake_animation():
            try:
                # MODIFICADO: Ahora llamamos a CreateAnimation directamente
                # para poder pasarle el nuevo parámetro que evita el reinicio del fotograma.
                bpy.ops.bim.create_animation(preserve_current_frame=True)
            except Exception as e:
                print(f"❌ Error re-baking animation automatically: {e}")
            return None
>>>>>>> 315c24fd3d3e09e4de3cfbcb36c9d95a73ed715f
        bpy.app.timers.register(re_bake_animation, first_interval=0.2)


    # Variance will only update when manually changing variance_source_a/variance_source_b
    # Not automatically when changing main date source

class BIMWorkScheduleProperties(PropertyGroup):
    work_schedule_predefined_types: EnumProperty(
        items=get_schedule_predefined_types, name="Predefined Type", default=None, update=update_work_schedule_predefined_type
    )
    object_type: StringProperty(name="Object Type")
    durations_attributes: CollectionProperty(name="Durations Attributes", type=ISODuration)
    work_calendars: EnumProperty(items=getWorkCalendars, name="Work Calendars")
    work_schedule_attributes: CollectionProperty(name="Work Schedule Attributes", type=Attribute)
    editing_type: StringProperty(name="Editing Type")
    editing_task_type: StringProperty(name="Editing Task Type")
    active_work_schedule_index: IntProperty(name="Active Work Schedules Index")
    active_work_schedule_id: IntProperty(name="Active Work Schedules Id", update=update_active_work_schedule_id)
    active_task_index: IntProperty(name="Active Task Index", update=update_active_task_index)
    active_task_id: IntProperty(name="Active Task Id")
    highlighted_task_id: IntProperty(name="Highlited Task Id")
    task_attributes: CollectionProperty(name="Task Attributes", type=Attribute)
    should_show_visualisation_ui: BoolProperty(name="Should Show Visualisation UI", default=True, update=switch_options)
    should_show_task_bar_selection: BoolProperty(name="Add to task bar", default=False)
    should_show_snapshot_ui: BoolProperty(name="Should Show Snapshot UI", default=False, update=switch_options2)
    should_show_column_ui: BoolProperty(name="Should Show Column UI", default=False)
    columns: CollectionProperty(name="Columns", type=Attribute)
    active_column_index: IntProperty(name="Active Column Index")
    sort_column: StringProperty(name="Sort Column")
    is_sort_reversed: BoolProperty(name="Is Sort Reversed", update=update_sort_reversed)
    column_types: EnumProperty(
        items=[
            ("IfcTask", "IfcTask", ""),
            ("IfcTaskTime", "IfcTaskTime", ""),
            ("Special", "Special", ""),
        ],
        name="Column Types",
    )
    task_columns: EnumProperty(items=getTaskColumns, name="Task Columns")
    task_time_columns: EnumProperty(items=getTaskTimeColumns, name="Task Time Columns")
    other_columns: EnumProperty(
        items=[
            ("Controls.Calendar", "Calendar", ""),
        ],
        name="Special Columns",
    )
    active_task_time_id: IntProperty(name="Active Task Time Id")
    task_time_attributes: CollectionProperty(name="Task Time Attributes", type=Attribute)
    contracted_tasks: StringProperty(name="Contracted Task Items", default="[]")
    task_bars: StringProperty(name="Checked Task Items", default="[]")
    is_task_update_enabled: BoolProperty(name="Is Task Update Enabled", default=True)
    editing_sequence_type: StringProperty(name="Editing Sequence Type")
    active_sequence_id: IntProperty(name="Active Sequence Id")
    date_source_type: EnumProperty(
        name="Date Source",
        description="Choose which set of dates to use for animation and snapshots",
        items=[
            ('SCHEDULE', "Schedule", "Use ScheduleStart and ScheduleFinish dates"),
            ('ACTUAL', "Actual", "Use ActualStart and ActualFinish dates"),
            ('EARLY', "Early", "Use EarlyStart and EarlyFinish dates"),
            ('LATE', "Late", "Use LateStart and LateFinish dates"),
        ],
        default='SCHEDULE',
        update=update_date_source
    )
    last_lookahead_window: StringProperty(
        name="Last Lookahead Window",
        description="Stores the last selected lookahead time window to allow re-applying it automatically.",
        default=""
    )
    sequence_attributes: CollectionProperty(name="Sequence Attributes", type=Attribute)
    lag_time_attributes: CollectionProperty(name="Time Lag Attributes", type=Attribute)
    visualisation_start: StringProperty(name="Visualisation Start", update=update_visualisation_start)
    visualisation_finish: StringProperty(name="Visualisation Finish", update=update_visualisation_finish)
    speed_multiplier: FloatProperty(name="Speed Multiplier", default=10000)
    speed_animation_duration: StringProperty(name="Speed Animation Duration", default="1 s")
    speed_animation_frames: IntProperty(name="Speed Animation Frames", default=24)
    speed_real_duration: StringProperty(name="Speed Real Duration", default="1 w")
    speed_types: EnumProperty(
        items=[
            ("FRAME_SPEED", "Frame-based", "e.g. 25 frames = 1 real week"),
            ("DURATION_SPEED", "Duration-based", "e.g. 1 video second = 1 real week"),
            ("MULTIPLIER_SPEED", "Multiplier", "e.g. 1000 x real life speed"),
        ],
        name="Speed Type",
        default="FRAME_SPEED",
    )
    task_resources: CollectionProperty(name="Task Resources", type=TaskResource)
    active_task_resource_index: IntProperty(name="Active Task Resource Index")
    task_inputs: CollectionProperty(name="Task Inputs", type=TaskProduct)
    active_task_input_index: IntProperty(name="Active Task Input Index")
    task_outputs: CollectionProperty(name="Task Outputs", type=TaskProduct)
    active_task_output_index: IntProperty(name="Active Task Output Index")
    show_saved_colortypes_section: BoolProperty(name="Show Saved colortypes", default=True)
    show_nested_outputs: BoolProperty(name="Show Nested Tasks", default=False, update=update_active_task_outputs)
    show_nested_resources: BoolProperty(name="Show Nested Tasks", default=False, update=update_active_task_resources)
    show_nested_inputs: BoolProperty(name="Show Nested Tasks", default=False, update=update_active_task_inputs)
    product_input_tasks: CollectionProperty(name="Product Task Inputs", type=TaskProduct)
    product_output_tasks: CollectionProperty(name="Product Task Outputs", type=TaskProduct)
    active_product_output_task_index: IntProperty(name="Active Product Output Task Index")
    active_product_input_task_index: IntProperty(name="Active Product Input Task Index")
    enable_reorder: BoolProperty(name="Enable Reorder", default=False)
    show_task_operators: BoolProperty(name="Show Task Options", default=True)
    should_show_schedule_baseline_ui: BoolProperty(name="Baselines", default=False)
    filter_by_active_schedule: BoolProperty(
        name="Filter By Active Schedule", default=False, update=update_filter_by_active_schedule
    )
    # New property to show selected tasks count
    selected_tasks_count: IntProperty(name="Selected Tasks Count", default=0)

    # --- START ADDED CODE ---
    # Property that will contain the filter configuration
    filters: PointerProperty(type=BIMTaskFilterProperties)
    # --- END ADDED CODE ---
    # --- START ADDED CODE ---
    saved_filter_sets: CollectionProperty(type=SavedFilterSet)
    active_saved_filter_set_index: IntProperty()
    variance_source_a: EnumProperty(
        name="Compare",
        items=get_date_source_items,
        default=0,
        description="The baseline date set for comparison",
        update=update_variance_calculation,
    )
    variance_source_b: EnumProperty(
        name="With",
        items=get_date_source_items,
        default=1,
        description="The date set to compare against the baseline",
        update=update_variance_calculation,
    )
    
    # --- START COLUMN NAVIGATION PROPERTIES ---
    column_start_index: IntProperty(
        name="Column Start Index",
        description="Starting index for visible columns",
        default=0,
        min=0
    )
    columns_per_view: IntProperty(
        name="Columns Per View", 
        description="Maximum number of columns to display at once",
        default=5,
        min=1,
        max=20
    )
    # --- END COLUMN NAVIGATION PROPERTIES ---
    # --- END ADDED CODE ---

    
    if TYPE_CHECKING:
        saved_filter_sets: bpy.types.bpy_prop_collection_idprop[SavedFilterSet]
        active_saved_filter_set_index: int
        work_schedule_predefined_types: str
        object_type: str
        durations_attributes: bpy.types.bpy_prop_collection_idprop[ISODuration]
        work_calendars: str
        work_schedule_attributes: bpy.types.bpy_prop_collection_idprop[Attribute]
        editing_type: str
        editing_task_type: str
        active_work_schedule_index: int
        active_work_schedule_id: int
        active_task_index: int
        active_task_id: int
        last_lookahead_window: str
        date_source_type: str
        highlighted_task_id: int
        task_attributes: bpy.types.bpy_prop_collection_idprop[Attribute]
        should_show_visualisation_ui: bool
        should_show_task_bar_selection: bool
        should_show_snapshot_ui: bool
        should_show_column_ui: bool
        columns: bpy.types.bpy_prop_collection_idprop[Attribute]
        active_column_index: int
        sort_column: str
        is_sort_reversed: bool
        column_types: str
        task_columns: str
        task_time_columns: str
        other_columns: str
        active_task_time_id: int
        task_time_attributes: bpy.types.bpy_prop_collection_idprop[Attribute]
        contracted_tasks: str
        task_bars: str
        is_task_update_enabled: bool
        editing_sequence_type: str
        active_sequence_id: int
        sequence_attributes: bpy.types.bpy_prop_collection_idprop[Attribute]
        lag_time_attributes: bpy.types.bpy_prop_collection_idprop[Attribute]
        visualisation_start: str
        visualisation_finish: str
        speed_multiplier: float
        speed_animation_duration: str
        speed_animation_frames: int
        speed_real_duration: str
        speed_types: str
        task_resources: bpy.types.bpy_prop_collection_idprop[TaskResource]
        active_task_resource_index: int
        task_inputs: bpy.types.bpy_prop_collection_idprop[TaskProduct]
        active_task_input_index: int
        task_outputs: bpy.types.bpy_prop_collection_idprop[TaskProduct]
        active_task_output_index: int
        show_nested_outputs: bool
        show_nested_resources: bool
        show_nested_inputs: bool
        product_input_tasks: bpy.types.bpy_prop_collection_idprop[TaskProduct]
        product_output_tasks: bpy.types.bpy_prop_collection_idprop[TaskProduct]
        active_product_output_task_index: int
        active_product_input_task_index: int
        enable_reorder: bool
        show_task_operators: bool
        should_show_schedule_baseline_ui: bool
        filter_by_active_schedule: bool
        selected_tasks_count: int
        filters: 'BIMTaskFilterProperties'
        variance_source_a: str
        variance_source_b: str


class BIMTaskTreeProperties(PropertyGroup):
    # This belongs by itself for performance reasons. https://developer.blender.org/T87737
    tasks: CollectionProperty(name="Tasks", type=Task)
    if TYPE_CHECKING:
        tasks: bpy.types.bpy_prop_collection_idprop[Task]


class WorkCalendar(PropertyGroup):
    name: StringProperty(name="Name")
    ifc_definition_id: IntProperty(name="IFC Definition ID")
    if TYPE_CHECKING:
        name: str
        ifc_definition_id: int


class RecurrenceComponent(PropertyGroup):
    name: StringProperty(name="Name")
    is_specified: BoolProperty(name="Is Specified")
    if TYPE_CHECKING:
        name: str
        is_specified: bool


class BIMWorkCalendarProperties(PropertyGroup):
    work_calendar_attributes: CollectionProperty(name="Work Calendar Attributes", type=Attribute)
    work_time_attributes: CollectionProperty(name="Work Time Attributes", type=Attribute)
    editing_type: StringProperty(name="Editing Type")
    active_work_calendar_id: IntProperty(name="Active Work Calendar Id")
    active_work_time_id: IntProperty(name="Active Work Time Id")
    day_components: CollectionProperty(name="Day Components", type=RecurrenceComponent)
    weekday_components: CollectionProperty(name="Weekday Components", type=RecurrenceComponent)
    month_components: CollectionProperty(name="Month Components", type=RecurrenceComponent)
    position: IntProperty(name="Position")
    interval: IntProperty(name="Recurrence Interval")
    occurrences: IntProperty(name="Occurs N Times")
    recurrence_types: EnumProperty(
        items=[
            ("DAILY", "Daily", "e.g. Every day"),
            ("WEEKLY", "Weekly", "e.g. Every Friday"),
            ("MONTHLY_BY_DAY_OF_MONTH", "Monthly on Specified Date", "e.g. Every 2nd of each Month"),
            ("MONTHLY_BY_POSITION", "Monthly on Specified Weekday", "e.g. Every 1st Friday of each Month"),
            ("YEARLY_BY_DAY_OF_MONTH", "Yearly on Specified Date", "e.g. Every 2nd of October"),
            ("YEARLY_BY_POSITION", "Yearly on Specified Weekday", "e.g. Every 1st Friday of October"),
        ],
        name="Recurrence Types",
    )
    start_time: StringProperty(name="Start Time")
    end_time: StringProperty(name="End Time")
    if TYPE_CHECKING:
        work_calendar_attributes: bpy.types.bpy_prop_collection_idprop[Attribute]
        work_time_attributes: bpy.types.bpy_prop_collection_idprop[Attribute]
        editing_type: str
        active_work_calendar_id: int
        active_work_time_id: int
        day_components: bpy.types.bpy_prop_collection_idprop[RecurrenceComponent]
        weekday_components: bpy.types.bpy_prop_collection_idprop[RecurrenceComponent]
        month_components: bpy.types.bpy_prop_collection_idprop[RecurrenceComponent]
        position: int
        interval: int
        occurrences: int
        recurrence_types: str
        start_time: str
        end_time: str


def update_selected_date(self: "DatePickerProperties", context: bpy.types.Context) -> None:
    include_time = True
    selected_date = tool.Sequence.parse_isodate_datetime(self.selected_date, include_time)
    selected_date = selected_date.replace(hour=self.selected_hour, minute=self.selected_min, second=self.selected_sec)
    self.selected_date = tool.Sequence.isodate_datetime(selected_date, include_time)


class DatePickerProperties(PropertyGroup):
    display_date: StringProperty(
        name="Display Date",
        description="Needed to keep track of what month is currently opened in date picker without affecting the currently selected date.",
    )
    selected_date: StringProperty(name="Selected Date")
    selected_hour: IntProperty(min=0, max=23, update=update_selected_date)
    selected_min: IntProperty(min=0, max=59, update=update_selected_date)
    selected_sec: IntProperty(min=0, max=59, update=update_selected_date)
    if TYPE_CHECKING:
        display_date: str
        selected_date: str
        selected_hour: int
        selected_min: int
        selected_sec: int


class BIMDateTextProperties(PropertyGroup):
    start_frame: IntProperty(name="Start Frame")
    total_frames: IntProperty(name="Total Frames")
    start: StringProperty(name="Start")
    finish: StringProperty(name="Finish")
    if TYPE_CHECKING:
        start_frame: int
        total_frames: int
        start: str
        finish: str


class BIMTaskTypeColor(PropertyGroup):
    """Color by task type (legacy - maintain for compatibility)"""
    name: StringProperty(name="Name")
    animation_type: StringProperty(name="Type")
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR", size=4,
        default=(1.0, 0.0, 0.0, 1.0),
        min=0.0,
        max=1.0,
    )
    if TYPE_CHECKING:
        name: str
        animation_type: str
        color: tuple[float, float, float, float]


def update_colortype_considerations(self, context):
    """
    Asegura que no se pueda tener "Start" y "End" activos si "Active" está inactivo.
    Esta es una combinación sin sentido lógico en la animación.
    """
    try:
        if getattr(self, "consider_start", False) and getattr(self, "consider_end", False) and not getattr(self, "consider_active", True):
            # Forzar que Active sea True si Start y End están activos
            self.consider_active = True
        elif (not getattr(self, "consider_active", True)) and getattr(self, "consider_start", False) and getattr(self, "consider_end", False):
            # Opcional: si se intenta desactivar Active con Start y End activos, desactivar End
            self.consider_end = False
    except Exception:
        # No romper la UI si el PG aún no está totalmente inicializado
        pass

def toggle_live_color_updates(self, context):
    """Callback to enable/disable the live color update handler."""
    print(f"[DEBUG] toggle_live_color_updates called, enable_live_color_updates = {self.enable_live_color_updates}")
    try:
        if self.enable_live_color_updates:
            tool.Sequence.register_live_color_update_handler()
            print("Live color updates enabled.")
        else:
            tool.Sequence.unregister_live_color_update_handler()
            print("Live color updates disabled.")
    except Exception as e:
        print(f"Error toggling live color updates: {e}")
        import traceback
        traceback.print_exc()


class AnimationColorSchemes(PropertyGroup):
    """Animation Color Scheme for 4D animation"""
    name: StringProperty(name="Color Type Name", default="New Color Type")
    
    # Considered States
    consider_start: BoolProperty(
        name="Start state", 
        default=False,
        description="When enabled, elements use start appearance throughout the entire animation, "
                   "useful for existing elements, demolition context, or persistent visibility",
        update=update_colortype_considerations)
    consider_active: BoolProperty(
        name="Active state", 
        default=True,
        description="Apply appearance during task execution period",
        update=update_colortype_considerations)
    consider_end: BoolProperty(
        name="End state", 
        default=True,
        description="Apply appearance after task completion",
        update=update_colortype_considerations)
    
    # Colors by State
    start_color: FloatVectorProperty(
        name="Start Color",
        subtype="COLOR",
        size=4, min=0.0, max=1.0,
        default=(1.0, 1.0, 1.0, 1.0),
    )
    in_progress_color: FloatVectorProperty(
        name="In Progress Color",
        subtype="COLOR",
        size=4, min=0.0, max=1.0,
        default=(0.8, 0.8, 0.0, 1.0),
    )
    end_color: FloatVectorProperty(
        name="End Color",
        subtype="COLOR",
        size=4, min=0.0, max=1.0,
        default=(0.0, 1.0, 0.0, 1.0),
    )
    
    # Option to keep original color
    use_start_original_color: BoolProperty(name="Start: Use Original Color", default=False)
    use_active_original_color: BoolProperty(name="Active: Use Original Color", default=False)
    use_end_original_color: BoolProperty(name="End: Use Original Color", default=True)
    
    # Transparency Control
    start_transparency: FloatProperty(name="Start Transparency", min=0.0, max=1.0, default=0.0)
    active_start_transparency: FloatProperty(name="Active Start Transparency", min=0.0, max=1.0, default=0.0)
    active_finish_transparency: FloatProperty(name="Active Finish Transparency", min=0.0, max=1.0, default=0.0)
    active_transparency_interpol: FloatProperty(name="Transparency Interpol.", min=0.0, max=1.0, default=1.0)
    end_transparency: FloatProperty(name="End Transparency", min=0.0, max=1.0, default=0.0)

    hide_at_end: BoolProperty(name="Hide When Finished", description="If enabled, the object will become invisible in the End phase", default=False)
    
    if TYPE_CHECKING:
        name: str
        start_color: tuple[float, float, float, float]
        in_progress_color: tuple[float, float, float, float]
        end_color: tuple[float, float, float, float]
        use_start_original_color: bool
        use_active_original_color: bool
        use_end_original_color: bool
        start_transparency: float
        active_start_transparency: float
        active_finish_transparency: float
        active_transparency_interpol: float
        end_transparency: float
        hide_at_end: bool


def update_legend_hud_on_group_change(self, context):
    """Callback que se ejecuta cuando cambia el estado enabled de un grupo"""
    try:
        # --- INICIO DE LA CORRECCIÓN ---
        # Cuando se activa/desactiva un grupo, es crucial actualizar el snapshot
        # del estado de la UI. El modo "Live Color Updates" depende de este
        # snapshot para saber qué perfiles aplicar.
        from .operators.schedule_task_operators import snapshot_all_ui_state
        snapshot_all_ui_state(context)
        # --- FIN DE LA CORRECCIÓN ---

        print(f"🔄 GROUP CHANGE CALLBACK: Group '{self.group}' enabled changed to: {self.enabled}")
        
        # NUEVA FUNCIONALIDAD: Sincronizar animation_color_schemes automáticamente
        _sync_animation_color_schemes_with_active_groups(context)
        
        # ... (código para actualizar el HUD de la leyenda) ...

        # Invalidar caché del legend HUD para refrescar
        from bonsai.bim.module.sequence.hud_overlay import invalidate_legend_hud_cache, refresh_hud
        invalidate_legend_hud_cache()

        # Forzar un redibujado del viewport. Esto es crucial para que el 
        # live_color_update_handler se ejecute y aplique los colores del nuevo grupo.
        refresh_hud()

        print("🔄 Legend HUD cache invalidated and viewport refreshed")
    except Exception as e:
        import traceback
        print(f"⚠️ Could not auto-update Legend HUD: {e}")
        traceback.print_exc()


def _sync_animation_color_schemes_with_active_groups(context):
    """
    Sincroniza automáticamente el campo animation_color_schemes de las tareas
    con el ColorType del grupo activo cuando se activa/desactiva un checkbox de grupo.
    """
    try:
        import bonsai.tool as tool
        
        # Obtener propiedades de las tareas
        tprops = tool.Sequence.get_task_tree_props()
        if not tprops or not hasattr(tprops, 'tasks'):
            return
        
        synced_tasks = 0
        
        for task in tprops.tasks:
            try:
                # Solo procesar tareas que usan grupos activos
                use_active_group = getattr(task, 'use_active_colortype_group', False)
                if not use_active_group:
                    continue
                
                # Buscar grupo activo (enabled=True) que no sea DEFAULT
                active_group_colortype = ''
                group_choices = getattr(task, 'colortype_group_choices', [])
                
                for choice in group_choices:
                    group_name = getattr(choice, 'group_name', '')
                    enabled = getattr(choice, 'enabled', False)
                    colortype = getattr(choice, 'selected_colortype', '')
                    
                    if enabled and group_name != 'DEFAULT' and colortype:
                        active_group_colortype = colortype
                        break
                
                # Sincronizar animation_color_schemes con el grupo activo
                if active_group_colortype:
                    current_animation_schemes = getattr(task, 'animation_color_schemes', '')
                    if active_group_colortype != current_animation_schemes:
                        print(f"🔄 AUTO-SYNC: Task {task.ifc_definition_id} - '{current_animation_schemes}' → '{active_group_colortype}'")
                        safe_set_animation_color_schemes(task, active_group_colortype)
                        synced_tasks += 1
                
            except Exception as e:
                print(f"❌ Error syncing task {getattr(task, 'ifc_definition_id', '?')}: {e}")
                continue
        
        if synced_tasks > 0:
            print(f"✅ AUTO-SYNC: Updated animation_color_schemes for {synced_tasks} tasks")
    
    except Exception as e:
        print(f"❌ Error in auto-sync animation_color_schemes: {e}")


class AnimationColorTypeGroupItem(PropertyGroup):
    """Item for animation group stack"""
    group: EnumProperty(name="Group", items=get_internal_ColorType_sets_enum)
    enabled: BoolProperty(name="Use", default=True, update=update_legend_hud_on_group_change)


class BIMAnimationProperties(PropertyGroup):
    """Animation properties with improved colortype system"""
    
    # Unified colortype system
    active_ColorType_system: EnumProperty(
        name="ColorType System",
        items=[
            ("ColorTypeS", "Animation Color Schemes", "Use advanced ColorType system"),
        ],
        default="ColorTypeS"
    )
    
    # Animation group stack
    animation_group_stack: CollectionProperty(name="Animation Group Stack", type=AnimationColorTypeGroupItem)
    animation_group_stack_index: IntProperty(name="Animation Group Stack Index", default=-1)
    
    # State and configuration
    is_editing: BoolProperty(name="Is Loaded", default=False)
    saved_colortype_name: StringProperty(name="colortype Set Name", default="Default")
    
    # Animation Color Scheme
    ColorTypes: CollectionProperty(name="Animation Color Scheme", type=AnimationColorSchemes)
    active_ColorType_index: IntProperty(name="Active ColorType Index")
    ColorType_groups: EnumProperty(name="ColorType Group", items=get_internal_ColorType_sets_enum, update=update_ColorType_group)

    # Bandera para controlar si la animación ha sido creada al menos una vez.
    is_animation_created: BoolProperty(
        name="Is Animation Created",
        description="Internal flag to check if the main animation has been created at least once",
        default=False
    )

    # New property, only for the Tasks panel UI, which excludes 'DEFAULT'
    task_colortype_group_selector: EnumProperty(
        name="Custom colortype Group",
        items=get_user_created_groups_enum,
        update=update_task_colortype_group_selector
    )
   
    # UI toggles
    show_saved_task_colortypes_panel: BoolProperty(name="Show Saved colortypes", default=False)
    should_show_task_bar_options: BoolProperty(name="Show Task Bar Options", default=False)

    # --- NEW: Live Color Updates ---
    enable_live_color_updates: BoolProperty(
        name="Live Color Updates",
        description="Enable to update object colors dynamically during animation playback when changing ColorType groups. Disable for faster playback and rendering (bakes colors).",
        default=False,
        update=toggle_live_color_updates
    )
    
    auto_update_on_date_source_change: BoolProperty(
        name="Auto-update Animation",
        description="Automatically update the 3D animation when the Date Source changes. May be slow on large models.",
        default=False
    )
    
    # Task bar colors
    color_full: FloatVectorProperty(
        name="Full Bar",
        subtype="COLOR", size=4,
        default=(1.0, 0.0, 0.0, 1.0),
        min=0.0, max=1.0,
        description="Color for full task bar",
        update=update_color_full,
    )
    color_progress: FloatVectorProperty(
        name="Progress Bar",
        subtype="COLOR", size=4,
        default=(0.0, 1.0, 0.0, 1.0),
        min=0.0, max=1.0,
        description="Color for progress task bar",
        update=update_color_progress,
    )
    
    # Legacy properties (maintain for compatibility)
    saved_color_schemes: EnumProperty(items=get_saved_color_schemes, name="Saved Colour Schemes")
    active_color_component_outputs_index: IntProperty(name="Active Color Component Index")
    active_color_component_inputs_index: IntProperty(name="Active Color Component Index")
    if TYPE_CHECKING:
        active_ColorType_system: str
        animation_group_stack: bpy.types.bpy_prop_collection_idprop[AnimationColorTypeGroupItem]
        animation_group_stack_index: int
        is_editing: bool
        saved_colortype_name: str
        ColorTypes: bpy.types.bpy_prop_collection_idprop[AnimationColorSchemes]
        active_ColorType_index: int
        ColorType_groups: str
        task_colortype_group_selector: str
        show_saved_task_colortypes_panel: bool
        should_show_task_bar_options: bool
        enable_live_color_updates: bool
        color_full: Color
        color_progress: Color
        saved_color_schemes: str
        active_color_component_outputs_index: int
        active_color_component_inputs_index: int


# === Camera & Orbit Settings (safe-inject) ===================================
# We attach properties dynamically to BIMAnimationProperties so we don't depend
# on the exact class body location. This works as long as registration happens
# after these attributes exist.

try:
    from bpy.props import FloatProperty, BoolProperty, EnumProperty, PointerProperty
    import bpy
    from bpy.types import Object as _BpyObject

    _C = BIMAnimationProperties  # type: ignore[name-defined]

    def _add_prop(cls, name, pdef):
        # Ensure annotation slot exists for Blender 2.8+ registration
        try:
            ann = getattr(cls, "__annotations__", None)
            if ann is None:
                cls.__annotations__ = {}
            if name not in cls.__annotations__:
                cls.__annotations__[name] = pdef
        except Exception:
            pass
        # Attach descriptor if missing
        if not hasattr(cls, name):
            setattr(cls, name, pdef)

    # --- Camera ---
    _add_prop(_C, "camera_focal_mm", FloatProperty(name="Focal (mm)", default=35.0, min=1.0, max=300.0))
    _add_prop(_C, "camera_clip_start", FloatProperty(name="Clip Start", default=0.1, min=0.0001))
    _add_prop(_C, "camera_clip_end", FloatProperty(name="Clip End", default=10000.0, min=1.0))

    # --- Orbit ---
    _add_prop(_C, "orbit_mode", EnumProperty(
        name="Orbit Mode",
        items=[
            ("NONE", "None (Static)", "No orbit animation"),
            ("CIRCLE_360", "Circle 360°", "Full circular orbit"),
            ("PINGPONG", "Ping-Pong", "Back and forth over an arc"),
        ],
        default="CIRCLE_360"
    ))

    _add_prop(_C, "orbit_radius_mode", EnumProperty(
        name="Radius Mode",
        items=[("AUTO", "Auto (from bbox)", "Compute radius from WorkSchedule bbox"),
               ("MANUAL", "Manual", "Use manual radius value")],
        default="AUTO"
    ))
    _add_prop(_C, "orbit_radius", FloatProperty(name="Radius (m)", default=10.0, min=0.01))
    _add_prop(_C, "orbit_height", FloatProperty(name="Height (Z offset)", default=8.0))
    _add_prop(_C, "orbit_start_angle_deg", FloatProperty(name="Start Angle (deg)", default=0.0))
    _add_prop(_C, "orbit_direction", EnumProperty(
        name="Direction",
        items=[("CCW", "CCW", "Counter-clockwise"), ("CW", "CW", "Clockwise")],
        default="CCW"
    ))

    # --- Look At ---
    _add_prop(_C, "look_at_mode", EnumProperty(
        name="Look At",
        items=[("AUTO", "Auto (active WorkSchedule area)", "Use bbox center of active WorkSchedule"),
               ("OBJECT", "Object", "Select object/Empty as target")],
        default="AUTO"
    ))
    _add_prop(_C, "look_at_object", PointerProperty(name="Target", type=_BpyObject))

    # --- NEW: Path Shape & Custom Path ---
    _add_prop(_C, "orbit_path_shape", EnumProperty(
        name="Path Shape",
        items=[
            ('CIRCLE', "Circle (Generated)", "The add-on creates a perfect circle"),
            ('CUSTOM', "Custom Path", "Use your own curve object as the path"),
        ],
        default='CIRCLE',
    ))
    _add_prop(_C, "custom_orbit_path", PointerProperty(
        name="Custom Path",
        type=_BpyObject,
        poll=lambda self, object: getattr(object, "type", None) == 'CURVE'
    ))

    # --- NEW: Interpolation ---
    _add_prop(_C, "interpolation_mode", EnumProperty(
        name="Interpolation",
        items=[
            ('LINEAR', "Linear (Constant Speed)", "Constant, mechanical speed"),
            ('BEZIER', "Bezier (Smooth)", "Smooth ease-in and ease-out for a natural feel"),
        ],
        default='LINEAR',
    ))


    _add_prop(_C, "bezier_smoothness_factor", FloatProperty(
        name="Smoothness Factor",
        description="Controls the intensity of the ease-in/ease-out. Higher values create a more gradual transition",
        default=0.35,
        min=0.0,
        max=2.0,
        soft_min=0.0,
        soft_max=1.0
    ))
    # --- Animation method & duration ---
    _add_prop(_C, "orbit_path_method", EnumProperty(
        name="Path Method",
        items=[("FOLLOW_PATH", "Follow Path (editable)", "Bezier circle + Follow Path"),
               ("KEYFRAMES", "Keyframes (lightweight)", "Animate location directly")],
        default="FOLLOW_PATH"
    ))
    _add_prop(_C, "orbit_use_4d_duration", BoolProperty(
        name="Use 4D total frames", default=True,
        description="If enabled, orbit spans the whole 4D animation range"))
    _add_prop(_C, "orbit_duration_frames", FloatProperty(
        name="Orbit Duration (frames)", default=250.0, min=1.0))

    # --- UI toggles ---
    _add_prop(_C, "show_camera_orbit_settings", BoolProperty(
        name="Camera & Orbit", default=False, description="Toggle Camera & Orbit settings visibility"))
    

    _add_prop(_C, "hide_orbit_path", BoolProperty(
        name="Hide Orbit Path", default=False,
        description="Hide the visible orbit path (Bezier Circle) in the viewport and render"))

    # --- HUD (Heads-Up Display) properties mirrored on BIMAnimationProperties ---
    _add_prop(_C, "enable_text_hud", BoolProperty(
        name="Enable Text HUD",
        description="Attach schedule texts as HUD elements to the active camera",
        default=False, update=update_gpu_hud_visibility))
    _add_prop(_C, "hud_margin_horizontal", FloatProperty(
        name="Horizontal Margin",
        description="Distance from camera edge (percentage of camera width)",
        default=0.05, min=0.0, max=0.3, precision=3,
        update=update_hud_gpu))
    _add_prop(_C, "hud_margin_vertical", FloatProperty(
        name="Vertical Margin",
        description="Distance from camera edge (percentage of camera height)",
        default=0.05, min=0.0, max=0.3, precision=3,
        update=update_hud_gpu))
    _add_prop(_C, "hud_text_spacing", FloatProperty(
        name="Text Spacing",
        description="Vertical spacing between HUD text elements",
        default=0.02, min=0.0, max=0.2, precision=3,
        update=update_hud_gpu))
    _add_prop(_C, "hud_scale_factor", FloatProperty(
        name="HUD Scale Factor",
        description="Scale multiplier for HUD elements relative to camera distance",
        default=1.0, min=0.1, max=5.0, precision=2,
        update=update_hud_gpu))
    _add_prop(_C, "hud_distance", FloatProperty(
        name="Distance",
        description="Distance from camera to place HUD elements",
        default=3.0, min=0.5, max=50.0, precision=1,
        update=update_hud_gpu))

    _add_prop(_C, "hud_position", EnumProperty(
        name="HUD Position",
        description="Position of HUD elements on screen",
        items=[
            ('TOP_LEFT', "Top Left", "Position HUD at top-left corner"),
            ('TOP_RIGHT', "Top Right", "Position HUD at top-right corner"),
            ('BOTTOM_LEFT', "Bottom Left", "Position HUD at bottom-left corner"),
            ('BOTTOM_RIGHT', "Bottom Right", "Position HUD at bottom-right corner"),
        ],
        default='TOP_RIGHT',
        update=update_hud_gpu))



except Exception as _e:
    # Failsafe: leave file importable if Bonsai internals are not present here
    pass
# === End Camera & Orbit Settings ====================================================================================