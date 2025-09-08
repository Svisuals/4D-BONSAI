import bpy
import json
import calendar
from mathutils import Matrix
from datetime import datetime, timedelta
from dateutil import relativedelta
import bonsai.tool as tool
import bonsai.core.sequence as core
import ifcopenshell.util.sequence
import ifcopenshell.util.selector
from bpy_extras.io_utils import ImportHelper, ExportHelper
from typing import TYPE_CHECKING

# --- Bloque de importaciones y fallbacks ---
try:
    from .prop import update_filter_column
    from . import prop
except Exception:
    try:
        from bonsai.bim.module.sequence.prop.filter import update_filter_column
        import bonsai.bim.module.sequence.prop as prop
    except Exception:
        def update_filter_column(*args, **kwargs): pass
        class PropFallback:
            @staticmethod
            def safe_set_selected_colortype_in_active_group(task_obj, value, skip_validation=False):
                try: setattr(task_obj, "selected_colortype_in_active_group", value)
                except Exception as e: pass
        prop = PropFallback()

# =============================================================================
# ▼▼▼ SISTEMA DE SNAPSHOT/RESTORE COMPLETO (BASADO EN V125 FUNCIONAL) ▼▼▼
# =============================================================================

# Variable global para cache de estado de tareas (usada por filtros)
_persistent_task_state = {}

def snapshot_all_ui_state(context):
    """
    Captura el estado completo de TODAS las tareas del cronograma activo.
    Basado en la v125 que funcionaba perfectamente.
    """
    import json
    try:
        # Detectar cronograma activo para usar claves específicas  
        ws_props = tool.Sequence.get_work_schedule_props()
        ws_id = int(getattr(ws_props, "active_work_schedule_id", 0))
        
        tprops = getattr(context.scene, 'BIMTaskTreeProperties', None)
        task_snap = {}
        
        # Obtener TODAS las tareas del cronograma activo (no solo visibles)
        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                import ifcopenshell.util.sequence
                
                def get_all_tasks_recursive(tasks):
                    all_tasks = []
                    for task in tasks:
                        all_tasks.append(task)
                        nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                        if nested:
                            all_tasks.extend(get_all_tasks_recursive(nested))
                    return all_tasks
                
                root_tasks = ifcopenshell.util.sequence.get_root_tasks(ws)
                all_tasks = get_all_tasks_recursive(root_tasks)
                
                # Mapear tareas visibles en la UI
                task_id_to_ui_data = {str(getattr(t, "ifc_definition_id", 0)): t for t in getattr(tprops, "tasks", [])}
                
                for task in all_tasks:
                    tid = str(task.id())
                    if tid == "0":
                        continue
                    
                    # Si la tarea está visible en la UI, usar sus datos actuales
                    if tid in task_id_to_ui_data:
                        t = task_id_to_ui_data[tid]
                        
                        # Capturar grupos de colores
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
                            # Datos adicionales para preservar estado UI
                            "is_selected": getattr(t, 'is_selected', False),
                            "is_expanded": getattr(t, 'is_expanded', False),
                        }
                    else:
                        # Si no está visible, preservar datos del caché o crear entrada vacía
                        cache_key = "_task_colortype_snapshot_cache_json"
                        cache_raw = context.scene.get(cache_key)
                        if cache_raw:
                            try:
                                cached_data = json.loads(cache_raw)
                                if tid in cached_data:
                                    task_snap[tid] = cached_data[tid]
                                else:
                                    task_snap[tid] = {
                                        "active": False,
                                        "selected_active_colortype": "",
                                        "animation_color_schemes": "",
                                        "groups": [],
                                        "is_selected": False,
                                        "is_expanded": False,
                                    }
                            except Exception:
                                task_snap[tid] = {
                                    "active": False,
                                    "selected_active_colortype": "",
                                    "animation_color_schemes": "",
                                    "groups": [],
                                    "is_selected": False,
                                    "is_expanded": False,
                                }
                        else:
                            task_snap[tid] = {
                                "active": False,
                                "selected_active_colortype": "",
                                "animation_color_schemes": "",
                                "groups": [],
                                "is_selected": False,
                                "is_expanded": False,
                            }
        except Exception as e:
            print(f"Bonsai WARNING: Error capturando todas las tareas: {e}")
            # Fallback: solo tareas visibles
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
                    "is_selected": getattr(t, 'is_selected', False),
                    "is_expanded": getattr(t, 'is_expanded', False),
                }
        
        # Guardar snapshot específico del cronograma Y actualizar caché general
        snap_key_specific = f"_task_colortype_snapshot_json_WS_{ws_id}"
        cache_key = "_task_colortype_snapshot_cache_json"
        
        context.scene[snap_key_specific] = json.dumps(task_snap)
        context.scene[cache_key] = json.dumps(task_snap)  # También actualizar caché
        
        print(f"📸 Snapshot guardado: {len(task_snap)} tareas en clave {snap_key_specific}")
        
    except Exception as e:
        print(f"Bonsai WARNING: snapshot_all_ui_state falló: {e}")

