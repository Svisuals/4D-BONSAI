import bpy
from bpy.types import UIList, Panel

# Toggle to show/hide saved ColorTypes section
# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2020, 2021 Dion Moult <dion@thinkmoult.com>
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

import re
import bpy
from bpy.types import UIList, Panel
import ifcopenshell
import isodate
import json
import bonsai.tool as tool
import bonsai.bim.helper
from bpy.types import Panel, UIList
from bonsai.bim.helper import draw_attributes
from bonsai.bim.module.sequence.data import (
    WorkPlansData,
    WorkScheduleData,
    SequenceData,
    TaskICOMData,
    AnimationColorSchemeData,
)
from bonsai.bim.module.sequence.prop.animation import UnifiedColorTypeManager
from bonsai.bim.module.sequence.prop.schedule import monitor_predefined_type_change
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from bonsai.bim.prop import Attribute
    from bonsai.bim.module.sequence.prop.schedule import BIMWorkScheduleProperties
    from bonsai.bim.module.sequence.prop.task import BIMTaskTreeProperties, Task


class BIM_PT_status(Panel):
    bl_label = "Status"
    bl_idname = "BIM_PT_status"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_variance_analysis"

    @classmethod
    def poll(cls, context):
        props = tool.Sequence.get_work_schedule_props()
        return props and props.active_work_schedule_id and props.editing_type == "TASKS"

    def draw(self, context):

        # ColorType maintenance buttons

        row = self.layout.row(align=True)

        row.operator('bim.cleanup_colortype_groups', icon='TRASH', text='Clean Invalid ColorTypes')

        row.operator('bim.initialize_colortype_system', icon='PLUS', text='Init DEFAULT All Tasks')


        self.props = tool.Sequence.get_status_props()

        assert self.layout
        if not self.props.is_enabled:
            row = self.layout.row()
            row.operator("bim.enable_status_filters", icon="GREASEPENCIL")
            return

        row = self.layout.row(align=True)
        row.label(text="Statuses found in the project:")
        row.operator("bim.activate_status_filters", icon="FILE_REFRESH", text="")
        row.operator("bim.disable_status_filters", icon="CANCEL", text="")

        for status in self.props.statuses:
            row = self.layout.row(align=True)
            row.label(text=status.name)
            row.prop(status, "is_visible", text="", emboss=False, icon="HIDE_OFF" if status.is_visible else "HIDE_ON")
            row.operator("bim.select_status_filter", icon="RESTRICT_SELECT_OFF", text="").name = status.name


class BIM_PT_work_plans(Panel):
    bl_label = "Work Plans"
    bl_idname = "BIM_PT_work_plans"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_tab_sequence"

    @classmethod
    def poll(cls, context):
        file = tool.Ifc.get()
        return file and file.schema != "IFC2X3"

    def draw(self, context):
        if not WorkPlansData.is_loaded:
            WorkPlansData.load()
        assert self.layout
        self.props = tool.Sequence.get_work_plan_props()

        row = self.layout.row()
        if WorkPlansData.data["total_work_plans"]:
            row.label(text=f"{WorkPlansData.data['total_work_plans']} Work Plans Found", icon="TEXT")
        else:
            row.label(text="No Work Plans found.", icon="TEXT")
        row.operator("bim.add_work_plan", icon="ADD", text="")
        for work_plan in WorkPlansData.data["work_plans"]:
            self.draw_work_plan_ui(work_plan)

    def draw_work_plan_ui(self, work_plan: dict[str, Any]) -> None:
        row = self.layout.row(align=True)
        row.label(text=work_plan["name"], icon="TEXT")
        if self.props.active_work_plan_id == work_plan["id"]:
            if self.props.editing_type == "ATTRIBUTES":
                row.operator("bim.edit_work_plan", text="", icon="CHECKMARK")
            row.operator("bim.disable_editing_work_plan", text="Cancel", icon="CANCEL")
        elif self.props.active_work_plan_id:
            row.operator("bim.remove_work_plan", text="", icon="X").work_plan = work_plan["id"]
        else:
            op = row.operator("bim.enable_editing_work_plan_schedules", text="", icon="LINENUMBERS_ON")
            op.work_plan = work_plan["id"]
            op = row.operator("bim.enable_editing_work_plan", text="", icon="GREASEPENCIL")
            op.work_plan = work_plan["id"]
            row.operator("bim.remove_work_plan", text="", icon="X").work_plan = work_plan["id"]

        if self.props.active_work_plan_id == work_plan["id"]:
            if self.props.editing_type == "ATTRIBUTES":
                self.draw_editable_ui()
            elif self.props.editing_type == "SCHEDULES":
                self.draw_work_schedule_ui()

    def draw_editable_ui(self) -> None:
        draw_attributes(self.props.work_plan_attributes, self.layout)

    def draw_work_schedule_ui(self) -> None:
        if WorkPlansData.data["has_work_schedules"]:
            row = self.layout.row(align=True)
            row.prop(self.props, "work_schedules", text="")
            op = row.operator("bim.assign_work_schedule", text="", icon="ADD")
            op.work_plan = self.props.active_work_plan_id
            op.work_schedule = int(self.props.work_schedules)
            for work_schedule in WorkPlansData.data["active_work_plan_schedules"]:
                row = self.layout.row(align=True)
                row.label(text=work_schedule["name"], icon="LINENUMBERS_ON")
                op = row.operator("bim.unassign_work_schedule", text="", icon="X")
                op.work_plan = self.props.active_work_plan_id
                op.work_schedule = work_schedule["id"]
        else:
            row = self.layout.row()
            row.label(text="No schedules found. See Work Schedule Panel", icon="INFO")


