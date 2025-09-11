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
from typing import TYPE_CHECKING, Optional

# Import animation functions with fallback
try:
    from ..prop.animation import UnifiedColorTypeManager
except ImportError:
    # Fallback for when running from the original location
    try:
        from .prop.animation import UnifiedColorTypeManager
    except ImportError:
        # Ultimate fallback - create dummy class
        class UnifiedColorTypeManager:
            @staticmethod
            def sync_default_colortype_for_task(task_pg, predefined_type):
                pass

if TYPE_CHECKING:
    import bpy
    import ifcopenshell
    import bonsai.tool as tool

def enable_editing_work_schedule_tasks(
    sequence: type[tool.Sequence], work_schedule: ifcopenshell.entity_instance
) -> None:
    # Only set active schedule, DO NOT load task tree immediately
    # El operador manejará la secuencia correcta: callback → load_task_tree → restore
    # The operator will handle the correct sequence: callback → load_task_tree → restore
    sequence.enable_editing_work_schedule_tasks(work_schedule)


def load_task_tree(sequence: type[tool.Sequence], work_schedule) -> None:
    sequence.load_task_tree(work_schedule)
    sequence.load_task_properties()

def remove_task(ifc: type[tool.Ifc], sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> None:
    ifc.run("sequence.remove_task", task=task)
    work_schedule = sequence.get_active_work_schedule()
    sequence.load_task_tree(work_schedule)
    sequence.load_task_properties()
    sequence.disable_selecting_deleted_task()


def load_task_properties(sequence: type[tool.Sequence]) -> None:
    sequence.load_task_properties()


def add_summary_task(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], work_schedule: ifcopenshell.entity_instance
) -> None:
    ifc.run("sequence.add_task", work_schedule=work_schedule)
    sequence.load_task_tree(work_schedule)
    sequence.load_task_properties()


def add_task(
    ifc: type[tool.Ifc], sequence: type[tool.Sequence], parent_task: Optional[ifcopenshell.entity_instance] = None
) -> None:
    ifc.run("sequence.add_task", parent_task=parent_task)
    work_schedule = sequence.get_active_work_schedule()
    sequence.load_task_tree(work_schedule)
    sequence.load_task_properties()


def enable_editing_task_attributes(sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> None:
    sequence.load_task_attributes(task)
    sequence.enable_editing_task_attributes(task)


def _auto_sync_task_predefined_type(task_id: int, predefined_type: str) -> None:
    """
    Synchronizes the PredefinedType with the task's DEFAULT ColorType AND FORCES UI REDRAW.
    """
    try:
        import bpy
        import bonsai.tool as tool
        # UnifiedColorTypeManager is already imported at module level

        # 1. Find the task in UI properties (task_pg)
        tprops = sequence.get_task_tree_props()
        task_pg = next((t for t in tprops.tasks if t.ifc_definition_id == task_id), None)

        if task_pg:
            # 2. Call central logic to update the data
            UnifiedColorTypeManager.sync_default_group_to_predefinedtype(bpy.context, task_pg)
            print(f"✅ Auto-Sync: Task {task_id} updated to DEFAULT ColorType '{predefined_type}'.")

            # 3. THE KEY PART! Force Properties UI redraw.
            # Blender doesn't always detect changes in nested collections, so we force it.
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'PROPERTIES':
                        area.tag_redraw()

    except Exception as e:
        print(f"❌ ERROR en _auto_sync_task_predefined_type: {e}")


def edit_task(ifc: type[tool.Ifc], sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> None:
    """Edits a task, reloads data and triggers DEFAULT ColorType synchronization."""
    attributes = sequence.get_task_attributes()
    old_predefined = getattr(task, "PredefinedType", "NOTDEFINED") or "NOTDEFINED"

    # 1. Save changes to the IFC file
    ifc.run("sequence.edit_task", task=task, attributes=attributes)

    # 2. Reload data from IFC so cache is updated
    try:
        from ...data.sequence_data import SequenceData
    except ImportError:
        # Fallback for different import structures
        try:
            from ....data.sequence_data import SequenceData
        except ImportError:
            # If data module is not available, skip the reload step
            print("⚠️ SequenceData module not available, skipping data reload")
            return
    SequenceData.load() # Complete reload to ensure consistency
    sequence.load_task_properties(task=task)

    # 3. Trigger synchronization if PredefinedType changed
    new_predefined = attributes.get("PredefinedType", old_predefined)
    if new_predefined != old_predefined:
        _auto_sync_task_predefined_type(task.id(), new_predefined)

    sequence.disable_editing_task()


def copy_task_attribute(ifc: type[tool.Ifc], sequence: type[tool.Sequence], attribute_name: str) -> None:
    for task in sequence.get_checked_tasks():
        ifc.run(
            "sequence.edit_task",
            task=task,
            attributes={attribute_name: sequence.get_task_attribute_value(attribute_name)},
        )
        sequence.load_task_properties(task)


def duplicate_task(ifc: type[tool.Ifc], sequence: type[tool.Sequence], task: ifcopenshell.entity_instance) -> None:
    ifc.run("sequence.duplicate_task", task=task)
    work_schedule = sequence.get_active_work_schedule()
    sequence.load_task_tree(work_schedule)
    sequence.load_task_properties()


def disable_editing_task(sequence: type[tool.Sequence]) -> None:
    sequence.disable_editing_task()


def refresh_task_output_counts(SequenceTool, work_schedule=None):
    """
    Recalcula de forma segura los contadores de 'Outputs' por tarea.
    Es un shim para evitar AttributeError si la lógica real vive en tool.Sequence.
    """
    try:
        ws = work_schedule or SequenceTool.get_active_work_schedule()
    except Exception:
        ws = None
    try:
        # Si la herramienta ya tiene el método nativo, usarlo
        if hasattr(SequenceTool, "refresh_task_output_counts"):
            if ws is not None:
                SequenceTool.refresh_task_output_counts(ws)
            else:
                SequenceTool.refresh_task_output_counts()
        else:
            # Reasonable fallback: reload tree and properties
            if ws is not None:
                SequenceTool.load_task_tree(ws)
            SequenceTool.load_task_properties()
    except Exception as e:
        print(f"Bonsai WARNING: refresh_task_output_counts shim failed: {e}")