def deferred_restore_task_state():
    """
    Se ejecuta de forma diferida para restaurar el estado, evitando condiciones de carrera.
    """
    global _persistent_task_state
    if not _persistent_task_state or not bpy.context:
        return

    context = bpy.context
    tprops = getattr(context.scene, 'BIMTaskTreeProperties', None)
    if not tprops or not hasattr(tprops, 'tasks'):
        return

    for task in tprops.tasks:
        task_id = str(task.ifc_definition_id)
        if task_id in _persistent_task_state:
            saved_data = _persistent_task_state[task_id]
            try:
                # Restaurar propiedades simples
                task.is_selected = saved_data.get("is_selected", False)
                task.is_expanded = saved_data.get("is_expanded", False)
                task.use_active_colortype_group = saved_data.get("use_active_colortype_group", False)

                # Restaurar grupo activo
                saved_active_group = saved_data.get("active_colortype_group", "")
                if saved_active_group and hasattr(task, 'active_colortype_group'):
                    try:
                        task.active_colortype_group = saved_active_group
                    except Exception:
                        pass

                # Restaurar ColorType personalizado con máxima robustez
                saved_colortype = saved_data.get("selected_colortype_in_active_group", "")
                if saved_colortype:
                    try:
                        task.selected_colortype_in_active_group = saved_colortype
                    except Exception:
                        pass
                
                # Restaurar valor del grupo DEFAULT si corresponde
                saved_default_value = saved_data.get("default_group_value", "")
                if saved_default_value and hasattr(task, 'active_colortype_group'):
                    try:
                        if task.active_colortype_group == "DEFAULT" or saved_active_group == "DEFAULT":
                            task.selected_colortype_in_active_group = saved_default_value
                    except Exception:
                        pass
                
                # Restaurar PredefinedType usando el sistema de propiedades de Blender
                predefined_type_to_restore = saved_data.get("PredefinedType")
                if predefined_type_to_restore:
                    try:
                        # Método 1: A través de las propiedades del workspace
                        ws_props = tool.Sequence.get_work_schedule_props()
                        if (hasattr(ws_props, 'active_task_index') and 
                            ws_props.active_task_index < len(tprops.tasks) and 
                            tprops.tasks[ws_props.active_task_index].ifc_definition_id == task.ifc_definition_id):
                            # La tarea está activa, podemos usar task_attributes
                            if hasattr(ws_props, "task_attributes"):
                                for attr in ws_props.task_attributes:
                                    if attr.name == "PredefinedType":
                                        attr.string_value = predefined_type_to_restore
                                        break
                        else:
                            # Método 2: Modificación directa (menos confiable pero de respaldo)
                            ifc_task = tool.Ifc.get().by_id(task.ifc_definition_id)
                            if ifc_task and hasattr(ifc_task, 'PredefinedType'):
                                ifc_task.PredefinedType = predefined_type_to_restore
                    except Exception as e:
                        print(f"Warning: Could not restore PredefinedType for task {task_id}: {e}")

            except (TypeError, ReferenceError):
                # Ignoramos los errores de asignación de Enum que puedan ocurrir si la UI
                # todavía no está 100% lista, el temporizador minimiza esto.
                pass
            except Exception as e:
                pass
                
    # Forzar un redibujado de la UI para asegurar que los cambios sean visibles
    for area in context.screen.areas:
        if area.type == 'PROPERTIES':
            area.tag_redraw()
            
    return None # Finaliza el temporizador

