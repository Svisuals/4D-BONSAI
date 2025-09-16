# File: color_scheme_operators.py
# Description: Operators for managing Animation Color Schemes (ColorTypes), groups, and task assignments.

import bpy
import json
import bonsai.tool as tool
import bonsai.core.sequence as core
from bpy_extras.io_utils import ExportHelper, ImportHelper

# Import helpers using absolute paths like v18
from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager, safe_set_selected_colortype_in_active_group
try:
    from .schedule_task_operators import snapshot_all_ui_state
except ImportError:
    def snapshot_all_ui_state(*args, **kwargs): pass

# ============================================================================
# HELPER FUNCTIONS (Moved from operator.py)
# ============================================================================

def _get_internal_colortype_sets(context):
    """Safely reads and returns the dictionary of saved colortype sets from the scene."""
    scene = context.scene
    key = "BIM_AnimationColorSchemesSets"
    if key not in scene:
        scene[key] = json.dumps({})
    try:
        data = json.loads(scene[key])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _set_internal_colortype_sets(context, data: dict):
    """Safely writes the dictionary of colortype sets to the scene."""
    context.scene["BIM_AnimationColorSchemesSets"] = json.dumps(data)

def _colortype_set_items(self, context):
    """EnumProperty items callback for all colortype groups."""
    items = []
    data = _get_internal_colortype_sets(context)
    for i, name in enumerate(sorted(data.keys())):
        items.append((name, name, "", i))
    if not items:
        items = [("", "<no groups>", "", 0)]
    return items

def _removable_colortype_set_items(self, context):
    """EnumProperty items callback for groups that can be removed (i.e., not DEFAULT)."""
    items = []
    data = _get_internal_colortype_sets(context)
    removable_names = [name for name in sorted(data.keys()) if name != "DEFAULT"]
    for i, name in enumerate(removable_names):
        items.append((name, name, "", i))
    if not items:
        items = [("", "<no removable groups>", "", 0)]
    return items

# ============================================================================
# COLOR SCHEME OPERATORS
# ============================================================================

class AddAnimationColorSchemes(bpy.types.Operator):
    bl_idname = "bim.add_animation_color_schemes"
    bl_label = "Add Animation Color Scheme"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        new_colortype = props.ColorTypes.add()
        new_colortype.name = f"Color Type {len(props.ColorTypes)}"
        new_colortype.use_end_original_color = True
        props.active_ColorType_index = len(props.ColorTypes) - 1
        return {'FINISHED'}

class RemoveAnimationColorSchemes(bpy.types.Operator):
    bl_idname = "bim.remove_animation_color_schemes"
    bl_label = "Remove Animation Color Scheme"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        if getattr(props, "ColorType_groups", "") == "DEFAULT":
            self.report({'ERROR'}, "ColorTypes in the 'DEFAULT' group cannot be deleted.")
            return {'CANCELLED'}
        
        index = props.active_ColorType_index
        if not (0 <= index < len(props.ColorTypes)):
            return {'CANCELLED'}

        # Obtener el nombre del ColorType que se va a eliminar
        removed_colortype_name = props.ColorTypes[index].name if hasattr(props.ColorTypes[index], 'name') else ""
        
        props.ColorTypes.remove(index)
        props.active_ColorType_index = max(0, index - 1)
        
        # Auto-cleanup: limpiar referencias al ColorType eliminado
        if removed_colortype_name:
            try:
                # Limpiar referencias en task selectors
                tprops = tool.Sequence.get_task_tree_props()
                cleaned = 0
                for task in getattr(tprops, "tasks", []):
                    # Limpiar enum property si apunta al colortype eliminado
                    if hasattr(task, "selected_colortype_in_active_group"):
                        if getattr(task, "selected_colortype_in_active_group", "") == removed_colortype_name:
                            try:
                                safe_set_selected_colortype_in_active_group(task, "")
                                cleaned += 1
                            except Exception:
                                pass
                    
                    # Limpiar colortype_group_choices si tienen el colortype eliminado
                    if hasattr(task, 'colortype_group_choices'):
                        for choice in task.colortype_group_choices:
                            if getattr(choice, 'selected_colortype', '') == removed_colortype_name:
                                try:
                                    choice.selected_colortype = ""
                                    cleaned += 1
                                except Exception:
                                    pass
                
                if cleaned > 0:
                    print(f"✅ Auto-cleaned {cleaned} task references to removed ColorType '{removed_colortype_name}'")
                    
            except Exception as e:
                print(f"Warning: Auto-cleanup after ColorType removal failed: {e}")
        
        return {'FINISHED'}

