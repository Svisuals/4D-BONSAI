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
import ifcopenshell.util.sequence
import bonsai.tool as tool

# Importación segura para llenar los menús desplegables de la UI
try:
    from ...prop.animation import get_user_created_groups_enum
except ImportError:
    def get_user_created_groups_enum(self, context):
        return [("NONE", "None", "")]

# Importación segura para UnifiedColorTypeManager
try:
    from ...prop.color_manager_prop import UnifiedColorTypeManager
except ImportError:
    class UnifiedColorTypeManager:
        @staticmethod
        def get_group_ColorTypes(context, group_name):
            return {}


class SearchCustomColorTypeGroup(bpy.types.Operator):
    bl_idname = "bim.search_custom_colortype_group"
    bl_label = "Search Custom ColorType Group"
    bl_description = "Search and filter custom ColorType groups"
    bl_options = {"REGISTER", "UNDO"}

    search_term: bpy.props.StringProperty(name="Search", default="")

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        if not self.search_term:
            self.report({'INFO'}, "Enter search term")
            return {'CANCELLED'}

        # Buscar en grupos disponibles
# get_user_created_groups_enum is already imported at module level
        items = get_user_created_groups_enum(None, context)

        matches = [item for item in items if self.search_term.lower() in item[1].lower()]

        if matches:
            # Seleccionar el primer match
            props.task_ColorType_group_selector = matches[0][0]
            self.report({'INFO'}, f"Found and selected: {matches[0][1]}")
        else:
            self.report({'WARNING'}, f"No groups found matching: {self.search_term}")

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "search_term")


class CopyCustomColorTypeGroup(bpy.types.Operator):
    bl_idname = "bim.copy_custom_colortype_group"
    bl_label = "Copy Custom ColorType Group"
    bl_description = "Copy current custom ColorType group to clipboard"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        current_value = getattr(props, "task_ColorType_group_selector", "")

        if current_value:
            context.window_manager.clipboard = current_value
            self.report({'INFO'}, f"Copied to clipboard: {current_value}")
        else:
            self.report({'WARNING'}, "No custom ColorType group selected to copy")

        return {'FINISHED'}


class PasteCustomColorTypeGroup(bpy.types.Operator):
    bl_idname = "bim.paste_custom_colortype_group"
    bl_label = "Paste Custom ColorType Group"
    bl_description = "Paste custom ColorType group from clipboard"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        clipboard_value = context.window_manager.clipboard.strip()

        if not clipboard_value:
            self.report({'WARNING'}, "Clipboard is empty")
            return {'CANCELLED'}

        # Verificar que el valor existe en los grupos disponibles
# get_user_created_groups_enum is already imported at module level
        items = get_user_created_groups_enum(None, context)
        valid_values = [item[0] for item in items]

        if clipboard_value in valid_values:
            props.task_ColorType_group_selector = clipboard_value
            self.report({'INFO'}, f"Pasted from clipboard: {clipboard_value}")
        else:
            self.report({'WARNING'}, f"Invalid group in clipboard: {clipboard_value}")

        return {'FINISHED'}

class SetCustomColorTypeGroupNull(bpy.types.Operator):
    bl_idname = "bim.set_custom_colortype_group_null"
    bl_label = "Set Custom ColorType Group to Null"
    bl_description = "Clear custom ColorType group selection (set to null)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()

        # Limpiar la selección
        props.task_ColorType_group_selector = ""

        # También limpiar el perfil seleccionado en la tarea activa si existe
        try:
            tprops = tool.Sequence.get_task_tree_props()
            wprops = tool.Sequence.get_work_schedule_props()
            if tprops.tasks and wprops.active_task_index < len(tprops.tasks):
                task = tprops.tasks[wprops.active_task_index]
                task.selected_ColorType_in_active_group = ""
                task.use_active_ColorType_group = False
        except Exception:
            pass

        self.report({'INFO'}, "Custom ColorType group cleared (set to null)")
        return {'FINISHED'}

class ShowCustomColorTypeGroupInfo(bpy.types.Operator):
    bl_idname = "bim.show_custom_colortype_group_info"
    bl_label = "Custom ColorType Group Info"
    bl_description = "Show information about the current custom ColorType group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        current_value = getattr(props, "task_ColorType_group_selector", "")

        if current_value:
            # Obtener información del grupo
            ColorTypes = UnifiedColorTypeManager.get_group_ColorTypes(context, current_value)

            info_text = f"Group: {current_value}\n"
            info_text += f"ColorTypes: {len(ColorTypes)}\n"
            if ColorTypes:
                info_text += f"Available: {', '.join(ColorTypes.keys())}"

            self.report({'INFO'}, info_text)
        else:
            self.report({'INFO'}, "No custom ColorType group selected")

        return {'FINISHED'}
    
def get_unified_date_range(self, work_schedule):
    """
    Calcula el rango de fechas unificado analizando TODOS los 4 tipos de cronograma.
    Devuelve el inicio más temprano y el fin más tardío de todos ellos.
    """
    if not work_schedule:
        return None, None

    all_starts = []
    all_finishes = []

    for schedule_type in ["SCHEDULE", "ACTUAL", "EARLY", "LATE"]:
        start_attr = f"{schedule_type.capitalize()}Start"
        finish_attr = f"{schedule_type.capitalize()}Finish"

        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)

        def get_all_tasks_recursive(tasks):
            result = []
            for task in tasks:
                result.append(task)
                nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                if nested:
                    result.extend(get_all_tasks_recursive(nested))
            return result

        all_tasks = get_all_tasks_recursive(root_tasks)

        for task in all_tasks:
            start_date = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
            if start_date:
                all_starts.append(start_date)

            finish_date = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
            if finish_date:
                all_finishes.append(finish_date)

    if not all_starts or not all_finishes:
        return None, None

    unified_start = min(all_starts)
    unified_finish = max(all_finishes)

    return unified_start, unified_finish


classes = (
    SearchCustomColorTypeGroup,
    CopyCustomColorTypeGroup,
    PasteCustomColorTypeGroup,
    SetCustomColorTypeGroupNull,
    ShowCustomColorTypeGroupInfo,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)




