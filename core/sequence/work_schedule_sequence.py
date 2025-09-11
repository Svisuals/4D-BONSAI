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


from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    import bpy
    import ifcopenshell
    import bonsai.tool as tool



def edit_work_schedule(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], work_schedule: ifcopenshell.entity_instance
) -> None:
    try:
        # Validate that the work_schedule exists before editing
        if not work_schedule or not hasattr(work_schedule, 'is_a'):
            print("ERROR: WorkSchedule is invalid or doesn't exist")
            return
            
        # Get ID for debug
        schedule_id = work_schedule.id()
        schedule_name = getattr(work_schedule, 'Name', 'Unnamed')
        print(f"DEBUG: Editing WorkSchedule ID {schedule_id} - Name: {schedule_name}")
        
        # Get attributes
        attributes = sequence.get_work_schedule_attributes()
        print(f"DEBUG: Attributes to update: {attributes}")
        
        # Validate that we have valid attributes
        if not attributes:
            print("WARNING: No attributes to update")
            sequence.disable_editing_work_schedule()
            return
            
        # Execute the edit
        ifc.run("sequence.edit_work_schedule", work_schedule=work_schedule, attributes=attributes)
        
        # Verify that the work_schedule still exists after editing
        try:
            # Try to access the work_schedule to verify that it was not deleted
            test_id = work_schedule.id()
            test_name = getattr(work_schedule, 'Name', 'Unnamed')
            print(f"DEBUG: WorkSchedule still exists after edit - ID {test_id} - Name: {test_name}")
        except:
            print("ERROR: WorkSchedule was deleted during edit operation!")
            sequence.disable_editing_work_schedule()
            return
            
        # SOLUCIÓN INTELIGENTE: Preservar cronograma original en lugar de resetear automáticamente
        try:
            # Refresh ALL schedule-related data
            from ...data.sequence_data import SequenceData
            from ...data.schedule_data import WorkScheduleData
            SequenceData.load()
            WorkScheduleData.load()
            
            props = sequence.get_work_schedule_props()
            current_active_id = props.active_work_schedule_id
            
            # CRÍTICO: Solo resetear si NO hay otros cronogramas disponibles
            # En lugar de resetear automáticamente, buscar un cronograma fallback
            ifc_file = tool.Ifc.get()
            all_schedules = ifc_file.by_type("IfcWorkSchedule")
            
            if all_schedules:
                # Si hay cronogramas disponibles, preferir originales sobre copias
                original_schedules = [ws for ws in all_schedules 
                                    if not (ws.Name and ws.Name.startswith("Copy of "))]
                
                if original_schedules:
                    # Usar el primer cronograma original encontrado
                    fallback_id = original_schedules[0].id()
                    props.active_work_schedule_id = fallback_id
                    props.editing_type = "TASKS"
                    print(f"🎯 EDIT_WORK_SCHEDULE: Preservando cronograma original ID {fallback_id} - '{original_schedules[0].Name}'")
                elif all_schedules:
                    # Si no hay originales, usar cualquier cronograma disponible
                    fallback_id = all_schedules[0].id()
                    props.active_work_schedule_id = fallback_id
                    props.editing_type = "TASKS"
                    print(f"🎯 EDIT_WORK_SCHEDULE: Usando cronograma disponible ID {fallback_id} - '{all_schedules[0].Name}'")
                else:
                    # Solo resetear si realmente no hay cronogramas
                    props.active_work_schedule_id = 0
                    props.editing_type = ""
                    print("ℹ️ EDIT_WORK_SCHEDULE: No hay cronogramas disponibles, reseteando")
            else:
                # Solo resetear si realmente no hay cronogramas
                props.active_work_schedule_id = 0
                props.editing_type = ""
                print("ℹ️ EDIT_WORK_SCHEDULE: No hay cronogramas disponibles, reseteando")
            
            # Force UI update
            import bpy
            for area in bpy.context.screen.areas:
                if area.type in ['PROPERTIES', 'OUTLINER']:
                    area.tag_redraw()
            
            print(f"INFO: WorkSchedule {work_schedule.id()} - UI reset completed successfully")
            
        except Exception as refresh_error:
            print(f"WARNING: Failed to reset UI after edit: {refresh_error}")
            sequence.disable_editing_work_schedule()
            
    except Exception as e:
        print(f"ERROR in edit_work_schedule: {e}")
        import traceback
        traceback.print_exc()
        sequence.disable_editing_work_schedule()


def enable_editing_work_plan_schedules(
    sequence: type[tool.Sequence], work_plan: Optional[ifcopenshell.entity_instance] = None
) -> None:
    sequence.enable_editing_work_plan_schedules(work_plan)


def add_work_schedule(ifc: type[tool.Ifc], sequence: type[tool.Sequence], name: str) -> ifcopenshell.entity_instance:
    res = sequence.get_user_predefined_type()
    if not isinstance(res, tuple) or len(res) != 2:
        # Usuario canceló o UI no disponible: usar defaults
        predefined_type, object_type = "NOTDEFINED", ""
    else:
        predefined_type, object_type = res
    return ifc.run("sequence.add_work_schedule", name=name, predefined_type=predefined_type, object_type=object_type)



def remove_work_schedule(ifc: type[tool.Ifc], work_schedule: ifcopenshell.entity_instance) -> None:
    ifc.run("sequence.remove_work_schedule", work_schedule=work_schedule)


def copy_work_schedule(sequence: type[tool.Sequence], work_schedule: ifcopenshell.entity_instance) -> None:
    sequence.copy_work_schedule(work_schedule)


def assign_work_schedule(
    ifc: type[tool.Ifc], work_plan: ifcopenshell.entity_instance, work_schedule: ifcopenshell.entity_instance
) -> Union[ifcopenshell.entity_instance, None]:
    if work_schedule:
        return ifc.run("aggregate.assign_object", relating_object=work_plan, products=[work_schedule])


def unassign_work_schedule(ifc: type[tool.Ifc], work_schedule: ifcopenshell.entity_instance) -> None:
    ifc.run("aggregate.unassign_object", products=[work_schedule])


def enable_editing_work_schedule(sequence: type[tool.Sequence], work_schedule: ifcopenshell.entity_instance) -> None:
    sequence.load_work_schedule_attributes(work_schedule)
    sequence.enable_editing_work_schedule(work_schedule)

def disable_editing_work_schedule(sequence: type[tool.Sequence]) -> None:
    sequence.disable_editing_work_schedule()

def recalculate_schedule(ifc: type[tool.Ifc], work_schedule: ifcopenshell.entity_instance) -> None:
    ifc.run("sequence.recalculate_schedule", work_schedule=work_schedule)

def create_baseline(
    ifc: type[tool.Ifc],
    sequence: type[tool.Sequence],
    work_schedule: ifcopenshell.entity_instance,
    name: Optional[str] = None,
) -> None:
    ifc.run("sequence.create_baseline", work_schedule=work_schedule, name=name)

def select_work_schedule_products(
    sequence: type[tool.Sequence], spatial: type[tool.Spatial], work_schedule: ifcopenshell.entity_instance
) -> None:
    products = sequence.get_work_schedule_products(work_schedule)
    spatial.select_products(products)


def select_unassigned_work_schedule_products(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], spatial: type[tool.Spatial]
) -> None:
    spatial.deselect_objects()
    products = ifc.get().by_type("IfcElement")
    work_schedule = sequence.get_active_work_schedule()
    schedule_products = sequence.get_work_schedule_products(work_schedule)
    selection = [product for product in products if product not in schedule_products]
    spatial.select_products(selection)