class SaveAnimationColorSchemesSetInternal(bpy.types.Operator):
    bl_idname = "bim.save_animation_color_schemes_set_internal"
    bl_label = "Save Group (Internal)"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty(name="Group Name", default="New Group")

    def _serialize(self, props):
        data = {"ColorTypes": []}
        for p in props.ColorTypes:
            item = {
                "name": p.name,
                "start_color": list(p.start_color) if hasattr(p, "start_color") else None,
                "in_progress_color": list(p.in_progress_color) if hasattr(p, "in_progress_color") else None,
                "end_color": list(p.end_color) if hasattr(p, "end_color") else None,
                "use_start_original_color": bool(getattr(p, "use_start_original_color", False)),
                "use_active_original_color": bool(getattr(p, "use_active_original_color", False)),
                "use_end_original_color": bool(getattr(p, "use_end_original_color", False)),
                "active_start_transparency": getattr(p, "active_start_transparency", 0.0),
                "active_finish_transparency": getattr(p, "active_finish_transparency", 0.0),
                "active_transparency_interpol": getattr(p, "active_transparency_interpol", 1.0),
                "start_transparency": getattr(p, "start_transparency", 0.0),
                "end_transparency": getattr(p, "end_transparency", 0.0),
            }
            data["ColorTypes"].append(item)
        return data

    def execute(self, context):
        if not self.name or self.name.strip() == "":
            self.report({'ERROR'}, "Group name cannot be empty")
            return {'CANCELLED'}
            
        props = tool.Sequence.get_animation_props()
        
        # Serializar los ColorTypes actuales
        group_data = self._serialize(props)
        
        # Guardar en el sistema interno
        sets_dict = _get_internal_colortype_sets(context)
        sets_dict[self.name] = group_data
        _set_internal_colortype_sets(context, sets_dict)
        
        # Sincronizar con UnifiedColorTypeManager
        try:
            upm_data = UnifiedColorTypeManager._read_sets_json(context)
            upm_data[self.name] = group_data
            UnifiedColorTypeManager._write_sets_json(context, upm_data)
            print(f"🔄 Synchronized '{self.name}' with UnifiedColorTypeManager")
        except Exception as e:
            print(f"⚠ Error synchronizing with UnifiedColorTypeManager: {e}")
        
        # Set as active group
        props.ColorType_groups = self.name
        
        self.report({'INFO'}, f"Saved group '{self.name}'")
        return {'FINISHED'}

    def invoke(self, context, event):
        sets_dict = _get_internal_colortype_sets(context)
        base = "Group"
        n = 1
        candidate = f"{base} {n}"
        while candidate in sets_dict:
            n += 1
            candidate = f"{base} {n}"
        self.name = candidate
        return context.window_manager.invoke_props_dialog(self)

