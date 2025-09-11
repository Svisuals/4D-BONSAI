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
import json
import ifcopenshell

from .props_sequence import PropsSequence
import bonsai.tool as tool

# Importación segura para la gestión de grupos de colores
try:
    from ...prop.color_manager_prop import UnifiedColorTypeManager
except ImportError:
    class UnifiedColorTypeManager:
        @staticmethod
        def _read_sets_json(context): return {}
        @staticmethod
        def _write_sets_json(context, data): pass

class ConfigSequence(PropsSequence):
    """Maneja la importación, exportación y sincronización de configuraciones del cronograma."""

    @classmethod
    def export_schedule_configuration(cls, work_schedule):
        """
        Gathers all relevant configuration from a work schedule and returns it as a dictionary.
        This includes task assignments (ICOM), ColorType libraries, and ColorType assignments.
        """
        ifc_file = tool.Ifc.get()
        context = bpy.context

        # 1. Get all tasks from the schedule from the IFC data to ensure completeness
        def get_all_tasks_recursive(tasks):
            all_tasks_list = []
            for task in tasks:
                all_tasks_list.append(task)
                nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                if nested_tasks:
                    all_tasks_list.extend(get_all_tasks_recursive(nested_tasks))
            return all_tasks_list

        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
        all_tasks_in_schedule = get_all_tasks_recursive(root_tasks)
        if not all_tasks_in_schedule:
            return {}

        # 2. Get ColorType assignments from the UI snapshot created by the operator.
        task_ColorType_snapshot = {}
        
        # First try schedule-specific snapshot key
        specific_snapshot_key = f"_task_colortype_snapshot_json_WS_{work_schedule.id()}"
        generic_snapshot_key = "_task_colortype_snapshot_json"
        
        snapshot_found = False
        if context.scene.get(specific_snapshot_key):
            try:
                task_ColorType_snapshot = json.loads(context.scene[specific_snapshot_key])
                print(f"✅ DEBUG EXPORT: Cargados {len(task_ColorType_snapshot)} perfiles desde clave específica WS_{work_schedule.id()}")
                snapshot_found = True
            except Exception as e:
                print(f"❌ DEBUG EXPORT: Error cargando perfiles desde clave específica: {e}")
        
        # Fallback to generic snapshot key if specific not found
        if not snapshot_found and context.scene.get(generic_snapshot_key):
            try:
                task_ColorType_snapshot = json.loads(context.scene[generic_snapshot_key])
                print(f"✅ DEBUG EXPORT: Cargados {len(task_ColorType_snapshot)} perfiles desde clave genérica (fallback)")
            except Exception as e:
                print(f"❌ DEBUG EXPORT: Error cargando perfiles desde clave genérica: {e}")
        
        if not snapshot_found and not context.scene.get(generic_snapshot_key):
            print("❌ DEBUG EXPORT: No se encontraron datos de perfiles en ninguna clave")
        
        # Clean problematic values before processing
        if task_ColorType_snapshot:
            task_ColorType_snapshot = cls._clean_ColorType_snapshot_data(task_ColorType_snapshot)

        # 3. Export ColorType Groups library from the scene property
        ColorType_groups_data = {}
        try:
            ColorType_groups_data = UnifiedColorTypeManager._read_sets_json(bpy.context)
        except Exception as e:
            print(f"Could not export ColorType groups: {e}")

        # 4. Export task-specific configurations
        task_configs = []
        for task in all_tasks_in_schedule:
            task_identification = getattr(task, "Identification", None)
            if not task_identification:
                print(f"Bonsai WARNING: Skipping task {task.id()} from config export as it has no 'Identification' attribute.")
                continue

            task_id_str = str(task.id())
            
            task_config = {
                "task_identification": task_identification,
                "predefined_type": getattr(task, "PredefinedType", None),
            }

            # ICOM Data (using GlobalId for stable mapping)
            inputs = ifcopenshell.util.sequence.get_task_inputs(task, is_deep=False)
            outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
            resources = ifcopenshell.util.sequence.get_task_resources(task, is_deep=False)
            task_config["inputs"] = [p.GlobalId for p in inputs if hasattr(p, 'GlobalId')]
            task_config["outputs"] = [p.GlobalId for p in outputs if hasattr(p, 'GlobalId')]
            task_config["resources"] = [r.GlobalId for r in resources if hasattr(r, 'GlobalId')]

            # ColorType Assignments from the snapshot (ALWAYS include, even if empty)
            ColorType_assignments = {
                "use_active_ColorType_group": False,
                "selected_ColorType_in_active_group": "",
                "animation_color_schemes": "",
                "choices": [],
            }
            
            # If task has configured ColorTypes, use them; otherwise use empty defaults
            if task_id_str in task_ColorType_snapshot:
                snap_data = task_ColorType_snapshot[task_id_str]
                choices = []
                for g_data in snap_data.get("groups", []):
                    # Buscar el valor del ColorType usando todas las claves posibles
                    colortype_value = (
                        g_data.get("selected_ColorType") or 
                        g_data.get("selected_value") or 
                        g_data.get("selected_colortype") or
                        ""
                    )
                    choices.append({
                        "group_name": g_data.get("group_name", ""),
                        "enabled": g_data.get("enabled", False),
                        "selected_ColorType": colortype_value,
                    })
                    
                    # DEBUG: Mostrar qué se está capturando
                    print(f"📤 DEBUG EXPORT: Group '{g_data.get('group_name')}' - enabled={g_data.get('enabled')}, colortype='{colortype_value}'")
                
                ColorType_assignments = {
                    "use_active_ColorType_group": snap_data.get("active", False),
                    "selected_ColorType_in_active_group": snap_data.get("selected_active_ColorType", ""),
                    "animation_color_schemes": snap_data.get("animation_color_schemes", ""),
                    "choices": choices,
                }
            else:
                # Task has no configured ColorTypes - export empty but valid structure
                # Get all available ColorType groups and create empty entries
                try:
    # UnifiedColorTypeManager is already imported at module level
                    available_groups = UnifiedColorTypeManager._read_sets_json(bpy.context) or {}
                    choices = []
                    for group_name in available_groups.keys():
                        choices.append({
                            "group_name": group_name,
                            "enabled": False,  # Not configured yet
                            "selected_ColorType": "",  # No ColorType selected yet
                        })
                    ColorType_assignments["choices"] = choices
                except Exception as e:
                    print(f"Warning: Could not load ColorType groups for unconfigured task {task_identification}: {e}")
            
            task_config["ColorType_assignments"] = ColorType_assignments
            task_configs.append(task_config)

        # 5. Assemble final JSON
        anim_props = cls.get_animation_props()
        export_data = {
            "version": "1.3",
            "schedule_name": work_schedule.Name,
            "ColorType_groups": ColorType_groups_data,
            "ui_settings": {
                "task_ColorType_group_selector": getattr(anim_props, "task_ColorType_group_selector", ""),
                "animation_group_stack": [
                    {"group": getattr(item, "group", ""), "enabled": bool(getattr(item, "enabled", False))}
                    for item in getattr(anim_props, "animation_group_stack", [])
                ]
            },
            "task_configurations": task_configs,
        }
        return export_data


    @classmethod
    def import_schedule_configuration(cls, data):
        """
        Applies a saved schedule configuration from a dictionary to the current IFC file.
        This function is non-destructive to the UI state.
        """
        ifc_file = tool.Ifc.get()
        work_schedule = cls.get_active_work_schedule()
        if not work_schedule:
            print("Import failed: No active work schedule.")
            return

        # 1. Import data and modify IFC
        if "ColorType_groups" in data:
            UnifiedColorTypeManager._write_sets_json(bpy.context, data["ColorType_groups"])

        if "ui_settings" in data:
            anim_props = cls.get_animation_props()
            anim_props.task_ColorType_group_selector = data["ui_settings"].get("task_ColorType_group_selector", "")
            
            # Import animation group stack
            if "animation_group_stack" in data["ui_settings"]:
                anim_props.animation_group_stack.clear()
                for item_data in data["ui_settings"]["animation_group_stack"]:
                    item = anim_props.animation_group_stack.add()
                    item.group = item_data.get("group", "")
                    if hasattr(item, "enabled"):
                        item.enabled = bool(item_data.get("enabled", False))

        guid_map = {p.GlobalId: p.id() for p in ifc_file.by_type("IfcProduct") if hasattr(p, 'GlobalId')}
        guid_map.update({r.GlobalId: r.id() for r in ifc_file.by_type("IfcResource") if hasattr(r, 'GlobalId')})

        # Create a map from Identification to task entity for the current file
        task_identification_map = {t.Identification: t for t in ifc_file.by_type("IfcTask") if getattr(t, 'Identification', None)}

        ColorType_assignments_to_restore = {}
        if "task_configurations" in data:
            for task_config in data["task_configurations"]:
                task_identification = task_config.get("task_identification")
                if not task_identification:
                    continue
                
                task = task_identification_map.get(task_identification)
                if not task: 
                    print(f"Bonsai WARNING: Task with Identification '{task_identification}' not found in current IFC file. Skipping.")
                    continue

                ifcopenshell.api.run("sequence.edit_task", ifc_file, task=task, attributes={"PredefinedType": task_config.get("predefined_type")})

                for product in ifcopenshell.util.sequence.get_task_outputs(task):
                    ifcopenshell.api.run("sequence.unassign_product", ifc_file, relating_product=product, related_object=task)
                for product_input in ifcopenshell.util.sequence.get_task_inputs(task):
                    ifcopenshell.api.run("sequence.unassign_process", ifc_file, relating_process=task, related_object=product_input)
                for resource in ifcopenshell.util.sequence.get_task_resources(task):
                    ifcopenshell.api.run("sequence.unassign_process", ifc_file, relating_process=task, related_object=resource)

                input_ids = [guid_map[guid] for guid in task_config.get("inputs", []) if guid in guid_map]
                output_ids = [guid_map[guid] for guid in task_config.get("outputs", []) if guid in guid_map]
                resource_ids = [guid_map[guid] for guid in task_config.get("resources", []) if guid in guid_map]

                if input_ids: ifcopenshell.api.run("sequence.assign_process", ifc_file, relating_process=task, products=[ifc_file.by_id(i) for i in input_ids])
                if output_ids:
                    for product_id in output_ids: ifcopenshell.api.run("sequence.assign_product", ifc_file, relating_product=ifc_file.by_id(product_id), related_object=task)
                if resource_ids: ifcopenshell.api.run("sequence.assign_process", ifc_file, relating_process=task, resources=[ifc_file.by_id(i) for i in resource_ids])
                
                if "ColorType_assignments" in task_config:
                    # Translate from the JSON file structure to the internal snapshot format
                    # that restore_all_ui_state() expects.
                    pa = task_config["ColorType_assignments"]
                    groups_to_restore = []
                    for choice in pa.get("choices", []):
                        groups_to_restore.append({
                            "group_name": choice.get("group_name"),
                            "enabled": choice.get("enabled"),
                            "selected_value": choice.get("selected_ColorType"), # Map key
                        })
                    translated_pa = {
                        "active": pa.get("use_active_ColorType_group"), # Map key
                        "selected_active_ColorType": pa.get("selected_ColorType_in_active_group"), # Map key
                        "animation_color_schemes": pa.get("animation_color_schemes", ""), # MISSING: Main ColorType field
                        "groups": groups_to_restore # Map key
                    }
                    ColorType_assignments_to_restore[str(task.id())] = translated_pa

        # 2. Store the ColorType data in a temporary property.
        # The restore_all_ui_state function (called by the operator) will use this
        # to apply the ColorType data after the UI has been reloaded.
        if ColorType_assignments_to_restore:
            snap_key_specific = f"_task_colortype_snapshot_json_WS_{work_schedule.id()}"
            bpy.context.scene[snap_key_specific] = json.dumps(ColorType_assignments_to_restore)
            print(f"Bonsai INFO: Stored {len(ColorType_assignments_to_restore)} ColorType assignments for restore under key {snap_key_specific}")


    @classmethod
    def _clean_and_update_ColorType_snapshot_for_schedule(cls, work_schedule):
        """
        Limpia específicamente los datos de perfiles corruptos del cronograma dado
        y actualiza el snapshot para evitar restaurar valores '0' problemáticos.
        """
        try:
            import json
            
            # Obtener la clave específica del cronograma
            ws_id = work_schedule.id()
            snapshot_key_specific = f"_task_colortype_snapshot_json_WS_{ws_id}"
            
            # Leer datos actuales del snapshot
            snapshot_raw = bpy.context.scene.get(snapshot_key_specific)
            if not snapshot_raw:
                print(f"🧹 Sync3D: No hay snapshot para limpiar en cronograma {ws_id}")
                return
            
            try:
                snapshot_data = json.loads(snapshot_raw)
                print(f"🧹 Sync3D: Limpiando {len(snapshot_data)} tareas en snapshot")
            except Exception as e:
                print(f"❌ Sync3D: Error parseando snapshot: {e}")
                return
            
            # Limpiar datos usando la función existente
            cleaned_data = cls._clean_ColorType_snapshot_data(snapshot_data)
            
            # Actualizar el snapshot con datos limpios
            bpy.context.scene[snapshot_key_specific] = json.dumps(cleaned_data)
            print(f"✅ Sync3D: Datos de perfiles limpiados en cronograma {ws_id}")
            
        except Exception as e:
            print(f"❌ Sync3D: Error en limpieza de perfiles: {e}")


    @classmethod
    def _clean_ColorType_snapshot_data(cls, snapshot_data):
        """
        Clean ColorType snapshot data by removing invalid enum values and ensuring data consistency.
        """
        if not isinstance(snapshot_data, dict):
            return {}
        
        cleaned_data = {}
        for task_id, task_data in snapshot_data.items():
            if not isinstance(task_data, dict):
                continue
                
            cleaned_task_data = {
                "active": bool(task_data.get("active", False)),
                "selected_active_ColorType": "",  # Always reset problematic values
                "groups": []
            }
            
            # Clean selected_active_ColorType - remove '0' and other invalid values
            selected_active = task_data.get("selected_active_ColorType", "")
            # Be more aggressive in cleaning problematic values
            problematic_values = ["0", 0, None, "", "None", "null", "undefined"]
            if selected_active and selected_active not in problematic_values:
                # Additional check: ensure it's a meaningful string
                selected_active_str = str(selected_active).strip()
                if selected_active_str and selected_active_str not in [str(v) for v in problematic_values]:
                    cleaned_task_data["selected_active_ColorType"] = selected_active_str
            
            # Clean groups data
            for group_data in task_data.get("groups", []):
                if isinstance(group_data, dict) and group_data.get("group_name"):
                    selected_value = group_data.get("selected_value", "")
                    # Clean selected_value - remove '0' and other invalid values
                    problematic_group_values = ["0", 0, None, "", "None", "null", "undefined"]
                    if selected_value in problematic_group_values:
                        selected_value = ""
                    else:
                        # Ensure it's a clean string
                        selected_value = str(selected_value).strip() if selected_value else ""
                        if selected_value in [str(v) for v in problematic_group_values]:
                            selected_value = ""
                    
                    cleaned_group = {
                        "group_name": str(group_data["group_name"]),
                        "enabled": bool(group_data.get("enabled", False)),
                        "selected_value": str(selected_value) if selected_value else ""
                    }
                    cleaned_task_data["groups"].append(cleaned_group)
            
            # Always store task data (even if no groups - represents unconfigured tasks)
            cleaned_data[task_id] = cleaned_task_data
        
        return cleaned_data


    


