class BIM_PT_work_schedules(Panel):
    bl_label = "Work Schedules"
    bl_idname = "BIM_PT_work_schedules"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_tab_sequence"

    @classmethod
    def poll(cls, context):
        file = tool.Ifc.get()
        return file and hasattr(file, "schema") and file.schema != "IFC2X3"

    def draw(self, context):
        if not SequenceData.is_loaded:
            SequenceData.load()
        if not WorkScheduleData.is_loaded:
            WorkScheduleData.load()
        self.props = tool.Sequence.get_work_schedule_props()
        self.tprops = tool.Sequence.get_task_tree_props()

        if not self.props.active_work_schedule_id:
            row = self.layout.row(align=True)
            if SequenceData.data["has_work_schedules"]:
                row.label(
                    text="{} Work Schedules Found".format(SequenceData.data["number_of_work_schedules_loaded"]),
                    icon="TEXT",
                )
            else:
                row.label(text="No Work Schedules found.", icon="TEXT")
            row.operator("bim.add_work_schedule", text="", icon="ADD")
            row.operator("bim.import_work_schedule_csv", text="", icon="IMPORT")

        for work_schedule_id, work_schedule in SequenceData.data["work_schedules"].items():
            self.draw_work_schedule_ui(work_schedule_id, work_schedule)

    def draw_work_schedule_ui(self, work_schedule_id: int, work_schedule: dict[str, Any]) -> None:
        assert self.layout
        # CORRECTION: BASELINE schedules should be editable normally
        # Only use readonly UI for specific cases, not for the BASELINE type
        # if work_schedule["PredefinedType"] == "BASELINE":
        #     self.draw_readonly_work_schedule_ui(work_schedule_id)
        # else:
        row = self.layout.row(align=True)
        if self.props.active_work_schedule_id == work_schedule_id:
            row.label(
                text="Currently editing: {}[{}]".format(work_schedule["Name"], work_schedule["PredefinedType"]),
                icon="LINENUMBERS_ON",
            )
            if self.props.editing_type == "WORK_SCHEDULE":
                row.operator("bim.edit_work_schedule", text="", icon="CHECKMARK")
                row.operator("bim.disable_editing_work_schedule", text="", icon="CANCEL")
            elif self.props.editing_type == "TASKS":
                grid = self.layout.grid_flow(columns=2, even_columns=True)
                col = grid.column()
                row1 = col.row(align=True)
                row1.alignment = "LEFT"
                row1.label(text="Schedule tools")
                row1 = col.row(align=True)
                row1.alignment = "RIGHT"
                row1.operator("bim.generate_gantt_chart", text="Generate Gantt", icon="NLA").work_schedule = (
                    work_schedule_id
                )
                row1.operator(
                    "bim.recalculate_schedule", text="Re-calculate Schedule", icon="FILE_REFRESH"
                ).work_schedule = work_schedule_id
                row2 = col.row(align=True)
                row2.alignment = "RIGHT"
                row2.operator(
                    "bim.select_work_schedule_products", text="Select Assigned", icon="RESTRICT_SELECT_OFF"
                ).work_schedule = work_schedule_id
                row2.operator(
                    "bim.select_unassigned_work_schedule_products",
                    text="Select Unassigned",
                    icon="RESTRICT_SELECT_OFF",
                ).work_schedule = work_schedule_id
                if WorkScheduleData.data["can_have_baselines"]:
                    row3 = col.row()
                    row3.alignment = "RIGHT"
                    row3.prop(self.props, "should_show_schedule_baseline_ui", icon="RESTRICT_INSTANCED_OFF")
                col = grid.column()
                row1 = col.row(align=True)
                row1.alignment = "LEFT"
                row1.label(text="Settings")
                row1 = col.row(align=True)
                row1.alignment = "RIGHT"
                
                # --- RESTORE BUTTONS AS THEY WERE ---
                row1.prop(self.props, "should_show_column_ui", text="Schedule Columns", toggle=True, icon="SHORTDISPLAY")
                row1.prop(self.props.filters, "show_filters", text="Filter Tasks", toggle=True, icon="FILTER")

                # --- START: COPY 3D AND SYNC 3D BUTTONS ---
                row_io = col.row(align=True)
                row_io.alignment = 'RIGHT'
                row_io.operator("bim.copy_3d", text="Copy 3D", icon="DUPLICATE")
                row_io.operator("bim.sync_3d", text="Sync 3D", icon="FILE_REFRESH")
                # --- END: COPY 3D AND SYNC 3D BUTTONS ---
                
                row2 = col.row(align=True)
                row.operator("bim.disable_editing_work_schedule", text="Cancel", icon="CANCEL")
        else:
            # NO EDITANDO: Mostrar los 4 botones para cualquier cronograma
            grid = self.layout.grid_flow(columns=2, even_columns=True)
            col1 = grid.column()
            col1.label(
                text="{}[{}]".format(work_schedule["Name"], work_schedule["PredefinedType"]) or "Unnamed",
                icon="LINENUMBERS_ON",
            )
            col2 = grid.column()
            row = col2.row(align=True)
            row.alignment = "RIGHT"
            row.operator("bim.enable_editing_work_schedule_tasks", text="", icon="ACTION").work_schedule = (
                work_schedule_id
            )
            row.operator("bim.enable_editing_work_schedule", text="", icon="GREASEPENCIL").work_schedule = (
                work_schedule_id
            )
            row.operator("bim.copy_work_schedule", text="", icon="DUPLICATE").work_schedule = work_schedule_id
            row.operator("bim.remove_work_schedule", text="", icon="X").work_schedule = work_schedule_id
            
        # UI adicional cuando se está editando este cronograma específico
        if self.props.active_work_schedule_id == work_schedule_id:
            if self.props.editing_type == "WORK_SCHEDULE":
                self.draw_editable_work_schedule_ui()
            elif self.props.editing_type == "TASKS":
                self.draw_baseline_ui(work_schedule_id)
                self.draw_column_ui()
                # RETURN TO THE ORIGINAL SYSTEM - Only call if activated
                if getattr(self.props.filters, "show_filters", False):
                    self.draw_filter_ui()
                self.draw_editable_task_ui(work_schedule_id)

    def draw_task_operators(self) -> None:
        row = self.layout.row(align=True)
        row.alignment = "RIGHT"
        ifc_definition_id = None
        if self.tprops.tasks and self.props.active_task_index < len(self.tprops.tasks):
            task = self.tprops.tasks[self.props.active_task_index]
            ifc_definition_id = task.ifc_definition_id
        if ifc_definition_id:
            if self.props.active_task_id:
                if self.props.editing_task_type == "TASKTIME":
                    row.operator("bim.edit_task_time", text="", icon="CHECKMARK")
                elif self.props.editing_task_type == "ATTRIBUTES":
                    row.operator("bim.edit_task", text="", icon="CHECKMARK")
                row.operator("bim.disable_editing_task", text="Cancel", icon="CANCEL")
            elif self.props.editing_task_type == "SEQUENCE":
                row.operator("bim.disable_editing_task", text="Cancel", icon="CANCEL")
            else:
                row.prop(self.props, "show_task_operators", text="Edit", icon="GREASEPENCIL")
                if self.props.show_task_operators:
                    row2 = self.layout.row(align=True)
                    row2.alignment = "RIGHT"

                    row2.prop(self.props, "enable_reorder", text="", icon="SORTALPHA")
                    row2.operator("bim.enable_editing_task_sequence", text="", icon="TRACKING")
                    row2.operator("bim.enable_editing_task_time", text="", icon="TIME").task = ifc_definition_id
                    row2.operator("bim.enable_editing_task_calendar", text="", icon="VIEW_ORTHO").task = (
                        ifc_definition_id
                    )
                    row2.operator("bim.enable_editing_task_attributes", text="", icon="GREASEPENCIL").task = (
                        ifc_definition_id
                    )
                row.operator("bim.add_task", text="Add", icon="ADD").task = ifc_definition_id
                row.operator("bim.duplicate_task", text="Copy", icon="DUPLICATE").task = ifc_definition_id
                row.operator("bim.remove_task", text="Delete", icon="X").task = ifc_definition_id

    def draw_column_ui(self) -> None:
        if not self.props.should_show_column_ui:
            return
        assert self.layout
        row = self.layout.row()
        row.operator("bim.setup_default_task_columns", text="Setup Default Columns", icon="ANCHOR_BOTTOM")
        row.alignment = "RIGHT"
        row = self.layout.row(align=True)
        row.prop(self.props, "column_types", text="")
        column_type = self.props.column_types
        if column_type == "IfcTask":
            row.prop(self.props, "task_columns", text="")
            name, data_type = self.props.task_columns.split("/")
        elif column_type == "IfcTaskTime":
            row.prop(self.props, "task_time_columns", text="")
            name, data_type = self.props.task_time_columns.split("/")
        elif column_type == "Special":
            row.prop(self.props, "other_columns", text="")
            column_type, name = self.props.other_columns.split(".")
            data_type = "string"
        row.operator("bim.set_task_sort_column", text="", icon="SORTALPHA").column = f"{column_type}.{name}"
        row.prop(
            self.props, "is_sort_reversed", text="", icon="SORT_DESC" if self.props.is_sort_reversed else "SORT_ASC"
        )
        op = row.operator("bim.add_task_column", text="", icon="ADD")
        op.column_type = column_type
        op.name = name
        op.data_type = data_type

        # === RESTORE THE COLUMNS CANVAS ===
        self.layout.template_list("BIM_UL_task_columns", "", self.props, "columns", self.props, "active_column_index")
    # Reemplaza el método draw_filter_ui existente en ui.py con este

    def draw_filter_ui(self) -> None:
        """Draws the filter configuration panel with the final corrected structure."""
        props = self.props

        if not getattr(props.filters, "show_filters", False):
            return

        main_box = self.layout.box()

        # 1. Static title "Smart Filter"
        header_row = main_box.row(align=True)
        header_row.label(text="Smart Filter", icon="FILTER")


        # Date source selector for filters, making it more accessible.
        date_source_row = main_box.row(align=True)
        date_source_row.label(text="Filter Date Source:")
        date_source_row.prop(props, "date_source_type", text="")
        # --- END OF MODIFICATION ---

        # 2. Active filters panel
        active_filters_box = main_box.box()
        row = active_filters_box.row(align=True)
        row.prop(props.filters, "logic", text="")
    
        # Presets Menu
        row.operator_menu_enum("bim.apply_lookahead_filter", "time_window", text="Lookahead", icon="TIME")
      
        row.operator("bim.add_task_filter", text="", icon='ADD')
        row.operator("bim.remove_task_filter", text="", icon='REMOVE')

        row.separator()
        row.operator("bim.apply_task_filters", text="Apply Filters", icon="FILE_REFRESH")
        row.operator("bim.clear_all_task_filters", text="Clean", icon="CANCEL")
       

        active_filters_box.template_list(
            "BIM_UL_task_filters", "",
            props.filters, "rules",
            props.filters, "active_rule_index"
        )

        active_filters_count = len([r for r in props.filters.rules if r.is_active])
        if active_filters_count > 0:
            info_row = active_filters_box.row()
            info_row.label(text=f"ℹ️ {active_filters_count} active filter(s)", icon='INFO')

        # 3. Saved Filters Panel (now collapsible)
        saved_filters_box = main_box.box()
        row = saved_filters_box.row(align=True)

        # The title is now a button to show/hide the section
        icon = 'TRIA_DOWN' if props.filters.show_saved_filters else 'TRIA_RIGHT'
        row.prop(props.filters, "show_saved_filters", text="Saved Filters", icon=icon, emboss=False)
        # --- END OF MODIFICATION ---

        # The content is only drawn if the section is expanded
        if props.filters.show_saved_filters:
            saved_filters_box.template_list(
                "BIM_UL_saved_filter_sets", "",
                props, "saved_filter_sets",
                props, "active_saved_filter_set_index"
            )

            row_ops = saved_filters_box.row(align=True)
            row_ops.enabled = len(props.saved_filter_sets) > 0

            load_op = row_ops.operator("bim.load_filter_set", text="Load", icon="FILE_TICK")
            load_op.set_index = props.active_saved_filter_set_index

            update_op = row_ops.operator("bim.update_saved_filter_set", text="Update", icon="FILE_REFRESH")
            update_op.set_index = props.active_saved_filter_set_index
           

            remove_op = row_ops.operator("bim.remove_filter_set", text="Remove", icon="TRASH")
            remove_op.set_index = props.active_saved_filter_set_index

            row_io = saved_filters_box.row(align=True)
            row_io.operator("bim.save_filter_set", text="Save Current", icon="PINNED")
            row_io.operator("bim.import_filter_set", text="Import Library", icon="IMPORT")
            row_io.operator("bim.export_filter_set", text="Export Library", icon="EXPORT")




    def draw_editable_work_schedule_ui(self):
        draw_attributes(self.props.work_schedule_attributes, self.layout)

    def draw_editable_task_ui(self, work_schedule_id: int) -> None:
        assert self.layout

        # The call to self.draw_filter_ui() was removed from here
        # as it is correctly called in draw_work_schedule_ui()
        
        row = self.layout.row(align=True)
        row.label(text="Task Tools")
        

        row = self.layout.row(align=True)
        
        # 1. Dividimos la fila. La primera columna (izquierda) será para el checkbox.
        #    Usamos un factor pequeño para darle un espacio limitado.
        split = row.split(factor=0.15)
        
        # 2. Colocamos el checkbox en la columna izquierda.
        #    Ahora está contenido y no se puede estirar más allá de este 25%.
        col_izquierda = split.column()
        col_izquierda.prop(self.props, "should_select_3d_on_task_click", text="3D Task", icon="RESTRICT_SELECT_OFF")
        
        # 3. Usamos la segunda columna para los botones de la derecha.
        col_derecha = split.column()
        
        # 4. Creamos una sub-fila DENTRO de la columna derecha para alinear los botones.
        sub_fila_botones = col_derecha.row(align=True)
        sub_fila_botones.alignment = 'RIGHT' # Esto los pega a la derecha de SU columna.
        
        sub_fila_botones.operator("bim.refresh_task_output_counts", text="", icon="FILE_REFRESH")
        sub_fila_botones.operator("bim.add_summary_task", text="Add Summary Task", icon="ADD").work_schedule = work_schedule_id
        sub_fila_botones.operator("bim.expand_all_tasks", text="Expand All")
        sub_fila_botones.operator("bim.contract_all_tasks", text="Contract All")
        row = self.layout.row(align=True)
        self.draw_task_operators()
        BIM_UL_tasks.draw_header(self.layout)
        self.layout.template_list(
            "BIM_UL_tasks",
            "",
            self.tprops,
            "tasks",
            self.props,
            "active_task_index",
        )

        if self.props.active_task_id and self.props.editing_task_type == "ATTRIBUTES":
            self.draw_editable_task_attributes_ui()
        elif self.props.active_task_id and self.props.editing_task_type == "CALENDAR":
            self.draw_editable_task_calendar_ui()
        elif self.props.highlighted_task_id and self.props.editing_task_type == "SEQUENCE":
            self.draw_editable_task_sequence_ui()
        elif self.props.active_task_time_id and self.props.editing_task_type == "TASKTIME":
            self.draw_editable_task_time_attributes_ui()

    def draw_editable_task_sequence_ui(self):
        task = SequenceData.data["tasks"][self.props.highlighted_task_id]
        row = self.layout.row()
        row.label(text="{} Predecessors".format(len(task["IsSuccessorFrom"])), icon="BACK")
        for sequence_id in task["IsSuccessorFrom"]:
            self.draw_editable_sequence_ui(SequenceData.data["sequences"][sequence_id], "RelatingProcess")

        row = self.layout.row()
        row.label(text="{} Successors".format(len(task["IsPredecessorTo"])), icon="FORWARD")
        for sequence_id in task["IsPredecessorTo"]:
            self.draw_editable_sequence_ui(SequenceData.data["sequences"][sequence_id], "RelatedProcess")

    def draw_editable_sequence_ui(self, sequence, process_type):
        task = SequenceData.data["tasks"][sequence[process_type]]
        row = self.layout.row(align=True)
        row.operator("bim.go_to_task", text="", icon="RESTRICT_SELECT_OFF").task = task["id"]
        row.label(text=task["Identification"] or "XXX")
        row.label(text=task["Name"] or "Unnamed")
        row.label(text=sequence["SequenceType"] or "N/A")
        if sequence["TimeLag"]:
            row.operator("bim.unassign_lag_time", text="", icon="X").sequence = sequence["id"]
            row.label(text=isodate.duration_isoformat(SequenceData.data["lag_times"][sequence["TimeLag"]]["LagValue"]))
        else:
            row.operator("bim.assign_lag_time", text="Add Time Lag", icon="ADD").sequence = sequence["id"]
        if self.props.active_sequence_id == sequence["id"]:
            if self.props.editing_sequence_type == "ATTRIBUTES":
                row.operator("bim.edit_sequence_attributes", text="", icon="CHECKMARK")
                row.operator("bim.disable_editing_sequence", text="Cancel", icon="CANCEL")
                self.draw_editable_sequence_attributes_ui()
            elif self.props.editing_sequence_type == "LAG_TIME":
                op = row.operator("bim.edit_sequence_lag_time", text="", icon="CHECKMARK")
                op.lag_time = sequence["TimeLag"]
                row.operator("bim.disable_editing_sequence", text="Cancel", icon="CANCEL")
                self.draw_editable_sequence_lag_time_ui()
        else:
            if sequence["TimeLag"]:
                op = row.operator("bim.enable_editing_sequence_lag_time", text="Edit Time Lag", icon="CON_LOCKTRACK")
                op.sequence = sequence["id"]
                op.lag_time = sequence["TimeLag"]
            op = row.operator("bim.enable_editing_sequence_attributes", text="Edit Sequence", icon="GREASEPENCIL")
            op.sequence = sequence["id"]
            if process_type == "RelatingProcess":
                op = row.operator("bim.unassign_predecessor", text="", icon="X")
            elif process_type == "RelatedProcess":
                op = row.operator("bim.unassign_successor", text="", icon="X")
            op.task = task["id"]

    def draw_editable_sequence_attributes_ui(self):
        bonsai.bim.helper.draw_attributes(self.props.sequence_attributes, self.layout)

    def draw_editable_sequence_lag_time_ui(self):
        bonsai.bim.helper.draw_attributes(self.props.lag_time_attributes, self.layout)

    def draw_editable_task_calendar_ui(self):
        task = SequenceData.data["tasks"][self.props.active_task_id]
        if task["HasAssignmentsWorkCalendar"]:
            row = self.layout.row(align=True)
            calendar = SequenceData.data["work_calendars"][task["HasAssignmentsWorkCalendar"][0]]
            row.label(text=calendar["Name"] or "Unnamed")
            op = row.operator("bim.remove_task_calendar", text="", icon="X")
            op.work_calendar = task["HasAssignmentsWorkCalendar"][0]
            op.task = self.props.active_task_id
        elif SequenceData.data["has_work_calendars"]:
            row = self.layout.row(align=True)
            row.prop(self.props, "work_calendars", text="")
            op = row.operator("bim.edit_task_calendar", text="", icon="ADD")
            op.work_calendar = int(self.props.work_calendars)
            op.task = self.props.active_task_id
        else:
            row = self.layout.row(align=True)
            row.label(text="Must Create a Calendar First. See Work Calendar Panel", icon="INFO")

    def draw_editable_task_attributes_ui(self):
        # Draw attributes but inject Animation Color Schemes after 'Priority'
        try:
            attrs = [a for a in self.props.task_attributes if a.name != "PredefinedType"]
        except Exception:
            attrs = list(self.props.task_attributes)

        # Split at Priority
        before = []
        after = []
        found = False
        for a in attrs:
            before.append(a)
            if a.name == "Priority":
                found = True
                break
        if found:
            after = attrs[len(before):]

        import bonsai.bim.helper as _h
        _h.draw_attributes(before, self.layout, copy_operator="bim.copy_task_attribute")


        # --- Draw PredefinedType exactly below Priority (as in Blender 4.2.1) ---
        try:
            _predef = None
            for _a in self.props.task_attributes:
                if getattr(_a, "name", "") == "PredefinedType":
                    _predef = _a
                    break
            if _predef is not None:
                _h.draw_attributes([_predef], self.layout, copy_operator="bim.copy_task_attribute")
        except Exception:
            pass
        # --- end PredefinedType ---

        # Ensures that the active task has its DEFAULT group synchronized when drawn
        try:
            from bonsai.bim.module.sequence.prop.animation import UnifiedColorTypeManager

            tprops = tool.Sequence.get_task_tree_props()
            if tprops.tasks and self.props.active_task_index < len(tprops.tasks):
                active_task_pg = tprops.tasks[self.props.active_task_index]
                # Call to the central logic to synchronize at the time of drawing
                # Only if there are no custom groups
                user_groups = UnifiedColorTypeManager.get_user_created_groups(bpy.context)
                if not user_groups:
                    UnifiedColorTypeManager.sync_default_group_to_predefinedtype(bpy.context, active_task_pg)
        except Exception as e:
            # It should not break the UI if something fails
            print(f"⚠ Error synchronizing DEFAULT in the UI: {e}")
        # === CORRECTED SECTION: Custom Appearance Groups ===
        try:
            if self.tprops.tasks and self.props.active_task_index < len(self.tprops.tasks):
                _task = self.tprops.tasks[self.props.active_task_index]
                animation_props = tool.Sequence.get_animation_props()

                # CORRECTION: Use the correctly implemented functions
                all_groups = UnifiedColorTypeManager.get_all_groups(bpy.context)
                user_groups = UnifiedColorTypeManager.get_user_created_groups(bpy.context)

                # Show information of selected tasks
                selected_count = len([task for task in self.tprops.tasks if getattr(task, 'is_selected', False)])

                # Always show the section if there are available groups
                if all_groups:
                    box = self.layout.box()

                    # Header with information
                    header_row = box.row(align=True)
                    header_row.label(text="colortype Group Assignment:", icon="GROUP")

                    # Information of selected tasks
                    if selected_count > 0:
                        info_row = box.row()
                        info_row.label(text=f"📋 {selected_count} tasks selected for copying", icon='INFO')

                        # Copy button
                        copy_row = box.row(align=True)
                        copy_op = copy_row.operator("bim.copy_task_custom_colortype_group", text="Copy Configuration to Selected", icon="COPYDOWN")
                        copy_op.enabled = selected_count > 0

                    # Custom group selector (only custom groups)
                    if user_groups:
                        row = box.row(align=True)
                        row.label(text="Custom Group:")
                        row.prop(animation_props, "task_colortype_group_selector", text="")

                        # Show profile selector if a group is selected
                        current_group = getattr(animation_props, 'task_colortype_group_selector', '')
                        if current_group and current_group != "DEFAULT":
                            row = box.row(align=True)
                            row.label(text="colortype:")
                            row.prop(_task, "selected_colortype_in_active_group", text="")

                            # Toggle para habilitar/deshabilitar
                            if getattr(_task, "selected_colortype_in_active_group", ""):
                                row = box.row(align=True)
                                row.prop(_task, "use_active_colortype_group", text="Enable custom assignment")
                        else:
                            # Show message when no group is selected
                            info_row = box.row()
                            info_row.label(text="ℹ️ Select a custom group to assign colortypes", icon='INFO')
                    else:
                        # Message when there are no custom groups
                        info_row = box.row()
                        info_row.label(text="ℹ️ No custom groups available. Create one in Animation Color Scheme.", icon='INFO')

                # Collapsible section of saved profiles (simplified)
                row_saved = self.layout.row(align=True)
                icon = 'TRIA_DOWN' if self.props.show_saved_colortypes_section else 'TRIA_RIGHT'
                row_saved.prop(self.props, "show_saved_colortypes_section", text="colortype Assignments Summary", icon=icon, emboss=False)

                if self.props.show_saved_colortypes_section:
                    sumbox = self.layout.box()

                    # Show assignments of the current task
                    if hasattr(_task, "colortype_group_choices") and _task.colortype_group_choices:
                        # Sort: DEFAULT first, then alphabetically
                        sorted_choices = sorted(_task.colortype_group_choices,
                                              key=lambda x: (x.group_name != "DEFAULT", x.group_name))

                        for choice in sorted_choices:
                            row = sumbox.row(align=True)

                            # Different icon for DEFAULT vs custom
                            icon = 'PINNED' if choice.group_name == "DEFAULT" else 'DOT'
                            if choice.enabled:
                                icon = 'RADIOBUT_ON' if choice.group_name != "DEFAULT" else 'PINNED'

                            # Show information
                            colortype_name = choice.selected_colortype or "(no colortype)"
                            status = "✓" if choice.enabled else "○"

                            row.label(text=f"{status} {choice.group_name} → {colortype_name}", icon=icon)
                    else:
                        # Initialize if there is no data
                        info_row = sumbox.row()
                        info_row.label(text="No colortype assignments found", icon='INFO')
                        init_button = sumbox.row()
                        init_button.operator('bim.initialize_colortype_system', text="Initialize colortype Assignments", icon='PLUS')

        except Exception as e:
            # Fallback si algo falla
            # Fallback if something fails
            error_box = self.layout.box()
            error_box.label(text=f"colortype system error: {str(e)}", icon='ERROR')
            error_box.operator('bim.initialize_colortype_system', text="Repair colortype System", icon='TOOL_SETTINGS')
    
    def draw_editable_task_time_attributes_ui(self):
        bonsai.bim.helper.draw_attributes(self.props.task_time_attributes, self.layout)

    def draw_baseline_ui(self, work_schedule_id):
        if not self.props.should_show_schedule_baseline_ui:
            return
        row3 = self.layout.row()
        row3.alignment = "RIGHT"
        row3.operator("bim.create_baseline", text="Add Baseline", icon="ADD").work_schedule = work_schedule_id
        if WorkScheduleData.data["active_work_schedule_baselines"]:
            for baseline in WorkScheduleData.data["active_work_schedule_baselines"]:
                baseline_row = self.layout.row()
                baseline_row.alignment = "RIGHT"
                baseline_row.label(
                    text="{} @ {}".format(baseline["name"], baseline["date"]), icon="RESTRICT_INSTANCED_OFF"
                )
                baseline_row.operator("bim.generate_gantt_chart", text="Compare", icon="NLA").work_schedule = baseline[
                    "id"
                ]
                baseline_row.operator(
                    "bim.enable_editing_work_schedule_tasks", text="Display Schedule", icon="ACTION"
                ).work_schedule = baseline["id"]
                baseline_row.operator("bim.remove_work_schedule", text="", icon="X").work_schedule = baseline["id"]

    def draw_readonly_work_schedule_ui(self, work_schedule_id):
        if self.props.active_work_schedule_id == work_schedule_id:
            row = self.layout.row()
            row.alignment = "RIGHT"
            row.operator("bim.disable_editing_work_schedule", text="Disable editing", icon="CANCEL")
            grid = self.layout.grid_flow(columns=2, even_columns=True)
            col = grid.column()
            row1 = col.row(align=True)
            row1.alignment = "LEFT"
            row1.label(text="Settings")
            row1 = col.row(align=True)
            row1.alignment = "RIGHT"
            row1.prop(self.props, "should_show_column_ui", text="Schedule Columns", icon="SHORTDISPLAY")
            row2 = col.row(align=True)
            if self.props.editing_type == "TASKS":
                self.draw_column_ui()
                # ELIMINADO: self.draw_filter_ui() - esto puede estar causando el problema
                self.layout.template_list(
                    "BIM_UL_tasks",
                    "",
                    self.tprops,
                    "tasks",
                    self.props,
                    "active_task_index",
                )
        else:
            # CORRECCION: Agregar barra con 4 botones para BASELINE cuando no está activo
            # This is similar to lines 254-271 but for the BASELINE case
            # This function should no longer be used for BASELINE schedules
            # BASELINEs now use the normal UI to allow full editing
            work_schedule = SequenceData.data["work_schedules"].get(work_schedule_id, {})
            grid = self.layout.grid_flow(columns=2, even_columns=True)
            col1 = grid.column()
            col1.label(
                text="{}[{}]".format(work_schedule.get("Name", "Unnamed"), work_schedule.get("PredefinedType", "BASELINE")),
                icon="LINENUMBERS_ON",
            )
            col2 = grid.column()
            row = col2.row(align=True)
            row.alignment = "RIGHT"
            # The 4 specific buttons that should appear for readonly cases
            row.operator("bim.enable_editing_work_schedule_tasks", text="", icon="ACTION").work_schedule = work_schedule_id
            row.operator("bim.enable_editing_work_schedule", text="", icon="GREASEPENCIL").work_schedule = work_schedule_id
            row.operator("bim.copy_work_schedule", text="", icon="DUPLICATE").work_schedule = work_schedule_id
            row.operator("bim.remove_work_schedule", text="", icon="X").work_schedule = work_schedule_id