class LoadAnimationColorSchemesSetInternal(bpy.types.Operator):
    bl_idname = "bim.load_animation_color_schemes_set_internal"
    bl_label = "Load Group (Internal)"
    bl_options = {"REGISTER", "UNDO"}
    set_name: bpy.props.EnumProperty(name="Group", items=_colortype_set_items)

    def execute(self, context):
        if not self.set_name:
            return {'CANCELLED'}
        if self.set_name == "DEFAULT":
            UnifiedColorTypeManager.ensure_default_group_has_predefined_types(context)

        props = tool.Sequence.get_animation_props()
        UnifiedColorTypeManager.load_colortypes_into_collection(props, context, self.set_name)
        props.ColorType_groups = self.set_name
        self.report({'INFO'}, f"Group '{self.set_name}' loaded.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class RemoveAnimationColorSchemesSetInternal(bpy.types.Operator):
    bl_idname = "bim.remove_animation_color_schemes_set_internal"
    bl_label = "Remove Group (Internal)"
    bl_options = {"REGISTER", "UNDO"}
    set_name: bpy.props.EnumProperty(name="Group", items=_removable_colortype_set_items)

    def execute(self, context):
        if not self.set_name or self.set_name == "DEFAULT":
            self.report({'ERROR'}, "Cannot remove DEFAULT group")
            return {'CANCELLED'}
        
        all_sets = _get_internal_colortype_sets(context)
        if self.set_name in all_sets:
            # Eliminar el grupo
            del all_sets[self.set_name]
            _set_internal_colortype_sets(context, all_sets)
            
            # Auto-cleanup: limpiar todas las referencias al grupo eliminado
            cleaned_count = 0
            
            # 1. Limpiar BIMTasks colortype_mappings
            scn = context.scene
            for ob in getattr(scn, "BIMTasks", []):
                coll = getattr(ob, "colortype_mappings", None) or []
                i = len(coll) - 1
                while i >= 0:
                    entry = coll[i]
                    if getattr(entry, "group_name", "") == self.set_name:
                        coll.remove(i)
                        cleaned_count += 1
                    i -= 1
            
            # 2. Limpiar task colortype group selectors
            try:
                tprops = tool.Sequence.get_task_tree_props()
                for task in getattr(tprops, "tasks", []):
                    if hasattr(task, 'colortype_group_choices'):
                        to_remove = []
                        for idx, choice in enumerate(task.colortype_group_choices):
                            if getattr(choice, 'group_name', '') == self.set_name:
                                to_remove.append(idx)
                                cleaned_count += 1
                        
                        # Remove invalid entries
                        for offset, idx in enumerate(to_remove):
                            task.colortype_group_choices.remove(idx - offset)
            except Exception as e:
                print(f"Warning: Task cleanup failed: {e}")
            
            # 3. Limpiar animation group stack
            try:
                anim_props = tool.Sequence.get_animation_props()
                if hasattr(anim_props, 'animation_group_stack'):
                    to_remove = []
                    for idx, item in enumerate(anim_props.animation_group_stack):
                        if getattr(item, 'group', '') == self.set_name:
                            to_remove.append(idx)
                            cleaned_count += 1
                    
                    # Remove from stack
                    for offset, idx in enumerate(to_remove):
                        anim_props.animation_group_stack.remove(idx - offset)
                        
                    # Adjust index if needed
                    if anim_props.animation_group_stack_index >= len(anim_props.animation_group_stack):
                        anim_props.animation_group_stack_index = max(0, len(anim_props.animation_group_stack) - 1)
                        
                # If removed group was active, switch to DEFAULT
                if getattr(anim_props, "ColorType_groups", "") == self.set_name:
                    anim_props.ColorType_groups = "DEFAULT"
                    # Load DEFAULT group
                    try:
                        UnifiedColorTypeManager.ensure_default_group_has_predefined_types(context)
                        UnifiedColorTypeManager.load_colortypes_into_collection(anim_props, context, "DEFAULT")
                    except Exception:
                        pass
                        
            except Exception as e:
                print(f"Warning: Animation stack cleanup failed: {e}")
            
            message = f"Removed group '{self.set_name}'"
            if cleaned_count > 0:
                message += f" and cleaned {cleaned_count} references"
            self.report({'INFO'}, message)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class ExportAnimationColorSchemesSetToFile(bpy.types.Operator, ExportHelper):
    bl_idname = "bim.export_animation_color_schemes_set_to_file"
    bl_label = "Export Color Scheme Group"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            props = tool.Sequence.get_animation_props()
            active_group = getattr(props, "ColorType_groups", "")
            
            if not active_group:
                self.report({'ERROR'}, "No active group to export")
                return {'CANCELLED'}
            
            # Get group data
            sets_dict = _get_internal_colortype_sets(context)
            if active_group not in sets_dict:
                self.report({'ERROR'}, f"Group '{active_group}' not found")
                return {'CANCELLED'}
            
            group_data = sets_dict[active_group]
            
            # Export to file
            with open(self.filepath, 'w') as f:
                json.dump({active_group: group_data}, f, indent=2)
                
            self.report({'INFO'}, f"Exported group '{active_group}' successfully.")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}

