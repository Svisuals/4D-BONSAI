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

import bpy
import json
import time
import bonsai.tool as tool
import bonsai.core.sequence as core


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

# Import helper functions from other modules
from .animation_operators import _clear_previous_animation, _get_animation_settings, _compute_product_frames, _ensure_default_group
from .schedule_task_operators import snapshot_all_ui_state, restore_all_ui_state

try:
    from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
except Exception:
    UnifiedColorTypeManager = None  # optional

try:
    from ..prop import TaskcolortypeGroupChoice
except Exception:
    TaskcolortypeGroupChoice = None  # optional


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


# ============================================================================
# WORK SCHEDULE OPERATORS
# ============================================================================

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
                "colortype_sets": {},  # Moved to config_operators.py
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
        import ifcopenshell.util.sequence
        
        schedule_to_remove_id = self.work_schedule
        schedule_to_remove = tool.Ifc.get().by_id(schedule_to_remove_id)
        
        print(f"\n🔍 === DEBUGGING ELIMINACIÓN CRONOGRAMA ===")
        print(f"🗑️ Eliminando cronograma ID {schedule_to_remove_id} - '{schedule_to_remove.Name}'")
        
        # ANTES de eliminar: Inspeccionar el estado
        ifc_file = tool.Ifc.get()
        all_schedules_before = ifc_file.by_type("IfcWorkSchedule")
        
        print(f"📊 ANTES - Total cronogramas: {len(all_schedules_before)}")
        for ws in all_schedules_before:
            tasks = ifcopenshell.util.sequence.get_root_tasks(ws)
            print(f"  📅 '{ws.Name}' (ID:{ws.id()}) - {len(tasks)} tareas raíz")
            for i, task in enumerate(tasks[:3]):  # Solo primeras 3 tareas
                print(f"    📝 Tarea {i+1}: '{task.Name}' (ID:{task.id()})")
        
        # Current active schedule
        ws_props = tool.Sequence.get_work_schedule_props()
        current_active = ws_props.active_work_schedule_id
        print(f"🎯 Cronograma activo actual: {current_active}")
        
        # Eliminar el cronograma (operación original)
        core.remove_work_schedule(tool.Ifc, work_schedule=schedule_to_remove)
        
        # DESPUÉS de eliminar: Inspeccionar el estado
        all_schedules_after = ifc_file.by_type("IfcWorkSchedule")
        
        print(f"📊 DESPUÉS - Total cronogramas: {len(all_schedules_after)}")
        for ws in all_schedules_after:
            try:
                tasks = ifcopenshell.util.sequence.get_root_tasks(ws)
                print(f"  📅 '{ws.Name}' (ID:{ws.id()}) - {len(tasks)} tareas raíz")
                for i, task in enumerate(tasks[:3]):  # Solo primeras 3 tareas
                    print(f"    📝 Tarea {i+1}: '{task.Name}' (ID:{task.id()})")
            except Exception as e:
                print(f"  ❌ Error inspeccionando '{ws.Name}': {e}")
        
        # Check active schedule after deletion
        current_active_after = ws_props.active_work_schedule_id
        print(f"🎯 Cronograma activo después: {current_active_after}")
        
        print(f"✅ Cronograma eliminado: ID {schedule_to_remove_id}")
        print(f"🔍 === FIN DEBUGGING ELIMINACIÓN ===\n")