class BIM_UL_animation_group_stack(UIList):
    bl_idname = "BIM_UL_animation_group_stack"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.group)

    def invoke(self, context, event):
        pass


class BIM_PT_animation_tools(Panel):
    bl_label = "Animation Tools"
    bl_idname = "BIM_PT_animation_tools"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_tab_sequence"
    bl_order = 3

    @classmethod
    def poll(cls, context):
        return True

    def draw_processing_options(self):
        layout = self.layout
        self.animation_props = tool.Sequence.get_animation_props()
        camera_props = self.animation_props.camera_orbit

        box = layout.box()
        col = box.column(align=True)

        row = col.row(align=True)
        # Changed to a toggle button for a more consistent UI style, as requested.
        row.prop(camera_props, "show_camera_orbit_settings", text="Camera & Orbit Settings", toggle=True, icon='CAMERA_DATA')

        if camera_props.show_camera_orbit_settings:
            self.draw_camera_orbit_ui()

    def draw_hud_settings_section(self, layout):
        """Dibuja la sección completa del HUD como panel independiente"""
        """Draws the complete HUD section as an independent panel"""
        try:
            camera_props = self.animation_props.camera_orbit
            hud_box = layout.box()

            # Main HUD header with expandable arrow
            hud_header = hud_box.row(align=True)
            # Changed to a toggle button for a more consistent UI style, as requested.
            hud_header.prop(camera_props, "expand_hud_settings", text="Schedule HUD", toggle=True, icon='SCRIPTPLUGINS')

            # Complete HUD settings (only if expanded)
            if camera_props.expand_hud_settings:
                self.draw_camera_hud_settings(hud_box)

        except Exception as e:
            # Fallback si hay problemas
            error_box = layout.box()
            error_box.label(text="Schedule HUD", icon="VIEW_CAMERA")
            error_box.label(text=f"Error: {str(e)}", icon='ERROR')

    def draw_visualisation_ui(self):
        # Appearance Groups (Animation): priority-ordered, selectable & re-orderable
        box = self.layout.box()
        col = box.column(align=True)
        col.label(text="Animation Groups (For Animation/Snapshot):")
        row = col.row()
        row.template_list("BIM_UL_animation_group_stack", "", self.animation_props, "animation_group_stack", self.animation_props, "animation_group_stack_index", rows=3)
        col2 = row.column(align=True)
        # Always enabled: Add
        col2.operator("bim.anim_group_stack_add", text="", icon="ADD")
        # Compute current selection and total for enabling logic
        idx = self.animation_props.animation_group_stack_index
        total = len(self.animation_props.animation_group_stack)
        # Remove: enabled only when a valid item is selected
        _row = col2.row(align=True)
        _row.enabled = (0 <= idx < total)
        _row.operator("bim.anim_group_stack_remove", text="", icon="REMOVE")
        col2.separator()
        # Move Up: enabled only when not the first item
        _row = col2.row(align=True)
        _row.enabled = (idx > 0)
        op = _row.operator("bim.anim_group_stack_move", text="", icon="TRIA_UP")
        op.direction = "UP"
        # Move Down: enabled only when not the last item
        _row = col2.row(align=True)
        _row.enabled = (0 <= idx < total - 1)
        op = _row.operator("bim.anim_group_stack_move", text="", icon="TRIA_DOWN")
        op.direction = "DOWN"

        if not AnimationColorSchemeData.is_loaded:
            AnimationColorSchemeData.load()

        row = self.layout.row(align=True)
        row.label(text="Start Date/ Date Range:", icon="CAMERA_DATA")

        row = self.layout.row(align=True)
        
        # Display schedule type selection without sync auto functionality
        row.prop(self.props, "date_source_type", expand=True)


        # --- REMOVED: Duplicated date source selector ---
        # Note: Using custom buttons above instead of expand=True to avoid duplication
        

        row = self.layout.row(align=True)
        row.alignment = "RIGHT"
        def _label_from_iso(val, placeholder):
            try:
                if not val or val.strip() in ("", "-"):
                    return placeholder
                return val.split("T")[0]
            except Exception:
                return placeholder
        op = row.operator("bim.datepicker", text=_label_from_iso(self.props.visualisation_start, "Start Date"), icon="REW")
        op.target_prop = "BIMWorkScheduleProperties.visualisation_start"
        op = row.operator("bim.datepicker", text=_label_from_iso(self.props.visualisation_finish, "Finish Date"), icon="FF")
        op.target_prop = "BIMWorkScheduleProperties.visualisation_finish"
        op = row.operator("bim.guess_date_range", text="Guess", icon="FILE_REFRESH")
        op.work_schedule = self.props.active_work_schedule_id

        row = self.layout.row(align=True)
        row.label(text="Speed Settings")
        row = self.layout.row(align=True)
        row.alignment = "RIGHT"
        row.prop(self.props, "speed_types", text="")
        if self.props.speed_types == "FRAME_SPEED":
            row.prop(self.props, "speed_animation_frames", text="")
            row.prop(self.props, "speed_real_duration", text="")
        elif self.props.speed_types == "DURATION_SPEED":
            row.prop(self.props, "speed_animation_duration", text="")
            row.label(text="->")
            row.prop(self.props, "speed_real_duration", text="")
        elif self.props.speed_types == "MULTIPLIER_SPEED":
            row.prop(self.props, "speed_multiplier", text="")

        # --- Display Settings Section ---
        row.label(text="Display Settings")
        row = self.layout.row(align=True)
        row.prop(self.animation_props, "should_show_task_bar_options", text="Task Bars", toggle=True, icon="NLA_PUSHDOWN")
        row.prop(self.animation_props, "enable_live_color_updates", text="Live Color Scheme Update", toggle=True)
        row.label(text="", icon='INFO')

        if self.animation_props.should_show_task_bar_options:
            box = self.layout.box()
            row = box.row()
            row.label(text="Task Bar Options", icon="NLA_PUSHDOWN")

            # NEW: Show schedule information for Task Bars
            try:
                schedule_start, schedule_finish = tool.Sequence.get_schedule_date_range()
                if schedule_start and schedule_finish:
                    info_row = box.row()
                    info_row.label(text=f"📅 Schedule: {schedule_start.strftime('%Y-%m-%d')} to {schedule_finish.strftime('%Y-%m-%d')}", icon='TIME')
                    info_row = box.row()
                    info_row.label(text="ℹ️ Task bars align with schedule dates (independent of animation settings)", icon='INFO')
                else:
                    info_row = box.row()
                    info_row.label(text="⚠️ No schedule dates available", icon='ERROR')
            except Exception:
                pass


            # Enable task selection
            row = box.row(align=True)
            row.prop(self.props, "should_show_task_bar_selection", text="Enable Selection", icon="CHECKBOX_HLT")

            # Show selected task counter
            task_count = len(tool.Sequence.get_task_bar_list())
            if task_count > 0:
                row.label(text=f"({task_count} selected)")

            # Button to generate bars
            row = box.row(align=True)
            row.operator("bim.add_task_bars", text="Generate Bars", icon="VIEW3D")

            # If there are selected tasks, show option to clear
            if task_count > 0:
                row.operator("bim.clear_task_bars", text="Clear", icon="TRASH")

            # Colores de las barras
            grid = box.grid_flow(columns=2, even_columns=True)
            col = grid.column()
            row = col.row(align=True)
            row.prop(self.animation_props, "color_progress")

            col = grid.column()
            row = col.row(align=True)
            row.prop(self.animation_props, "color_full")

        self.layout.separator()  # Visual separator

        row = self.layout.row(align=True)
        row.alignment = "RIGHT"

        # Selector de esquema de colores (opcional, ya no se usa)
        if AnimationColorSchemeData.data.get("saved_color_schemes"):
            row.prop(
                self.animation_props,
                "saved_color_schemes",
                text="Color Scheme",
                icon=tool.Blender.SEQUENCE_COLOR_SCHEME_ICON,
            )

        
        # Selector de esquema de colores (opcional, ya no se usa)
        if AnimationColorSchemeData.data.get("saved_color_schemes"):
            row.prop(
                self.animation_props,
                "saved_color_schemes",
                text="Color Scheme",
                icon=tool.Blender.SEQUENCE_COLOR_SCHEME_ICON,
            )

        # === MAIN BUTTONS - Animation Settings ===
        main_actions_box = self.layout.box()
        main_actions_box.label(text="Animation Actions:", icon="OUTLINER_OB_CAMERA")

        # Main button
        main_row = main_actions_box.row()
        op = main_row.operator(
            "bim.visualise_work_schedule_date_range",
            text="Create / Update Animation",
            icon="OUTLINER_OB_CAMERA")
        op.work_schedule = self.props.active_work_schedule_id

        # Reset Button - DUPLICATE
        reset_row = main_actions_box.row()
        reset_row.operator("bim.clear_previous_animation", text="Reset", icon="TRASH")

        # --- Processing Tools (moved below main actions) ---
        self.draw_processing_options()
        
        # === NEW: Independent HUD Settings ===
        self.layout.separator()
        self.draw_hud_settings_section(self.layout)



    def draw_snapshot_ui(self):
        # Asegurar propiedades de animación siempre disponibles
        try:
            import bonsai.tool as tool
            self.animation_props = tool.Sequence.get_animation_props()
        except Exception:
            pass  # Si falla, mantenemos el valor previo si existe

        # Label and date selector
        row = self.layout.row(align=True)
        row.label(text="Date of Snapshot:", icon="CAMERA_STEREO")

        row = self.layout.row(align=True)
        row.alignment = "RIGHT"
        def _label_from_iso(val, placeholder):
            try:
                if not val or val.strip() in ("", "-"):
                    return placeholder
                return val.split("T")[0]
            except Exception:
                return placeholder
        op = row.operator("bim.datepicker", text=_label_from_iso(self.props.visualisation_start, "Date"), icon="PROP_PROJECTED")
        op.target_prop = "BIMWorkScheduleProperties.visualisation_start"

        # Active Profile Group information box (simplified)
        box = self.layout.box()
        row = box.row(align=True)
        
        # Get only the first active group
        active_group = None
        try:
            for stack_item in getattr(self.animation_props, "animation_group_stack", []):
                if getattr(stack_item, "enabled", False) and getattr(stack_item, "group", None):
                    active_group = stack_item.group
                    break
        except Exception:
            active_group = None

        # Simple layout: label on the left, group on the right
        row.label(text="Active colortype Group:", icon='PRESET')
        if active_group:
            row.label(text=active_group)
        else:
            row.label(text="DEFAULT")

        # === SNAPSHOT ACTIONS (moved above camera controls) ===
        actions_box = self.layout.box()
        actions_box.label(text="Snapshot Actions:", icon="RENDER_STILL")

        # Main button to create the snapshot
        main_row = actions_box.row()
        op = main_row.operator("bim.snapshot_with_colortypes_fixed", text="Create SnapShot", icon="CAMERA_STEREO")
        try:
            op.work_schedule = self.props.active_work_schedule_id
        except Exception:
            pass

        # Reset Button (replicating the position of Animation Settings)
        reset_row = actions_box.row()
        reset_row.operator("bim.clear_previous_snapshot", text="Reset", icon="TRASH")

        self.layout.separator()

        # === Snapshot Camera Controls (now below actions) ===
        try:
            import bpy  # Ensure local import in case of partial Blender contexts
            camera_box = self.layout.box()
            camera_header = camera_box.row()
            camera_header.label(text="Snapshot Camera Controls:", icon="CAMERA_DATA")
            camera_row = camera_box.row(align=True)
            camera_row.operator("bim.add_snapshot_camera", text="Add Camera", icon="OUTLINER_OB_CAMERA")
            camera_row.operator("bim.align_snapshot_camera_to_view", text="Align to View", icon="CAMERA_DATA")

            active_cam = bpy.context.scene.camera if bpy.context and bpy.context.scene else None
            info_row = camera_box.row()
            if active_cam:
                info_row.label(text=f"Active: {active_cam.name}", icon="CAMERA_DATA")
            else:
                info_row.label(text="No active camera", icon="ERROR")

            # --- Manage Snapshot Cameras ---
            camera_props = self.animation_props.camera_orbit
            col = camera_box.column(align=True)
            col.separator()
            col.label(text="Manage Snapshot Cameras:", icon="OUTLINER_OB_CAMERA")

            row = col.row(align=True)

            delete_col = row.split(factor=0.5, align=True)
            delete_col.operator("bim.delete_snapshot_camera", text="Delete Snapshot Camera", icon="TRASH")

            row.prop(camera_props, "active_snapshot_camera", text="")
            row.prop(camera_props, "hide_all_snapshot_cameras", text="", icon='HIDE_ON' if camera_props.hide_all_snapshot_cameras else 'HIDE_OFF')
        except Exception:
            pass

        # === NEW: HUD Settings for Snapshot ===
        self.layout.separator()
        self.draw_hud_settings_section(self.layout)

    def draw_camera_orbit_ui(self):
        self.animation_props = tool.Sequence.get_animation_props()
        camera_props = self.animation_props.camera_orbit

        # Camera Block
        box = self.layout.box()
        col = box.column(align=True)
        col.label(text="Camera", icon="CAMERA_DATA")
        row = col.row(align=True)
        row.prop(camera_props, "camera_focal_mm")
        row = col.row(align=True)
        row.prop(camera_props, "camera_clip_start")
        row.prop(camera_props, "camera_clip_end")

        # Orbit Block
        box = self.layout.box()
        col = box.column(align=True)
        col.label(text="Orbit", icon="ORIENTATION_GIMBAL")
        row = col.row(align=True)
        row.prop(camera_props, "orbit_mode", expand=True)

        # Radius, Height, Angle and Direction options
        row = col.row(align=True)
        row.prop(camera_props, "orbit_radius_mode", text="")
        sub = row.row(align=True)
        sub.enabled = camera_props.orbit_radius_mode == "MANUAL"
        sub.prop(camera_props, "orbit_radius", text="")
        row = col.row(align=True)
        row.prop(camera_props, "orbit_height")
        row = col.row(align=True)
        row.prop(camera_props, "orbit_start_angle_deg")
        row.prop(camera_props, "orbit_direction", expand=True)

        # Look At
        col.separator()
        row = col.row(align=True)
        row.prop(camera_props, "look_at_mode", expand=True)
        if camera_props.look_at_mode == "OBJECT":
            col.prop(camera_props, "look_at_object")
        
        # Method and Path Section
        col.separator()
        col.label(text="Animation Method & Path:")
        
        row = col.row(align=True)
        row.prop(camera_props, "orbit_path_shape", expand=True)
        
        if camera_props.orbit_path_shape == 'CUSTOM':
            col.prop(camera_props, "custom_orbit_path")

        row = col.row(align=True)
        row.enabled = camera_props.orbit_path_shape == 'CIRCLE'
        row.prop(camera_props, "orbit_path_method", expand=True)

        # Hide interpolation options for CIRCLE_360 since it always uses LINEAR
        is_circle_360 = camera_props.orbit_path_method == 'CIRCLE_360'
        
        col.prop(camera_props, "hide_orbit_path")
        
        # Duration Options
        col.separator()
        row = col.row(align=True)
        row.prop(camera_props, "orbit_use_4d_duration")
        sub = row.row(align=True)
        sub.enabled = not camera_props.orbit_use_4d_duration
        sub.prop(camera_props, "orbit_duration_frames", text="")

        # Action Buttons
        col.separator()
        action_row = col.row(align=True)
        action_row.operator("bim.align_4d_camera_to_view", text="Align Cam to View", icon="CAMERA_DATA")
        action_row.operator("bim.reset_camera_settings", text="Reset Settings", icon="FILE_REFRESH")

        # --- NEW: 4D Camera Management ---
        col.separator()
        col.label(text="Manage Animation Cameras:", icon="OUTLINER_OB_CAMERA")
        
        # Create a single row for all new camera management controls
        row = col.row(align=True)
        
        # Dividir la fila para balancear los controles: 50% para eliminar, 50% para el resto.
        delete_col = row.split(factor=0.5, align=True)
        
        # Column 1: Delete button
        delete_col.operator("bim.delete_animation_camera", text="Delete Animation Camera", icon="TRASH")
        
        # El selector ahora ocupa la mayor parte del espacio restante, empujando el botón de ocultar a la derecha.
        # Seleccionar una cámara del desplegable ahora la convertirá automáticamente en la cámara activa de la escena.
        row.prop(camera_props, "active_animation_camera", text="")
        row.prop(camera_props, "hide_all_animation_cameras", text="", icon='HIDE_ON' if camera_props.hide_all_animation_cameras else 'HIDE_OFF')

    def draw_camera_hud_settings(self, layout):
        """Dibuja los paneles de configuración para ambos HUDs."""
        camera_props = self.animation_props.camera_orbit

        # --- PANEL FOR THE TEXT HUD ---
        text_hud_box = layout.box()
        text_header = text_hud_box.row(align=True)
        text_header.prop(camera_props, "enable_text_hud", text="")
        icon = 'TRIA_DOWN' if camera_props.expand_schedule_hud else 'TRIA_RIGHT'
        text_header.prop(camera_props, "expand_schedule_hud", text="Text HUD", toggle=True, icon=icon)

        if camera_props.expand_schedule_hud:
            # Visibility Controls for Text HUD elements
            visibility_box = text_hud_box.box()
            visibility_box.label(text="Element Visibility", icon="HIDE_OFF")
            visibility_row1 = visibility_box.row(align=True)
            visibility_row1.prop(camera_props, "hud_show_date", text="Date")
            visibility_row1.prop(camera_props, "hud_show_week", text="Week")
            visibility_row2 = visibility_box.row(align=True)
            visibility_row2.prop(camera_props, "hud_show_day", text="Day")
            visibility_row2.prop(camera_props, "hud_show_progress", text="Progress")

            # ==========================================
            # === LAYOUT - COMPLETE SECTION ===
            # ==========================================
            layout_box = text_hud_box.box()
            layout_box.label(text="Layout", icon="SNAP_GRID")
            layout_box.prop(camera_props, "hud_position", text="Position")

            # Margins
            margin_row = layout_box.row(align=True)
            margin_row.prop(camera_props, "hud_margin_horizontal", text="H-Margin")
            margin_row.prop(camera_props, "hud_margin_vertical", text="V-Margin")

            # Escala y Espaciado de líneas
            spacing_row = layout_box.row(align=True)
            spacing_row.prop(camera_props, "hud_scale_factor", text="Scale")
            if hasattr(camera_props, 'hud_text_spacing'):
                spacing_row.prop(camera_props, "hud_text_spacing", text="Line Spacing")

            # Padding
            if hasattr(camera_props, 'hud_padding_horizontal'):
                padding_row = layout_box.row(align=True)
                padding_row.prop(camera_props, "hud_padding_horizontal", text="H-Padding")
                padding_row.prop(camera_props, "hud_padding_vertical", text="V-Padding")

            # ==========================================
            # === COLORS - COMPLETE SECTION ===
            # ==========================================
            colors_box = text_hud_box.box()
            colors_box.label(text="Colors", icon="COLOR")

            # Basic colors
            if hasattr(camera_props, 'hud_text_color'):
                colors_box.prop(camera_props, "hud_text_color", text="Text")
            if hasattr(camera_props, 'hud_background_color'):
                colors_box.prop(camera_props, "hud_background_color", text="Background")

            # Gradient
            if hasattr(camera_props, 'hud_background_gradient_enabled'):
                gradient_row = colors_box.row()
                gradient_row.prop(camera_props, "hud_background_gradient_enabled", text="Gradient")

                if getattr(camera_props, "hud_background_gradient_enabled", False):
                    colors_box.prop(camera_props, "hud_background_gradient_color", text="Gradient Color")
                    if hasattr(camera_props, 'hud_gradient_direction'):
                        colors_box.prop(camera_props, "hud_gradient_direction", text="Direction")

            # ==========================================
            # === BORDERS & EFFECTS - COMPLETE SECTION ===
            # ==========================================
            effects_box = text_hud_box.box()
            effects_box.label(text="Borders & Effects", icon="MESH_PLANE")

            # Borders
            if hasattr(camera_props, 'hud_border_width'):
                border_row = effects_box.row(align=True)
                border_row.prop(camera_props, "hud_border_width", text="Border Width")
                if getattr(camera_props, "hud_border_width", 0) > 0 and hasattr(camera_props, 'hud_border_color'):
                    border_row.prop(camera_props, "hud_border_color", text="")

            if hasattr(camera_props, 'hud_border_radius'):
                effects_box.prop(camera_props, "hud_border_radius", text="Border Radius")

            # ==========================================
            # === SHADOWS - COMPLETE SECTION ===
            # ==========================================
            shadows_box = text_hud_box.box()
            shadows_box.label(text="Shadows", icon="LIGHT_SUN")

            # Text shadow
            if hasattr(camera_props, 'hud_text_shadow_enabled'):
                text_shadow_row = shadows_box.row()
                text_shadow_row.prop(camera_props, "hud_text_shadow_enabled", text="Text Shadow")

                if getattr(camera_props, "hud_text_shadow_enabled", False):
                    shadow_offset_row = shadows_box.row(align=True)
                    if hasattr(camera_props, 'hud_text_shadow_offset_x'):
                        shadow_offset_row.prop(camera_props, "hud_text_shadow_offset_x", text="X")
                    if hasattr(camera_props, 'hud_text_shadow_offset_y'):
                        shadow_offset_row.prop(camera_props, "hud_text_shadow_offset_y", text="Y")
                    if hasattr(camera_props, 'hud_text_shadow_color'):
                        shadows_box.prop(camera_props, "hud_text_shadow_color", text="Shadow Color")

            # Background shadow
            if hasattr(camera_props, 'hud_background_shadow_enabled'):
                bg_shadow_row = shadows_box.row()
                bg_shadow_row.prop(camera_props, "hud_background_shadow_enabled", text="Background Shadow")

                if getattr(camera_props, "hud_background_shadow_enabled", False):
                    if hasattr(camera_props, 'hud_background_shadow_offset_x'):
                        bg_shadow_offset_row = shadows_box.row(align=True)
                        bg_shadow_offset_row.prop(camera_props, "hud_background_shadow_offset_x", text="X")
                        bg_shadow_offset_row.prop(camera_props, "hud_background_shadow_offset_y", text="Y")
                    if hasattr(camera_props, 'hud_background_shadow_blur'):
                        shadows_box.prop(camera_props, "hud_background_shadow_blur", text="Blur")
                    if hasattr(camera_props, 'hud_background_shadow_color'):
                        shadows_box.prop(camera_props, "hud_background_shadow_color", text="Shadow Color")

            # ==========================================
            # === TYPOGRAPHY - COMPLETE SECTION ===
            # ==========================================
            if hasattr(camera_props, 'hud_font_weight'):
                typo_box = text_hud_box.box()
                typo_box.label(text="Typography", icon="FONT_DATA")

                typo_box.prop(camera_props, "hud_font_weight", text="Weight")
                if hasattr(camera_props, 'hud_letter_spacing'):
                    typo_box.prop(camera_props, "hud_letter_spacing", text="Letter Spacing")

        # ==========================================
        # === TIMELINE HUD - CONFIGURATION PANEL ===
        # ==========================================
        timeline_box = layout.box()
        timeline_header = timeline_box.row(align=True)
        timeline_header.prop(camera_props, "enable_timeline_hud", text="")
        icon = 'TRIA_DOWN' if camera_props.expand_timeline_hud else 'TRIA_RIGHT'
        timeline_header.prop(camera_props, "expand_timeline_hud", text="Timeline HUD", toggle=True, icon=icon)

        if camera_props.expand_timeline_hud:
            timeline_box.prop(camera_props, "timeline_hud_locked", text="Lock Position", icon="LOCKED" if getattr(camera_props, "timeline_hud_locked", True) else "UNLOCKED")
            # Layout & Position
            # Controls according to lock state
            if getattr(camera_props, "timeline_hud_locked", True):
                row = timeline_box.row()
                row.prop(camera_props, "timeline_hud_position", text="Position")
                margin_row = timeline_box.row(align=True)
                margin_row.prop(camera_props, "timeline_hud_margin_horizontal", text="H-Margin")
                margin_row.prop(camera_props, "timeline_hud_margin_vertical", text="V-Margin")
                row = timeline_box.row(align=True)
                row.prop(camera_props, "timeline_hud_height", text="Height")
                row.prop(camera_props, "timeline_hud_width", text="Width")
            else:
                manual_row = timeline_box.row(align=True)
                manual_row.label(text="Manual Position:", icon="TRANSFORM_ORIGINS")
                manual_pos_row = timeline_box.row(align=True)
                manual_pos_row.prop(camera_props, "timeline_hud_manual_x", text="X")
                manual_pos_row.prop(camera_props, "timeline_hud_manual_y", text="Y")
                timeline_box.prop(camera_props, "timeline_hud_height", text="Height")
                timeline_box.prop(camera_props, "timeline_hud_width", text="Width")

            # Colors - Simplified for Synchro 4D Style
            colors_box = timeline_box.box()
            colors_box.label(text="Colors", icon="COLOR")
            colors_box.prop(camera_props, "timeline_hud_color_inactive_range", text="Background")
            colors_box.prop(camera_props, "timeline_hud_color_text", text="Text & Lines")
            colors_box.prop(camera_props, "timeline_hud_color_indicator", text="Current Date Indicator")
            
            # Progress Bar Controls
            progress_row = colors_box.row()
            progress_row.prop(camera_props, "timeline_hud_show_progress_bar", text="Show Progress Bar")
            if getattr(camera_props, "timeline_hud_show_progress_bar", True):
                colors_box.prop(camera_props, "timeline_hud_color_progress", text="Progress Color")
            
            # Style
            style_box = timeline_box.box()
            style_box.label(text="Style", icon="MESH_PLANE")
            style_box.prop(camera_props, "timeline_hud_border_radius", text="Border Radius")

        # ==================== LEGEND HUD ====================
        legend_box = layout.box()
        legend_header = legend_box.row(align=True)
        legend_header.prop(camera_props, "enable_legend_hud", text="")
        icon = 'TRIA_DOWN' if camera_props.expand_legend_hud else 'TRIA_RIGHT'
        legend_header.prop(camera_props, "expand_legend_hud", text="Legend HUD", toggle=True, icon=icon)

        if camera_props.expand_legend_hud:
            # Position & Layout
            position_box = legend_box.box()
            position_box.label(text="Position & Layout", icon="SNAP_GRID")
            
            position_row = position_box.row(align=True)
            position_row.prop(camera_props, "legend_hud_position", text="Position")
            position_row.prop(camera_props, "legend_hud_orientation", text="")
            
            margins_row = position_box.row(align=True)
            margins_row.prop(camera_props, "legend_hud_margin_horizontal", text="Margin H")
            margins_row.prop(camera_props, "legend_hud_margin_vertical", text="Margin V")
            
            scaling_row = position_box.row(align=True)
            scaling_row.prop(camera_props, "legend_hud_scale", text="Scale")
            scaling_row.prop(camera_props, "legend_hud_auto_scale", text="Auto Scale")
            
            if not getattr(camera_props, "legend_hud_auto_scale", True):
                position_box.prop(camera_props, "legend_hud_max_width", text="Max Width")
            
            # Content Settings
            content_box = legend_box.box()
            content_box.label(text="Content", icon="TEXT")
            
            title_row = content_box.row(align=True)
            title_row.prop(camera_props, "legend_hud_show_title", text="Show Title")
            if getattr(camera_props, "legend_hud_show_title", True):
                title_row.prop(camera_props, "legend_hud_title_text", text="",)
                title_row.prop(camera_props, "legend_hud_title_font_size", text="Size")
            
            spacing_row = content_box.row(align=True)
            spacing_row.prop(camera_props, "legend_hud_item_spacing", text="Item Spacing")
            spacing_row.prop(camera_props, "legend_hud_color_indicator_size", text="Color Size")
            
            # colortype Selection with Scrollable List
            colortypes_box = content_box.box()
            colortypes_header = colortypes_box.row(align=True)
            colortypes_header.label(text="colortype Visibility", icon="RESTRICT_VIEW_OFF")
            
            # Get ALL colortypes from the active animation group (NEVER filtered)
            all_colortypes = []
            try:
                import bonsai.tool as tool
                anim_props = tool.Sequence.get_animation_props()
                if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                    # CORRECTION: Only get profiles from the first active group (enabled=True)
                    active_group = None
                    print("🔍 UI: Checking animation group stack for active group:")
                    for i, group_item in enumerate(anim_props.animation_group_stack):
                        enabled = getattr(group_item, 'enabled', False)
                        print(f"  {i}: Group '{group_item.group}' enabled={enabled}")
                        if enabled and active_group is None:
                            active_group = group_item.group
                            print(f"🎯 UI: Selected active group: {active_group}")
                            break
                    
                    # FALLBACK: If there are no active groups, use the first group as a fallback
                    if active_group is None:
                        if anim_props.animation_group_stack:
                            active_group = anim_props.animation_group_stack[0].group
                            print(f"🔄 UI: Using FALLBACK to first group: {active_group}")
                        else:
                            print("❌ UI: No groups available at all")
                    
                    if active_group:
                        print(f"🎯 UI: Getting colortypes from group: {active_group}")
                        
                        # Get colortypes directly from the active group JSON data
                        try:
                            import json
                            scene = bpy.context.scene
                            key = "BIM_AnimationColorSchemesSets"
                            raw_data = scene.get(key, "{}")
                            
                            if isinstance(raw_data, str):
                                colortype_sets = json.loads(raw_data)
                            else:
                                colortype_sets = raw_data or {}
                                
                            if active_group in colortype_sets and 'ColorTypes' in colortype_sets[active_group]:
                                # For the DEFAULT group, always use the hardcoded, predefined order.
                                if active_group == "DEFAULT":
                                    default_order = [
                                        "CONSTRUCTION", "INSTALLATION", "DEMOLITION", "REMOVAL",
                                        "DISPOSAL", "DISMANTLE", "OPERATION", "MAINTENANCE",
                                        "ATTENDANCE", "RENOVATION", "LOGISTIC", "MOVE", "NOTDEFINED"
                                    ]
                                    for colortype_name in default_order:
                                        if colortype_name and colortype_name not in all_colortypes:
                                            all_colortypes.append(colortype_name)
                                            print(f"🎯 UI: Added DEFAULT colortype in predefined order: {colortype_name}")
                                else:
                                    # For custom groups, maintain the order from the JSON file.
                                    for colortype in colortype_sets[active_group]['ColorTypes']:
                                        colortype_name = colortype.get('name', '')
                                        if colortype_name and colortype_name not in all_colortypes:
                                            all_colortypes.append(colortype_name)
                                            print(f"🎯 UI: Added custom colortype to list: {colortype_name}")
                        except Exception as e:
                            print(f"❌ UI: Error getting colortypes from active group {active_group}: {e}")
                    else:
                        print("🎯 UI: No active group found (no enabled groups)")
                            
            except Exception as e:
                print(f"❌ UI: Error getting animation props: {e}")
                all_colortypes = []
                
            print(f"🎯 UI: Total colortypes for settings list: {len(all_colortypes)} - {all_colortypes}")
            
            # Force refresh - make sure we always have the full list
            if not all_colortypes:
                print("⚠️ UI: No colortypes found, trying alternative method...")
                try:
                    # Fallback: try to get from scene property directly
                    scene = bpy.context.scene
                    if hasattr(scene, 'BIMAnimationProperties') and scene.BIMAnimationProperties.ColorType_groups:
                        active_group = scene.BIMAnimationProperties.ColorType_groups
                        print(f"🎯 UI: Fallback - trying group: {active_group}")
                        
                        import json
                        key = "BIM_AnimationColorSchemesSets"
                        raw_data = scene.get(key, "{}")
                        colortype_sets = json.loads(raw_data) if isinstance(raw_data, str) else (raw_data or {})
                        
                        if active_group in colortype_sets and 'ColorTypes' in colortype_sets[active_group]:
                            all_colortypes = [colortype.get('name', '') for colortype in colortype_sets[active_group]['ColorTypes'] if colortype.get('name')]
                            print(f"🎯 UI: Fallback found {len(all_colortypes)} colortypes: {all_colortypes}")
                except Exception as e:
                    print(f"❌ UI: Fallback failed: {e}")
            
            if all_colortypes:
                # Get current scroll position and hidden colortypes
                scroll_offset = getattr(camera_props, 'legend_hud_colortype_scroll_offset', 0)
                colortypes_per_page = 5  # Fixed to show 5 colortypes at a time
                
                # NOTE: legend_hud_visible_colortypes now stores HIDDEN colortypes (inverted logic)
                # By default all colortypes are visible, user unchecks to hide them
                hidden_colortypes_str = getattr(camera_props, 'legend_hud_visible_colortypes', '')
                hidden_colortypes = [p.strip() for p in hidden_colortypes_str.split(',') if p.strip()] if hidden_colortypes_str else []
                
                # Calculate pagination
                total_colortypes = len(all_colortypes)
                max_scroll = max(0, total_colortypes - colortypes_per_page)
                scroll_offset = max(0, min(scroll_offset, max_scroll))
                
                # Navigation controls (only arrows, no text)
                nav_row = colortypes_box.row(align=True)
                nav_row.operator("bim.legend_hud_colortype_scroll_up", text="", icon="TRIA_UP")
                # Spacer to center the arrows
                nav_row.separator()
                nav_row.operator("bim.legend_hud_colortype_scroll_down", text="", icon="TRIA_DOWN")
                
                # colortype checkboxes - All colortypes are always visible in the list
                # Checkbox controls if a colortype appears in the viewport HUD legend
                end_index = min(scroll_offset + colortypes_per_page, total_colortypes)
                print(f"🎯 UI: Displaying colortypes {scroll_offset} to {end_index} of {total_colortypes}")
                print(f"🎯 UI: Hidden colortypes: {hidden_colortypes}")
                
                for i in range(scroll_offset, end_index):
                    if i < len(all_colortypes):  # Safety check
                        colortype_name = all_colortypes[i]
                        colortype_row = colortypes_box.row(align=True)
                        
                        # Checkbox: checked = show in viewport HUD, unchecked = hide from viewport HUD
                        # colortype always remains visible in this settings list
                        is_visible_in_hud = colortype_name not in hidden_colortypes
                        
                        # Use checkbox icon with tilde when checked
                        icon = "CHECKBOX_HLT" if is_visible_in_hud else "CHECKBOX_DEHLT"
                        checkbox_op = colortype_row.operator(
                            "bim.legend_hud_toggle_colortype_visibility", 
                            text="", 
                            icon=icon,
                            depress=False  # Don't use depress, use icon state instead
                        )
                        checkbox_op.colortype_name = colortype_name
                        
                        # colortype name - always visible
                        colortype_row.label(text=colortype_name)
                        
                        print(f"🎯 UI: Showing colortype {i}: {colortype_name} (HUD visible: {is_visible_in_hud})")
                    else:
                        print(f"❌ UI: Index {i} out of range for colortypes list (len: {len(all_colortypes)})")
                    
            else:
                colortypes_box.label(text="No colortypes available", icon="INFO")
            
            # Color Columns
            columns_box = content_box.box()
            columns_box.label(text="Color Columns", icon="COLORSET_01_VEC")
            
            columns_vis_row = columns_box.row(align=True)
            columns_vis_row.prop(camera_props, "legend_hud_show_start_column", text="Start")
            columns_vis_row.prop(camera_props, "legend_hud_show_active_column", text="Active") 
            columns_vis_row.prop(camera_props, "legend_hud_show_end_column", text="End")
            
            titles_vis_row = columns_box.row(align=True)
            titles_vis_row.label(text="Show Titles:")
            if getattr(camera_props, "legend_hud_show_start_column", True):
                titles_vis_row.prop(camera_props, "legend_hud_show_start_title", text="Start", toggle=True)
            if getattr(camera_props, "legend_hud_show_active_column", True):
                titles_vis_row.prop(camera_props, "legend_hud_show_active_title", text="Active", toggle=True)
            if getattr(camera_props, "legend_hud_show_end_column", True):
                titles_vis_row.prop(camera_props, "legend_hud_show_end_title", text="End", toggle=True)
            
            columns_box.prop(camera_props, "legend_hud_column_spacing", text="Column Spacing")
            
            # Styling
            style_box = legend_box.box()
            style_box.label(text="Styling", icon="BRUSH_DATA")
            
            # Background
            bg_row = style_box.row(align=True)
            bg_row.prop(camera_props, "legend_hud_background_color", text="Background")
            bg_row.prop(camera_props, "legend_hud_border_radius", text="Radius")
            
            # Padding
            padding_row = style_box.row(align=True)
            padding_row.prop(camera_props, "legend_hud_padding_horizontal", text="Padding H")
            padding_row.prop(camera_props, "legend_hud_padding_vertical", text="Padding V")
            
            # Text
            text_color_row = style_box.row(align=True)
            text_color_row.prop(camera_props, "legend_hud_text_color", text="Text Color")
            text_color_row.prop(camera_props, "legend_hud_title_color", text="Title Color")
            
            # Text Shadow
            shadow_row = style_box.row(align=True)
            shadow_row.prop(camera_props, "legend_hud_text_shadow_enabled", text="Text Shadow")
            if getattr(camera_props, "legend_hud_text_shadow_enabled", True):
                shadow_row.prop(camera_props, "legend_hud_text_shadow_color", text="")
                
                shadow_offset_row = style_box.row(align=True)
                shadow_offset_row.label(text="Shadow Offset:")
                shadow_offset_row.prop(camera_props, "legend_hud_text_shadow_offset_x", text="X")
                shadow_offset_row.prop(camera_props, "legend_hud_text_shadow_offset_y", text="Y")
        

        # --- 3D Scene Texts ---
        layout.separator()
        
        # 3D HUD Render expandable section
        schedule_box = layout.box()
        schedule_header = schedule_box.row(align=True)
        schedule_header.prop(camera_props, "show_3d_schedule_texts", text="")
        icon = 'TRIA_DOWN' if camera_props.expand_3d_hud_render else 'TRIA_RIGHT'
        schedule_header.prop(camera_props, "expand_3d_hud_render", text="3D HUD Render", toggle=True, icon=icon)

        if camera_props.expand_3d_hud_render:
            self.draw_3d_hud_render_settings(schedule_box)

    def draw(self, context):
        self.props = tool.Sequence.get_work_schedule_props()
        self.animation_props = tool.Sequence.get_animation_props()
        
        row = self.layout.row(align=True)
        row.alignment = "RIGHT"
        row.prop(self.props, "should_show_visualisation_ui", text="Animation Settings", icon="SETTINGS")
        row.prop(self.props, "should_show_snapshot_ui", text="Snapshot Settings", icon="SETTINGS")

        if not (self.props.should_show_visualisation_ui or self.props.should_show_snapshot_ui):
            self.props.should_show_visualisation_ui = True

        if self.props.should_show_visualisation_ui:
            self.draw_visualisation_ui()
        if self.props.should_show_snapshot_ui:
            self.draw_snapshot_ui()


    def draw_3d_hud_render_settings(self, layout):
        """Draw 3D HUD Render settings (empty controls + individual text controls)"""
        import bpy
        import bonsai.tool as tool

        # ==================== 3D LEGEND HUD ====================
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            
            # 3D Legend HUD simple checkbox - NO ICONS
            layout.prop(camera_props, "enable_3d_legend_hud", text="3D Legend HUD")
                    
        except Exception:
            pass # Fail silently if props aren't available

        # --- Parent Empty Controls (from original version) ---
        parent_empty = bpy.data.objects.get("Schedule_Display_Parent")
        if parent_empty:
            box = layout.box()
            row = box.row(align=True)
            row.label(text="Display Group Control", icon="EMPTY_DATA")
            row.prop(parent_empty, "hide_viewport", text="", icon='HIDE_OFF' if not parent_empty.hide_viewport else 'HIDE_ON', emboss=False)

            col = box.column(align=True)
            col.prop(parent_empty, "location", text="Group Position")
            col.prop(parent_empty, "rotation_euler", text="Group Rotation")
            col.prop(parent_empty, "scale", text="Group Scale")

            # --- Custom Rotation Constraint ---
            try:
                anim_props = tool.Sequence.get_animation_props()
                camera_props = anim_props.camera_orbit
                
                # --- Rotation Constraint ---
                col.separator()
                col.label(text="Rotation Constraint:")
                
                row = col.row(align=True)
                row.prop(camera_props, "use_custom_rotation_target", text="Use Custom Target")
                
                sub_row = col.row(align=True)
                sub_row.enabled = camera_props.use_custom_rotation_target
                sub_row.prop(camera_props, "schedule_display_rotation_target", text="")
                
                # --- Location Constraint ---
                col.separator()
                col.label(text="Location Constraint:")
                
                row = col.row(align=True)
                row.prop(camera_props, "use_custom_location_target", text="Use Custom Target")
                
                sub_row = col.row(align=True)
                sub_row.enabled = camera_props.use_custom_location_target
                sub_row.prop(camera_props, "schedule_display_location_target", text="")
            except Exception:
                pass # Fail silently if props aren't available

            info_row = box.row()
            info_row.label(text="Note: Rotation and Location follow the active camera by default.", icon='INFO')
            layout.separator()

        collection = bpy.data.collections.get("Schedule_Display_Texts")
        if not collection or not collection.objects:
            layout.label(text="No display texts found", icon='INFO')
            return
        
        # Define the desired order
        order = ["Schedule_Name", "Schedule_Date", "Schedule_Week", "Schedule_Day_Counter", "Schedule_Progress"]
        
        # Get objects in the desired order, and any others at the end
        sorted_objects = []
        existing_objects = {obj.name: obj for obj in collection.objects}
        
        for name in order:
            if name in existing_objects:
                sorted_objects.append(existing_objects.pop(name))
        
        # Add any remaining objects (e.g., if new ones are added in the future)
        sorted_objects.extend(existing_objects.values())

        for text_obj in sorted_objects:
            box = layout.box()
            row = box.row(align=True)
            text_type = text_obj.data.get("text_type", "unknown")
            icon_map = {"schedule_name": "TEXT", "date": "TIME","week": "COLLAPSEMENU","day_counter": "SORTTIME","progress": "STATUSBAR"}
            row.label(text=text_type.replace("_", " ").title(), icon=icon_map.get(text_type, "FONT_DATA"))
            row.prop(text_obj, "hide_viewport", text="", icon='HIDE_OFF', emboss=False)
            col = box.column(align=True)
            col.prop(text_obj, "location", text="Position")
            try:
                col.prop(text_obj.data, "size", text="Size")
            except Exception:
                pass
            if text_obj.data.materials:
                mat = text_obj.data.materials[0]
                if getattr(mat, "use_nodes", False) and mat.node_tree:
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        col.prop(bsdf.inputs["Base Color"], "default_value", text="Color")
        row = layout.row(align=True)
        row.operator("bim.arrange_schedule_texts", text="Auto-Arrange", icon="ALIGN_TOP")



