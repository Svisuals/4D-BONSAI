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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai.  If not, see <http://www.gnu.org/licenses/>.



import bpy
import ifcopenshell
import ifcopenshell.util.sequence
import ifcopenshell.util.date
import ifcopenshell.util.element
import json
import re
from datetime import datetime
from typing import Any
import bonsai.tool as tool
from . import props_sequence
from . import utils_sequence
from . import animation_sequence


def get_active_work_schedule():
    """Gets the currently active work schedule from props."""
    props = props_sequence.get_work_schedule_props()
    if not props.active_work_schedule_id or props.active_work_schedule_id <= 0:
        return None
    try:
        return tool.Ifc.get().by_id(props.active_work_schedule_id)
    except RuntimeError as e:
        if "not found" in str(e):
            # Reset the invalid ID and return None
            props.active_work_schedule_id = 0
            return None
        raise


def get_task_outputs(task: ifcopenshell.entity_instance):
    """Gets task outputs, respecting the nested output setting."""
    props = props_sequence.get_work_schedule_props()
    is_deep = getattr(props, 'show_nested_outputs', False)
    return ifcopenshell.util.sequence.get_task_outputs(task, is_deep)


def get_task_inputs(task: ifcopenshell.entity_instance):
    """Gets task inputs, respecting the nested input setting."""
    props = props_sequence.get_work_schedule_props()
    is_deep = getattr(props, 'show_nested_inputs', False)  
    return ifcopenshell.util.sequence.get_task_inputs(task, is_deep)


def load_task_outputs(outputs):
    """Load task outputs into UI props."""
    props = props_sequence.get_work_schedule_props()
    props.task_outputs.clear()
    for output in outputs:
        new_output = props.task_outputs.add()
        new_output.ifc_definition_id = output.id()
        new_output.name = output.Name or "Unnamed Output"


def load_task_inputs(inputs):
    """Load task inputs into UI props."""
    props = props_sequence.get_work_schedule_props()
    props.task_inputs.clear()
    for input_item in inputs:
        new_input = props.task_inputs.add()
        new_input.ifc_definition_id = input_item.id()
        new_input.name = input_item.Name or "Unnamed Input"


def load_task_resources(task: ifcopenshell.entity_instance):
    """Load task resources into UI props."""
    props = props_sequence.get_work_schedule_props()
    props.task_resources.clear()
    try:
        resources = ifcopenshell.util.sequence.get_task_resources(task)
        for resource in resources:
            new_resource = props.task_resources.add()
            new_resource.ifc_definition_id = resource.id()
            new_resource.name = resource.Name or "Unnamed Resource"
    except Exception as e:
        print(f"Error loading task resources: {e}")



def update_task_ICOM(task: ifcopenshell.entity_instance) -> None:
    """Refreshes the ICOM data (Outputs, Inputs, Resources) of the panel for the active task."""
    props = props_sequence.get_work_schedule_props()
    if task:
        outputs = get_task_outputs(task) or []
        load_task_outputs(outputs)
        inputs = get_task_inputs(task) or []
        load_task_inputs(inputs)
        load_task_resources(task)
    else:
        props.task_outputs.clear()
        props.task_inputs.clear()
        props.task_resources.clear()


def load_task_tree(work_schedule: ifcopenshell.entity_instance) -> None:
    """Load tasks for the given work schedule into the UI properties."""
    print(f"🔄 Loading task tree for work schedule: {work_schedule.id() if work_schedule else 'None'}")
    
    if not work_schedule:
        print("❌ No work schedule provided to load_task_tree")
        return
        
    try:
        props = props_sequence.get_task_tree_props()
        props.tasks.clear()
        schedule_props = props_sequence.get_work_schedule_props()
        
        # Ensure we have valid contracted_tasks JSON
        try:
            contracted_tasks = json.loads(schedule_props.contracted_tasks)
        except (json.JSONDecodeError, AttributeError):
            contracted_tasks = []
            schedule_props.contracted_tasks = "[]"

        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
        print(f"📋 Found {len(root_tasks) if root_tasks else 0} root tasks")
        
        if not root_tasks:
            print("⚠️ No root tasks found for this work schedule")
            return
            
        # Use the working get_filtered_tasks function or fallback
        try:
            filtered_root_tasks = get_filtered_tasks(root_tasks)
        except (NameError, AttributeError) as e:
            print(f"⚠️ Filtering failed ({e}), using all tasks")
            filtered_root_tasks = root_tasks
            
        related_objects_ids = get_sorted_tasks_ids(filtered_root_tasks)
        print(f"📝 Processing {len(related_objects_ids)} tasks for UI")

        for related_object_id in related_objects_ids:
            try:
                create_new_task_li(related_object_id, 0, contracted_tasks)
            except Exception as e:
                print(f"⚠️ Error creating task UI for {related_object_id}: {e}")
                
        print(f"✅ Task tree loaded successfully - {len(props.tasks)} tasks in UI")
        
    except Exception as e:
        print(f"❌ Error in load_task_tree: {e}")
        import traceback
        traceback.print_exc()