def restore_all_ui_state(context):
    """
    Restaura el estado completo de la UI desde snapshot + caché persistente.
    Basado en la v125 que funcionaba perfectamente.
    """
    import json
    try:
        # Detectar cronograma activo para usar claves específicas
        ws_props = tool.Sequence.get_work_schedule_props()
        ws_id = int(getattr(ws_props, "active_work_schedule_id", 0))
                
        # Claves para snapshot específico y caché general
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
                print(f"📥 Restaurando de clave {snap_key_specific} - {len(snap_data)} tareas")
            except Exception:
                pass
        else:
            print(f"❌ No se encontró clave {snap_key_specific}")

        if union:
            tprops = getattr(context.scene, 'BIMTaskTreeProperties', None)
            task_map = {str(getattr(t, "ifc_definition_id", 0)): t for t in getattr(tprops, "tasks", [])}

            for tid, cfg in union.items():
                t = task_map.get(str(tid))
                if not t:
                    continue
                    
                # Restaurar estado principal de la tarea
                try:
                    t.use_active_colortype_group = cfg.get("active", False)
                    
                    # Validar y restaurar selected_active_colortype
                    selected_active_colortype = cfg.get("selected_active_colortype", "")
                    problematic_values = ["0", 0, None, "", "None", "null", "undefined"]
                    
                    if selected_active_colortype in problematic_values:
                        selected_active_colortype = ""
                    else:
                        selected_active_str = str(selected_active_colortype).strip()
                        if selected_active_str in [str(v) for v in problematic_values]:
                            selected_active_colortype = ""
                    
                    prop.safe_set_selected_colortype_in_active_group(t, selected_active_colortype, skip_validation=True)
                    
                    # Restaurar animation_color_schemes si existe la función
                    try:
                        animation_color_schemes = cfg.get("animation_color_schemes", "")
                        if hasattr(t, 'animation_color_schemes'):
                            t.animation_color_schemes = animation_color_schemes
                    except Exception:
                        pass
                    
                    # Restaurar estado UI básico
                    t.is_selected = cfg.get("is_selected", False)
                    t.is_expanded = cfg.get("is_expanded", False)
                    
                except Exception as e:
                    print(f"❌ Error setting colortype for task {tid}: {e}")
                
                # Restaurar grupos de colores
                try:
                    t.colortype_group_choices.clear()
                    for g_data in cfg.get("groups", []):
                        item = t.colortype_group_choices.add()
                        item.group_name = g_data.get("group_name", "")
                        
                        # Detectar atributo de selección del item 
                        sel_attr = None
                        for cand in ("selected_colortype", "selected", "active_colortype", "colortype"):
                            if hasattr(item, cand):
                                sel_attr = cand
                                break
                        
                        if sel_attr:
                            selected_value = g_data.get("selected_value", "")
                            if selected_value not in problematic_values:
                                setattr(item, sel_attr, selected_value)
                            
                        item.enabled = g_data.get("enabled", False)
                        
                except Exception as e:
                    print(f"❌ Error setting groups for task {tid}: {e}")
        
        print(f"🔄 Restauración completada: {len(union)} tareas procesadas")
        
    except Exception as e:
        print(f"Bonsai WARNING: restore_all_ui_state falló: {e}")

def populate_persistent_task_state_from_snapshot(context):
    """
    Llena _persistent_task_state desde los snapshots JSON de context.scene.
    Esto sincroniza los dos sistemas de memoria.
    """
    global _persistent_task_state
    
    try:
        # Buscar cronograma activo
        ws_props = tool.Sequence.get_work_schedule_props()
        ws_id = getattr(ws_props, "active_work_schedule_id", 0)
        if not ws_id:
            return
        
        # Intentar cargar desde snapshot específico del cronograma
        snap_key = f"_task_colortype_snapshot_json_WS_{ws_id}"
        snapshot_data = context.scene.get(snap_key)
        
        if snapshot_data:
            import json
            try:
                data = json.loads(snapshot_data)
                for task_id, task_data in data.items():
                    _persistent_task_state[task_id] = {
                        "is_selected": task_data.get("is_selected", False),
                        "is_expanded": task_data.get("is_expanded", False),
                        "use_active_colortype_group": task_data.get("active", False),
                        "selected_colortype_in_active_group": task_data.get("selected_active_colortype", ""),
                    }
                print(f"📥 Sincronizado _persistent_task_state desde snapshot: {len(data)} tareas")
            except Exception as e:
                print(f"⚠️ Error sincronizando desde snapshot: {e}")
                
    except Exception as e:
        print(f"⚠️ Error poblando _persistent_task_state: {e}")

def restore_persistent_task_state(context):
    """Inicia la restauración de estado de forma diferida."""
    # Primero sincronizar desde snapshots si es necesario
    populate_persistent_task_state_from_snapshot(context)
    # Luego restaurar con retardo para la UI
    bpy.app.timers.register(deferred_restore_task_state, first_interval=0.05)

