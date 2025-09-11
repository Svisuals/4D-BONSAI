import bpy
import json
import calendar
from mathutils import Matrix
from datetime import datetime
from dateutil import relativedelta
import bonsai.tool as tool
import bonsai.core.sequence as core

try:
    from ..prop.task import safe_set_selected_colortype_in_active_group
    # ... otras importaciones de ..prop
except (ImportError, ValueError):
    # Fallback si la estructura cambia
    try:
        from ..prop.animation import safe_set_selected_colortype_in_active_group
    except ImportError:
        # Ultimate fallback
        def safe_set_selected_colortype_in_active_group(task_obj, value, skip_validation=False):
            try:
                setattr(task_obj, "selected_colortype_in_active_group", value)
            except Exception:
                pass

try:
    from ..prop import update_filter_column
    from .. import prop
    from .ui import calculate_visible_columns_count
except Exception:
    try:
        from ..prop.filter import update_filter_column
        from .. import prop as prop
        from ..ui import calculate_visible_columns_count
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
                except Exception as e:
                    print(f"❌ DEBUG RESTORE: Error restoring groups for task {tid}: {e}")

        # 2. Restaurar configuración de los selectores de grupo de animación
        anim_raw = context.scene.get("_anim_state_snapshot_json")
        if anim_raw:
            try:
                anim_data = json.loads(anim_raw) or {}
                anim_props = tool.Sequence.get_animation_props()

                # Restaurar selector principal de grupo
                colortype_groups = anim_data.get("ColorType_groups", "DEFAULT")
                if hasattr(anim_props, "ColorType_groups"):
                    anim_props.ColorType_groups = colortype_groups

                # Restaurar selector del árbol de tareas
                task_group_selector = anim_data.get("task_colortype_group_selector", "")
                if hasattr(anim_props, "task_colortype_group_selector"):
                    anim_props.task_colortype_group_selector = task_group_selector

                # Restaurar stack de grupos de animación
                stack_data = anim_data.get("animation_group_stack", [])
                if hasattr(anim_props, "animation_group_stack"):
                    anim_props.animation_group_stack.clear()
                    for item_data in stack_data:
                        item = anim_props.animation_group_stack.add()
                        item.group = item_data.get("group", "")
                        item.enabled = bool(item_data.get("enabled", False))

            except Exception as e:
                print(f"Bonsai WARNING: Error restaurando selectores de animación: {e}")

        # 3. Restaurar selección/índice activo del árbol de tareas
        try:
            sel_raw = context.scene.get('_task_selection_snapshot_json')
            if sel_raw:
                sel_data = json.loads(sel_raw) or {}
                wprops = tool.Sequence.get_work_schedule_props()
                tprops = tool.Sequence.get_task_tree_props()

                # Restaurar índices activos
                active_idx = sel_data.get('active_index', -1)
                active_id = sel_data.get('active_id', 0)
                if hasattr(wprops, 'active_task_index'):
                    wprops.active_task_index = max(active_idx, -1)
                if hasattr(wprops, 'active_task_id'):
                    wprops.active_task_id = max(active_id, 0)

                # Restaurar selecciones de tareas
                selected_ids = set(sel_data.get('selected_ids', []))
                task_map = {int(getattr(t, 'ifc_definition_id', 0)): t for t in getattr(tprops, 'tasks', [])}

                for tid, t in task_map.items():
                    is_selected = tid in selected_ids
                    # Intentar múltiples nombres de atributo
                    for cand in ('is_selected', 'selected'):
                        if hasattr(t, cand):
                            try:
                                setattr(t, cand, is_selected)
                                break
                            except Exception:
                                pass
        except Exception as e:
            print(f"Bonsai WARNING: Error restaurando selección de tareas: {e}")

    except Exception as e:
        print(f"Bonsai WARNING: No se pudo restaurar el estado de la UI: {e}")


# ============================================================================
# CORE TASK MANAGEMENT OPERATORS
# ============================================================================

class LoadTaskProperties(bpy.types.Operator):
    bl_idname = "bim.load_task_properties"
    bl_label = "Load Task Properties"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.load_task_properties(tool.Sequence)
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
        bpy.ops.bim.refresh_animation_view()


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


class ContractTask(bpy.types.Operator):
    bl_idname = "bim.contract_task"
    bl_label = "Contract Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        snapshot_all_ui_state(context)

        core.contract_task(tool.Sequence, task=tool.Ifc.get().by_id(self.task))

        return {'FINISHED'}


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
        # Save UI state before canceling edit
        snapshot_all_ui_state(context)
        
        try:
            # Execute the core cancel operation
            core.disable_editing_task(tool.Sequence)
            
            # Restore UI state after canceling - this is what was missing!
            restore_all_ui_state(context)
            
            # Refresh the interface
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                    
        except Exception as e:
            self.report({'ERROR'}, f"Failed to cancel task editing: {str(e)}")
            return {"CANCELLED"}
        
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


class GoToTask(bpy.types.Operator):
    bl_idname = "bim.go_to_task"
    bl_label = "Highlight Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        print(f"🚀 GoToTask operator executed with task ID: {self.task}")
        try:
            task_entity = tool.Ifc.get().by_id(self.task)
            print(f"📋 Retrieved task entity: {task_entity} (Name: {getattr(task_entity, 'Name', 'N/A')})")
            r = core.go_to_task(tool.Sequence, task=task_entity)
            if isinstance(r, str):
                print(f"⚠️ GoToTask returned warning: {r}")
                self.report({"WARNING"}, r)
            else:
                print(f"✅ GoToTask completed successfully")
        except Exception as e:
            print(f"❌ Error in GoToTask operator: {e}")
            import traceback
            traceback.print_exc()
            self.report({"ERROR"}, f"Error: {e}")
        return {"FINISHED"}


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

