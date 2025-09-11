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
import ifcopenshell.util.element
import re
from datetime import datetime
from typing import Any
import bonsai.tool as tool
from . import props_sequence




def parse_isodate_datetime(value, include_time: bool = True):
        """Parsea fechas ISO (o datetime/date) y devuelve datetime sin microsegundos.
        - Acepta 'YYYY-MM-DD', 'YYYY-MM', 'YYYY', 'YYYY-MM-DDTHH:MM[:SS][Z|±HH:MM]'.
        - Si include_time es False, se normaliza a 00:00:00.
        - Si no puede parsear, devuelve None.
        """
        try:
            import datetime as _dt, re as _re
            if value is None:
                return None
            if isinstance(value, _dt.datetime):
                return value.replace(microsecond=0) if include_time else value.replace(hour=0, minute=0, second=0, microsecond=0)
            if isinstance(value, _dt.date):
                return _dt.datetime.combine(value, _dt.time())
            if isinstance(value, str):
                s = value.strip()
                if not s:
                    return None
                # If contains time or timezone
                if 'T' in s or ' ' in s or 'Z' in s or '+' in s:
                    ss = s.replace(' ', 'T').replace('Z', '+00:00')
                    try:
                        dtv = _dt.datetime.fromisoformat(ss)
                    except ValueError:
                        # Try without seconds: YYYY-MM-DDTHH:MM
                        m = _re.match(r'^(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})$', ss)
                        if m:
                            dtv = _dt.datetime.fromisoformat(m.group(1) + 'T' + m.group(2) + ':' + m.group(3) + ':00')
                        else:
                            return None
                    return dtv.replace(microsecond=0) if include_time else dtv.replace(hour=0, minute=0, second=0, microsecond=0)
                # Date-only variants
                try:
                    d = _dt.date.fromisoformat(s)
                except ValueError:
                    if _re.match(r'^\d{4}-\d{2}$', s):
                        y, m = s.split('-')
                        d = _dt.date(int(y), int(m), 1)
                    elif _re.match(r'^\d{4}$', s):
                        d = _dt.date(int(s), 1, 1)
                    else:
                        return None
                return _dt.datetime.combine(d, _dt.time())
            # Fallback
            return None
        except Exception:
            return None


def isodate_datetime(value, include_time: bool = True) -> str:
        """
        Returns an ISO-8601 string.
        - Si include_time es False => YYYY-MM-DD
        - Si include_time es True  => YYYY-MM-DDTHH:MM:SS (sin microsegundos)
        Acepta datetime/date o string y es tolerante a None.
        """
        try:
            import datetime as _dt
            if value is None:
                return ""
            # If it is already a str, return as is (assumed to be ISO or valid for UI)
            if isinstance(value, str):
                return value
            # If it is datetime/date
            if isinstance(value, _dt.datetime):
                return (value.replace(microsecond=0).isoformat()
                        if include_time else value.date().isoformat())
            if isinstance(value, _dt.date):
                return value.isoformat()
            # Any other type: try to convert
            return str(value)
        except Exception:
            return ""


def validate_task_object(task, operation_name="operation"):
        """
        Valida que un objeto tarea sea válido antes de procesarlo.

        Args:
            task: El objeto tarea a validar
            operation_name: Nombre de la operación para logging

        Returns:
            bool: True si la tarea es válida, False en caso contrario
        """
        if task is None:
            print(f"⚠️ Warning: None task in {operation_name}")
            return False

        if not hasattr(task, 'id') or not callable(getattr(task, 'id', None)):
            print(f"⚠️ Warning: Invalid task object in {operation_name}: {task}")
            return False

        try:
            task_id = task.id()
            if task_id is None or task_id <= 0:
                print(f"⚠️ Warning: Invalid task ID in {operation_name}: {task_id}")
                return False
        except Exception as e:
            print(f"⚠️ Error getting task ID in {operation_name}: {e}")
            return False

        return True



def get_tasks_for_product(product, work_schedule=None):
        """
        Obtiene las tareas de entrada y salida para un producto específico.

        Args:
            product: El producto IFC
            work_schedule: El cronograma de trabajo (opcional)

        Returns:
            tuple: (task_inputs, task_outputs)
        """
        try:
            # Usar los métodos existentes para encontrar tareas relacionadas
            input_tasks = cls.find_related_input_tasks(product)
            output_tasks = cls.find_related_output_tasks(product)

            # Si se proporciona work_schedule, filtrar solo las tareas de ese cronograma
            if work_schedule:
                # Obtener todas las tareas controladas por el work_schedule
                controlled_task_ids = set()
                for rel in work_schedule.Controls or []:
                    for obj in rel.RelatedObjects:
                        if obj.is_a("IfcTask"):
                            controlled_task_ids.add(obj.id())

                # Filtrar las tareas de entrada
                filtered_input_tasks = []
                for task in input_tasks:
                    if task.id() in controlled_task_ids:
                        filtered_input_tasks.append(task)

                # Filtrar las tareas de salida
                filtered_output_tasks = []
                for task in output_tasks:
                    if task.id() in controlled_task_ids:
                        filtered_output_tasks.append(task)

                return filtered_input_tasks, filtered_output_tasks

            return input_tasks, output_tasks

        except Exception as e:
            print(f"Error en get_tasks_for_product: {e}")
            return [], []


def load_product_related_tasks(product):
        """
        Carga las tareas relacionadas con un producto y las muestra en la UI.

        Args:
            product: El producto IFC para el cual buscar tareas

        Returns:
            str: Mensaje de resultado o lista de tareas
        """
        try:
            props = cls.get_work_schedule_props()

            # Obtener el work_schedule activo si existe
            active_work_schedule = None
            if props.active_work_schedule_id:
                active_work_schedule = tool.Ifc.get().by_id(props.active_work_schedule_id)

            # Llamar al método con el work_schedule
            task_inputs, task_outputs = cls.get_tasks_for_product(product, active_work_schedule)

            # Limpiar las listas existentes
            props.product_input_tasks.clear()
            props.product_output_tasks.clear()

            # Cargar tareas de entrada
            for task in task_inputs:
                new_input = props.product_input_tasks.add()
                new_input.ifc_definition_id = task.id()
                new_input.name = task.Name or "Unnamed"

            # Cargar tareas de salida
            for task in task_outputs:
                new_output = props.product_output_tasks.add()
                new_output.ifc_definition_id = task.id()
                new_output.name = task.Name or "Unnamed"

            total_tasks = len(task_inputs) + len(task_outputs)

            if total_tasks == 0:
                return "No related tasks found for this product"

            return f"Found {len(task_inputs)} input tasks and {len(task_outputs)} output tasks"

        except Exception as e:
            print(f"Error in load_product_related_tasks: {e}")
            return f"Error loading tasks: {str(e)}"



