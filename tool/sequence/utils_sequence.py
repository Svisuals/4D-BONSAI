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
    import bonsai.bim.module.sequence.helper as helper
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
    import bonsai.bim.module.sequence.helper as helper
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        if "Time" in prop.name:
            attributes[prop.name] = None if prop.is_null else helper.parse_datetime(prop.string_value)
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
    import bonsai.bim.module.sequence.helper as helper
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        if "Time" in prop.name:
            attributes[prop.name] = None if prop.is_null else helper.parse_datetime(prop.string_value)
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
    import bonsai.bim.module.sequence.helper as helper
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
    import bonsai.bim.module.sequence.helper as helper
    from typing import Any
    from bonsai.bim.prop import Attribute
    import bonsai.bim.helper
    
    def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
        if prop.name == "LagValue":
            attributes[prop.name] = None if prop.is_null else helper.parse_duration(prop.string_value)
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
    import bonsai.bim.module.sequence.helper as helper
    
    if prop.is_null:
        attributes[prop.name] = None
        return True
    
    try:
        duration = helper.parse_duration(prop.string_value)
        attributes[prop.name] = duration
        return True
    except:
        return False

def add_duration_prop(prop, value) -> None:
    """Add duration property with proper formatting"""
    import bonsai.bim.module.sequence.helper as helper
    
    if value is None:
        prop.is_null = True
        prop.string_value = ""
    else:
        prop.is_null = False
        prop.string_value = helper.isodate_duration(value) if value else ""







