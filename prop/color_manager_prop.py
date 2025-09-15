import bpy
import json
import bonsai.tool as tool
from typing import Dict

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
                    {"name": "INSTALLATION", "start_color": [1,1,1,0], "in_progress_color": [0,1,0,1], "end_color": [0.3,0.8,0.5,1]},
                    {"name": "DEMOLITION", "start_color": [1,1,1,1], "in_progress_color": [1,0,0,1], "end_color": [0,0,0,0]},
                    {"name": "REMOVAL", "start_color": [1,1,1,1], "in_progress_color": [1,0,0,1], "end_color": [0,0,0,0]},
                    {"name": "DISPOSAL", "start_color": [1,1,1,1], "in_progress_color": [1,0,0,1], "end_color": [0,0,0,0]},
                    {"name": "DISMANTLE", "start_color": [1,1,1,1], "in_progress_color": [1,0,0,1], "end_color": [0,0,0,0]},
                    {"name": "OPERATION", "start_color": [1,1,1,1], "in_progress_color": [0,0,1,1], "end_color": [1,1,1,1]},
                    {"name": "MAINTENANCE", "start_color": [1,1,1,1], "in_progress_color": [0,0,1,1], "end_color": [1,1,1,1]},
                    {"name": "ATTENDANCE", "start_color": [1,1,1,1], "in_progress_color": [0,0,1,1], "end_color": [1,1,1,1]},
                    {"name": "RENOVATION", "start_color": [1,1,1,1], "in_progress_color": [0,0,1,1], "end_color": [0.9,0.9,0.9,1]},
                    {"name": "LOGISTIC", "start_color": [1,1,1,1], "in_progress_color": [1,1,0,1], "end_color": [1,0.8,0.3,1]},
                    {"name": "MOVE", "start_color": [1,1,1,1], "in_progress_color": [1,1,0,1], "end_color": [0.8,0.6,0,1]},
                    {"name": "NOTDEFINED", "start_color": [0.7,0.7,0.7,1], "in_progress_color": [0.5,0.5,0.5,1], "end_color": [0.3,0.3,0.3,1]},
                    {"name": "USERDEFINED", "start_color": [0.7,0.7,0.7,1], "in_progress_color": [0.5,0.5,0.5,1], "end_color": [0.3,0.3,0.3,1]},
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
    def get_active_group_name(context) -> str:
        """Get the currently active ColorType group name from Animation Settings."""
        try:
            # Try to get from Animation Settings
            anim_props = tool.Sequence.get_animation_props()
            if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                # Find the first enabled group in the stack
                for item in anim_props.animation_group_stack:
                    if getattr(item, 'enabled', False):
                        return getattr(item, 'group', 'DEFAULT')

            # Fallback: if no active group found, return first available group or DEFAULT
            all_groups = UnifiedColorTypeManager.get_all_groups(context)
            return all_groups[0] if all_groups else 'DEFAULT'

        except Exception as e:
            print(f"⚠️ Error getting active group name: {e}")
            return 'DEFAULT'

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