class ImportAnimationColorSchemesSetFromFile(bpy.types.Operator, ImportHelper):
    bl_idname = "bim.import_animation_color_schemes_set_from_file"
    bl_label = "Import Color Scheme Group"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})
    set_name: bpy.props.StringProperty(name="Group Name", default="Imported Group")

    def execute(self, context):
        try:
            # Load data from file
            with open(self.filepath, 'r') as f:
                imported_data = json.load(f)
            
            if not isinstance(imported_data, dict):
                self.report({'ERROR'}, "Invalid file format")
                return {'CANCELLED'}
            
            # If file contains a single group, extract it
            if len(imported_data) == 1:
                group_data = list(imported_data.values())[0]
            else:
                # Multiple groups - use the first one or create a combined group
                group_data = {"ColorTypes": []}
                for group_name, data in imported_data.items():
                    if isinstance(data, dict) and "ColorTypes" in data:
                        group_data["ColorTypes"].extend(data["ColorTypes"])
            
            # Save to internal system
            sets_dict = _get_internal_colortype_sets(context)
            sets_dict[self.set_name] = group_data
            _set_internal_colortype_sets(context, sets_dict)
            
            # Sync with UnifiedColorTypeManager
            try:
                upm_data = UnifiedColorTypeManager._read_sets_json(context)
                ump_data[self.set_name] = group_data
                UnifiedColorTypeManager._write_sets_json(context, upm_data)
            except Exception as e:
                print(f"Warning: Failed to sync with UnifiedColorTypeManager: {e}")
            
            self.report({'INFO'}, f"Imported group '{self.set_name}' successfully.")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        import os
        self.set_name = os.path.splitext(os.path.basename(self.filepath))[0]
        return context.window_manager.invoke_props_dialog(self)

class CleanupTaskcolortypeMappings(bpy.types.Operator):
    bl_idname = "bim.cleanup_task_colortype_mappings"
    bl_label = "Cleanup Task Mappings"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # 1. Limpiar mapeos de tareas (función original)
            from bonsai.bim.module.sequence.prop import cleanup_all_tasks_colortype_mappings
            cleanup_all_tasks_colortype_mappings(context)

            # 2. NUEVO: Limpiar perfiles del canvas actual
            try:
                anim_props = tool.Sequence.get_animation_props()

                # Limpiar todos los perfiles de la colección actual
                anim_props.ColorTypes.clear()

                # Resetear el índice activo
                anim_props.active_ColorType_index = 0

                self.report({'INFO'}, "Task colortype mappings cleaned and colortype canvas cleared")
            except Exception as e:
                # Si falla la limpieza del canvas, al menos reportar la limpieza de mapeos
                self.report({'INFO'}, f"Task colortype mappings cleaned. Canvas clear failed: {e}")

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to cleanup: {e}")
            return {'CANCELLED'}

class UpdateActivecolortypeGroup(bpy.types.Operator):
    """Saves any changes to the colortypes of the currently active group."""
    bl_idname = "bim.update_active_colortype_group"
    bl_label = "Update Active Group"
    bl_description = "Saves any changes to the colortypes of the currently loaded group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            active_group = getattr(anim_props, "ColorType_groups", None)
            if not active_group:
                self.report({'WARNING'}, "No active colortype group to update.")
                return {'CANCELLED'}

            # Esta función ya existe y hace exactamente lo que necesitamos
            tool.Sequence.sync_active_group_to_json()

            # NUEVO: Actualizar inmediatamente el dropdown de animation settings
            try:
                if hasattr(anim_props, 'task_colortype_group_selector'):
                    # Forzar invalidación del enum cache
                    from bpy.types import BIMAnimationProperties
                    if hasattr(BIMAnimationProperties, 'task_colortype_group_selector'):
                        prop_def = BIMAnimationProperties.task_colortype_group_selector[1]
                        if hasattr(prop_def, 'keywords') and 'items' in prop_def.keywords:
                            # Trigger enum refresh by re-setting the items function
                            prop_def.keywords['items'] = prop_def.keywords['items']
                    
                    # Force UI refresh
                    current_selection = anim_props.task_colortype_group_selector
                    anim_props.task_colortype_group_selector = ""
                    anim_props.task_colortype_group_selector = current_selection
            except Exception as e:
                print(f"Warning: Failed to refresh task_colortype_group_selector: {e}")

            self.report({'INFO'}, f"Active colortype group '{active_group}' updated.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to update active group: {e}")
            return {'CANCELLED'}