class ClearTaskStateCache(bpy.types.Operator):
    bl_idname = "bim.clear_task_state_cache"; bl_label = "Clear Task State Cache"; bl_options = {"REGISTER", "INTERNAL"}
    work_schedule_id: bpy.props.IntProperty(default=0)  # Para limpieza selectiva
    
    def execute(self, context):
        global _persistent_task_state
        
        # Si no se especifica cronograma, limpiar todo (comportamiento original)
        if self.work_schedule_id == 0:
            _persistent_task_state.clear()
            print("🧹 Cache completo limpiado (modo global)")
            return {'FINISHED'}
        
        # Limpieza selectiva: solo remover tareas del cronograma especificado
        try:
            import ifcopenshell.util.sequence
            work_schedule = tool.Ifc.get().by_id(self.work_schedule_id)
            if not work_schedule:
                print(f"⚠️ Cronograma {self.work_schedule_id} no encontrado para limpieza selectiva")
                return {'FINISHED'}
            
            # Obtener todas las tareas del cronograma especificado
            def get_all_task_ids_recursive(tasks):
                all_ids = set()
                for task in tasks:
                    all_ids.add(str(task.id()))
                    nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested:
                        all_ids.update(get_all_task_ids_recursive(nested))
                return all_ids
            
            root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
            task_ids_to_clear = get_all_task_ids_recursive(root_tasks)
            
            # Remover solo las tareas de este cronograma del cache
            removed_count = 0
            for task_id in list(_persistent_task_state.keys()):
                if task_id in task_ids_to_clear:
                    del _persistent_task_state[task_id]
                    removed_count += 1
            
            print(f"🧹 Cache selectivo: {removed_count} tareas removidas del cronograma '{work_schedule.Name or 'Sin nombre'}'")
            
        except Exception as e:
            print(f"❌ Error en limpieza selectiva: {e}. Fallback a limpieza global.")
            _persistent_task_state.clear()
        
        return {'FINISHED'}

# =============================================================================
# ▲▲▲ FIN DEL SISTEMA DE MEMORIA ▲▲▲
# =============================================================================


# =============================================================================
# ▼▼▼ OPERADORES DE FILTRO DE ESTADO ▼▼▼
# =============================================================================
class EnableStatusFilters(bpy.types.Operator):
    bl_idname = "bim.enable_status_filters"; bl_label = "Enable Status Filters"; bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        props = tool.Sequence.get_status_props(); props.is_enabled = True; hidden_statuses = {s.name for s in props.statuses if not s.is_visible}; props.statuses.clear(); statuses = set()
        for element in tool.Ifc.get().by_type("IfcPropertyEnumeratedValue"):
            if element.Name == "Status":
                if element.PartOfPset and isinstance(element.EnumerationValues, tuple):
                    pset = element.PartOfPset[0]
                    if pset.Name.startswith("Pset_") and pset.Name.endswith("Common"): statuses.update(element.EnumerationValues)
                    elif pset.Name == "EPset_Status": statuses.update(element.EnumerationValues)
            elif element.Name == "UserDefinedStatus": statuses.add(element.NominalValue)
        statuses = ["No Status"] + sorted([s.wrappedValue for s in statuses])
        for status in statuses:
            new = props.statuses.add(); new.name = status
            if new.name in hidden_statuses: new.is_visible = False
        visible_statuses = {s.name for s in props.statuses if s.is_visible}; tool.Sequence.set_visibility_by_status(visible_statuses); return {"FINISHED"}

class DisableStatusFilters(bpy.types.Operator):
    bl_idname = "bim.disable_status_filters"; bl_label = "Disable Status Filters"; bl_description = "Deactivate status filters panel"; bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        props = tool.Sequence.get_status_props(); all_statuses = {s.name for s in props.statuses}; tool.Sequence.set_visibility_by_status(all_statuses); props.is_enabled = False; return {"FINISHED"}

class ActivateStatusFilters(bpy.types.Operator):
    bl_idname = "bim.activate_status_filters"; bl_label = "Activate Status Filters"; bl_description = "Filter objects based on selected IFC statuses"; bl_options = {"REGISTER", "UNDO"}; only_if_enabled: bpy.props.BoolProperty(default=False)
    def execute(self, context):
        props = tool.Sequence.get_status_props()
        if not props.is_enabled and self.only_if_enabled: return {"FINISHED"}
        visible_statuses = {s.name for s in props.statuses if s.is_visible}; tool.Sequence.set_visibility_by_status(visible_statuses); return {"FINISHED"}

class SelectStatusFilter(bpy.types.Operator):
    bl_idname = "bim.select_status_filter"; bl_label = "Select Status Filter"; bl_description = "Select elements with the specified status"; bl_options = {"REGISTER", "UNDO"}; name: bpy.props.StringProperty()
    def execute(self, context):
        query = f"IfcProduct, /Pset_.*Common/.Status={self.name} + IfcProduct, EPset_Status.Status={self.name}"
        if self.name == "No Status": query = f"IfcProduct, /Pset_.*Common/.Status=NULL, EPset_Status.Status=NULL"
        for element in ifcopenshell.util.selector.filter_elements(tool.Ifc.get(), query):
            obj = tool.Ifc.get_object(element)
            if obj: obj.select_set(True)
        return {"FINISHED"}
