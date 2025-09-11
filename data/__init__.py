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


# Importa las clases principales de cada módulo para que sean fácilmente accesibles
# desde el paquete 'data'. Por ejemplo: from bonsai.data import SequenceCache
from .animation_data import AnimationColorSchemeData
from .cache_data import SequenceCache
from .plan_data import WorkPlansData
from .schedule_data import WorkScheduleData
from .sequence_data import SequenceData
from .task_data import TaskICOMData

def refresh():
    """
    Refresca todos los datos y limpia la caché.
    Llama a los estados 'is_loaded = False' de cada clase de datos
    y limpia la caché de SequenceCache.
    """
    SequenceData.is_loaded = False
    WorkPlansData.is_loaded = False
    TaskICOMData.is_loaded = False
    WorkScheduleData.is_loaded = False
    AnimationColorSchemeData.is_loaded = False
    # Limpia la caché de alto rendimiento
    SequenceCache.clear()