class BIM_PT_task_icom(Panel):
    bl_label = "Task ICOM"
    bl_idname = "BIM_PT_task_icom"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_work_schedules"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        props = tool.Sequence.get_work_schedule_props()
        if not props.active_work_schedule_id:
            return False
        tprops = tool.Sequence.get_task_tree_props()
        total_tasks = len(tprops.tasks)
        if total_tasks > 0 and props.active_task_index < total_tasks:
            return True
        return False

    def draw(self, context):
        if not TaskICOMData.is_loaded:
            TaskICOMData.load()

        self.props = tool.Sequence.get_work_schedule_props()
        self.tprops = tool.Sequence.get_task_tree_props()
        task = self.tprops.tasks[self.props.active_task_index]

        grid = self.layout.grid_flow(columns=3, even_columns=True)

        # Column1
        col = grid.column()

        row2 = col.row(align=True)
        total_task_inputs = len(self.props.task_inputs)
        row2.label(text="Inputs ({})".format(total_task_inputs))

        if context.selected_objects:
            op = row2.operator("bim.assign_process", icon="ADD", text="")
            op.task = task.ifc_definition_id
            op.related_object_type = "PRODUCT"
        if total_task_inputs:
            op = row2.operator("bim.unassign_process", icon="REMOVE", text="")
            op.task = task.ifc_definition_id
            op.related_object_type = "PRODUCT"
            if not context.selected_objects and self.props.active_task_input_index < total_task_inputs:
                input_id = self.props.task_inputs[self.props.active_task_input_index].ifc_definition_id
                op.related_object = input_id

        op = row2.operator("bim.select_task_related_inputs", icon="RESTRICT_SELECT_OFF", text="Select")
        op.task = task.ifc_definition_id

        row2 = col.row()
        row2.prop(self.props, "show_nested_inputs", text="Show Nested")
        row2 = col.row()
        row2.template_list("BIM_UL_task_inputs", "", self.props, "task_inputs", self.props, "active_task_input_index")

        # Column2
        col = grid.column()

        row2 = col.row(align=True)
        total_task_resources = len(self.props.task_resources)
        row2.label(text="Resources ({})".format(total_task_resources))
        op = row2.operator("bim.calculate_task_duration", text="", icon="TEMP")
        op.task = task.ifc_definition_id

        if TaskICOMData.data["can_active_resource_be_assigned"]:
            op = row2.operator("bim.assign_process", icon="ADD", text="")
            op.task = task.ifc_definition_id
            op.related_object_type = "RESOURCE"

        if total_task_resources and self.props.active_task_resource_index < total_task_resources:
            op = row2.operator("bim.unassign_process", icon="REMOVE", text="")
            op.task = task.ifc_definition_id
            op.related_object_type = "RESOURCE"
            op.resource = self.props.task_resources[self.props.active_task_resource_index].ifc_definition_id

        row2 = col.row()
        row2.prop(self.props, "show_nested_resources", text="Show Nested")

        row2 = col.row()
        row2.template_list(
            "BIM_UL_task_resources", "", self.props, "task_resources", self.props, "active_task_resource_index"
        )

        # Column3
        col = grid.column()

        row2 = col.row(align=True)
        total_task_outputs = len(self.props.task_outputs)
        row2.label(text="Outputs ({})".format(total_task_outputs))

        if context.selected_objects:
            op = row2.operator("bim.assign_product", icon="ADD", text="")
            op.task = task.ifc_definition_id
        if total_task_outputs:
            op = row2.operator("bim.unassign_product", icon="REMOVE", text="")
            op.task = task.ifc_definition_id
            if (
                total_task_outputs
                and not context.selected_objects
                and self.props.active_task_output_index < total_task_outputs
            ):
                output_id = self.props.task_outputs[self.props.active_task_output_index].ifc_definition_id
                op.relating_product = output_id

        op = row2.operator("bim.select_task_related_products", icon="RESTRICT_SELECT_OFF", text="Select")
        op.task = task.ifc_definition_id
        row2 = col.row()
        row2.prop(self.props, "show_nested_outputs", text="Show Nested")
        row2 = col.row()
        row2.template_list(
            "BIM_UL_task_outputs", "", self.props, "task_outputs", self.props, "active_task_output_index"
        )


