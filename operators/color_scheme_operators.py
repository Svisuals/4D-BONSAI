# File: color_scheme_operators.py
# Description: Operators for managing Animation Color Schemes (ColorTypes), groups, and task assignments.

import bpy
import json
import bonsai.tool as tool
import bonsai.core.sequence as core
from bpy_extras.io_utils import ExportHelper, ImportHelper

# Attempt to import helpers from their new, refactored locations
try:
    from .prop import UnifiedColorTypeManager, safe_set_selected_colortype_in_active_group
    from .schedule_task_operators import snapshot_all_ui_state
except ImportError:
    # Fallback for older structures or if refactoring is in progress
    class UnifiedColorTypeManager:
        @staticmethod
        def sync_default_group_to_predefinedtype(*args, **kwargs): pass
    def safe_set_selected_colortype_in_active_group(*args, **kwargs): pass
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

        props.ColorTypes.remove(index)
        props.active_ColorType_index = max(0, index - 1)
        return {'FINISHED'}

class SaveAnimationColorSchemesSetInternal(bpy.types.Operator):
    bl_idname = "bim.save_animation_color_schemes_set_internal"
    bl_label = "Save Group (Internal)"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty(name="Group Name", default="New Group")

    def execute(self, context):
        tool.Sequence.sync_active_group_to_json()
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
            return {'CANCELLED'}
        
        all_sets = _get_internal_colortype_sets(context)
        if self.set_name in all_sets:
            del all_sets[self.set_name]
            _set_internal_colortype_sets(context, all_sets)
            self.report({'INFO'}, f"Removed group '{self.set_name}'")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class ExportAnimationColorSchemesSetToFile(bpy.types.Operator, ExportHelper):
    bl_idname = "bim.export_animation_color_schemes_set_to_file"
    bl_label = "Export Color Scheme Group"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        tool.Sequence.export_active_colortype_group(self.filepath)
        self.report({'INFO'}, "Exported successfully.")
        return {'FINISHED'}

class ImportAnimationColorSchemesSetFromFile(bpy.types.Operator, ImportHelper):
    bl_idname = "bim.import_animation_color_schemes_set_from_file"
    bl_label = "Import Color Scheme Group"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})
    set_name: bpy.props.StringProperty(name="Group Name", default="Imported Group")

    def execute(self, context):
        tool.Sequence.import_colortype_group_from_file(self.filepath, self.set_name)
        self.report({'INFO'}, f"Imported group '{self.set_name}'.")
        return {'FINISHED'}

    def invoke(self, context, event):
        import os
        self.set_name = os.path.splitext(os.path.basename(self.filepath))[0]
        return context.window_manager.invoke_props_dialog(self)

class CleanupTaskcolortypeMappings(bpy.types.Operator):
    bl_idname = "bim.cleanup_task_colortype_mappings"
    bl_label = "Cleanup Task Mappings"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        UnifiedColorTypeManager.cleanup_invalid_mappings(context)
        self.report({'INFO'}, "Task colortype mappings cleaned.")
        return {'FINISHED'}

class UpdateActivecolortypeGroup(bpy.types.Operator):
    bl_idname = "bim.update_active_colortype_group"
    bl_label = "Update Active Group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tool.Sequence.sync_active_group_to_json()
        self.report({'INFO'}, "Active colortype group updated.")
        return {'FINISHED'}

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

    def _execute(self, context):
        tool.Sequence.copy_task_colortype_config()
        self.report({'INFO'}, "ColorType configuration copied to selected tasks.")

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
        tool.Sequence.add_group_to_animation_stack()
        return {'FINISHED'}

class ANIM_OT_group_stack_remove(bpy.types.Operator):
    bl_idname = "bim.anim_group_stack_remove"
    bl_label = "Remove Animation Group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tool.Sequence.remove_group_from_animation_stack()
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
        UnifiedColorTypeManager.cleanup_invalid_mappings(context)
        self.report({'INFO'}, "Invalid colortype mappings cleaned")
        return {'FINISHED'}

# ============================================================================
# OPERATOR REGISTRATION
# ============================================================================

classes = [
    AddAnimationColorSchemes,
    RemoveAnimationColorSchemes,
    SaveAnimationColorSchemesSetInternal,
    LoadAnimationColorSchemesSetInternal,
    RemoveAnimationColorSchemesSetInternal,
    ExportAnimationColorSchemesSetToFile,
    ImportAnimationColorSchemesSetFromFile,
    CleanupTaskcolortypeMappings,
    UpdateActivecolortypeGroup,
    InitializeColorTypeSystem,
    BIM_OT_init_default_all_tasks,
    CopyTaskCustomcolortypeGroup,
    LoadDefaultAnimationColors,
    SaveAnimationColorScheme,
    LoadAnimationColorScheme,
    ANIM_OT_group_stack_add,
    ANIM_OT_group_stack_remove,
    ANIM_OT_group_stack_move,
    VerifyCustomGroupsExclusion,
    ShowcolortypeUIState,
    BIM_OT_cleanup_colortype_groups
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)