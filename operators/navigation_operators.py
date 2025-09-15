# File: navigation_operators.py
# Description: Navigation operators for column navigation in task views.

import bpy
import bonsai.tool as tool

try:
    from .ui import calculate_visible_columns_count
except Exception:
    try:
        from bonsai.bim.module.sequence.ui import calculate_visible_columns_count
    except Exception:
        def calculate_visible_columns_count(context):
            return 3  # Safe fallback

# === Navigation operators ===

class NavigateColumnsLeft(bpy.types.Operator):
    """Navigate to previous columns"""
    bl_idname = "bim.navigate_columns_left"
    bl_label = "Previous Columns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Move left by 1 column for fine control
        if props.column_start_index > 0:
            props.column_start_index -= 1
        # Force UI to update to show column changes
        context.area.tag_redraw()
        return {'FINISHED'}


class NavigateColumnsRight(bpy.types.Operator):
    """Navigate to next columns"""
    bl_idname = "bim.navigate_columns_right"
    bl_label = "Next Columns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        max_columns = len(props.columns)
        visible_columns = calculate_visible_columns_count(context)
        
        # Move right by 1 column for fine control, but don't go past the last set
        if props.column_start_index + visible_columns < max_columns:
            props.column_start_index += 1
        # Force UI to update to show column changes  
        context.area.tag_redraw()
        return {'FINISHED'}


class NavigateColumnsHome(bpy.types.Operator):
    """Jump to first column"""
    bl_idname = "bim.navigate_columns_home"
    bl_label = "First Columns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        props.column_start_index = 0
        return {'FINISHED'}


class NavigateColumnsEnd(bpy.types.Operator):
    """Jump to last set of columns"""
    bl_idname = "bim.navigate_columns_end"
    bl_label = "Last Columns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        max_columns = len(props.columns)
        visible_columns = 6  # Max visible columns at once (sync with UI)
        
        if max_columns > visible_columns:
            props.column_start_index = max_columns - visible_columns
        else:
            props.column_start_index = 0
        return {'FINISHED'}