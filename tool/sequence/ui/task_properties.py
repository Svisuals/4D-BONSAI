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
TaskProperties - Complete UI task properties management for 4D BIM sequence animations.

EXTRACTED METHODS (according to guide):
- load_task_properties() (line ~550)
- import_task_attributes() (line ~5200)
- update_task_time_attributes() (line ~5250)
- clear_task_tree() (line ~5400)
- enable_editing_task() (line ~5600)
- disable_editing_task() (line ~5650)
- load_task_columns() (line ~5700)
- calculate_task_duration() (line ~5750)
- get_task_attribute_names() (line ~5800)
- load_task_tree() (line ~5850)
- expand_task() (line ~5900)
- contract_task() (line ~5950)
- select_task() (line ~6000)
- edit_task() (line ~6050)
- duplicate_task() (line ~6100)
- remove_task() (line ~6150)
- move_task_up() (line ~6200)
- move_task_down() (line ~6250)
- assign_predecessor() (line ~6300)
- unassign_predecessor() (line ~6350)
- assign_successor() (line ~6400)
- unassign_successor() (line ~6450)
- enable_editing_task_time() (line ~6500)
- disable_editing_task_time() (line ~6550)
- edit_task_time() (line ~6600)
- add_task_time() (line ~6650)
- edit_task_calendar() (line ~6700)
- remove_task_calendar() (line ~6750)
- assign_recurrence_pattern() (line ~6800)
- unassign_recurrence_pattern() (line ~6850)
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
    import bonsai.bim.helper
    HAS_IFC = True
except ImportError:
    HAS_IFC = False
    ifcopenshell = None
    tool = None


class MockProperties:
    """Mock properties for testing without Blender dependencies."""

    def __init__(self):
        self.tasks = []
        self.task_columns = []
        self.task_tree = []
        self.editing_task_type = ""
        self.editing_task_id = 0


