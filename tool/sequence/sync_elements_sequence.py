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

from .props_sequence import PropsSequence
from .config_sequence import ConfigSequence
import bonsai.tool as tool

class SyncElementsSequence(ConfigSequence):
    """Maneja la funcionalidad de "Sync 3D Elements"."""



    @classmethod
    def sync_3d_elements(cls, work_schedule, property_set_name):
        """
        Sync IFC elements to tasks based on property set values matching task indicators.
        Returns a dict with success status and sync statistics.
        """
        try:
            ifc_file = tool.Ifc.get()
            if not ifc_file:
                return {"success": False, "error": "No IFC file loaded"}

            # Get all tasks from the schedule
            def get_all_tasks_recursive(tasks):
                all_tasks_list = []
                for task in tasks:
                    all_tasks_list.append(task)
                    nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested_tasks:
                        all_tasks_list.extend(get_all_tasks_recursive(nested_tasks))
                return all_tasks_list

            root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
            all_tasks = get_all_tasks_recursive(root_tasks)
            
            if not all_tasks:
                return {"success": False, "error": "No tasks found in schedule"}

            # Build task indicator map
            task_indicators = {}
            for task in all_tasks:
                identification = getattr(task, "Identification", None)
                if identification:
                    task_indicators[identification] = task

            print(f"🎯 Sync3D: Encontradas {len(task_indicators)} tareas con identificación:")
            for identification, task in list(task_indicators.items())[:5]:  # Show first 5
                print(f"  📋 Task ID {task.id()}: '{identification}'")

            if not task_indicators:
                return {"success": False, "error": "No task identifications found"}

            # Get all IFC elements with the specified property set
            matched_elements = 0
            processed_tasks = 0
            elements_checked = 0
            elements_with_pset = 0

            print(f"🔍 Sync3D: Buscando property set '{property_set_name}' en elementos IFC...")

            for element in ifc_file.by_type("IfcProduct"):
                if not hasattr(element, 'GlobalId'):
                    continue
                
                elements_checked += 1

                # Look for the property set
                property_set = None
                if hasattr(element, 'IsDefinedBy') and element.IsDefinedBy:
                    for rel in element.IsDefinedBy:
                        if hasattr(rel, 'RelatingPropertyDefinition'):
                            prop_def = rel.RelatingPropertyDefinition
                            if hasattr(prop_def, 'Name') and prop_def.Name == property_set_name:
                                property_set = prop_def
                                elements_with_pset += 1
                                if elements_with_pset <= 3:  # Log first 3
                                    element_type = getattr(element, 'is_a', lambda: 'Unknown')()
                                    print(f"  ✅ Sync3D: Elemento {element_type} (ID: {element.id()}) tiene property set '{property_set_name}'")
                                break

                if not property_set:
                    continue

                # Get property value that matches a task indicator
                if hasattr(property_set, 'HasProperties'):
                    for prop in property_set.HasProperties:
                        if hasattr(prop, 'NominalValue') and hasattr(prop.NominalValue, 'wrappedValue'):
                            prop_value = str(prop.NominalValue.wrappedValue)
                            prop_name = getattr(prop, 'Name', 'Unknown')
                            
                            if matched_elements < 3:  # Log first few mappings
                                print(f"  🔗 Sync3D: Property '{prop_name}' = '{prop_value}' en elemento {element.id()}")
                            
                            # Find matching task
                            matching_task = task_indicators.get(prop_value)
                            if matching_task:
                                element_type = getattr(element, 'is_a', lambda: 'Unknown')()
                                print(f"  ✅ Sync3D: MATCH! Asignando {element_type} (ID: {element.id()}) → Task '{prop_value}' (ID: {matching_task.id()})")
                                
                                # Assign element to task as output
                                try:
                                    ifcopenshell.api.run("sequence.assign_product", ifc_file,
                                                       relating_product=element, 
                                                       related_object=matching_task)
                                    matched_elements += 1
                                    print(f"  🎯 Sync3D: Asignación exitosa #{matched_elements}")
                                except Exception as e:
                                    print(f"  ❌ Sync3D: Error asignando elemento: {e}")
                                break
                            else:
                                if matched_elements < 5:  # Log first few no-matches
                                    print(f"  ⚠️ Sync3D: No se encontró tarea para valor '{prop_value}'")

            # Count processed tasks
            for task in task_indicators.values():
                outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
                if outputs:
                    processed_tasks += 1

            print(f"📊 Sync3D: RESUMEN:")
            print(f"  - Elementos revisados: {elements_checked}")
            print(f"  - Elementos con property set '{property_set_name}': {elements_with_pset}")
            print(f"  - Elementos asignados a tareas: {matched_elements}")
            print(f"  - Tareas con elementos asignados: {processed_tasks}")

            # CRÍTICO: Limpiar datos de perfiles corruptos antes del retorno
            # Esto asegura que cuando restore_all_ui_state() se ejecute, 
            # no restaure valores '0' problemáticos
            print(f"🧹 Sync3D: Limpiando datos de perfiles corruptos en cronograma")
            cls._clean_and_update_ColorType_snapshot_for_schedule(work_schedule)
            
            return {
                "success": True,
                "matched_elements": matched_elements,
                "processed_tasks": processed_tasks
            }

        except Exception as e:
            return {"success": False, "error": str(e)}