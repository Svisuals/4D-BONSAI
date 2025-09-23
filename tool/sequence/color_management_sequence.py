# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021, 2022 Dion Moult <dion@thinkmoult.com>, Yassine Oualid <yassine@sigmadimensions.com>, Federico Eraso <feraso@svisuals.net
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


from __future__ import annotations
import bpy
import json
from typing import Optional
import ifcopenshell
from .props_sequence import PropsSequence

# Asumimos que UnifiedColorTypeManager estará en el módulo prop
try:
    from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
except ImportError:
    UnifiedColorTypeManager = None


class ColorManagementSequence(PropsSequence):
    """Mixin class for managing 4D animation color schemes and profiles (ColorTypes)."""

@classmethod
def load_ColorType_group_data(cls, group_name):
    """Loads data from a specific profile group"""
    import bpy, json
    scene = bpy.context.scene
    raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        return data.get(group_name, {})
    except Exception:
        return {}
    
@classmethod
def get_all_ColorType_groups(cls):
    """Gets all available profile groups"""
    import bpy
    return UnifiedColorTypeManager.get_all_groups(bpy.context)

@classmethod
def get_custom_ColorType_groups(cls):
    """Gets only custom groups (without DEFAULT)"""
    import bpy
    return UnifiedColorTypeManager.get_user_created_groups(bpy.context)

@classmethod
def has_animation_colors(cls):
    return bpy.context.scene.BIMAnimationProperties.task_output_colors


@classmethod
def load_default_animation_color_scheme(cls):
    """CORRECTED: Restaura los ColorTypes originales de cada tarea en lugar de sobrescribir con hardcoded"""
    print("🔄 RESET: Restaurando ColorTypes originales de las tareas...")

    try:
        import bpy
        context = bpy.context
        tprops = getattr(context.scene, 'BIMTaskTreeProperties', None)
        if not tprops:
            print("[ERROR] RESET: No se encontraron propiedades de tareas")
            return

        reset_count = 0
        for task in tprops.tasks:
            task_id = str(task.ifc_definition_id)
            if task_id == "0":
                continue

            try:
                # 1. Obtener el grupo personalizado original de la tarea
                original_group = None
                if hasattr(task, 'animation_group_stack') and task.animation_group_stack:
                    for group_item in task.animation_group_stack:
                        if group_item.enabled:
                            original_group = group_item.group
                            break

                # 2. Si la tarea tiene grupo personalizado, restaurar sus ColorTypes
                if original_group and original_group != "DEFAULT":
                    print(f"🔄 RESET: Restaurando tarea {task_id} del grupo '{original_group}'")

                    # Restaurar ColorType del grupo original
                    predefined_type = getattr(task, 'PredefinedType', 'NOTDEFINED') or 'NOTDEFINED'
                    original_colortype = cls.load_ColorType_from_group(original_group, predefined_type)

                    if original_colortype:
                        # Aplicar ColorType original a la tarea
                        if hasattr(task, 'animation_color_schemes'):
                            task.animation_color_schemes = predefined_type

                        # Restore group configuration in the task
                        if hasattr(task, 'selected_colortype_in_active_group'):
                            try:
                                task.selected_colortype_in_active_group = predefined_type
                            except:
                                task.selected_colortype_in_active_group = ""

                        reset_count += 1
                        print(f"[OK] RESET: Tarea {task_id} restaurada con ColorType '{predefined_type}' del grupo '{original_group}'")
                    else:
                        pass

                # 3. If task uses DEFAULT, maintain current configuration
                elif not original_group or original_group == "DEFAULT":
                    pass
                    # No hacer cambios para tareas que usan DEFAULT

            except Exception as e:
                print(f"[ERROR] RESET: Error procesando tarea {task_id}: {e}")

        print(f"[OK] RESET COMPLETADO: {reset_count} tareas restauradas a sus grupos personalizados originales")

    except Exception as e:
        # Fallback to previous behavior only if there's a critical error
        cls._legacy_load_default_colors()

