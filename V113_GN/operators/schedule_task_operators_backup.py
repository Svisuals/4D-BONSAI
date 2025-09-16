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
    """Simple v60-style snapshot - just save ColorTypes"""
    from .simple_colortype_persistence import save_colortypes_simple
    save_colortypes_simple()


def restore_all_ui_state(context):
    """Simple v60-style restore - just restore ColorTypes"""
    from .simple_colortype_persistence import restore_colortypes_simple
    restore_colortypes_simple()


def _save_3d_texts_state():
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
                tool.Sequence.load_task_properties(task=None)
        except Exception:
            pass

        restore_all_ui_state(context)


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
                tool.Sequence.load_task_properties(task=None)
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
                tool.Sequence.load_task_properties(task=None)
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
        # USAR EL MISMO PATRÓN QUE LOS FILTROS (que funciona correctamente):
        snapshot_all_ui_state(context)  # >>> 1. Guardar estado ANTES de cancelar
        
        # >>> 2. Ejecutar la operación de cancelar usando llamada directa
        print("🔍 DEBUG: Llamando core.disable_editing_task con tool.Sequence")
        # Necesitamos usar core porque disable_editing_task no está en nuestras clases
        core.disable_editing_task(tool.Sequence)
        
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
                tool.Sequence.load_task_properties(task=None)
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
                tool.Sequence.load_task_properties(task=None)
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