# =============================================================================
# ▲▲▲ FIN DE OPERADORES DE FILTRO DE ESTADO ▲▲▲
# =============================================================================


# =============================================================================
# ▼▼▼ OPERADORES DE FILTRO DE TAREAS ▼▼▼
# =============================================================================
class ApplyTaskFilters(bpy.types.Operator):
    bl_idname = "bim.apply_task_filters"; bl_label = "Apply Task Filters"; bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        # SISTEMA V125 FUNCIONAL: Snapshot → Recarga → Restore
        try:
            snapshot_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: snapshot_all_ui_state falló: {e}")
        
        # Recarga destructiva de tareas
        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws: 
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties()
        except Exception as e: 
            print(f"Bonsai WARNING: Task tree reload failed: {e}")
        
        # Restaurar estado completo
        try:
            restore_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: restore_all_ui_state falló: {e}")
        
        # Lógica de colores de varianza
        try:
            if not tool.Sequence.has_variance_calculation_in_tasks(): 
                tool.Sequence.clear_variance_colors_only()
        except Exception as e: 
            print(f"⚠️ Error in variance color check: {e}")
        
        return {'FINISHED'}

class AddTaskFilter(bpy.types.Operator):
    bl_idname = "bim.add_task_filter"; bl_label = "Add Task Filter"; bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props(); new_rule = props.filters.rules.add(); new_rule.column = "IfcTask.Name||string"; update_filter_column(new_rule, context); props.filters.active_rule_index = len(props.filters.rules) - 1; return {'FINISHED'}

class RemoveTaskFilter(bpy.types.Operator):
    bl_idname = "bim.remove_task_filter"; bl_label = "Remove Task Filter"; bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props(); index = props.filters.active_rule_index
        if 0 <= index < len(props.filters.rules):
            props.filters.rules.remove(index); props.filters.active_rule_index = min(max(0, index - 1), len(props.filters.rules) - 1)
            if len(props.filters.rules) == 0: props.last_lookahead_window = ""
            bpy.ops.bim.apply_task_filters()
        return {'FINISHED'}

class ClearAllTaskFilters(bpy.types.Operator):
    bl_idname = "bim.clear_all_task_filters"; bl_label = "Clear All Filters"; bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props(); props.filters.rules.clear(); props.filters.active_rule_index = 0; props.last_lookahead_window = ""; bpy.ops.bim.apply_task_filters(); self.report({'INFO'}, "All filters cleared"); return {'FINISHED'}

class ApplyLookaheadFilter(bpy.types.Operator):
    bl_idname = "bim.apply_lookahead_filter"; bl_label = "Apply Lookahead Filter"; bl_options = {"REGISTER", "UNDO"}
    time_window: bpy.props.EnumProperty(name="Time Window", items=[('THIS_WEEK', "This Week", ""), ('LAST_WEEK', "Last Week", ""), ("1_WEEK", "Next 1 Week", ""), ("2_WEEKS", "Next 2 Weeks", ""), ("4_WEEKS", "Next 4 Weeks", ""), ("6_WEEKS", "Next 6 Weeks", ""), ("12_WEEKS", "Next 12 Weeks", "")])
    def execute(self, context):
        active_schedule = tool.Sequence.get_active_work_schedule()
        if not active_schedule: self.report({'ERROR'}, "No active work schedule."); return {'CANCELLED'}
        if not ifcopenshell.util.sequence.get_root_tasks(active_schedule): self.report({'WARNING'}, "The active schedule has no tasks."); return {'CANCELLED'}
        props = tool.Sequence.get_work_schedule_props(); props.last_lookahead_window = self.time_window; props.filters.rules.clear(); date_source = getattr(props, "date_source_type", "SCHEDULE"); date_prefix = date_source.capitalize(); start_column = f"IfcTaskTime.{date_prefix}Start||date"; finish_column = f"IfcTaskTime.{date_prefix}Finish||date"; today = datetime.now()
        if self.time_window == 'THIS_WEEK': filter_start = today - timedelta(days=today.weekday()); filter_end = filter_start + timedelta(days=6)
        elif self.time_window == 'LAST_WEEK': filter_start = today - timedelta(days=today.weekday(), weeks=1); filter_end = filter_start + timedelta(days=6)
        else: weeks = int(self.time_window.split('_')[0]); filter_start = today; filter_end = today + timedelta(weeks=weeks)
        rule1 = props.filters.rules.add(); rule1.is_active = True; rule1.column = start_column; rule1.operator = "LTE"; rule1.value_string = filter_end.strftime("%Y-%m-%d")
        rule2 = props.filters.rules.add(); rule2.is_active = True; rule2.column = finish_column; rule2.operator = "GTE"; rule2.value_string = filter_start.strftime("%Y-%m-%d")
        props.filters.logic = "AND"; tool.Sequence.update_visualisation_date(filter_start, filter_end); bpy.ops.bim.apply_task_filters(); self.report({"INFO"}, f"Filter applied: {self.time_window.replace('_', ' ')}"); return {"FINISHED"}