@classmethod
def _legacy_load_default_colors(cls):
    """Legacy method as fallback in case of error"""
    def _to_rgba(col):
        try:
            if isinstance(col, (list, tuple)):
                if len(col) >= 4:
                    return (float(col[0]), float(col[1]), float(col[2]), float(col[3]))
                if len(col) == 3:
                    return (float(col[0]), float(col[1]), float(col[2]), 1.0)
        except Exception:
            pass
        return (1.0, 0.0, 0.0, 1.0)

    groups = {
        "CREATION": {"PredefinedType": ["CONSTRUCTION", "INSTALLATION"], "Color": (0.0, 1.0, 0.0)},
        "OPERATION": {"PredefinedType": ["ATTENDANCE", "MAINTENANCE", "OPERATION", "RENOVATION"], "Color": (0.0, 0.0, 1.0)},
        "MOVEMENT_TO": {"PredefinedType": ["LOGISTIC", "MOVE"], "Color": (1.0, 1.0, 0.0)},
        "DESTRUCTION": {"PredefinedType": ["DEMOLITION", "DISMANTLE", "DISPOSAL", "REMOVAL"], "Color": (1.0, 0.0, 0.0)},
        "MOVEMENT_FROM": {"PredefinedType": ["LOGISTIC", "MOVE"], "Color": (1.0, 0.5, 0.0)},
        "USERDEFINED": {"PredefinedType": ["USERDEFINED", "NOTDEFINED"], "Color": (0.2, 0.2, 0.2)},
    }

    props = cls.get_animation_props()
    props.task_output_colors.clear()
    props.task_input_colors.clear()

    for group, data in groups.items():
        for predefined_type in data["PredefinedType"]:
            if group in ["CREATION", "OPERATION", "MOVEMENT_TO"]:
                item = props.task_output_colors.add()
            elif group in ["MOVEMENT_FROM"]:
                item = props.task_input_colors.add()
            elif group in ["USERDEFINED", "DESTRUCTION"]:
                item = props.task_input_colors.add()
                item2 = props.task_output_colors.add()
                item2.name = predefined_type
                item2.color = _to_rgba(data["Color"])
            item.name = predefined_type
            item.color = _to_rgba(data["Color"])


@classmethod
def create_default_ColorType_group(cls):
        """
        Automatically creates the DEFAULT group with profiles for each PredefinedType.
        This group is used when the user has not configured any profiles.
        """
        import json
        scene = bpy.context.scene
        key = "BIM_AnimationColorSchemesSets"
        raw = scene.get(key, "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else {}
        except Exception:
            data = {}
        if "DEFAULT" not in data:
            default_ColorTypes = {
                # Green Group (Construction)
                "CONSTRUCTION": {"start": [1, 1, 1, 0], "active": [0, 1, 0, 1], "end": [0.3, 1, 0.3, 1]},
                "INSTALLATION": {"start": [1, 1, 1, 0], "active": [0, 1, 0, 1], "end": [0.3, 0.8, 0.5, 1]},

                # Red Group (Demolition)
                "DEMOLITION": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
                "REMOVAL": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
                "DISPOSAL": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
                "DISMANTLE": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},

                # Blue Group (Operation / Maintenance)
                "OPERATION": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
                "MAINTENANCE": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
                "ATTENDANCE": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
                "RENOVATION": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [0.9, 0.9, 0.9, 1]},

                # Yellow Group (Logistics)
                "LOGISTIC": {"start": [1, 1, 1, 1], "active": [1, 1, 0, 1], "end": [1, 0.8, 0.3, 1]},
                "MOVE": {"start": [1, 1, 1, 1], "active": [1, 1, 0, 1], "end": [0.8, 0.6, 0, 1]},
                
                # Gray Group (Undefined / Others)
                "NOTDEFINED": {"start": [0.7, 0.7, 0.7, 1], "active": [0.5, 0.5, 0.5, 1], "end": [0.3, 0.3, 0.3, 1]},
                "USERDEFINED": {"start": [0.7, 0.7, 0.7, 1], "active": [0.5, 0.5, 0.5, 1], "end": [0.3, 0.3, 0.3, 1]}
            }
            ColorTypes = []
            for name, colors in default_ColorTypes.items():
                disappears = name in ["DEMOLITION", "REMOVAL", "DISPOSAL", "DISMANTLE"]
                ColorTypes.append({
                    "name": name,
                    "consider_start": False,  # DEFAULT: Objects should NOT appear at start (v110 behavior)
                    "consider_active": True,
                    "consider_end": True,
                    "start_color": colors["start"],
                    "in_progress_color": colors["active"],
                    "end_color": colors["end"],
                    "use_start_original_color": False,
                    "use_active_original_color": False,
                    "use_end_original_color": not disappears,
                    "start_transparency": 0.0,
                    "active_start_transparency": 0.0,
                    "active_finish_transparency": 0.0,
                    "active_transparency_interpol": 1.0,
                    "end_transparency": 0.0
                })
            data["DEFAULT"] = {"ColorTypes": ColorTypes}
            scene[key] = json.dumps(data)

