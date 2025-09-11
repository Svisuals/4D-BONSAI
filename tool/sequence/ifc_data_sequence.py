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



import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid
import ifcopenshell.util.sequence
from typing import Any, Union, Literal, TYPE_CHECKING
import traceback

from .props_sequence import PropsSequence
import bonsai.bim.helper
import bonsai.tool as tool

if TYPE_CHECKING:
    from bonsai.bim.prop import Attribute


class IFCDataSequence(PropsSequence):
    """Maneja la carga, edición y manipulación de datos de entidades IFC."""



    @classmethod
    def get_work_plan_attributes(cls) -> dict[str, Any]:
        import bonsai.bim.module.sequence.helper as helper

        def callback(attributes: dict[str, Any], prop: "Attribute") -> bool:
            if "Date" in prop.name or "Time" in prop.name:
                if prop.is_null:
                    attributes[prop.name] = None
                    return True
                attributes[prop.name] = helper.parse_datetime(prop.string_value)
                return True
            elif prop.name == "Duration" or prop.name == "TotalFloat":
                if prop.is_null:
                    attributes[prop.name] = None
                    return True
                attributes[prop.name] = helper.parse_duration(prop.string_value)
                return True
            return False

        props = cls.get_work_plan_props()
        return bonsai.bim.helper.export_attributes(props.work_plan_attributes, callback)


    @classmethod
    def load_work_plan_attributes(cls, work_plan: ifcopenshell.entity_instance) -> None:
        def callback(name: str, prop: Union["Attribute", None], data: dict[str, Any]) -> None | Literal[True]:
            if name in ["CreationDate", "StartTime", "FinishTime"]:
                assert prop
                prop.string_value = "" if prop.is_null else data[name]
                return True

        props = cls.get_work_plan_props()
        props.work_plan_attributes.clear()
        bonsai.bim.helper.import_attributes(work_plan, props.work_plan_attributes, callback)


    @classmethod
    def get_work_schedule_attributes(cls) -> dict[str, Any]:
        import bonsai.bim.module.sequence.helper as helper

        def callback(attributes: dict[str, Any], prop: "Attribute") -> bool:
            if "Date" in prop.name or "Time" in prop.name:
                if prop.is_null:
                    attributes[prop.name] = None
                    return True
                attributes[prop.name] = helper.parse_datetime(prop.string_value)
                return True
            elif prop.special_type == "DURATION":
                return cls.export_duration_prop(prop, attributes)
            return False

        props = cls.get_work_schedule_props()
        return bonsai.bim.helper.export_attributes(props.work_schedule_attributes, callback)

    @classmethod
    def load_work_schedule_attributes(cls, work_schedule: ifcopenshell.entity_instance) -> None:
        schema = tool.Ifc.schema()
        entity = schema.declaration_by_name("IfcWorkSchedule").as_entity()
        assert entity

        def callback(name: str, prop: Union["Attribute", None], data: dict[str, Any]) -> None | Literal[True]:
            if name in ["CreationDate", "StartTime", "FinishTime"]:
                assert prop
                prop.string_value = "" if prop.is_null else data[name]
                return True
            else:
                attr = entity.attribute_by_index(entity.attribute_index(name))
                if not attr.type_of_attribute()._is("IfcDuration"):
                    return
                assert prop
                cls.add_duration_prop(prop, data[name])

        props = cls.get_work_schedule_props()
        props.work_schedule_attributes.clear()
        bonsai.bim.helper.import_attributes(work_schedule, props.work_schedule_attributes, callback)


    @classmethod
    def copy_work_schedule(cls, work_schedule: ifcopenshell.entity_instance) -> None:
        """Creates a deep copy of the given work schedule, including all its tasks and relationships."""
        import ifcopenshell
        import ifcopenshell.api
        import ifcopenshell.util.sequence
        import ifcopenshell.guid
        file = tool.Ifc.get()
        if not work_schedule or not file:
            print("Error: Invalid work schedule or IFC file.")
            return

        # --- PRIMARY METHOD: Use the modern clone API if available ---
        try:
            import ifcopenshell.api.clone
            new_schedule = ifcopenshell.api.run("clone.clone_deep", file, element=work_schedule)
            original_name = getattr(work_schedule, "Name", "Unnamed Schedule")
            new_schedule.Name = f"Copy of {original_name}"
            print(f"Bonsai INFO: Successfully copied schedule using modern clone.clone_deep API.")
            return
        except (ImportError, ModuleNotFoundError) as e:
            print(f"Bonsai WARNING: clone.clone_deep not available ('{e}'). This may be due to an outdated IfcOpenShell version. Falling back to a basic manual copy.")
        except Exception as e:
            print(f"Bonsai WARNING: An unexpected error occurred with clone.clone_deep ('{e}'). Falling back to manual copy.")

        # --- FALLBACK METHOD: Manual deep copy for very old IfcOpenShell versions ---
        def _create_entity_copy(ifc_file, entity: ifcopenshell.entity_instance):
            """Creates a TRUE copy of an IFC entity with a new unique ID."""
            if not entity:
                return None
            try:
                # CRÍTICO: Usar create_entity para crear una nueva entidad con nuevo ID
                # NO usar .add() que solo reutiliza la entidad existente
                entity_info = entity.get_info()
                
                # Remover campos que deben ser únicos para la nueva entidad
                if 'id' in entity_info:
                    del entity_info['id']
                if 'GlobalId' in entity_info:
                    entity_info['GlobalId'] = ifcopenshell.guid.new()
                
                # Crear nueva entidad con los datos copiados
                new_entity = ifc_file.create_entity(entity.is_a(), **entity_info)
                print(f"✅ Tarea copiada: '{entity.Name}' - Original ID: {entity.id()} → Nuevo ID: {new_entity.id()}")
                return new_entity
                
            except Exception as e:
                print(f"❌ Error copiando entidad {entity} - {e}")
                # Fallback: intentar con método API si está disponible
                try:
                    if entity.is_a("IfcTask"):
                        # Para tareas, usar la API específica si está disponible
                        work_schedule = None  # Se asignará después
                        new_task = ifcopenshell.api.run("sequence.add_task", ifc_file, parent_task=None, work_schedule=work_schedule)
                        
                        # Copiar atributos importantes
                        if hasattr(entity, 'Name') and entity.Name:
                            new_task.Name = entity.Name
                        if hasattr(entity, 'Description') and entity.Description:
                            new_task.Description = entity.Description
                        if hasattr(entity, 'Identification') and entity.Identification:
                            new_task.Identification = entity.Identification
                        if hasattr(entity, 'PredefinedType') and entity.PredefinedType:
                            new_task.PredefinedType = entity.PredefinedType
                            
                        print(f"✅ Tarea creada con API: '{entity.Name}' - Original ID: {entity.id()} → Nuevo ID: {new_task.id()}")
                        return new_task
                except Exception as api_error:
                    print(f"❌ También falló el método API: {api_error}")
                
                return None

        try:
            old_to_new_tasks = {}  # Map old task IDs to new task entities
            cls.last_duplication_mapping = {}  # Para uso posterior en ColorType

            def _copy_task_recursive(old_task, new_parent):
                # 1. Crear una tarea completamente nueva con ID único
                try:
                    if new_parent.is_a("IfcWorkSchedule"):
                        # Para tareas raíz, usar la API con work_schedule
                        new_task = ifcopenshell.api.run("sequence.add_task", file, 
                                                       work_schedule=new_parent, 
                                                       parent_task=None)
                    else:
                        # Para tareas anidadas, usar la API con parent_task
                        work_schedule = ifcopenshell.util.sequence.get_task_work_schedule(new_parent)
                        new_task = ifcopenshell.api.run("sequence.add_task", file,
                                                       work_schedule=work_schedule,
                                                       parent_task=new_parent)
                    
                    # Copiar todos los atributos importantes
                    if hasattr(old_task, 'Name') and old_task.Name:
                        new_task.Name = old_task.Name
                    if hasattr(old_task, 'Description') and old_task.Description:
                        new_task.Description = old_task.Description
                    if hasattr(old_task, 'Identification') and old_task.Identification:
                        new_task.Identification = old_task.Identification
                    if hasattr(old_task, 'PredefinedType') and old_task.PredefinedType:
                        new_task.PredefinedType = old_task.PredefinedType
                    if hasattr(old_task, 'Priority') and old_task.Priority:
                        new_task.Priority = old_task.Priority
                    if hasattr(old_task, 'Status') and old_task.Status:
                        new_task.Status = old_task.Status
                    if hasattr(old_task, 'WorkMethod') and old_task.WorkMethod:
                        new_task.WorkMethod = old_task.WorkMethod
                    if hasattr(old_task, 'IsMilestone') and old_task.IsMilestone is not None:
                        new_task.IsMilestone = old_task.IsMilestone
                        
                    print(f"✅ NUEVA TAREA CREADA: '{old_task.Name}' - Original ID: {old_task.id()} → Nuevo ID: {new_task.id()}")
                    
                except Exception as api_error:
                    print(f"❌ Error con API, intentando método directo: {api_error}")
                    # Fallback al método de copia de entidad
                    new_task = _create_entity_copy(file, old_task)
                    if not new_task:
                        print(f"❌ FALLO TOTAL: No se pudo copiar tarea {getattr(old_task, 'id', 'N/A')}. Saltando.")
                        return

                # 2. Copiar TaskTime si existe
                if old_task.TaskTime:
                    try:
                        # Crear nuevo TaskTime usando API
                        new_task_time = ifcopenshell.api.run("sequence.add_task_time", file, task=new_task)
                        
                        # Copiar atributos de tiempo
                        old_time = old_task.TaskTime
                        if hasattr(old_time, 'DurationType') and old_time.DurationType:
                            new_task_time.DurationType = old_time.DurationType
                        if hasattr(old_time, 'ScheduleDuration') and old_time.ScheduleDuration:
                            new_task_time.ScheduleDuration = old_time.ScheduleDuration
                        if hasattr(old_time, 'ScheduleStart') and old_time.ScheduleStart:
                            new_task_time.ScheduleStart = old_time.ScheduleStart
                        if hasattr(old_time, 'ScheduleFinish') and old_time.ScheduleFinish:
                            new_task_time.ScheduleFinish = old_time.ScheduleFinish
                        if hasattr(old_time, 'ActualStart') and old_time.ActualStart:
                            new_task_time.ActualStart = old_time.ActualStart
                        if hasattr(old_time, 'ActualFinish') and old_time.ActualFinish:
                            new_task_time.ActualFinish = old_time.ActualFinish
                            
                        print(f"✅ TaskTime copiado para tarea '{new_task.Name}'")
                        
                    except Exception as time_error:
                        print(f"⚠️ Error copiando TaskTime: {time_error}")
                        # Fallback: copiar TaskTime con método directo
                        try:
                            new_task.TaskTime = _create_entity_copy(file, old_task.TaskTime)
                        except:
                            print(f"⚠️ No se pudo copiar TaskTime para '{new_task.Name}'")
                
                old_to_new_tasks[old_task.id()] = new_task
                cls.last_duplication_mapping[old_task.id()] = new_task.id()

                # 3. Las relaciones ya se crearon automáticamente con la API
                # Copiar productos y recursos a la nueva tarea
                for product in ifcopenshell.util.sequence.get_task_outputs(old_task):
                    ifcopenshell.api.run("sequence.assign_product", file, relating_product=product, related_object=new_task)
                for product_input in ifcopenshell.util.sequence.get_task_inputs(old_task):
                    ifcopenshell.api.run("sequence.assign_process", file, relating_process=new_task, related_object=product_input)
                for resource in ifcopenshell.util.sequence.get_task_resources(old_task):
                    ifcopenshell.api.run("sequence.assign_process", file, relating_process=new_task, related_object=resource)
                
                # 4. Recursively copy nested tasks
                for child_task in ifcopenshell.util.sequence.get_nested_tasks(old_task):
                    _copy_task_recursive(child_task, new_task)

            # 1. Create the new, empty work schedule
            new_schedule = ifcopenshell.api.run("sequence.add_work_schedule", file, name=f"Copy of {getattr(work_schedule, 'Name', 'Unnamed')}")

            # 2. Start the recursive copy from the root tasks
            for root_task in ifcopenshell.util.sequence.get_root_tasks(work_schedule):
                _copy_task_recursive(root_task, new_schedule)
                
            # 3. Re-link predecessors and successors
            for old_id, new_task in old_to_new_tasks.items():
                old_task = file.by_id(old_id)
                for rel in getattr(old_task, 'IsSuccessorFrom', []):
                    old_predecessor = rel.RelatingProcess
                    if old_predecessor.id() in old_to_new_tasks:
                        new_predecessor = old_to_new_tasks[old_predecessor.id()]
                        time_lag = _create_entity_copy(file, rel.TimeLag) if getattr(rel, 'TimeLag', None) else None
                        # The 'time_lag' argument is not supported in older ifcopenshell API versions.
                        # We create the relationship first, then assign the time lag manually for compatibility.
                        new_rel = ifcopenshell.api.run(
                            "sequence.assign_sequence",
                            file,
                            relating_process=new_predecessor,
                            related_process=new_task,
                            sequence_type=rel.SequenceType,
                        )
                        if time_lag:
                            new_rel.TimeLag = time_lag
            
            print(f"Bonsai INFO: Successfully copied schedule using manual fallback method.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error during manual schedule copy: {e}")


    @classmethod
    def add_duration_prop(cls, prop: "Attribute", duration_value: Union[str, None]) -> None:
        import bonsai.bim.module.sequence.helper as helper

        props = cls.get_work_schedule_props()
        prop.special_type = "DURATION"
        duration_props = props.durations_attributes.add()
        duration_props.name = prop.name
        if duration_value is None:
            return
        for key, value in helper.parse_duration_as_blender_props(duration_value).items():
            setattr(duration_props, key, value)


    @classmethod
    def export_duration_prop(cls, prop: "Attribute", out_attributes: dict[str, Any]) -> Literal[True]:
        import bonsai.bim.module.sequence.helper as helper

        props = cls.get_work_schedule_props()
        if prop.is_null:
            out_attributes[prop.name] = None
        else:
            duration_type = out_attributes["DurationType"] if "DurationType" in out_attributes else None
            time_split_iso_duration = helper.blender_props_to_iso_duration(
                props.durations_attributes, duration_type, prop.name
            )
            out_attributes[prop.name] = time_split_iso_duration
        return True


    @classmethod
    def load_task_attributes(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.task_attributes.clear()
        bonsai.bim.helper.import_attributes(task, props.task_attributes)


    @classmethod
    def get_task_attributes(cls) -> dict[str, Any]:
        props = cls.get_work_schedule_props()
        return bonsai.bim.helper.export_attributes(props.task_attributes)


    @classmethod
    def load_task_time_attributes(cls, task_time: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        schema = tool.Ifc.schema()
        entity = schema.declaration_by_name("IfcTaskTime").as_entity()
        assert entity

        def callback(name: str, prop: Union["Attribute", None], data: dict[str, Any]) -> Union[bool, None]:
            attr = entity.attribute_by_index(entity.attribute_index(name))
            if attr.type_of_attribute()._is("IfcDuration"):
                assert prop
                cls.add_duration_prop(prop, data[name])
            if isinstance(data[name], datetime):
                assert prop
                prop.string_value = "" if prop.is_null else data[name].isoformat()
                return True

        props.task_time_attributes.clear()
        props.durations_attributes.clear()
        bonsai.bim.helper.import_attributes(task_time, props.task_time_attributes, callback)


    @classmethod
    def get_task_time_attributes(cls) -> dict[str, Any]:
        import bonsai.bim.module.sequence.helper as helper

        props = cls.get_work_schedule_props()

        def callback(attributes: dict[str, Any], prop: "Attribute") -> bool:
            if "Start" in prop.name or "Finish" in prop.name or prop.name == "StatusTime":
                if prop.is_null:
                    attributes[prop.name] = None
                    return True
                attributes[prop.name] = helper.parse_datetime(prop.string_value)
                return True
            elif prop.special_type == "DURATION":
                return cls.export_duration_prop(prop, attributes)
            return False

        return bonsai.bim.helper.export_attributes(props.task_time_attributes, callback)



    @classmethod
    def enable_editing_work_plan(cls, work_plan: Union[ifcopenshell.entity_instance, None]) -> None:
        if work_plan:
            props = cls.get_work_plan_props()
            props.active_work_plan_id = work_plan.id()
            props.editing_type = "ATTRIBUTES"

    @classmethod
    def disable_editing_work_plan(cls) -> None:
        props = cls.get_work_plan_props()
        props.active_work_plan_id = 0

    @classmethod
    def enable_editing_work_plan_schedules(cls, work_plan: Union[ifcopenshell.entity_instance, None]) -> None:
        if work_plan:
            props = cls.get_work_plan_props()
            props.active_work_plan_id = work_plan.id()
            props.editing_type = "SCHEDULES"



    @classmethod
    def enable_editing_work_schedule(cls, work_schedule: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_work_schedule_id = work_schedule.id()
        props.editing_type = "WORK_SCHEDULE"

    @classmethod
    def disable_editing_work_schedule(cls) -> None:
        props = cls.get_work_schedule_props()
        props.active_work_schedule_id = 0

    @classmethod
    def enable_editing_work_schedule_tasks(cls, work_schedule: Union[ifcopenshell.entity_instance, None]) -> None:
        print(f"🔍 DEBUG IFCDataSequence.enable_editing_work_schedule_tasks: work_schedule={work_schedule}")
        if work_schedule:
            props = cls.get_work_schedule_props()
            print(f"🔍 DEBUG: Estableciendo active_work_schedule_id={work_schedule.id()}")
            props.active_work_schedule_id = work_schedule.id()
            props.editing_type = "TASKS"
            print("🔍 DEBUG: editing_type establecido como TASKS")
        else:
            print("🔍 DEBUG: work_schedule es None, no se realizan cambios")

    @classmethod
    def disable_work_schedule(cls) -> None:
        props = cls.get_work_schedule_props()
        props.active_work_schedule_id = 0


    @classmethod
    def get_task_attribute_value(cls, attribute_name: str) -> Any:
        props = cls.get_work_schedule_props()
        return props.task_attributes[attribute_name].get_value()

    @classmethod
    def get_task_time(cls, task: ifcopenshell.entity_instance) -> Union[ifcopenshell.entity_instance, None]:
        return task.TaskTime or None

    @classmethod
    def enable_editing_task_attributes(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_task_id = task.id()
        props.editing_task_type = "ATTRIBUTES"

    @classmethod
    def enable_editing_task_time(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_task_id = task.id()
        props.active_task_time_id = task.TaskTime.id()
        props.editing_task_type = "TASKTIME"

    @classmethod
    def disable_editing_task(cls) -> None:
        props = cls.get_work_schedule_props()
        props.active_task_id = 0
        props.active_task_time_id = 0
        props.editing_task_type = ""












