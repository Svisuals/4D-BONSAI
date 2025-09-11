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
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    import ifcopenshell
    import bonsai.tool as tool


def load_animation_color_scheme(
    sequence: type[tool.Sequence], scheme: Union[ifcopenshell.entity_instance, None]
) -> None:
    sequence.load_animation_color_scheme(scheme)


def guess_date_range(sequence: type[tool.Sequence], work_schedule: ifcopenshell.entity_instance) -> None:
    start, finish = sequence.guess_date_range(work_schedule)
    sequence.update_visualisation_date(start, finish)

def add_task_bars(sequence: "type[tool.Sequence]") -> set[str]:
    """Genera las barras visuales para las tareas seleccionadas.

    - Synchronizes `has_bar_visual` from tree with `props.task_bars` (JSON).
    - Calls `sequence.refresh_task_bars()` to create/delete bars in viewport.
    - Devuelve {'FINISHED'} para mantener la semántica estilo operador.
    """
    # Update has_bar_visual synchronization with task_bars
    task_tree = sequence.get_task_tree_props()
    selected_tasks = []

    for task in getattr(task_tree, "tasks", []):
        try:
            tid = int(task.ifc_definition_id)
        except Exception:
            continue

        if getattr(task, "has_bar_visual", False):
            selected_tasks.append(tid)
            sequence.add_task_bar(tid)
        else:
            sequence.remove_task_bar(tid)

    # Generate/update visual bars
    sequence.refresh_task_bars()

    return {"FINISHED"}



def load_default_animation_color_scheme(sequence: type[tool.Sequence]) -> None:
    sequence.load_default_animation_color_scheme()



def visualise_work_schedule_date_range(
    sequence: type[tool.Sequence], work_schedule: ifcopenshell.entity_instance
) -> None:
    """
    Creates 4D animation using ONLY the Animation Color Schemes system.
    No fallback to old system - if no ColorTypes exist, creates DEFAULT.

    Proceso:
    1. Limpia animaciones previas
    2. Calculates time configuration
    3. Verifies/creates DEFAULT group if necessary
    4. Generates frames with state information
    5. Applies animation with ColorTypes
    6. Agrega elementos adicionales (timeline, barras)
    """

    # Clear any previous animation
    sequence.clear_objects_animation(include_blender_objects=False)

    # Get time configuration (dates, frames, speed)
    settings = sequence.get_animation_settings()
    if not settings:
        print("❌ Error: Could not calculate animation configuration")
        return


    # NUEVO: Validar rango de fechas
    import ifcopenshell.util.sequence
    all_tasks = []
    for root_task in ifcopenshell.util.sequence.get_root_tasks(work_schedule):
        all_tasks.extend(ifcopenshell.util.sequence.get_all_nested_tasks(root_task))
    
    # Verificar tareas fuera de rango
    out_of_range_count = 0
    earliest_task_date = None
    latest_task_date = None
    
    for task in all_tasks:
        start = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
        finish = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
        
        if start and finish:
            if not earliest_task_date or start < earliest_task_date:
                earliest_task_date = start
            if not latest_task_date or finish > latest_task_date:
                latest_task_date = finish
                
            if finish < settings["start"] or start > settings["finish"]:
                out_of_range_count += 1
    
    # Advertir si hay discrepancias
    if earliest_task_date and earliest_task_date < settings["start"]:
        print(f"⚠️ Warning: Earliest task starts {(settings['start'] - earliest_task_date).days} days before visualization range")
    if latest_task_date and latest_task_date > settings["finish"]:
        print(f"⚠️ Warning: Latest task ends {(latest_task_date - settings['finish']).days} days after visualization range")
    if out_of_range_count > 0:
        print(f"⚠️ {out_of_range_count} tasks are completely outside the visualization range")
    # Get animation properties
    animation_props = sequence.get_animation_props()

    # If no groups configured, create and use DEFAULT
    if not animation_props.animation_group_stack:
        print("⚠️ No ColorType groups configured")
        print("   Creating DEFAULT group automatically...")

        # Create DEFAULT group with basic ColorTypes
        sequence.create_default_ColorType_group()

        # Agregar DEFAULT al stack de animación
        item = animation_props.animation_group_stack.add()
        item.group = "DEFAULT"
        item.enabled = True

        print("✅ Grupo DEFAULT agregado al stack")

    # Generate frame information with states
    print(f"📊 Procesando tareas del cronograma...")
    product_frames = sequence.get_animation_product_frames_enhanced(
        work_schedule, settings
    )

    if not product_frames:
        print("⚠️ No se encontraron productos para animar")
        return

    print(f"✅ {len(product_frames)} productos encontrados")

    # ALWAYS use ColorType system (no fallback)
    print(f"🎬 Applying animation with Animation Color Schemes...")
    sequence.animate_objects_with_ColorTypes(settings, product_frames)

    # Agregar elementos adicionales
    sequence.add_text_animation_handler(settings)  # Timeline con fecha
    add_task_bars(sequence)  # Barras de Gantt (opcional)
    sequence.set_object_shading()  # Configure view for colors

    print(f"✅ Animation created: {settings['total_frames']:.0f} frames")
    print(f"   Desde: {settings['start'].strftime('%Y-%m-%d')}")
    print(f"   Hasta: {settings['finish'].strftime('%Y-%m-%d')}")

def visualise_work_schedule_date(sequence: type[tool.Sequence], work_schedule: ifcopenshell.entity_instance) -> None:
    """Visualizes the schedule state at a specific date.
    CORRECCIÓN: Procesa TODOS los elementos visibles, no solo los activos."""
    # Clear keyframes and previous visual states is crucial for clean snapshot.
    sequence.clear_objects_animation(include_blender_objects=True)

    # Parsear la fecha de visualización
    props = sequence.get_work_schedule_props()
    date_text = props.visualisation_start
    if not date_text:
        return
    try:
        from dateutil import parser
        current_date = parser.parse(date_text, yearfirst=True, fuzzy=True)
    except Exception:
        return

    # Process ALL states up to current date
    product_states = sequence.process_construction_state(work_schedule, current_date)

    # Apply snapshot with correct ColorTypes
    sequence.show_snapshot(product_states)

    # Asegurar que los colores sean visibles
    sequence.set_object_shading()


def clear_previous_animation(sequence: type[tool.Sequence]) -> None:
    sequence.clear_objects_animation(include_blender_objects=False)


def add_animation_camera(sequence: type[tool.Sequence]) -> None:
    sequence.add_animation_camera()


def save_animation_color_scheme(sequence: type[tool.Sequence], name: str) -> None:
    sequence.save_animation_color_scheme(name)


def generate_gantt_chart(sequence: type[tool.Sequence], work_schedule: ifcopenshell.entity_instance) -> None:
    """Generates the task data and sends it to the web UI for Gantt chart rendering."""
    json_data = sequence.create_tasks_json(work_schedule)
    sequence.generate_gantt_browser_chart(json_data, work_schedule)