@classmethod
def get_assigned_ColorType_for_task(cls, task: ifcopenshell.entity_instance, animation_props, active_group_name: Optional[str] = None):
    """Gets the profile for a task GIVEN a specific active group."""
    # Resolve active group if not provided
    if not active_group_name:
        try:
            ag = None
            for it in getattr(animation_props, 'animation_group_stack', []):
                if getattr(it, 'enabled', False) and getattr(it, 'group', None):
                    ag = it.group
                    break
            if not ag:
                ag = getattr(animation_props, 'ColorType_groups', None)
            active_group_name = ag or "DEFAULT"
        except Exception:
            active_group_name = "DEFAULT"

    # Debug info when DEFAULT is active
    if active_group_name == "DEFAULT":
        task_id_str = str(task.id()) if task is not None else "None"
        print(f"🎯 DEBUG: DEFAULT group is active for task {task_id_str} (PredefinedType: {getattr(task, 'PredefinedType', 'NOTDEFINED') if task is not None else 'NOTDEFINED'})")

    # Get task configuration from the persistent cache instead of the UI list.
    # This makes the function independent of the current UI filters.
    import bpy, json
    context = bpy.context
    task_id_str = str(task.id()) if task is not None else "None"
    task_config = None
    
    try:
        cache_key = "_task_colortype_snapshot_cache_json"
        cache_raw = context.scene.get(cache_key)
        if cache_raw:
            cached_data = json.loads(cache_raw)
            task_config = cached_data.get(task_id_str)
    except Exception as e:
        print(f"Bonsai WARNING: Could not read task config cache: {e}")
        task_config = None

    # 1) Specific assignment by group in the task
    if task_config:
        for choice in task_config.get("groups", []):
            is_enabled = choice.get("enabled", False)
            group_name = choice.get("group_name")
            selected_value = choice.get("selected_value") or choice.get("selected_colortype")
            if group_name == active_group_name and is_enabled and selected_value:
                ColorType = cls.load_ColorType_from_group(active_group_name, selected_value)
                if ColorType:
                    return ColorType

    task_predefined_type = getattr(task, "PredefinedType", "NOTDEFINED") if task is not None else "NOTDEFINED"

    # 2) PredefinedType in active group
    ColorType = cls.load_ColorType_from_group(active_group_name, task_predefined_type)
    if ColorType:
        return ColorType

    # 3) If no profile found and active group is not DEFAULT, try DEFAULT group
    if active_group_name != "DEFAULT":
        default_profile = cls.load_ColorType_from_group("DEFAULT", task_predefined_type)
        if default_profile:
            return default_profile

        # Try NOTDEFINED in DEFAULT as fallback
        notdefined_profile = cls.load_ColorType_from_group("DEFAULT", "NOTDEFINED")
        if notdefined_profile:
            return notdefined_profile

    # 4) If active group IS DEFAULT, ensure we try NOTDEFINED profile in DEFAULT
    elif active_group_name == "DEFAULT":
        notdefined_profile = cls.load_ColorType_from_group("DEFAULT", "NOTDEFINED")
        if notdefined_profile:
            return notdefined_profile

    # 5) Final fallback: create a basic ColorType only if DEFAULT group has no profiles
    task_id_for_warning = task.id() if task is not None else "None"
    print(f"[WARNING]️ WARNING: No ColorType found for task {task_id_for_warning} (PredefinedType: {task_predefined_type}) in group '{active_group_name}' - using fallback")
    return cls.create_fallback_ColorType(task_predefined_type)


