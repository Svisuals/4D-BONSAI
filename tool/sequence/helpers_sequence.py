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
from collections.abc import Iterable
from typing import Union

# Importaciones internas
import bonsai.tool as tool

class HelpersSequence:
    """Colección de funciones auxiliares generales para la gestión de secuencias."""

    @classmethod
    def set_object_shading(cls):
            area = tool.Blender.get_view3d_area()
            if area:
                # Use area.spaces.active for stability in newer Blender versions
                space = area.spaces.active
                if space and space.type == 'VIEW_3D':
                    space.shading.color_type = "OBJECT"

    @classmethod
    def select_products(cls, products: Iterable[ifcopenshell.entity_instance]) -> None:
        [obj.select_set(False) for obj in bpy.context.selected_objects]
        for product in products:
            obj = tool.Ifc.get_object(product)
            obj.select_set(True) if obj else None

    @classmethod
    def find_related_input_tasks(cls, product):
        related_tasks = []
        for assignment in product.HasAssignments:
            if assignment.is_a("IfcRelAssignsToProcess") and assignment.RelatingProcess.is_a("IfcTask"):
                related_tasks.append(assignment.RelatingProcess)
        return related_tasks

    @classmethod
    def find_related_output_tasks(cls, product):
        related_tasks = []
        for reference in product.ReferencedBy:
            if reference.is_a("IfcRelAssignsToProduct") and reference.RelatedObjects[0].is_a("IfcTask"):
                related_tasks.append(reference.RelatedObjects[0])
        return related_tasks

    @classmethod
    def are_entities_same_class(cls, entities: list[ifcopenshell.entity_instance]) -> bool:
        if not entities:
            return False
        if len(entities) == 1:
            return True
        first_class = entities[0].is_a()
        for entity in entities:
            if entity.is_a() != first_class:
                return False
        return True


    @classmethod
    def validate_task_object(cls, task, operation_name="operation"):
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


    @classmethod
    def get_work_schedule_products(cls, work_schedule: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
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

    @classmethod
    def select_work_schedule_products(cls, work_schedule: ifcopenshell.entity_instance) -> str:
        """
        Selecciona todos los productos asociados a un cronograma de trabajo.

        Args:
            work_schedule: El cronograma de trabajo IFC

        Returns:
            Mensaje de resultado
        """
        try:
            products = cls.get_work_schedule_products(work_schedule)

            if not products:
                return "No products found in work schedule"

            # Usar la función segura de spatial para seleccionar productos
            tool.Spatial.select_products(products)

            return f"Selected {len(products)} products from work schedule"

        except Exception as e:
            print(f"Error selecting work schedule products: {e}")
            return f"Error selecting products: {str(e)}"

    @classmethod
    def select_unassigned_work_schedule_products(cls) -> str:
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
                ws_products = cls.get_work_schedule_products(work_schedule) or []
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

    @classmethod
    def copy_task_colortype_config(cls):
        """
        Copy ColorType configuration from the active task to selected tasks.
        """
        try:
            # Get task tree properties
            tprops = cls.get_task_tree_props()
            if not tprops or not tprops.tasks:
                print("Warning: No task tree properties found")
                return

            # Get work schedule properties to find active task
            ws_props = cls.get_work_schedule_props()
            if not ws_props or ws_props.active_task_index < 0 or ws_props.active_task_index >= len(tprops.tasks):
                print("Warning: No active task found")
                return

            # Get the source task (active task)
            source_task = tprops.tasks[ws_props.active_task_index]
            print(f"Source task: {getattr(source_task, 'name', 'Unknown')} (ID: {source_task.ifc_definition_id})")

            # Get selected tasks (tasks with is_selected = True)
            selected_tasks = [task for task in tprops.tasks if getattr(task, 'is_selected', False)]
            if not selected_tasks:
                print("Warning: No tasks selected to copy to")
                return

            print(f"Found {len(selected_tasks)} selected tasks to copy to")

            # Copy configuration from source to selected tasks
            copied_count = 0
            for target_task in selected_tasks:
                if target_task.ifc_definition_id == source_task.ifc_definition_id:
                    continue  # Skip copying to self

                try:
                    # Copy main colortype settings
                    target_task.use_active_colortype_group = getattr(source_task, 'use_active_colortype_group', False)
                    target_task.selected_colortype_in_active_group = getattr(source_task, 'selected_colortype_in_active_group', "")
                    
                    # Copy animation_color_schemes if it exists
                    if hasattr(target_task, 'animation_color_schemes') and hasattr(source_task, 'animation_color_schemes'):
                        target_task.animation_color_schemes = source_task.animation_color_schemes

                    # Copy colortype group choices
                    target_task.colortype_group_choices.clear()
                    for source_group in source_task.colortype_group_choices:
                        target_group = target_task.colortype_group_choices.add()
                        target_group.group_name = source_group.group_name
                        target_group.enabled = source_group.enabled
                        
                        # Copy the selected value using the appropriate attribute
                        for attr_candidate in ("selected_colortype", "selected", "active_colortype", "colortype"):
                            if hasattr(source_group, attr_candidate) and hasattr(target_group, attr_candidate):
                                setattr(target_group, attr_candidate, getattr(source_group, attr_candidate))
                                break

                    copied_count += 1
                    print(f"Copied configuration to task: {getattr(target_task, 'name', 'Unknown')} (ID: {target_task.ifc_definition_id})")

                except Exception as e:
                    print(f"Error copying to task {target_task.ifc_definition_id}: {e}")

            print(f"Successfully copied ColorType configuration to {copied_count} tasks")

        except Exception as e:
            print(f"Error in copy_task_colortype_config: {e}")
            import traceback
            traceback.print_exc()


    @classmethod
    def set_visibility_by_status(cls, visible_statuses: set[str]) -> None:
        """
        Hides or shows objects based on their IFC status property.
        """
        import bpy
        import ifcopenshell.util.element
        import bonsai.tool as tool

        ifc_file = tool.Ifc.get()
        if not ifc_file:
            return

        all_products = ifc_file.by_type("IfcProduct")
        for product in all_products:
            obj = tool.Ifc.get_object(product)
            if not obj:
                continue

            current_status = "No Status"
            psets = ifcopenshell.util.element.get_psets(product)
            for pset_name, pset_props in psets.items():
                if "Status" in pset_props:
                    if pset_name.startswith("Pset_") and pset_name.endswith("Common"):
                        current_status = pset_props["Status"]
                        break
                    elif pset_name == "EPset_Status":
                        current_status = pset_props["Status"]
                        break
            
            obj.hide_viewport = current_status not in visible_statuses
            obj.hide_render = current_status not in visible_statuses


    @classmethod
    def get_tasks_for_product(cls, product, work_schedule=None):
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

    @classmethod
    def load_product_related_tasks(cls, product):
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


    @classmethod
    def get_task_for_product(cls, product):
        """Obtiene la tarea asociada a un producto IFC."""
        element = tool.Ifc.get_entity(product) if hasattr(product, 'name') else product
        if not element:
            return None

        # Search in outputs
        for rel in element.ReferencedBy or []:
            if rel.is_a("IfcRelAssignsToProduct"):
                for task in rel.RelatedObjects:
                    if task.is_a("IfcTask"):
                        return task

        # Search in inputs
        for rel in element.HasAssignments or []:
            if rel.is_a("IfcRelAssignsToProcess"):
                task = rel.RelatingProcess
                if task.is_a("IfcTask"):
                    return task

        return None

    @classmethod
    def get_work_schedule(cls, task: ifcopenshell.entity_instance) -> Union[ifcopenshell.entity_instance, None]:
        for rel in task.HasAssignments or []:
            if rel.is_a("IfcRelAssignsToControl") and rel.RelatingControl.is_a("IfcWorkSchedule"):
                return rel.RelatingControl
        for rel in task.Nests or []:
            return cls.get_work_schedule(rel.RelatingObject)

    @classmethod
    def is_work_schedule_active(cls, work_schedule):
        props = cls.get_work_schedule_props()
        return True if work_schedule.id() == props.active_work_schedule_id else False










