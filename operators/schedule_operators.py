# File: schedule_operators.py
# Description: General operators for schedule-wide actions like recalculation, Gantt charts, and variance analysis.

import bpy
import bonsai.tool as tool
import bonsai.core.sequence as core
from .schedule_task_operators import snapshot_all_ui_state, restore_all_ui_state

# ============================================================================
# SCHEDULE UTILITY OPERATORS
# ============================================================================

class RecalculateSchedule(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.recalculate_schedule"
    bl_label = "Recalculate Schedule"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def _execute(self, context):
        core.recalculate_schedule(tool.Ifc, work_schedule=tool.Ifc.get().by_id(self.work_schedule))


class GenerateGanttChart(bpy.types.Operator):
    bl_idname = "bim.generate_gantt_chart"
    bl_label = "Generate Gantt Chart"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def execute(self, context):
        try:
            work_schedule = tool.Ifc.get().by_id(self.work_schedule)
            if not work_schedule:
                self.report({'ERROR'}, "Work schedule not found")
                return {'CANCELLED'}
            import ifcopenshell.util.sequence as _useq
            if not _useq.get_root_tasks(work_schedule):
                self.report({'WARNING'}, "No tasks found in schedule")
                return {'CANCELLED'}
            core.generate_gantt_chart(tool.Sequence, work_schedule=work_schedule)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to generate Gantt chart: {str(e)}")
            return {'CANCELLED'}


class AddTaskColumn(bpy.types.Operator):
    bl_idname = "bim.add_task_column"
    bl_label = "Add Task Column"
    bl_options = {"REGISTER", "UNDO"}
    column_type: bpy.props.StringProperty()
    name: bpy.props.StringProperty()
    data_type: bpy.props.StringProperty()

    def execute(self, context):
        core.add_task_column(tool.Sequence, self.column_type, self.name, self.data_type)
        return {"FINISHED"}


class SetupDefaultTaskColumns(bpy.types.Operator):
    bl_idname = "bim.setup_default_task_columns"
    bl_label = "Setup Default Task Columns"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.setup_default_task_columns(tool.Sequence)
        return {"FINISHED"}


class RemoveTaskColumn(bpy.types.Operator):
    bl_idname = "bim.remove_task_column"
    bl_label = "Remove Task Column"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def execute(self, context):
        core.remove_task_column(tool.Sequence, self.name)
        return {"FINISHED"}


class SetTaskSortColumn(bpy.types.Operator):
    bl_idname = "bim.set_task_sort_column"
    bl_label = "Set Task Sort Column"
    bl_options = {"REGISTER", "UNDO"}
    column: bpy.props.StringProperty()

    def execute(self, context):
        snapshot_all_ui_state(context)
        core.set_task_sort_column(tool.Sequence, self.column)
        restore_all_ui_state(context)
        return {'FINISHED'}


class CreateBaseline(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.create_baseline"
    bl_label = "Create Schedule Baseline"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()
    name: bpy.props.StringProperty()

    def _execute(self, context):
        core.create_baseline(
            tool.Ifc, tool.Sequence, work_schedule=tool.Ifc.get().by_id(self.work_schedule), name=self.name
        )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name", text="Baseline Name")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class CalculateScheduleVariance(bpy.types.Operator):
    """Calculates the variance between two date sets for all tasks."""
    bl_idname = "bim.calculate_schedule_variance"
    bl_label = "Calculate Schedule Variance"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        import ifcopenshell.util.sequence

        ws_props = tool.Sequence.get_work_schedule_props()
        task_props = tool.Sequence.get_task_tree_props()

        if not task_props.tasks:
            self.report({'WARNING'}, "No tasks visible to calculate variance. Clear filters to see all tasks.")
            return {'CANCELLED'}

        source_a = ws_props.variance_source_a
        source_b = ws_props.variance_source_b

        if source_a == source_b:
            self.report({'WARNING'}, "Cannot compare a date set with itself.")
            return {'CANCELLED'}

        finish_attr_a = f"{source_a.capitalize()}Finish"
        finish_attr_b = f"{source_b.capitalize()}Finish"

        tasks_processed = 0
        for task_pg in task_props.tasks:
            task_ifc = tool.Ifc.get().by_id(task_pg.ifc_definition_id)
            if not task_ifc:
                continue

            date_a = ifcopenshell.util.sequence.derive_date(task_ifc, finish_attr_a, is_latest=True)
            date_b = ifcopenshell.util.sequence.derive_date(task_ifc, finish_attr_b, is_latest=True)

            if date_a and date_b:
                delta = date_b.date() - date_a.date()
                variance_days = delta.days
                task_pg.variance_days = variance_days

                if variance_days > 0:
                    task_pg.variance_status = f"Delayed (+{variance_days}d)"
                elif variance_days < 0:
                    task_pg.variance_status = f"Ahead ({variance_days}d)"
                else:
                    task_pg.variance_status = "On Time"
                tasks_processed += 1
            else:
                task_pg.variance_status = "N/A"
                task_pg.variance_days = 0

        self.report({'INFO'}, f"Variance calculated for {tasks_processed} tasks ({source_a} vs {source_b}).")
        return {'FINISHED'}


class ClearScheduleVariance(bpy.types.Operator):
    """Clears the calculated variance from all visible tasks."""
    bl_idname = "bim.clear_schedule_variance"
    bl_label = "Clear Variance"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tool.Sequence.clear_schedule_variance()
        self.report({'INFO'}, "Cleared variance and color mode.")
        return {'FINISHED'}


class DeactivateVarianceColorMode(bpy.types.Operator):
    bl_idname = "bim.deactivate_variance_color_mode"
    bl_label = "Deactivate Variance Color Mode"
    bl_description = "Deactivate variance color mode and restore normal colors"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        try:
            tool.Sequence.deactivate_variance_color_mode()
            self.report({'INFO'}, "Variance color mode deactivated")
        except Exception as e:
            self.report({'ERROR'}, f"Deactivation failed: {e}")
        return {'FINISHED'}


class RefreshTaskOutputCounts(bpy.types.Operator):
    """Recalculates the number of 'Outputs' for all tasks in the list."""
    bl_idname = "bim.refresh_task_output_counts"
    bl_label = "Refresh Output Counts"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            core.refresh_task_output_counts(tool.Sequence)
            self.report({'INFO'}, "Recuentos de 'Outputs' actualizados.")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to refresh: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}


class AddTaskBars(bpy.types.Operator):
    bl_idname = "bim.add_task_bars"
    bl_label = "Generate Task Bars"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Generate 3D bars for selected tasks aligned with schedule dates"

    def execute(self, context):
        try:
            tool.Sequence.refresh_task_bars()
            task_count = len(tool.Sequence.get_task_bar_list())
            self.report({'INFO'}, f"Generated bars for {task_count} tasks.")
            return {"FINISHED"}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to generate task bars: {str(e)}")
            return {'CANCELLED'}


class ClearTaskBars(bpy.types.Operator):
    bl_idname = "bim.clear_task_bars"
    bl_label = "Clear Task Bars"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Remove all task bar visualizations"

    def execute(self, context):
        tool.Sequence.clear_task_bars()
        self.report({'INFO'}, "Task bars cleared")
        return {"FINISHED"}


class GuessDateRange(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.guess_date_range"
    bl_label = "Guess Work Schedule Date Range"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def _execute(self, context):
        work_schedule = tool.Ifc.get().by_id(self.work_schedule)
        start_date, finish_date = tool.Sequence.guess_date_range(work_schedule)
        tool.Sequence.update_visualisation_date(start_date, finish_date)
        if not (start_date and finish_date):
            props = tool.Sequence.get_work_schedule_props()
            date_source = getattr(props, "date_source_type", "SCHEDULE")
            self.report({'WARNING'}, f"No '{date_source.capitalize()}' dates found to guess a range.")
        return {"FINISHED"}