@classmethod
def load_ColorType_from_group(cls, group_name, ColorType_name):
    import bpy, json
    scene = bpy.context.scene
    raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        data = {}

    # Debug: Show full DEFAULT group data
    if group_name == "DEFAULT":
        print(f"[CHECK] DEBUG: Raw scene data for BIM_AnimationColorSchemesSets:")
        print(f"    Raw type: {type(raw)}")
        print(f"    Raw content: {raw[:200] if isinstance(raw, str) else str(raw)[:200]}...")
        print(f"    Parsed data keys: {list(data.keys())}")
        if "DEFAULT" in data:
            print(f"    DEFAULT group structure: {data['DEFAULT']}")

    group_data = data.get(group_name, {})
    available_types = [prof.get("name") for prof in group_data.get("ColorTypes", [])]

    # Debug info for DEFAULT group specifically
    if group_name == "DEFAULT":
        print(f"[CHECK] DEBUG: Loading ColorType '{ColorType_name}' from DEFAULT group")
        print(f"    Available ColorTypes in DEFAULT: {available_types}")
        print(f"    Group data has {len(group_data.get('ColorTypes', []))} ColorTypes")

        # Show color details for each ColorType in DEFAULT
        for prof in group_data.get("ColorTypes", []):
            if prof.get("name") == ColorType_name:
                print(f"    🎨 ColorType '{ColorType_name}' colors:")
                print(f"        start_color: {prof.get('start_color', 'N/A')}")
                print(f"        in_progress_color: {prof.get('in_progress_color', 'N/A')}")
                print(f"        end_color: {prof.get('end_color', 'N/A')}")

                # AUTO-FIX: Detect problematic green/gray colors and force recreation
                in_progress = prof.get('in_progress_color', [])
                end_color = prof.get('end_color', [])

                if (in_progress == [0, 1, 0, 1] and end_color == [0.7, 0.7, 0.7, 1]):
                    print(f"🚨 DETECTED OLD GREEN/GRAY COLORS in '{ColorType_name}' - FORCING RECREATION!")
                    cls.force_recreate_default_group()
                    return cls.load_ColorType_from_group(group_name, ColorType_name)  # Retry with new data

    for prof_data in group_data.get("ColorTypes", []):
        if prof_data.get("name") == ColorType_name:
            if group_name == "DEFAULT":
                print(f"[OK] DEBUG: Found ColorType '{ColorType_name}' in DEFAULT group")
            return type('AnimationColorSchemes', (object,), {
                'name': prof_data.get("name", ""),
                'consider_start': prof_data.get("consider_start", True),
                'consider_active': prof_data.get("consider_active", True),
                'consider_end': prof_data.get("consider_end", True),
                'start_color': prof_data.get("start_color", [1,1,1,1]),
                'in_progress_color': prof_data.get("in_progress_color", [1,1,0,1]),
                'end_color': prof_data.get("end_color", [0,1,0,1]),
                'use_start_original_color': prof_data.get("use_start_original_color", False),
                'use_active_original_color': prof_data.get("use_active_original_color", False),
                'use_end_original_color': prof_data.get("use_end_original_color", True),
                'start_transparency': prof_data.get("start_transparency", 0.0),
                'active_start_transparency': prof_data.get("active_start_transparency", 0.0),
                'active_finish_transparency': prof_data.get("active_finish_transparency", 0.0),
                'active_transparency_interpol': prof_data.get("active_transparency_interpol", 1.0),
                'end_transparency': prof_data.get("end_transparency", 0.0),
                'hide_at_end': bool(prof_data.get("hide_at_end", prof_data.get("name") in {"DEMOLITION","REMOVAL","DISPOSAL","DISMANTLE"})),
            })()

    # Debug when ColorType not found in DEFAULT group
    if group_name == "DEFAULT":
        print(f"[ERROR] DEBUG: ColorType '{ColorType_name}' NOT found in DEFAULT group")

    return None

