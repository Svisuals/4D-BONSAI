# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021, 2022 Dion Moult <dion@thinkmoult.com>, Yassine Oualid <yassine@sigmadimensions.com>, Federico Eraso <feraso@svisuals.net
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
import bpy
import json
from datetime import datetime
from typing import Any, List
import ifcopenshell
import bonsai.tool as tool
# Try to import SequenceCache for optimization, fallback if not available
try:
    from bonsai.bim.module.sequence.data import SequenceCache
except ImportError:
    try:
        import bonsai.data
        SequenceCache = bonsai.data.SequenceCache
    except ImportError:
        # Fallback: Create a dummy SequenceCache that returns None
        class SequenceCache:
            @staticmethod
            def get_vectorized_task_states(*args, **kwargs):
                return None
            @staticmethod
            def get_schedule_dates(*args, **kwargs):
                return None
            @staticmethod
            def get_task_products(*args, **kwargs):
                return None

class SnapshotSequence:
    """Mixin class for processing and displaying construction state snapshots."""

    to_build = set()
    in_construction = set()
    completed = set()
    to_demolish = set()
    in_demolition = set()
    demolished = set()


    @classmethod
    def process_construction_state(
        cls,
        work_schedule: ifcopenshell.entity_instance,
        date: datetime,
        viz_start: datetime = None,
        viz_finish: datetime = None,
        date_source: str = "SCHEDULE") -> dict[str, Any]:
        """
        OPTIMIZED: Processes states considering the configured visualization range.
        Now uses cached data structures for massive performance improvement.

        Args:
            work_schedule: Work schedule
            date: Fecha actual del snapshot
            viz_start: Visualization start date (optional)
            date_source: El tipo de fecha a usar ('SCHEDULE', 'ACTUAL', etc.)
            viz_finish: Visualization end date (optional)
        """
        # Initialize state sets
        cls.to_build = set()
        cls.in_construction = set()
        cls.completed = set()
        cls.to_demolish = set()
        cls.in_demolition = set()
        cls.demolished = set()

        # SAFE OPTIMIZATION: Try NumPy vectorized computation with robust fallbacks
        work_schedule_id = work_schedule.id()
        optimization_used = None
        
        try:
            # ULTRA-FAST PATH: NumPy vectorized computation
            vectorized_result = SequenceCache.get_vectorized_task_states(
                work_schedule_id, date, date_source, viz_start, viz_finish
            )
            
            if vectorized_result and vectorized_result.get('vectorized'):
                # SUCCESS: Use NumPy vectorized operations
                cls.to_build = vectorized_result["TO_BUILD"]
                cls.in_construction = vectorized_result["IN_CONSTRUCTION"] 
                cls.completed = vectorized_result["COMPLETED"]
                cls.to_demolish = vectorized_result.get("TO_DEMOLISH", set())
                cls.in_demolition = vectorized_result.get("IN_DEMOLITION", set())
                cls.demolished = vectorized_result.get("DEMOLISHED", set())
                optimization_used = f"NumPy vectorized: {vectorized_result['tasks_processed']} tasks, {vectorized_result['products_processed']} products"
                print(f"[OPTIMIZED] {optimization_used}")
                return  # Early return - optimization successful
        except Exception as e:
            print(f"[WARNING]️ NumPy optimization failed (safe fallback): {e}")
        
        # FAST FALLBACK PATH: Use cached data if available
        try:
            cached_dates = SequenceCache.get_schedule_dates(work_schedule_id, date_source)
            cached_products = SequenceCache.get_task_products(work_schedule_id)
            
            if cached_dates and cached_products:
                # CACHED OPTIMIZATION: Process using cached data (faster than full iteration)
                tasks_data = cached_dates.get('tasks_dates', [])
                optimization_used = f"Cached data: {len(tasks_data)} tasks from cache"
                print(f"[FAST] {optimization_used}")
                
                # Process cached data efficiently
                for task_id, start_date, finish_date in tasks_data:
                    if not start_date or not finish_date:
                        continue
                        
                    # Apply visualization range filtering first (if any)
                    if viz_start and viz_finish:
                        if finish_date < viz_start:
                            # Task completed before visualization range
                            cls.completed.update(cached_products.get(task_id, []))
                            continue
                        elif start_date > viz_finish:
                            # Task starts after visualization range - skip
                            continue
                    
                    # Normal date-based state determination
                    if start_date > date:
                        cls.to_build.update(cached_products.get(task_id, []))
                    elif finish_date < date:
                        cls.completed.update(cached_products.get(task_id, []))
                    else:
                        cls.in_construction.update(cached_products.get(task_id, []))
                
                return  # Early return - cached optimization successful
        except Exception as e:
            print(f"[WARNING]️ Cache optimization failed (safe fallback): {e}")
        
        # TRADITIONAL FALLBACK PATH: Use original logic if optimizations fail
        print("🔄 Using original processing logic")
        for rel in work_schedule.Controls or []:
            for related_object in rel.RelatedObjects:
                if related_object.is_a("IfcTask"):
                    cls.process_task_status(related_object, date, viz_start, viz_finish, date_source=date_source)

        return {
            "TO_BUILD": cls.to_build,
            "IN_CONSTRUCTION": cls.in_construction,
            "COMPLETED": cls.completed,
            "TO_DEMOLISH": cls.to_demolish,
            "IN_DEMOLITION": cls.in_demolition,
            "DEMOLISHED": cls.demolished,
        }

    @classmethod 
    def _process_task_status_cached(
        cls,
        task_id: int,
        product_ids: List[int], 
        start_date: datetime,
        finish_date: datetime,
        current_date: datetime,
        viz_start: datetime = None,
        viz_finish: datetime = None
    ):
        """
        NEW: Fast version of task status processing using cached data.
        This eliminates the need to traverse IFC relationships repeatedly.
        """
        if not product_ids:
            return
        
        # Apply visualization range filtering
        if viz_start and finish_date < viz_start:
            # Task finished before visualization range - outputs completed, inputs demolished
            cls.completed.update(product_ids)
            return
            
        if viz_finish and start_date > viz_finish:
            # Task starts after visualization range - skip entirely
            return
        
        # Normal status logic based on current date
        if current_date < start_date:
            # Task hasn't started - inputs ready to build, outputs to be demolished
            cls.to_build.update(product_ids)
        elif start_date <= current_date <= finish_date:
            # Task in progress - products in construction/demolition
            cls.in_construction.update(product_ids)
        else:  # current_date > finish_date
            # Task completed - outputs built, inputs demolished
            cls.completed.update(product_ids)

    @classmethod
    def process_task_status(
        cls,
        task: ifcopenshell.entity_instance,
        date: datetime,
        viz_start: datetime = None,
        viz_finish: datetime = None,
        date_source: str = "SCHEDULE"
    ) -> None:
        """
        CORRECTION: Processes a task's state considering the visualization range.

        Lógica corregida:
        1. Tareas que terminan antes de viz_start: outputs completados, inputs demolidos
        2. Tareas que empiezan después de viz_finish: NO aparecen (se omiten)
        3. Tareas dentro del rango: lógica normal basada en la fecha actual
        """
        # Procesar tareas anidadas recursivamente
        for rel in task.IsNestedBy or []: # type: ignore
            [cls.process_task_status(related_object, date, viz_start, viz_finish, date_source=date_source) for related_object in rel.RelatedObjects]

        # --- Use the selected date source ---
        start_date_type = f"{date_source.capitalize()}Start"
        finish_date_type = f"{date_source.capitalize()}Finish"

        start = ifcopenshell.util.sequence.derive_date(task, start_date_type, is_earliest=True)
        finish = ifcopenshell.util.sequence.derive_date(task, finish_date_type, is_latest=True)

        if not start or not finish:
            return

        outputs = ifcopenshell.util.sequence.get_task_outputs(task) or []
        inputs = cls.get_task_inputs(task) or []

        # Consider visualization range

        # 1. Task starts after the end of visualization -> DO NOT SHOW
        if viz_finish and start > viz_finish:
            # Estas tareas no deben aparecer en absoluto
            return

        # 2. Task ends before the start of visualization -> SHOW AS COMPLETED
        if viz_start and finish < viz_start:
            # Outputs completados (visibles), inputs demolidos (ocultos)
            [cls.completed.add(tool.Ifc.get_object(output)) for output in outputs]
            [cls.demolished.add(tool.Ifc.get_object(input)) for input in inputs]
            return

        # 3. Task within the visualization range -> NORMAL LOGIC
        # (Also includes tasks that partially extend outside the range)

        if date < start:
            # Before start: hidden outputs, visible inputs
            [cls.to_build.add(tool.Ifc.get_object(output)) for output in outputs]
            [cls.to_demolish.add(tool.Ifc.get_object(input)) for input in inputs]
        elif date <= finish:
            # During execution
            [cls.in_construction.add(tool.Ifc.get_object(output)) for output in outputs]
            [cls.in_demolition.add(tool.Ifc.get_object(input)) for input in inputs]
        else:
            # After finishing: outputs remain visible, inputs disappear
            [cls.completed.add(tool.Ifc.get_object(output)) for output in outputs]
            [cls.demolished.add(tool.Ifc.get_object(input)) for input in inputs]


    @classmethod
    def show_snapshot(cls, product_states):
        """
        Muestra un snapshot visual de todos los objetos IFC en la fecha especificada.
        Esta función es autocontenida y robusta, similar a la lógica de v30.
        """

        import bpy
        import json

        # Solo guardar si no existen ya colores originales guardados
        if not bpy.context.scene.get('BIM_VarianceOriginalObjectColors'):
            cls._save_original_object_colors()

        original_properties = {}
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                # Intentar obtener el color del material IFC original primero
                original_color = None
                try:
                    if obj.material_slots and obj.material_slots[0].material:
                        material = obj.material_slots[0].material
                        if material.use_nodes:
                            principled = tool.Blender.get_material_node(material, "BSDF_PRINCIPLED")
                            if principled and principled.inputs.get("Base Color"):
                                base_color = principled.inputs["Base Color"].default_value
                                original_color = [base_color[0], base_color[1], base_color[2], base_color[3]]
                except Exception:
                    pass

                # Fallback: usar el color actual del viewport si no se pudo obtener del material
                if original_color is None:
                    original_color = list(obj.color)

                original_properties[obj.name] = {
                    "color": original_color,
                    "hide_viewport": obj.hide_viewport,
                    "hide_render": obj.hide_render,
                }
        # We save the state in a different property to not overwrite the animation one.
        bpy.context.scene['bonsai_snapshot_original_props'] = json.dumps(original_properties)
        print(f"📸 Se ha guardado el estado original de {len(original_properties)} objetos para el snapshot.")
        # --- END OF MODIFICATION ---

        # 1. Limpiar keyframes
        for obj in bpy.data.objects:
            if getattr(obj, "animation_data", None):
                obj.animation_data_clear()

        # 2. Obtener la fecha del snapshot y la fuente de fechas desde la UI
        ws_props = cls.get_work_schedule_props()
        snapshot_date_str = getattr(ws_props, "visualisation_start", None)
        if not snapshot_date_str or snapshot_date_str == "-":
            print("Snapshot abortado: no se ha establecido una fecha.")
            return
        try:
            snapshot_date = cls.parse_isodate_datetime(snapshot_date_str)
        except Exception:
            print(f"Snapshot abortado: fecha inválida '{snapshot_date_str}'.")
            return
        date_source = getattr(ws_props, "date_source_type", "SCHEDULE")

        # 3. Determinar el grupo de perfiles activo desde el Animation Stack
        anim_props = cls.get_animation_props()
        active_group_name = None
        for item in anim_props.animation_group_stack:
            if item.enabled and item.group:
                active_group_name = item.group
                break
        if not active_group_name:
            active_group_name = "DEFAULT"
        print(f"📸 Snapshot usando grupo '{active_group_name}' para fecha '{snapshot_date.strftime('%Y-%m-%d')}'")

        # 4. Procesar cada objeto IFC en la escena
        applied_count = 0
        for obj in bpy.data.objects:
            element = tool.Ifc.get_entity(obj)
            if not element or not obj.type == 'MESH':
                continue

            task = cls.get_task_for_product(element)
            if not task:
                # Si no tiene tarea, ocultarlo para un snapshot limpio
                obj.hide_viewport = True
                obj.hide_render = True
                continue

            # Determinar estado del objeto en la fecha del snapshot
            start_attr = f"{date_source.capitalize()}Start"
            finish_attr = f"{date_source.capitalize()}Finish"
            task_start = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
            task_finish = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)

            if not task_start or not task_finish:
                obj.hide_viewport = True
                obj.hide_render = True
                continue

            state = ""
            if snapshot_date < task_start:
                state = "start"
            elif task_start <= snapshot_date <= task_finish:
                state = "in_progress"
            else: # snapshot_date > task_finish
                state = "end"

            # Obtener el perfil de color correcto
            ColorType = cls.get_assigned_ColorType_for_task(task, anim_props, active_group_name)
            original_color = original_properties.get(obj.name, {}).get("color", [1,1,1,1])

            # PRIORITY MODE CHECK for snapshot
            consider_start = getattr(ColorType, 'consider_start', False)
            consider_active = getattr(ColorType, 'consider_active', True)
            consider_end = getattr(ColorType, 'consider_end', True)
            is_priority_mode = (consider_start and not consider_active and not consider_end)

            # Aplicar apariencia
            is_demolition = (getattr(task, "PredefinedType", "") or "").upper() in {"DEMOLITION", "REMOVAL", "DISPOSAL", "DISMANTLE"}
            is_construction = not is_demolition

            if is_priority_mode:
                # PRIORITY MODE: START solo activado - siempre aplicar estado START
                print(f"🔍 SNAPSHOT PRIORITY MODE: {obj.name} using START state regardless of date")
                obj.hide_viewport = False  # Siempre visible en priority mode
                state = "start"  # Force START state for coloring
            else:
                # NORMAL MODE: Apply consider flags logic
                if state == "start":
                    if consider_start:
                        # START activado: mostrar objeto en estado START
                        obj.hide_viewport = False
                    else:
                        # START disabled: apply traditional logic
                        if is_construction:
                            obj.hide_viewport = True  # Hide construction elements if consider_start=False
                        else:
                            obj.hide_viewport = False # Demolition elements remain visible
                elif state == "in_progress" and not consider_active:
                    obj.hide_viewport = True  # Ocultar durante fase activa si consider_active=False
                elif state == "end":
                    if not consider_end:
                        obj.hide_viewport = True  # Ocultar al final si consider_end=False
                    elif getattr(ColorType, 'hide_at_end', False):
                        obj.hide_viewport = True  # Ocultar al final si hide_at_end=True
                    else:
                        obj.hide_viewport = False  # Visible al final
                else:
                    # Apply traditional demolition vs construction logic
                    if is_demolition:
                        if state == "start": obj.hide_viewport = False # Visible antes de demoler
                        elif state == "in_progress": obj.hide_viewport = False # Visible during demolition
                        else: obj.hide_viewport = True # Hidden after demolition
                    else: # Construction
                        if state == "start": obj.hide_viewport = True # Oculto antes de construir
                        else: obj.hide_viewport = False # Visible during and after

            # Color logic (only if visible)
            if not obj.hide_viewport:
                color_to_apply = original_color
                transparency = 0.0  # Valor por defecto

                if state == "start":
                    if not getattr(ColorType, 'use_start_original_color', False):
                        color_to_apply = list(ColorType.start_color)
                    transparency = getattr(ColorType, 'start_transparency', 0.0)
                elif state == "in_progress":
                    if not getattr(ColorType, 'use_active_original_color', False):
                        color_to_apply = list(ColorType.in_progress_color)
                    transparency = getattr(ColorType, 'active_start_transparency', 0.0)
                else: # end
                    if getattr(ColorType, 'hide_at_end', False):
                        obj.hide_viewport = True
                    elif not getattr(ColorType, 'use_end_original_color', True):
                        color_to_apply = list(ColorType.end_color)
                    transparency = getattr(ColorType, 'end_transparency', 0.0)

                if not obj.hide_viewport:
                
                    # Calcular alpha desde transparencia (igual que en live update)
                    alpha = 1.0 - transparency
                    # Asegurar que el color tenga 3 componentes RGB
                    color_rgb = list(color_to_apply[:3])
                    while len(color_rgb) < 3:
                        color_rgb.append(1.0)
                    # Aplicar color con transparencia calculada
                    obj.color = (color_rgb[0], color_rgb[1], color_rgb[2], alpha)
                

            obj.hide_render = obj.hide_viewport
            applied_count += 1

        # 5. Configurar el 3D view
        cls.set_object_shading()
        print(f"[OK] Snapshot aplicado. {applied_count} objetos procesados.")

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