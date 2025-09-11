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


from datetime import datetime
from typing import Union, Any
import ifcopenshell

class DatetimeHelpersSequence:
    """Funciones auxiliares para parsear y formatear fechas."""


    @classmethod
    def parse_isodate_datetime(cls, value, include_time: bool = True):
        """Parsea fechas ISO (o datetime/date) y devuelve datetime sin microsegundos.
        - Acepta 'YYYY-MM-DD', 'YYYY-MM', 'YYYY', 'YYYY-MM-DDTHH:MM[:SS][Z|±HH:MM]'.
        - Si include_time es False, se normaliza a 00:00:00.
        - Si no puede parsear, devuelve None.
        """
        try:
            import datetime as _dt, re as _re
            if value is None:
                return None
            if isinstance(value, _dt.datetime):
                return value.replace(microsecond=0) if include_time else value.replace(hour=0, minute=0, second=0, microsecond=0)
            if isinstance(value, _dt.date):
                return _dt.datetime.combine(value, _dt.time())
            if isinstance(value, str):
                s = value.strip()
                if not s:
                    return None
                # If contains time or timezone
                if 'T' in s or ' ' in s or 'Z' in s or '+' in s:
                    ss = s.replace(' ', 'T').replace('Z', '+00:00')
                    try:
                        dtv = _dt.datetime.fromisoformat(ss)
                    except ValueError:
                        # Try without seconds: YYYY-MM-DDTHH:MM
                        m = _re.match(r'^(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})$', ss)
                        if m:
                            dtv = _dt.datetime.fromisoformat(m.group(1) + 'T' + m.group(2) + ':' + m.group(3) + ':00')
                        else:
                            return None
                    return dtv.replace(microsecond=0) if include_time else dtv.replace(hour=0, minute=0, second=0, microsecond=0)
                # Date-only variants
                try:
                    d = _dt.date.fromisoformat(s)
                except ValueError:
                    if _re.match(r'^\d{4}-\d{2}$', s):
                        y, m = s.split('-')
                        d = _dt.date(int(y), int(m), 1)
                    elif _re.match(r'^\d{4}$', s):
                        d = _dt.date(int(s), 1, 1)
                    else:
                        return None
                return _dt.datetime.combine(d, _dt.time())
            # Fallback
            return None
        except Exception:
            return None


    @classmethod
    def isodate_datetime(cls, value, include_time: bool = True) -> str:
        """
        Returns an ISO-8601 string.
        - Si include_time es False => YYYY-MM-DD
        - Si include_time es True  => YYYY-MM-DDTHH:MM:SS (sin microsegundos)
        Acepta datetime/date o string y es tolerante a None.
        """
        try:
            import datetime as _dt
            if value is None:
                return ""
            # If it is already a str, return as is (assumed to be ISO or valid for UI)
            if isinstance(value, str):
                return value
            # If it is datetime/date
            if isinstance(value, _dt.datetime):
                return (value.replace(microsecond=0).isoformat()
                        if include_time else value.date().isoformat())
            if isinstance(value, _dt.date):
                return value.isoformat()
            # Any other type: try to convert
            return str(value)
        except Exception:
            return ""


    @classmethod
    def get_start_date(cls) -> Union[datetime, None]:
        """Devuelve la fecha de inicio configurada (visualisation_start) o None.
        Parseo robusto: ISO-8601 primero (YYYY-MM-DD), luego dateutil con yearfirst=True.
        """
        props = cls.get_work_schedule_props()
        s = getattr(props, "visualisation_start", None)
        if not s or s == "-":
            return None
        try:
            from datetime import datetime as _dt
            if isinstance(s, str):
                try:
                    if "T" in s or " " in s:
                        s2 = s.replace(" ", "T")
                        dt = _dt.fromisoformat(s2[:19])
                    else:
                        dt = _dt.fromisoformat(s[:10])
                    return dt.replace(microsecond=0)
                except Exception:
                    pass
            if isinstance(s, (_dt, )):
                return s.replace(microsecond=0)
        except Exception:
            pass
        try:
            from dateutil import parser
            dt = parser.parse(str(s), yearfirst=True, dayfirst=False, fuzzy=True)
            return dt.replace(microsecond=0)
        except Exception:
            try:
                dt = parser.parse(str(s), yearfirst=True, dayfirst=True, fuzzy=True)
                return dt.replace(microsecond=0)
            except Exception as e:
                print(f"❌ Error parseando visualisation_start: {s} -> {e}")
                return None

    @classmethod
    def get_finish_date(cls) -> Union[datetime, None]:
        """Devuelve la fecha de fin configurada (visualisation_finish) o None.
        Parseo robusto: ISO-8601 primero, luego dateutil con yearfirst=True.
        """
        props = cls.get_work_schedule_props()
        s = getattr(props, "visualisation_finish", None)
        if not s or s == "-":
            return None
        try:
            from datetime import datetime as _dt
            if isinstance(s, str):
                try:
                    if "T" in s or " " in s:
                        s2 = s.replace(" ", "T")
                        dt = _dt.fromisoformat(s2[:19])
                    else:
                        dt = _dt.fromisoformat(s[:10])
                    return dt.replace(microsecond=0)
                except Exception:
                    pass
            if isinstance(s, (_dt, )):
                return s.replace(microsecond=0)
        except Exception:
            pass
        try:
            from dateutil import parser
            dt = parser.parse(str(s), yearfirst=True, dayfirst=False, fuzzy=True)
            return dt.replace(microsecond=0)
        except Exception:
            try:
                dt = parser.parse(str(s), yearfirst=True, dayfirst=True, fuzzy=True)
                return dt.replace(microsecond=0)
            except Exception as e:
                print(f"❌ Error parseando visualisation_finish: {s} -> {e}")
                return None


    @classmethod
    def get_schedule_date_range(cls, work_schedule=None):
        """
        Obtiene el rango de fechas REAL del cronograma activo (no las fechas de visualización).
        OPTIMIZED: Now uses SequenceCache for fast access.

        Returns:
            tuple: (schedule_start: datetime, schedule_finish: datetime) o (None, None) si falla
        """
        try:
            if not work_schedule:
                work_schedule = cls.get_active_work_schedule()

            if not work_schedule:
                print("⚠️ No hay cronograma activo para obtener fechas")
                return None, None

            # TEMPORARILY DISABLED: Cache optimization to prevent infinite loops
            # NEW: Use cache-optimized date retrieval
            # work_schedule_id = work_schedule.id()
            # props = cls.get_work_schedule_props()
            # date_source = getattr(props, "date_source_type", "SCHEDULE")
            # 
            # cached_dates = SequenceCache.get_schedule_dates(work_schedule_id, date_source)
            # if cached_dates and cached_dates['date_range'][0] and cached_dates['date_range'][1]:
            #     schedule_start, schedule_finish = cached_dates['date_range']
            #     print(f"⚡ Schedule dates (cached): {schedule_start.strftime('%Y-%m-%d')} to {schedule_finish.strftime('%Y-%m-%d')}")
            #     return schedule_start, schedule_finish

            # Fallback to original logic if cache fails
            schedule_start = None
            schedule_finish = None
            try:
                infer = getattr(cls, "_infer_schedule_date_range", None)
                if infer:
                    schedule_start, schedule_finish = infer(work_schedule)
            except Exception as e:
                print(f"⚠️ Error en _infer_schedule_date_range: {e}")

            if schedule_start and schedule_finish:
                print(f"📅 Schedule dates: {schedule_start.strftime('%Y-%m-%d')} to {schedule_finish.strftime('%Y-%m-%d')}")
                return schedule_start, schedule_finish

            # Final fallback: usar guess_date_range
            try:
                schedule_start, schedule_finish = cls.guess_date_range(work_schedule)
                if schedule_start and schedule_finish:
                    return schedule_start, schedule_finish
            except Exception as e:
                print(f"⚠️ Error en guess_date_range: {e}")

            print("⚠️ No se pudieron determinar las fechas del cronograma")
            return None, None

        except Exception as e:
            print(f"❌ Error obteniendo fechas del cronograma: {e}")
            return None, None



    @classmethod
    def get_visualization_date_range(cls):
        """
        Obtiene el rango de fechas de visualización configurado en la UI.

        Returns:
        tuple: (viz_start: datetime, viz_finish: datetime) o (None, None) si no están configuradas
        """
        try:
            props = cls.get_work_schedule_props()
            viz_start = cls.get_start_date()  # Ya existe esta función
            viz_finish = cls.get_finish_date()  # Ya existe esta función

            return viz_start, viz_finish
        except Exception as e:
            print(f"⚠️ Error obteniendo rango de visualización: {e}")
            return None, None

    @classmethod
    def update_visualisation_date(cls, start_date, finish_date):
        props = cls.get_work_schedule_props()
        if start_date and finish_date:
            start_iso = ifcopenshell.util.date.canonicalise_time(start_date)
            finish_iso = ifcopenshell.util.date.canonicalise_time(finish_date)
            
            # CRITICAL FIX 4: Debug the actual update
            print(f"📝 UPDATE_VIZ_DATE: Setting {start_iso} to {finish_iso}")
            print(f"📝 UPDATE_VIZ_DATE: Previous values were: {getattr(props, 'visualisation_start', 'None')} to {getattr(props, 'visualisation_finish', 'None')}")
            
            props.visualisation_start = start_iso
            props.visualisation_finish = finish_iso
            
            # Verify the update worked
            print(f"✅ UPDATE_VIZ_DATE: New values are: {props.visualisation_start} to {props.visualisation_finish}")
        else:
            print(f"❌ UPDATE_VIZ_DATE: Invalid dates provided - start: {start_date}, finish: {finish_date}")
            props.visualisation_start = ""
            props.visualisation_finish = ""


    @classmethod
    def guess_date_range(cls, work_schedule: ifcopenshell.entity_instance) -> tuple[Any, Any]:
        """
        Guesses the date range for a work schedule, respecting the date source type
        (Schedule, Actual, etc.) set in the UI. It now calculates the range based
        on ALL tasks in the schedule, ignoring any UI filters.
        """
        if not work_schedule:
            return None, None

      
        # Helper function to get all tasks recursively, ignoring UI filters.
        def get_all_tasks_from_schedule(schedule):
            all_tasks = []
            root_tasks = ifcopenshell.util.sequence.get_root_tasks(schedule)

            def recurse(tasks):
                for task in tasks:
                    all_tasks.append(task)
                    nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested:
                        recurse(nested)

            recurse(root_tasks)
            return all_tasks

        all_schedule_tasks = get_all_tasks_from_schedule(work_schedule)

        if not all_schedule_tasks:
            return None, None

        props = cls.get_work_schedule_props()
        date_source = getattr(props, "date_source_type", "SCHEDULE")
        start_attr = f"{date_source.capitalize()}Start"
        finish_attr = f"{date_source.capitalize()}Finish"

        # CRITICAL FIX 3: Debug info to track what's happening
        print(f"🔍 GUESS_DATE_RANGE: Using date source '{date_source}' -> {start_attr}/{finish_attr}")
        print(f"📊 GUESS_DATE_RANGE: Processing {len(all_schedule_tasks)} tasks")

        all_starts = []
        all_finishes = []
        found_dates_count = 0

        # Iterate over ALL tasks from the schedule, not just the visible ones.
        for task in all_schedule_tasks:
            start_date = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
            if start_date:
                all_starts.append(start_date)

            finish_date = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
            if finish_date:
                all_finishes.append(finish_date)
            
            if start_date or finish_date:
                found_dates_count += 1
        
        print(f"📅 GUESS_DATE_RANGE: Found dates in {found_dates_count}/{len(all_schedule_tasks)} tasks")
        

        if not all_starts or not all_finishes:
            print(f"❌ GUESS_DATE_RANGE: No valid dates found for {date_source}")
            return None, None

        result_start = min(all_starts)
        result_finish = max(all_finishes)
        print(f"✅ GUESS_DATE_RANGE: Result for {date_source}: {result_start.strftime('%Y-%m-%d')} to {result_finish.strftime('%Y-%m-%d')}")
        
        return result_start, result_finish