@classmethod
def force_recreate_default_group(cls):
    """Force recreation of DEFAULT group with correct colors"""
    import bpy, json
    scene = bpy.context.scene
    key = "BIM_AnimationColorSchemesSets"

    # Cargar datos existentes
    raw = scene.get(key, "{}")
    try:
        data = json.loads(raw) if isinstance(raw, str) else {}
    except Exception:
        data = {}

    print("[PROCESS] FORCE RECREATING DEFAULT group with distinctive colors...")

    # LISTA COMPLETA de ColorTypes para el grupo DEFAULT (14 tipos)
    default_ColorTypes = {
        # Green Group (Construction)
        "CONSTRUCTION": {"start": [1, 1, 1, 0], "active": [0, 1, 0, 1], "end": [0.3, 1, 0.3, 1]},
        "INSTALLATION": {"start": [1, 1, 1, 0], "active": [0, 1, 0, 1], "end": [0.3, 0.8, 0.5, 1]},

        # Red Group (Demolition)
        "DEMOLITION": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0]},
        "REMOVAL": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0]},
        "DISPOSAL": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0]},
        "DISMANTLE": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0]},

        # Blue Group (Operation / Maintenance)
        "OPERATION": {"start": [1, 1, 1, 0], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
        "MAINTENANCE": {"start": [1, 1, 1, 0], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
        "ATTENDANCE": {"start": [1, 1, 1, 0], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
        "RENOVATION": {"start": [1, 1, 1, 0], "active": [0, 0, 1, 1], "end": [0.9, 0.9, 0.9, 1]},

        # Yellow Group (Logistics)
        "LOGISTIC": {"start": [1, 1, 1, 0], "active": [1, 1, 0, 1], "end": [1, 0.8, 0.3, 1]},
        "MOVE": {"start": [1, 1, 1, 0], "active": [1, 1, 0, 1], "end": [0.8, 0.6, 0, 1]},

        # Gray Group (Undefined / Others)
        "NOTDEFINED": {"start": [1, 1, 1, 0], "active": [0.5, 0.5, 0.5, 1], "end": [0.7, 0.7, 0.7, 1]},
        "USERDEFINED": {"start": [1, 1, 1, 0], "active": [0.5, 0.5, 0.5, 1], "end": [0.7, 0.7, 0.7, 1]},
    }

    ColorTypes = []
    for name, colors in default_ColorTypes.items():
        disappears = name in ["DEMOLITION", "REMOVAL", "DISPOSAL", "DISMANTLE"]
        ColorTypes.append({
            "name": name,
            "consider_start": False,  # DEFAULT: Los objetos NO deben aparecer al inicio
            "consider_active": True,
            "consider_end": True,
            "start_color": colors["start"],
            "in_progress_color": colors["active"],
            "end_color": colors["end"],
            "use_start_original_color": False,
            "use_active_original_color": False,
            "use_end_original_color": not disappears,
            "start_transparency": 0.0,
            "active_start_transparency": 0.0,
            "active_finish_transparency": 0.0,
            "active_transparency_interpol": 1.0,
            "end_transparency": 0.0,
            "hide_at_end": disappears
        })

    # Sobrescribir el grupo DEFAULT
    data["DEFAULT"] = {"ColorTypes": ColorTypes}
    scene[key] = json.dumps(data)

    print(f"[OK] FORCE RECREATED DEFAULT group with {len(ColorTypes)} distinctive ColorTypes")

    # Debug: Mostrar los nuevos colores
    for ct in ColorTypes[:3]:  # Solo mostrar los primeros 3
        print(f"   {ct['name']}: start={ct['start_color']}, active={ct['in_progress_color']}, end={ct['end_color']}")


@classmethod
def create_fallback_ColorType(cls, predefined_type):
    """Creates a fallback ColorType when none is found in any group"""
    # Use the original default color scheme based on PredefinedType
    color_map = {
        "CONSTRUCTION": (0.0, 1.0, 0.0, 1.0),     # Green for construction
        "INSTALLATION": (0.0, 1.0, 0.0, 1.0),     # Green for installation
        "DEMOLITION": (1.0, 0.0, 0.0, 1.0),       # Red for demolition
        "REMOVAL": (1.0, 0.0, 0.0, 1.0),          # Red for removal
        "DISPOSAL": (1.0, 0.0, 0.0, 1.0),         # Red for disposal
        "DISMANTLE": (1.0, 0.0, 0.0, 1.0),        # Red for dismantle
        "LOGISTIC": (1.0, 1.0, 0.0, 1.0),         # Yellow for logistic
        "MOVE": (1.0, 1.0, 0.0, 1.0),             # Yellow for move
        "MAINTENANCE": (0.0, 0.0, 1.0, 1.0),      # Blue for maintenance
        "OPERATION": (0.0, 0.0, 1.0, 1.0),        # Blue for operation
        "RENOVATION": (0.0, 0.0, 1.0, 1.0),       # Blue for renovation
        "ATTENDANCE": (0.0, 0.0, 1.0, 1.0),       # Blue for attendance
    }

    # Default colors for unknown types
    start_color = color_map.get(predefined_type, (0.8, 0.8, 0.8, 1.0))  # Light gray default
    in_progress_color = color_map.get(predefined_type, (1.0, 1.0, 0.0, 1.0))  # Yellow default
    end_color = color_map.get(predefined_type, (0.0, 1.0, 0.0, 1.0))     # Green default

    return type('FallbackColorType', (object,), {
        'name': predefined_type,
        'consider_start': True,
        'consider_active': True,
        'consider_end': True,
        'start_color': start_color,
        'in_progress_color': in_progress_color,
        'end_color': end_color,
        'use_start_original_color': False,
        'use_active_original_color': False,
        'use_end_original_color': False,
        'start_transparency': 0.0,
        'active_start_transparency': 0.0,
        'active_finish_transparency': 0.0,
        'active_transparency_interpol': 1.0,
        'end_transparency': 0.0,
        'hide_at_end': predefined_type in {"DEMOLITION", "REMOVAL", "DISPOSAL", "DISMANTLE"},
    })()


@classmethod
def sync_active_group_to_json(cls):
    """Sincroniza los perfiles del grupo activo de la UI al JSON de la escena"""
    import bpy, json
    scene = bpy.context.scene
    anim_props = cls.get_animation_props()
    active_group = getattr(anim_props, "ColorType_groups", None)
    if not active_group:
        return

    if active_group == "DEFAULT":
        
        print("[PROCESS] RECREATING DEFAULT group with correct colors...")
        cls.force_recreate_default_group()
  
    raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        data = {}
    ColorTypes_data = []
    for ColorType in getattr(anim_props, "ColorTypes", []):
        try:
            ColorTypes_data.append({
                "name": ColorType.name,
                "consider_start": bool(getattr(ColorType, "consider_start", False)),
                "consider_active": bool(getattr(ColorType, "consider_active", True)),
                "consider_end": bool(getattr(ColorType, "consider_end", True)),
                "start_color": list(getattr(ColorType, "start_color", [1,1,1,1])),
                "in_progress_color": list(getattr(ColorType, "in_progress_color", [1,1,0,1])),
                "end_color": list(getattr(ColorType, "end_color", [0,1,0,1])),
                "use_start_original_color": bool(getattr(ColorType, "use_start_original_color", False)),
                "use_active_original_color": bool(getattr(ColorType, "use_active_original_color", False)),
                "use_end_original_color": bool(getattr(ColorType, "use_end_original_color", True)),
                "start_transparency": float(getattr(ColorType, "start_transparency", 0.0)),
                "active_start_transparency": float(getattr(ColorType, "active_start_transparency", 0.0)),
                "active_finish_transparency": float(getattr(ColorType, "active_finish_transparency", 0.0)),
                "active_transparency_interpol": float(getattr(ColorType, "active_transparency_interpol", 1.0)),
                "end_transparency": float(getattr(ColorType, "end_transparency", 0.0)),
                "hide_at_end": bool(getattr(ColorType, "hide_at_end", getattr(ColorType, "name", "") in {"DEMOLITION","REMOVAL","DISPOSAL","DISMANTLE"})),
            })
        except Exception:
            pass
    data[active_group] = {"ColorTypes": ColorTypes_data}
    scene["BIM_AnimationColorSchemesSets"] = json.dumps(data)





