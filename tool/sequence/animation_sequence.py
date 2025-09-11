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




import bpy
import ifcopenshell
import ifcopenshell.util.date
from datetime import datetime
from typing import Any, List

from .props_sequence import PropsSequence
from .datetime_helpers_sequence import DatetimeHelpersSequence
from .colortype_sequence import ColorTypeSequence
from bonsai.bim.module.sequence.data import SequenceCache
import bonsai.tool as tool
        

class AnimationSequence(ColorTypeSequence, DatetimeHelpersSequence):
    """Lógica para generar la animación 4D, colores, barras y textos."""

    @classmethod
    def get_animation_settings(cls):
        
        def calculate_total_frames(fps):
            if props.speed_types == "FRAME_SPEED":
                return calculate_using_frames(
                    start,
                    finish,
                    props.speed_animation_frames,
                    ifcopenshell.util.date.parse_duration(props.speed_real_duration),
                )
            elif props.speed_types == "DURATION_SPEED":
                animation_duration = ifcopenshell.util.date.parse_duration(props.speed_animation_duration)
                real_duration = ifcopenshell.util.date.parse_duration(props.speed_real_duration)
                return calculate_using_duration(
                    start,
                    finish,
                    fps,
                    animation_duration,
                    real_duration,
                )
            elif props.speed_types == "MULTIPLIER_SPEED":
                return calculate_using_multiplier(
                    start,
                    finish,
                    1,
                    props.speed_multiplier,
                )

        def calculate_using_multiplier(start, finish, fps, multiplier):
            animation_time = (finish - start) / multiplier
            return animation_time.total_seconds() * fps

        def calculate_using_duration(start, finish, fps, animation_duration, real_duration):
            return calculate_using_multiplier(start, finish, fps, real_duration / animation_duration)

        def calculate_using_frames(start, finish, animation_frames, real_duration):
            return ((finish - start) / real_duration) * animation_frames
        props = cls.get_work_schedule_props()
        # Get visualization dates: first UI, if missing, infer from active schedule
        viz_start_prop = getattr(props, "visualisation_start", None)
        viz_finish_prop = getattr(props, "visualisation_finish", None)

        inferred_start = None
        inferred_finish = None
        if not (viz_start_prop and viz_finish_prop):
            try:
                ws = cls.get_active_work_schedule()
                if ws:
                    inferred_start, inferred_finish = cls.guess_date_range(ws)
            except Exception:
                inferred_start, inferred_finish = (None, None)

        def _to_dt(v):
            try:
                from datetime import datetime as _dt, date as _d
                if isinstance(v, _dt):
                    return v.replace(microsecond=0)
                if isinstance(v, _d):
                    return _dt(v.year, v.month, v.day)
                s = str(v)
                try:
                    if "T" in s or " " in s:
                        s2 = s.replace(" ", "T")
                        return _dt.fromisoformat(s2[:19])
                    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                        return _dt.fromisoformat(s[:10])
                except Exception:
                    pass
                from dateutil import parser as _p
                return _p.parse(s, yearfirst=True, dayfirst=False, fuzzy=True)
            except Exception:
                try:
                    from dateutil import parser as _p
                    return _p.parse(str(v), yearfirst=True, dayfirst=True, fuzzy=True)
                except Exception:
                    return None

        if viz_start_prop and viz_finish_prop:
            start = cls.get_start_date()
            finish = cls.get_finish_date()
        else:
            start = _to_dt(inferred_start)
            finish = _to_dt(inferred_finish)
            try:
                if start and finish:
                    props.visualisation_start = ifcopenshell.util.date.canonicalise_time(start)
                    props.visualisation_finish = ifcopenshell.util.date.canonicalise_time(finish)
            except Exception:
                pass

        if not start or not finish:
            print("❌ No se pudieron determinar fechas de visualización (UI ni inferidas)")
            return None

        try:
            start = start.replace(microsecond=0)
            finish = finish.replace(microsecond=0)
        except Exception:
            pass

        if finish <= start:
            try:
                from datetime import timedelta as _td
                if finish == start:
                    finish = start + _td(days=1)
                else:
                    print(f"❌ Error: Fecha de fin ({finish}) debe ser posterior a fecha de inicio ({start})")
                    return None
            except Exception:
                print(f"❌ Error ajustando rango de fechas: start={start}, finish={finish}")
                return None


        duration = finish - start
        # Use frame_start from the scene if it exists; default 1
        try:
            start_frame = int(getattr(bpy.context.scene, 'frame_start', 1) or 1)
        except Exception:
            start_frame = 1

        # Calculate total frames based on speed settings
        try:
            fps = int(getattr(bpy.context.scene.render, 'fps', 24) or 24)
        except Exception:
            fps = 24
        total_frames = int(round(calculate_total_frames(fps)))

        print(f"📅 Animation Settings:")
        try:
            print(f"   Start Date: {start.strftime('%Y-%m-%d')}")
            print(f"   Finish Date: {finish.strftime('%Y-%m-%d')}")
        except Exception:
            print(f"   Start Date: {start}")
            print(f"   Finish Date: {finish}")
        print(f"   Duration: {duration.days} days")
        print(f"   Start Frame: {start_frame}")
        print(f"   Total Frames: {total_frames}")

        return {
            "start": start,
            "finish": finish,
            "duration": duration,
            "start_frame": start_frame,
            "total_frames": total_frames,
            # NEW: Add full schedule dates for reference
            "schedule_start": None,
            "schedule_finish": None,
        }



    @classmethod
    def get_animation_product_frames(cls, work_schedule: ifcopenshell.entity_instance, settings: dict[str, Any]):

            def add_product_frame(product_id, type, product_start, product_finish, relationship):
                product_frames.setdefault(product_id, []).append(
                    {
                        "type": type,
                        "relationship": relationship,
                        "STARTED": round(
                            settings["start_frame"]
                            + (((product_start - settings["start"]) / settings["duration"]) * settings["total_frames"])
                        ),
                        "COMPLETED": round(
                            settings["start_frame"]
                            + (((product_finish - settings["start"]) / settings["duration"]) * settings["total_frames"])
                        ),
                    }
                )

            product_frames = {}
            for root_task in ifcopenshell.util.sequence.get_root_tasks(work_schedule):
                preprocess_task(root_task)
            return product_frames



    @classmethod
    def process_construction_state(
        cls,
        work_schedule: ifcopenshell.entity_instance,
        date: datetime,
        viz_start: datetime = None,
        viz_finish: datetime = None,
        date_source: str = "SCHEDULE") -> dict[str, Any]:
        """
        OPTIMIZED: Procesa estados considerando el rango de visualización configurado.
        Now uses cached data structures for massive performance improvement.

        Args:
            work_schedule: Work schedule
            date: Fecha actual del snapshot
            viz_start: Fecha de inicio de visualización (opcional)
            date_source: El tipo de fecha a usar ('SCHEDULE', 'ACTUAL', etc.)
            viz_finish: Fecha de fin de visualización (opcional)
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
                print(f"🚀 {optimization_used}")
                return  # Early return - optimization successful
        except Exception as e:
            print(f"⚠️ NumPy optimization failed (safe fallback): {e}")
        
        # FAST FALLBACK PATH: Use cached data if available
        try:
            cached_dates = SequenceCache.get_schedule_dates(work_schedule_id, date_source)
            cached_products = SequenceCache.get_task_products(work_schedule_id)
            
            if cached_dates and cached_products:
                # CACHED OPTIMIZATION: Process using cached data (faster than full iteration)
                tasks_data = cached_dates.get('tasks_dates', [])
                optimization_used = f"Cached data: {len(tasks_data)} tasks from cache"
                print(f"⚡ {optimization_used}")
                
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
            print(f"⚠️ Cache optimization failed (safe fallback): {e}")
        
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
        
        # Procesar tareas anidadas recursivamente
        for rel in task.IsNestedBy or []: # type: ignore
            [cls.process_task_status(related_object, date, viz_start, viz_finish, date_source=date_source) for related_object in rel.RelatedObjects]

        
        start_date_type = f"{date_source.capitalize()}Start"
        finish_date_type = f"{date_source.capitalize()}Finish"

        start = ifcopenshell.util.sequence.derive_date(task, start_date_type, is_earliest=True)
        finish = ifcopenshell.util.sequence.derive_date(task, finish_date_type, is_latest=True)

        if not start or not finish:
            return

        outputs = ifcopenshell.util.sequence.get_task_outputs(task) or []
        inputs = cls.get_task_inputs(task) or []

        # NEW LOGIC: Consider visualization range

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
            # Después de finalizar: outputs permanecen visibles, inputs desaparecen
            [cls.completed.add(tool.Ifc.get_object(output)) for output in outputs]
            [cls.demolished.add(tool.Ifc.get_object(input)) for input in inputs]

    @classmethod
    def clear_objects_animation(
            cls,
            include_blender_objects: bool = True,
            *,
            clear_texts: bool = True,
            clear_bars: bool = True,
            reset_timeline: bool = True,
            reset_colors_and_visibility: bool = True,
        ):
        """Cleans the 4D animation selectively and robustly."""

        # 1. Desregistrar handlers de actualización por frame para evitar errores
        cls._unregister_frame_change_handler()

        # 2. Limpiar textos del cronograma
        if clear_texts:
            coll = bpy.data.collections.get("Schedule_Display_Texts")
            if coll:
                for obj in list(coll.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(coll)

        # 3. Limpiar barras de Gantt 3D
        if clear_bars:
            coll = bpy.data.collections.get("Bar Visual")
            if coll:
                for obj in list(coll.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(coll)

        # 4. Limpiar objetos 3D (productos del IFC)
        if include_blender_objects:
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    if obj.animation_data:
                        obj.animation_data_clear()
                    if reset_colors_and_visibility:
                        obj.hide_viewport = False  # ← ENSURE IT IS VISIBLE
                        obj.hide_render = False    # ← ENSURE IT IS VISIBLE
                        obj.color = (0.8, 0.8, 0.8, 1.0) # Reset a un color gris neutro

        # 5. Reset the timeline
        if reset_timeline:
            scene = bpy.context.scene
            scene.frame_current = scene.frame_start

        print("✅ Animation data cleared.")

    @classmethod
    def show_snapshot(cls, product_states):
        """
        Muestra un snapshot visual de todos los objetos IFC en la fecha especificada.
        Esta función es autocontenida y robusta, similar a la lógica de v30.
        """
        # 1. Limpiar keyframes y guardar colores originales
        original_properties = {}
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                original_properties[obj.name] = {
                    "color": list(obj.color),
                    "hide": obj.hide_get(),
                }
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

            # Aplicar apariencia
            is_demolition = (getattr(task, "PredefinedType", "") or "").upper() in {"DEMOLITION", "REMOVAL", "DISPOSAL", "DISMANTLE"}

            # Lógica de visibilidad
            if is_demolition:
                if state == "start": obj.hide_viewport = False # Visible antes de demoler
                elif state == "in_progress": obj.hide_viewport = False # Visible durante demolición
                else: obj.hide_viewport = True # Oculto después de demoler
            else: # Construcción
                if state == "start": obj.hide_viewport = True # Oculto antes de construir
                else: obj.hide_viewport = False # Visible durante y después

            # Lógica de color (solo si es visible)
            if not obj.hide_viewport:
                color_to_apply = original_color
                if state == "start":
                    if not getattr(ColorType, 'use_start_original_color', False):
                        color_to_apply = list(ColorType.start_color)
                elif state == "in_progress":
                    if not getattr(ColorType, 'use_active_original_color', False):
                        color_to_apply = list(ColorType.in_progress_color)
                else: # end
                    if getattr(ColorType, 'hide_at_end', False):
                        obj.hide_viewport = True
                    elif not getattr(ColorType, 'use_end_original_color', True):
                        color_to_apply = list(ColorType.end_color)
                
                if not obj.hide_viewport:
                    obj.color = color_to_apply

            obj.hide_render = obj.hide_viewport
            applied_count += 1

        # 5. Configurar el 3D view
        cls.set_object_shading()
        print(f"✅ Snapshot aplicado. {applied_count} objetos procesados.")

    
    
    @staticmethod
    def add_group_to_animation_stack():
        """Add a new group to the animation group stack"""
        try:
            anim_props = cls.get_animation_props()
            if not hasattr(anim_props, 'animation_group_stack'):
                print("❌ animation_group_stack not found in animation properties")
                return
            
            # Add new item to stack
            item = anim_props.animation_group_stack.add()
            item.group = "DEFAULT"  # Default group name
            item.enabled = True
            
            # Set as active item
            anim_props.animation_group_stack_index = len(anim_props.animation_group_stack) - 1
            
            print(f"✅ Added group '{item.group}' to animation stack")
            
        except Exception as e:
            print(f"❌ Error adding group to animation stack: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def remove_group_from_animation_stack():
        """Remove the selected group from the animation group stack"""
        try:
            anim_props = cls.get_animation_props()
            if not hasattr(anim_props, 'animation_group_stack'):
                print("❌ animation_group_stack not found in animation properties")
                return
            
            idx = anim_props.animation_group_stack_index
            if 0 <= idx < len(anim_props.animation_group_stack):
                removed_group = anim_props.animation_group_stack[idx].group
                anim_props.animation_group_stack.remove(idx)
                
                # Adjust index if needed
                if anim_props.animation_group_stack_index >= len(anim_props.animation_group_stack):
                    anim_props.animation_group_stack_index = len(anim_props.animation_group_stack) - 1
                    
                print(f"✅ Removed group '{removed_group}' from animation stack")
            else:
                print("❌ No valid group selected to remove")
                
        except Exception as e:
            print(f"❌ Error removing group from animation stack: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def move_group_in_animation_stack(direction):
        """Move the selected group up or down in the animation group stack"""
        try:
            anim_props = cls.get_animation_props()
            if not hasattr(anim_props, 'animation_group_stack'):
                print("❌ animation_group_stack not found in animation properties")
                return
            
            idx = anim_props.animation_group_stack_index
            stack_len = len(anim_props.animation_group_stack)
            
            if not (0 <= idx < stack_len):
                print("❌ No valid group selected to move")
                return
                
            new_idx = idx
            if direction == "UP" and idx > 0:
                new_idx = idx - 1
            elif direction == "DOWN" and idx < stack_len - 1:
                new_idx = idx + 1
            else:
                print(f"❌ Cannot move {direction} from position {idx}")
                return
                
            # Move the item by removing and re-inserting
            item = anim_props.animation_group_stack[idx]
            group_name = item.group
            enabled = item.enabled
            
            # Remove old item
            anim_props.animation_group_stack.remove(idx)
            
            # Add at new position
            new_item = anim_props.animation_group_stack.add()
            anim_props.animation_group_stack.move(len(anim_props.animation_group_stack) - 1, new_idx)
            
            # Restore properties
            anim_props.animation_group_stack[new_idx].group = group_name
            anim_props.animation_group_stack[new_idx].enabled = enabled
            
            # Update index
            anim_props.animation_group_stack_index = new_idx
            
            print(f"✅ Moved group '{group_name}' {direction} to position {new_idx}")
            
        except Exception as e:
            print(f"❌ Error moving group in animation stack: {e}")
            import traceback
            traceback.print_exc()

    
    





















