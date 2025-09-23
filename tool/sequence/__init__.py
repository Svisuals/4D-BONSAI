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
import bonsai.core.tool
from collections.abc import Iterable
import ifcopenshell

from .props_sequence import PropsSequence
from .camera_sequence import CameraSequence
from .text_sequence import TextSequence
from .task_bars_sequence import TaskBarsSequence
from .date_utils_sequence import DateUtilsSequence
from .color_management_sequence import ColorManagementSequence
from .task_tree_sequence import TaskTreeSequence
from .task_icom_sequence import TaskIcomSequence
from .snapshot_sequence import SnapshotSequence
from .animation_engine_sequence import AnimationEngineSequence
from .task_attributes_sequence import TaskAttributesSequence
from .schedule_management_sequence import ScheduleManagementSequence
from .calendar_sequence import CalendarSequence
from .variance_sequence import VarianceSequence
from .sync_config_sequence import SyncConfigSequence
from .sequence_relations_sequence import SequenceRelationsSequence
from .ui_helpers_sequence import UiHelpersSequence
from .gantt_chart_sequence import GanttChartSequence
from .schedule_utils_sequence import ScheduleUtilsSequence


class Sequence(
    # Nivel 3: Clases más especializadas (incluyen automáticamente sus dependencias)
    SyncConfigSequence,

    # Nivel 2: Clases compuestas de múltiples mixins
    AnimationEngineSequence,
    SnapshotSequence,
    VarianceSequence,

    # Nivel 2: Clases que extienden funcionalidad específica
    TaskBarsSequence,
    TextSequence,
    ScheduleUtilsSequence,

    # Nivel 1: Clases independientes que solo dependen de PropsSequence
    CameraSequence,
    SequenceRelationsSequence,
    UiHelpersSequence,
    CalendarSequence,

    # Clases sin dependencias internas
    GanttChartSequence,

    # Clase base fundamental de todo
    bonsai.core.tool.Sequence
):
    """
    The main Sequence tool class, assembled from refactored mixins.
    This __init__.py file acts as the package's public interface.
    """
    ELEMENT_STATUSES = ("NEW", "EXISTING", "DEMOLISH", "TEMPORARY", "OTHER", "NOTKNOWN", "UNSET")

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
    def select_products(cls, products: Iterable[ifcopenshell.entity_instance]) -> None:
        import bpy
        import bonsai.tool as tool
        [obj.select_set(False) for obj in bpy.context.selected_objects]
        for product in products:
            obj = tool.Ifc.get_object(product)
            obj.select_set(True) if obj else None