def get_sorted_tasks_ids(tasks: list[ifcopenshell.entity_instance]) -> list[int]:
    props = props_sequence.get_work_schedule_props()

    def get_sort_key(task):
        column_type, name = props.sort_column.split(".")
        if column_type == "IfcTask":
            return task.get_info(task)[name] or ""
        elif column_type == "IfcTaskTime" and task.TaskTime:
            return task.TaskTime.get_info(task)[name] if task.TaskTime.get_info(task)[name] else ""
        return task.Identification or ""

    def natural_sort_key(i, _nsre=re.compile("([0-9]+)")):
        s = sort_keys[i]
        return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]

    if props.sort_column:
        sort_keys = {task.id(): get_sort_key(task) for task in tasks}
        related_object_ids = sorted(sort_keys, key=natural_sort_key)
    else:
        related_object_ids = [task.id() for task in tasks]
    if props.is_sort_reversed:
        related_object_ids.reverse()
    return related_object_ids

 
# Removed broken get_filtered_tasks_internal function - using the working one at the end of file


def create_new_task_li(related_object_id: int, level_index: int, contracted_tasks: list) -> None:
    task = tool.Ifc.get().by_id(related_object_id)
    props = props_sequence.get_task_tree_props()
    new = props.tasks.add()
    new.ifc_definition_id = related_object_id
    new.is_expanded = related_object_id not in contracted_tasks
    new.level_index = level_index
    if task.IsNestedBy:
        new.has_children = True
        if new.is_expanded:
            for child_related_object_id in get_sorted_tasks_ids(ifcopenshell.util.sequence.get_nested_tasks(task)):
                create_new_task_li(child_related_object_id, level_index + 1, contracted_tasks)


def _load_task_date_properties(item, task, date_type_prefix):
    """Helper to load a pair of dates (e.g., ScheduleStart/Finish) for a task item."""
    prop_prefix = date_type_prefix.lower()
    start_attr, finish_attr = f"{date_type_prefix}Start", f"{date_type_prefix}Finish"
    item_start, item_finish = ("start", "finish") if prop_prefix == "schedule" else (f"{prop_prefix}_start", f"{prop_prefix}_finish")
    derived_start, derived_finish = f"derived_{item_start}", f"derived_{item_finish}"
    task_time = getattr(task, "TaskTime", None)
    if task_time and (getattr(task_time, start_attr, None) or getattr(task_time, finish_attr, None)):
        start_val = getattr(task_time, start_attr, None)
        finish_val = getattr(task_time, finish_attr, None)
        setattr(item, item_start, ifcopenshell.util.date.canonicalise_time(ifcopenshell.util.date.ifc2datetime(start_val)) if start_val else "-")
        setattr(item, item_finish, ifcopenshell.util.date.canonicalise_time(ifcopenshell.util.date.ifc2datetime(finish_val)) if finish_val else "-")
        setattr(item, derived_start, "")
        setattr(item, derived_finish, "")
    else:
        d_start = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
        d_finish = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
        setattr(item, derived_start, ifcopenshell.util.date.canonicalise_time(d_start) if d_start else "")
        setattr(item, derived_finish, ifcopenshell.util.date.canonicalise_time(d_finish) if d_finish else "")
        setattr(item, item_start, "-")
        setattr(item, item_finish, "-")


def load_task_properties() -> None:
    from . import visuals_sequence
    props = props_sequence.get_work_schedule_props()
    task_props = props_sequence.get_task_tree_props()
    tasks_with_visual_bar = visuals_sequence.get_task_bar_list()
    props.is_task_update_enabled = False

    for item in task_props.tasks:
        task = tool.Ifc.get().by_id(item.ifc_definition_id)
        item.name = task.Name or "Unnamed"
        item.identification = task.Identification or "XXX"
        item.has_bar_visual = item.ifc_definition_id in tasks_with_visual_bar
        if props.highlighted_task_id:
            item.is_predecessor = props.highlighted_task_id in [rel.RelatedProcess.id() for rel in task.IsPredecessorTo]
            item.is_successor = props.highlighted_task_id in [rel.RelatingProcess.id() for rel in task.IsSuccessorFrom]
        calendar = ifcopenshell.util.sequence.derive_calendar(task)
        if ifcopenshell.util.sequence.get_calendar(task):
            item.calendar = calendar.Name or "Unnamed" if calendar else ""
        else:
            item.calendar = ""
            item.derived_calendar = calendar.Name or "Unnamed" if calendar else ""

        _load_task_date_properties(item, task, "Schedule")
        _load_task_date_properties(item, task, "Actual")
        _load_task_date_properties(item, task, "Early")
        _load_task_date_properties(item, task, "Late")

        task_time = task.TaskTime
        if task_time and task_time.ScheduleDuration:
            item.duration = str(ifcopenshell.util.date.readable_ifc_duration(task_time.ScheduleDuration))
        else:
            derived_start = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
            derived_finish = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
            if derived_start and derived_finish:
                derived_duration = ifcopenshell.util.sequence.count_working_days(derived_start, derived_finish, calendar)
                item.derived_duration = str(ifcopenshell.util.date.readable_ifc_duration(f"P{derived_duration}D"))
            else:
                item.derived_duration = ""
            item.duration = "-"
    try:
        refresh_task_output_counts()
    except Exception:
        pass
    props.is_task_update_enabled = True


def refresh_task_output_counts() -> None:
    """
    Recalcula y guarda (si existe) el conteo de Outputs por tarea en el árbol actual.
    """
    try:
        tprops = props_sequence.get_task_tree_props()
    except Exception:
        return
    for item in getattr(tprops, "tasks", []):
        try:
            task = tool.Ifc.get().by_id(item.ifc_definition_id)
            count = len(ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)) if task else 0
            if hasattr(item, "outputs_count"):
                setattr(item, "outputs_count", count)
        except Exception:
            continue