# =============================================================================
# ▼▼▼ OPERADORES DE SETS DE FILTROS ▼▼▼
# =============================================================================
class UpdateSavedFilterSet(bpy.types.Operator):
    bl_idname = "bim.update_saved_filter_set"; bl_label = "Update Saved Filter Set"; bl_options = {"REGISTER", "UNDO"}; set_index: bpy.props.IntProperty()
    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props(); saved_set = props.saved_filter_sets[self.set_index]; saved_set.rules.clear()
        for active_rule in props.filters.rules:
            saved_rule = saved_set.rules.add(); saved_rule.is_active = active_rule.is_active; saved_rule.column = active_rule.column; saved_rule.operator = active_rule.operator; saved_rule.value_string = active_rule.value_string; saved_rule.data_type = active_rule.data_type
        self.report({'INFO'}, f"Filter '{saved_set.name}' updated."); return {'FINISHED'}

class SaveFilterSet(bpy.types.Operator):
    bl_idname = "bim.save_filter_set"; bl_label = "Save Filter Set"; bl_options = {"REGISTER", "UNDO"}; set_name: bpy.props.StringProperty(name="Name", description="Name for this filter set")
    def execute(self, context):
        if not self.set_name.strip(): self.report({'ERROR'}, "Name cannot be empty."); return {'CANCELLED'}
        props = tool.Sequence.get_work_schedule_props(); new_set = props.saved_filter_sets.add(); new_set.name = self.set_name
        for active_rule in props.filters.rules:
            saved_rule = new_set.rules.add(); saved_rule.is_active = active_rule.is_active; saved_rule.column = active_rule.column; saved_rule.operator = active_rule.operator; saved_rule.value_string = active_rule.value_string; saved_rule.data_type = active_rule.data_type
        self.report({'INFO'}, f"Filter '{self.set_name}' saved."); return {'FINISHED'}
    def invoke(self, context, event): return context.window_manager.invoke_props_dialog(self)

class LoadFilterSet(bpy.types.Operator):
    bl_idname = "bim.load_filter_set"; bl_label = "Load Filter Set"; bl_options = {"REGISTER", "UNDO"}; set_index: bpy.props.IntProperty()
    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        if not (0 <= self.set_index < len(props.saved_filter_sets)): self.report({'ERROR'}, "Invalid filter index."); return {'CANCELLED'}
        saved_set = props.saved_filter_sets[self.set_index]; props.filters.rules.clear()
        for saved_rule in saved_set.rules:
            active_rule = props.filters.rules.add(); active_rule.is_active = saved_rule.is_active; active_rule.column = saved_rule.column; active_rule.operator = saved_rule.operator; active_rule.value_string = saved_rule.value_string; active_rule.data_type = saved_rule.data_type
        bpy.ops.bim.apply_task_filters(); return {'FINISHED'}

class RemoveFilterSet(bpy.types.Operator):
    bl_idname = "bim.remove_filter_set"; bl_label = "Remove Filter Set"; bl_options = {"REGISTER", "UNDO"}; set_index: bpy.props.IntProperty()
    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        if not (0 <= self.set_index < len(props.saved_filter_sets)): self.report({'ERROR'}, "Invalid filter index."); return {'CANCELLED'}
        set_name = props.saved_filter_sets[self.set_index].name; props.saved_filter_sets.remove(self.set_index); props.active_saved_filter_set_index = min(max(0, self.set_index - 1), len(props.saved_filter_sets) - 1); self.report({'INFO'}, f"Filter '{set_name}' removed."); return {'FINISHED'}

class ExportFilterSet(bpy.types.Operator, ExportHelper):
    bl_idname = "bim.export_filter_set"; bl_label = "Export Filter Library"; bl_description = "Export all saved filters to a JSON file"; filename_ext = ".json"; filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})
    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props(); library_data = {}
        for saved_set in props.saved_filter_sets:
            rules_data = []
            for rule in saved_set.rules: rules_data.append({"is_active": rule.is_active, "column": rule.column, "operator": rule.operator, "value": rule.value})
            library_data[saved_set.name] = {"rules": rules_data}
        with open(self.filepath, 'w', encoding='utf-8') as f: json.dump(library_data, f, ensure_ascii=False, indent=4)
        self.report({'INFO'}, f"Filter library exported to {self.filepath}"); return {'FINISHED'}