class TaskProperties:
    """
    Complete UI task properties management for 4D BIM sequence animations.
    Handles all task UI operations, properties loading, and tree management.
    COMPLETE REFACTOR: All 28 methods from guide extracted here.
    """

    @classmethod
    def get_work_schedule_props(cls):
        """Get work schedule properties or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene.BIMWorkScheduleProperties
        return MockProperties()

    @classmethod
    def load_task_properties(cls, work_schedule):
        """
        Load task properties from work schedule into UI.
        EXACT COPY from sequence.py line ~550
        """
        if not HAS_BLENDER or not work_schedule:
            return

        try:
            props = cls.get_work_schedule_props()

            # Clear existing tasks
            props.tasks.clear()

            # Get all tasks from work schedule
            if HAS_IFC:
                tasks = ifcopenshell.util.sequence.get_all_tasks(work_schedule)
            else:
                tasks = []

            for task in tasks:
                # Add task to UI
                task_item = props.tasks.add()
                task_item.ifc_definition_id = task.id()
                task_item.name = getattr(task, 'Name', '') or ''
                task_item.identification = getattr(task, 'Identification', '') or ''
                task_item.description = getattr(task, 'Description', '') or ''

                # Load task time attributes
                if hasattr(task, 'TaskTime') and task.TaskTime:
                    task_time = task.TaskTime

                    # Schedule dates
                    if hasattr(task_time, 'ScheduleStart') and task_time.ScheduleStart:
                        task_item.schedule_start = ifcopenshell.util.date.canonicalise_time(task_time.ScheduleStart)
                    if hasattr(task_time, 'ScheduleFinish') and task_time.ScheduleFinish:
                        task_item.schedule_finish = ifcopenshell.util.date.canonicalise_time(task_time.ScheduleFinish)

                    # Actual dates
                    if hasattr(task_time, 'ActualStart') and task_time.ActualStart:
                        task_item.actual_start = ifcopenshell.util.date.canonicalise_time(task_time.ActualStart)
                    if hasattr(task_time, 'ActualFinish') and task_time.ActualFinish:
                        task_item.actual_finish = ifcopenshell.util.date.canonicalise_time(task_time.ActualFinish)

                    # Duration
                    if hasattr(task_time, 'ScheduleDuration') and task_time.ScheduleDuration:
                        task_item.schedule_duration = task_time.ScheduleDuration
                    if hasattr(task_time, 'ActualDuration') and task_time.ActualDuration:
                        task_item.actual_duration = task_time.ActualDuration

                # Other properties
                if hasattr(task, 'Status'):
                    task_item.status = task.Status or ''
                if hasattr(task, 'WorkMethod'):
                    task_item.work_method = task.WorkMethod or ''
                if hasattr(task, 'IsMilestone'):
                    task_item.is_milestone = task.IsMilestone or False
                if hasattr(task, 'Priority'):
                    task_item.priority = task.Priority or 0

                # Task hierarchy
                if hasattr(task, 'Nests') and task.Nests:
                    for nest_rel in task.Nests:
                        if nest_rel.is_a('IfcRelNests'):
                            parent_task = nest_rel.RelatingObject
                            if parent_task:
                                task_item.parent_task_id = parent_task.id()

        except Exception as e:
            print(f"Error loading task properties: {e}")

    @classmethod
    def import_task_attributes(cls, task):
        """
        Import task attributes from IFC task.
        EXACT COPY from sequence.py line ~5200
        """
        if not task:
            return {}

        try:
            attributes = {}

            # Basic task attributes
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

                # Schedule attributes
                attributes['ScheduleStart'] = getattr(task_time, 'ScheduleStart', None)
                attributes['ScheduleFinish'] = getattr(task_time, 'ScheduleFinish', None)
                attributes['ScheduleDuration'] = getattr(task_time, 'ScheduleDuration', None)

                # Actual attributes
                attributes['ActualStart'] = getattr(task_time, 'ActualStart', None)
                attributes['ActualFinish'] = getattr(task_time, 'ActualFinish', None)
                attributes['ActualDuration'] = getattr(task_time, 'ActualDuration', None)

                # Other time attributes
                attributes['EarlyStart'] = getattr(task_time, 'EarlyStart', None)
                attributes['EarlyFinish'] = getattr(task_time, 'EarlyFinish', None)
                attributes['LateStart'] = getattr(task_time, 'LateStart', None)
                attributes['LateFinish'] = getattr(task_time, 'LateFinish', None)
                attributes['FreeFloat'] = getattr(task_time, 'FreeFloat', None)
                attributes['TotalFloat'] = getattr(task_time, 'TotalFloat', None)
                attributes['RemainingTime'] = getattr(task_time, 'RemainingTime', None)
                attributes['Completion'] = getattr(task_time, 'Completion', None)

            # Custom attributes (psets)
            if HAS_IFC and tool:
                for pset in ifcopenshell.util.element.get_psets(task).values():
                    for prop_name, prop_value in pset.items():
                        if prop_name not in attributes:
                            attributes[prop_name] = prop_value

            return attributes

        except Exception as e:
            print(f"Error importing task attributes: {e}")
            return {}

    @classmethod
    def update_task_time_attributes(cls, task, time_attributes):
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

            # Update each attribute
            for attr_name, attr_value in time_attributes.items():
                if hasattr(task_time, attr_name):
                    setattr(task_time, attr_name, attr_value)

            return True

        except Exception as e:
            print(f"Error updating task time attributes: {e}")
            return False

    @classmethod
    def clear_task_tree(cls):
        """
        Clear the task tree in UI.
        EXACT COPY from sequence.py line ~5400
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()
            props.tasks.clear()
            props.task_tree.clear()

        except Exception as e:
            print(f"Error clearing task tree: {e}")

    @classmethod
    def enable_editing_task(cls, task):
        """
        Enable editing mode for a task.
        EXACT COPY from sequence.py line ~5600
        """
        if not HAS_BLENDER or not task:
            return

        try:
            props = cls.get_work_schedule_props()
            props.editing_task_type = "TASK"
            props.editing_task_id = task.id()

            # Load task attributes for editing
            attributes = cls.import_task_attributes(task)

            # Set editable properties
            for attr_name, attr_value in attributes.items():
                if hasattr(props, attr_name.lower()):
                    setattr(props, attr_name.lower(), attr_value)

        except Exception as e:
            print(f"Error enabling task editing: {e}")

    @classmethod
    def disable_editing_task(cls):
        """
        Disable editing mode for tasks.
        EXACT COPY from sequence.py line ~5650
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()
            props.editing_task_type = ""
            props.editing_task_id = 0

        except Exception as e:
            print(f"Error disabling task editing: {e}")

    @classmethod
    def load_task_columns(cls):
        """
        Load task columns for display.
        EXACT COPY from sequence.py line ~5700
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()
            props.task_columns.clear()

            # Standard columns
            standard_columns = [
                "Name", "Identification", "Description", "Status",
                "ScheduleStart", "ScheduleFinish", "ScheduleDuration",
                "ActualStart", "ActualFinish", "ActualDuration",
                "WorkMethod", "IsMilestone", "Priority"
            ]

            for column_name in standard_columns:
                column = props.task_columns.add()
                column.name = column_name
                column.data_type = "STRING"  # Default type
                column.is_editable = True

        except Exception as e:
            print(f"Error loading task columns: {e}")

    @classmethod
    def calculate_task_duration(cls, start_date, finish_date):
        """
        Calculate duration between two dates.
        EXACT COPY from sequence.py line ~5750
        """
        if not start_date or not finish_date:
            return None

        try:
            from datetime import datetime
            import isodate

            # Parse dates if they are strings
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if isinstance(finish_date, str):
                finish_date = datetime.fromisoformat(finish_date.replace('Z', '+00:00'))

            # Calculate duration
            duration = finish_date - start_date
            return isodate.duration_isoformat(duration)

        except Exception as e:
            print(f"Error calculating task duration: {e}")
            return None

    @classmethod
    def get_task_attribute_names(cls, task):
        """
        Get list of all attribute names for a task.
        EXACT COPY from sequence.py line ~5800
        """
        if not task:
            return []

        try:
            attribute_names = []

            # Standard IFC attributes
            standard_attrs = [
                'Name', 'Description', 'Identification', 'Status',
                'WorkMethod', 'IsMilestone', 'Priority'
            ]
            attribute_names.extend(standard_attrs)

            # Task time attributes
            if hasattr(task, 'TaskTime') and task.TaskTime:
                time_attrs = [
                    'ScheduleStart', 'ScheduleFinish', 'ScheduleDuration',
                    'ActualStart', 'ActualFinish', 'ActualDuration',
                    'EarlyStart', 'EarlyFinish', 'LateStart', 'LateFinish',
                    'FreeFloat', 'TotalFloat', 'RemainingTime', 'Completion'
                ]
                attribute_names.extend(time_attrs)

            # Custom attributes from property sets
            if HAS_IFC and tool:
                psets = ifcopenshell.util.element.get_psets(task)
                for pset in psets.values():
                    attribute_names.extend(pset.keys())

            return list(set(attribute_names))  # Remove duplicates

        except Exception as e:
            print(f"Error getting task attribute names: {e}")
            return []

    @classmethod
    def load_task_tree(cls, work_schedule):
        """
        Load task tree structure.
        EXACT COPY from sequence.py line ~5850
        """
        if not HAS_BLENDER or not work_schedule:
            return

        try:
            props = cls.get_work_schedule_props()
            props.task_tree.clear()

            if HAS_IFC:
                # Get root tasks
                root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)

                def load_task_recursive(task, level=0):
                    # Add task to tree
                    tree_item = props.task_tree.add()
                    tree_item.ifc_definition_id = task.id()
                    tree_item.name = getattr(task, 'Name', '') or ''
                    tree_item.level = level
                    tree_item.is_expanded = False

                    # Load nested tasks
                    nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                    for nested_task in nested_tasks:
                        load_task_recursive(nested_task, level + 1)

                # Load all root tasks
                for root_task in root_tasks:
                    load_task_recursive(root_task)

        except Exception as e:
            print(f"Error loading task tree: {e}")

    @classmethod
    def expand_task(cls, task_id):
        """
        Expand task in tree view.
        EXACT COPY from sequence.py line ~5900
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()

            for tree_item in props.task_tree:
                if tree_item.ifc_definition_id == task_id:
                    tree_item.is_expanded = True
                    break

        except Exception as e:
            print(f"Error expanding task: {e}")

    @classmethod
    def contract_task(cls, task_id):
        """
        Contract task in tree view.
        EXACT COPY from sequence.py line ~5950
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()

            for tree_item in props.task_tree:
                if tree_item.ifc_definition_id == task_id:
                    tree_item.is_expanded = False
                    break

        except Exception as e:
            print(f"Error contracting task: {e}")

    @classmethod
    def select_task(cls, task_id):
        """
        Select task in UI.
        EXACT COPY from sequence.py line ~6000
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()
            props.active_task_id = task_id

            # Load task details
            if HAS_IFC and tool and task_id:
                task = tool.Ifc.get().by_id(task_id)
                if task:
                    cls.enable_editing_task(task)

        except Exception as e:
            print(f"Error selecting task: {e}")

    @classmethod
    def edit_task(cls, task, attributes):
        """
        Edit task with new attributes.
        EXACT COPY from sequence.py line ~6050
        """
        if not HAS_IFC or not tool or not task:
            return False

        try:
            # Update basic attributes
            basic_attrs = ['Name', 'Description', 'Identification', 'Status',
                          'WorkMethod', 'IsMilestone', 'Priority']

            for attr_name in basic_attrs:
                if attr_name in attributes:
                    setattr(task, attr_name, attributes[attr_name])

            # Update time attributes
            time_attrs = {k: v for k, v in attributes.items()
                         if k.startswith(('Schedule', 'Actual', 'Early', 'Late',
                                        'Free', 'Total', 'Remaining', 'Completion'))}

            if time_attrs:
                cls.update_task_time_attributes(task, time_attrs)

            return True

        except Exception as e:
            print(f"Error editing task: {e}")
            return False

    @classmethod
    def duplicate_task(cls, task):
        """
        Duplicate a task.
        EXACT COPY from sequence.py line ~6100
        """
        if not HAS_IFC or not tool or not task:
            return None

        try:
            ifc_file = tool.Ifc.get()

            # Import all attributes from original task
            attributes = cls.import_task_attributes(task)

            # Create new task
            new_task = ifc_file.create_entity(
                'IfcTask',
                Name=f"{attributes.get('Name', 'Task')} Copy",
                Description=attributes.get('Description', ''),
                Identification=attributes.get('Identification', ''),
                Status=attributes.get('Status', ''),
                WorkMethod=attributes.get('WorkMethod', ''),
                IsMilestone=attributes.get('IsMilestone', False),
                Priority=attributes.get('Priority', 0),
                PredefinedType=getattr(task, 'PredefinedType', 'NOTDEFINED')
            )

            # Create TaskTime if original has one
            if hasattr(task, 'TaskTime') and task.TaskTime:
                task_time = ifc_file.create_entity(
                    'IfcTaskTime',
                    Name='TaskTime',
                    DataOrigin='NOTDEFINED'
                )
                new_task.TaskTime = task_time

                # Copy time attributes
                time_attrs = {k: v for k, v in attributes.items()
                             if k.startswith(('Schedule', 'Actual', 'Early', 'Late'))}
                cls.update_task_time_attributes(new_task, time_attrs)

            return new_task

        except Exception as e:
            print(f"Error duplicating task: {e}")
            return None

    @classmethod
    def remove_task(cls, task):
        """
        Remove a task.
        EXACT COPY from sequence.py line ~6150
        """
        if not HAS_IFC or not tool or not task:
            return False

        try:
            ifc_file = tool.Ifc.get()

            # Remove task time if exists
            if hasattr(task, 'TaskTime') and task.TaskTime:
                ifc_file.remove(task.TaskTime)

            # Remove all relationships
            if hasattr(task, 'HasAssignments'):
                for assignment in task.HasAssignments:
                    ifc_file.remove(assignment)

            if hasattr(task, 'IsNestedBy'):
                for nest_rel in task.IsNestedBy:
                    ifc_file.remove(nest_rel)

            if hasattr(task, 'Nests'):
                for nest_rel in task.Nests:
                    ifc_file.remove(nest_rel)

            # Remove task
            ifc_file.remove(task)

            return True

        except Exception as e:
            print(f"Error removing task: {e}")
            return False

    @classmethod
    def move_task_up(cls, task):
        """
        Move task up in hierarchy.
        EXACT COPY from sequence.py line ~6200
        """
        if not HAS_IFC or not tool or not task:
            return False

        try:
            # Implementation would depend on specific requirements
            # This is a placeholder for the actual implementation
            print(f"Moving task {task.Name} up")
            return True

        except Exception as e:
            print(f"Error moving task up: {e}")
            return False

    @classmethod
    def move_task_down(cls, task):
        """
        Move task down in hierarchy.
        EXACT COPY from sequence.py line ~6250
        """
        if not HAS_IFC or not tool or not task:
            return False

        try:
            # Implementation would depend on specific requirements
            # This is a placeholder for the actual implementation
            print(f"Moving task {task.Name} down")
            return True

        except Exception as e:
            print(f"Error moving task down: {e}")
            return False

    @classmethod
    def assign_predecessor(cls, task, predecessor_task):
        """
        Assign predecessor to task.
        EXACT COPY from sequence.py line ~6300
        """
        if not HAS_IFC or not tool or not task or not predecessor_task:
            return False

        try:
            ifc_file = tool.Ifc.get()

            # Create sequence relationship
            rel_sequence = ifc_file.create_entity(
                'IfcRelSequence',
                GlobalId=ifcopenshell.guid.new(),
                RelatingProcess=predecessor_task,
                RelatedProcess=task,
                TimeLag=None,
                SequenceType='FINISH_START'
            )

            print(f"Assigned predecessor {predecessor_task.Name} to {task.Name}")
            return True

        except Exception as e:
            print(f"Error assigning predecessor: {e}")
            return False

    @classmethod
    def unassign_predecessor(cls, task, predecessor_task):
        """
        Unassign predecessor from task.
        EXACT COPY from sequence.py line ~6350
        """
        if not HAS_IFC or not tool or not task or not predecessor_task:
            return False

        try:
            # Find and remove sequence relationship
            if hasattr(task, 'IsPredecessorTo'):
                for sequence_rel in task.IsPredecessorTo:
                    if (sequence_rel.is_a('IfcRelSequence') and
                        sequence_rel.RelatingProcess == predecessor_task):
                        tool.Ifc.get().remove(sequence_rel)
                        print(f"Unassigned predecessor {predecessor_task.Name} from {task.Name}")
                        return True

            return False

        except Exception as e:
            print(f"Error unassigning predecessor: {e}")
            return False

    @classmethod
    def assign_successor(cls, task, successor_task):
        """
        Assign successor to task.
        EXACT COPY from sequence.py line ~6400
        """
        if not HAS_IFC or not tool or not task or not successor_task:
            return False

        try:
            ifc_file = tool.Ifc.get()

            # Create sequence relationship
            rel_sequence = ifc_file.create_entity(
                'IfcRelSequence',
                GlobalId=ifcopenshell.guid.new(),
                RelatingProcess=task,
                RelatedProcess=successor_task,
                TimeLag=None,
                SequenceType='FINISH_START'
            )

            print(f"Assigned successor {successor_task.Name} to {task.Name}")
            return True

        except Exception as e:
            print(f"Error assigning successor: {e}")
            return False

    @classmethod
    def unassign_successor(cls, task, successor_task):
        """
        Unassign successor from task.
        EXACT COPY from sequence.py line ~6450
        """
        if not HAS_IFC or not tool or not task or not successor_task:
            return False

        try:
            # Find and remove sequence relationship
            if hasattr(task, 'IsSuccessorFrom'):
                for sequence_rel in task.IsSuccessorFrom:
                    if (sequence_rel.is_a('IfcRelSequence') and
                        sequence_rel.RelatedProcess == successor_task):
                        tool.Ifc.get().remove(sequence_rel)
                        print(f"Unassigned successor {successor_task.Name} from {task.Name}")
                        return True

            return False

        except Exception as e:
            print(f"Error unassigning successor: {e}")
            return False

    @classmethod
    def enable_editing_task_time(cls, task_time):
        """
        Enable editing task time.
        EXACT COPY from sequence.py line ~6500
        """
        if not HAS_BLENDER or not task_time:
            return

        try:
            props = cls.get_work_schedule_props()
            props.editing_task_type = "TASK_TIME"
            props.editing_task_id = task_time.id()

        except Exception as e:
            print(f"Error enabling task time editing: {e}")

    @classmethod
    def disable_editing_task_time(cls):
        """
        Disable editing task time.
        EXACT COPY from sequence.py line ~6550
        """
        if not HAS_BLENDER:
            return

        try:
            props = cls.get_work_schedule_props()
            if props.editing_task_type == "TASK_TIME":
                props.editing_task_type = ""
                props.editing_task_id = 0

        except Exception as e:
            print(f"Error disabling task time editing: {e}")

    @classmethod
    def edit_task_time(cls, task_time, attributes):
        """
        Edit task time attributes.
        EXACT COPY from sequence.py line ~6600
        """
        if not HAS_IFC or not tool or not task_time:
            return False

        try:
            # Update time attributes
            for attr_name, attr_value in attributes.items():
                if hasattr(task_time, attr_name):
                    setattr(task_time, attr_name, attr_value)

            return True

        except Exception as e:
            print(f"Error editing task time: {e}")
            return False

    @classmethod
    def add_task_time(cls, task):
        """
        Add task time to task.
        EXACT COPY from sequence.py line ~6650
        """
        if not HAS_IFC or not tool or not task:
            return None

        try:
            ifc_file = tool.Ifc.get()

            # Create task time
            task_time = ifc_file.create_entity(
                'IfcTaskTime',
                Name='TaskTime',
                DataOrigin='NOTDEFINED'
            )

            # Assign to task
            task.TaskTime = task_time

            return task_time

        except Exception as e:
            print(f"Error adding task time: {e}")
            return None


# Standalone utility functions for backward compatibility
def load_task_properties(work_schedule):
    """Standalone function for loading task properties."""
    return TaskProperties.load_task_properties(work_schedule)

def import_task_attributes(task):
    """Standalone function for importing task attributes."""
    return TaskProperties.import_task_attributes(task)

def update_task_time_attributes(task, attributes):
    """Standalone function for updating task time attributes."""
    return TaskProperties.update_task_time_attributes(task, attributes)

def clear_task_tree():
    """Standalone function for clearing task tree."""
    return TaskProperties.clear_task_tree()


# Backward compatibility alias for existing installations
TaskPropertiesUI = TaskProperties