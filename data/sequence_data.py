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


class SequenceData:
    data: dict[str, Any] = {}
    is_loaded = False

    @classmethod
    def load(cls):
        cls.data = {
            "has_work_plans": cls.has_work_plans(),
            "has_work_schedules": cls.has_work_schedules(),
            "has_work_calendars": cls.has_work_calendars(),
            "schedule_predefined_types_enum": cls.schedule_predefined_types_enum(),
            "task_columns_enum": cls.task_columns_enum(),
            "task_time_columns_enum": cls.task_time_columns_enum(),
        }
        cls.load_work_plans()
        cls.load_work_schedules()
        cls.load_work_calendars()
        cls.load_work_times()
        cls.load_recurrence_patterns()
        cls.load_time_periods()
        cls.load_sequences()
        cls.load_lag_times()
        cls.load_task_times()
        cls.load_tasks()
        cls.is_loaded = True

    @classmethod
    def has_work_plans(cls):
        return bool(tool.Ifc.get().by_type("IfcWorkPlan"))

    @classmethod
    def has_work_calendars(cls):
        return bool(tool.Ifc.get().by_type("IfcWorkCalendar"))

    @classmethod
    def number_of_work_plans_loaded(cls):
        return len(tool.Ifc.get().by_type("IfcWorkPlan"))

    @classmethod
    def number_of_work_schedules_loaded(cls):
        return len(tool.Ifc.get().by_type("IfcWorkSchedule"))

    @classmethod
    def has_work_schedules(cls):
        return bool(tool.Ifc.get().by_type("IfcWorkSchedule"))

    @classmethod
    def load_work_plans(cls):
        cls.data["work_plans"] = {}
        for work_plan in tool.Ifc.get().by_type("IfcWorkPlan"):
            data = {"Name": work_plan.Name or "Unnamed"}
            data["IsDecomposedBy"] = []
            for rel in work_plan.IsDecomposedBy:
                data["IsDecomposedBy"].extend([o.id() for o in rel.RelatedObjects])
            cls.data["work_plans"][work_plan.id()] = data
        cls.data["number_of_work_plans_loaded"] = cls.number_of_work_plans_loaded()

    @classmethod
    def load_work_schedules(cls):
        cls.data["work_schedules"] = {}
        cls.data["work_schedules_enum"] = []
        for work_schedule in tool.Ifc.get().by_type("IfcWorkSchedule"):
            data = work_schedule.get_info()
            if not data["Name"]:
                data["Name"] = "Unnamed"
            del data["OwnerHistory"]
            if data["Creators"]:
                data["Creators"] = [p.id() for p in data["Creators"]]
            data["CreationDate"] = (
                ifcopenshell.util.date.ifc2datetime(data["CreationDate"]) if data["CreationDate"] else ""
            )
            data["StartTime"] = ifcopenshell.util.date.ifc2datetime(data["StartTime"]) if data["StartTime"] else ""
            data["FinishTime"] = ifcopenshell.util.date.ifc2datetime(data["FinishTime"]) if data["FinishTime"] else ""
            data["RelatedObjects"] = []
            for rel in work_schedule.Controls:
                for obj in rel.RelatedObjects:
                    if obj.is_a("IfcTask"):
                        data["RelatedObjects"].append(obj.id())
            cls.data["work_schedules"][work_schedule.id()] = data
            cls.data["work_schedules_enum"].append((str(work_schedule.id()), data["Name"], ""))

        cls.data["number_of_work_schedules_loaded"] = cls.number_of_work_schedules_loaded()

    @classmethod
    def load_work_calendars(cls):
        cls.data["work_calendars"] = {}
        cls.data["work_calendars_enum"] = []
        for work_calendar in tool.Ifc.get().by_type("IfcWorkCalendar"):
            data = work_calendar.get_info()
            del data["OwnerHistory"]
            if not data["Name"]:
                data["Name"] = "Unnamed"
            data["WorkingTimes"] = [t.id() for t in work_calendar.WorkingTimes or []]
            data["ExceptionTimes"] = [t.id() for t in work_calendar.ExceptionTimes or []]
            cls.data["work_calendars"][work_calendar.id()] = data
            cls.data["work_calendars_enum"].append((str(work_calendar.id()), data["Name"], ""))

        cls.data["number_of_work_calendars_loaded"] = len(cls.data["work_calendars"].keys())

    @classmethod
    def load_work_times(cls):
        cls.data["work_times"] = {}
        for work_time in tool.Ifc.get().by_type("IfcWorkTime"):
            data = work_time.get_info()
            if tool.Ifc.get_schema() == "IFC4X3":
                start_date, finish_date = data["StartDate"], data["FinishDate"]
            else:
                start_date, finish_date = data["Start"], data["Finish"]
            data["Start"] = ifcopenshell.util.date.ifc2datetime(start_date) if start_date else None
            data["Finish"] = ifcopenshell.util.date.ifc2datetime(finish_date) if finish_date else None
            data["RecurrencePattern"] = work_time.RecurrencePattern.id() if work_time.RecurrencePattern else None
            cls.data["work_times"][work_time.id()] = data

    @classmethod
    def load_recurrence_patterns(cls):
        cls.data["recurrence_patterns"] = {}
        for recurrence_pattern in tool.Ifc.get().by_type("IfcRecurrencePattern"):
            data = recurrence_pattern.get_info()
            data["TimePeriods"] = [t.id() for t in recurrence_pattern.TimePeriods or []]
            cls.data["recurrence_patterns"][recurrence_pattern.id()] = data

    @classmethod
    def load_sequences(cls):
        cls.data["sequences"] = {}
        for sequence in tool.Ifc.get().by_type("IfcRelSequence"):
            data = sequence.get_info()
            data["RelatingProcess"] = sequence.RelatingProcess.id()
            data["RelatedProcess"] = sequence.RelatedProcess.id()
            data["TimeLag"] = sequence.TimeLag.id() if sequence.TimeLag else None
            cls.data["sequences"][sequence.id()] = data

    @classmethod
    def load_time_periods(cls):
        cls.data["time_periods"] = {}
        for time_period in tool.Ifc.get().by_type("IfcTimePeriod"):
            cls.data["time_periods"][time_period.id()] = {
                "StartTime": ifcopenshell.util.date.ifc2datetime(time_period.StartTime),
                "EndTime": ifcopenshell.util.date.ifc2datetime(time_period.EndTime),
            }

    @classmethod
    def load_task_times(cls):
        cls.data["task_times"] = {}
        for task_time in tool.Ifc.get().by_type("IfcTaskTime"):
            data = task_time.get_info()
            for key, value in data.items():
                if not value:
                    continue
                if "Start" in key or "Finish" in key or key == "StatusTime":
                    data[key] = ifcopenshell.util.date.ifc2datetime(value)
                elif key == "ScheduleDuration":
                    data[key] = ifcopenshell.util.date.ifc2datetime(value)
            cls.data["task_times"][task_time.id()] = data

    @classmethod
    def load_lag_times(cls):
        cls.data["lag_times"] = {}
        for lag_time in tool.Ifc.get().by_type("IfcLagTime"):
            data = lag_time.get_info()
            if data["LagValue"]:
                if data["LagValue"].is_a("IfcDuration"):
                    data["LagValue"] = ifcopenshell.util.date.ifc2datetime(data["LagValue"].wrappedValue)
                else:
                    data["LagValue"] = float(data["LagValue"].wrappedValue)
            cls.data["lag_times"][lag_time.id()] = data

    @classmethod
    def load_tasks(cls):
        cls.data["tasks"] = {}
        for task in tool.Ifc.get().by_type("IfcTask"):
            data = task.get_info()
            del data["OwnerHistory"]
            data["HasAssignmentsWorkCalendar"] = []
            data["RelatedObjects"] = []
            data["Inputs"] = []
            data["Controls"] = []
            data["Outputs"] = []
            data["Resources"] = []
            data["IsPredecessorTo"] = []
            data["IsSuccessorFrom"] = []
            if task.TaskTime:
                data["TaskTime"] = data["TaskTime"].id()
            for rel in task.IsNestedBy:
                [data["RelatedObjects"].append(o.id()) for o in rel.RelatedObjects if o.is_a("IfcTask")]
            data["Nests"] = [r.RelatingObject.id() for r in task.Nests or []]
            [
                data["Outputs"].append(r.RelatingProduct.id())
                for r in task.HasAssignments
                if r.is_a("IfcRelAssignsToProduct")
            ]
            [
                data["Resources"].extend([o.id() for o in r.RelatedObjects if o.is_a("IfcResource")])
                for r in task.OperatesOn
            ]
            [
                data["Controls"].extend([o.id() for o in r.RelatedObjects if o.is_a("IfcControl")])
                for r in task.OperatesOn
            ]
            [data["Inputs"].extend([o.id() for o in r.RelatedObjects if o.is_a("IfcProduct")]) for r in task.OperatesOn]
            [data["IsPredecessorTo"].append(rel.id()) for rel in task.IsPredecessorTo or []]
            [data["IsSuccessorFrom"].append(rel.id()) for rel in task.IsSuccessorFrom or []]
            for rel in task.HasAssignments:
                if rel.is_a("IfcRelAssignsToControl") and rel.RelatingControl:
                    if rel.RelatingControl.is_a("IfcWorkCalendar"):
                        data["HasAssignmentsWorkCalendar"].append(rel.RelatingControl.id())
            data["NestingIndex"] = None
            for rel in task.Nests or []:
                data["NestingIndex"] = rel.RelatedObjects.index(task)
            cls.data["tasks"][task.id()] = data
    @classmethod
    def schedule_predefined_types_enum(cls) -> list[tuple[str, str, str]]:
        results: list[tuple[str, str, str]] = []
        declaration = tool.Ifc().schema().declaration_by_name("IfcWorkSchedule").as_entity()
        assert declaration
        version = tool.Ifc.get_schema()
        for attribute in declaration.attributes():
            if attribute.name() == "PredefinedType":
                results.extend(
                    [
                        (e, e, get_predefined_type_doc(version, "IfcWorkSchedule", e))
                        for e in ifcopenshell.util.attribute.get_enum_items(attribute)
                    ]
                )
                break
        return results

    @classmethod
    def task_columns_enum(cls) -> list[tuple[str, str, str]]:
        schema = tool.Ifc.schema()
        taskcolumns_enum = []
        assert (entity := schema.declaration_by_name("IfcTask").as_entity())
        for a in entity.all_attributes():
            if (primitive_type := ifcopenshell.util.attribute.get_primitive_type(a)) not in (
                "string",
                "float",
                "integer",
                "boolean",
                "enum",
            ):
                continue
            taskcolumns_enum.append((f"{a.name()}/{primitive_type}", a.name(), ""))
        return taskcolumns_enum

    @classmethod
    def task_time_columns_enum(cls) -> list[tuple[str, str, str]]:
        schema = tool.Ifc.schema()
        tasktimecolumns_enum = []
        assert (entity := schema.declaration_by_name("IfcTaskTime").as_entity())
        for a in entity.all_attributes():
            if (primitive_type := ifcopenshell.util.attribute.get_primitive_type(a)) not in (
                "string",
                "float",
                "integer",
                "boolean",
                "enum",
            ):
                continue
            tasktimecolumns_enum.append((f"{a.name()}/{primitive_type}", a.name(), ""))
        return tasktimecolumns_enum


    @classmethod
    def load_product_task_relationships(cls, product_id):
        """
        Loads task relationships for a specific product.
        """
        try:
            if not tool.Ifc.get():
                return {"input_tasks": [], "output_tasks": []}
            product = tool.Ifc.get().by_id(product_id)
            if not product:
                return {"input_tasks": [], "output_tasks": []}
            
            # Use the corrected Sequence method
            input_tasks, output_tasks = tool.Sequence.get_tasks_for_product(product)
            
            def _to_dict(task):
                try:
                    return {"id": task.id(), "name": getattr(task, "Name", None) or "Unnamed"}
                except Exception:
                    return None
            
            inputs = [d for d in (_to_dict(t) for t in (input_tasks or [])) if d]
            outputs = [d for d in (_to_dict(t) for t in (output_tasks or [])) if d]
            
            return {
                "input_tasks": inputs,
                "output_tasks": outputs
            }
        except Exception as e:
            print(f"Error loading product task relationships: {e}")
            return {"input_tasks": [], "output_tasks": []}


def refresh():
    """Refresh the sequence data by reloading all cached information."""
    SequenceData.load()