class BIM_UL_task_columns(UIList):
    def draw_item(
        self,
        context,
        layout: bpy.types.UILayout,
        data: "BIMWorkScheduleProperties",
        item: "Attribute",
        icon,
        active_data,
        active_propname,
    ):
        props = tool.Sequence.get_work_schedule_props()
        if item:
            row = layout.row(align=True)
            row.prop(item, "name", emboss=False, text="")
            if props.sort_column == item.name:
                row.label(text="", icon="SORTALPHA")
            row.operator("bim.remove_task_column", text="", icon="X").name = item.name


# === INICIO DE CÓDIGO AÑADIDO PARA FILTROS ===



class BIM_UL_task_filters(UIList):
    """Dibuja la lista de reglas de filtro."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        # 'item' es una instancia de TaskFilterRule
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # El tipo de dato ahora se lee directamente de la propiedad de la regla
            data_type = getattr(item, 'data_type', 'string')

            row = layout.row(align=True)

            # Controles comunes (checkbox, columna, operador)
            row.prop(item, "is_active", text="")
            row.prop(item, "column", text="")
            row.prop(item, "operator", text="")

            # El campo de valor solo se habilita si el operador lo requiere
            value_row = row.row(align=True)
            value_row.enabled = item.operator not in {'EMPTY', 'NOT_EMPTY'}

            # Lógica condicional para dibujar el widget de valor correcto
            if data_type == 'integer':
                value_row.prop(item, "value_integer", text="")
            elif data_type in ('float', 'real'):
                value_row.prop(item, "value_float", text="")
            elif data_type == 'boolean':
                value_row.prop(item, "value_boolean", text="")
            elif data_type == 'date':
                # Para fechas, mostramos el texto y un botón que abre el calendario
                # For dates, we show the text and a button that opens the calendar
                value_row.prop(item, "value_string", text="")
                # ✅ CORRECTED CALENDAR BUTTON
                op = value_row.operator("bim.filter_datepicker", text="", icon="OUTLINER_DATA_CAMERA")
                op.rule_index = index  # ✅ ESTO ES CRUCIAL - pasar el índice
            else:  # Por defecto, usar string (para texto, enums, etc.)
                value_row.prop(item, "value_string", text="")


class BIM_UL_saved_filter_sets(UIList):

    """Dibuja la lista de conjuntos de filtros guardados."""
    """Draws the list of saved filter sets."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        # 'item' es una instancia de SavedFilterSet
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=item.name, icon='FILTER')