def expand_task(task: ifcopenshell.entity_instance) -> None:
    props = props_sequence.get_work_schedule_props()
    contracted_tasks = json.loads(props.contracted_tasks)
    contracted_tasks.remove(task.id())
    props.contracted_tasks = json.dumps(contracted_tasks)


def contract_task(task: ifcopenshell.entity_instance) -> None:
    props = props_sequence.get_work_schedule_props()
    contracted_tasks = json.loads(props.contracted_tasks)
    contracted_tasks.append(task.id())
    props.contracted_tasks = json.dumps(contracted_tasks)


def expand_all_tasks() -> None:
    props = props_sequence.get_work_schedule_props()
    props.contracted_tasks = json.dumps([])


def contract_all_tasks() -> None:
    props = props_sequence.get_work_schedule_props()
    tprops = props_sequence.get_task_tree_props()
    contracted_tasks = json.loads(props.contracted_tasks)
    for task_item in tprops.tasks:
        if task_item.is_expanded:
            contracted_tasks.append(task_item.ifc_definition_id)
    props.contracted_tasks = json.dumps(contracted_tasks)


def get_checked_tasks() -> list[ifcopenshell.entity_instance]:
    return [
        tool.Ifc.get().by_id(task.ifc_definition_id) for task in props_sequence.get_task_tree_props().tasks if task.is_selected
    ] or []


# These functions are duplicated - removed to avoid conflicts