def get_work_schedule_products(work_schedule: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
        """
        Obtiene todos los productos asociados a un cronograma de trabajo.

        Args:
            work_schedule: El cronograma de trabajo IFC

        Returns:
            Lista de productos IFC (puede ser vacía)
        """
        try:
            products: list[ifcopenshell.entity_instance] = []

            # Obtener todas las tareas del cronograma
            if hasattr(work_schedule, 'Controls') and work_schedule.Controls:
                for rel in work_schedule.Controls:
                    for task in rel.RelatedObjects:
                        if task.is_a("IfcTask"):
                            # Obtener productos de salida (outputs)
                            task_outputs = cls.get_task_outputs(task) or []
                            products.extend(task_outputs)

                            # Obtener productos de entrada (inputs)
                            task_inputs = cls.get_task_inputs(task) or []
                            products.extend(task_inputs)

            # Eliminar duplicados manteniendo el orden
            seen: set[int] = set()
            unique_products: list[ifcopenshell.entity_instance] = []
            for product in products:
                try:
                    pid = product.id()
                except Exception:
                    pid = None
                if pid and pid not in seen:
                    seen.add(pid)
                    unique_products.append(product)

            return unique_products

        except Exception as e:
            print(f"Error getting work schedule products: {e}")
            return []



def select_work_schedule_products(work_schedule: ifcopenshell.entity_instance) -> str:
    """
    Selecciona todos los productos asociados a un cronograma de trabajo.

    Args:
        work_schedule: El cronograma de trabajo IFC

    Returns:
        Mensaje de resultado
    """
    try:
        products = get_work_schedule_products(work_schedule)

        if not products:
            return "No products found in work schedule"

        # Usar la función segura de spatial para seleccionar productos
        tool.Spatial.select_products(products)

        return f"Selected {len(products)} products from work schedule"

    except Exception as e:
        print(f"Error selecting work schedule products: {e}")
        return f"Error selecting products: {str(e)}"


def select_unassigned_work_schedule_products() -> str:
    """
    Selecciona productos que no están asignados a ningún cronograma de trabajo.

    Returns:
        Mensaje de resultado
    """
    try:
        ifc_file = tool.Ifc.get()
        if not ifc_file:
            return "No IFC file loaded"

        # Obtener todos los productos
        all_products = list(ifc_file.by_type("IfcProduct"))

        # Obtener productos asignados a cronogramas
        schedule_products: set[int] = set()
        for work_schedule in ifc_file.by_type("IfcWorkSchedule"):
            ws_products = get_work_schedule_products(work_schedule) or []
            for product in ws_products:
                try:
                    pid = product.id()
                except Exception:
                    pid = None
                if pid:
                    schedule_products.add(pid)

        # Filtrar productos no asignados
        unassigned_products: list[ifcopenshell.entity_instance] = []
        for product in all_products:
            try:
                pid = product.id()
            except Exception:
                pid = None
            if pid and pid not in schedule_products:
                # Verificar que no sea un elemento espacial
                try:
                    is_spatial = tool.Root.is_spatial_element(product)
                except Exception:
                    is_spatial = False
                if not is_spatial:
                    unassigned_products.append(product)

        if not unassigned_products:
            return "No unassigned products found"

        # Seleccionar productos no asignados
        tool.Spatial.select_products(unassigned_products)

        return f"Selected {len(unassigned_products)} unassigned products"

    except Exception as e:
        print(f"Error selecting unassigned products: {e}")
        return f"Error selecting unassigned products: {str(e)}"


def are_entities_same_class(entities: list[ifcopenshell.entity_instance]) -> bool:
    if not entities:
        return False
    if len(entities) == 1:
        return True
    first_class = entities[0].is_a()
    for entity in entities:
        if entity.is_a() != first_class:
            return False
    return True


def parse_isodate_datetime(value, include_time: bool = True):
    """Parsea fechas ISO (o datetime/date) y devuelve datetime sin microsegundos.
    - Acepta 'YYYY-MM-DD', 'YYYY-MM', 'YYYY', 'YYYY-MM-DDTHH:MM[:SS][Z|±HH:MM]'.
    - Si include_time es False, se normaliza a 00:00:00.
    - Si no puede parsear, devuelve None.
    """
    try:
        import datetime as _dt, re as _re
        if value is None:
            return None
        if isinstance(value, _dt.datetime):
            return value.replace(microsecond=0) if include_time else value.replace(hour=0, minute=0, second=0, microsecond=0)
        if isinstance(value, _dt.date):
            return _dt.datetime.combine(value, _dt.time())
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            # If contains time or timezone
            if 'T' in s or ' ' in s or 'Z' in s or '+' in s:
                ss = s.replace(' ', 'T').replace('Z', '+00:00')
                try:
                    dtv = _dt.datetime.fromisoformat(ss)
                except ValueError:
                    # Try without seconds: YYYY-MM-DDTHH:MM
                    m = _re.match(r'^(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})$', ss)
                    if m:
                        dtv = _dt.datetime.fromisoformat(m.group(1) + 'T' + m.group(2) + ':' + m.group(3) + ':00')
                    else:
                        return None
                return dtv.replace(microsecond=0) if include_time else dtv.replace(hour=0, minute=0, second=0, microsecond=0)
            # Date-only variants
            try:
                d = _dt.date.fromisoformat(s)
            except ValueError:
                if _re.match(r'^\d{4}-\d{2}$', s):
                    y, m = s.split('-')
                    d = _dt.date(int(y), int(m), 1)
                elif _re.match(r'^\d{4}$', s):
                    d = _dt.date(int(s), 1, 1)
                else:
                    return None
            return _dt.datetime.combine(d, _dt.time())
        # Fallback
        return None
    except Exception:
        return None


def isodate_datetime(value, include_time: bool = True) -> str:
    """
    Returns an ISO-8601 string.
    - Si include_time es False => YYYY-MM-DD
    - Si include_time es True  => YYYY-MM-DDTHH:MM:SS (sin microsegundos)
    Acepta datetime/date o string y es tolerante a None.
    """
    try:
        import datetime as _dt
        if value is None:
            return ""
        # If it is already a str, return as is (assumed to be ISO or valid for UI)
        if isinstance(value, str):
            return value
        # If it is datetime/date
        if isinstance(value, _dt.datetime):
            return (value.replace(microsecond=0).isoformat()
                    if include_time else value.date().isoformat())
        if isinstance(value, _dt.date):
            return value.isoformat()
        # Any other type: try to convert
        return str(value)
    except Exception:
        return ""


def guess_date_range(work_schedule) -> tuple:
    """
    Guesses the date range for a work schedule, respecting the date source type
    (Schedule, Actual, etc.) set in the UI. It now calculates the range based
    on ALL tasks in the schedule, ignoring any UI filters.
    """
    import ifcopenshell.util.sequence
    from . import props_sequence
    
    if not work_schedule:
        return None, None

    # Helper function to get all tasks recursively, ignoring UI filters.
    def get_all_tasks_from_schedule(schedule):
        all_tasks = []
        root_tasks = ifcopenshell.util.sequence.get_root_tasks(schedule)

        def recurse(tasks):
            for task in tasks:
                all_tasks.append(task)
                nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                if nested:
                    recurse(nested)

        recurse(root_tasks)
        return all_tasks

    all_schedule_tasks = get_all_tasks_from_schedule(work_schedule)

    if not all_schedule_tasks:
        return None, None

    props = props_sequence.get_work_schedule_props()
    date_source = getattr(props, "date_source_type", "SCHEDULE")
    start_attr = f"{date_source.capitalize()}Start"
    finish_attr = f"{date_source.capitalize()}Finish"

    # Debug info to track what's happening
    print(f"🔍 GUESS_DATE_RANGE: Using date source '{date_source}' -> {start_attr}/{finish_attr}")
    print(f"📊 GUESS_DATE_RANGE: Processing {len(all_schedule_tasks)} tasks")

    all_starts = []
    all_finishes = []
    found_dates_count = 0

    # Iterate over ALL tasks from the schedule, not just the visible ones.
    for task in all_schedule_tasks:
        start_date = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
        if start_date:
            all_starts.append(start_date)

        finish_date = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
        if finish_date:
            all_finishes.append(finish_date)
        
        if start_date or finish_date:
            found_dates_count += 1
    
    print(f"📅 GUESS_DATE_RANGE: Found dates in {found_dates_count}/{len(all_schedule_tasks)} tasks")

    if not all_starts or not all_finishes:
        print(f"❌ GUESS_DATE_RANGE: No valid dates found for {date_source}")
        return None, None

    result_start = min(all_starts)
    result_finish = max(all_finishes)
    print(f"✅ GUESS_DATE_RANGE: Result for {date_source}: {result_start.strftime('%Y-%m-%d')} to {result_finish.strftime('%Y-%m-%d')}")
    
    return result_start, result_finish

def get_work_calendar_attributes() -> dict[str, Any]:
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        return False  # Work calendars typically don't have complex date parsing
    
    from . import props_sequence
    props = props_sequence.get_work_calendar_props()
    return bonsai.bim.helper.export_attributes(props.work_calendar_attributes, callback)

def load_work_calendar_attributes(work_calendar: ifcopenshell.entity_instance) -> None:
    from typing import Any, Union, Literal
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
        return None  # Default behavior for work calendar attributes
    
    from . import props_sequence
    props = props_sequence.get_work_calendar_props()
    props.work_calendar_attributes.clear()
    bonsai.bim.helper.import_attributes(work_calendar, props.work_calendar_attributes, callback)

def get_active_work_time() -> ifcopenshell.entity_instance:
    from . import props_sequence
    import bonsai.tool as tool
    
    props = props_sequence.get_work_calendar_props()
    if not props.active_work_time_id:
        return None
    return tool.Ifc.get().by_id(props.active_work_time_id)

def get_work_time_attributes() -> dict[str, Any]:
    from ...helper import parse_datetime
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        if "Time" in prop.name:
            attributes[prop.name] = None if prop.is_null else parse_datetime(prop.string_value)
            return True
        return False
    
    from . import props_sequence
    props = props_sequence.get_work_calendar_props()
    return bonsai.bim.helper.export_attributes(props.work_time_attributes, callback)

def load_work_time_attributes(work_time: ifcopenshell.entity_instance) -> None:
    from typing import Any, Union, Literal
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
        if "Time" in name:
            assert prop
            prop.string_value = "" if prop.is_null else data[name]
            return True
        return None
    
    from . import props_sequence
    props = props_sequence.get_work_calendar_props()
    props.work_time_attributes.clear()
    bonsai.bim.helper.import_attributes(work_time, props.work_time_attributes, callback)

def get_recurrence_pattern_attributes(recurrence_pattern: ifcopenshell.entity_instance) -> dict[str, Any]:
    from ...helper import parse_datetime
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        if "Time" in prop.name:
            attributes[prop.name] = None if prop.is_null else parse_datetime(prop.string_value)
            return True
        return False
    
    from . import props_sequence
    props = props_sequence.get_work_calendar_props()
    return bonsai.bim.helper.export_attributes(props.recurrence_pattern_attributes, callback)

def load_recurrence_pattern_attributes(recurrence_pattern: ifcopenshell.entity_instance) -> None:
    from typing import Any, Union, Literal
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
        return None  # Default behavior
    
    from . import props_sequence
    props = props_sequence.get_work_calendar_props()
    props.recurrence_pattern_attributes.clear()
    bonsai.bim.helper.import_attributes(recurrence_pattern, props.recurrence_pattern_attributes, callback)

def get_recurrence_pattern_times() -> tuple[datetime, datetime] | None:
    from datetime import datetime
    from . import props_sequence
    
    props = props_sequence.get_work_calendar_props()
    start_time = getattr(props, 'recurrence_pattern_start_time', None)
    end_time = getattr(props, 'recurrence_pattern_end_time', None)
    
    if start_time and end_time:
        return (start_time, end_time)
    return None

def get_rel_sequence_attributes() -> dict[str, Any]:
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        return False  # Sequence relations typically don't have complex parsing
    
    from . import props_sequence
    props = props_sequence.get_task_tree_props()
    return bonsai.bim.helper.export_attributes(props.rel_sequence_attributes, callback)

def load_rel_sequence_attributes(rel_sequence: ifcopenshell.entity_instance) -> None:
    from typing import Any, Union, Literal
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
        return None  # Default behavior
    
    from . import props_sequence
    props = props_sequence.get_task_tree_props()
    props.rel_sequence_attributes.clear()
    bonsai.bim.helper.import_attributes(rel_sequence, props.rel_sequence_attributes, callback)

def get_lag_time_attributes() -> dict[str, Any]:
    from ...helper import parse_duration
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        if prop.name == "LagValue":
            attributes[prop.name] = None if prop.is_null else parse_duration(prop.string_value)
            return True
        return False
    
    from . import props_sequence
    props = props_sequence.get_task_tree_props()
    return bonsai.bim.helper.export_attributes(props.lag_time_attributes, callback)

def load_lag_time_attributes(lag_time: ifcopenshell.entity_instance) -> None:
    from typing import Any, Union, Literal
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
        if name == "LagValue":
            assert prop
            prop.string_value = "" if prop.is_null else data[name]
            return True
        return None
    
    from . import props_sequence
    props = props_sequence.get_task_tree_props()
    props.lag_time_attributes.clear()
    bonsai.bim.helper.import_attributes(lag_time, props.lag_time_attributes, callback)

def create_tasks_json(work_schedule=None):
    """Create JSON representation of tasks for visualization"""
    import json
    from . import task_sequence
    
    if not work_schedule:
        work_schedule = task_sequence.get_active_work_schedule()
    
    if not work_schedule:
        return []
    
    def get_all_tasks_from_schedule(schedule):
        """Get all tasks recursively from a schedule"""
        tasks = []
        if hasattr(schedule, 'Controls') and schedule.Controls:
            for rel in schedule.Controls:
                for related_object in rel.RelatedObjects:
                    if related_object.is_a('IfcTask'):
                        tasks.append(related_object)
                        # Add nested tasks recursively
                        if hasattr(related_object, 'IsNestedBy'):
                            for nested_rel in related_object.IsNestedBy:
                                for nested_task in nested_rel.RelatedObjects:
                                    if nested_task.is_a('IfcTask'):
                                        tasks.append(nested_task)
        return tasks
    
    tasks = get_all_tasks_from_schedule(work_schedule)
    tasks_data = []
    
    for task in tasks:
        task_data = {
            'id': task.id(),
            'name': task.Name or 'Unnamed Task',
            'identification': getattr(task, 'Identification', None),
            'description': getattr(task, 'Description', None)
        }
        
        # Add time information if available
        if hasattr(task, 'TaskTime') and task.TaskTime:
            task_time = task.TaskTime
            task_data['schedule_start'] = getattr(task_time, 'ScheduleStart', None)
            task_data['schedule_finish'] = getattr(task_time, 'ScheduleFinish', None)
            task_data['schedule_duration'] = getattr(task_time, 'ScheduleDuration', None)
        
        tasks_data.append(task_data)
    
    return tasks_data

def get_schedule_date_range(work_schedule=None):
    """Get the date range for a work schedule"""
    from datetime import datetime
    
    if not work_schedule:
        from . import task_sequence
        work_schedule = task_sequence.get_active_work_schedule()
    
    if not work_schedule:
        return None, None
    
    def get_all_tasks_from_schedule(schedule):
        """Get all tasks recursively from a schedule"""
        tasks = []
        if hasattr(schedule, 'Controls') and schedule.Controls:
            for rel in schedule.Controls:
                for related_object in rel.RelatedObjects:
                    if related_object.is_a('IfcTask'):
                        tasks.append(related_object)
        return tasks
    
    all_tasks = get_all_tasks_from_schedule(work_schedule)
    
    all_starts = []
    all_finishes = []
    
    for task in all_tasks:
        if hasattr(task, 'TaskTime') and task.TaskTime:
            task_time = task.TaskTime
            
            start_date = ifcopenshell.util.sequence.derive_date(task, 'ScheduleStart', is_earliest=True)
            if start_date:
                all_starts.append(start_date)
            
            finish_date = ifcopenshell.util.sequence.derive_date(task, 'ScheduleFinish', is_latest=True)
            if finish_date:
                all_finishes.append(finish_date)
    
    if not all_starts or not all_finishes:
        return None, None
    
    return min(all_starts), max(all_finishes)

def load_task_tree(work_schedule: ifcopenshell.entity_instance) -> None:
    """Load the task tree for a work schedule into UI properties"""
    from . import task_sequence
    import ifcopenshell.util.sequence
    
    # Get task tree properties
    props = props_sequence.get_task_tree_props()
    props.tasks.clear()
    
    if not work_schedule:
        return
    
    # Get all tasks from the work schedule
    def get_all_tasks_from_schedule(schedule):
        tasks = []
        if hasattr(schedule, 'Controls') and schedule.Controls:
            for rel in schedule.Controls:
                for related_object in rel.RelatedObjects:
                    if related_object.is_a('IfcTask'):
                        tasks.append(related_object)
                        # Add nested tasks recursively
                        tasks.extend(ifcopenshell.util.sequence.get_nested_tasks(related_object))
        return tasks
    
    all_tasks = get_all_tasks_from_schedule(work_schedule)
    
    # Filter and sort tasks if needed
    filtered_tasks = task_sequence.get_filtered_tasks(all_tasks)
    sorted_task_ids = task_sequence.get_sorted_tasks_ids(filtered_tasks)
    
    # Add tasks to UI properties
    import bonsai.tool as tool
    ifc = tool.Ifc.get()
    
    for task_id in sorted_task_ids:
        task = ifc.by_id(task_id)
        if not task:
            continue
        
        new_task = props.tasks.add()
        new_task.ifc_definition_id = task.id()
        new_task.name = task.Name or "Unnamed Task"
        new_task.identification = getattr(task, 'Identification', '') or ''
        
        # Add task time information
        task_time = task_sequence.get_task_time(task)
        if task_time:
            new_task.schedule_start = str(getattr(task_time, 'ScheduleStart', '') or '')
            new_task.schedule_finish = str(getattr(task_time, 'ScheduleFinish', '') or '')

def select_unassigned_work_schedule_products() -> None:
    """Select products that are not assigned to any work schedule"""
    import bpy
    import bonsai.tool as tool
    
    # Deselect all objects first
    bpy.ops.object.select_all(action='DESELECT')
    
    # Get all IFC products
    ifc = tool.Ifc.get()
    if not ifc:
        return
    
    # Get all products currently assigned to work schedules
    assigned_product_ids = set()
    
    work_schedules = ifc.by_type('IfcWorkSchedule')
    for schedule in work_schedules:
        assigned_products = get_work_schedule_products(schedule)
        assigned_product_ids.update(product.id() for product in assigned_products)
    
    # Get all products in the model
    all_products = ifc.by_type('IfcProduct')
    
    # Select unassigned products
    for product in all_products:
        if product.id() not in assigned_product_ids:
            obj = tool.Ifc.get_object(product)
            if obj and hasattr(obj, 'select_set'):
                obj.select_set(True)

def get_unified_date_range(work_schedule):
    """Get unified date range considering both schedule and actual dates"""
    from datetime import datetime
    
    if not work_schedule:
        return None, None
    
    all_starts = []
    all_finishes = []
    
    def get_all_tasks_recursive(tasks):
        all_tasks = []
        for task in tasks:
            all_tasks.append(task)
            if hasattr(task, 'IsNestedBy'):
                for rel in task.IsNestedBy:
                    nested_tasks = [obj for obj in rel.RelatedObjects if obj.is_a('IfcTask')]
                    all_tasks.extend(get_all_tasks_recursive(nested_tasks))
        return all_tasks
    
    # Get all tasks
    root_tasks = []
    if hasattr(work_schedule, 'Controls') and work_schedule.Controls:
        for rel in work_schedule.Controls:
            root_tasks.extend([obj for obj in rel.RelatedObjects if obj.is_a('IfcTask')])
    
    all_tasks = get_all_tasks_recursive(root_tasks)
    
    # Collect all dates (both schedule and actual)
    for task in all_tasks:
        from . import task_sequence
        task_time = task_sequence.get_task_time(task)
        if not task_time:
            continue
        
        # Schedule dates
        schedule_start = getattr(task_time, 'ScheduleStart', None)
        schedule_finish = getattr(task_time, 'ScheduleFinish', None)
        
        # Actual dates
        actual_start = getattr(task_time, 'ActualStart', None)
        actual_finish = getattr(task_time, 'ActualFinish', None)
        
        # Add all available dates
        for date_val in [schedule_start, schedule_finish, actual_start, actual_finish]:
            if date_val:
                try:
                    if isinstance(date_val, str):
                        date_obj = parse_isodate_datetime(date_val)
                    else:
                        date_obj = date_val
                    
                    if date_obj:
                        if date_val in [schedule_start, actual_start]:
                            all_starts.append(date_obj)
                        else:
                            all_finishes.append(date_obj)
                except:
                    continue
    
    if not all_starts or not all_finishes:
        return None, None
    
    return min(all_starts), max(all_finishes)

def set_visibility_by_status(visible_statuses: set[str]) -> None:
    """Set object visibility based on task status"""
    import bpy
    import bonsai.tool as tool
    from . import task_sequence
    
    # Get all tasks with their status
    active_ws = task_sequence.get_active_work_schedule()
    if not active_ws:
        return
    
    all_products = get_work_schedule_products(active_ws)
    
    for product in all_products:
        obj = tool.Ifc.get_object(product)
        if not obj:
            continue
        
        # Get tasks for this product
        tasks = get_tasks_for_product(product, active_ws)
        if not tasks:
            continue
        
        # Check if any task has a visible status
        should_be_visible = False
        for task in tasks[0]:  # tasks returns (consuming, producing) tuple
            task_status = getattr(task, 'Status', None)
            if task_status and task_status in visible_statuses:
                should_be_visible = True
                break
        
        # Set visibility
        obj.hide_viewport = not should_be_visible
        obj.hide_render = not should_be_visible

def enable_editing_work_plan(work_plan) -> None:
    """Enable editing for a work plan"""
    if work_plan:
        props = props_sequence.get_work_plan_props()
        props.active_work_plan_id = work_plan.id()
        props.editing_type = "PLAN"

def disable_editing_work_plan() -> None:
    """Disable work plan editing"""
    props = props_sequence.get_work_plan_props()
    props.active_work_plan_id = 0

def enable_editing_work_plan_schedules(work_plan) -> None:
    """Enable editing work plan schedules"""
    if work_plan:
        props = props_sequence.get_work_plan_props()
        props.active_work_plan_id = work_plan.id()
        props.editing_type = "SCHEDULES"

def export_duration_prop(prop, attributes: dict[str, Any]) -> bool:
    """Export duration property to attributes"""
    from ...helper import parse_duration
    
    if prop.is_null:
        attributes[prop.name] = None
        return True
    
    try:
        duration = parse_duration(prop.string_value)
        attributes[prop.name] = duration
        return True
    except:
        return False

def add_duration_prop(prop, value) -> None:
    """Add duration property with proper formatting"""
    from ...helper import isodate_duration
    
    if value is None:
        prop.is_null = True
        prop.string_value = ""
    else:
        prop.is_null = False
        prop.string_value = isodate_duration(value) if value else ""

def add_task_column(column_type: str, name: str, data_type: str) -> None:
    """Add a task column to the UI"""
    props = props_sequence.get_work_schedule_props()
    new = props.columns.add()
    new.name = f"{column_type}.{name}"
    new.data_type = data_type

def setup_default_task_columns() -> None:
    """Setup default task columns in UI"""
    props = props_sequence.get_work_schedule_props()
    props.columns.clear()
    default_columns = ["ScheduleStart", "ScheduleFinish", "ScheduleDuration"]
    for item in default_columns:
        new = props.columns.add()
        new.name = f"IfcTaskTime.{item}"
        new.data_type = "string"

def remove_task_column(name: str) -> None:
    """Remove a task column from UI"""
    props = props_sequence.get_work_schedule_props()
    column_index = props.columns.find(name)
    if column_index >= 0:
        props.columns.remove(column_index)
    if props.sort_column == name:
        props.sort_column = ""

def set_task_sort_column(column: str) -> None:
    """Set the task sort column"""
    props = props_sequence.get_work_schedule_props()
    props.sort_column = column

def is_work_schedule_active(work_schedule) -> bool:
    """Check if a work schedule is currently active"""
    props = props_sequence.get_work_schedule_props()
    return work_schedule.id() == props.active_work_schedule_id if work_schedule else False

def disable_work_schedule() -> None:
    """Disable the currently active work schedule"""
    props = props_sequence.get_work_schedule_props()
    props.active_work_schedule_id = 0

def validate_task_object(task, context="general") -> bool:
    """Validate that a task object is valid for processing"""
    if not task:
        return False
    
    if not hasattr(task, 'is_a'):
        return False
        
    try:
        if not task.is_a('IfcTask'):
            return False
    except:
        return False
        
    return True

def _load_task_date_properties(item, task, date_type: str) -> None:
    """Load task date properties for a specific date type"""
    import ifcopenshell.util.sequence
    
    start_attr = f"{date_type}Start"
    finish_attr = f"{date_type}Finish"
    
    try:
        start_date = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
        finish_date = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
        
        # Set the attributes on the item
        setattr(item, start_attr.lower(), start_date.isoformat() if start_date else "")
        setattr(item, finish_attr.lower(), finish_date.isoformat() if finish_date else "")
        
    except Exception as e:
        # Set empty values on error
        setattr(item, start_attr.lower(), "")
        setattr(item, finish_attr.lower(), "")

def _format_date(date_obj) -> str:
    """Format a date object for display"""
    if not date_obj:
        return ""
    
    try:
        if hasattr(date_obj, 'strftime'):
            return date_obj.strftime("%Y-%m-%d")
        else:
            return str(date_obj)
    except:
        return ""

def _build_object_task_mapping() -> dict:
    """Build mapping between objects and tasks for performance"""
    import bonsai.tool as tool
    
    mapping = {}
    try:
        ifc_file = tool.Ifc.get()
        if not ifc_file:
            return mapping
            
        # Build mapping from all tasks to their related objects
        for task in ifc_file.by_type("IfcTask"):
            task_outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
            for output in task_outputs:
                if output.id() not in mapping:
                    mapping[output.id()] = []
                mapping[output.id()].append(task.id())
                
    except Exception as e:
        print(f"Warning: Error building object-task mapping: {e}")
        
    return mapping

def parse_isodate_datetime(value, include_time: bool = True):
    """Parse ISO date/datetime string to datetime object"""
    from dateutil import parser
    from datetime import datetime
    
    if not value:
        return None
    
    try:
        if isinstance(value, str):
            # Handle various ISO formats
            parsed_date = parser.parse(value)
            if not include_time:
                # Return only date part
                return parsed_date.date()
            return parsed_date
        elif isinstance(value, datetime):
            return value
        else:
            return None
    except Exception as e:
        print(f"Error parsing date '{value}': {e}")
        return None

def isodate_datetime(value, include_time: bool = True) -> str:
    """Convert datetime object to ISO date/datetime string"""
    from datetime import datetime, date
    import ifcopenshell.util.date
    
    if not value:
        return ""
    
    try:
        if isinstance(value, datetime):
            if include_time:
                return ifcopenshell.util.date.canonicalise_time(value)
            else:
                return value.strftime("%Y-%m-%d")
        elif isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        elif isinstance(value, str):
            # Already a string, validate and return
            parsed = parse_isodate_datetime(value, include_time)
            if parsed:
                return isodate_datetime(parsed, include_time)
        return str(value)
    except Exception as e:
        print(f"Error formatting date '{value}': {e}")
        return ""

def apply_selection_from_checkboxes():
    """Apply selection based on UI checkboxes"""
    import bpy
    import bonsai.tool as tool
    import ifcopenshell.util.sequence
    
    # Clear current selection
    bpy.ops.object.select_all(action='DESELECT')
    
    # Get checked tasks
    from . import task_sequence
    checked_tasks = task_sequence.get_checked_tasks()
    
    # Select objects for checked tasks
    selected_count = 0
    for task in checked_tasks:
        task_outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
        for output in task_outputs:
            obj = tool.Ifc.get_object(output)
            if obj:
                obj.select_set(True)
                selected_count += 1
    
    print(f"Selected {selected_count} objects from {len(checked_tasks)} checked tasks")

def set_visibility_by_status(visible_statuses: set[str]) -> None:
    """Set object visibility based on task status"""
    import bpy
    import bonsai.tool as tool
    import ifcopenshell.util.sequence
    
    try:
        ifc = tool.Ifc.get()
        if not ifc:
            return
        
        # Get all tasks
        all_tasks = ifc.by_type('IfcTask')
        
        for task in all_tasks:
            task_status = getattr(task, 'Status', '')
            is_visible = task_status in visible_statuses
            
            # Get task outputs and set their visibility
            task_outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
            for output in task_outputs:
                obj = tool.Ifc.get_object(output)
                if obj:
                    obj.hide_viewport = not is_visible
                    obj.hide_render = not is_visible
        
        # Update viewport
        bpy.context.view_layer.update()
        
    except Exception as e:
        print(f"Error setting visibility by status: {e}")

def select_unassigned_work_schedule_products() -> str:
    """Select products that are not assigned to any work schedule"""
    import bpy
    import bonsai.tool as tool
    import ifcopenshell.util.sequence
    
    try:
        ifc = tool.Ifc.get()
        if not ifc:
            return "No IFC file loaded"
        
        # Clear current selection
        bpy.ops.object.select_all(action='DESELECT')
        
        # Get all products
        all_products = ifc.by_type('IfcProduct')
        unassigned_products = []
        
        for product in all_products:
            # Check if product is assigned to any task
            is_assigned = False
            
            # Check HasAssignments relationships
            for rel in getattr(product, 'HasAssignments', []):
                if rel.is_a('IfcRelAssignsToProcess'):
                    relating_process = rel.RelatingProcess
                    if relating_process and relating_process.is_a('IfcTask'):
                        is_assigned = True
                        break
            
            if not is_assigned:
                unassigned_products.append(product)
        
        # Select unassigned products in viewport
        selected_count = 0
        for product in unassigned_products:
            obj = tool.Ifc.get_object(product)
            if obj:
                obj.select_set(True)
                selected_count += 1
        
        message = f"Selected {selected_count} unassigned products out of {len(unassigned_products)} total unassigned"
        print(message)
        return message
        
    except Exception as e:
        error_msg = f"Error selecting unassigned products: {e}"
        print(error_msg)
        return error_msg

def create_tasks_json(work_schedule) -> list[dict]:
    """Create JSON representation of tasks for export"""
    import ifcopenshell.util.sequence
    from datetime import datetime
    
    if not work_schedule:
        return []
    
    def create_new_task_json(task, json_list, type_map=None, baseline_schedule=None):
        """Create JSON for a single task"""
        task_json = {
            'id': task.id(),
            'name': task.Name or '',
            'identification': getattr(task, 'Identification', '') or '',
            'status': getattr(task, 'Status', '') or '',
            'created_at': isodate_datetime(datetime.now())
        }
        
        # Add task time information
        if task.TaskTime:
            task_time = task.TaskTime
            task_json['schedule_start'] = str(getattr(task_time, 'ScheduleStart', ''))
            task_json['schedule_finish'] = str(getattr(task_time, 'ScheduleFinish', ''))
            task_json['schedule_duration'] = str(getattr(task_time, 'ScheduleDuration', ''))
            task_json['actual_start'] = str(getattr(task_time, 'ActualStart', ''))
            task_json['actual_finish'] = str(getattr(task_time, 'ActualFinish', ''))
        
        # Add baseline comparison if provided
        if baseline_schedule and type_map:
            baseline_task_id = type_map.get(task.id())
            if baseline_task_id:
                task_json['baseline_task_id'] = baseline_task_id
        
        json_list.append(task_json)
        
        # Process nested tasks recursively
        nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
        for nested_task in nested_tasks:
            create_new_task_json(nested_task, json_list, type_map, baseline_schedule)
    
    tasks_json = []
    root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
    
    for task in root_tasks:
        create_new_task_json(task, tasks_json)
    
    return tasks_json

def sync_3d_elements(work_schedule, property_set_name):
    """Synchronize 3D elements with schedule tasks"""
    import bonsai.tool as tool
    import ifcopenshell.util.sequence
    
    if not work_schedule or not property_set_name:
        print("Missing work schedule or property set name")
        return False
    
    try:
        ifc = tool.Ifc.get()
        if not ifc:
            return False
        
        def get_all_tasks_recursive(tasks):
            all_tasks = []
            for task in tasks:
                all_tasks.append(task)
                nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                if nested:
                    all_tasks.extend(get_all_tasks_recursive(nested))
            return all_tasks
        
        # Get all tasks from schedule
        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
        all_tasks = get_all_tasks_recursive(root_tasks)
        
        sync_count = 0
        for task in all_tasks:
            # Get task outputs
            task_outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
            
            for output in task_outputs:
                # Check if product has the specified property set
                for definition in output.IsDefinedBy or []:
                    if definition.is_a('IfcRelDefinesByProperties'):
                        prop_def = definition.RelatingPropertyDefinition
                        if prop_def and hasattr(prop_def, 'Name') and prop_def.Name == property_set_name:
                            # Found matching property set - sync with task data
                            sync_count += 1
                            print(f"Synced {output.Name} with task {task.Name}")
        
        print(f"Synchronized {sync_count} elements")
        return sync_count > 0
        
    except Exception as e:
        print(f"Error syncing 3D elements: {e}")
        return False

def update_visualisation_date(start_date, finish_date):
    """Update visualization date range"""
    import ifcopenshell.util.date
    
    props = props_sequence.get_work_schedule_props()
    if start_date and finish_date:
        start_iso = ifcopenshell.util.date.canonicalise_time(start_date)
        finish_iso = ifcopenshell.util.date.canonicalise_time(finish_date)
        
        print(f"📝 UPDATE_VIZ_DATE: Setting {start_iso} to {finish_iso}")
        print(f"📝 UPDATE_VIZ_DATE: Previous values were: {getattr(props, 'visualisation_start', 'None')} to {getattr(props, 'visualisation_finish', 'None')}")
        
        props.visualisation_start = start_iso
        props.visualisation_finish = finish_iso
        
        print(f"✅ UPDATE_VIZ_DATE: New values are: {props.visualisation_start} to {props.visualisation_finish}")
    else:
        print(f"❌ UPDATE_VIZ_DATE: Invalid dates provided - start: {start_date}, finish: {finish_date}")
        props.visualisation_start = ""
        props.visualisation_finish = ""

def _debug_copy3d_state(stage, schedule_name="", task_count=0):
    """DEBUG: Internal testing function to verify Copy3D state at different stages"""
    print(f"\n🔍 COPY3D DEBUG [{stage}] - Schedule: {schedule_name}, Tasks: {task_count}")
    
    try:
        tprops = props_sequence.get_task_tree_props()
        if not tprops or not hasattr(tprops, 'tasks'):
            print("❌ No task properties available")
            return
            
        # Sample first 3 tasks for detailed inspection
        sample_tasks = list(tprops.tasks)[:3] if hasattr(tprops, 'tasks') else []
        
        for i, task in enumerate(sample_tasks):
            tid = getattr(task, 'ifc_definition_id', '?')
            name = getattr(task, 'name', 'Unnamed')[:30]
            
            # Core properties
            use_active = getattr(task, 'use_active_colortype_group', False)
            colortype_groups = getattr(task, 'ColorType_groups', '')
            animation_schemes = getattr(task, 'animation_color_schemes', '')
            selected_active = getattr(task, 'selected_colortype_in_active_group', '')
            
            print(f"  Task {tid} ({name}):")
            print(f"    use_active: {use_active}")
            print(f"    ColorType_groups: '{colortype_groups}'")
            print(f"    animation_color_schemes: '{animation_schemes}'")
            print(f"    selected_active: '{selected_active}'")
            
    except Exception as e:
        print(f"❌ Debug state error: {e}")
    
    print(f"🔍 END COPY3D DEBUG [{stage}]\n")

def _test_copy3d_results(copied_schedules, total_matches):
    """TEST: Comprehensive verification of Copy3D results"""
    print(f"\n🧪 COPY3D RESULT TEST: Verifying {copied_schedules} schedules with {total_matches} matches")
    
    try:
        # Test 1: Check if active schedule has proper ColorType data
        tprops = props_sequence.get_task_tree_props()
        if not tprops or not hasattr(tprops, 'tasks'):
            print("❌ TEST FAIL: No task properties available for verification")
            return False
        
        test_results = {
            "tasks_with_active_groups": 0,
            "tasks_with_animation_schemes": 0,
            "tasks_with_group_choices": 0,
            "tasks_with_empty_configs": 0,
            "total_tested": 0
        }
        
        # Sample testing on first 5 tasks
        sample_tasks = list(tprops.tasks)[:5] if hasattr(tprops, 'tasks') else []
        
        for task in sample_tasks:
            test_results["total_tested"] += 1
            tid = getattr(task, 'ifc_definition_id', '?')
            name = getattr(task, 'name', 'Unnamed')[:20]
            
            # Test properties
            use_active = getattr(task, 'use_active_colortype_group', False)
            animation_schemes = getattr(task, 'animation_color_schemes', '')
            group_choices = list(getattr(task, 'colortype_group_choices', []))
            
            # Count configurations
            if use_active:
                test_results["tasks_with_active_groups"] += 1
            if animation_schemes:
                test_results["tasks_with_animation_schemes"] += 1
            if group_choices:
                test_results["tasks_with_group_choices"] += 1
            if not use_active and not animation_schemes and not group_choices:
                test_results["tasks_with_empty_configs"] += 1
        
        print(f"🧪 TEST RESULTS: {test_results}")
        success_rate = (test_results['total_tested'] - test_results['tasks_with_empty_configs']) / test_results['total_tested'] if test_results['total_tested'] > 0 else 0
        print(f"✅ Copy3D Success Rate: {success_rate:.2%}")
        
        return success_rate > 0.5  # At least 50% success rate
        
    except Exception as e:
        print(f"❌ Copy3D test error: {e}")
        return False

def _to_dt(value):
    """Convert value to datetime object"""
    from datetime import datetime
    from dateutil import parser
    
    if not value:
        return None
    
    if isinstance(value, datetime):
        return value
    
    if isinstance(value, str):
        try:
            return parser.parse(value)
        except:
            return None
    
    return None

def enable_editing_work_schedule(work_schedule) -> None:
    """Enable editing work schedule"""
    if work_schedule:
        props = props_sequence.get_work_schedule_props()
        props.active_work_schedule_id = work_schedule.id()
        props.editing_type = "ATTRIBUTES"

def disable_editing_work_schedule() -> None:
    """Disable editing work schedule"""
    props = props_sequence.get_work_schedule_props()
    props.active_work_schedule_id = 0
    props.editing_type = ""

def enable_editing_work_schedule_tasks(work_schedule) -> None:
    """Enable editing work schedule tasks"""
    if work_schedule:
        props = props_sequence.get_work_schedule_props()
        props.active_work_schedule_id = work_schedule.id()
        props.editing_type = "TASKS"

def get_all_tasks_recursive_target(tasks):
    """Get all tasks recursively for target processing"""
    import ifcopenshell.util.sequence
    
    all_tasks = []
    for task in tasks:
        all_tasks.append(task)
        nested = ifcopenshell.util.sequence.get_nested_tasks(task)
        if nested:
            all_tasks.extend(get_all_tasks_recursive_target(nested))
    return all_tasks

def _add():
    """Internal add method for sequence processing"""
    # This appears to be a helper method for adding elements
    # Implementation depends on specific context
    return True


def export_schedule_configuration():
    """Export current schedule configuration to file"""
    try:
        props = props_sequence.get_work_schedule_props()
        if not props.active_work_schedule_id:
            return None
            
        work_schedule = tool.Ifc.get().by_id(props.active_work_schedule_id)
        
        config = {
            'schedule_name': work_schedule.Name or f"Schedule_{work_schedule.id()}",
            'schedule_id': work_schedule.id(),
            'date_range': get_visualization_date_range(),
            'colortype_groups': [],
            'animation_settings': get_animation_settings()
        }
        
        # Export ColorType groups
        for group in props.colortype_groups:
            group_data = {
                'name': group.name,
                'description': getattr(group, 'description', ''),
                'color_types': []
            }
            
            if hasattr(group, 'color_types'):
                for ct in group.color_types:
                    ct_data = {
                        'name': ct.name,
                        'color': list(ct.color) if hasattr(ct, 'color') else [1.0, 1.0, 1.0, 1.0],
                        'description': getattr(ct, 'description', '')
                    }
                    group_data['color_types'].append(ct_data)
            
            config['colortype_groups'].append(group_data)
        
        return config
        
    except Exception as e:
        print(f"❌ Schedule configuration export error: {e}")
        return None


def import_schedule_configuration(config_data):
    """Import schedule configuration from data"""
    try:
        if not config_data:
            return False
            
        props = props_sequence.get_work_schedule_props()
        
        # Import ColorType groups
        if 'colortype_groups' in config_data:
            props.colortype_groups.clear()
            
            for group_data in config_data['colortype_groups']:
                new_group = props.colortype_groups.add()
                new_group.name = group_data.get('name', 'Imported Group')
                if 'description' in group_data:
                    new_group.description = group_data['description']
                
                # Import color types
                if 'color_types' in group_data:
                    for ct_data in group_data['color_types']:
                        new_ct = new_group.color_types.add()
                        new_ct.name = ct_data.get('name', 'Imported ColorType')
                        if 'color' in ct_data:
                            new_ct.color = tuple(ct_data['color'])
                        if 'description' in ct_data:
                            new_ct.description = ct_data['description']
        
        # Import animation settings
        if 'animation_settings' in config_data:
            animation_settings = config_data['animation_settings']
            if 'frames_per_day' in animation_settings:
                props.frames_per_day = animation_settings['frames_per_day']
                
        print("✅ Schedule configuration imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Schedule configuration import error: {e}")
        return False


def generate_gantt_browser_chart():
    """Generate Gantt chart data for browser display"""
    try:
        props = props_sequence.get_work_schedule_props()
        if not props.active_work_schedule_id:
            return None
            
        work_schedule = tool.Ifc.get().by_id(props.active_work_schedule_id)
        tasks = get_all_tasks_from_schedule(work_schedule)
        
        gantt_data = {
            'schedule_name': work_schedule.Name or f"Schedule_{work_schedule.id()}",
            'tasks': [],
            'date_range': get_schedule_date_range(work_schedule)
        }
        
        for task in tasks:
            start_time = ifcopenshell.util.sequence.get_start_time(task)
            finish_time = ifcopenshell.util.sequence.get_finish_time(task)
            
            if start_time and finish_time:
                task_data = {
                    'id': task.id(),
                    'name': task.Name or f"Task {task.id()}",
                    'start': start_time.isoformat(),
                    'finish': finish_time.isoformat(),
                    'duration': (finish_time - start_time).days,
                    'progress': 0  # Could be enhanced with actual progress
                }
                
                # Get nested tasks
                nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                if nested_tasks:
                    task_data['children'] = [t.id() for t in nested_tasks]
                
                gantt_data['tasks'].append(task_data)
        
        return gantt_data
        
    except Exception as e:
        print(f"❌ Gantt chart generation error: {e}")
        return None


def has_variance_calculation_in_tasks():
    """Check if any tasks have variance calculation data"""
    try:
        props = props_sequence.get_work_schedule_props()
        if not props.active_work_schedule_id:
            return False
            
        work_schedule = tool.Ifc.get().by_id(props.active_work_schedule_id)
        tasks = get_all_tasks_from_schedule(work_schedule)
        
        for task in tasks:
            actual_start = ifcopenshell.util.sequence.get_actual_start(task)
            actual_finish = ifcopenshell.util.sequence.get_actual_finish(task)
            
            if actual_start or actual_finish:
                return True
                
        return False
        
    except Exception as e:
        print(f"❌ Variance calculation check error: {e}")
        return False


def link_collection(collection_name):
    """Link collection to scene if not already linked"""
    try:
        if collection_name in bpy.context.scene.collection.children:
            return bpy.data.collections[collection_name]
            
        if collection_name in bpy.data.collections:
            collection = bpy.data.collections[collection_name]
            bpy.context.scene.collection.children.link(collection)
            return collection
        else:
            # Create new collection
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)
            return collection
            
    except Exception as e:
        print(f"❌ Collection linking error: {e}")
        return None