class ImportFilterSet(bpy.types.Operator, ImportHelper):
    bl_idname = "bim.import_filter_set"; bl_label = "Import Filter Library"; bl_description = "Import filters from a JSON file"; filename_ext = ".json"; filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})
    def execute(self, context):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f: library_data = json.load(f)
        except Exception as e: self.report({'ERROR'}, f"Could not read JSON file: {e}"); return {'CANCELLED'}
        props = tool.Sequence.get_work_schedule_props(); existing_names = {fs.name for fs in props.saved_filter_sets}; imported_count = 0
        for set_name, set_data in library_data.items():
            if set_name in existing_names: continue
            new_set = props.saved_filter_sets.add(); new_set.name = set_name
            for rule_data in set_data.get("rules", []):
                new_rule = new_set.rules.add(); new_rule.is_active = rule_data.get("is_active", True); new_rule.column = rule_data.get("column", ""); new_rule.operator = rule_data.get("operator", "CONTAINS"); new_rule.value = rule_data.get("value", "")
            imported_count += 1
        self.report({'INFO'}, f"{imported_count} new filter sets imported."); return {'FINISHED'}

# =============================================================================
# ▼▼▼ OPERADORES DE DATE PICKER ▼▼▼
# =============================================================================
class Bonsai_DatePicker(bpy.types.Operator):
    bl_label = "Date Picker"; bl_idname = "bim.datepicker"; bl_options = {"REGISTER", "UNDO"}; target_prop: bpy.props.StringProperty(name="Target date prop to set"); include_time: bpy.props.BoolProperty(name="Include Time", default=True)
    def execute(self, context):
        selected_date = context.scene.DatePickerProperties.selected_date
        try: tool.Sequence.parse_isodate_datetime(selected_date, self.include_time); self.set_scene_prop(self.target_prop, selected_date); return {"FINISHED"}
        except Exception as e: self.report({"ERROR"}, f"Invalid date: '{selected_date}'. Error: {str(e)}."); return {"CANCELLED"}
    def draw(self, context):
        props = context.scene.DatePickerProperties; display_date = tool.Sequence.parse_isodate_datetime(props.display_date, False); current_month = (display_date.year, display_date.month); lines = calendar.monthcalendar(*current_month); month_title, week_titles = calendar.month(*current_month).splitlines()[:2]; layout = self.layout; row = layout.row(); row.prop(props, "selected_date", text="Date")
        if self.include_time: row = layout.row(); row.label(text="Time:"); row.prop(props, "selected_hour", text="H"); row.prop(props, "selected_min", text="M"); row.prop(props, "selected_sec", text="S")
        month_delta = relativedelta.relativedelta(months=1); split = layout.split(); col = split.row(); op = col.operator("wm.context_set_string", icon="TRIA_LEFT", text=""); op.data_path = "scene.DatePickerProperties.display_date"; op.value = tool.Sequence.isodate_datetime(display_date - month_delta, False)
        col = split.row(); col.label(text=month_title.strip()); col = split.row(); col.alignment = "RIGHT"; op = col.operator("wm.context_set_string", icon="TRIA_RIGHT", text=""); op.data_path = "scene.DatePickerProperties.display_date"; op.value = tool.Sequence.isodate_datetime(display_date + month_delta, False)
        row = layout.row(align=True)
        for title in week_titles.split(): col = row.column(align=True); col.alignment = "CENTER"; col.label(text=title.strip())
        current_selected_date = tool.Sequence.parse_isodate_datetime(props.selected_date, self.include_time); current_selected_date = current_selected_date.replace(hour=0, minute=0, second=0)
        for line in lines:
            row = layout.row(align=True)
            for i in line:
                col = row.column(align=True)
                if i == 0: col.label(text="  ")
                else:
                    selected_date = datetime(year=display_date.year, month=display_date.month, day=i); is_current_date = current_selected_date == selected_date; op = col.operator("wm.context_set_string", text="{:2d}".format(i), depress=is_current_date)
                    if self.include_time: selected_date = selected_date.replace(hour=props.selected_hour, minute=props.selected_min, second=props.selected_sec)
                    op.data_path = "scene.DatePickerProperties.selected_date"; op.value = tool.Sequence.isodate_datetime(selected_date, self.include_time)
    def invoke(self, context, event):
        props = context.scene.DatePickerProperties; current_date_str = self.get_scene_prop(self.target_prop); current_date = None
        if current_date_str: 
            try: current_date = tool.Sequence.parse_isodate_datetime(current_date_str, self.include_time)
            except: pass
        if current_date is None: current_date = datetime.now(); current_date = current_date.replace(second=0)
        if self.include_time: props["selected_hour"] = current_date.hour; props["selected_min"] = current_date.minute; props["selected_sec"] = current_date.second
        props.display_date = tool.Sequence.isodate_datetime(current_date.replace(day=1), False); props.selected_date = tool.Sequence.isodate_datetime(current_date, self.include_time); return context.window_manager.invoke_props_dialog(self)
    def get_scene_prop(self, prop_path: str) -> str: return bpy.context.scene.path_resolve(prop_path)
    def set_scene_prop(self, prop_path: str, value: str) -> None: tool.Blender.set_prop_from_path(bpy.context.scene, prop_path, value)