def get_direct_nested_tasks(task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
    return ifcopenshell.util.sequence.get_nested_tasks(task)


def get_direct_task_outputs(task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
    return ifcopenshell.util.sequence.get_direct_task_outputs(task)


# These functions are duplicated - removed to avoid conflicts


def load_task_resources(task: ifcopenshell.entity_instance) -> None:
    props = props_sequence.get_work_schedule_props()
    rprops = tool.Resource.get_resource_props()
    props.task_resources.clear()
    rprops.is_resource_update_enabled = False
    for resource in get_task_resources(task) or []:
        new = props.task_resources.add()
        new.ifc_definition_id = resource.id()
        new.name = resource.Name or "Unnamed"
        new.schedule_usage = resource.Usage.ScheduleUsage or 0 if resource.Usage else 0
    rprops.is_resource_update_enabled = True


def get_task_resources(task: ifcopenshell.entity_instance | None) -> list[ifcopenshell.entity_instance] | None:
    if not task:
        return
    props = props_sequence.get_work_schedule_props()
    is_deep = props.show_nested_resources
    return ifcopenshell.util.sequence.get_task_resources(task, is_deep)


def apply_selection_from_checkboxes():
    """
    Selects the 3D objects of all tasks marked with the checkbox in the viewport.
    """
    try:
        tprops = props_sequence.get_task_tree_props()
        if not tprops:
            return

        selected_tasks_pg = [task_pg for task_pg in tprops.tasks if getattr(task_pg, 'is_selected', False)]
        bpy.ops.object.select_all(action='DESELECT')
        if not selected_tasks_pg:
            return

        objects_to_select = []
        for task_pg in selected_tasks_pg:
            task_ifc = tool.Ifc.get().by_id(task_pg.ifc_definition_id)
            if not task_ifc:
                continue
            outputs = get_task_outputs(task_ifc)
            for product in outputs:
                obj = tool.Ifc.get_object(product)
                if obj:
                    objects_to_select.append(obj)
        if objects_to_select:
            for obj in objects_to_select:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = objects_to_select[0]
    except Exception as e:
        print(f"Error applying selection from checkboxes: {e}")

def get_task_attributes() -> dict[str, Any]:
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    from bonsai.bim.helper import draw_attributes
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        if "Date" in prop.name or "Time" in prop.name:
            attributes[prop.name] = None if prop.is_null else bonsai.bim.helper.parse_datetime(prop.string_value)
            return True
        elif prop.name == "Duration" or prop.name == "TotalFloat":
            attributes[prop.name] = None if prop.is_null else helper.parse_duration(prop.string_value)
            return True
        return False
    
    props = props_sequence.get_work_schedule_props()
    return bonsai.bim.helper.export_attributes(props.task_attributes, callback)

def load_task_attributes(task: ifcopenshell.entity_instance) -> None:
    from typing import Any, Union, Literal
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
        if name in ["ScheduleStart", "ScheduleFinish", "ActualStart", "ActualFinish"]:
            assert prop
            prop.string_value = "" if prop.is_null else data[name]
            return True
    
    props = props_sequence.get_work_schedule_props()
    props.task_attributes.clear()
    bonsai.bim.helper.import_attributes(task, props.task_attributes, callback)

def get_active_task() -> ifcopenshell.entity_instance:
    import bonsai.tool as tool
    
    props = props_sequence.get_work_schedule_props()
    if not props.active_task_id:
        return None
    return tool.Ifc.get().by_id(props.active_task_id)

def get_task_attribute_value(attribute_name: str) -> Any:
    props = props_sequence.get_work_schedule_props()
    try:
        return props.task_attributes[attribute_name].get_value()
    except (KeyError, IndexError):
        return None

def get_task_time(task: ifcopenshell.entity_instance) -> ifcopenshell.entity_instance | None:
    """Get the task time object associated with a task"""
    import bonsai.tool as tool
    
    if not task or not hasattr(task, 'TaskTime'):
        return None
    return task.TaskTime

def get_task_time_attributes() -> dict[str, Any]:
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    from bonsai.bim.helper import draw_attributes
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        if "Date" in prop.name or "Time" in prop.name:
            attributes[prop.name] = None if prop.is_null else bonsai.bim.helper.parse_datetime(prop.string_value)
            return True
        elif prop.name == "Duration" or prop.name == "TotalFloat":
            attributes[prop.name] = None if prop.is_null else helper.parse_duration(prop.string_value)
            return True
        return False
    
    props = props_sequence.get_task_tree_props()
    return bonsai.bim.helper.export_attributes(props.task_time_attributes, callback)

def load_task_time_attributes(task_time: ifcopenshell.entity_instance) -> None:
    from typing import Any, Union, Literal
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
        if name in ["ScheduleStart", "ScheduleFinish", "ScheduleDuration", "ActualStart", "ActualFinish", "ActualDuration"]:
            assert prop
            prop.string_value = "" if prop.is_null else data[name]
            return True
    
    props = props_sequence.get_task_tree_props()
    props.task_time_attributes.clear()
    bonsai.bim.helper.import_attributes(task_time, props.task_time_attributes, callback)

def has_duration(task: ifcopenshell.entity_instance) -> bool:
    """Check if a task has a duration defined"""
    task_time = get_task_time(task)
    if not task_time:
        return False
    
    return bool(
        getattr(task_time, 'ScheduleDuration', None) or 
        getattr(task_time, 'ActualDuration', None)
    )

def get_work_schedule(task: ifcopenshell.entity_instance) -> ifcopenshell.entity_instance | None:
    """Get the work schedule that contains a task"""
    
    def get_ancestor_ids(task):
        """Recursively get all ancestor task IDs"""
        ids = []
        if hasattr(task, 'Nests') and task.Nests:
            for rel in task.Nests:
                if hasattr(rel, 'RelatingObject') and rel.RelatingObject:
                    parent = rel.RelatingObject
                    ids.append(parent.id())
                    ids.extend(get_ancestor_ids(parent))
        return ids

    # Check if task is directly in a work schedule
    if hasattr(task, 'Nests') and task.Nests:
        for rel in task.Nests:
            if hasattr(rel, 'RelatingObject') and rel.RelatingObject:
                relating_obj = rel.RelatingObject
                if relating_obj.is_a('IfcWorkSchedule'):
                    return relating_obj
    
    # Check ancestor tasks
    ancestor_ids = get_ancestor_ids(task)
    import bonsai.tool as tool
    ifc = tool.Ifc.get()
    
    for ancestor_id in ancestor_ids:
        ancestor = ifc.by_id(ancestor_id)
        if ancestor.is_a('IfcWorkSchedule'):
            return ancestor
    
    return None

def get_highlighted_task() -> ifcopenshell.entity_instance | None:
    """Get the currently highlighted task in the UI"""
    props = props_sequence.get_task_tree_props()
    if not hasattr(props, 'highlighted_task_id') or not props.highlighted_task_id:
        return None
    
    import bonsai.tool as tool
    return tool.Ifc.get().by_id(props.highlighted_task_id)

def get_checked_tasks() -> list[ifcopenshell.entity_instance]:
    """Get all tasks that are currently checked in the UI"""
    props = props_sequence.get_task_tree_props()
    tasks = []
    
    import bonsai.tool as tool
    ifc = tool.Ifc.get()
    
    for task_item in props.tasks:
        if getattr(task_item, 'is_selected', False):
            task = ifc.by_id(task_item.ifc_definition_id)
            if task:
                tasks.append(task)
    
    return tasks

def refresh_task_resources():
    """Refresh the task resources display for the active task"""
    props = props_sequence.get_work_schedule_props()
    if props.active_task_id:
        import bonsai.tool as tool
        task = tool.Ifc.get().by_id(props.active_task_id)
        if task:
            load_task_resources(task)

def load_task_resources(task: ifcopenshell.entity_instance):
    """Load resources for a specific task"""
    props = props_sequence.get_work_schedule_props()
    rprops = props_sequence.get_status_props()
    
    props.task_resources.clear()
    rprops.is_resource_update_enabled = False
    
    for resource in get_task_resources(task) or []:
        new = props.task_resources.add()
        new.ifc_definition_id = resource.id()
        new.name = resource.Name or "Unnamed"
        new.schedule_usage = resource.Usage.ScheduleUsage or 0 if resource.Usage else 0
    
    rprops.is_resource_update_enabled = True

def get_sorted_tasks_ids(tasks: list[ifcopenshell.entity_instance]) -> list[int]:
    """Sort tasks by their properties and return sorted IDs"""
    
    def get_sort_key(task):
        props = props_sequence.get_task_tree_props()
        sort_column = getattr(props, 'sort_column', 'Name')
        
        if sort_column == 'Name':
            return task.Name or ''
        elif sort_column == 'Identification':
            return getattr(task, 'Identification', '') or ''
        elif sort_column == 'ScheduleStart':
            task_time = get_task_time(task)
            if task_time:
                return getattr(task_time, 'ScheduleStart', '') or ''
            return ''
        elif sort_column == 'ScheduleFinish':
            task_time = get_task_time(task)
            if task_time:
                return getattr(task_time, 'ScheduleFinish', '') or ''
            return ''
        else:
            return ''
    
    # Sort tasks
    sorted_tasks = sorted(tasks, key=get_sort_key)
    
    # Get reverse order if needed
    props = props_sequence.get_task_tree_props()
    if getattr(props, 'is_sort_reversed', False):
        sorted_tasks.reverse()
    
    return [task.id() for task in sorted_tasks]

def get_filtered_tasks(tasks: list[ifcopenshell.entity_instance]) -> list[ifcopenshell.entity_instance]:
    """Filter tasks based on current filter settings"""
    props = props_sequence.get_task_tree_props()
    
    if not getattr(props, 'filter_value', ''):
        return tasks
    
    filter_value = props.filter_value.lower()
    filter_column = getattr(props, 'filter_column', 'Name')
    
    def get_task_value(task, column_identifier):
        if column_identifier == 'Name':
            return (task.Name or '').lower()
        elif column_identifier == 'Identification':
            return (getattr(task, 'Identification', '') or '').lower()
        elif column_identifier == 'ScheduleStart':
            task_time = get_task_time(task)
            if task_time:
                return str(getattr(task_time, 'ScheduleStart', '') or '').lower()
            return ''
        elif column_identifier == 'ScheduleFinish':
            task_time = get_task_time(task)
            if task_time:
                return str(getattr(task_time, 'ScheduleFinish', '') or '').lower()
            return ''
        else:
            return ''
    
    filtered_tasks = []
    for task in tasks:
        task_value = get_task_value(task, filter_column)
        if filter_value in task_value:
            filtered_tasks.append(task)
    
    return filtered_tasks

def get_selected_task_ids():
    """Get IDs of all selected tasks in the task tree"""
    props = props_sequence.get_task_tree_props()
    selected_ids = []
    
    for task_item in props.tasks:
        if getattr(task_item, 'is_selected', False):
            selected_ids.append(task_item.ifc_definition_id)
    
    return selected_ids

def load_product_related_tasks(product):
    """Load tasks related to a specific product"""
    import bonsai.tool as tool
    
    if not product:
        return
    
    # Get tasks that use this product as input or output
    consuming_tasks, producing_tasks = get_tasks_for_product(product)
    
    # Load these tasks into UI properties if needed
    props = props_sequence.get_task_tree_props()
    
    # Clear existing product-related tasks
    props.product_related_tasks.clear()
    
    # Add consuming tasks
    for task in consuming_tasks:
        new_task = props.product_related_tasks.add()
        new_task.ifc_definition_id = task.id()
        new_task.name = task.Name or "Unnamed Task"
        new_task.relationship_type = "CONSUMES"
    
    # Add producing tasks  
    for task in producing_tasks:
        new_task = props.product_related_tasks.add()
        new_task.ifc_definition_id = task.id()
        new_task.name = task.Name or "Unnamed Task"
        new_task.relationship_type = "PRODUCES"

def validate_task_object(task, operation_name="operation"):
    """Validate that a task object is valid for operations"""
    if not task:
        raise ValueError(f"Task is None for {operation_name}")
    
    if not hasattr(task, 'is_a') or not task.is_a('IfcTask'):
        raise ValueError(f"Object is not an IfcTask for {operation_name}")
    
    return True

# These functions are duplicated - removed to avoid conflicts

def load_active_task_properties() -> None:
    """Load properties for the active task"""
    props = props_sequence.get_work_schedule_props()
    if not props.active_task_id:
        return
    
    import bonsai.tool as tool
    task = tool.Ifc.get().by_id(props.active_task_id)
    if not task:
        return
    
    # Load task attributes
    load_task_attributes(task)
    
    # Load task time if available
    task_time = get_task_time(task)
    if task_time:
        load_task_time_attributes(task_time)
    
    # Load task resources
    load_task_resources(task)
    
    # Load inputs and outputs
    inputs = get_task_inputs(task)
    outputs = get_task_outputs(task)
    load_task_inputs(inputs)
    load_task_outputs(outputs)

# This function is duplicated - removed to avoid conflicts

def get_direct_nested_tasks(task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
    """Get direct nested tasks (not recursive)"""
    nested_tasks = []
    
    if hasattr(task, 'IsNestedBy'):
        for rel in task.IsNestedBy:
            for nested_task in rel.RelatedObjects:
                if nested_task.is_a('IfcTask'):
                    nested_tasks.append(nested_task)
    
    return nested_tasks

def get_direct_task_outputs(task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
    """Get direct outputs of a task (products it produces)"""
    outputs = []
    
    # Check IfcRelAssignsToProcess where task produces products  
    for rel in getattr(task, 'OperatesOn', []):
        for related_object in rel.RelatedObjects:
            if related_object.is_a('IfcProduct'):
                outputs.append(related_object)
    
    return outputs

def enable_editing_work_calendar_times(work_calendar: ifcopenshell.entity_instance) -> None:
    """Enable editing work calendar times"""
    props = props_sequence.get_work_calendar_props()
    props.active_work_calendar_id = work_calendar.id()
    props.editing_type = "WORKTIMES"

def load_work_calendar_attributes(work_calendar: ifcopenshell.entity_instance) -> dict:
    """Load work calendar attributes into UI"""
    import bonsai.bim.helper
    
    props = props_sequence.get_work_calendar_props()
    props.work_calendar_attributes.clear()
    return bonsai.bim.helper.import_attributes(work_calendar, props.work_calendar_attributes)

def enable_editing_work_calendar(work_calendar: ifcopenshell.entity_instance) -> None:
    """Enable editing work calendar"""
    props = props_sequence.get_work_calendar_props()
    props.active_work_calendar_id = work_calendar.id()
    props.editing_type = "ATTRIBUTES"

def disable_editing_work_calendar() -> None:
    """Disable editing work calendar"""
    props = props_sequence.get_work_calendar_props()
    props.active_work_calendar_id = 0

def get_work_calendar_attributes() -> dict:
    """Get work calendar attributes from UI"""
    import bonsai.bim.helper
    
    props = props_sequence.get_work_calendar_props()
    return bonsai.bim.helper.export_attributes(props.work_calendar_attributes)

def load_work_time_attributes(work_time: ifcopenshell.entity_instance) -> None:
    """Load work time attributes into UI"""
    import bonsai.bim.helper
    
    props = props_sequence.get_work_calendar_props()
    props.work_time_attributes.clear()
    bonsai.bim.helper.import_attributes(work_time, props.work_time_attributes)

def enable_editing_work_time(work_time: ifcopenshell.entity_instance) -> None:
    """Enable editing work time with recurrence pattern support"""
    def initialise_recurrence_components(props):
        if len(props.day_components) == 0:
            for i in range(0, 31):
                new = props.day_components.add()
                new.name = str(i + 1)
        if len(props.weekday_components) == 0:
            for d in ["M", "T", "W", "T", "F", "S", "S"]:
                new = props.weekday_components.add()
                new.name = d
        if len(props.month_components) == 0:
            for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]:
                new = props.month_components.add()
                new.name = m

    def load_recurrence_pattern_data(work_time, props):
        props.position = 0
        props.interval = 0
        props.occurrences = 0
        props.start_time = ""
        props.end_time = ""
        
        for component in props.day_components:
            component.is_specified = False
        for component in props.weekday_components:
            component.is_specified = False
        for component in props.month_components:
            component.is_specified = False
            
        if not work_time.RecurrencePattern:
            return
            
        recurrence_pattern = work_time.RecurrencePattern
        for attribute in ["Position", "Interval", "Occurrences"]:
            if getattr(recurrence_pattern, attribute):
                setattr(props, attribute.lower(), getattr(recurrence_pattern, attribute))
                
        for component in recurrence_pattern.DayComponent or []:
            props.day_components[component - 1].is_specified = True
        for component in recurrence_pattern.WeekdayComponent or []:
            props.weekday_components[component - 1].is_specified = True
        for component in recurrence_pattern.MonthComponent or []:
            props.month_components[component - 1].is_specified = True

    props = props_sequence.get_work_calendar_props()
    initialise_recurrence_components(props)
    load_recurrence_pattern_data(work_time, props)
    props.active_work_time_id = work_time.id()
    props.editing_type = "WORKTIMES"

def get_work_time_attributes() -> dict:
    """Get work time attributes with date parsing"""
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    from bonsai.bim.helper import draw_attributes

    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        if "Start" in prop.name or "Finish" in prop.name:
            if prop.is_null:
                attributes[prop.name] = None
                return True
            attributes[prop.name] = bonsai.bim.helper.parse_datetime(prop.string_value)
            return True
        return False

    props = props_sequence.get_work_calendar_props()
    return bonsai.bim.helper.export_attributes(props.work_time_attributes, callback)

def get_recurrence_pattern_attributes(recurrence_pattern):
    """Get recurrence pattern attributes for work time"""
    props = props_sequence.get_work_calendar_props()
    attributes = {
        "Interval": props.interval if props.interval > 0 else None,
        "Occurrences": props.occurrences if props.occurrences > 0 else None,
    }
    
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
    
    if "Position" in applicable_data[recurrence_pattern.RecurrenceType]:
        attributes["Position"] = props.position if props.position != 0 else None
    if "DayComponent" in applicable_data[recurrence_pattern.RecurrenceType]:
        attributes["DayComponent"] = [i + 1 for i, c in enumerate(props.day_components) if c.is_specified]
    if "WeekdayComponent" in applicable_data[recurrence_pattern.RecurrenceType]:
        attributes["WeekdayComponent"] = [i + 1 for i, c in enumerate(props.weekday_components) if c.is_specified]
    if "MonthComponent" in applicable_data[recurrence_pattern.RecurrenceType]:
        attributes["MonthComponent"] = [i + 1 for i, c in enumerate(props.month_components) if c.is_specified]
    
    return attributes

def disable_editing_work_time() -> None:
    """Disable editing work time"""
    props = props_sequence.get_work_calendar_props()
    props.active_work_time_id = 0

def get_recurrence_pattern_times():
    """Get recurrence pattern times from UI"""
    from dateutil import parser
    from datetime import datetime
    
    props = props_sequence.get_work_calendar_props()
    try:
        start_time = parser.parse(props.start_time)
        end_time = parser.parse(props.end_time)
        return start_time, end_time
    except:
        return None

def reset_time_period() -> None:
    """Reset time period in UI"""
    props = props_sequence.get_work_calendar_props()
    props.start_time = ""
    props.end_time = ""

def get_active_work_time():
    """Get the active work time being edited"""
    import bonsai.tool as tool
    
    props = props_sequence.get_work_calendar_props()
    if not props.active_work_time_id:
        return None
    return tool.Ifc.get().by_id(props.active_work_time_id)

def enable_editing_task_calendar(task: ifcopenshell.entity_instance) -> None:
    """Enable editing task calendar"""
    props = props_sequence.get_work_schedule_props()
    props.active_task_id = task.id()
    props.editing_task_type = "CALENDAR"

def enable_editing_task_sequence() -> None:
    """Enable editing task sequence"""
    props = props_sequence.get_work_schedule_props()
    props.editing_task_type = "SEQUENCE"

def disable_editing_task_time() -> None:
    """Disable editing task time"""
    props = props_sequence.get_work_schedule_props()
    props.active_task_id = 0
    props.active_task_time_id = 0

def load_rel_sequence_attributes(rel_sequence: ifcopenshell.entity_instance) -> None:
    """Load relationship sequence attributes"""
    import bonsai.bim.helper
    
    props = props_sequence.get_work_schedule_props()
    props.sequence_attributes.clear()
    bonsai.bim.helper.import_attributes(rel_sequence, props.sequence_attributes)

def enable_editing_rel_sequence_attributes(rel_sequence: ifcopenshell.entity_instance) -> None:
    """Enable editing relationship sequence attributes"""
    props = props_sequence.get_work_schedule_props()
    props.active_sequence_id = rel_sequence.id()
    props.editing_sequence_type = "ATTRIBUTES"

def load_lag_time_attributes(lag_time: ifcopenshell.entity_instance) -> None:
    """Load lag time attributes"""
    import bonsai.bim.helper
    import ifcopenshell.util.date
    from typing import Any, Union, Literal
    from bonsai.bim.prop import Attribute
    
    def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
        if name == "LagValue":
            prop = props_sequence.get_work_schedule_props().lag_time_attributes.add()
            prop.name = name
            prop.is_null = data[name] is None
            prop.is_optional = False
            prop.data_type = "string"
            prop.string_value = (
                "" if prop.is_null else ifcopenshell.util.date.datetime2ifc(data[name].wrappedValue, "IfcDuration")
            )
            return True

    props = props_sequence.get_work_schedule_props()
    props.lag_time_attributes.clear()
    bonsai.bim.helper.import_attributes(lag_time, props.lag_time_attributes, callback)

def enable_editing_sequence_lag_time(rel_sequence: ifcopenshell.entity_instance) -> None:
    """Enable editing sequence lag time"""
    props = props_sequence.get_work_schedule_props()
    props.active_sequence_id = rel_sequence.id()
    props.editing_sequence_type = "LAG_TIME"

def get_rel_sequence_attributes() -> dict:
    """Get relationship sequence attributes"""
    import bonsai.bim.helper
    
    props = props_sequence.get_work_schedule_props()
    return bonsai.bim.helper.export_attributes(props.sequence_attributes)

def disable_editing_rel_sequence() -> None:
    """Disable editing relationship sequence"""
    props = props_sequence.get_work_schedule_props()
    props.active_sequence_id = 0

def get_lag_time_attributes() -> dict:
    """Get lag time attributes"""
    import bonsai.bim.helper
    
    props = props_sequence.get_work_schedule_props()
    return bonsai.bim.helper.export_attributes(props.lag_time_attributes)

def refresh_task_output_counts() -> None:
    """Refresh task output counts for UI display"""
    import bonsai.tool as tool
    import ifcopenshell.util.sequence
    
    try:
        tprops = props_sequence.get_task_tree_props()
    except Exception:
        return
        
    for item in getattr(tprops, "tasks", []):
        try:
            task = tool.Ifc.get().by_id(item.ifc_definition_id)
            count = len(ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)) if task else 0
            if hasattr(item, "outputs_count"):
                setattr(item, "outputs_count", count)
        except Exception:
            continue

def disable_selecting_deleted_task() -> None:
    """Disable selecting deleted task in UI"""
    props = props_sequence.get_work_schedule_props()
    if props.active_task_id not in [
        task.ifc_definition_id for task in props_sequence.get_task_tree_props().tasks
    ]:
        props.active_task_id = 0
        props.active_task_time_id = 0

def enable_editing_task_attributes(task: ifcopenshell.entity_instance) -> None:
    """Enable editing task attributes"""
    props = props_sequence.get_work_schedule_props()
    props.active_task_id = task.id()
    props.editing_task_type = "ATTRIBUTES"

def disable_editing_task() -> None:
    """Disable editing task"""
    props = props_sequence.get_work_schedule_props()
    props.active_task_id = 0
    props.active_task_time_id = 0
    props.editing_task_type = ""

def enable_editing_task_time(task: ifcopenshell.entity_instance) -> None:
    """Enable editing task time"""
    props = props_sequence.get_work_schedule_props()
    props.active_task_id = task.id()
    if task.TaskTime:
        props.active_task_time_id = task.TaskTime.id()
    props.editing_task_type = "TASKTIME"

def copy_work_schedule(work_schedule: ifcopenshell.entity_instance) -> None:
    """Creates a deep copy of the given work schedule, including all its tasks and relationships."""
    import ifcopenshell
    import ifcopenshell.api
    import ifcopenshell.util.sequence
    import ifcopenshell.guid
    import bonsai.tool as tool
    
    file = tool.Ifc.get()
    if not work_schedule or not file:
        print("Error: Invalid work schedule or IFC file.")
        return

    # Use the modern clone API if available
    try:
        import ifcopenshell.api.clone
        new_schedule = ifcopenshell.api.run("clone.clone_deep", file, element=work_schedule)
        original_name = getattr(work_schedule, "Name", "Unnamed Schedule")
        new_schedule.Name = f"Copy of {original_name}"
        print(f"Successfully copied schedule using modern clone.clone_deep API.")
        return new_schedule
    except (ImportError, ModuleNotFoundError) as e:
        print(f"clone.clone_deep not available. Falling back to manual copy.")
    except Exception as e:
        print(f"Error with clone.clone_deep. Falling back to manual copy: {e}")

    # Fallback: Manual deep copy
    def _create_entity_copy(ifc_file, entity: ifcopenshell.entity_instance):
        """Creates a copy of an IFC entity with a new unique ID."""
        if not entity:
            return None
        try:
            entity_info = entity.get_info()
            
            # Remove fields that must be unique for the new entity
            if 'id' in entity_info:
                del entity_info['id']
            if 'GlobalId' in entity_info:
                entity_info['GlobalId'] = ifcopenshell.guid.new()
            
            # Create new entity with copied data
            new_entity = ifc_file.create_entity(entity.is_a(), **entity_info)
            print(f"✅ Copied entity: '{getattr(entity, 'Name', 'Unnamed')}' - Original ID: {entity.id()} → New ID: {new_entity.id()}")
            return new_entity
            
        except Exception as e:
            print(f"❌ Error copying entity {entity} - {e}")
            return None

    def _copy_task_recursive(original_task, new_parent=None):
        """Recursively copy tasks and their nested structure."""
        try:
            # Copy the task itself
            new_task = _create_entity_copy(file, original_task)
            if not new_task:
                return None

            # Handle task time if it exists
            if original_task.TaskTime:
                new_task_time = _create_entity_copy(file, original_task.TaskTime)
                if new_task_time:
                    new_task.TaskTime = new_task_time

            # Copy nested tasks
            nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(original_task)
            for nested_task in nested_tasks:
                _copy_task_recursive(nested_task, new_task)

            return new_task

        except Exception as e:
            print(f"❌ Error in recursive task copy: {e}")
            return None

    try:
        # Create copy of the work schedule
        new_schedule = _create_entity_copy(file, work_schedule)
        if not new_schedule:
            print("❌ Failed to create work schedule copy")
            return None

        # Copy all root tasks
        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
        for task in root_tasks:
            _copy_task_recursive(task)

        print(f"✅ Successfully copied work schedule: {new_schedule.Name}")
        return new_schedule

    except Exception as e:
        print(f"❌ Error in work schedule copy: {e}")
        return None

def load_work_schedule_attributes(work_schedule: ifcopenshell.entity_instance) -> None:
    """Load work schedule attributes into UI"""
    import bonsai.tool as tool
    import bonsai.bim.helper
    from typing import Any, Union, Literal
    from bonsai.bim.prop import Attribute
    
    schema = tool.Ifc.schema()
    entity = schema.declaration_by_name("IfcWorkSchedule").as_entity()
    assert entity

    def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
        if name in ["CreationDate", "StartTime", "FinishTime"]:
            assert prop
            prop.string_value = "" if prop.is_null else str(data[name])
            return True
        else:
            attr = entity.attribute_by_index(entity.attribute_index(name))
            if not attr.type_of_attribute()._is("IfcDuration"):
                return
            assert prop
            from . import utils_sequence
            utils_sequence.add_duration_prop(prop, data[name])

    props = props_sequence.get_work_schedule_props()
    props.work_schedule_attributes.clear()
    bonsai.bim.helper.import_attributes(work_schedule, props.work_schedule_attributes, callback)

def enable_editing_work_plan_schedules(work_plan) -> None:
    """Enable editing work plan schedules"""
    if work_plan:
        props = props_sequence.get_work_plan_props()
        props.active_work_plan_id = work_plan.id()
        props.editing_type = "SCHEDULES"

def load_work_plan_attributes(work_plan: ifcopenshell.entity_instance) -> None:
    """Load work plan attributes"""
    import bonsai.bim.helper
    from typing import Any, Union, Literal
    from bonsai.bim.prop import Attribute
    
    def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
        if name in ["CreationDate", "StartTime", "FinishTime"]:
            assert prop
            prop.string_value = "" if prop.is_null else str(data[name])
            return True
    
    props = props_sequence.get_work_plan_props()
    props.work_plan_attributes.clear()
    bonsai.bim.helper.import_attributes(work_plan, props.work_plan_attributes, callback)

def enable_editing_work_plan(work_plan) -> None:
    """Enable editing work plan"""
    if work_plan:
        props = props_sequence.get_work_plan_props()
        props.active_work_plan_id = work_plan.id()
        props.editing_type = "ATTRIBUTES"

def disable_editing_work_plan() -> None:
    """Disable editing work plan"""
    props = props_sequence.get_work_plan_props()
    props.active_work_plan_id = 0

def get_work_plan_attributes() -> dict:
    """Get work plan attributes"""
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    from bonsai.bim.helper import draw_attributes
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        if "Date" in prop.name or "Time" in prop.name:
            if prop.is_null:
                attributes[prop.name] = None
                return True
            attributes[prop.name] = bonsai.bim.helper.parse_datetime(prop.string_value)
            return True
        elif prop.special_type == "DURATION":
            from . import utils_sequence
            return utils_sequence.export_duration_prop(prop, attributes)
        return False

    props = props_sequence.get_work_plan_props()
    return bonsai.bim.helper.export_attributes(props.work_plan_attributes, callback)


def _add(total, new_value):
    """Internal utility method to safely add values"""
    if total is None:
        return new_value
    if new_value is None:
        return total
    return total + new_value


def get_all_tasks_recursive_target(work_schedule=None, flatten=True):
    """Recursively get all tasks from work schedule with optional flattening"""
    if work_schedule is None:
        work_schedule = get_active_work_schedule()
    
    if not work_schedule:
        return []
    
    all_tasks = []
    
    def collect_tasks_recursive(task_list):
        """Recursively collect all tasks"""
        for task in task_list:
            all_tasks.append(task)
            # Get nested tasks if any
            nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
            if nested_tasks:
                collect_tasks_recursive(nested_tasks)
    
    # Get root level tasks
    root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
    collect_tasks_recursive(root_tasks)
    
    if flatten:
        return all_tasks
    else:
        # Return structured hierarchy (not implemented in original)
        return all_tasks