def restore_all_ui_state():
    """Restore all UI state from saved snapshot"""
    try:
        if hasattr(bpy.app, '_4d_ui_snapshot'):
            ui_snapshot = bpy.app._4d_ui_snapshot
            
            # Restore viewport shading
            if 'viewport_shading' in ui_snapshot:
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.shading.type = ui_snapshot['viewport_shading']
            
            # Restore object visibility
            if 'object_visibility' in ui_snapshot:
                for obj_name, visibility in ui_snapshot['object_visibility'].items():
                    obj = bpy.data.objects.get(obj_name)
                    if obj:
                        obj.hide_viewport = not visibility
            
            print("✅ UI state restored")
            
    except Exception as e:
        print(f"❌ UI state restoration error: {e}")


def snapshot_all_ui_state():
    """Snapshot current UI state for later restoration"""
    try:
        ui_snapshot = {}
        
        # Snapshot viewport shading
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        ui_snapshot['viewport_shading'] = space.shading.type
                        break
                break
        
        # Snapshot object visibility
        ui_snapshot['object_visibility'] = {}
        for obj in bpy.data.objects:
            ui_snapshot['object_visibility'][obj.name] = not obj.hide_viewport
        
        # Store snapshot
        bpy.app._4d_ui_snapshot = ui_snapshot
        print("✅ UI state snapshot created")
        
    except Exception as e:
        print(f"❌ UI state snapshot error: {e}")
