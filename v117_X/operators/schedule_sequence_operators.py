# File: schedule_sequence_operators.py
# Description: Operators for managing task sequence relationships and their properties.

import bpy
import bonsai.tool as tool
import bonsai.core.sequence as core

# ============================================================================
# SEQUENCE EDITING OPERATORS
# ============================================================================

class EnableEditingTaskSequence(bpy.types.Operator):
    bl_idname = "bim.enable_editing_task_sequence"
    bl_label = "Enable Editing Task Sequence"
    task: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_task_sequence(tool.Sequence)
        return {"FINISHED"}

class EnableEditingSequenceAttributes(bpy.types.Operator):
    bl_idname = "bim.enable_editing_sequence_attributes"
    bl_label = "Enable Editing Sequence Attributes"
    bl_options = {"REGISTER", "UNDO"}
    sequence: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_sequence_attributes(tool.Sequence, rel_sequence=tool.Ifc.get().by_id(self.sequence))
        return {"FINISHED"}

class EditSequenceAttributes(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_sequence_attributes"
    bl_label = "Edit Sequence"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        core.edit_sequence_attributes(
            tool.Ifc,
            tool.Sequence,
            rel_sequence=tool.Ifc.get().by_id(props.active_sequence_id),
        )

class DisableEditingSequence(bpy.types.Operator):
    bl_idname = "bim.disable_editing_sequence"
    bl_label = "Disable Editing Sequence"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.disable_editing_rel_sequence(tool.Sequence)
        return {"FINISHED"}

class EnableEditingSequenceTimeLag(bpy.types.Operator):
    bl_idname = "bim.enable_editing_sequence_lag_time"
    bl_label = "Enable Editing Sequence Time Lag"
    bl_options = {"REGISTER", "UNDO"}
    sequence: bpy.props.IntProperty()
    lag_time: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_sequence_lag_time(
            tool.Sequence,
            rel_sequence=tool.Ifc.get().by_id(self.sequence),
            lag_time=tool.Ifc.get().by_id(self.lag_time),
        )
        return {"FINISHED"}

class EditSequenceTimeLag(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_sequence_lag_time"
    bl_label = "Edit Time Lag"
    bl_options = {"REGISTER", "UNDO"}
    lag_time: bpy.props.IntProperty()

    def _execute(self, context):
        core.edit_sequence_lag_time(tool.Ifc, tool.Sequence, lag_time=tool.Ifc.get().by_id(self.lag_time))