class BIM_UL_task_inputs(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            row = layout.row(align=True)
            op = row.operator("bim.select_product", text="", icon="RESTRICT_SELECT_OFF")
            op.product = item.ifc_definition_id
            row.prop(item, "name", emboss=False, text="")
            # row.operator("bim.remove_task_column", text="", icon="X").name = item.name


class BIM_UL_task_resources(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            row = layout.row(align=True)
            row.operator("bim.go_to_resource", text="", icon="STYLUS_PRESSURE").resource = item.ifc_definition_id
            row.prop(item, "name", emboss=False, text="")
            row.prop(item, "schedule_usage", emboss=False, text="")


class BIM_UL_animation_colors(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            row = layout.row()
            row.prop(item, "color", text="")
            row.prop(item, "name", text="")


class BIM_UL_task_outputs(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            row = layout.row(align=True)
            op = row.operator("bim.select_product", text="", icon="RESTRICT_SELECT_OFF")
            op.product = item.ifc_definition_id
            row.prop(item, "name", emboss=False, text="")


class BIM_UL_product_input_tasks(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            row = layout.row(align=True)
            op = row.operator("bim.go_to_task", text="", icon="STYLUS_PRESSURE")
            op.task = item.ifc_definition_id
            row.split(factor=0.8)
            row.prop(item, "name", text="")


class BIM_UL_product_output_tasks(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            row = layout.row(align=True)
            op = row.operator("bim.go_to_task", text="", icon="STYLUS_PRESSURE")
            op.task = item.ifc_definition_id
            row.split(factor=0.8)
            row.prop(item, "name", text="")


class BIM_UL_tasks(UIList):
    @classmethod
    def draw_header(cls, layout: bpy.types.UILayout):
        props = tool.Sequence.get_work_schedule_props()
        row = layout.row(align=True)

        # Apply original COPIA alignment system with virtual columns support
        split1 = row.split(factor=0.1)
        # Header "ID" + quick sort-by-ID button (with spacing)
        hdr = split1.row(align=False)  # Changed to False to avoid tight alignment
        hdr.label(text="ID", icon="BLANK1")
        hdr.operator("bim.sort_schedule_by_id_asc", text="", icon="SORTALPHA")
        
        # Calculate split factor accounting for 2 virtual columns (Outputs 3D + Variance)
        # Drastically reduced to compensate for 18+ spaces in virtual columns manual spacing
        split2 = split1.split(factor=0.4 - min(0.2, 0.1 * len(props.columns)))
        split2.label(text="Name", icon="BLANK1")
        
        # Use same split2 for custom columns to ensure perfect alignment
        split3 = cls.draw_custom_columns(props, split2, header=True)
        
        # Virtual columns headers using the returned split from draw_custom_columns
        split3.label(text="  Outputs 3D  ")  # Add manual spacing
        split3.label(text="Variance")


    def draw_item(
        self,
        context,
        layout: bpy.types.UILayout,
        data: "BIMTaskTreeProperties",
        item: "Task",
        icon,
        active_data,
        active_propname,
    ):
        if item:
            self.props = tool.Sequence.get_work_schedule_props()
            task = SequenceData.data["tasks"][item.ifc_definition_id]
            row = layout.row(align=True)
            
            self.draw_hierarchy(row, item)

            # Apply original COPIA alignment system with virtual columns support
            split1 = row.split(factor=0.1)
            split1.prop(item, "identification", emboss=False, text="")
            
            # Use SAME split calculation as header for perfect alignment
            # Drastically reduced to compensate for 18+ spaces in virtual columns manual spacing
            split2 = split1.split(factor=0.4 - min(0.2, 0.1 * len(self.props.columns)))
            # Align Name values to start at beginning of "Name" title - remove icon and add left alignment
            name_row = split2.row(align=False)
            name_row.alignment = 'LEFT'
            name_row.label(text=item.name or "Unnamed")  # No padding, no icon - pure left align

            # Use same split2 for custom columns to ensure perfect alignment
            split3 = BIM_UL_tasks.draw_custom_columns(self.props, split2, item, task)

            # Virtual columns data using the returned split from draw_custom_columns
            split3.label(text=f"                  {item.outputs_count}    ")  # Move back left - better center for 3D Outputs

            # Variance column with status and colored background
            variance_status_text = item.variance_status or ""
            icon = 'BLANK1'
            
            # Status field display based on variance result
            if "Delayed" in variance_status_text:
                icon = 'TIME'
                red_box = split3.box()
                red_box.alert = True
                red_row = red_box.row()
                red_row.scale_y = 0.9
                red_row.label(text=variance_status_text, icon=icon)
                
            elif "Ahead" in variance_status_text:
                # VERDE: Usar box con active = True para verde
                icon = 'TIME'
                green_box = split3.box()
                green_box.active = True
                green_row = green_box.row()
                green_row.scale_y = 0.9
                # Usar una etiqueta para que no sea un botón
                green_row.label(text=variance_status_text, icon=icon)
            elif "On Time" in variance_status_text:
                # AZUL: Usar box con active = False para azul
                icon = 'TIME'
                blue_box = split3.box()
                blue_box.active = False
                blue_box.enabled = True
                blue_row = blue_box.row()
                blue_row.scale_y = 0.9
                # Usar una etiqueta para que no sea un botón
                blue_row.label(text=variance_status_text, icon=icon)
            else:
                # Default
                icon = 'BLANK1'
                split3.label(text=variance_status_text, icon=icon)

            # Add variance color mode checkbox - TODOS FUNCIONALES
            if variance_status_text:
                checkbox_container = row.row(align=True)
                checkbox_container.scale_x = 0.8
                
                # CONDICIONAL según resultado de varianza - TODOS usan prop() real
                if "Delayed" in variance_status_text:
                    # ROJO: alert funciona perfecto
                    checkbox_container.alert = True
                    
                elif "Ahead" in variance_status_text:
                    # VERDE: box con active = True
                    checkbox_box = checkbox_container.box()
                    checkbox_box.active = True
                    checkbox_box.scale_y = 0.9
                    checkbox_container = checkbox_box.row()
                    
                elif "On Time" in variance_status_text:
                    # AZUL: box con active = False
                    checkbox_box = checkbox_container.box() 
                    checkbox_box.active = False
                    checkbox_box.enabled = True
                    checkbox_box.scale_y = 0.9
                    checkbox_container = checkbox_box.row()
                
                # TODOS usan el prop() real para que funcionen
                checkbox_container.prop(
                    item,
                    "is_variance_color_selected",
                    text="",
                    icon="CHECKBOX_HLT" if item.is_variance_color_selected else "CHECKBOX_DEHLT",
                )

            if self.props.active_task_id and self.props.editing_task_type == "ATTRIBUTES":
                row.prop(
                    item,
                    "is_selected",
                    icon="CHECKBOX_HLT" if item.is_selected else "CHECKBOX_DEHLT",
                    text="",
                    emboss=False,
                )
            if self.props.should_show_task_bar_selection:
                row.prop(
                    item,
                    "has_bar_visual",
                    icon="COLLECTION_COLOR_04" if item.has_bar_visual else "OUTLINER_COLLECTION",
                    text="",
                    emboss=False,
                )
            if self.props.enable_reorder:
                self.draw_order_operator(row, item.ifc_definition_id)
            if self.props.editing_task_type == "SEQUENCE" and self.props.highlighted_task_id != item.ifc_definition_id:
                if item.is_predecessor:
                    op = row.operator("bim.unassign_predecessor", text="", icon="BACK", emboss=False)
                else:
                    op = row.operator("bim.assign_predecessor", text="", icon="TRACKING_BACKWARDS", emboss=False)
                op.task = item.ifc_definition_id

                if item.is_successor:
                    op = row.operator("bim.unassign_successor", text="", icon="FORWARD", emboss=False)
                else:
                    op = row.operator("bim.assign_successor", text="", icon="TRACKING_FORWARDS", emboss=False)
                op.task = item.ifc_definition_id

    def draw_order_operator(self, row: bpy.types.UILayout, ifc_definition_id: int) -> None:
        task = SequenceData.data["tasks"][ifc_definition_id]
        if task["NestingIndex"] is not None:
            if task["NestingIndex"] == 0:
                op = row.operator("bim.reorder_task_nesting", icon="TRIA_DOWN", text="")
                op.task = ifc_definition_id
                op.new_index = task["NestingIndex"] + 1
            elif task["NestingIndex"] > 0:
                op = row.operator("bim.reorder_task_nesting", icon="TRIA_UP", text="")
                op.task = ifc_definition_id
                op.new_index = task["NestingIndex"] - 1

    def draw_hierarchy(self, row: bpy.types.UILayout, item: bpy.types.PropertyGroup) -> None:
        for i in range(0, item.level_index):
            row.label(text="", icon="BLANK1")
        if item.has_children:
            if item.is_expanded:
                row.operator("bim.contract_task", text="", emboss=False, icon="DISCLOSURE_TRI_DOWN").task = (
                    item.ifc_definition_id
                )
            else:
                row.operator("bim.expand_task", text="", emboss=False, icon="DISCLOSURE_TRI_RIGHT").task = (
                    item.ifc_definition_id
                )
        else:
            row.label(text="", icon="DOT")

    @classmethod
    def draw_custom_columns(
        cls,
        props: bpy.types.PropertyGroup,
        row: bpy.types.UILayout,
        item: Optional[bpy.types.PropertyGroup] = None,
        task: Optional[dict[str, Any]] = None,
        *,
        header: bool = False,
    ) -> bpy.types.UILayout:
        """Original COPIA alignment system: simple and perfect alignment"""
        if not header:
            assert item and task, "Item and task must be provided when not drawing a header"

        # Apply original COPIA system: simple iteration through all columns
        # This ensures perfect alignment between headers and data
        for column in props.columns:
            column_name = column.name
            
            # --- Generalized handling for all date columns ---
            date_match = re.match(r"IfcTaskTime\.(Schedule|Actual|Early|Late)(Start|Finish)", column_name)
            if date_match:
                date_type = date_match.group(1).lower()
                date_part = date_match.group(2)

                prop_name = f"{date_type.lower()}_{date_part.lower()}"
                if date_type == "schedule":
                    prop_name = date_part.lower()

                derived_prop_name = f"derived_{prop_name}"

                if header:
                    # Show full names: Schedule Start, Actual Start, Late Start, etc.
                    full_name = f"{date_type.title()} {date_part}"
                    # Create sub-split for Schedule columns to reduce spacing
                    if date_type == "schedule":
                        subsplit = row.split(factor=0.6)  # Reduce space for Schedule columns
                        subsplit.label(text=full_name)
                    else:
                        row.label(text=full_name)
                else:
                    derived_value = getattr(item, derived_prop_name, "")
                    if derived_value:
                        # Add manual spacing to move Finish dates right - adjusted only for Schedule columns
                        if date_part == "Finish" and date_type == "schedule":
                            subsplit = row.split(factor=0.6)  # Reduce space for Schedule columns
                            subsplit.label(text=f"     {derived_value}*")  # 5 spaces - Schedule Finish (reduced from 10)
                        elif date_part == "Start" and date_type == "schedule":
                            subsplit = row.split(factor=0.6)  # Reduce space for Schedule columns  
                            subsplit.label(text=f"     {derived_value}*")  # 5 spaces - Schedule Start (corrected from 10)
                        elif date_part == "Finish" and date_type == "actual":
                            row.label(text=f"          {derived_value}*")  # 10 spaces - Actual Finish (original)
                        elif date_part == "Start" and date_type == "actual":
                            row.label(text=f"     {derived_value}*")  # 5 spaces - Actual Start (original)
                        elif date_part == "Finish" and date_type == "early":
                            row.label(text=f"          {derived_value}*")  # 10 spaces - Early Finish (original)
                        elif date_part == "Start" and date_type == "early":
                            row.label(text=f"     {derived_value}*")  # 5 spaces - Early Start (original)
                        elif date_part == "Finish" and date_type == "late":
                            row.label(text=f"          {derived_value}*")  # 10 spaces - Late Finish (original)
                        elif date_part == "Start" and date_type == "late":
                            row.label(text=f"     {derived_value}*")  # 5 spaces - Late Start (original)
                        else:
                            row.label(text=derived_value + "*")
                    else:
                        # Apply same alignment logic when there's no derived_value
                        if date_part in ["Finish", "Start"] and date_type in ["schedule", "actual", "early", "late"]:
                            # Get the actual value and apply the same spacing as derived_value
                            actual_value = getattr(item, prop_name, "")
                            if actual_value:
                                if date_type == "schedule":
                                    subsplit = row.split(factor=0.6)  # Reduce space for Schedule columns
                                    if date_part == "Start":
                                        subsplit.label(text=f"     {actual_value}")  # 5 spaces - Schedule Start
                                    else:  # Finish
                                        subsplit.label(text=f"     {actual_value}")  # 5 spaces - Schedule Finish
                                else:
                                    if date_part == "Start":
                                        row.label(text=f"     {actual_value}")  # 5 spaces - Other Start columns (original)
                                    else:  # Finish
                                        row.label(text=f"          {actual_value}")  # 10 spaces - Other Finish columns (original)
                            else:
                                row.prop(item, prop_name, emboss=False, text="")
                        else:
                            row.prop(item, prop_name, emboss=False, text="")
                continue

            if column_name == "IfcTaskTime.ScheduleDuration":
                if header:
                    row.label(text="Duration")
                else:
                    if item.derived_duration:
                        row.label(text=f"     {item.derived_duration}*")  # 5 spaces - Duration
                    else:
                        # Apply same 15-space alignment for editable fields
                        duration_value = getattr(item, "duration", "")
                        if duration_value:
                            row.label(text=f"       {duration_value}")  # 10 spaces - Duration
                        else:
                            row.prop(item, "duration", emboss=False, text="")
            elif column_name == "Controls.Calendar":
                if header:
                    row.label(text="Calendar")
                else:
                    if item.derived_calendar:
                        row.label(text=f"               {item.derived_calendar}*")  # 15 spaces - Calendar
                    else:
                        calendar_value = item.calendar or "-"
                        row.label(text=f"               {calendar_value}")  # 15 spaces - Calendar
            else:
                ifc_class, name = column_name.split(".")
                if header:
                    row.label(text=name)
                else:
                    if ifc_class == "IfcTask":
                        value = task[name]
                    elif ifc_class == "IfcTaskTime":
                        if (task_time_id := task["TaskTime"]) is None:
                            value = None
                        else:
                            value = SequenceData.data["task_times"][task_time_id][name]
                    else:
                        assert False, f"Unexpected ifc_class '{ifc_class}'."
                    if value is None:
                        row.label(text=f"               -")  # 15 spaces - NULL value
                    else:
                        row.label(text=f"               {str(value)}")  # 15 spaces - All other columns
        
        # Return the row for virtual columns to use
        return row


class BIM_PT_variance_analysis(Panel):
    bl_label = "Variance Analysis"
    bl_idname = "BIM_PT_variance_analysis"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_tab_sequence"

    @classmethod
    def poll(cls, context):
        props = tool.Sequence.get_work_schedule_props()
        # Only show if a schedule is being edited for tasks
        return props.active_work_schedule_id and props.editing_type == "TASKS"

    def draw(self, context):
        layout = self.layout
        props = tool.Sequence.get_work_schedule_props()

        row = layout.row(align=True)
        row.prop(props, "variance_source_a", text="Compare")
        row.prop(props, "variance_source_b", text="With")
        row.operator("bim.calculate_schedule_variance", text="Calculate", icon="PLAY")
        row.operator("bim.clear_schedule_variance", text="", icon="TRASH")
        
        # Variance color mode controls
        is_variance_active = context.scene.get('BIM_VarianceColorModeActive', False)
        if is_variance_active:
            col = layout.column(align=True)
            col.separator()
            variance_row = col.row(align=True)
            variance_row.label(text="Variance Mode Active", icon="RESTRICT_COLOR_OFF")
            variance_row.operator("bim.deactivate_variance_color_mode", text="Deactivate", icon="CANCEL")


class BIM_PT_work_calendars(Panel):
    bl_label = "Work Calendars"
    bl_idname = "BIM_PT_work_calendars"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_tab_sequence"

    @classmethod
    def poll(cls, context):
        file = tool.Ifc.get()
        return file and hasattr(file, "schema") and file.schema != "IFC2X3"

    layout: bpy.types.UILayout

    def draw(self, context):
        if not SequenceData.is_loaded:
            SequenceData.load()

        self.props = tool.Sequence.get_work_calendar_props()
        row = self.layout.row()
        if SequenceData.data["has_work_calendars"]:
            row.label(
                text="{} Work Calendars Found".format(SequenceData.data["number_of_work_calendars_loaded"]),
                icon="TEXT",
            )
        else:
            row.label(text="No Work Calendars found.", icon="TEXT")
        row.operator("bim.add_work_calendar", icon="ADD", text="")
        for work_calendar_id, work_calendar in SequenceData.data["work_calendars"].items():
            self.draw_work_calendar_ui(work_calendar_id, work_calendar)

    def draw_work_calendar_ui(self, work_calendar_id, work_calendar):
        row = self.layout.row(align=True)
        row.label(text=work_calendar["Name"] or "Unnamed", icon="VIEW_ORTHO")
        if self.props.active_work_calendar_id == work_calendar_id:
            if self.props.editing_type == "ATTRIBUTES":
                row.operator("bim.edit_work_calendar", icon="CHECKMARK")
            row.operator("bim.disable_editing_work_calendar", text="", icon="CANCEL")
        elif self.props.active_work_calendar_id:
            row.operator("bim.remove_work_calendar", text="", icon="X").work_calendar = work_calendar_id
        else:
            op = row.operator("bim.enable_editing_work_calendar_times", text="", icon="MESH_GRID")
            op.work_calendar = work_calendar_id
            op = row.operator("bim.enable_editing_work_calendar", text="", icon="GREASEPENCIL")
            op.work_calendar = work_calendar_id
            row.operator("bim.remove_work_calendar", text="", icon="X").work_calendar = work_calendar_id

        if self.props.active_work_calendar_id == work_calendar_id:
            if self.props.editing_type == "ATTRIBUTES":
                self.draw_editable_ui()
            elif self.props.editing_type == "WORKTIMES":
                self.draw_work_times_ui(work_calendar_id, work_calendar)

    def draw_work_times_ui(self, work_calendar_id, work_calendar):
        row = self.layout.row(align=True)
        op = row.operator("bim.add_work_time", text="Add Work Time", icon="ADD")
        op.work_calendar = work_calendar_id
        op.time_type = "WorkingTimes"
        op = row.operator("bim.add_work_time", text="Add Exception Time", icon="ADD")
        op.work_calendar = work_calendar_id
        op.time_type = "ExceptionTimes"

        for work_time_id in work_calendar["WorkingTimes"]:
            self.draw_work_time_ui(SequenceData.data["work_times"][work_time_id], time_type="WorkingTimes")

        for work_time_id in work_calendar["ExceptionTimes"]:
            self.draw_work_time_ui(SequenceData.data["work_times"][work_time_id], time_type="ExceptionTimes")

    def draw_work_time_ui(self, work_time, time_type):
        row = self.layout.row(align=True)
        row.label(text=work_time["Name"] or "Unnamed", icon="AUTO" if time_type == "WorkingTimes" else "HOME")
        if work_time["Start"] or work_time["Finish"]:
            row.label(text="{} - {}".format(work_time["Start"] or "*", work_time["Finish"] or "*"))
        if self.props.active_work_time_id == work_time["id"]:
            row.operator("bim.edit_work_time", text="", icon="CHECKMARK")
            row.operator("bim.disable_editing_work_time", text="Cancel", icon="CANCEL")
        elif self.props.active_work_time_id:
            op = row.operator("bim.remove_work_time", text="", icon="X")
            op.work_time = work_time["id"]
        else:
            op = row.operator("bim.enable_editing_work_time", text="", icon="GREASEPENCIL")
            op.work_time = work_time["id"]
            op = row.operator("bim.remove_work_time", text="", icon="X")
            op.work_time = work_time["id"]

        if self.props.active_work_time_id == work_time["id"]:
            self.draw_editable_work_time_ui(work_time)

    def draw_editable_work_time_ui(self, work_time: dict[str, Any]) -> None:
        draw_attributes(self.props.work_time_attributes, self.layout)
        if work_time["RecurrencePattern"]:
            self.draw_editable_recurrence_pattern_ui(
                SequenceData.data["recurrence_patterns"][work_time["RecurrencePattern"]]
            )
        else:
            row = self.layout.row(align=True)
            row.prop(self.props, "recurrence_types", icon="RECOVER_LAST", text="")
            op = row.operator("bim.assign_recurrence_pattern", icon="ADD", text="")
            op.work_time = work_time["id"]
            op.recurrence_type = self.props.recurrence_types

    def draw_editable_recurrence_pattern_ui(self, recurrence_pattern):
        box = self.layout.box()
        row = box.row(align=True)
        row.label(text=recurrence_pattern["RecurrenceType"], icon="RECOVER_LAST")
        op = row.operator("bim.unassign_recurrence_pattern", text="", icon="X")
        op.recurrence_pattern = recurrence_pattern["id"]

        row = box.row(align=True)
        row.prop(self.props, "start_time", text="")
        row.prop(self.props, "end_time", text="")
        op = row.operator("bim.add_time_period", text="", icon="ADD")
        op.recurrence_pattern = recurrence_pattern["id"]

        for time_period_id in recurrence_pattern["TimePeriods"]:
            time_period = SequenceData.data["time_periods"][time_period_id]
            row = box.row(align=True)
            row.label(text="{} - {}".format(time_period["StartTime"], time_period["EndTime"]), icon="TIME")
            op = row.operator("bim.remove_time_period", text="", icon="X")
            op.time_period = time_period_id

        applicable_data = {
            "DAILY": ["Interval", "Occurrences"],
            "WEEKLY": ["WeekdayComponent", "Interval", "Occurrences"],
            "MONTHLY_BY_DAY_OF_MONTH": ["DayComponent", "Interval", "Occurrences"],
            "MONTHLY_BY_POSITION": ["WeekdayComponent", "Position", "Interval", "Occurrences"],
            "BY_DAY_COUNT": ["Interval", "Occurrences"],
            "BY_WEEKDAY_COUNT": ["WeekdayComponent", "Interval", "Occurrences"],
            "YEARLY_BY_DAY_OF_MONTH": ["DayComponent", "MonthComponent", "Interval", "Occurrences"],
            "YEARLY_BY_POSITION": ["WeekdayComponent", "MonthComponent", "Position", "Interval", "Occurrences"],
        }

        if "Position" in applicable_data[recurrence_pattern["RecurrenceType"]]:
            row = box.row()
            row.prop(self.props, "position")

        if "DayComponent" in applicable_data[recurrence_pattern["RecurrenceType"]]:
            for i, component in enumerate(self.props.day_components):
                if i % 7 == 0:
                    row = box.row(align=True)
                row.prop(component, "is_specified", text=component.name)

        if "WeekdayComponent" in applicable_data[recurrence_pattern["RecurrenceType"]]:
            row = box.row(align=True)
            for component in self.props.weekday_components:
                row.prop(component, "is_specified", text=component.name)

        if "MonthComponent" in applicable_data[recurrence_pattern["RecurrenceType"]]:
            for i, component in enumerate(self.props.month_components):
                if i % 4 == 0:
                    row = box.row(align=True)
                row.prop(component, "is_specified", text=component.name)

        row = box.row()
        row.prop(self.props, "interval")
        row = box.row()
        row.prop(self.props, "occurrences")

    def draw_editable_ui(self):
        draw_attributes(self.props.work_calendar_attributes, self.layout)


class BIM_PT_4D_Tools(Panel):
    bl_label = "4D Tools"
    bl_idname = "BIM_PT_4D_Tools"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_tab_sequence"
    bl_order = 5
    def draw(self, context):
        self.props = tool.Sequence.get_work_schedule_props()

        # --- Active Work Schedule Info ---
        row = self.layout.row()
        try:
            if self.props.active_work_schedule_id:
                file = tool.Ifc.get()
                if file:
                    ws = file.by_id(self.props.active_work_schedule_id)
                    if ws:
                        row.label(text=f"Active Schedule: {getattr(ws, 'Name', None) or 'Unnamed'}", icon="TIME")
                    else:
                        row.label(text="No valid schedule selected", icon="ERROR")
                else:
                    row.label(text="No IFC file loaded", icon="ERROR")
            else:
                row.label(text="No schedule selected", icon="INFO")
        except Exception:
            row.label(text="No valid schedule selected", icon="ERROR")

        # --- Actions ---
        row = self.layout.row()
        row.operator("bim.load_product_related_tasks", text="Load Tasks", icon="FILE_REFRESH")
        row.prop(self.props, "filter_by_active_schedule", text="Filter by Active Schedule")

        # --- Lists ---
        grid = self.layout.grid_flow(columns=2, even_columns=True)
        col1 = grid.column()
        col1.label(text="Product Input Tasks")
        col1.template_list(
            "BIM_UL_product_input_tasks",
            "",
            self.props,
            "product_input_tasks",
            self.props,
            "active_product_input_task_index",
        )

        col2 = grid.column()
        col2.label(text="Product Output Tasks")
        col2.template_list(
            "BIM_UL_product_output_tasks",
            "",
            self.props,
            "product_output_tasks",
            self.props,
            "active_product_output_task_index",
        )


class BIM_PT_animation_color_schemes(Panel):
    bl_label = "Animation Color Scheme"
    bl_idname = "BIM_PT_animation_color_scheme"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_tab_sequence"

    bl_order = 4
    @classmethod
    def poll(cls, context):
        file = tool.Ifc.get()
        return file and hasattr(file, "schema") and file.schema != "IFC2X3"

    def draw(self, context):
        layout = self.layout
        props = tool.Sequence.get_animation_props()
        row = layout.row()
        row.template_list(
            "UI_UL_list", "animation_color_schemes_list",
            props, "ColorTypes",
            props, "active_ColorType_index"
        )

        col = row.column(align=True)
        col.operator("bim.add_animation_color_schemes", icon='ADD', text="")
        col.operator("bim.remove_animation_color_schemes", icon='REMOVE', text="")
        col.separator()  # Add visual separator
        col.operator("bim.load_animation_color_schemes_set_internal", icon='FILE_TICK', text="")

        if props.ColorTypes and props.active_ColorType_index < len(props.ColorTypes):
            p = props.ColorTypes[props.active_ColorType_index]
            # --- Saved Sets (Internal) ---
            box = layout.box()
            row = box.row(align=True)
            row.operator("bim.save_animation_color_schemes_set_internal", icon='ADD', text="Save Set")
            row.operator("bim.update_active_colortype_group", icon='FILE_REFRESH', text="Update Group")
            row.operator("bim.cleanup_task_colortype_mappings", icon='BRUSH_DATA', text="Clean")
            # REMOVED: Load Set (now it's above next to the - button)
            row.operator("bim.remove_animation_color_schemes_set_internal", icon='TRASH', text="Remove Set")
            row.operator("bim.import_animation_color_schemes_set_from_file", icon='IMPORT', text="")
            row.operator("bim.export_animation_color_schemes_set_to_file", icon='EXPORT', text="")
            box = layout.box()
            box.prop(p, "name")

            # === States to consider with improved documentation ===
            row = layout.row(align=True)
            row.label(text="States to consider:")

            # IMPROVEMENT: Add explanatory tooltips
            start_row = row.row(align=True)
            start_row.prop(p, "consider_start", text="Start", toggle=True)
            if p.consider_start:
                start_row.label(text="", icon='INFO')

            row.prop(p, "consider_active", text="Active", toggle=True)
            row.prop(p, "consider_end", text="End", toggle=True)

            # NEW: Information about consider_start
            if p.consider_start:
                info_box = layout.box()
                info_box.label(text="ℹ️  Start Mode: Elements will maintain start appearance", icon='INFO')
                info_box.label(text="   throughout the entire animation, ignoring task dates.")
                info_box.label(text="   Useful for: existing elements, demolition context.")

            # --- Start Appearance ---
            start_box = layout.box()
            header = start_box.row(align=True)
            header.label(text="Start Appearance", icon='PLAY')
            col = start_box.column()
            col.enabled = bool(getattr(p, "consider_start", True))
            row = col.row(align=True)
            row.prop(p, "use_start_original_color")
            if not p.use_start_original_color:
                col.prop(p, "start_color")
            col.prop(p, "start_transparency")

            # --- Active / In Progress Appearance ---
            active_box = layout.box()
            header = active_box.row(align=True)
            header.label(text="Active Appearance", icon='SEQUENCE')
            col = active_box.column()
            col.enabled = bool(getattr(p, "consider_active", True))
            row = col.row(align=True)
            row.prop(p, "use_active_original_color")
            if not p.use_active_original_color:
                if hasattr(p, "in_progress_color"):
                    col.prop(p, "in_progress_color")
                elif hasattr(p, "active_color"):
                    col.prop(p, "active_color")
            col.prop(p, "active_start_transparency")
            col.prop(p, "active_finish_transparency")
            col.prop(p, "active_transparency_interpol")

            # --- End Appearance ---
            end_box = layout.box()
            header = end_box.row(align=True)
            header.label(text="End Appearance", icon='FF')
            col = end_box.column()
            col.enabled = bool(getattr(p, "consider_end", True))

            # <-- START OF MODIFICATION -->
            # Add the new switch to hide at the end
            col.prop(p, "hide_at_end")

            # Disable the following options if "Hide When Finished" is enabled
            row_original = col.row(align=True)
            row_original.enabled = not p.hide_at_end
            row_original.prop(p, "use_end_original_color")

            if not p.use_end_original_color:
                row_color = col.row(align=True)
                row_color.enabled = not p.hide_at_end
                row_color.prop(p, "end_color")

            row_transparency = col.row(align=True)
            row_transparency.enabled = not p.hide_at_end
            row_transparency.prop(p, "end_transparency")
            # <-- END OF MODIFICATION -->
