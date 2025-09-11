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


import bonsai.tool as tool


class WorkPlansData:
    data = {}
    is_loaded = False

    @classmethod
    def load(cls):
        cls.data = {
            "total_work_plans": cls.total_work_plans(),
            "work_plans": cls.work_plans(),
            "has_work_schedules": cls.has_work_schedules(),
            "active_work_plan_schedules": cls.active_work_plan_schedules(),
        }
        cls.is_loaded = True

    @classmethod
    def total_work_plans(cls):
        return len(tool.Ifc.get().by_type("IfcWorkPlan"))

    @classmethod
    def work_plans(cls):
        results = []
        for work_plan in tool.Ifc.get().by_type("IfcWorkPlan"):
            results.append({"id": work_plan.id(), "name": work_plan.Name or "Unnamed"})
        return results

    @classmethod
    def has_work_schedules(cls):
        return len(tool.Ifc.get().by_type("IfcWorkSchedule"))

    @classmethod
    def active_work_plan_schedules(cls):
        results = []
        props = tool.Sequence.get_work_plan_props()
        if not props.active_work_plan_id:
            return []
        for rel in tool.Ifc.get().by_id(props.active_work_plan_id).IsDecomposedBy:
            for work_schedule in rel.RelatedObjects:
                results.append({"id": work_schedule.id(), "name": work_schedule.Name or "Unnamed"})
        return results

