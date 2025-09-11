# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>, 2025 Federico Eraso <feraso@svisuals.net>
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
import ifcopenshell.util.element
import json
import re
from typing import Any, List, Optional, Union, TYPE_CHECKING

from .props_sequence import PropsSequence
import bonsai.bim.module.sequence.helper as helper
import bonsai.tool as tool
import bonsai.bim.helper

if TYPE_CHECKING:
    from bonsai.bim.prop import Attribute

class TaskManagementSequence(PropsSequence):
    """Maneja la lógica del árbol de tareas, filtros, ordenamiento y datos ICOM."""


    @classmethod
    def apply_selection_from_checkboxes(cls):
        """
        Selecciona en el viewport los objetos 3D de todas las tareas marcadas con el checkbox.
        Deselecciona todo lo demás.
        Selects the 3D objects of all tasks marked with the checkbox in the viewport. Deselects everything else.
        """
        try:
            tprops = cls.get_task_tree_props()
            if not tprops:
                return

            # 1. Obtener todas las tareas que están marcadas con el checkbox
            # 1. Get all tasks that are marked with the checkbox
            selected_tasks_pg = [task_pg for task_pg in tprops.tasks if getattr(task_pg, 'is_selected', False)]

            # 2. Deselect everything in the scene
            bpy.ops.object.select_all(action='DESELECT')

            # 3. If no tasks are marked, finish
            if not selected_tasks_pg:
                return

            # 4. Collect all objects to select
            objects_to_select = []
            for task_pg in selected_tasks_pg:
                task_ifc = tool.Ifc.get().by_id(task_pg.ifc_definition_id)
                if not task_ifc:
                    continue
                
                outputs = cls.get_task_outputs(task_ifc)
                for product in outputs:
                    obj = tool.Ifc.get_object(product)
                    if obj:
                        objects_to_select.append(obj)

            # 5. Select all collected objects
            if objects_to_select:
                for obj in objects_to_select:
                    obj.select_set(True)
                # Make the first object in the list the active one
                bpy.context.view_layer.objects.active = objects_to_select[0]

        except Exception as e:
            print(f"Error applying selection from checkboxes: {e}")


    @classmethod
    def get_selected_task_ids(cls):
        """Returns list of task IDs that are currently selected/checked in the UI"""
        try:
            tprops = cls.get_task_tree_props()
            if not tprops:
                return []
            
            selected_ids = []
            for task_pg in tprops.tasks:
                if getattr(task_pg, 'is_selected', False):
                    try:
                        task_id = int(task_pg.ifc_definition_id)
                        selected_ids.append(task_id)
                    except (ValueError, AttributeError):
                        continue
            
            return selected_ids
        except Exception as e:
            print(f"❌ Error getting selected task IDs: {e}")
            return []


    @classmethod
    def load_task_tree(cls, work_schedule: ifcopenshell.entity_instance) -> None:
        props = cls.get_task_tree_props()

        props.tasks.clear()
        schedule_props = cls.get_work_schedule_props()
        cls.contracted_tasks = json.loads(schedule_props.contracted_tasks)

        # 1. Obtener TODAS las tareas raíz, como antes
        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
        print(f"🔍 DEBUG load_task_tree: Tareas raíz encontradas: {len(root_tasks)}")
        
        # 2. APLICAR FILTRO: Pasar la lista de tareas raíz a nuestra nueva función de filtrado
        filtered_root_tasks = cls.get_filtered_tasks(root_tasks)
        print(f"🔍 DEBUG load_task_tree: Tareas después de filtro: {len(filtered_root_tasks)}")

        # 3. Ordenar solo las tareas que pasaron el filtro
        related_objects_ids = cls.get_sorted_tasks_ids(filtered_root_tasks)
        print(f"🔍 DEBUG load_task_tree: IDs después de ordenar: {len(related_objects_ids)}")
        
        # 4. Crear los elementos de la UI solo para las tareas filtradas y ordenadas
        for related_object_id in related_objects_ids:
            cls.create_new_task_li(related_object_id, 0)
            
        print(f"🔍 DEBUG load_task_tree: Tareas finales en UI: {len(props.tasks)}")


    @classmethod
    def load_task_properties(cls, task: Optional[ifcopenshell.entity_instance] = None) -> None:
        print(f"🔍 DEBUG load_task_properties: Iniciando carga de propiedades")
        props = cls.get_work_schedule_props()
        task_props = cls.get_task_tree_props()
        print(f"🔍 DEBUG load_task_properties: Encontradas {len(task_props.tasks)} tareas en UI")
        tasks_with_visual_bar = cls.get_task_bar_list()
        props.is_task_update_enabled = False

        for i, item in enumerate(task_props.tasks):
            task = tool.Ifc.get().by_id(item.ifc_definition_id)
            item.name = task.Name or "Unnamed"
            item.identification = task.Identification or "XXX"
            if i < 5:  # Solo mostrar las primeras 5 para no saturar el log
                print(f"🔍 DEBUG: Tarea {i}: ID={item.ifc_definition_id}, Name='{task.Name}' → item.name='{item.name}'")
            item.has_bar_visual = item.ifc_definition_id in tasks_with_visual_bar
            if props.highlighted_task_id:
                item.is_predecessor = props.highlighted_task_id in [
                    rel.RelatedProcess.id() for rel in task.IsPredecessorTo
                ]
                item.is_successor = props.highlighted_task_id in [
                    rel.RelatingProcess.id() for rel in task.IsSuccessorFrom
                ]
            calendar = ifcopenshell.util.sequence.derive_calendar(task)
            if ifcopenshell.util.sequence.get_calendar(task):
                item.calendar = calendar.Name or "Unnamed" if calendar else ""
            else:
                item.calendar = ""
                item.derived_calendar = calendar.Name or "Unnamed" if calendar else ""

            # Load all date pairs using the helper
            cls._load_task_date_properties(item, task, "Schedule")
            cls._load_task_date_properties(item, task, "Actual")
            cls._load_task_date_properties(item, task, "Early")
            cls._load_task_date_properties(item, task, "Late")

            # Duration logic (remains the same, based on Schedule dates)
            task_time = task.TaskTime
            if task_time and task_time.ScheduleDuration:
                item.duration = str(ifcopenshell.util.date.readable_ifc_duration(task_time.ScheduleDuration))
            else:
                derived_start = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
                derived_finish = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
                if derived_start and derived_finish:
                    derived_duration = ifcopenshell.util.sequence.count_working_days(
                        derived_start, derived_finish, calendar
                    )
                    item.derived_duration = str(ifcopenshell.util.date.readable_ifc_duration(f"P{derived_duration}D"))
                else:
                    item.derived_duration = ""
                item.duration = "-"

        # After processing all tasks, refresh the Outputs count so UI stays accurate.
        try:
            cls.refresh_task_output_counts()
        except Exception:
            # Be defensive; never break UI loading if counting fails.
            pass

        props.is_task_update_enabled = True


    @classmethod
    def refresh_task_output_counts(cls) -> None:
        """
        Recalcula y guarda (si existe) el conteo de Outputs por tarea en el árbol actual.
        Es seguro: si los atributos/propiedades no existen, simplemente no hace nada.
        """
        try:
            tprops = cls.get_task_tree_props()
        except Exception:
            return
        try:
            from bonsai import tool as _tool
            import ifcopenshell  # type: ignore
        except Exception:
            # Si los módulos no están disponibles en este contexto, salimos silenciosamente.
            return
        for item in getattr(tprops, "tasks", []):
            try:
                task = _tool.Ifc.get().by_id(item.ifc_definition_id)
                count = len(ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)) if task else 0
                if hasattr(item, "outputs_count"):
                    # Algunas builds definen este atributo en el item del árbol
                    setattr(item, "outputs_count", count)
                # En otros casos el recuento se utiliza de forma dinámica (p.ej. en columnas),
                # por lo que no es necesario almacenar nada; el cálculo anterior actúa como verificación.
            except Exception:
                # Nunca interrumpir la UI por errores de tareas individuales.
                continue

    @classmethod
    def create_new_task_li(cls, related_object_id: int, level_index: int) -> None:
        task = tool.Ifc.get().by_id(related_object_id)
        props = cls.get_task_tree_props()
        new = props.tasks.add()
        new.ifc_definition_id = related_object_id
        new.is_expanded = related_object_id not in cls.contracted_tasks
        new.level_index = level_index
        if task.IsNestedBy:
            new.has_children = True
            if new.is_expanded:
                for related_object_id in cls.get_sorted_tasks_ids(ifcopenshell.util.sequence.get_nested_tasks(task)):
                    cls.create_new_task_li(related_object_id, level_index + 1)


    @classmethod
    def _load_task_date_properties(cls, item, task, date_type_prefix):
        """Helper to load a pair of dates (e.g., ScheduleStart/Finish) for a task item."""
        prop_prefix = date_type_prefix.lower()
        start_attr, finish_attr = f"{date_type_prefix}Start", f"{date_type_prefix}Finish"

        # Map 'schedule' to the old property names for compatibility
        if prop_prefix == "schedule":
            item_start, item_finish = "start", "finish"
        else:
            item_start, item_finish = f"{prop_prefix}_start", f"{prop_prefix}_finish"

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


    @classmethod
    def get_sorted_tasks_ids(cls, tasks: list[ifcopenshell.entity_instance]) -> list[int]:
        props = cls.get_work_schedule_props()

        def get_sort_key(task):
            # Sorting only applies to actual tasks, not the WBS
            # for rel in task.IsNestedBy:
            #     for object in rel.RelatedObjects:
            #         if object.is_a("IfcTask"):
            #             return "0000000000" + (task.Identification or "")
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


    @classmethod
    def get_filtered_tasks(cls, tasks: list[ifcopenshell.entity_instance]) -> list[ifcopenshell.entity_instance]:
        """
        Filtra una lista de tareas (y sus hijos) basándose en las reglas activas.
        Si una tarea padre no cumple el filtro, sus hijos tampoco se mostrarán.
        """
        props = cls.get_work_schedule_props()
        try:
            filter_rules = [r for r in getattr(props, "filters").rules if r.is_active]
            print(f"🔍 DEBUG get_filtered_tasks: Reglas de filtro activas: {len(filter_rules)}")
        except Exception as e:
            print(f"🔍 DEBUG get_filtered_tasks: Error accediendo filtros: {e}")
            return tasks

        if not filter_rules:
            print(f"🔍 DEBUG get_filtered_tasks: Sin filtros activos, retornando todas las tareas: {len(tasks)}")
            return tasks

        filter_logic_is_and = getattr(props.filters, "logic", 'AND') == 'AND'
        
        def get_task_value(task, column_identifier):
            """Función auxiliar mejorada para obtener el valor de una columna para una tarea."""
            if not task or not column_identifier:
                return None
            
            column_name = column_identifier.split('||')[0]

            if column_name == "Special.OutputsCount":
                try:
                    # Usa la función de utilidad de ifcopenshell para obtener los outputs
                    return len(ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False))
                except Exception:
                    return 0

            if column_name in ("Special.VarianceStatus", "Special.VarianceDays"):
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
            """Comprueba si una única tarea cumple con el conjunto de filtros."""
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
                            task_date = helper.parse_datetime(str(task_value))
                            rule_date = helper.parse_datetime(rule.value_string)
                            if task_date and rule_date:
                                if op == 'EQUALS': match = task_date.date() == rule_date.date()
                                elif op == 'NOT_EQUALS': match = task_date.date() != rule_date.date()
                                elif op == 'GREATER': match = task_date > rule_date
                                elif op == 'LESS': match = task_date < rule_date
                                elif op == 'GTE': match = task_date >= rule_date
                                elif op == 'LTE': match = task_date <= rule_date
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
            nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
            filtered_children = cls.get_filtered_tasks(nested_tasks) if nested_tasks else []

            if task_matches_filters(task) or len(filtered_children) > 0:
                filtered_list.append(task)
                
        return filtered_list


    @classmethod
    def expand_task(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        contracted_tasks = json.loads(props.contracted_tasks)
        contracted_tasks.remove(task.id())
        props.contracted_tasks = json.dumps(contracted_tasks)

    @classmethod
    def expand_all_tasks(cls) -> None:
        props = cls.get_work_schedule_props()
        props.contracted_tasks = json.dumps([])

    @classmethod
    def contract_all_tasks(cls) -> None:
        props = cls.get_work_schedule_props()
        tprops = cls.get_task_tree_props()
        contracted_tasks = json.loads(props.contracted_tasks)
        for task_item in tprops.tasks:
            if task_item.is_expanded:
                contracted_tasks.append(task_item.ifc_definition_id)
        props.contracted_tasks = json.dumps(contracted_tasks)

    @classmethod
    def disable_selecting_deleted_task(cls) -> None:
        props = cls.get_work_schedule_props()
        if props.active_task_id not in [
            task.ifc_definition_id for task in cls.get_task_tree_props().tasks
        ]:  # Task was deleted
            props.active_task_id = 0
            props.active_task_time_id = 0

    @classmethod
    def contract_task(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        contracted_tasks = json.loads(props.contracted_tasks)
        contracted_tasks.append(task.id())
        props.contracted_tasks = json.dumps(contracted_tasks)


    @classmethod
    def update_task_ICOM(cls, task: Union[ifcopenshell.entity_instance, None]) -> None:
        """Refreshes the ICOM data (Outputs, Inputs, Resources) of the panel for the active task.
        If there is no task, it clears the lists to avoid remnants of the previous task."""
        props = cls.get_work_schedule_props()
        if task:
            # Outputs
            outputs = cls.get_task_outputs(task) or []
            cls.load_task_outputs(outputs)
            # Inputs
            inputs = cls.get_task_inputs(task) or []
            cls.load_task_inputs(inputs)
            # Resources
            cls.load_task_resources(task)
        else:
            props.task_outputs.clear()
            props.task_inputs.clear()
            props.task_resources.clear()


    @classmethod
    def load_task_resources(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        rprops = tool.Resource.get_resource_props()
        props.task_resources.clear()
        rprops.is_resource_update_enabled = False
        for resource in cls.get_task_resources(task) or []:
            new = props.task_resources.add()
            new.ifc_definition_id = resource.id()
            new.name = resource.Name or "Unnamed"
            new.schedule_usage = resource.Usage.ScheduleUsage or 0 if resource.Usage else 0
        rprops.is_resource_update_enabled = True


    @classmethod
    def get_task_inputs(cls, task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
        props = cls.get_work_schedule_props()
        is_deep = props.show_nested_inputs
        return ifcopenshell.util.sequence.get_task_inputs(task, is_deep)

    @classmethod
    def get_task_outputs(cls, task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
        props = cls.get_work_schedule_props()
        is_deep = props.show_nested_outputs
        return ifcopenshell.util.sequence.get_task_outputs(task, is_deep)

    @classmethod
    def get_task_resources(
        cls, task: Union[ifcopenshell.entity_instance, None]
    ) -> Union[list[ifcopenshell.entity_instance], None]:
        if not task:
            return
        props = cls.get_work_schedule_props()
        is_deep = props.show_nested_resources
        return ifcopenshell.util.sequence.get_task_resources(task, is_deep)

    @classmethod
    def load_task_inputs(cls, inputs: list[ifcopenshell.entity_instance]) -> None:
        props = cls.get_work_schedule_props()
        props.task_inputs.clear()
        for input in inputs:
            new = props.task_inputs.add()
            new.ifc_definition_id = input.id()
            new.name = input.Name or "Unnamed"

    @classmethod
    def load_task_outputs(cls, outputs: list[ifcopenshell.entity_instance]) -> None:
        props = cls.get_work_schedule_props()
        props.task_outputs.clear()
        if outputs:
            for output in outputs:
                new = props.task_outputs.add()
                new.ifc_definition_id = output.id()
                new.name = output.Name or "Unnamed"

    @classmethod
    def get_checked_tasks(cls) -> list[ifcopenshell.entity_instance]:
        return [
            tool.Ifc.get().by_id(task.ifc_definition_id) for task in cls.get_task_tree_props().tasks if task.is_selected
        ] or []

    @classmethod
    def get_highlighted_task(cls) -> Union[ifcopenshell.entity_instance, None]:
        tasks = cls.get_task_tree_props().tasks
        props = cls.get_work_schedule_props()
        if len(tasks) and len(tasks) > props.active_task_index:
            return tool.Ifc.get().by_id(tasks[props.active_task_index].ifc_definition_id)

    @classmethod
    def go_to_task(cls, task):
        props = cls.get_work_schedule_props()

        def get_ancestor_ids(task):
            ids = []
            for rel in task.Nests or []:
                ids.append(rel.RelatingObject.id())
                ids.extend(get_ancestor_ids(rel.RelatingObject))
            return ids

        contracted_tasks = json.loads(props.contracted_tasks)
        for ancestor_id in get_ancestor_ids(task):
            if ancestor_id in contracted_tasks:
                contracted_tasks.remove(ancestor_id)
        props.contracted_tasks = json.dumps(contracted_tasks)

        work_schedule = cls.get_active_work_schedule()
        cls.load_task_tree(work_schedule)
        cls.load_task_properties()

        task_props = cls.get_task_tree_props()
        expanded_tasks = [item.ifc_definition_id for item in task_props.tasks]
        props.active_task_index = expanded_tasks.index(task.id()) or 0


    @classmethod
    def get_direct_nested_tasks(cls, task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
        return ifcopenshell.util.sequence.get_nested_tasks(task)

    @classmethod
    def get_direct_task_outputs(cls, task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
        return ifcopenshell.util.sequence.get_direct_task_outputs(task)

    @classmethod
    def enable_editing_task_calendar(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_task_id = task.id()
        props.editing_task_type = "CALENDAR"


    @classmethod
    def enable_editing_task_sequence(cls) -> None:
        props = cls.get_work_schedule_props()
        props.editing_task_type = "SEQUENCE"

    @classmethod
    def disable_editing_task_time(cls) -> None:
        props = cls.get_work_schedule_props()
        props.active_task_id = 0
        props.active_task_time_id = 0

    @classmethod
    def load_rel_sequence_attributes(cls, rel_sequence: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.sequence_attributes.clear()
        bonsai.bim.helper.import_attributes(rel_sequence, props.sequence_attributes)

    @classmethod
    def enable_editing_rel_sequence_attributes(cls, rel_sequence: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_sequence_id = rel_sequence.id()
        props.editing_sequence_type = "ATTRIBUTES"

    @classmethod
    def load_lag_time_attributes(cls, lag_time: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()

        def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
            if name == "LagValue":
                prop = props.lag_time_attributes.add()
                prop.name = name
                prop.is_null = data[name] is None
                prop.is_optional = False
                prop.data_type = "string"
                prop.string_value = (
                    "" if prop.is_null else ifcopenshell.util.date.datetime2ifc(data[name].wrappedValue, "IfcDuration")
                )
                return True

        props.lag_time_attributes.clear()
        bonsai.bim.helper.import_attributes(lag_time, props.lag_time_attributes, callback)

    @classmethod
    def enable_editing_sequence_lag_time(cls, rel_sequence: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_sequence_id = rel_sequence.id()
        props.editing_sequence_type = "LAG_TIME"

    @classmethod
    def get_rel_sequence_attributes(cls) -> dict[str, Any]:
        props = cls.get_work_schedule_props()
        return bonsai.bim.helper.export_attributes(props.sequence_attributes)

    @classmethod
    def disable_editing_rel_sequence(cls) -> None:
        props = cls.get_work_schedule_props()
        props.active_sequence_id = 0

    @classmethod
    def get_lag_time_attributes(cls) -> dict[str, Any]:
        props = cls.get_work_schedule_props()
        return bonsai.bim.helper.export_attributes(props.lag_time_attributes)

    @classmethod
    def add_task_column(cls, column_type: str, name: str, data_type: str) -> None:
        props = cls.get_work_schedule_props()
        new = props.columns.add()
        new.name = f"{column_type}.{name}"
        new.data_type = data_type

    @classmethod
    def setup_default_task_columns(cls) -> None:
        props = cls.get_work_schedule_props()
        props.columns.clear()
        default_columns = ["ScheduleStart", "ScheduleFinish", "ScheduleDuration"]
        for item in default_columns:
            new = props.columns.add()
            new.name = f"IfcTaskTime.{item}"
            new.data_type = "string"

    @classmethod
    def remove_task_column(cls, name: str) -> None:
        props = cls.get_work_schedule_props()
        props.columns.remove(props.columns.find(name))
        if props.sort_column == name:
            props.sort_column = ""

    @classmethod
    def set_task_sort_column(cls, column: str) -> None:
        props = cls.get_work_schedule_props()
        props.sort_column = column

    
































   