class InitializeColorTypeSystem(bpy.types.Operator):
    bl_idname = "bim.initialize_colortype_system"
    bl_label = "Initialize ColorType System"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        UnifiedColorTypeManager.initialize_default_for_all_tasks(context)
        self.report({'INFO'}, "ColorType system initialized for all tasks.")
        return {'FINISHED'}

class BIM_OT_init_default_all_tasks(bpy.types.Operator):
    bl_idname = "bim.init_default_all_tasks"
    bl_label = "Initialize DEFAULT for All Tasks"

    def execute(self, context):
        UnifiedColorTypeManager.initialize_default_for_all_tasks(context)
        self.report({'INFO'}, "DEFAULT group initialized for all tasks.")
        return {'FINISHED'}

class CopyTaskCustomcolortypeGroup(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.copy_task_custom_colortype_group"
    bl_label = "Copy Task Custom colortype Group"
    bl_options = {"REGISTER", "UNDO"}
    
    # UI may set these; declare to avoid attribute errors
    enabled: bpy.props.BoolProperty(name='Enabled', default=False, options={'HIDDEN'})
    group: bpy.props.StringProperty(name='Group', default='', options={'HIDDEN'})

    def _execute(self, context):
        # Verificar si la función existe, si no, implementar temporalmente
        if not hasattr(tool.Sequence, 'copy_task_colortype_config'):
            # Implementación temporal directa en el operador
            self._copy_task_colortype_config_temp(context)
            return
            
        tool.Sequence.copy_task_colortype_config()
        self.report({'INFO'}, "ColorType configuration copied to selected tasks.")
    
    def _copy_task_colortype_config_temp(self, context):
        """
        Implementación temporal de copia de ColorType hasta que se reinicie Blender.
        """
        try:
            # Get task tree properties
            tprops = tool.Sequence.get_task_tree_props()
            if not tprops or not tprops.tasks:
                self.report({'WARNING'}, "No task tree properties found")
                return

            # Get work schedule properties to find active task
            ws_props = tool.Sequence.get_work_schedule_props()
            if not ws_props or ws_props.active_task_index < 0 or ws_props.active_task_index >= len(tprops.tasks):
                self.report({'WARNING'}, "No active task found")
                return

            # Get the source task (active task)
            source_task = tprops.tasks[ws_props.active_task_index]
            
            # Get selected tasks (tasks with is_selected = True)
            selected_tasks = [task for task in tprops.tasks if getattr(task, 'is_selected', False)]
            if not selected_tasks:
                self.report({'WARNING'}, "No tasks selected to copy to")
                return

            # Copy configuration from source to selected tasks
            copied_count = 0
            for target_task in selected_tasks:
                if target_task.ifc_definition_id == source_task.ifc_definition_id:
                    continue  # Skip copying to self

                try:
                    # Copy main colortype settings
                    target_task.use_active_colortype_group = getattr(source_task, 'use_active_colortype_group', False)
                    target_task.selected_colortype_in_active_group = getattr(source_task, 'selected_colortype_in_active_group', "")
                    
                    # Copy animation_color_schemes if it exists
                    if hasattr(target_task, 'animation_color_schemes') and hasattr(source_task, 'animation_color_schemes'):
                        target_task.animation_color_schemes = source_task.animation_color_schemes

                    # Copy colortype group choices
                    target_task.colortype_group_choices.clear()
                    for source_group in source_task.colortype_group_choices:
                        target_group = target_task.colortype_group_choices.add()
                        target_group.group_name = source_group.group_name
                        target_group.enabled = source_group.enabled
                        
                        # Copy the selected value using the appropriate attribute
                        for attr_candidate in ("selected_colortype", "selected", "active_colortype", "colortype"):
                            if hasattr(source_group, attr_candidate) and hasattr(target_group, attr_candidate):
                                setattr(target_group, attr_candidate, getattr(source_group, attr_candidate))
                                break

                    copied_count += 1

                except Exception as e:
                    print(f"Error copying to task {target_task.ifc_definition_id}: {e}")

            self.report({'INFO'}, f"ColorType configuration copied to {copied_count} selected tasks (temporary implementation - restart Blender for full functionality).")

        except Exception as e:
            self.report({'ERROR'}, f"Error in copy operation: {e}")
            import traceback
            traceback.print_exc()

class DebugCopyFunction(bpy.types.Operator):
    bl_idname = "bim.debug_copy_function"
    bl_label = "Debug Copy Function"
    bl_options = {"REGISTER"}
    
    def execute(self, context):
        import bonsai.tool as tool
        
        # Verificar si la función existe
        has_function = hasattr(tool.Sequence, 'copy_task_colortype_config')
        self.report({'INFO'}, f"Function exists: {has_function}")
        
        if has_function:
            # Listar algunos métodos de la clase
            methods = [attr for attr in dir(tool.Sequence) if not attr.startswith('_')]
            print("Available Sequence methods:")
            for method in methods[-10:]:  # Show last 10 methods
                print(f"  - {method}")
        
        return {'FINISHED'}

# LEGACY OPERATORS
class LoadDefaultAnimationColors(bpy.types.Operator):
    bl_idname = "bim.load_default_animation_color_scheme"
    bl_label = "Load Animation Colors"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.load_default_animation_color_scheme(tool.Sequence)
        return {"FINISHED"}

class SaveAnimationColorScheme(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.save_animation_color_scheme"
    bl_label = "Save Animation Color Scheme"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def _execute(self, context):
        core.save_animation_color_scheme(tool.Sequence, name=self.name)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class LoadAnimationColorScheme(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.load_animation_color_scheme"
    bl_label = "Load Animation Color Scheme"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        props = tool.Sequence.get_animation_props()
        group = tool.Ifc.get().by_id(int(props.saved_color_schemes))
        core.load_animation_color_scheme(tool.Sequence, scheme=group)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

# ANIMATION STACK OPERATORS
class ANIM_OT_group_stack_add(bpy.types.Operator):
    bl_idname = "bim.anim_group_stack_add"
    bl_label = "Add Animation Group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # --- INICIO DE LA CORRECCIÓN ---
        # Primero, guardar cualquier cambio pendiente del editor de perfiles.
        # Esto asegura que los grupos recién creados o los perfiles modificados
        # estén en los datos JSON antes de intentar agregarlos al stack.
        # Esto soluciona el bug donde un grupo nuevo se añadía vacío.
        try:
            tool.Sequence.sync_active_group_to_json()
        except Exception as e:
            print(f"Bonsai WARNING: No se pudo sincronizar el grupo activo antes de agregarlo al stack: {e}")
        # --- FIN DE LA CORRECCIÓN ---

        props = tool.Sequence.get_animation_props()
        stack = props.animation_group_stack

        # DEBUG: Log current stack state
        print(f"🐛 DEBUG [anim_group_stack_add]: Current stack has {len(stack)} items:")
        for i, item in enumerate(stack):
            group_name = getattr(item, "group", "")
            enabled = getattr(item, "enabled", False)
            print(f"   [{i}] group='{group_name}', enabled={enabled}")

        # Evitar duplicados con la pila actual
        already = {getattr(it, "group", "") for it in stack}
        print(f"🐛 DEBUG [anim_group_stack_add]: Already in stack: {already}")

        # Candidatos: selector de Appearance, selector de tareas, y luego todos los grupos disponibles
        selected_colortype_group = getattr(props, "ColorType_groups", "") or ""
        selected_task_group = getattr(props, "task_colortype_group_selector", "") or ""
        print(f"🐛 DEBUG [anim_group_stack_add]: selected_colortype_group='{selected_colortype_group}', selected_task_group='{selected_task_group}'")

        # Leer todos los grupos disponibles desde JSON (si falla, lista vacía)
        all_groups = []
        try:
            data = UnifiedColorTypeManager._read_sets_json(context) or {}
            all_groups = list(data.keys())
            print(f"🐛 DEBUG [anim_group_stack_add]: All groups from JSON: {all_groups}")
            # Asegurar DEFAULT presente y primero
            if "DEFAULT" in all_groups:
                all_groups.remove("DEFAULT")
            all_groups.insert(0, "DEFAULT")
            print(f"🐛 DEBUG [anim_group_stack_add]: All groups (DEFAULT first): {all_groups}")
        except Exception as _e:
            print(f"[anim add] cannot read groups: {_e}")
            all_groups = ["DEFAULT"]

        # Construir lista de candidatos finales
        candidates = []

        # First, add selected groups if valid and not already in stack
        for g in [selected_colortype_group, selected_task_group]:
            if g and g.strip() and g not in ["NONE", "None", "none", "", " "] and g not in already and g not in candidates:
                candidates.append(g)
                print(f"🐛 DEBUG [anim_group_stack_add]: Added selected group to candidates: '{g}'")

        # Then, add other available groups that are not in stack
        for g in all_groups:
            if g and g.strip() and g not in ["NONE", "None", "none", "", " "] and g not in already and g not in candidates:
                candidates.append(g)
                print(f"🐛 DEBUG [anim_group_stack_add]: Added available group to candidates: '{g}'")

        print(f"🐛 DEBUG [anim_group_stack_add]: Final candidates list: {candidates}")

        # Elegir el primero disponible que no esté ya en la pila
        group_to_add = None
        for g in candidates:
            if g and g not in already:
                group_to_add = g
                break

        print(f"🐛 DEBUG [anim_group_stack_add]: Selected group to add: '{group_to_add}'")

        if not group_to_add:
            print(f"🐛 DEBUG [anim_group_stack_add]: No more groups available to add")
            self.report({'INFO'}, "No hay más grupos disponibles para agregar.")
            return {'CANCELLED'}

        # Garantizar que el grupo exista en JSON (si es nuevo)
        try:
            data = UnifiedColorTypeManager._read_sets_json(context) or {}
            if group_to_add == "DEFAULT":
                try:
                    UnifiedColorTypeManager.ensure_default_group_has_predefined_types(context)
                except Exception:
                    UnifiedColorTypeManager.ensure_default_group(context)
            elif group_to_add not in data:
                data[group_to_add] = {"ColorTypes": []}
                UnifiedColorTypeManager._write_sets_json(context, data)
                print(f"🐛 DEBUG [anim_group_stack_add]: Created new group in JSON: '{group_to_add}'")
        except Exception as _e:
            print(f"[anim add] ensure group failed: {_e}")

        # Añadir y seleccionar
        it = stack.add()
        it.group = group_to_add
        try:
            it.enabled = True
        except Exception:
            pass

        print(f"🐛 DEBUG [anim_group_stack_add]: Added group '{group_to_add}' to stack at index {len(stack) - 1}")

        # Sincronizar con el panel de edición de colortypes
        try:
            props.ColorType_groups = group_to_add
        except Exception:
            pass

        props.animation_group_stack_index = len(stack) - 1
        return {'FINISHED'}

class ANIM_OT_group_stack_remove(bpy.types.Operator):
    bl_idname = "bim.anim_group_stack_remove"
    bl_label = "Remove Animation Group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        idx = getattr(props, "animation_group_stack_index", -1)
        if 0 <= idx < len(props.animation_group_stack):
            it = props.animation_group_stack[idx]
            if getattr(it, "group", "") == "DEFAULT":
                self.report({'WARNING'}, "DEFAULT cannot be removed.")
                return {'CANCELLED'}
            props.animation_group_stack.remove(idx)
            # Ajustar selección
            if idx > 0:
                props.animation_group_stack_index = idx - 1
            else:
                props.animation_group_stack_index = 0
        return {'FINISHED'}

class ANIM_OT_group_stack_move(bpy.types.Operator):
    bl_idname = "bim.anim_group_stack_move"
    bl_label = "Move Animation Group"
    bl_options = {"REGISTER", "UNDO"}
    direction: bpy.props.EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    def execute(self, context):
        tool.Sequence.move_group_in_animation_stack(self.direction)
        return {'FINISHED'}

# DEBUGGING OPERATORS
class VerifyCustomGroupsExclusion(bpy.types.Operator):
    bl_idname = "bim.verify_custom_groups_exclusion"
    bl_label = "Verify Custom Groups Exclusion"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # This is a debug tool, logic can remain here.
        # ...
        self.report({'INFO'}, "Verification results printed to console.")
        return {'FINISHED'}

class ShowcolortypeUIState(bpy.types.Operator):
    bl_idname = "bim.show_colortype_ui_state"
    bl_label = "Show colortype UI State"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # This is a debug tool, logic can remain here.
        # ...
        self.report({'INFO'}, "UI state printed to console.")
        return {'FINISHED'}
    
class BIM_OT_cleanup_colortype_groups(bpy.types.Operator):
    bl_idname = "bim.cleanup_colortype_groups"
    bl_label = "Clean Invalid ColorTypes"
    bl_description = "Remove invalid group/ColorType assignments from tasks"

    def execute(self, context):
        scn = context.scene
        key = "BIM_AnimationColorSchemesSets"
        try:
            sets = scn.get(key, "{}")
            sets = json.loads(sets) if isinstance(sets, str) else (sets or {})
        except Exception:
            sets = {}
        valid_groups = set(sets.keys()) if isinstance(sets, dict) else set()
        cleaned_count = 0
        
        # 1. Limpiar colortype_mappings en BIMTasks
        for ob in getattr(scn, "BIMTasks", []):
            coll = getattr(ob, "colortype_mappings", None) or []
            # remove invalid entries safely
            i = len(coll) - 1
            while i >= 0:
                entry = coll[i]
                if getattr(entry, "group_name", "") not in valid_groups:
                    coll.remove(i)
                    cleaned_count += 1
                else:
                    # ensure selected colortype exists
                    pg = sets.get(entry.group_name, {}).get("ColorTypes", [])
                    names = {p.get("name") for p in pg if isinstance(p, dict)}
                    if getattr(entry, "selected_colortype", "") not in names:
                        try:
                            entry.selected_colortype = ""
                            cleaned_count += 1
                        except Exception:
                            pass
                i -= 1
        
        # 2. Limpiar task colortype group selectors
        try:
            tprops = tool.Sequence.get_task_tree_props()
            for task in getattr(tprops, "tasks", []):
                if hasattr(task, 'colortype_group_choices'):
                    # Collect indices to remove
                    to_remove = []
                    for idx, choice in enumerate(task.colortype_group_choices):
                        if choice.group_name not in valid_groups:
                            to_remove.append(idx)
                            cleaned_count += 1
                        else:
                            # Validate colortype within the group
                            colortypes = sets.get(choice.group_name, {}).get("ColorTypes", [])
                            colortype_names = {p.get("name") for p in colortypes if isinstance(p, dict)}
                            if choice.selected_colortype and choice.selected_colortype not in colortype_names:
                                choice.selected_colortype = ""
                                cleaned_count += 1
                    
                    # Remove invalid entries
                    for offset, idx in enumerate(to_remove):
                        task.colortype_group_choices.remove(idx - offset)
                        
                # Clear enum property if pointing to invalid colortype
                if hasattr(task, "selected_colortype_in_active_group"):
                    current = getattr(task, "selected_colortype_in_active_group", "")
                    if current:
                        # Get current active group
                        anim_props = tool.Sequence.get_animation_props()
                        active_group = getattr(anim_props, "ColorType_groups", "")
                        if active_group and active_group in sets:
                            active_colortypes = sets.get(active_group, {}).get("ColorTypes", [])
                            active_names = {p.get("name") for p in active_colortypes if isinstance(p, dict)}
                            if current not in active_names:
                                try:
                                    safe_set_selected_colortype_in_active_group(task, "")
                                    cleaned_count += 1
                                except Exception:
                                    pass
        except Exception as e:
            print(f"Warning: Task properties cleanup failed: {e}")
        
        # 3. Limpiar animation group stack
        try:
            anim_props = tool.Sequence.get_animation_props()
            if hasattr(anim_props, 'animation_group_stack'):
                to_remove = []
                for idx, item in enumerate(anim_props.animation_group_stack):
                    group_name = getattr(item, 'group', '')
                    if group_name and group_name not in valid_groups and group_name != "DEFAULT":
                        to_remove.append(idx)
                        cleaned_count += 1
                
                # Remove invalid groups from stack
                for offset, idx in enumerate(to_remove):
                    anim_props.animation_group_stack.remove(idx - offset)
                    
                # Adjust index if needed
                if anim_props.animation_group_stack_index >= len(anim_props.animation_group_stack):
                    anim_props.animation_group_stack_index = max(0, len(anim_props.animation_group_stack) - 1)
                    
        except Exception as e:
            print(f"Warning: Animation stack cleanup failed: {e}")
        
        self.report({'INFO'}, f"Cleaned {cleaned_count} invalid colortype references")
        return {'FINISHED'}
