


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
from typing import TYPE_CHECKING, Literal, get_args, Optional, Dict, List, Set

# Importamos el manager que ya separamos
from .color_manager_prop import UnifiedColorTypeManager


# Hacemos una importación circular segura
from . import enums_prop
from .enums_prop import get_custom_group_colortype_items



def update_filter_column(self, context):
    """
    Callback que se ejecuta al cambiar la columna del filtro.
    Identifica el tipo de dato y resetea los valores para evitar inconsistencias.
    Callback that runs when changing the filter column.
    It identifies the data type and resets the values to avoid inconsistencies.
    """
    from . import enums_prop
    
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



def update_date_source_type(self, context):
    """
    Simple callback when the user changes schedule type.
    Only updates date range using Guess functionality.
    """
    try:
        print(f"📅 Date source changed to: {self.date_source_type}")
        
        # Store previous dates for sync animation
        previous_start = self.visualisation_start
        previous_finish = self.visualisation_finish

        # Update date range for the new schedule type using Guess
        bpy.ops.bim.guess_date_range('INVOKE_DEFAULT', work_schedule=self.active_work_schedule_id)
        
        # Call sync animation if it exists
        try:
            bpy.ops.bim.sync_animation_by_date(
                'INVOKE_DEFAULT',
                previous_start_date=previous_start,
                previous_finish_date=previous_finish
            )
        except Exception as e:
            print(f"⚠️ Animation sync failed: {e}")
                
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
        # Crear el empty si no existe
        parent_empty = bpy.data.objects.new(parent_name, None)
        bpy.context.scene.collection.objects.link(parent_empty)
        parent_empty.empty_display_type = 'PLAIN_AXES'
        parent_empty.empty_display_size = 2

    # LIMPIAR anchor modes SIEMPRE (como en el script que funcionaba)
    if 'anchor_mode' in parent_empty:
        del parent_empty['anchor_mode']
    if 'hud_anchor_mode' in context.scene:
        del context.scene['hud_anchor_mode']


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

    # Clear existing constraints
    for c in list(parent_empty.constraints):
        parent_empty.constraints.remove(c)

    # Si CUALQUIER checkbox está activado, crear AMBOS constraints
    if use_custom_rot_target or use_custom_loc_target:
        # Determinar targets
        rotation_target = custom_rotation_target if (use_custom_rot_target and custom_rotation_target) else active_camera
        location_target = custom_location_target if (use_custom_loc_target and custom_location_target) else active_camera

        # Crear constraint de rotación
        if rotation_target:
            rot_constraint = parent_empty.constraints.new(type='COPY_ROTATION')
            rot_constraint.target = rotation_target

        # Crear constraint de ubicación
        if location_target:
            loc_constraint = parent_empty.constraints.new(type='COPY_LOCATION')
            loc_constraint.target = location_target


