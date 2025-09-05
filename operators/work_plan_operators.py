# File: work_plan_operators.py
# Description: Operators for adding, editing, and managing IfcWorkPlan entities.

import bpy
import bonsai.tool as tool
import bonsai.core.sequence as core

# ============================================================================
# WORK PLAN OPERATORS
# ============================================================================

class AddWorkPlan(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_work_plan"
    bl_label = "Add Work Plan"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        core.add_work_plan(tool.Ifc)

class EditWorkPlan(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_work_plan"
    bl_options = {"REGISTER", "UNDO"}
    bl_label = "Edit Work Plan"

    def _execute(self, context):
        props = tool.Sequence.get_work_plan_props()
        core.edit_work_plan(
            tool.Ifc,
            tool.Sequence,
            work_plan=tool.Ifc.get().by_id(props.active_work_plan_id),
        )

class RemoveWorkPlan(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.remove_work_plan"
    bl_label = "Remove Work Plan"
    bl_options = {"REGISTER", "UNDO"}
    work_plan: bpy.props.IntProperty()

    def _execute(self, context):
        core.remove_work_plan(tool.Ifc, work_plan=tool.Ifc.get().by_id(self.work_plan))

class EnableEditingWorkPlan(bpy.types.Operator):
    bl_idname = "bim.enable_editing_work_plan"
    bl_label = "Enable Editing Work Plan"
    bl_options = {"REGISTER", "UNDO"}
    work_plan: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_work_plan(tool.Sequence, work_plan=tool.Ifc.get().by_id(self.work_plan))
        return {"FINISHED"}

class DisableEditingWorkPlan(bpy.types.Operator):
    bl_idname = "bim.disable_editing_work_plan"
    bl_options = {"REGISTER", "UNDO"}
    bl_label = "Disable Editing Work Plan"

    def execute(self, context):
        core.disable_editing_work_plan(tool.Sequence)
        return {"FINISHED"}

class EnableEditingWorkPlanSchedules(bpy.types.Operator):
    bl_idname = "bim.enable_editing_work_plan_schedules"
    bl_label = "Enable Editing Work Plan Schedules"
    bl_options = {"REGISTER", "UNDO"}
    work_plan: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_work_plan_schedules(tool.Sequence, work_plan=tool.Ifc.get().by_id(self.work_plan))
        return {"FINISHED"}

