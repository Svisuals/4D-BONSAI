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



import bonsai.core.tool
import bonsai.tool as tool

# Importa TODAS las clases de funcionalidad separadas (Mixins)
from .props_sequence import PropsSequence
from .camera_sequence import CameraSequence
from .task_management_sequence import TaskManagementSequence
from .datetime_helpers_sequence import DatetimeHelpersSequence
from .ifc_data_sequence import IFCDataSequence
from .gantt_sequence import GanttSequence
from .helpers_sequence import HelpersSequence
from .calendar_sequence import CalendarSequence
from .colortype_sequence import ColorTypeSequence
from .variance_sequence import VarianceSequence
from .animation_sequence import AnimationSequence
from .bars_sequence import BarsSequence
from .text_display_sequence import TextDisplaySequence
from .object_animation_sequence import ObjectAnimationSequence
from .config_sequence import ConfigSequence
from .copy_config_sequence import CopyConfigSequence
from .sync_elements_sequence import SyncElementsSequence


class Sequence(
    # NUESTRAS CLASES PRIMERO (para que tengan prioridad en MRO)
    AnimationSequence,           # Incluye: ColorTypeSequence, DatetimeHelpersSequence
    BarsSequence,               # Incluye: PropsSequence, DatetimeHelpersSequence, HelpersSequence  
    TextDisplaySequence,        # Incluye: IFCDataSequence, DatetimeHelpersSequence
    CameraSequence,             # Incluye: PropsSequence
    TaskManagementSequence,     # Incluye: PropsSequence
    GanttSequence,              # Standalone
    CalendarSequence,           # Incluye: PropsSequence
    VarianceSequence,           # Incluye: PropsSequence
    ObjectAnimationSequence,    # Incluye: ColorTypeSequence
    CopyConfigSequence,         # Incluye: PropsSequence
    SyncElementsSequence,       # Incluye: ConfigSequence
    
    # La clase base original AL FINAL (para que sea fallback)
    bonsai.core.tool.Sequence,
):
    """
    Clase coordinadora que une toda la funcionalidad de secuencia.
    """
    pass