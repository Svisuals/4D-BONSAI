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
import bonsai.tool as tool
from . import props_sequence
from . import colortype_sequence

try:
    from ...prop.animation import get_user_created_groups_enum, UnifiedColorTypeManager
except ImportError:
    def get_user_created_groups_enum(self, context): return [("NONE", "None", "")]
    class UnifiedColorTypeManager: pass


class SearchCustomColorTypeGroup(bpy.types.Operator):
    bl_idname = "bim.search_custom_ColorType_group"
    bl_label = "Search Custom ColorType Group"
    bl_description = "Search and filter custom ColorType groups"
    bl_options = {"REGISTER", "UNDO"}

    search_term: bpy.props.StringProperty(name="Search", default="")

    def execute(self, context):
        props = props_sequence.get_animation_props()
        if not self.search_term:
            self.report({'INFO'}, "Enter search term")
            return {'CANCELLED'}
        items = get_user_created_groups_enum(None, context)
        matches = [item for item in items if self.search_term.lower() in item[1].lower()]
        if matches:
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
    bl_idname = "bim.copy_custom_ColorType_group"
    bl_label = "Copy Custom ColorType Group"
    bl_description = "Copy current custom ColorType group to clipboard"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = props_sequence.get_animation_props()
        current_value = getattr(props, "task_ColorType_group_selector", "")
        if current_value:
            context.window_manager.clipboard = current_value
            self.report({'INFO'}, f"Copied to clipboard: {current_value}")
        else:
            self.report({'WARNING'}, "No custom ColorType group selected to copy")
        return {'FINISHED'}


class PasteCustomColorTypeGroup(bpy.types.Operator):
    bl_idname = "bim.paste_custom_ColorType_group"
    bl_label = "Paste Custom ColorType Group"
    bl_description = "Paste custom ColorType group from clipboard"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = props_sequence.get_animation_props()
        clipboard_value = context.window_manager.clipboard.strip()
        if not clipboard_value:
            self.report({'WARNING'}, "Clipboard is empty")
            return {'CANCELLED'}
        items = get_user_created_groups_enum(None, context)
        valid_values = [item[0] for item in items]
        if clipboard_value in valid_values:
            props.task_ColorType_group_selector = clipboard_value
            self.report({'INFO'}, f"Pasted from clipboard: {clipboard_value}")
        else:
            self.report({'WARNING'}, f"Invalid group in clipboard: {clipboard_value}")
        return {'FINISHED'}


class SetCustomColorTypeGroupNull(bpy.types.Operator):
    bl_idname = "bim.set_custom_ColorType_group_null"
    bl_label = "Set Custom ColorType Group to Null"
    bl_description = "Clear custom ColorType group selection (set to null)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = props_sequence.get_animation_props()
        props.task_ColorType_group_selector = ""
        try:
            tprops = props_sequence.get_task_tree_props()
            wprops = props_sequence.get_work_schedule_props()
            if tprops.tasks and wprops.active_task_index < len(tprops.tasks):
                task = tprops.tasks[wprops.active_task_index]
                task.selected_ColorType_in_active_group = ""
                task.use_active_ColorType_group = False
        except Exception:
            pass
        self.report({'INFO'}, "Custom ColorType group cleared (set to null)")
        return {'FINISHED'}


class ShowCustomColorTypeGroupInfo(bpy.types.Operator):
    bl_idname = "bim.show_custom_ColorType_group_info"
    bl_label = "Custom ColorType Group Info"
    bl_description = "Show information about the current custom ColorType group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = props_sequence.get_animation_props()
        current_value = getattr(props, "task_ColorType_group_selector", "")
        if current_value:
            group_data = colortype_sequence.load_ColorType_group_data(current_value)
            ColorTypes = group_data.get("ColorTypes", [])
            info_text = f"Group: {current_value}\nColorTypes: {len(ColorTypes)}\n"
            if ColorTypes:
                info_text += f"Available: {', '.join(c.get('name', '') for c in ColorTypes)}"
            self.report({'INFO'}, info_text)
        else:
            self.report({'INFO'}, "No custom ColorType group selected")
        return {'FINISHED'}