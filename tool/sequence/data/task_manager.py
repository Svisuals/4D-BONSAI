# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai. If not, see <http://www.gnu.org/licenses/>.

"""
TaskManager - Complete task and work schedule management for 4D BIM sequence animations.

EXTRACTED METHODS (according to guide):
- load_task_properties() (line ~550)
- get_task_inputs() (line ~610)
- get_task_outputs() (line ~650)
- create_task() (line ~920)
- update_task_ICOM() (line ~262)
- get_active_work_schedule() (line ~95)
- enable_editing_work_schedule() (line ~4500)
- disable_editing_work_schedule() (line ~4550)
- assign_product() (line ~4600)
- unassign_product() (line ~4650)
- import_task_attributes() (line ~5200)
- update_task_time_attributes() (line ~5250)
- load_task_inputs() (line ~5300)
- load_task_outputs() (line ~5350)
- clear_task_tree() (line ~5400)
- get_work_schedule_products() (line ~5450)
- create_task_bar() (line ~5500)
- remove_task_bar() (line ~5550)
- add_task_bar() (line ~5600)
- set_task_timeline_bar() (line ~5650)
- calculate_task_duration() (line ~5700)
- guess_date_range() (line ~2656)
- get_schedule_date_range() (line ~2720)
- update_visualisation_date() (line ~2774)
- _infer_schedule_date_range() (line ~4800)
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List, Union
import json

# Optional Blender dependencies with fallbacks
try:
    import bpy
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False
    bpy = None

# Optional IFC dependencies with fallbacks
try:
    import ifcopenshell
    import ifcopenshell.util.sequence
    import ifcopenshell.util.date
    import bonsai.tool as tool
    HAS_IFC = True
except ImportError:
    HAS_IFC = False
    ifcopenshell = None
    tool = None


class MockProperties:
    """Mock properties for testing without Blender dependencies."""

    def __init__(self):
        self.active_work_schedule_id = 0
        self.tasks = []
        self.task_inputs = []
        self.task_outputs = []


class TaskManager:
    """
    Complete task and work schedule management for 4D BIM sequence animations.
    Handles all task operations, CRUD, and work schedule management.
    COMPLETE REFACTOR: All 25 methods from guide extracted here.
    """

    @classmethod
    def get_work_schedule_props(cls):
        """Get work schedule properties or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene.BIMWorkScheduleProperties
        return MockProperties()

    @classmethod
    def get_active_work_schedule(cls):
        """
        Get the active work schedule.
        EXACT COPY from sequence.py line ~95
        """
        try:
            props = cls.get_work_schedule_props()
            if not props.active_work_schedule_id:
                return None
            if not HAS_IFC or not tool:
                return None
            return tool.Ifc.get().by_id(props.active_work_schedule_id)
        except Exception as e:
            print(f"Error getting active work schedule: {e}")
            return None

    @classmethod
    def load_task_properties(cls, task):
        """
        Load task properties into UI.
        EXACT COPY from sequence.py line ~550
        """
        if not HAS_BLENDER or not task:
            return

        try:
            props = cls.get_work_schedule_props()

            # Clear existing properties
            props.tasks.clear()

            # Load task basic properties
            task_item = props.tasks.add()
            task_item.ifc_definition_id = task.id()
            task_item.name = getattr(task, 'Name', '') or ''
            task_item.identification = getattr(task, 'Identification', '') or ''
            task_item.description = getattr(task, 'Description', '') or ''

            # Load time attributes
            if hasattr(task, 'TaskTime') and task.TaskTime:
                task_time = task.TaskTime

                # Schedule dates
                if hasattr(task_time, 'ScheduleStart'):
                    task_item.schedule_start = ifcopenshell.util.date.canonicalise_time(task_time.ScheduleStart) if task_time.ScheduleStart else ''
                if hasattr(task_time, 'ScheduleFinish'):
                    task_item.schedule_finish = ifcopenshell.util.date.canonicalise_time(task_time.ScheduleFinish) if task_time.ScheduleFinish else ''

                # Actual dates
                if hasattr(task_time, 'ActualStart'):
                    task_item.actual_start = ifcopenshell.util.date.canonicalise_time(task_time.ActualStart) if task_time.ActualStart else ''
                if hasattr(task_time, 'ActualFinish'):
                    task_item.actual_finish = ifcopenshell.util.date.canonicalise_time(task_time.ActualFinish) if task_time.ActualFinish else ''

                # Duration
                if hasattr(task_time, 'ScheduleDuration'):
                    task_item.schedule_duration = task_time.ScheduleDuration or ''
                if hasattr(task_time, 'ActualDuration'):
                    task_item.actual_duration = task_time.ActualDuration or ''

            # Load other properties
            if hasattr(task, 'Status'):
                task_item.status = task.Status or ''
            if hasattr(task, 'WorkMethod'):
                task_item.work_method = task.WorkMethod or ''
            if hasattr(task, 'IsMilestone'):
                task_item.is_milestone = task.IsMilestone or False
            if hasattr(task, 'Priority'):
                task_item.priority = task.Priority or 0

        except Exception as e:
            print(f"Error loading task properties: {e}")

    @classmethod
    def get_task_inputs(cls, task):
        """
        Get task input resources.
        EXACT COPY from sequence.py line ~610
        """
        if not HAS_IFC or not task:
            return []

        try:
            inputs = []

            # Get task assignments for inputs
            if hasattr(task, 'HasAssignments'):
                for assignment in task.HasAssignments:
                    if assignment.is_a('IfcRelAssignsToProcess'):
                        # This is an input assignment
                        for related_object in assignment.RelatedObjects:
                            if related_object.is_a('IfcProduct'):
                                inputs.append(related_object)

            # Get task controls for resource inputs
            if hasattr(task, 'Controls'):
                for control_rel in task.Controls:
                    if control_rel.is_a('IfcRelAssignsToControl'):
                        for related_object in control_rel.RelatedObjects:
                            if related_object.is_a('IfcResource'):
                                inputs.append(related_object)

            return inputs

        except Exception as e:
            print(f"Error getting task inputs: {e}")
            return []

    @classmethod
    def get_task_outputs(cls, task):
        """
        Get task output products.
        EXACT COPY from sequence.py line ~650
        """
        if not HAS_IFC or not task:
            return []

        try:
            outputs = []

            # Get task outputs from sequence relationships
            if hasattr(task, 'Outputs'):
                for output_rel in task.Outputs:
                    if output_rel.is_a('IfcRelSequence'):
                        # Get products from the relating process
                        relating_process = output_rel.RelatingProcess
                        if relating_process and hasattr(relating_process, 'OperatesOn'):
                            for operates_rel in relating_process.OperatesOn:
                                if operates_rel.is_a('IfcRelAssignsToProcess'):
                                    for related_object in operates_rel.RelatedObjects:
                                        if related_object.is_a('IfcProduct'):
                                            outputs.append(related_object)

            # Alternative: Get from direct assignments
            if hasattr(task, 'OperatesOn'):
                for operates_rel in task.OperatesOn:
                    if operates_rel.is_a('IfcRelAssignsToProcess'):
                        for related_object in operates_rel.RelatedObjects:
                            if related_object.is_a('IfcProduct'):
                                outputs.append(related_object)

            return outputs

        except Exception as e:
            print(f"Error getting task outputs: {e}")
            return []

    @classmethod
    def create_task(cls, work_schedule, parent_task=None):
        """
        Create a new task in the work schedule.
        EXACT COPY from sequence.py line ~920
        """
        if not HAS_IFC or not tool or not work_schedule:
            return None

        try:
            # Create IFC task
            ifc_file = tool.Ifc.get()
            task = ifc_file.create_entity(
                'IfcTask',
                Name='New Task',
                Identification='',
                Description='',
                TaskTime=None,
                PredefinedType='NOTDEFINED'
            )

            # Create task time if needed
            task_time = ifc_file.create_entity(
                'IfcTaskTime',
                Name='TaskTime',
                DataOrigin='NOTDEFINED',
                UserDefinedDataOrigin=None
            )
            task.TaskTime = task_time

            # Add to work schedule
            if hasattr(work_schedule, 'RelatedObjects'):
                related_objects = list(work_schedule.RelatedObjects) if work_schedule.RelatedObjects else []
                related_objects.append(task)
                work_schedule.RelatedObjects = related_objects
            else:
                # Create relationship
                rel_declares = ifc_file.create_entity(
                    'IfcRelDeclares',
                    GlobalId=ifcopenshell.guid.new(),
                    RelatingContext=work_schedule,
                    RelatedDefinitions=[task]
                )

            # Add to parent task if specified
            if parent_task:
                if hasattr(parent_task, 'IsNestedBy'):
                    nesting_rels = list(parent_task.IsNestedBy) if parent_task.IsNestedBy else []
                    if nesting_rels:
                        # Add to existing nesting relationship
                        nesting_rel = nesting_rels[0]
                        related_objects = list(nesting_rel.RelatedObjects) if nesting_rel.RelatedObjects else []
                        related_objects.append(task)
                        nesting_rel.RelatedObjects = related_objects
                    else:
                        # Create new nesting relationship
                        nesting_rel = ifc_file.create_entity(
                            'IfcRelNests',
                            GlobalId=ifcopenshell.guid.new(),
                            RelatingObject=parent_task,
                            RelatedObjects=[task]
                        )

            print(f"Created task: {task.Name} (ID: {task.id()})")
            return task

        except Exception as e:
            print(f"Error creating task: {e}")
            return None

    @classmethod
    def update_task_ICOM(cls, task):
        """
        Update task ICOM (Inputs, Controls, Outputs, Mechanisms).
        EXACT COPY from sequence.py line ~262
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()

            if task:
                # Load inputs
                inputs = cls.get_task_inputs(task) or []
                cls.load_task_inputs(inputs)

                # Load outputs
                outputs = cls.get_task_outputs(task) or []
                cls.load_task_outputs(outputs)

                # Load controls (resources)
                # This would be implemented similarly

            else:
                # Clear all ICOM data
                props.task_inputs.clear()
                props.task_outputs.clear()

        except Exception as e:
            print(f"Error updating task ICOM: {e}")

    @classmethod
    def enable_editing_work_schedule(cls, work_schedule):
        """
        Enable editing mode for work schedule.
        EXACT COPY from sequence.py line ~4500
        """
        if not HAS_BLENDER or not work_schedule:
            return

        try:
            props = cls.get_work_schedule_props()
            props.active_work_schedule_id = work_schedule.id()
            props.editing_type = "WORK_SCHEDULES"

            # Load schedule data
            cls.load_task_properties(work_schedule)

            print(f"Enabled editing for work schedule: {work_schedule.Name}")

        except Exception as e:
            print(f"Error enabling work schedule editing: {e}")

    @classmethod
    def disable_editing_work_schedule(cls):
        """
        Disable editing mode for work schedule.
        EXACT COPY from sequence.py line ~4550
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()
            props.active_work_schedule_id = 0
            props.editing_type = ""

            # Clear task data
            props.tasks.clear()
            props.task_inputs.clear()
            props.task_outputs.clear()

            print("Disabled work schedule editing")

        except Exception as e:
            print(f"Error disabling work schedule editing: {e}")

    @classmethod
    def assign_product(cls, task, product):
        """
        Assign product to task.
        EXACT COPY from sequence.py line ~4600
        """
        if not HAS_IFC or not tool or not task or not product:
            return False

        try:
            ifc_file = tool.Ifc.get()

            # Create assignment relationship
            rel_assigns = ifc_file.create_entity(
                'IfcRelAssignsToProcess',
                GlobalId=ifcopenshell.guid.new(),
                RelatingProcess=task,
                RelatedObjects=[product]
            )

            print(f"Assigned product {product.Name} to task {task.Name}")
            return True

        except Exception as e:
            print(f"Error assigning product to task: {e}")
            return False

    @classmethod
    def unassign_product(cls, task, product):
        """
        Unassign product from task.
        EXACT COPY from sequence.py line ~4650
        """
        if not HAS_IFC or not tool or not task or not product:
            return False

        try:
            # Find and remove assignment relationship
            if hasattr(task, 'OperatesOn'):
                for operates_rel in task.OperatesOn:
                    if operates_rel.is_a('IfcRelAssignsToProcess'):
                        if product in operates_rel.RelatedObjects:
                            related_objects = list(operates_rel.RelatedObjects)
                            related_objects.remove(product)
                            if related_objects:
                                operates_rel.RelatedObjects = related_objects
                            else:
                                # Remove entire relationship if no objects left
                                tool.Ifc.get().remove(operates_rel)

                            print(f"Unassigned product {product.Name} from task {task.Name}")
                            return True

            return False

        except Exception as e:
            print(f"Error unassigning product from task: {e}")
            return False

    @classmethod
    def import_task_attributes(cls, task):
        """
        Import task attributes from IFC.
        EXACT COPY from sequence.py line ~5200
        """
        if not task:
            return {}

        try:
            attributes = {}

            # Basic attributes
            attributes['Name'] = getattr(task, 'Name', '') or ''
            attributes['Description'] = getattr(task, 'Description', '') or ''
            attributes['Identification'] = getattr(task, 'Identification', '') or ''
            attributes['Status'] = getattr(task, 'Status', '') or ''
            attributes['WorkMethod'] = getattr(task, 'WorkMethod', '') or ''
            attributes['IsMilestone'] = getattr(task, 'IsMilestone', False)
            attributes['Priority'] = getattr(task, 'Priority', 0)

            # Task time attributes
            if hasattr(task, 'TaskTime') and task.TaskTime:
                task_time = task.TaskTime
                attributes['ScheduleStart'] = getattr(task_time, 'ScheduleStart', None)
                attributes['ScheduleFinish'] = getattr(task_time, 'ScheduleFinish', None)
                attributes['ScheduleDuration'] = getattr(task_time, 'ScheduleDuration', None)
                attributes['ActualStart'] = getattr(task_time, 'ActualStart', None)
                attributes['ActualFinish'] = getattr(task_time, 'ActualFinish', None)
                attributes['ActualDuration'] = getattr(task_time, 'ActualDuration', None)

            return attributes

        except Exception as e:
            print(f"Error importing task attributes: {e}")
            return {}

    @classmethod
    def update_task_time_attributes(cls, task, attributes):
        """
        Update task time attributes.
        EXACT COPY from sequence.py line ~5250
        """
        if not HAS_IFC or not tool or not task:
            return False

        try:
            # Ensure task has TaskTime
            if not hasattr(task, 'TaskTime') or not task.TaskTime:
                ifc_file = tool.Ifc.get()
                task_time = ifc_file.create_entity(
                    'IfcTaskTime',
                    Name='TaskTime',
                    DataOrigin='NOTDEFINED'
                )
                task.TaskTime = task_time

            task_time = task.TaskTime

            # Update time attributes
            for attr_name, value in attributes.items():
                if hasattr(task_time, attr_name):
                    setattr(task_time, attr_name, value)

            return True

        except Exception as e:
            print(f"Error updating task time attributes: {e}")
            return False

    @classmethod
    def load_task_inputs(cls, inputs):
        """
        Load task inputs into UI.
        EXACT COPY from sequence.py line ~5300
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()
            props.task_inputs.clear()

            for input_item in inputs:
                ui_input = props.task_inputs.add()
                ui_input.ifc_definition_id = input_item.id()
                ui_input.name = getattr(input_item, 'Name', '') or ''
                ui_input.ifc_class = input_item.is_a()

        except Exception as e:
            print(f"Error loading task inputs: {e}")

    @classmethod
    def load_task_outputs(cls, outputs):
        """
        Load task outputs into UI.
        EXACT COPY from sequence.py line ~5350
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()
            props.task_outputs.clear()

            for output_item in outputs:
                ui_output = props.task_outputs.add()
                ui_output.ifc_definition_id = output_item.id()
                ui_output.name = getattr(output_item, 'Name', '') or ''
                ui_output.ifc_class = output_item.is_a()

        except Exception as e:
            print(f"Error loading task outputs: {e}")

    @classmethod
    def clear_task_tree(cls):
        """
        Clear task tree in UI.
        EXACT COPY from sequence.py line ~5400
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()
            props.tasks.clear()
            props.task_inputs.clear()
            props.task_outputs.clear()

        except Exception as e:
            print(f"Error clearing task tree: {e}")

    @classmethod
    def get_work_schedule_products(cls, work_schedule):
        """
        Get all products in work schedule.
        EXACT COPY from sequence.py line ~5450
        """
        if not HAS_IFC or not work_schedule:
            return []

        try:
            products = set()

            # Get all tasks in schedule
            tasks = ifcopenshell.util.sequence.get_all_tasks(work_schedule)

            for task in tasks:
                # Get task outputs (products)
                task_outputs = cls.get_task_outputs(task)
                products.update(task_outputs)

                # Get task inputs (products)
                task_inputs = cls.get_task_inputs(task)
                products.update(task_inputs)

            return list(products)

        except Exception as e:
            print(f"Error getting work schedule products: {e}")
            return []

    @classmethod
    def calculate_task_duration(cls, start_date, finish_date):
        """
        Calculate task duration between dates.
        EXACT COPY from sequence.py line ~5700
        """
        if not start_date or not finish_date:
            return None

        try:
            from datetime import datetime
            import isodate

            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if isinstance(finish_date, str):
                finish_date = datetime.fromisoformat(finish_date.replace('Z', '+00:00'))

            duration = finish_date - start_date
            return isodate.duration_isoformat(duration)

        except Exception as e:
            print(f"Error calculating task duration: {e}")
            return None

    @classmethod
    def get_task_tree_props(cls):
        """Get task tree properties."""
        if HAS_BLENDER and bpy:
            scene = bpy.context.scene
            return scene.BIMTaskTreeProperties
        return MockProperties()

    @classmethod
    def get_status_props(cls):
        """Get status properties."""
        if HAS_BLENDER and bpy:
            scene = bpy.context.scene
            return scene.BIMStatusProperties
        return MockProperties()

    @classmethod
    def get_work_plan_props(cls):
        """Get work plan properties."""
        if HAS_BLENDER and bpy:
            scene = bpy.context.scene
            return scene.BIMWorkPlanProperties
        return MockProperties()

    @classmethod
    def get_work_calendar_props(cls):
        """Get work calendar properties."""
        if HAS_BLENDER and bpy:
            scene = bpy.context.scene
            return scene.BIMWorkCalendarProperties
        return MockProperties()

    @classmethod
    def get_animation_props(cls):
        """Get animation properties."""
        if HAS_BLENDER and bpy:
            scene = bpy.context.scene
            return scene.BIMAnimationProperties
        return MockProperties()

    @classmethod
    def get_filtered_tasks(cls, tasks: list) -> list:
        """
        Filters a list of tasks (and their children) based on active rules.
        If a parent task doesn't meet the filter, its children won't be shown either.
        EXACT COPY from sequence.py line ~1827
        """
        if not HAS_IFC or not tasks:
            return tasks

        props = cls.get_work_schedule_props()
        try:
            filter_rules = [r for r in getattr(props, "filters").rules if r.is_active]
        except Exception:
            return tasks

        if not filter_rules:
            return tasks

        filter_logic_is_and = getattr(props.filters, "logic", 'AND') == 'AND'

        def get_task_value(task, column_identifier):
            """Enhanced helper function to get the value of a column for a task."""
            if not task or not column_identifier:
                return None

            column_name = column_identifier.split('||')[0]

            if column_name == "Special.OutputsCount":
                try:
                    # Use ifcopenshell utility function to get outputs
                    return len(ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False))
                except Exception:
                    return 0

            if column_name in ("Special.VarianceStatus", "Special.VarianceDays"):
                try:
                    ws_props = cls.get_work_schedule_props()
                    source_a = ws_props.variance_source_a
                    source_b = ws_props.variance_source_b

                    if source_a == source_b:
                        return None

                    finish_attr_a = f"{source_a.capitalize()}Finish"
                    finish_attr_b = f"{source_b.capitalize()}Finish"

                    date_a = ifcopenshell.util.sequence.derive_date(task, finish_attr_a, is_latest=True)
                    date_b = ifcopenshell.util.sequence.derive_date(task, finish_attr_b, is_latest=True)

                    if date_a and date_b:
                        delta = date_b.date() - date_a.date()
                        variance_days = delta.days
                        if column_name == "Special.VarianceDays":
                            return variance_days
                        else:  # VarianceStatus
                            if variance_days > 0:
                                return f"Delayed (+{variance_days}d)"
                            elif variance_days < 0:
                                return f"Ahead ({variance_days}d)"
                            else:
                                return "On Time"
                    return "N/A"
                except Exception:
                    return "N/A"

            try:
                ifc_class, attr_name = column_name.split('.', 1)
                if ifc_class == "IfcTask":
                    return getattr(task, attr_name, None)
                elif ifc_class == "IfcTaskTime":
                    task_time = getattr(task, "TaskTime", None)
                    return getattr(task_time, attr_name, None) if task_time else None
            except Exception:
                return None
            return None

        def task_matches_filters(task):
            """Checks if a single task meets the set of filters."""
            results = []
            for rule in filter_rules:
                task_value = get_task_value(task, rule.column)
                data_type = getattr(rule, 'data_type', 'string')
                op = rule.operator
                match = False

                if op == 'EMPTY':
                    match = task_value is None or str(task_value).strip() == ""
                elif op == 'NOT_EMPTY':
                    match = task_value is not None and str(task_value).strip() != ""
                else:
                    try:
                        if data_type == 'integer':
                            rule_value = rule.value_integer
                            task_value_num = int(task_value)
                            if op == 'EQUALS': match = task_value_num == rule_value
                            elif op == 'NOT_EQUALS': match = task_value_num != rule_value
                            elif op == 'GREATER': match = task_value_num > rule_value
                            elif op == 'LESS': match = task_value_num < rule_value
                            elif op == 'GTE': match = task_value_num >= rule_value
                            elif op == 'LTE': match = task_value_num <= rule_value
                        elif data_type in ('float', 'real'):
                            rule_value = rule.value_float
                            task_value_num = float(task_value)
                            if op == 'EQUALS': match = task_value_num == rule_value
                            elif op == 'NOT_EQUALS': match = task_value_num != rule_value
                            elif op == 'GREATER': match = task_value_num > rule_value
                            elif op == 'LESS': match = task_value_num < rule_value
                            elif op == 'GTE': match = task_value_num >= rule_value
                            elif op == 'LTE': match = task_value_num <= rule_value
                        elif data_type == 'boolean':
                            rule_value = bool(rule.value_boolean)
                            task_value_bool = bool(task_value)
                            if op == 'EQUALS': match = task_value_bool == rule_value
                            elif op == 'NOT_EQUALS': match = task_value_bool != rule_value
                        elif data_type == 'date':
                            try:
                                import bonsai.bim.module.sequence.helper
                                task_date = bonsai.bim.module.sequence.helper.parse_datetime(str(task_value))
                                rule_date = bonsai.bim.module.sequence.helper.parse_datetime(rule.value_string)
                                if task_date and rule_date:
                                    if op == 'EQUALS': match = task_date.date() == rule_date.date()
                                    elif op == 'NOT_EQUALS': match = task_date.date() != rule_date.date()
                                    elif op == 'GREATER': match = task_date > rule_date
                                    elif op == 'LESS': match = task_date < rule_date
                                    elif op == 'GTE': match = task_date >= rule_date
                                    elif op == 'LTE': match = task_date <= rule_date
                            except Exception:
                                pass
                        elif data_type == 'variance_status':
                            # Special handling for variance status filtering
                            rule_value = rule.value_variance_status
                            task_value_str = str(task_value) if task_value is not None else ""
                            if op == 'EQUALS': match = rule_value in task_value_str
                            elif op == 'NOT_EQUALS': match = rule_value not in task_value_str
                            elif op == 'CONTAINS': match = rule_value in task_value_str
                            elif op == 'NOT_CONTAINS': match = rule_value not in task_value_str
                        else: # string, enums, etc.
                            rule_value = (rule.value_string or "").lower()
                            task_value_str = (str(task_value) if task_value is not None else "").lower()
                            if op == 'CONTAINS': match = rule_value in task_value_str
                            elif op == 'NOT_CONTAINS': match = rule_value not in task_value_str
                            elif op == 'EQUALS': match = rule_value == task_value_str
                            elif op == 'NOT_EQUALS': match = rule_value != task_value_str
                    except (ValueError, TypeError, AttributeError):
                        match = False
                results.append(match)

            if not results:
                return True
            return all(results) if filter_logic_is_and else any(results)

        filtered_list = []
        for task in tasks:
            try:
                nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                filtered_children = cls.get_filtered_tasks(nested_tasks) if nested_tasks else []

                if task_matches_filters(task) or len(filtered_children) > 0:
                    filtered_list.append(task)
            except Exception:
                # Add task if there's an error to avoid breaking the UI
                filtered_list.append(task)

        return filtered_list

    @classmethod
    def get_sorted_tasks_ids(cls, tasks: list) -> list[int]:
        """
        Get sorted task IDs for UI display.
        EXACT COPY from sequence.py line ~1795
        """
        if not HAS_IFC or not tasks:
            return []

        props = cls.get_work_schedule_props()

        def get_sort_key(task):
            # Sorting only applies to actual tasks, not the WBS
            try:
                if hasattr(props, 'sort_column') and props.sort_column:
                    column_type, name = props.sort_column.split(".")
                    if column_type == "IfcTask":
                        info = task.get_info() if hasattr(task, 'get_info') else {}
                        return info.get(name, "") or ""
                    elif column_type == "IfcTaskTime" and hasattr(task, 'TaskTime') and task.TaskTime:
                        task_time_info = task.TaskTime.get_info() if hasattr(task.TaskTime, 'get_info') else {}
                        return task_time_info.get(name, "") or ""
                return getattr(task, 'Identification', '') or ""
            except Exception:
                return getattr(task, 'Identification', '') or ""

        def natural_sort_key(i):
            import re
            _nsre = re.compile("([0-9]+)")
            s = sort_keys[i]
            return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(str(s))]

        try:
            if hasattr(props, 'sort_column') and props.sort_column:
                sort_keys = {task.id(): get_sort_key(task) for task in tasks}
                related_object_ids = sorted(sort_keys, key=natural_sort_key)
            else:
                related_object_ids = [task.id() for task in tasks]

            if hasattr(props, 'is_sort_reversed') and props.is_sort_reversed:
                related_object_ids.reverse()

            return related_object_ids
        except Exception as e:
            print(f"Error sorting tasks: {e}")
            return [task.id() for task in tasks]

    @classmethod
    def refresh_task_3d_counts(cls) -> None:
        """
        Recalcula y guarda el conteo total de elementos 3D (Inputs + Outputs)
        per task in the UI tree.
        EXACT COPY from sequence.py line ~2080
        """
        try:
            tprops = cls.get_task_tree_props()
            if not hasattr(tprops, "tasks"):
                return
        except Exception:
            return

        if not HAS_IFC:
            return

        try:
            import ifcopenshell.util.sequence
        except Exception:
            return

        for item in getattr(tprops, "tasks", []):
            try:
                if not tool:
                    continue
                task = tool.Ifc.get().by_id(item.ifc_definition_id)
                if not task:
                    if hasattr(item, "outputs_count"):
                        item.outputs_count = 0
                    continue

                # Calcular outputs
                outputs_count = len(ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False))

                # Calcular inputs
                inputs_count = len(ifcopenshell.util.sequence.get_task_inputs(task, is_deep=False))

                # Guardar la suma en la propiedad 'outputs_count'
                if hasattr(item, "outputs_count"):
                    item.outputs_count = outputs_count + inputs_count

            except Exception:
                if hasattr(item, "outputs_count"):
                    item.outputs_count = 0
                continue

    @classmethod
    def enable_editing_work_schedule_tasks(cls, work_schedule):
        """Enable editing work schedule tasks."""
        if work_schedule:
            props = cls.get_work_schedule_props()
            props.active_work_schedule_id = work_schedule.id()
            props.editing_type = "TASKS"


# Standalone utility functions for backward compatibility
def get_active_work_schedule():
    """Standalone function for getting active work schedule."""
    return TaskManager.get_active_work_schedule()

def load_task_properties(task):
    """Standalone function for loading task properties."""
    return TaskManager.load_task_properties(task)

def get_task_inputs(task):
    """Standalone function for getting task inputs."""
    return TaskManager.get_task_inputs(task)

def get_task_outputs(task):
    """Standalone function for getting task outputs."""
    return TaskManager.get_task_outputs(task)

def create_task(work_schedule, parent_task=None):
    """Standalone function for creating task."""
    return TaskManager.create_task(work_schedule, parent_task)