class CopyWorkSchedule(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.copy_work_schedule"
    bl_label = "Copy Work Schedule"
    bl_description = "Create a duplicate of the provided work schedule."
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()  # pyright: ignore[reportRedeclaration]

    def _execute(self, context):
        import ifcopenshell.util.sequence
        
        # 0. CRÍTICO: Hacer snapshot ANTES de capturar para asegurar que todo esté guardado
        print(f"🔄 Forzando snapshot completo antes de duplicar...")
        from .filter_operators import snapshot_all_ui_state
        snapshot_all_ui_state(context)
        
        # 1. Capturar configuración de ColorType del cronograma origen DESPUÉS del snapshot
        source_schedule = tool.Ifc.get().by_id(self.work_schedule)
        source_colortype_config = self._capture_schedule_colortype_config(context, source_schedule)
        
        print(f"\n🔍 === DEBUGGING DUPLICACIÓN CRONOGRAMA ===")
        print(f"📋 Duplicando cronograma '{source_schedule.Name}' (ID:{source_schedule.id()})")
        
        # ANTES de duplicar: Inspeccionar el estado
        ifc_file = tool.Ifc.get()
        all_schedules_before = ifc_file.by_type("IfcWorkSchedule")
        source_tasks = ifcopenshell.util.sequence.get_root_tasks(source_schedule)
        
        print(f"📊 ANTES - Total cronogramas: {len(all_schedules_before)}")
        print(f"📝 Cronograma origen tiene {len(source_tasks)} tareas raíz:")
        for i, task in enumerate(source_tasks[:3]):  # Solo primeras 3 tareas
            print(f"  📝 Tarea {i+1}: '{task.Name}' (ID:{task.id()})")
        
        # 2. Ejecutar la lógica de copia que ahora sí crea un duplicado en el IFC.
        core.copy_work_schedule(tool.Sequence, work_schedule=source_schedule)
        
        # DESPUÉS de duplicar: Inspeccionar el estado
        all_schedules_after = ifc_file.by_type("IfcWorkSchedule")
        
        print(f"📊 DESPUÉS - Total cronogramas: {len(all_schedules_after)}")
        
        # Encontrar el cronograma recién duplicado
        new_schedules = [ws for ws in all_schedules_after if ws.id() not in [s.id() for s in all_schedules_before]]
        
        if new_schedules:
            duplicate_schedule = new_schedules[0]
            duplicate_tasks = ifcopenshell.util.sequence.get_root_tasks(duplicate_schedule)
            print(f"🆕 Cronograma duplicado: '{duplicate_schedule.Name}' (ID:{duplicate_schedule.id()})")
            print(f"📝 Cronograma duplicado tiene {len(duplicate_tasks)} tareas raíz:")
            for i, task in enumerate(duplicate_tasks[:3]):  # Solo primeras 3 tareas
                print(f"  📝 Tarea {i+1}: '{task.Name}' (ID:{task.id()})")
        else:
            print("❌ No se encontró cronograma duplicado!")
        
        # Verificar si las tareas tienen IDs diferentes
        if new_schedules and source_tasks:
            duplicate_tasks = ifcopenshell.util.sequence.get_root_tasks(new_schedules[0])
            if duplicate_tasks:
                print(f"🔍 VERIFICACIÓN IDs:")
                print(f"  Original tarea 1 ID: {source_tasks[0].id()}")
                print(f"  Duplicada tarea 1 ID: {duplicate_tasks[0].id()}")
                if source_tasks[0].id() == duplicate_tasks[0].id():
                    print("🚨 ¡¡¡PROBLEMA!!! Las tareas comparten el mismo ID!")
                else:
                    print("✅ Las tareas tienen IDs diferentes")
        
        print(f"🔍 === FIN DEBUGGING DUPLICACIÓN ===\n")

        # 3. Aplicar configuración de ColorType al cronograma duplicado
        if source_colortype_config:
            # Obtener el mapeo de tareas originales a duplicadas
            task_mapping = getattr(tool.Sequence, 'last_duplication_mapping', {})
            self._apply_colortype_config_to_duplicate(context, source_colortype_config, task_mapping)

        # 4. Forzar la recarga de los datos y el redibujado de la UI.
        try:
            from bonsai.bim.module.sequence.data import SequenceData, WorkScheduleData
            SequenceData.load()
            WorkScheduleData.load()
            for area in context.screen.areas:
                if area.type in ['PROPERTIES', 'OUTLINER']:
                    area.tag_redraw()
        except Exception as e:
            print(f"Bonsai WARNING: UI refresh failed after copying schedule: {e}")
    
    def _capture_schedule_colortype_config(self, context, source_schedule):
        """
        Captura DIRECTAMENTE desde la UI toda la configuración de ColorType del cronograma origen.
        """
        try:
            import json
            import ifcopenshell.util.sequence
            
            config = {}
            
            # DIAGNÓSTICO EXHAUSTIVO: Capturar DIRECTAMENTE desde las propiedades de UI
            print(f"🔍🔍🔍 === INICIANDO CAPTURA DIRECTA EXHAUSTIVA ===")
            print(f"📋 Cronograma origen: {source_schedule.Name} (ID: {source_schedule.id()})")
            
            # Obtener todas las tareas del cronograma origen
            def get_all_tasks_recursive(tasks):
                all_tasks_list = []
                for task in tasks:
                    all_tasks_list.append(task)
                    nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested_tasks:
                        all_tasks_list.extend(get_all_tasks_recursive(nested_tasks))
                return all_tasks_list
            
            root_tasks = ifcopenshell.util.sequence.get_root_tasks(source_schedule)
            all_tasks = get_all_tasks_recursive(root_tasks)
            print(f"📊 Total tareas en cronograma: {len(all_tasks)}")
            
            # Obtener propiedades de UI
            try:
                tprops = tool.Sequence.get_task_tree_props()
                if not tprops:
                    print(f"❌ No se pudieron obtener task_tree_props")
                    return {}
                
                print(f"✅ task_tree_props obtenidas exitosamente")
                
                # Examinar estructura completa de tprops
                print(f"🔎 Estructura de tprops:")
                for attr_name in dir(tprops):
                    if not attr_name.startswith('_'):
                        attr_value = getattr(tprops, attr_name, None)
                        if hasattr(attr_value, '__len__') and not isinstance(attr_value, str):
                            try:
                                print(f"  {attr_name}: tipo {type(attr_value).__name__}, longitud {len(attr_value)}")
                            except:
                                print(f"  {attr_name}: tipo {type(attr_value).__name__}")
                        else:
                            print(f"  {attr_name}: {type(attr_value).__name__} = {attr_value}")
                
                # Crear mapeo de IDs a elementos de UI
                tasks_prop = getattr(tprops, "tasks", [])
                print(f"📋 tprops.tasks longitud: {len(tasks_prop)}")
                
                task_id_to_ui = {}
                for i, t in enumerate(tasks_prop):
                    task_id = str(getattr(t, "ifc_definition_id", 0))
                    task_id_to_ui[task_id] = t
                    print(f"  UI Task {i}: ID={task_id}, Name='{getattr(t, 'name', 'NO_NAME')}'")
                    
                    # Examinar propiedades de ColorType de esta UI task
                    colortype_attrs = []
                    for attr_name in dir(t):
                        if 'color' in attr_name.lower() and not attr_name.startswith('_'):
                            attr_value = getattr(t, attr_name, None)
                            colortype_attrs.append(f"{attr_name}={attr_value}")
                    if colortype_attrs:
                        print(f"    ColorType attrs: {', '.join(colortype_attrs)}")
                    
                    # Examinar colortype_group_choices específicamente
                    colortype_group_choices = getattr(t, "colortype_group_choices", [])
                    print(f"    colortype_group_choices: {len(colortype_group_choices)} grupos")
                    for j, group in enumerate(colortype_group_choices):
                        print(f"      Grupo {j}:")
                        for attr_name in dir(group):
                            if not attr_name.startswith('_'):
                                attr_value = getattr(group, attr_name, None)
                                print(f"        {attr_name}: {attr_value}")
                
                print(f"📋 UI tiene {len(task_id_to_ui)} tareas cargadas, IDs: {list(task_id_to_ui.keys())}")
                
                # Capturar configuración de cada tarea
                for task in all_tasks:
                    task_id = str(task.id())
                    task_name = getattr(task, 'Name', 'SIN_NOMBRE')
                    print(f"\n🎯 Procesando tarea IFC: {task_id} '{task_name}'")
                    
                    if task_id == "0":
                        print(f"    ⏭️ Saltando tarea ID=0")
                        continue
                        
                    # Buscar la tarea en la UI
                    if task_id in task_id_to_ui:
                        ui_task = task_id_to_ui[task_id]
                        print(f"    ✅ Encontrada en UI")
                        
                        # Capturar grupos de colores DIRECTAMENTE
                        groups_list = []
                        colortype_group_choices = getattr(ui_task, "colortype_group_choices", [])
                        print(f"    📊 colortype_group_choices: {len(colortype_group_choices)} grupos")
                        
                        for idx, group in enumerate(colortype_group_choices):
                            group_name = getattr(group, "group_name", "")
                            print(f"      Grupo {idx}: name='{group_name}'")
                            
                            if group_name:
                                # Detectar el atributo correcto para el valor seleccionado
                                selected_value = ""
                                selected_attr = ""
                                
                                for attr in ["selected_colortype", "selected", "active_colortype", "colortype"]:
                                    if hasattr(group, attr):
                                        val = getattr(group, attr, "")
                                        print(f"        {attr}: '{val}'")
                                        if val and not selected_value:
                                            selected_value = val
                                            selected_attr = attr
                                
                                enabled = bool(getattr(group, "enabled", False))
                                print(f"        enabled: {enabled}")
                                print(f"        selected_value: '{selected_value}' (de {selected_attr})")
                                
                                groups_list.append({
                                    "group_name": group_name,
                                    "enabled": enabled,
                                    "selected_value": selected_value,
                                    "selected_attr": selected_attr,
                                })
                        
                        # Capturar estado de checkbox y selector activo
                        use_active = bool(getattr(ui_task, "use_active_colortype_group", False))
                        selected_active = getattr(ui_task, "selected_colortype_in_active_group", "")
                        animation_schemes = getattr(ui_task, "animation_color_schemes", "")
                        
                        print(f"    📋 use_active_colortype_group: {use_active}")
                        print(f"    📋 selected_colortype_in_active_group: '{selected_active}'")
                        print(f"    📋 animation_color_schemes: '{animation_schemes}'")
                        
                        config[task_id] = {
                            "active": use_active,
                            "selected_active_colortype": selected_active,
                            "animation_color_schemes": animation_schemes,
                            "groups": groups_list,
                            "is_selected": getattr(ui_task, 'is_selected', False),
                            "is_expanded": getattr(ui_task, 'is_expanded', False),
                        }
                        
                        print(f"    ✅ Configuración capturada: {len(groups_list)} grupos, active={use_active}")
                        
                    else:
                        print(f"    ❌ Tarea {task_id} '{task_name}' NO encontrada en UI")
                        print(f"       IDs disponibles en UI: {list(task_id_to_ui.keys())}")
                
                print(f"\n🎨 === RESUMEN CAPTURA DIRECTA ===")
                print(f"🎨 Total configuraciones capturadas: {len(config)} tareas")
                
                # DEBUG: Mostrar estructura DIRECTA capturada para TODAS las tareas
                for task_id, task_config in config.items():
                    print(f"🔍 TASK {task_id} configuración final:")
                    groups = task_config.get("groups", [])
                    print(f"    groups: {len(groups)} items")
                    for g in groups:
                        print(f"      - '{g.get('group_name', 'sin nombre')}': enabled={g.get('enabled')}, value='{g.get('selected_value', '')}'")
                    print(f"    active: {task_config.get('active')}")
                    print(f"    selected_active_colortype: '{task_config.get('selected_active_colortype', '')}'")
                
                return config
                
            except Exception as ui_error:
                print(f"❌ Error capturando desde UI: {ui_error}")
                import traceback
                traceback.print_exc()
                return {}
            
        except Exception as e:
            print(f"❌ Error general en captura: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _apply_colortype_config_to_duplicate(self, context, source_config, task_mapping=None):
        """
        Aplica la configuración de ColorType capturada al cronograma duplicado.
        """
        try:
            import json
            import ifcopenshell.util.sequence
            
            print(f"🔄🔄🔄 === INICIANDO APLICACIÓN EXHAUSTIVA ===")
            
            if not source_config:
                print(f"❌ source_config está vacío, no hay nada que aplicar")
                return
            
            print(f"📊 source_config tiene {len(source_config)} entradas")
            
            # Encontrar el cronograma recién creado (último "Copy of...")
            ifc_file = tool.Ifc.get()
            all_schedules = ifc_file.by_type("IfcWorkSchedule")
            duplicate_schedule = None
            
            print(f"📋 Buscando cronograma duplicado entre {len(all_schedules)} cronogramas:")
            for schedule in all_schedules:
                schedule_name = getattr(schedule, 'Name', 'SIN_NOMBRE')
                print(f"  - {schedule.id()}: '{schedule_name}'")
                if schedule_name and schedule_name.startswith("Copy of "):
                    duplicate_schedule = schedule
                    print(f"    ✅ Este es el cronograma duplicado")
            
            if not duplicate_schedule:
                print("❌ No se encontró cronograma duplicado")
                return
            
            # Obtener todas las tareas del cronograma duplicado
            def get_all_tasks_recursive(tasks):
                all_tasks_list = []
                for task in tasks:
                    all_tasks_list.append(task)
                    nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested_tasks:
                        all_tasks_list.extend(get_all_tasks_recursive(nested_tasks))
                return all_tasks_list
            
            root_tasks = ifcopenshell.util.sequence.get_root_tasks(duplicate_schedule)
            all_duplicate_tasks = get_all_tasks_recursive(root_tasks)
            
            print(f"📊 Cronograma duplicado '{duplicate_schedule.Name}' tiene {len(all_duplicate_tasks)} tareas")
            
            # Crear mapping por Identification para encontrar tareas correspondientes
            duplicate_task_map = {}
            for task in all_duplicate_tasks:
                identification = getattr(task, "Identification", None)
                if identification:
                    duplicate_task_map[identification] = task
                    print(f"  Duplicate task {task.id()}: '{getattr(task, 'Name', 'SIN_NOMBRE')}' -> identification: '{identification}'")
            
            # Aplicar configuración a las tareas duplicadas
            duplicate_ws_id = duplicate_schedule.id()
            snap_key_duplicate = f"_task_colortype_snapshot_json_WS_{duplicate_ws_id}"
            cache_key = "_task_colortype_snapshot_cache_json"
            
            print(f"📁 Keys para guardar configuración:")
            print(f"  snap_key_duplicate: {snap_key_duplicate}")
            print(f"  cache_key: {cache_key}")
            
            # NUEVO: Usar el mapeo exacto de IDs si está disponible
            duplicate_config = {}
            
            if task_mapping:
                print(f"🎯 Usando mapeo exacto de {len(task_mapping)} tareas para ColorType")
                print(f"🔗 Mapeo disponible: {task_mapping}")
                
                # Mapeo directo usando el mapeo de duplicación
                for source_task_id_int, target_task_id_int in task_mapping.items():
                    source_task_id_str = str(source_task_id_int)
                    target_task_id_str = str(target_task_id_int)
                    
                    print(f"\n🎯 Procesando mapeo: {source_task_id_str} → {target_task_id_str}")
                    
                    if source_task_id_str in source_config:
                        config_data = source_config[source_task_id_str].copy()
                        duplicate_config[target_task_id_str] = config_data
                        
                        print(f"  ✅ ColorType copiado exitosamente")
                        print(f"    📁 Keys en config original: {list(config_data.keys())}")
                        
                        # Verificar estructura detalladamente
                        if "groups" in config_data:
                            groups = config_data["groups"]
                            print(f"    📁 Groups encontrados: {len(groups)} items")
                            
                            for idx, g in enumerate(groups):
                                group_name = g.get("group_name", "SIN_NOMBRE")
                                enabled = g.get("enabled", False)
                                value = g.get("selected_value", "")
                                print(f"      {idx}: '{group_name}' (enabled={enabled}, value='{value}')")
                                
                                # Enfoque especial en DEFAULT
                                if group_name == "DEFAULT":
                                    print(f"      🔍 DEFAULT DETECTADO: enabled={enabled}, value='{value}'")
                        else:
                            print(f"    ❌ Campo 'groups' NO encontrado en configuración")
                        
                        # Verificar checkbox activo
                        active = config_data.get("active", False)
                        selected = config_data.get("selected_active_colortype", "")
                        print(f"    📋 Checkbox activo: {active}")
                        print(f"    📋 Valor seleccionado: '{selected}'")
                        
                    else:
                        print(f"  ❌ ID de origen {source_task_id_str} NO encontrado en source_config")
                        print(f"      IDs disponibles: {list(source_config.keys())}")
                        
                print(f"🎨 Resultado mapeo exacto: {len(duplicate_config)} configuraciones transferidas")
                
            else:
                print(f"⚠️ No hay mapeo exacto, usando método fallback por Identification")
                # Fallback: mapeo por Identification (método anterior)
                for source_task_id, config_data in source_config.items():
                    print(f"🔍 Buscando correspondencia para source task {source_task_id}")
                    
                    # Intentar encontrar la tarea correspondiente por Identification
                    for identification, duplicate_task in duplicate_task_map.items():
                        duplicate_task_id = str(duplicate_task.id())
                        if duplicate_task_id not in duplicate_config:
                            duplicate_config[duplicate_task_id] = config_data.copy()
                            print(f"  ✅ Asignado por Identification '{identification}': {source_task_id} → {duplicate_task_id}")
                            break
                
                # Si no hay suficientes mapeos por Identification, aplicar secuencialmente
                if len(duplicate_config) < len(source_config):
                    print(f"⚠️ Mapeo por Identification insuficiente, aplicando secuencialmente")
                    duplicate_task_ids = [str(task.id()) for task in all_duplicate_tasks]
                    source_configs = list(source_config.values())
                    
                    for i, duplicate_task_id in enumerate(duplicate_task_ids):
                        if duplicate_task_id not in duplicate_config and i < len(source_configs):
                            duplicate_config[duplicate_task_id] = source_configs[i].copy()
                            print(f"  ✅ Asignado secuencialmente: índice {i} → {duplicate_task_id}")
            
            print(f"\n📊 === RESULTADO FINAL DE CONFIGURACIÓN ===")
            print(f"Total configuraciones a aplicar: {len(duplicate_config)}")
            
            # Mostrar configuración final que se va a guardar
            for task_id, config in duplicate_config.items():
                print(f"🔍 TASK {task_id} configuración final:")
                groups = config.get("groups", [])
                print(f"    groups: {len(groups)} items")
                for g in groups:
                    name = g.get('group_name', 'sin nombre')
                    enabled = g.get('enabled', False)
                    value = g.get('selected_value', '')
                    print(f"      - '{name}': enabled={enabled}, value='{value}'")
                    if name == "DEFAULT":
                        print(f"        🔍 DEFAULT: enabled={enabled}, value='{value}'")
                print(f"    active: {config.get('active')}")
                print(f"    selected_active_colortype: '{config.get('selected_active_colortype', '')}'")
            
            # Guardar configuración en el snapshot y caché
            print(f"\n💾 === GUARDANDO CONFIGURACIÓN ===")
            
            config_json = json.dumps(duplicate_config)
            context.scene[snap_key_duplicate] = config_json
            print(f"✅ Guardado en snapshot: {len(config_json)} caracteres")
            
            # También actualizar el caché general
            try:
                cache_raw = context.scene.get(cache_key, "{}")
                cache_data = json.loads(cache_raw) if cache_raw else {}
                cache_data.update(duplicate_config)
                context.scene[cache_key] = json.dumps(cache_data)
                print(f"✅ Cache general actualizado")
            except Exception as cache_error:
                print(f"⚠️ Error actualizando cache general: {cache_error}")
                context.scene[cache_key] = json.dumps(duplicate_config)
                print(f"✅ Cache general recreado")
            
            # Verificar que efectivamente se guardó
            verification = context.scene.get(snap_key_duplicate, "")
            if verification:
                verification_data = json.loads(verification)
                print(f"✅ Verificación: {len(verification_data)} entradas guardadas correctamente")
            else:
                print(f"❌ ERROR: No se pudo verificar el guardado")
            
            print(f"🎨 Applied ColorType config to {len(duplicate_config)} tasks in duplicated schedule '{duplicate_schedule.Name}'")
            
            # CRÍTICO: Cargar la configuración en la UI para que sea visible
            if duplicate_config:
                try:
                    from .filter_operators import restore_persistent_task_state
                    print(f"🔄 === CARGANDO CONFIGURACIÓN EN UI ===")
                    
                    # Temporalmente cambiar al cronograma duplicado para cargar su configuración
                    ws_props = tool.Sequence.get_work_schedule_props()
                    original_active_id = ws_props.active_work_schedule_id
                    print(f"📋 Cronograma activo original: {original_active_id}")
                    
                    # Cambiar temporalmente al cronograma duplicado
                    ws_props.active_work_schedule_id = duplicate_ws_id
                    print(f"📋 Cambiando temporalmente a cronograma duplicado: {duplicate_ws_id}")
                    tool.Sequence.load_task_tree(duplicate_schedule)
                    
                    # Restaurar la configuración en la UI
                    print(f"🔄 Ejecutando restore_persistent_task_state...")
                    restore_persistent_task_state(context)
                    print(f"✅ restore_persistent_task_state completado")
                    
                    # Volver al cronograma original
                    if original_active_id != 0:
                        print(f"📋 Volviendo al cronograma original: {original_active_id}")
                        ws_props.active_work_schedule_id = original_active_id
                        original_schedule = tool.Ifc.get().by_id(original_active_id)
                        tool.Sequence.load_task_tree(original_schedule)
                    
                    print(f"✅ Configuración ColorType cargada en UI del cronograma duplicado")
                    
                except Exception as ui_error:
                    print(f"❌ Error cargando configuración en UI: {ui_error}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"❌ No hay configuración que cargar en UI")
            
            print(f"🎨 === ColorType duplication process COMPLETED ===")
            
        except Exception as e:
            print(f"❌ Error general aplicando ColorType config: {e}")
            import traceback
            traceback.print_exc()


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
    """
    Habilita la edición de la estructura de tareas para un cronograma de trabajo específico,
    asegurando que la caché de estado se gestione correctamente.
    """
    bl_idname = "bim.enable_editing_work_schedule_tasks"
    bl_label = "Enable Editing Work Schedule Tasks"
    bl_description = "Enable editing work schedule tasks."
    bl_options = {"REGISTER", "UNDO"}
    
    work_schedule: bpy.props.IntProperty()

    def execute(self, context):
        
        # --- PASO 1: LIMPIAR LA CACHÉ PERSISTENTE DE FORMA SELECTIVA ---
        # Solo limpiamos el cache del cronograma ANTERIOR, no globalmente.
        # Esto preserva las tareas del cronograma original cuando se duplica/elimina.
        try:
            # Obtener el cronograma que se está dejando (si hay uno)
            ws_props = tool.Sequence.get_work_schedule_props()
            previous_schedule_id = getattr(ws_props, "active_work_schedule_id", 0)
            
            if previous_schedule_id != 0 and previous_schedule_id != self.work_schedule:
                # Solo limpiar cache del cronograma anterior, no del que se va a activar
                bpy.ops.bim.clear_task_state_cache(work_schedule_id=previous_schedule_id)
                print(f"🎯 Cache selectivo: limpiado cronograma anterior {previous_schedule_id}")
            else:
                print("🔄 Cambio de cronograma: sin limpieza de cache necesaria")
                
        except Exception as e:
            print(f"Advertencia: Limpieza selectiva falló: {e}. Sin limpieza de cache.")

        # --- PASO 2: GUARDAR EL ESTADO GENERAL DE LA UI ---
        # Esto guarda cosas como la posición del scroll o la tarea activa,
        # usando el mecanismo que ya tenías.
        snapshot_all_ui_state(context)

        # --- PASO 3: ESTABLECER EL NUEVO CRONOGRAMA ACTIVO Y CARGAR DATOS ---
        # Obtenemos la instancia del cronograma a partir de su ID
        work_schedule_instance = tool.Ifc.get().by_id(self.work_schedule)
        
        # Llamamos a tu función 'core' que se encarga de la lógica principal de activación
        core.enable_editing_work_schedule_tasks(tool.Sequence, work_schedule=work_schedule_instance)
        
        # Recargamos el árbol de tareas y las propiedades, como en tu versión original.
        # Esto es necesario para que la UI muestre las tareas del nuevo cronograma.
        tool.Sequence.load_task_tree(work_schedule_instance)
        tool.Sequence.load_task_properties()

        # --- PASO 4: RESTAURAR EL ESTADO GENERAL DE LA UI ---
        # Restauramos el scroll y la selección que guardamos en el paso 2.
        # Como la caché de ColorTypes está vacía, no intentará restaurar
        # datos incorrectos del cronograma anterior.
        restore_all_ui_state(context)

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
                        "colortype_sets": {},  # Moved to config_operators.py
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

            
            # FORCE OPTIMIZED FRAME COMPUTATION - SOLVE PROBLEM #2
            frames_start = time.time()
            try:
                # Always try optimized method first
                from bonsai.bim.module.sequence import ifc_lookup
                lookup = ifc_lookup.get_ifc_lookup()
                date_cache = ifc_lookup.get_date_cache()
                if not lookup.lookup_built:
                    print("[OPTIMIZED] Building lookup tables...")
                    lookup.build_lookup_tables(work_schedule)
                print("[OPTIMIZED] Using enhanced optimized frame computation...")
                product_frames = tool.Sequence.get_animation_product_frames_enhanced_optimized(
                    work_schedule, settings, lookup, date_cache
                )
                frames_time = time.time() - frames_start
                print(f"📊 FRAMES COMPUTED: {len(product_frames)} products in {frames_time:.2f}s")
            except Exception as e:
                print(f"[WARNING] Optimized frames method not available, using fallback: {e}")
                product_frames = tool.Sequence.get_animation_product_frames_enhanced(work_schedule, settings)
            if not product_frames:
                self.report({'WARNING'}, "No products found to animate.")

            # FORCE OPTIMIZED ANIMATION APPLICATION - SOLVE PROBLEMS #1 & #2
            anim_start = time.time()

            # BUILD COLORTYPE CACHE - SOLVE PROBLEM #1
            try:
                try:
                    from . import colortype_cache
                except ImportError:
                    import sys, os
                    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                    import colortype_cache
                cache_instance = colortype_cache.get_colortype_cache()
                colortype_build_time = cache_instance.build_cache(bpy.context)
                print(f"🎨 COLORTYPE CACHE: Built in {colortype_build_time:.3f}s")
            except Exception as e:
                print(f"[WARNING] ColorType cache failed to build: {e}")

            try:
                # FORCE OPTIMIZED PATH - SOLVE PROBLEM #2
                from bonsai.bim.module.sequence import performance_cache, batch_processor
                cache = performance_cache.get_performance_cache()
                batch = batch_processor.BlenderBatchProcessor()
                if not cache.cache_valid:
                    print("[OPTIMIZED] Building performance cache...")
                    cache.build_scene_cache()
                print("[OPTIMIZED] Using FULL optimization stack (IFC + Performance + Batch + ColorType)...")
                tool.Sequence.animate_objects_with_ColorTypes_optimized(
                    settings, product_frames, cache, batch
                )
                anim_time = time.time() - anim_start
                print(f"🎬 ANIMATION APPLIED: Completed in {anim_time:.2f}s")
            except Exception as e:
                print(f"[WARNING] Batch processor not available, using ultra-optimized fallback: {e}")
                print(f"[ULTRA-OPTIMIZED] Using our integrated optimization system...")
                # Use our ultra-optimized version with ALL built-in optimizations
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
                    # Persist world-origin anchoring for Snapshot workflow - COMENTADO para permitir constraints
                    # try:
                    #     parent_empty['anchor_mode'] = 'WORLD_ORIGIN'
                    #     context.scene['hud_anchor_mode'] = 'WORLD_ORIGIN'
                    # except Exception:
                    #     pass

                    for obj in text_coll.objects:
                        if obj.parent != parent_empty:
                            obj.parent = parent_empty
                            obj.matrix_parent_inverse = parent_empty.matrix_world.inverted()

                    # Llamar directamente a la función en lugar de usar prop fallback
                    from ..prop import callbacks_prop
                    callbacks_prop.update_schedule_display_parent_constraint(context)
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
                should_hide = not getattr(camera_props, "show_3d_schedule_texts", False)
                
                # Aplicar lógica de desactivación automática si 3D HUD Render está desactivado
                if should_hide:
                    current_legend_enabled = getattr(camera_props, "enable_3d_legend_hud", False)
                    if current_legend_enabled:
                        print("🔴 ANIMATION: 3D HUD Render disabled, auto-disabling 3D Legend HUD")
                        camera_props.enable_3d_legend_hud = False
                
                collection = bpy.data.collections.get("Schedule_Display_Texts")
                if collection:
                    # Sincroniza la visibilidad de la colección con el estado del checkbox.
                    # Si show_3d_schedule_texts es False, hide_viewport debe ser True.
                    collection.hide_viewport = should_hide
                    collection.hide_render = should_hide
                    
                # También aplicar a 3D Legend HUD collection
                legend_collection = bpy.data.collections.get("Schedule_Display_3D_Legend")
                if legend_collection:
                    legend_collection.hide_viewport = should_hide
                    legend_collection.hide_render = should_hide
                    
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
                    from ..hud import invalidate_legend_hud_cache
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