class FilterDatePicker(bpy.types.Operator):
    bl_idname = "bim.filter_datepicker"; bl_label = "Select Filter Date"; bl_options = {"REGISTER", "UNDO"}; rule_index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        if self.rule_index < 0 or self.rule_index >= len(props.filters.rules): self.report({'ERROR'}, "Invalid filter rule index."); return {'CANCELLED'}
        selected_date_str = context.scene.DatePickerProperties.selected_date
        if not selected_date_str: self.report({'ERROR'}, "No date selected."); return {'CANCELLED'}
        target_rule = props.filters.rules[self.rule_index]; target_rule.value_string = selected_date_str
        try: bpy.ops.bim.apply_task_filters()
        except Exception as e: print(f"Error applying filters: {e}")
        self.report({'INFO'}, f"Date set to: {selected_date_str}"); return {"FINISHED"}
    def invoke(self, context, event):
        if self.rule_index < 0: self.report({'ERROR'}, "No rule index specified."); return {'CANCELLED'}
        props = tool.Sequence.get_work_schedule_props()
        if self.rule_index >= len(props.filters.rules): self.report({'ERROR'}, "Invalid filter rule index."); return {'CANCELLED'}
        current_date_str = props.filters.rules[self.rule_index].value_string; date_picker_props = context.scene.DatePickerProperties
        if current_date_str and current_date_str.strip():
            try: current_date = datetime.fromisoformat(current_date_str.split('T')[0])
            except Exception:
                try: from dateutil import parser as date_parser; current_date = date_parser.parse(current_date_str)
                except Exception: current_date = datetime.now()
        else: current_date = datetime.now()
        date_picker_props.selected_date = current_date.strftime("%Y-%m-%d"); date_picker_props.display_date = current_date.replace(day=1).strftime("%Y-%m-%d"); return context.window_manager.invoke_props_dialog(self, width=350)
    def draw(self, context):
        layout = self.layout; props = context.scene.DatePickerProperties
        try: display_date = datetime.fromisoformat(props.display_date)
        except Exception: display_date = datetime.now(); props.display_date = display_date.strftime("%Y-%m-%d")
        row = layout.row(); row.prop(props, "selected_date", text="Date"); current_month = (display_date.year, display_date.month); lines = calendar.monthcalendar(*current_month); month_title = calendar.month_name[display_date.month] + f" {display_date.year}"; row = layout.row(align=True)
        prev_month = display_date - relativedelta.relativedelta(months=1); op = row.operator("wm.context_set_string", icon="TRIA_LEFT", text=""); op.data_path = "scene.DatePickerProperties.display_date"; op.value = prev_month.strftime("%Y-%m-%d")
        row.label(text=month_title)
        next_month = display_date + relativedelta.relativedelta(months=1); op = row.operator("wm.context_set_string", icon="TRIA_RIGHT", text=""); op.data_path = "scene.DatePickerProperties.display_date"; op.value = next_month.strftime("%Y-%m-%d")
        row = layout.row(align=True)
        for day_name in ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']: col = row.column(align=True); col.alignment = "CENTER"; col.label(text=day_name)
        try: selected_date = datetime.fromisoformat(props.selected_date)
        except Exception: selected_date = None
        for week in lines:
            row = layout.row(align=True)
            for day in week:
                col = row.column(align=True)
                if day == 0: col.label(text="")
                else:
                    day_date = datetime(display_date.year, display_date.month, day); day_str = day_date.strftime("%Y-%m-%d"); is_selected = (selected_date and day_date.date() == selected_date.date()); op = col.operator("wm.context_set_string", text=str(day), depress=is_selected); op.data_path = "scene.DatePickerProperties.selected_date"; op.value = day_str