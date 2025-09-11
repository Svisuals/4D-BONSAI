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


from typing import Any
import bonsai.tool as tool
import ifcopenshell
import ifcopenshell.util.attribute
import ifcopenshell.util.date
from ifcopenshell.util.doc import get_predefined_type_doc


from typing import Any
import bonsai.tool as tool
import ifcopenshell.util.date


class WorkScheduleData:
    data = {}
    is_loaded = False

    @classmethod
    def load(cls):
        cls.data = {
            "can_have_baselines": cls.can_have_baselines(),
            "active_work_schedule_baselines": cls.active_work_schedule_baselines(),
        }
        cls.is_loaded = True

    @classmethod
    def can_have_baselines(cls) -> bool:
        props = tool.Sequence.get_work_schedule_props()
        if not props.active_work_schedule_id:
            return False
        return tool.Ifc.get().by_id(props.active_work_schedule_id).PredefinedType == "PLANNED"

    @classmethod
    def active_work_schedule_baselines(cls) -> list[dict[str, Any]]:
        results = []
        props = tool.Sequence.get_work_schedule_props()
        if not props.active_work_schedule_id:
            return []
        for rel in tool.Ifc.get().by_id(props.active_work_schedule_id).Declares:
            for work_schedule in rel.RelatedObjects:
                if work_schedule.PredefinedType == "BASELINE":
                    results.append(
                        {
                            "id": work_schedule.id(),
                            "name": work_schedule.Name or "Unnamed",
                            "date": str(ifcopenshell.util.date.ifc2datetime(work_schedule.CreationDate)),
                        }
                    )
        return results


def refresh():
    """Refresh the work schedule data by reloading all cached information."""
    WorkScheduleData.load()