def update_legend_3d_hud_constraint(context):
    """
    Finds the 'HUD_3D_Legend' empty and updates its rotation and location constraints.
    Rotation and location can follow the active camera or custom targets.
    """
    print("🚀 DEBUG: ¡update_legend_3d_hud_constraint EJECUTÁNDOSE!")
    import bpy
    import bonsai.tool as tool

    hud_empty = None
    for obj in bpy.data.objects:
        if obj.get("is_3d_legend_hud", False):
            hud_empty = obj
            break

    print(f"🔍 DEBUG: 3D Legend HUD encontrado: {hud_empty.name if hud_empty else 'None'}")

    if not hud_empty:
        print("❌ DEBUG: No se encontró 3D Legend HUD")
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
        # Persist intent - COMENTADO para permitir constraints custom
        # try:
        #     hud_empty['anchor_mode'] = 'WORLD_ORIGIN'
        #     if scene is not None:
        #         scene['hud_anchor_mode'] = 'WORLD_ORIGIN'
        # except Exception:
        #     pass
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

    # --- Clear existing constraints to ensure a clean state ---
    for c in list(hud_empty.constraints):
        hud_empty.constraints.remove(c)

    # SOLO crear constraints si los checkboxes están activados

    # Add rotation constraint SOLO si el checkbox está activado
    if use_custom_rot_target:
        rotation_target = custom_rotation_target if custom_rotation_target else active_camera
        if rotation_target:
            rot_constraint = hud_empty.constraints.new(type='COPY_ROTATION')
            rot_constraint.target = rotation_target
            print(f"✅ Constraint de Rotación creado en '{hud_empty.name}' apuntando a '{rotation_target.name}'")
        else:
            print(f"⚠️ Checkbox de rotación activado pero no hay target para '{hud_empty.name}'")

    # Add location constraint SOLO si el checkbox está activado
    if use_custom_loc_target:
        location_target = custom_location_target if custom_location_target else active_camera
        if location_target:
            loc_constraint = hud_empty.constraints.new(type='COPY_LOCATION')
            loc_constraint.target = location_target
            print(f"✅ Constraint de Ubicación creado en '{hud_empty.name}' apuntando a '{location_target.name}'")
        else:
            print(f"⚠️ Checkbox de ubicación activado pero no hay target para '{hud_empty.name}'")

    # Si ningún checkbox está activado, no se crean constraints
    if not use_custom_rot_target and not use_custom_loc_target:
        print(f"📝 Sin checkboxes activados - '{hud_empty.name}' sin constraints (libre)")

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
    Callback that is executed when checking/unchecking a checkbox.
    Uses a timer to execute the 3D selection logic safely.
    """
    def apply_selection():
        try:
            # --- START OF MODIFICATION ---
            # Get the properties to check if 3D selection is active
            props = tool.Sequence.get_work_schedule_props()
            if props.should_select_3d_on_task_click:
                tool.Sequence.apply_selection_from_checkboxes()
            # If the main checkbox is off, do nothing.
            # --- END OF MODIFICATION ---
        except Exception as e:
            print(f"Error in delayed checkbox selection update: {e}")
        return None  # The timer only runs once

    # Register the function with a timer to avoid context issues
    import bpy
    if not bpy.app.timers.is_registered(apply_selection):
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
                "ATTENDANCE", "RENOVATION", "LOGISTIC", "MOVE", "NOTDEFINED", "USERDEFINED"
            ]
            colortypes = {}
            for name in default_order:
                # Aquí forzamos que se use el método que ya hemos corregido
                colortypes[name] = UnifiedColorTypeManager._create_default_colortype_data(name)
            return colortypes

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
                "ATTENDANCE", "RENOVATION", "LOGISTIC", "MOVE", "NOTDEFINED", "USERDEFINED"
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
                    "ATTENDANCE", "RENOVATION", "LOGISTIC", "MOVE", "NOTDEFINED", "USERDEFINED"
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
            "INSTALLATION": {"start": [1,1,1,0], "active": [0,1,0,1], "end": [0.3,0.8,0.5,1]},
            "DEMOLITION": {"start": [1,1,1,1], "active": [1,0,0,1], "end": [0,0,0,0], "hide": True},
            "REMOVAL": {"start": [1,1,1,1], "active": [1,0,0,1], "end": [0,0,0,0], "hide": True},
            "DISPOSAL": {"start": [1,1,1,1], "active": [1,0,0,1], "end": [0,0,0,0], "hide": True},
            "DISMANTLE": {"start": [1,1,1,1], "active": [1,0,0,1], "end": [0,0,0,0], "hide": True},
            "OPERATION": {"start": [1,1,1,1], "active": [0,0,1,1], "end": [1,1,1,1]},
            "MAINTENANCE": {"start": [1,1,1,1], "active": [0,0,1,1], "end": [1,1,1,1]},
            "ATTENDANCE": {"start": [1,1,1,1], "active": [0,0,1,1], "end": [1,1,1,1]},
            "RENOVATION": {"start": [1,1,1,1], "active": [0,0,1,1], "end": [0.9,0.9,0.9,1]},
            "LOGISTIC": {"start": [1,1,1,1], "active": [1,1,0,1], "end": [1,0.8,0.3,1]},
            "MOVE": {"start": [1,1,1,1], "active": [1,1,0,1], "end": [0.8,0.6,0,1]},
            "NOTDEFINED": {"start": [0.7,0.7,0.7,1], "active": [0.5,0.5,0.5,1], "end": [0.3,0.3,0.3,1]},
            "USERDEFINED": {"start": [0.7,0.7,0.7,1], "active": [0.5,0.5,0.5,1], "end": [0.3,0.3,0.3,1]},
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
            "active_start_transparency": 0.8,
            "active_finish_transparency": 0.3,
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
        from ..operators.schedule_task_operators import snapshot_all_ui_state
        
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

    # --- 3D SELECTION LOGIC FOR SINGLE CLICK ---
    props = tool.Sequence.get_work_schedule_props()
    if props.should_select_3d_on_task_click:
        if not task_ifc:
            try:
                bpy.ops.object.select_all(action='DESELECT')
            except RuntimeError:
                # Ocurre si no estamos en modo objeto, es seguro ignorarlo.
                pass
            # Salida temprana de la función de actualización - no continuar con la selección 3D
            return

        try:
            outputs = tool.Sequence.get_task_outputs(task_ifc)
            
            # Deseleccionar todo lo demás primero
            if bpy.context.view_layer.objects.active:
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')

            if outputs:
                objects_to_select = [tool.Ifc.get_object(p) for p in outputs if tool.Ifc.get_object(p)]
                
                if objects_to_select:
                    for obj in objects_to_select:
                        # <-- PASO 1: Asegurarse de que el objeto sea visible y seleccionable
                        obj.hide_set(False)
                        obj.hide_select = False
                        
                        # <-- PASO 2: Seleccionar el objeto
                        obj.select_set(True)
                    
                    # <-- PASO 3: Establecer el primer objeto como activo
                    context.view_layer.objects.active = objects_to_select[0]
                    
                    # <-- PASO 4: Centrar la vista 3D en los objetos seleccionados
                    bpy.ops.view3d.view_selected()
                    
        except Exception as e:
            print(f"Error selecting 3D objects for task: {e}")

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
    """Updates active colortype group - FIXED: No auto-sync to prevent data corruption"""

    # Mark that user manually changed ColorType_groups for editing
    self._ColorType_groups_manually_set = True
    print(f"🎯 User manually selected '{self.ColorType_groups}' for editing")

    # REMOVED: sync_active_group_to_json() - This was causing data corruption
    # When switching groups, the editor content would overwrite the wrong group
    # Users must manually save groups with "Save Group" button
    print(f"⚠️  Group switched to '{self.ColorType_groups}' - use 'Save Group' to persist changes")

    # Clean up invalid mappings
    UnifiedColorTypeManager.cleanup_invalid_mappings(context)

    # Load colortypes of the selected group
    if self.ColorType_groups:
        UnifiedColorTypeManager.load_colortypes_into_collection(self, context, self.ColorType_groups)

    # REMOVED: Task synchronization that was corrupting data
    # When switching groups in editor, we should NOT modify task colortype assignments
    # This was causing the last custom group to get overwritten with wrong values
    print(f"ℹ️  Editor group changed to '{self.ColorType_groups}' - task assignments unchanged")


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

        from bonsai.bim.module.sequence import hud as hud_overlay

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
                import bonsai.bim.module.sequence.hud as hud_overlay
                
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
    
    # --- LÓGICA DE DESACTIVACIÓN AUTOMÁTICA ---
    # Si 3D HUD Render se desactiva, desactivar automáticamente el 3D Legend HUD
    try:
        import bonsai.tool as tool
        anim_props = tool.Sequence.get_animation_props()
        camera_props = anim_props.camera_orbit
        
        if should_hide:  # Si se está desactivando el 3D HUD Render
            current_legend_enabled = getattr(camera_props, "enable_3d_legend_hud", False)
            if current_legend_enabled:
                print("🔴 3D HUD Render disabled: Auto-disabling 3D Legend HUD checkbox")
                camera_props.enable_3d_legend_hud = False
                
    except Exception as e:
        print(f"⚠️ Error in auto-disable logic: {e}")
    
    # Toggle visibility for "Schedule_Display_Texts"
    try:
        collection_texts = bpy.data.collections.get("Schedule_Display_Texts")
        if collection_texts:
            collection_texts.hide_viewport = should_hide
            collection_texts.hide_render = should_hide
            # También itera sobre los objetos para asegurar la visibilidad
            for obj in collection_texts.objects:
                obj.hide_viewport = should_hide
                obj.hide_render = should_hide
            print(f"✅ Schedule_Display_Texts collection and objects visibility set to hide={should_hide}")
    except Exception as e:
        print(f"❌ Error toggling 3D text visibility: {e}")

    # Toggle visibility for "Schedule_Display_3D_Legend" (controlled by show_3d_schedule_texts)
    try:
        import bonsai.tool as tool
        camera_props = tool.Sequence.get_animation_props().camera_orbit
        legend_should_be_hidden = should_hide or not camera_props.enable_3d_legend_hud

        collection_legend = bpy.data.collections.get("Schedule_Display_3D_Legend")
        if collection_legend:
            collection_legend.hide_viewport = legend_should_be_hidden
            collection_legend.hide_render = legend_should_be_hidden
            # Itera sobre los objetos de la leyenda para asegurar la visibilidad
            for obj in collection_legend.objects:
                obj.hide_viewport = legend_should_be_hidden
                obj.hide_render = legend_should_be_hidden
            print(f"✅ Schedule_Display_3D_Legend visibility set to hide={legend_should_be_hidden}")
    except Exception as e:
        print(f"❌ Error toggling 3D Legend HUD visibility: {e}")

    # Forzar refresco de la pantalla
    try:
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass
        
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


def update_legend_hud_on_group_change(self, context):
    """Callback que se ejecuta cuando cambia el estado enabled de un grupo"""
    try:
        # --- INICIO DE LA CORRECCIÓN ---
        # Cuando se activa/desactiva un grupo, es crucial actualizar el snapshot
        # del estado de la UI. El modo "Live Color Updates" depende de este
        # snapshot para saber qué perfiles aplicar.
        from ..operators.schedule_task_operators import snapshot_all_ui_state
        snapshot_all_ui_state(context)
        # --- FIN DE LA CORRECCIÓN ---

        print(f"🔄 GROUP CHANGE CALLBACK: Group '{self.group}' enabled changed to: {self.enabled}")
        
        # NUEVA FUNCIONALIDAD: Sincronizar animation_color_schemes automáticamente
        _sync_animation_color_schemes_with_active_groups(context)
        
        # ... (código para actualizar el HUD de la leyenda) ...

        # Invalidar caché del legend HUD para refrescar
        from ..hud import invalidate_legend_hud_cache, refresh_hud
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

def update_selected_date(self: "DatePickerProperties", context: bpy.types.Context) -> None:
    include_time = True
    selected_date = tool.Sequence.parse_isodate_datetime(self.selected_date, include_time)
    selected_date = selected_date.replace(hour=self.selected_hour, minute=self.selected_min, second=self.selected_sec)
    self.selected_date = tool.Sequence.isodate_datetime(selected_date, include_time)






















