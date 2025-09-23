# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021, 2022 Dion Moult <dion@thinkmoult.com>, Yassine Oualid <yassine@sigmadimensions.com>, Federico Eraso <feraso@svisuals.net
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
import bonsai.core.sequence as core

# Import shared state management functions
try:
    from .operator import snapshot_all_ui_state, restore_all_ui_state
except ImportError:
    # Fallback implementations
    def snapshot_all_ui_state(context):
        pass
    def restore_all_ui_state(context):
        pass


class ContractTask(bpy.types.Operator):
    bl_idname = "bim.contract_task"
    bl_label = "Contract Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        snapshot_all_ui_state(context)
        core.contract_task(tool.Sequence, task=tool.Ifc.get().by_id(self.task))
        return {'FINISHED'}
        restore_all_ui_state(context)


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


class EnableEditingTaskTime(bpy.types.Operator, tool.Ifc.Operator):
    # IFC operator is needed because operator is adding a new task time to IFC
    # if it doesn't exist.
    bl_idname = "bim.enable_editing_task_time"
    bl_label = "Enable Editing Task Time"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.enable_editing_task_time(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))


class EditTaskTime(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_task_time"
    bl_label = "Edit Task Time"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        core.edit_task_time(
            tool.Ifc,
            tool.Sequence,
            tool.Resource,
            task_time=tool.Ifc.get().by_id(props.active_task_time_id),
        )


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
        # USE THE SAME PATTERN AS THE FILTERS (which works correctly):
        snapshot_all_ui_state(context)  # >>> 1. Save state BEFORE canceling
        
        # >>> 2. Execute the cancel operation
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


class AddTimePeriod(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_time_period"
    bl_label = "Add Time Period"
    bl_options = {"REGISTER", "UNDO"}
    recurrence_pattern: bpy.props.IntProperty()

    def _execute(self, context):
        core.add_time_period(tool.Ifc, tool.Sequence, recurrence_pattern=tool.Ifc.get().by_id(self.recurrence_pattern))


class RemoveTimePeriod(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.remove_time_period"
    bl_label = "Remove Time Period"
    bl_options = {"REGISTER", "UNDO"}
    time_period: bpy.props.IntProperty()

    def _execute(self, context):
        core.remove_time_period(tool.Ifc, time_period=tool.Ifc.get().by_id(self.time_period))


class EnableEditingTaskCalendar(bpy.types.Operator):
    bl_idname = "bim.enable_editing_task_calendar"
    bl_label = "Enable Editing Task Calendar"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_task_calendar(tool.Sequence, task=tool.Ifc.get().by_id(self.task))
        return {"FINISHED"}


class DisableEditingTaskTime(bpy.types.Operator):
    bl_idname = "bim.disable_editing_task_time"
    bl_label = "Disable Editing Task Time"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.disable_editing_task_time(tool.Sequence)
        return {"FINISHED"}


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
        r = core.go_to_task(tool.Sequence, task=tool.Ifc.get().by_id(self.task))
        if isinstance(r, str):
            self.report({"WARNING"}, r)
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