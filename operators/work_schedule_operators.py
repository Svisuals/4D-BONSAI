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
    from bonsai.bim.module.sequence.prop import TaskcolortypeGroupChoice
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
        core.remove_work_schedule(tool.Ifc, work_schedule=tool.Ifc.get().by_id(self.work_schedule))


class CopyWorkSchedule(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.copy_work_schedule"
    bl_label = "Copy Work Schedule"
    bl_description = "Create a duplicate of the provided work schedule."
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()  # pyright: ignore[reportRedeclaration]

    def _execute(self, context):
        # 0. Capturar configuración de ColorType del cronograma origen ANTES de duplicar
        source_schedule = tool.Ifc.get().by_id(self.work_schedule)
        source_colortype_config = self._capture_schedule_colortype_config(context, source_schedule)
        
        # 1. Ejecutar la lógica de copia que ahora sí crea un duplicado en el IFC.
        core.copy_work_schedule(tool.Sequence, work_schedule=source_schedule)

        # 2. Aplicar configuración de ColorType al cronograma duplicado
        if source_colortype_config:
            self._apply_colortype_config_to_duplicate(context, source_colortype_config)

        # 3. Forzar la recarga de los datos y el redibujado de la UI.
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
        Captura toda la configuración de ColorType del cronograma origen.
        """
        try:
            import json
            ws_id = source_schedule.id()
            
            # Capturar snapshot específico del cronograma origen
            snap_key_specific = f"_task_colortype_snapshot_json_WS_{ws_id}"
            cache_key = "_task_colortype_snapshot_cache_json"
            
            config = {}
            
            # Obtener datos del snapshot específico
            snap_raw = context.scene.get(snap_key_specific)
            if snap_raw:
                try:
                    config.update(json.loads(snap_raw) or {})
                except Exception:
                    pass
            
            # Obtener datos del caché general
            cache_raw = context.scene.get(cache_key)
            if cache_raw:
                try:
                    cache_data = json.loads(cache_raw) or {}
                    # Solo agregar datos de tareas del cronograma origen
                    for task_id, task_data in cache_data.items():
                        if task_id not in config:  # No sobrescribir datos específicos
                            config[task_id] = task_data
                except Exception:
                    pass
            
            print(f"🎨 Captured ColorType config for {len(config)} tasks from schedule '{source_schedule.Name}'")
            return config
            
        except Exception as e:
            print(f"Warning: Could not capture ColorType config: {e}")
            return {}
    
    def _apply_colortype_config_to_duplicate(self, context, source_config):
        """
        Aplica la configuración de ColorType capturada al cronograma duplicado.
        """
        try:
            import json
            import ifcopenshell.util.sequence
            
            if not source_config:
                return
            
            # Encontrar el cronograma recién creado (último "Copy of...")
            ifc_file = tool.Ifc.get()
            all_schedules = ifc_file.by_type("IfcWorkSchedule")
            duplicate_schedule = None
            
            for schedule in all_schedules:
                if schedule.Name and schedule.Name.startswith("Copy of "):
                    duplicate_schedule = schedule
                    break
            
            if not duplicate_schedule:
                print("Warning: Could not find duplicated schedule")
                return
            
            # Mapear tareas del cronograma duplicado por Identification
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
            
            # Crear mapping por Identification para encontrar tareas correspondientes
            duplicate_task_map = {}
            for task in all_duplicate_tasks:
                identification = getattr(task, "Identification", None)
                if identification:
                    duplicate_task_map[identification] = task
            
            # Aplicar configuración a las tareas duplicadas
            duplicate_ws_id = duplicate_schedule.id()
            snap_key_duplicate = f"_task_colortype_snapshot_json_WS_{duplicate_ws_id}"
            cache_key = "_task_colortype_snapshot_cache_json"
            
            # Mapear configuración origen a tareas duplicadas
            duplicate_config = {}
            for source_task_id, config_data in source_config.items():
                # Intentar encontrar la tarea correspondiente por Identification
                # (Esto funciona si las tareas tienen Identification únicos)
                for identification, duplicate_task in duplicate_task_map.items():
                    duplicate_task_id = str(duplicate_task.id())
                    if duplicate_task_id not in duplicate_config:
                        # Aplicar configuración de cualquier tarea origen a esta tarea duplicada
                        duplicate_config[duplicate_task_id] = config_data.copy()
                        break
            
            # Si no hay suficientes mapeos por Identification, aplicar secuencialmente
            if len(duplicate_config) < len(source_config):
                duplicate_task_ids = [str(task.id()) for task in all_duplicate_tasks]
                source_configs = list(source_config.values())
                
                for i, duplicate_task_id in enumerate(duplicate_task_ids):
                    if duplicate_task_id not in duplicate_config and i < len(source_configs):
                        duplicate_config[duplicate_task_id] = source_configs[i].copy()
            
            # Guardar configuración en el snapshot y caché
            context.scene[snap_key_duplicate] = json.dumps(duplicate_config)
            
            # También actualizar el caché general
            try:
                cache_raw = context.scene.get(cache_key, "{}")
                cache_data = json.loads(cache_raw) or {}
                cache_data.update(duplicate_config)
                context.scene[cache_key] = json.dumps(cache_data)
            except Exception:
                context.scene[cache_key] = json.dumps(duplicate_config)
            
            print(f"🎨 Applied ColorType config to {len(duplicate_config)} tasks in duplicated schedule '{duplicate_schedule.Name}'")
            
        except Exception as e:
            print(f"Warning: Could not apply ColorType config to duplicate: {e}")
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
        
        # --- PASO 1: LIMPIAR LA CACHÉ PERSISTENTE ---
        # Este es el paso más importante. Antes de hacer NADA, nos aseguramos
        # de que la memoria de los ColorTypes del cronograma anterior sea borrada.
        try:
            bpy.ops.bim.clear_task_state_cache()
        except Exception as e:
            print(f"Advertencia: No se pudo ejecutar bim.clear_task_state_cache(). Error: {e}")

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

