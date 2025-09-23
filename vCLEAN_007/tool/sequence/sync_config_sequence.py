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
import ifcopenshell
import ifcopenshell.util.sequence
import bonsai.tool as tool

# Importar otros mixins necesarios
from .schedule_management_sequence import ScheduleManagementSequence
from .task_tree_sequence import TaskTreeSequence

# Importar operadores para snapshot/restore
try:
    from ...operators.operator import snapshot_all_ui_state, restore_all_ui_state
except ImportError:
    def snapshot_all_ui_state(context): pass
    def restore_all_ui_state(context): pass

class SyncConfigSequence:
    """Mixin class for advanced Sync and Copy Configuration tools."""

    @classmethod
    def _force_complete_task_snapshot(cls, context, work_schedule):
        """
        Fuerza una captura completa de TODAS las tareas del cronograma especificado,
        no solo las visibles en la UI. Esto asegura que Copy3D capture configuraciones
        de todas las tareas, no solo las actualmente mostradas en el task tree.
        """
        import json
        try:
            print(f"🔄 Copy3D: Forcing complete task snapshot for schedule '{work_schedule.Name}'...")
            
            # Obtener todas las tareas del cronograma directamente del IFC
            def get_all_tasks_recursive(tasks):
                all_tasks = []
                for task in tasks:
                    all_tasks.append(task)
                    nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested:
                        all_tasks.extend(get_all_tasks_recursive(nested))
                return all_tasks
            
            root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
            all_schedule_tasks = get_all_tasks_recursive(root_tasks)
            
            print(f"🔄 Copy3D: Found {len(all_schedule_tasks)} total tasks in schedule")
            
            # Crear un snapshot manual de todas las tareas del cronograma
            # Esto se hace ANTES de snapshot_all_ui_state para poblar el caché
            
            # Obtener datos actuales del caché si existen
            cache_key = "_task_colortype_snapshot_cache_json"
            cache_raw = context.scene.get(cache_key, "{}")
            try:
                cache_data = json.loads(cache_raw) if cache_raw else {}
            except:
                cache_data = {}
            
            # Para cada tarea del cronograma, asegurar que tenga entrada en el caché
            tasks_added_to_cache = 0
            for task in all_schedule_tasks:
                tid = str(task.id())
                if tid == "0":
                    continue
                    
                # Si la tarea ya está en el caché, conservar sus datos actuales
                if tid in cache_data:
                    continue
                    
                # Si no está en caché, crear entrada por defecto
                # Esto permitirá que export_schedule_configuration la encuentre
                cache_data[tid] = {
                    "active": False,
                    "selected_active_colortype": "",
                    "animation_color_schemes": "",
                    "groups": [],
                }
                tasks_added_to_cache += 1
            
            # Actualizar el caché
            if tasks_added_to_cache > 0:
                context.scene[cache_key] = json.dumps(cache_data)
                print(f"🔄 Copy3D: Added {tasks_added_to_cache} uncached tasks to snapshot cache")
            
            print(f"[OK] Copy3D: Complete task snapshot forced - {len(cache_data)} tasks ready for export")
            
        except Exception as e:
            print(f"[ERROR] Copy3D: Error forcing complete task snapshot: {e}")

    @classmethod
    def _sync_source_animation_color_schemes(cls, context):
        """
        Sincroniza el campo animation_color_schemes en tareas que tienen grupo activo
        ANTES de hacer el snapshot. Esto asegura que Copy3D capture el valor correcto.
        """
        try:
            print(f"🔄 Copy3D: Syncing animation_color_schemes in source schedule...")
            
            tprops = tool.Sequence.get_task_tree_props()
            tasks_synced = 0
            
            for task in getattr(tprops, 'tasks', []):
                try:
                    # Solo procesar tareas que tienen grupo activo
                    if getattr(task, 'use_active_colortype_group', False):
                        current_animation_schemes = getattr(task, 'animation_color_schemes', '')
                        
                        # Encontrar el grupo activo y obtener su selected_colortype
                        selected_colortype = ''
                        
                        # Buscar en los grupos de la tarea directamente (más confiable)
                        group_choices = getattr(task, 'colortype_group_choices', [])
                        for choice in group_choices:
                            group_name = getattr(choice, 'group_name', '')
                            enabled = getattr(choice, 'enabled', False)
                            choice_colortype = getattr(choice, 'selected_colortype', '')
                            
                            # Encontrar el grupo activo (enabled=True) que no sea DEFAULT
                            if enabled and group_name != 'DEFAULT' and choice_colortype:
                                selected_colortype = choice_colortype
                                print(f"[CHECK] Copy3D SYNC: Task {task.ifc_definition_id} - Found active group '{group_name}' with colortype '{selected_colortype}'")
                                break
                        
                        # Si el grupo activo tiene un ColorType pero animation_color_schemes no coincide
                        if selected_colortype and selected_colortype != current_animation_schemes:
                            print(f"🔄 Copy3D SYNC: Task {task.ifc_definition_id} - '{current_animation_schemes}' -> '{selected_colortype}'")
                            
                            # Usar la función segura para asignar
                            from ..prop import safe_set_animation_color_schemes
                            safe_set_animation_color_schemes(task, selected_colortype)
                            tasks_synced += 1
                        elif selected_colortype:
                            print(f"[OK] Copy3D SYNC: Task {task.ifc_definition_id} already synced: '{selected_colortype}'")
                        else:
                            print(f"[WARNING]️ Copy3D SYNC: Task {task.ifc_definition_id} has active group but no selected colortype")
                            
                except Exception as e:
                    print(f"[ERROR] Copy3D SYNC: Error syncing task {getattr(task, 'ifc_definition_id', '?')}: {e}")
                    continue
            
            print(f"[OK] Copy3D: Synced animation_color_schemes for {tasks_synced} tasks with active groups")
            
        except Exception as e:
            print(f"[ERROR] Copy3D: Error syncing source animation_color_schemes: {e}")

    @classmethod
    def _force_fresh_snapshot_from_ui(cls, context):
        """
        Fuerza un snapshot fresco basado en el estado actual de la UI,
        no en datos antiguos del caché. Esto asegura que Copy3D capture
        los valores reales de los dropdowns.
        """
        try:
            import json
            
            tprops = tool.Sequence.get_task_tree_props()
            if not tprops or not hasattr(tprops, 'tasks'):
                return
            
            # Obtener cronograma activo
            ws = cls.get_active_work_schedule()
            if not ws:
                return
            
            fresh_snapshot = {}
            
            for task in tprops.tasks:
                tid = str(getattr(task, 'ifc_definition_id', 0))
                if not tid or tid == '0':
                    continue
                
                # Capturar estado actual directamente de la UI
                use_active = getattr(task, 'use_active_colortype_group', False)
                selected_active = getattr(task, 'selected_colortype_in_active_group', '')
                animation_schemes = getattr(task, 'animation_color_schemes', '')
                
                # Capturar grupos directamente del estado UI actual
                groups_data = []
                group_choices = getattr(task, 'colortype_group_choices', [])
                for choice in group_choices:
                    group_name = getattr(choice, 'group_name', '')
                    enabled = getattr(choice, 'enabled', False)
                    selected_colortype = getattr(choice, 'selected_colortype', '')
                    
                    groups_data.append({
                        "group_name": group_name,
                        "enabled": enabled,
                        "selected_value": selected_colortype,  # Usar selected_value para consistencia
                    })
                    
                    # DEBUG: Mostrar qué se está capturando desde la UI
                    if group_name == 'Group 2' and enabled:
                        pass
                
                fresh_snapshot[tid] = {
                    "active": use_active,
                    "selected_active_colortype": selected_active,
                    "animation_color_schemes": animation_schemes,
                    "groups": groups_data,
                }
            
            # Sobrescribir el snapshot con los datos frescos
            snap_key = f"_task_colortype_snapshot_json_WS_{ws.id()}"
            context.scene[snap_key] = json.dumps(fresh_snapshot)
            
            print(f"[OK] Copy3D: Fresh snapshot created with {len(fresh_snapshot)} tasks from current UI state")
            
        except Exception as e:
            print(f"[ERROR] Copy3D: Error creating fresh snapshot: {e}")

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
                print(f"[OK] DEBUG EXPORT: Cargados {len(task_ColorType_snapshot)} perfiles desde clave específica WS_{work_schedule.id()}")
                snapshot_found = True
            except Exception as e:
                print(f"[ERROR] DEBUG EXPORT: Error cargando perfiles desde clave específica: {e}")
        
        # Fallback to generic snapshot key if specific not found
        if not snapshot_found and context.scene.get(generic_snapshot_key):
            try:
                task_ColorType_snapshot = json.loads(context.scene[generic_snapshot_key])
                print(f"[OK] DEBUG EXPORT: Cargados {len(task_ColorType_snapshot)} perfiles desde clave genérica (fallback)")
            except Exception as e:
                print(f"[ERROR] DEBUG EXPORT: Error cargando perfiles desde clave genérica: {e}")
        
        if not snapshot_found and not context.scene.get(generic_snapshot_key):
            print("[ERROR] DEBUG EXPORT: No se encontraron datos de perfiles en ninguna clave")
        
        # Clean problematic values before processing
        if task_ColorType_snapshot:
            task_ColorType_snapshot = cls._clean_ColorType_snapshot_data(task_ColorType_snapshot)

        # 3. Export ColorType Groups library from the scene property
        ColorType_groups_data = {}
        try:
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
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
                    from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
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
        anim_props = tool.Sequence.get_animation_props()
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
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
            UnifiedColorTypeManager._write_sets_json(bpy.context, data["ColorType_groups"])

        if "ui_settings" in data:
            anim_props = tool.Sequence.get_animation_props()
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
            # --- Usar la clave específica del cronograma para el snapshot ---
            snap_key_specific = f"_task_colortype_snapshot_json_WS_{work_schedule.id()}"
            bpy.context.scene[snap_key_specific] = json.dumps(ColorType_assignments_to_restore)
            print(f"Bonsai INFO: Stored {len(ColorType_assignments_to_restore)} ColorType assignments for restore under key {snap_key_specific}")

    @classmethod
    def _debug_copy3d_state(cls, stage, schedule_name="", task_count=0):
        """
        DEBUG: Internal testing function to verify Copy3D state at different stages
        """
        print(f"\n[CHECK] COPY3D DEBUG [{stage}] - Schedule: {schedule_name}, Tasks: {task_count}")
        
        try:
            tprops = tool.Sequence.get_task_tree_props()
            if not tprops or not hasattr(tprops, 'tasks'):
                print("[ERROR] No task properties available")
                return
                
            # Sample first 3 tasks for detailed inspection
            sample_tasks = list(tprops.tasks)[:3] if hasattr(tprops, 'tasks') else []
            
            for i, task in enumerate(sample_tasks):
                tid = getattr(task, 'ifc_definition_id', '?')
                name = getattr(task, 'name', 'Unnamed')[:30]
                
                # Core properties
                use_active = getattr(task, 'use_active_colortype_group', False)
                colortype_groups = getattr(task, 'ColorType_groups', '')
                animation_schemes = getattr(task, 'animation_color_schemes', '')
                selected_active = getattr(task, 'selected_colortype_in_active_group', '')
                
                # Group choices
                group_choices = getattr(task, 'colortype_group_choices', [])
                group_info = []
                for choice in group_choices:
                    enabled = getattr(choice, 'enabled', False)
                    group_name = getattr(choice, 'group_name', '')
                    selected_colortype = getattr(choice, 'selected_colortype', '')
                    group_info.append(f"{group_name}:{selected_colortype}({enabled})")
                
                print(f"  Task {tid} ({name}):")
                print(f"    use_active: {use_active}")
                print(f"    ColorType_groups: '{colortype_groups}'")
                print(f"    animation_color_schemes: '{animation_schemes}'")
                print(f"    selected_active: '{selected_active}'")
                print(f"    groups: [{', '.join(group_info)}]")
                
        except Exception as e:
            print(f"[ERROR] Debug state error: {e}")
        
        print(f"[CHECK] END COPY3D DEBUG [{stage}]\n")

    @classmethod
    def _test_copy3d_results(cls, copied_schedules, total_matches):
        """
        Comprehensive verification of Copy3D results
        """
        print(f"\n[TEST] COPY3D RESULT TEST: Verifying {copied_schedules} schedules with {total_matches} matches")
        
        try:
            # Check if active schedule has proper ColorType data
            tprops = tool.Sequence.get_task_tree_props()
            if not tprops or not hasattr(tprops, 'tasks'):
                print("[ERROR] TEST FAIL: No task properties available for verification")
                return False
            
            test_results = {
                "tasks_with_active_groups": 0,
                "tasks_with_animation_schemes": 0,
                "tasks_with_group_choices": 0,
                "tasks_with_empty_configs": 0,
                "total_tested": 0
            }
            
            # Sample testing on first 5 tasks
            sample_tasks = list(tprops.tasks)[:5] if hasattr(tprops, 'tasks') else []
            
            for task in sample_tasks:
                test_results["total_tested"] += 1
                tid = getattr(task, 'ifc_definition_id', '?')
                name = getattr(task, 'name', 'Unnamed')[:20]
                
                # Test properties
                use_active = getattr(task, 'use_active_colortype_group', False)
                animation_schemes = getattr(task, 'animation_color_schemes', '')
                group_choices = list(getattr(task, 'colortype_group_choices', []))
                
                # Count configurations
                if use_active:
                    test_results["tasks_with_active_groups"] += 1
                if animation_schemes:
                    test_results["tasks_with_animation_schemes"] += 1
                if group_choices:
                    test_results["tasks_with_group_choices"] += 1
                if not use_active and not animation_schemes and not group_choices:
                    test_results["tasks_with_empty_configs"] += 1
                
                # Detailed result for this task
                status = "[OK]" if (use_active or animation_schemes or group_choices) else "[ERROR]"
                print(f"  {status} Task {tid} ({name}): active={use_active}, schemes='{animation_schemes}', groups={len(group_choices)}")
            
            # Summary
            print(f"\n[TEST] TEST SUMMARY:")
            print(f"  Total tested: {test_results['total_tested']}")
            print(f"  With active groups: {test_results['tasks_with_active_groups']}")
            print(f"  With animation schemes: {test_results['tasks_with_animation_schemes']}")
            print(f"  With group choices: {test_results['tasks_with_group_choices']}")
            print(f"  Completely empty: {test_results['tasks_with_empty_configs']}")
            
            # Test outcome
            configured_tasks = (test_results['tasks_with_active_groups'] + 
                                test_results['tasks_with_animation_schemes'] + 
                                test_results['tasks_with_group_choices'])
            
            if configured_tasks > 0:
                success_rate = (configured_tasks / test_results['total_tested']) * 100
                print(f"[OK] COPY3D TEST RESULT: {success_rate:.1f}% tasks have ColorType configurations")
                return success_rate > 50  # At least half should be configured
            else:
                print(f"[ERROR] COPY3D TEST RESULT: NO tasks have ColorType configurations - Copy3D failed!")
                return False
                
        except Exception as e:
            print(f"[ERROR] COPY3D TEST ERROR: {e}")
            return False
    
    @classmethod
    def copy_3d_configuration(cls, source_schedule):
        """
        Copy configuration from source schedule to all other schedules with matching task indicators.
        Returns a dict with success status and copy statistics.
        """
        print(f"\n[OPTIMIZED] COPY3D TEST: Starting comprehensive Copy3D testing")
        cls._debug_copy3d_state("BEFORE_COPY3D_START", source_schedule.Name if source_schedule else "?", 0)
        
        try:
            print(f"[OPTIMIZED] Copy3D: Starting copy from schedule '{source_schedule.Name}' (ID: {source_schedule.id()})")
            
            ifc_file = tool.Ifc.get()
            if not ifc_file:
                return {"success": False, "error": "No IFC file loaded"}

            # Get source schedule configuration
            print("📤 Copy3D: Capturing source schedule configuration...")
            cls._debug_copy3d_state("BEFORE_FORCE_SNAPSHOT", source_schedule.Name, 0)
            
            # FORZAR captura completa de TODAS las tareas del cronograma, no solo las visibles
            cls._force_complete_task_snapshot(bpy.context, source_schedule)
            cls._debug_copy3d_state("AFTER_FORCE_SNAPSHOT", source_schedule.Name, 0)
            
            # SINCRONIZAR animation_color_schemes en tareas activas ANTES del snapshot
            cls._sync_source_animation_color_schemes(bpy.context)
            cls._debug_copy3d_state("AFTER_SYNC_SOURCE", source_schedule.Name, 0)
            
            # FORZAR snapshot FRESCO basado en el estado UI actual (no datos antiguos)
            print("🔄 Copy3D: Forcing fresh snapshot from current UI state...")
            cls._force_fresh_snapshot_from_ui(bpy.context)
            
            snapshot_all_ui_state(bpy.context)
            cls._debug_copy3d_state("AFTER_SNAPSHOT_UI", source_schedule.Name, 0)
            
            try:
                config_data = cls.export_schedule_configuration(source_schedule)
                print(f"[STATS] COPY3D TEST: Exported config has {len(config_data.get('task_configurations', []))} task configurations")
            finally:
                restore_all_ui_state(bpy.context)
                cls._debug_copy3d_state("AFTER_RESTORE_UI", source_schedule.Name, 0)
            
            print(f"[STATS] Copy3D: Exported {len(config_data.get('task_configurations', []))} task configurations")

            if not config_data or not config_data.get("task_configurations"):
                return {"success": False, "error": "No configuration data to copy"}

            # Get all work schedules except the source
            all_schedules = [ws for ws in ifc_file.by_type("IfcWorkSchedule") 
                            if ws.id() != source_schedule.id()]
            
            print(f"🎯 Copy3D: Found {len(all_schedules)} target schedules to copy to:")
            for ws in all_schedules:
                print(f"  - '{ws.Name}' (ID: {ws.id()})")
            
            if not all_schedules:
                return {"success": False, "error": "No other schedules found to copy to"}

            copied_schedules = 0
            total_task_matches = 0

            # For each target schedule, find matching tasks and copy configuration
            for target_schedule in all_schedules:
                print(f"📋 Copy3D: Processing target schedule '{target_schedule.Name}' (ID: {target_schedule.id()})")
                
                # Switch to target schedule for UI state  
                ws_props = tool.Sequence.get_work_schedule_props()
                if ws_props:
                    ws_props.active_work_schedule_id = target_schedule.id()
                
                cls._debug_copy3d_state("BEFORE_TARGET_PROCESSING", target_schedule.Name, 0)
                target_task_map = {}
                
                # Build map of task identifications for target schedule
                def get_all_tasks_recursive(tasks):
                    all_tasks_list = []
                    for task in tasks:
                        all_tasks_list.append(task)
                        nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                        if nested_tasks:
                            all_tasks_list.extend(get_all_tasks_recursive(nested_tasks))
                    return all_tasks_list

                root_tasks = ifcopenshell.util.sequence.get_root_tasks(target_schedule)
                all_target_tasks = get_all_tasks_recursive(root_tasks)
                
                for task in all_target_tasks:
                    identification = getattr(task, "Identification", None)
                    if identification:
                        target_task_map[identification] = task

                print(f"📋 Copy3D: Target schedule has {len(target_task_map)} tasks with identifications")
                
                if not target_task_map:
                    print("[WARNING]️ Copy3D: No tasks with identifications in target schedule, skipping")
                    continue

                # Copy matching configurations
                schedule_matches = 0
                matched_identifications = []
                
                for task_config in config_data["task_configurations"]:
                    task_identification = task_config.get("task_identification")
                    if not task_identification:
                        continue

                    target_task = target_task_map.get(task_identification)
                    if not target_task:
                        continue
                    
                    matched_identifications.append(task_identification)
                    print(f"[OK] Copy3D: Found matching task '{task_identification}' -> ID {target_task.id()}")

                    # Copy PredefinedType
                    predefined_type = task_config.get("predefined_type")
                    if predefined_type is not None:
                        ifcopenshell.api.run("sequence.edit_task", ifc_file, 
                                            task=target_task, 
                                            attributes={"PredefinedType": predefined_type})

                    # Copy ICOM data
                    guid_map = {p.GlobalId: p for p in ifc_file.by_type("IfcProduct") if hasattr(p, 'GlobalId')}
                    guid_map.update({r.GlobalId: r for r in ifc_file.by_type("IfcResource") if hasattr(r, 'GlobalId')})

                    # Clear existing assignments
                    for product in ifcopenshell.util.sequence.get_task_outputs(target_task):
                        ifcopenshell.api.run("sequence.unassign_product", ifc_file, 
                                            relating_product=product, related_object=target_task)
                    for product_input in ifcopenshell.util.sequence.get_task_inputs(target_task):
                        ifcopenshell.api.run("sequence.unassign_process", ifc_file, 
                                            relating_process=target_task, related_object=product_input)
                    for resource in ifcopenshell.util.sequence.get_task_resources(target_task):
                        ifcopenshell.api.run("sequence.unassign_process", ifc_file, 
                                            relating_process=target_task, related_object=resource)

                    # Assign new inputs, outputs, resources
                    inputs = [guid_map[guid] for guid in task_config.get("inputs", []) if guid in guid_map]
                    outputs = [guid_map[guid] for guid in task_config.get("outputs", []) if guid in guid_map]
                    resources = [guid_map[guid] for guid in task_config.get("resources", []) if guid in guid_map]

                    if inputs:
                        ifcopenshell.api.run("sequence.assign_process", ifc_file, 
                                            relating_process=target_task, products=inputs)
                    if outputs:
                        for product in outputs:
                            ifcopenshell.api.run("sequence.assign_product", ifc_file, 
                                                relating_product=product, related_object=target_task)
                    if resources:
                        ifcopenshell.api.run("sequence.assign_process", ifc_file, 
                                            relating_process=target_task, resources=resources)

                    schedule_matches += 1

                print(f"[STATS] Copy3D: Completed target schedule - {schedule_matches} task matches")
                print(f"  Matched tasks: {', '.join(matched_identifications) if matched_identifications else 'None'}")
                
                if schedule_matches > 0:
                    copied_schedules += 1
                    total_task_matches += schedule_matches

            # Copy ColorType groups library
            if config_data.get("ColorType_groups"):
                from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                UnifiedColorTypeManager._write_sets_json(bpy.context, config_data["ColorType_groups"])

            # Copy UI settings
            if config_data.get("ui_settings"):
                anim_props = tool.Sequence.get_animation_props()
                anim_props.task_ColorType_group_selector = config_data["ui_settings"].get("task_ColorType_group_selector", "")
                
                # Copy animation group stack
                if "animation_group_stack" in config_data["ui_settings"]:
                    anim_props.animation_group_stack.clear()
                    for item_data in config_data["ui_settings"]["animation_group_stack"]:
                        item = anim_props.animation_group_stack.add()
                        item.group = item_data.get("group", "")
                        if hasattr(item, "enabled"):
                            item.enabled = bool(item_data.get("enabled", False))
                    print(f"📋 Copy3D: Copied {len(config_data['ui_settings']['animation_group_stack'])} animation group stack items")

            # Copy ColorType assignments to all target schedules
            print("👥 Copy3D: Starting ColorType assignments copy...")
            if config_data.get("task_configurations"):
                ColorType_assignments_data = {}
                
                # Extract ColorType assignments from source config
                print("📤 Copy3D: Extracting ColorType assignments from source...")
                for task_config in config_data["task_configurations"]:
                    if "ColorType_assignments" in task_config:
                        task_identification = task_config.get("task_identification")
                        if task_identification:
                            # Convert from export format to internal snapshot format
                            pa = task_config["ColorType_assignments"]
                            groups_data = []
                            for choice in pa.get("choices", []):
                                # Clean and validate ColorType values
                                group_name = choice.get("group_name", "")
                                enabled = bool(choice.get("enabled", False))
                                selected_ColorType = choice.get("selected_ColorType", "")
                                
                                # Add all groups (even if not configured)
                                if group_name:
                                    groups_data.append({
                                        "group_name": group_name,
                                        "enabled": enabled,
                                        "selected_value": selected_ColorType if selected_ColorType else "",
                                    })
                            
                            # Always store ColorType assignments (even if empty/unconfigured)
                            selected_active_ColorType = pa.get("selected_ColorType_in_active_group", "")
                            
                            # LIMPIEZA CONSERVADORA: Solo limpiar valores claramente inválidos
                            if selected_active_ColorType in [None, "0", 0, "None"]:
                                selected_active_ColorType = ""
                            # Nota: NO limpiamos strings vacíos "" porque podrían ser valores válidos
                            
                            ColorType_assignments_data[task_identification] = {
                                "active": bool(pa.get("use_active_ColorType_group", False)),
                                "selected_active_ColorType": selected_active_ColorType,
                                "animation_color_schemes": pa.get("animation_color_schemes", ""),
                                "groups": groups_data  # Can be empty for unconfigured tasks
                            }
                            
                            # DEBUG: Show extracted data
                            print(f"📤 Copy3D EXTRACT DEBUG: Task '{task_identification}'")
                            print(f"    Source Active: {pa.get('use_active_ColorType_group', False)}")
                            print(f"    Source Selected Active: '{pa.get('selected_ColorType_in_active_group', '')}'")
                            print(f"    Source Animation Color Schemes: '{pa.get('animation_color_schemes', '')}'")
                            print(f"    Source Groups: {len(pa.get('choices', []))} choices")
                            
                            if groups_data:
                                print(f"📝 Copy3D: Extracted ColorTypes for task '{task_identification}': {len(groups_data)} groups")
                            else:
                                print(f"📝 Copy3D: Task '{task_identification}' has no configured ColorTypes (will copy empty structure)")
                
                print(f"📋 Copy3D: Total ColorType assignments extracted: {len(ColorType_assignments_data)} tasks")

                # Apply ColorType assignments to each target schedule that had task matches
                for target_schedule in all_schedules:
                    target_task_map = {}
                    
                    # Build task identification map for this target schedule
                    def get_all_tasks_recursive_target(tasks):
                        all_tasks_list = []
                        for task in tasks:
                            all_tasks_list.append(task)
                            nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                            if nested_tasks:
                                all_tasks_list.extend(get_all_tasks_recursive_target(nested_tasks))
                        return all_tasks_list

                    root_tasks = ifcopenshell.util.sequence.get_root_tasks(target_schedule)
                    all_target_tasks = get_all_tasks_recursive_target(root_tasks)
                    
                    for task in all_target_tasks:
                        identification = getattr(task, "Identification", None)
                        if identification:
                            target_task_map[identification] = task

                    if not target_task_map:
                        continue

                    # Check if this schedule has matching tasks
                    has_matches = any(task_id in target_task_map for task_id in ColorType_assignments_data.keys())
                    
                    if has_matches:
                        # Get available ColorType groups to validate against
                        available_groups = {}
                        try:
                            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                            available_groups = UnifiedColorTypeManager._read_sets_json(bpy.context) or {}
                        except Exception as e:
                            print(f"Warning: Could not load ColorType groups for validation: {e}")
                        
                        # Create ColorType assignments for matching tasks only
                        target_ColorType_assignments = {}
                        for task_identification, ColorType_data in ColorType_assignments_data.items():
                            if task_identification in target_task_map:
                                target_task = target_task_map[task_identification]
                                
                                # Validate and clean ColorType data
                                validated_groups = []
                                for group_data in ColorType_data.get("groups", []):
                                    group_name = group_data.get("group_name", "")
                                    selected_ColorType = group_data.get("selected_value", "")
                                    
                                    # Check if group exists in available groups
                                    if group_name in available_groups:
                                        group_ColorTypes = available_groups[group_name].get("ColorTypes", [])
                                        ColorType_names = [p.get("name", "") for p in group_ColorTypes]
                                        
                                        # Validate selected ColorType exists in group - pero ser conservador
                                        if selected_ColorType and selected_ColorType not in ColorType_names:
                                            # If ColorType doesn't exist, warn but keep it (could be user defined)
                                            print(f"Warning: ColorType '{selected_ColorType}' not found in group '{group_name}', keeping anyway")
                                            # selected_ColorType = ""  # Comentado para ser menos agresivo
                                        
                                        validated_groups.append({
                                            "group_name": group_name,
                                            "enabled": group_data.get("enabled", False),
                                            "selected_value": selected_ColorType,
                                        })
                                    else:
                                        # Group doesn't exist, skip it
                                        print(f"Warning: ColorType group '{group_name}' not found, skipping for task '{task_identification}'")
                                
                                # Always store ColorType assignments (even if empty for unconfigured tasks)
                                # Also validate selected_active_ColorType against available ColorTypes
                                selected_active_ColorType = ColorType_data.get("selected_active_ColorType", "")
                                # Clean only clearly problematic values
                                if selected_active_ColorType in [None, "0", 0, "None"]:
                                    selected_active_ColorType = ""
                                # Nota: NO limpiamos strings vacíos porque pueden ser válidos
                                
                                # Additional validation: ensure selected_active_ColorType exists in available groups
                                if selected_active_ColorType and available_groups:
                                    # Check if the selected ColorType exists in any group
                                    ColorType_exists = False
                                    for group_name, group_data in available_groups.items():
                                        group_ColorTypes = group_data.get("ColorTypes", [])
                                        ColorType_names = [p.get("name", "") for p in group_ColorTypes]
                                        if selected_active_ColorType in ColorType_names:
                                            ColorType_exists = True
                                            break
                                    
                                    if not ColorType_exists:
                                        print(f"Warning: Selected active ColorType '{selected_active_ColorType}' not found in any group, keeping anyway for task '{task_identification}'")
                                        # selected_active_ColorType = ""  # Comentado para ser menos agresivo
                                
                                target_ColorType_assignments[str(target_task.id())] = {
                                    "active": ColorType_data.get("active", False),
                                    "selected_active_ColorType": selected_active_ColorType,
                                    "animation_color_schemes": ColorType_data.get("animation_color_schemes", ""),
                                    "groups": validated_groups  # Can be empty for unconfigured tasks
                                }
                                
                                # DEBUG: Show exactly what data is being stored
                                print(f"[CHECK] Copy3D DEBUG: Task '{task_identification}' (ID: {target_task.id()})")
                                print(f"    Active: {ColorType_data.get('active', False)}")
                                print(f"    Selected Active ColorType: '{selected_active_ColorType}'")
                                print(f"    Animation Color Schemes: '{ColorType_data.get('animation_color_schemes', '')}'")
                                print(f"    Groups: {len(validated_groups)} groups")
                                
                                if validated_groups:
                                    print(f"👤 Copy3D: Copied {len(validated_groups)} ColorType groups for task '{task_identification}'")
                                else:
                                    print(f"👤 Copy3D: Copied empty ColorType structure for unconfigured task '{task_identification}'")

                        # Store ColorType assignments for this target schedule
                        if target_ColorType_assignments:
                            target_snap_key = f"_task_colortype_snapshot_json_WS_{target_schedule.id()}"
                            bpy.context.scene[target_snap_key] = json.dumps(target_ColorType_assignments)
                            
                            # Also update the persistent cache to maintain ColorType data when switching schedules
                            cache_key = "_task_colortype_snapshot_cache_json"
                            cache_raw = bpy.context.scene.get(cache_key, "{}")
                            try:
                                cache_data = json.loads(cache_raw) if cache_raw else {}
                            except:
                                cache_data = {}
                            
                            # Merge target ColorType assignments into cache
                            cache_data.update(target_ColorType_assignments)
                            bpy.context.scene[cache_key] = json.dumps(cache_data)
                            
                            print(f"Bonsai INFO: Stored {len(target_ColorType_assignments)} ColorType assignments for schedule '{target_schedule.Name}' (ID: {target_schedule.id()})")
                            
                            # Debug: Show what ColorType assignments were copied
                            for task_id, ColorType_data in target_ColorType_assignments.items():
                                groups_info = ", ".join([f"{g['group_name']}:{g['selected_value']}" for g in ColorType_data.get('groups', [])])
                                print(f"  📋 Copy3D: Task {task_id}: active={ColorType_data.get('active')}, selected_active='{ColorType_data.get('selected_active_ColorType')}', groups=[{groups_info}]")
                            
                            # Comprobar que los datos se guardaron correctamente
                            verification_data = bpy.context.scene.get(target_snap_key)
                            if verification_data:
                                try:
                                    parsed_data = json.loads(verification_data)
                                    print(f"[OK] Copy3D: VERIFICACIÓN - {len(parsed_data)} asignaciones guardadas correctamente en {target_snap_key}")
                                except Exception as e:
                                    print(f"[ERROR] Copy3D: VERIFICACIÓN ERROR - No se pudo parsear datos guardados: {e}")
                            else:
                                print(f"[ERROR] Copy3D: VERIFICACIÓN ERROR - No se encontraron datos en {target_snap_key}")
                            
                            
                            # Extra debug: Show what task IDs we're storing vs task names
                            print(f"[CHECK] Copy3D: ColorType snapshot keys being stored:")
                            try:
                                for task_identification, target_task in target_task_map.items():
                                    if task_identification in ColorType_assignments_data:
                                        print(f"  Task identification '{task_identification}' -> Task ID {target_task.id()} (Name: {target_task.Name})")
                            except Exception as e:
                                print(f"  Error in debug mapping: {e}")

            # Check current UI state after Copy3D
            print(f"\n[CHECK] COPY3D FINAL VERIFICATION TEST")
            
            # Forzar reload completo de la UI desde el cronograma destino
            # para verificar que los datos se copiaron correctamente
            print("🔄 Copy3D: Forcing complete UI reload from destination schedule data...")
            restore_all_ui_state(bpy.context)
            
            # Forzar refresh completo de la UI y re-trigger de todas las funciones de update
            print("🔄 Copy3D: Forcing complete UI refresh...")
            for area in bpy.context.screen.areas:
                area.tag_redraw()
            
            # Verificar estado de task_colortype_group_selector después de Copy3D
            print("[CHECK] Copy3D: Checking task_colortype_group_selector state...")
            try:
                anim_props = tool.Sequence.get_animation_props()
                current_group = getattr(anim_props, "task_colortype_group_selector", "")
                print(f"[CHECK] Current task_colortype_group_selector: '{current_group}'")
                
                if not current_group or current_group == "DEFAULT":
                    print("[WARNING]️ PROBLEM: task_colortype_group_selector is empty or DEFAULT - dropdown will be empty!")
                    
                    # Try to find and set a valid group from copied data
                    from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                    all_sets = UnifiedColorTypeManager._read_sets_json(bpy.context)
                    available_groups = [k for k in all_sets.keys() if k != "DEFAULT"]
                    if available_groups:
                        first_group = available_groups[0]
                        anim_props.task_colortype_group_selector = first_group
                        print(f"🔄 Auto-set task_colortype_group_selector to: '{first_group}'")
                else:
                    print(f"[OK] task_colortype_group_selector is set to valid group: '{current_group}'")
                    
                # Verify ColorType data exists for the selected group
                from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                all_sets = UnifiedColorTypeManager._read_sets_json(bpy.context)
                if current_group in all_sets:
                    group_data = all_sets[current_group]
                    colortypes_list = group_data.get("ColorTypes", [])
                    colortype_names = [ct.get("name", "") for ct in colortypes_list if isinstance(ct, dict)]
                    print(f"[CHECK] Available ColorTypes in '{current_group}': {colortype_names}")
                    
                    if not colortype_names:
                        print("[WARNING]️ PROBLEM: No ColorTypes found in selected group - data may not have been copied properly!")
                else:
                    print(f"[WARNING]️ PROBLEM: Group '{current_group}' not found in ColorType data!")
                    
            except Exception as e:
                print(f"[WARNING]️ Error checking task_colortype_group_selector: {e}")
            
            # Forzar refresh de EnumProperty items functions después de Copy3D
            print("🔄 Copy3D: Forcing EnumProperty items refresh...")
            try:
                tprops = tool.Blender.get_active_tasks_props(bpy.context)
                if tprops and tprops.tasks:
                    for task in tprops.tasks:
                        if hasattr(task, 'selected_colortype_in_active_group'):
                            # Trigger items function refresh by accessing and reassigning the property
                            current_val = task.selected_colortype_in_active_group
                            # Force items function re-evaluation
                            task.property_unset("selected_colortype_in_active_group")
                            task.selected_colortype_in_active_group = current_val
                            print(f"🔄 Refreshed dropdown items for task {getattr(task, 'ifc_definition_id', 'unknown')}")
            except Exception as e:
                print(f"[WARNING]️ Error refreshing EnumProperty items: {e}")
            
            # Forzar snapshot fresco después de la restauración para asegurar consistencia
            snapshot_all_ui_state(bpy.context)
            
            cls._debug_copy3d_state("AFTER_COPY3D_COMPLETE", "Current_Active", copied_schedules)
            
            # Test verification function
            cls._test_copy3d_results(copied_schedules, total_task_matches)
            
            return {
                "success": True,
                "copied_schedules": copied_schedules,
                "task_matches": total_task_matches
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def sync_3d_elements(cls, work_schedule, property_set_name):
        """
        Sync IFC elements to tasks based on property set values matching task indicators.
        Returns a dict with success status and sync statistics.
        """
        try:
            ifc_file = tool.Ifc.get()
            if not ifc_file:
                return {"success": False, "error": "No IFC file loaded"}

            # Get all tasks from the schedule
            def get_all_tasks_recursive(tasks):
                all_tasks_list = []
                for task in tasks:
                    all_tasks_list.append(task)
                    nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested_tasks:
                        all_tasks_list.extend(get_all_tasks_recursive(nested_tasks))
                return all_tasks_list

            root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
            all_tasks = get_all_tasks_recursive(root_tasks)
            
            if not all_tasks:
                return {"success": False, "error": "No tasks found in schedule"}

            # Build task indicator map
            task_indicators = {}
            for task in all_tasks:
                identification = getattr(task, "Identification", None)
                if identification:
                    task_indicators[identification] = task

            print(f"🎯 Sync3D: Encontradas {len(task_indicators)} tareas con identificación:")
            for identification, task in list(task_indicators.items())[:5]:  # Show first 5
                print(f"  📋 Task ID {task.id()}: '{identification}'")

            if not task_indicators:
                return {"success": False, "error": "No task identifications found"}

            # Get all IFC elements with the specified property set
            matched_elements = 0
            processed_tasks = 0
            elements_checked = 0
            elements_with_pset = 0

            print(f"[CHECK] Sync3D: Buscando property set '{property_set_name}' en elementos IFC...")

            for element in ifc_file.by_type("IfcProduct"):
                if not hasattr(element, 'GlobalId'):
                    continue
                
                elements_checked += 1

                # Look for the property set
                property_set = None
                if hasattr(element, 'IsDefinedBy') and element.IsDefinedBy:
                    for rel in element.IsDefinedBy:
                        if hasattr(rel, 'RelatingPropertyDefinition'):
                            prop_def = rel.RelatingPropertyDefinition
                            if hasattr(prop_def, 'Name') and prop_def.Name == property_set_name:
                                property_set = prop_def
                                elements_with_pset += 1
                                if elements_with_pset <= 3:  # Log first 3
                                    element_type = getattr(element, 'is_a', lambda: 'Unknown')()
                                    print(f"  [OK] Sync3D: Elemento {element_type} (ID: {element.id()}) tiene property set '{property_set_name}'")
                                break

                if not property_set:
                    continue

                # Get property value that matches a task indicator
                if hasattr(property_set, 'HasProperties'):
                    for prop in property_set.HasProperties:
                        if hasattr(prop, 'NominalValue') and hasattr(prop.NominalValue, 'wrappedValue'):
                            prop_value = str(prop.NominalValue.wrappedValue)
                            prop_name = getattr(prop, 'Name', 'Unknown')
                            
                            if matched_elements < 3:  # Log first few mappings
                                print(f"  🔗 Sync3D: Property '{prop_name}' = '{prop_value}' en elemento {element.id()}")
                            
                            # Find matching task
                            matching_task = task_indicators.get(prop_value)
                            if matching_task:
                                element_type = getattr(element, 'is_a', lambda: 'Unknown')()
                                print(f"  [OK] Sync3D: MATCH! Asignando {element_type} (ID: {element.id()}) → Task '{prop_value}' (ID: {matching_task.id()})")
                                
                                # Assign element to task as output
                                try:
                                    ifcopenshell.api.run("sequence.assign_product", ifc_file,
                                                        relating_product=element, 
                                                        related_object=matching_task)
                                    matched_elements += 1
                                    print(f"  🎯 Sync3D: Asignación exitosa #{matched_elements}")
                                except Exception as e:
                                    print(f"  [ERROR] Sync3D: Error asignando elemento: {e}")
                                break
                            else:
                                if matched_elements < 5:  # Log first few no-matches
                                    print(f"  [WARNING]️ Sync3D: No se encontró tarea para valor '{prop_value}'")

            # Count processed tasks
            for task in task_indicators.values():
                outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
                if outputs:
                    processed_tasks += 1

            print(f"[STATS] Sync3D: RESUMEN:")
            print(f"  - Elementos revisados: {elements_checked}")
            print(f"  - Elementos con property set '{property_set_name}': {elements_with_pset}")
            print(f"  - Elementos asignados a tareas: {matched_elements}")
            print(f"  - Tareas con elementos asignados: {processed_tasks}")

            # Limpiar datos de perfiles corruptos antes del retorno
            # Esto asegura que cuando restore_all_ui_state() se ejecute, 
            # no restaure valores '0' problemáticos
            print(f"[CLEAN] Sync3D: Limpiando datos de perfiles corruptos en cronograma")
            cls._clean_and_update_ColorType_snapshot_for_schedule(work_schedule)
            
            return {
                "success": True,
                "matched_elements": matched_elements,
                "processed_tasks": processed_tasks
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

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
                print(f"[CLEAN] Sync3D: No hay snapshot para limpiar en cronograma {ws_id}")
                return
            
            try:
                snapshot_data = json.loads(snapshot_raw)
                print(f"[CLEAN] Sync3D: Limpiando {len(snapshot_data)} tareas en snapshot")
            except Exception as e:
                print(f"[ERROR] Sync3D: Error parseando snapshot: {e}")
                return
            
            # Limpiar datos usando la función existente
            cleaned_data = cls._clean_ColorType_snapshot_data(snapshot_data)
            
            # Actualizar el snapshot con datos limpios
            bpy.context.scene[snapshot_key_specific] = json.dumps(cleaned_data)
            print(f"[OK] Sync3D: Datos de perfiles limpiados en cronograma {ws_id}")
            
        except Exception as e:
            print(f"[ERROR] Sync3D: Error en limpieza de perfiles: {e}")

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




