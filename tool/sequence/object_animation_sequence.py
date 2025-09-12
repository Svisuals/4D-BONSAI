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
from datetime import datetime
from typing import Any

from .props_sequence import PropsSequence
from .colortype_sequence import ColorTypeSequence
import bonsai.tool as tool

# Importación segura de dependencias de UI y color
try:
    from ...prop.color_manager_prop import UnifiedColorTypeManager
except ImportError:
    class UnifiedColorTypeManager:
        @staticmethod
        def ensure_default_group(context): pass

class ObjectAnimationSequence(ColorTypeSequence):
    """Maneja la animación de colores y visibilidad de los objetos IFC."""


    @classmethod
    def animate_objects_with_ColorTypes(cls, settings, product_frames):
       
        animation_props = cls.get_animation_props()
        
        # Active group logic (stack → DEFAULT)
        active_group_name = None
        for item in getattr(animation_props, "animation_group_stack", []):
            if getattr(item, "enabled", False) and getattr(item, "group", None):
                active_group_name = item.group
                break
        if not active_group_name:
            active_group_name = "DEFAULT"
        print(f"🎬 INICIANDO ANIMACIÓN: Usando el grupo de perfiles '{active_group_name}'")

        original_colors = {}
        # --- NEW: Live Update Cache ---
        live_update_props = {"product_frames": {}, "original_colors": {}}
        
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                original_colors[obj.name] = list(obj.color)
      
        for obj in bpy.data.objects:
            element = tool.Ifc.get_entity(obj)
            if not element or element.is_a("IfcSpace"):
                if element and element.is_a("IfcSpace"): cls.hide_object(obj)
                continue

            if element.id() not in product_frames:
                obj.hide_viewport = True
                obj.hide_render = True
                continue

           
            # los ocultamos inmediatamente y establecemos keyframes en frame 0
            obj.hide_viewport = True
            obj.hide_render = True
            obj.keyframe_insert(data_path="hide_viewport", frame=0)
            obj.keyframe_insert(data_path="hide_render", frame=0)

            if animation_props.enable_live_color_updates:
                # No hacer los objetos visibles aquí - la visibilidad se controlará por apply_ColorType_animation
                live_update_props["original_colors"][str(element.id())] = original_colors.get(obj.name, [1.0, 1.0, 1.0, 1.0])
            else: # Baking mode
                original_color = original_colors.get(obj.name, [1.0, 1.0, 1.0, 1.0])
                for frame_data in product_frames[element.id()]:
                    task = frame_data.get("task") or tool.Ifc.get().by_id(frame_data.get("task_id"))
                    ColorType = cls.get_assigned_ColorType_for_task(task, animation_props, active_group_name)
                    # The fallback to DEFAULT is now handled inside get_assigned_ColorType_for_task
                    cls.apply_ColorType_animation(obj, frame_data, ColorType, original_color, settings)

        # --- NEW: Cache data for live updates ---
        print(f"[DEBUG] Checking live updates: enable_live_color_updates = {animation_props.enable_live_color_updates}")
        if animation_props.enable_live_color_updates:
            
            string_keyed_product_frames = {str(k): v for k, v in product_frames.items()}

            
            # para evitar guardar objetos de ifcopenshell en las propiedades de la escena.
            serializable_product_frames = {}
            for pid_str, frame_data_list in string_keyed_product_frames.items():
                serializable_frame_data_list = []
                for frame_data_item in frame_data_list:
                    serializable_item = {}
                    for key, value in frame_data_item.items():
                        if key == 'task':
                            # Store task_id to recover task in live handler
                            if hasattr(value, 'id') and callable(value.id):
                                serializable_item['task_id'] = value.id()
                            continue  # Omitir el objeto 'task' que no es serializable
                        elif isinstance(value, datetime):
                            serializable_item[key] = value.isoformat()  # Convertir datetime a string
                        else:
                            serializable_item[key] = value
                    serializable_frame_data_list.append(serializable_item)
                serializable_product_frames[pid_str] = serializable_frame_data_list
            live_update_props["product_frames"] = serializable_product_frames
            bpy.context.scene['BIM_LiveUpdateProductFrames'] = live_update_props
            print(f"[DEBUG] Created live update cache with {len(serializable_product_frames)} products")
            
            # Immediate verification
            if bpy.context.scene.get('BIM_LiveUpdateProductFrames'):
                print("[DEBUG] Cache verification: SUCCESS - BIM_LiveUpdateProductFrames exists")
            else:
                print("[DEBUG] Cache verification: FAILED - BIM_LiveUpdateProductFrames missing!")
                
            cls.register_live_color_update_handler() # Ensure handler is active

        area = tool.Blender.get_view3d_area()
        try:
            # This ensures colors are visible if baked, or if live updates are on
            area.spaces[0].shading.color_type = "OBJECT"
        except Exception:
            pass
        bpy.context.scene.frame_start = settings["start_frame"]
        bpy.context.scene.frame_end = int(settings["start_frame"] + settings["total_frames"] + 1)


    @classmethod
    def apply_ColorType_animation(cls, obj, frame_data, ColorType, original_color, settings):
        """Aplica la animación a un objeto basándose en su perfil de apariencia,con una lógica corregida y robusta para todos los estados."""
        # Limpiar cualquier animación previa en este objeto para empezar de cero.
        if obj.animation_data:
            obj.animation_data_clear()

        # --- LÓGICA DE ESTADO "START" (ANTES DE QUE LA TAREA EMPIECE) ---
        start_state_frames = frame_data["states"]["before_start"]
        start_f, end_f = start_state_frames

        # Determinar si el objeto debe estar oculto o visible en la fase inicial.
        is_construction = frame_data.get("relationship") == "output"
        should_be_hidden_at_start = is_construction and not getattr(ColorType, 'consider_start', False)

        
        # El objeto ya está oculto desde animate_objects_with_ColorTypes.
        # Solo preparar los valores para los keyframes.
        
        start_visibility = not should_be_hidden_at_start
        
        # Preparar color para keyframes (solo si será visible)
        if not should_be_hidden_at_start:
            use_original = getattr(ColorType, 'use_start_original_color', False)
            color = original_color if use_original else list(ColorType.start_color)
            alpha = 1.0 - getattr(ColorType, 'start_transparency', 0.0)
            start_color = (color[0], color[1], color[2], alpha)

        # Insertar keyframes para el estado inicial completo.
        if end_f >= start_f:
            # Establecer visibilidad para keyframes sin cambiar el estado actual
            current_hide_state = obj.hide_viewport
            obj.hide_viewport = not start_visibility
            obj.hide_render = not start_visibility
            obj.keyframe_insert(data_path="hide_viewport", frame=start_f)
            obj.keyframe_insert(data_path="hide_render", frame=start_f)
            
            if not should_be_hidden_at_start:
                obj.color = start_color
                obj.keyframe_insert(data_path="color", frame=start_f)

            # Keyframe al final de la fase para mantener el estado.
            obj.keyframe_insert(data_path="hide_viewport", frame=end_f)
            obj.keyframe_insert(data_path="hide_render", frame=end_f)
            if not should_be_hidden_at_start:
                obj.keyframe_insert(data_path="color", frame=end_f)
                
            # CRÍTICO: Restaurar el estado oculto para que no sea visible antes de la animación
            obj.hide_viewport = True
            obj.hide_render = True

        # --- LÓGICA DE ESTADO "ACTIVE" (DURANTE LA TAREA) ---
        active_state_frames = frame_data["states"]["active"]
        start_f, end_f = active_state_frames

        if end_f >= start_f and getattr(ColorType, 'consider_active', True):
            
            # Aplicar color y transparencia del estado "active".
            use_original = getattr(ColorType, 'use_active_original_color', False)
            color = original_color if use_original else list(ColorType.in_progress_color)

            # Interpolar transparencia
            alpha_start = 1.0 - getattr(ColorType, 'active_start_transparency', 0.0)
            alpha_end = 1.0 - getattr(ColorType, 'active_finish_transparency', 0.0)

            # Establecer keyframes de visibilidad (visible durante fase activa)
            obj.hide_viewport = False
            obj.hide_render = False
            obj.keyframe_insert(data_path="hide_viewport", frame=start_f)
            obj.keyframe_insert(data_path="hide_render", frame=start_f)

            # Keyframe inicial del estado activo
            obj.color = (color[0], color[1], color[2], alpha_start)
            obj.keyframe_insert(data_path="color", frame=start_f)

            # Keyframe final del estado activo (si hay duración)
            if end_f > start_f:
                obj.color = (color[0], color[1], color[2], alpha_end)
                obj.keyframe_insert(data_path="color", frame=end_f)
                
            # CRÍTICO: Restaurar el estado oculto para que no sea visible antes de la animación
            obj.hide_viewport = True
            obj.hide_render = True

        # --- LÓGICA DE ESTADO "END" (DESPUÉS DE QUE LA TAREA TERMINA) ---
        end_state_frames = frame_data["states"]["after_end"]
        start_f, end_f = end_state_frames

        if end_f >= start_f and getattr(ColorType, 'consider_end', True):
            # Determinar si el objeto debe ocultarse al final.
            should_hide_at_end = getattr(ColorType, 'hide_at_end', False)

            
            end_visibility = not should_hide_at_end
            
            # Preparar color para keyframes (solo si será visible)
            if not should_hide_at_end:
                use_original = getattr(ColorType, 'use_end_original_color', True)
                color = original_color if use_original else list(ColorType.end_color)
                alpha = 1.0 - getattr(ColorType, 'end_transparency', 0.0)
                end_color = (color[0], color[1], color[2], alpha)

            # Establecer keyframes de visibilidad
            obj.hide_viewport = not end_visibility
            obj.hide_render = not end_visibility
            obj.keyframe_insert(data_path="hide_viewport", frame=start_f)
            obj.keyframe_insert(data_path="hide_render", frame=start_f)
            
            if not should_hide_at_end:
                obj.color = end_color
                obj.keyframe_insert(data_path="color", frame=start_f)
                
            # CRÍTICO: Restaurar el estado oculto para que no sea visible antes de la animación
            obj.hide_viewport = True
            obj.hide_render = True

    @classmethod
    def get_product_frames_with_ColorTypes(cls, work_schedule, settings):
            """Versión mejorada con soporte de perfiles y 'states' compatibles.
            Si existe el método 'get_animation_product_frames_enhanced', lo utiliza y retorna su estructura,
            garantizando así compatibilidad con apply_ColorType_animation.
            """
            # Guarantees DEFAULT group if the user has not configured anything
            try:
                UnifiedColorTypeManager.ensure_default_group(bpy.context)
            except Exception:
                pass

            # We prefer the existing 'enhanced' path to maintain compatibility
            try:
                frames = cls.get_animation_product_frames_enhanced(work_schedule, settings)
                if isinstance(frames, dict):
                    return frames
            except Exception:
                pass

            # Fallback: build product->frames with minimal states from the basic method
            basic = cls.get_animation_product_frames(work_schedule, settings)
            product_frames = {}
            for pid, items in (basic or {}).items():
                product_frames[pid] = []
                for it in items:
                    start_f = it.get("STARTED")
                    finish_f = it.get("COMPLETED")
                    if start_f is None or finish_f is None:
                        continue
                    product_frames[pid].append({
                        "task": None,
                        "task_id": 0,
                        "type": it.get("type") or "NOTDEFINED",
                        "relationship": it.get("relationship") or "output",
                        "start_date": settings.get("start"),
                        "finish_date": settings.get("finish"),
                        "STARTED": start_f,
                        "COMPLETED": finish_f,
                        "start_frame": start_f,
                        "finish_frame": finish_f,
                        "states": {
                            "before_start": (settings["start_frame"], max(settings["start_frame"], int(start_f) - 1)),
                            "active": (int(start_f), int(finish_f)),
                            "after_end": (min(int(finish_f) + 1, int(settings["start_frame"] + settings["total_frames"])), int(settings["start_frame"] + settings["total_frames"])),
                        },
                    })
            return product_frames

    @classmethod
    def _process_task_with_ColorTypes(cls, task, settings, product_frames, anim_props, ColorType_cache):
            """Procesa recursivamente una tarea, agregando frames con estados.
            Mantiene compatibilidad con la estructura 'enhanced'."""
            for subtask in ifcopenshell.util.sequence.get_nested_tasks(task):
                cls._process_task_with_ColorTypes(subtask, settings, product_frames, anim_props, ColorType_cache)

            # Dates
            start = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
            finish = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
            if not start or not finish:
                return

            # Precalculate frames
            start_frame = round(settings["start_frame"] + (((start - settings["start"]) / settings["duration"]) * settings["total_frames"]))
            finish_frame = round(settings["start_frame"] + (((finish - settings["start"]) / settings["duration"]) * settings["total_frames"]))

            # Cache de perfil (aunque el perfil puede resolverse en apply)
            task_id = task.id()
            if task_id not in ColorType_cache:
                ColorType_cache[task_id] = cls._get_best_ColorType_for_task(task, anim_props)

            def _add(pid, relationship):
                product_frames.setdefault(pid, []).append({
                    "task": task,
                    "task_id": task.id(),
                    "type": task.PredefinedType or "NOTDEFINED",
                    "relationship": relationship,
                    "start_date": start,
                    "finish_date": finish,
                    "STARTED": start_frame,
                    "COMPLETED": finish_frame,
                    "start_frame": start_frame,
                    "finish_frame": finish_frame,
                    "states": {
                        "before_start": (settings["start_frame"], max(settings["start_frame"], start_frame - 1)),
                        "active": (start_frame, finish_frame),
                        "after_end": (min(finish_frame + 1, int(settings["start_frame"] + settings["total_frames"])), int(settings["start_frame"] + settings["total_frames"])),
                    },
                })

            for output in ifcopenshell.util.sequence.get_task_outputs(task):
                _add(output.id(), "output")
            for input_prod in cls.get_task_inputs(task):
                _add(input_prod.id(), "input")


    @classmethod
    def get_animation_product_frames_enhanced(cls, work_schedule: ifcopenshell.entity_instance, settings: dict[str, Any]):
        animation_start = int(settings["start_frame"])
        animation_end = int(settings["start_frame"] + settings["total_frames"])
        viz_start = settings["start"]
        viz_finish = settings["finish"]
        viz_duration = settings["duration"]
        product_frames: dict[int, list] = {}
        
        # --- NUEVO: Obtener la fuente de fechas desde las propiedades ---
        props = cls.get_work_schedule_props()
        date_source = getattr(props, "date_source_type", "SCHEDULE")
        start_date_type = f"{date_source.capitalize()}Start"
        finish_date_type = f"{date_source.capitalize()}Finish"

        def add_product_frame_enhanced(product_id, task, start_date, finish_date, start_frame, finish_frame, relationship):
            if finish_date < viz_start:
                states = {
                    "before_start": (animation_start, animation_start - 1),
                    "active": (animation_start, animation_start - 1),
                    "after_end": (animation_start, animation_end),
                }
            elif start_date > viz_finish:
                return
            else:
                s_vis = max(animation_start, int(start_frame))
                f_vis = min(animation_end, int(finish_frame))
                if f_vis < s_vis:
                    s_vis = max(animation_start, min(animation_end, s_vis))
                    f_vis = s_vis
                before_end = s_vis - 1
                after_start = f_vis + 1
                states = {
                    "before_start": (animation_start, before_end) if before_end >= animation_start else (animation_start, animation_start - 1),
                    "active": (s_vis, f_vis),
                    "after_end": (after_start if after_start <= animation_end else animation_end + 1, animation_end),
                }

            product_frames.setdefault(product_id, []).append({
                "task": task, "task_id": task.id(),
                "type": getattr(task, "PredefinedType", "NOTDEFINED"),
                "relationship": relationship,
                "start_date": start_date, "finish_date": finish_date,
                "STARTED": int(start_frame), "COMPLETED": int(finish_frame),
                "start_frame": max(animation_start, int(start_frame)),
                "finish_frame": min(animation_end, int(finish_frame)),
                "states": states,
            })

        def add_product_frame_full_range(product_id, task, relationship):
            states = { "active": (animation_start, animation_end) }
            product_frames.setdefault(product_id, []).append({
                "task": task, "task_id": task.id(),
                "type": getattr(task, "PredefinedType", "NOTDEFINED"),
                "relationship": relationship,
                "start_date": viz_start, "finish_date": viz_finish,
                "STARTED": animation_start, "COMPLETED": animation_end,
                "start_frame": animation_start, "finish_frame": animation_end,
                "states": states,
                "consider_start_active": True,
            })
            print(f"🔒 Product {product_id}: Frame de rango completo (ignora fechas) creado.")

        def preprocess_task(task):
            for subtask in ifcopenshell.util.sequence.get_nested_tasks(task):
                preprocess_task(subtask)

           
            task_start = ifcopenshell.util.sequence.derive_date(task, start_date_type, is_earliest=True)
            task_finish = ifcopenshell.util.sequence.derive_date(task, finish_date_type, is_latest=True)
            if not task_start or not task_finish:
                return

            
            # Obtener el perfil completo para verificar la combinación de estados, no solo 'consider_start'.
            ColorType = cls._get_best_ColorType_for_task(task, cls.get_animation_props())
            is_priority_mode = (
                getattr(ColorType, 'consider_start', False) and
                not getattr(ColorType, 'consider_active', True) and
                not getattr(ColorType, 'consider_end', True)
            )

            # If it is priority mode, IGNORE DATES and use the full range.
            if is_priority_mode:
                print(f"🔒 Tarea '{task.Name}' en modo prioritario. Ignorando fechas.")
                for output in ifcopenshell.util.sequence.get_task_outputs(task):
                    add_product_frame_full_range(output.id(), task, "output")
                for input_prod in cls.get_task_inputs(task):
                    add_product_frame_full_range(input_prod.id(), task, "input")
                return

            # If it is NOT priority mode, use the task dates to calculate the frames.
            if task_start > viz_finish:
                return

            if viz_duration.total_seconds() > 0:
                start_progress = (task_start - viz_start).total_seconds() / viz_duration.total_seconds()
                finish_progress = (task_finish - viz_start).total_seconds() / viz_duration.total_seconds()
            else:
                start_progress, finish_progress = 0.0, 1.0

            sf = int(round(settings["start_frame"] + (start_progress * settings["total_frames"])))
            ff = int(round(settings["start_frame"] + (finish_progress * settings["total_frames"])))

            for output in ifcopenshell.util.sequence.get_task_outputs(task):
                add_product_frame_enhanced(output.id(), task, task_start, task_finish, sf, ff, "output")
            for input_prod in cls.get_task_inputs(task):
                add_product_frame_enhanced(input_prod.id(), task, task_start, task_finish, sf, ff, "input")

        for root_task in ifcopenshell.util.sequence.get_root_tasks(work_schedule):
            preprocess_task(root_task)

        return product_frames


    @classmethod
    def apply_visibility_animation(cls, obj, frame_data, ColorType):
        """Applies only the visibility (hide/show) keyframes for live update mode."""
        # Nota: Los keyframes en frame 0 ya se establecieron en animate_objects_with_ColorTypes
        
        for state_name, (start_f, end_f) in frame_data["states"].items():
            if end_f < start_f:
                continue

            # Logic for hiding objects based on state and ColorType properties
            is_hidden = False
            if state_name == "before_start" and not getattr(ColorType, 'consider_start', True) and frame_data.get("relationship") == "output":
                is_hidden = True
            elif state_name == "after_end" and getattr(ColorType, 'hide_at_end', False):
                is_hidden = True

            obj.hide_viewport = obj.hide_render = is_hidden
            obj.keyframe_insert(data_path="hide_viewport", frame=start_f)
            obj.keyframe_insert(data_path="hide_render", frame=start_f)
            if end_f > start_f:
                obj.keyframe_insert(data_path="hide_viewport", frame=end_f)
                obj.keyframe_insert(data_path="hide_render", frame=end_f)

    @classmethod
    def debug_ColorType_application(cls, obj, ColorType, frame_data):
        """Debug helper para verificar aplicación de perfiles"""
        print(f"🔍 DEBUG ColorType Application:")
        print(f"   Object: {obj.name}")
        print(f"   ColorType: {getattr(ColorType, 'name', 'Unknown')}")
        print(f"   consider_start: {getattr(ColorType, 'consider_start', False)}")
        print(f"   consider_active: {getattr(ColorType, 'consider_active', True)}")
        print(f"   consider_end: {getattr(ColorType, 'consider_end', True)}")
        print(f"   Frame states: {frame_data.get('states', {})}")
        print(f"   Relationship: {frame_data.get('relationship', 'unknown')}")

    _live_color_update_handler = None

    @classmethod
    def live_color_update_handler(cls, scene, depsgraph=None):
        """Frame change handler to dynamically update object colors."""
        print(f"[DEBUG] *** HANDLER TRIGGERED *** Frame: {scene.frame_current}")
        
        # CHECK: Verificar si está en modo de varianza
        is_variance_mode = scene.get('BIM_VarianceColorModeActive', False)
        if is_variance_mode:
            print("[DEBUG] Variance mode active, using variance color logic")
            cls._variance_aware_color_update()
            return
        
        # Debug: Check what scene properties exist
        scene_props = [key for key in scene.keys() if 'BIM' in key]
        print(f"[DEBUG] Scene BIM properties: {scene_props}")
        
        # Use get() method instead of hasattr() for scene properties
        live_props = scene.get('BIM_LiveUpdateProductFrames')
        if not live_props:
            print("[DEBUG] No BIM_LiveUpdateProductFrames found in scene")
            return
        product_frames = live_props.get("product_frames", {})
        original_colors = live_props.get("original_colors", {})
        if not product_frames:
            print("[DEBUG] No product_frames in live_props")
            return

        print(f"[DEBUG] Found {len(product_frames)} products in cache")
        current_frame = scene.frame_current
        anim_props = cls.get_animation_props()

        # Determine active group
        active_group_name = "DEFAULT"
        for item in getattr(anim_props, "animation_group_stack", []):
            if getattr(item, "enabled", False) and getattr(item, "group", None):
                active_group_name = item.group
                break
        
        print(f"[DEBUG] Active group: {active_group_name}")
        
        # Ensure viewport shading shows object colors
        try:
            area = tool.Blender.get_view3d_area()
            if area and area.spaces[0].shading.color_type != "OBJECT":
                area.spaces[0].shading.color_type = "OBJECT"
                print("[DEBUG] Set viewport shading to OBJECT color")
        except Exception as e:
            print(f"[DEBUG] Could not set viewport shading: {e}")

        # Iterate through objects that have animation data
        objects_processed = 0
        objects_colored = 0
        for obj in bpy.data.objects:
            element = tool.Ifc.get_entity(obj)
            if not element:
                continue
                
            
            pid_str = str(element.id())
            if pid_str not in product_frames:
                continue

            objects_processed += 1
            frame_data_list = product_frames[pid_str]
            
            # Find the current state for the object
            current_frame_data = None
            current_state_name = None
            for fd in frame_data_list:
                for state_name, (start_f, end_f) in fd["states"].items():
                    if start_f <= current_frame <= end_f:
                        current_frame_data = fd
                        current_state_name = state_name
                        break
                if current_frame_data:
                    break
            
            if not current_frame_data:
                continue

            # Get the correct ColorType
            task_id = current_frame_data.get("task_id")
            task = current_frame_data.get("task")
            if not task and task_id:
                try:
                    task = tool.Ifc.get().by_id(task_id)
                except:
                    task = None
            
            if not task:
                # Cannot determine ColorType without task - skip coloring for this object
                print(f"[DEBUG] No task found for object {obj.name} (ID: {pid_str})")
                continue
                
            ColorType = cls.get_assigned_ColorType_for_task(task, anim_props, active_group_name)
            if not ColorType:
                predefined_type = getattr(task, "PredefinedType", "NOTDEFINED") or "NOTDEFINED"
                print(f"[DEBUG] No ColorType from assignment, trying predefined_type: {predefined_type}")
                ColorType = cls.load_ColorType_from_group(active_group_name, predefined_type) or cls.create_generic_ColorType(predefined_type)

            # Apply the color for the current state (without creating keyframes)
            state_map = {"before_start": "start", "active": "in_progress", "after_end": "end"}
            state = state_map.get(current_state_name)
            if not state:
                continue

            # --- START: Live Visibility Logic ---
            is_hidden = False
            if state == "start":
                if not getattr(ColorType, 'consider_start', True) and current_frame_data.get("relationship") == "output":
                    is_hidden = True
            elif state == "end":
                if getattr(ColorType, 'hide_at_end', False):
                    is_hidden = True
            
            obj.hide_viewport = is_hidden
            obj.hide_render = is_hidden

            if is_hidden:
                continue
            # --- END: Live Visibility Logic ---

            original_color = original_colors.get(pid_str, [1.0, 1.0, 1.0, 1.0])

            if state == "start":
                use_original = getattr(ColorType, 'use_start_original_color', False)
                color = original_color if use_original else list(ColorType.start_color[:])
                transparency = getattr(ColorType, 'start_transparency', 0.0)
            elif state == "in_progress":
                use_original = getattr(ColorType, 'use_active_original_color', False)
                color = original_color if use_original else list(ColorType.in_progress_color[:])
                transparency = getattr(ColorType, 'active_start_transparency', 0.0) # Simplified for live view
            else: # end
                use_original = getattr(ColorType, 'use_end_original_color', True)
                color = original_color if use_original else list(ColorType.end_color[:])
                transparency = getattr(ColorType, 'end_transparency', 0.0)

            alpha = 1.0 - transparency
            obj.color = (color[0], color[1], color[2], alpha)
            objects_colored += 1
            print(f"[DEBUG] Colored {obj.name} (state: {state}) with color: {color} alpha: {alpha}")
        
        print(f"[DEBUG] Processed {objects_processed} objects, colored {objects_colored} objects")



    @classmethod
    def register_live_color_update_handler(cls):
        # Check if handler is already registered
        if cls.live_color_update_handler not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(cls.live_color_update_handler)
            cls._live_color_update_handler = cls.live_color_update_handler
            print(f"[DEBUG] Live color update handler registered. Total handlers: {len(bpy.app.handlers.frame_change_post)}")
        else:
            print("[DEBUG] Live color update handler already registered")
        
        # Try different handler events as backup
        if cls.live_color_update_handler not in bpy.app.handlers.frame_change_pre:
            bpy.app.handlers.frame_change_pre.append(cls.live_color_update_handler)
            print("[DEBUG] Also registered in frame_change_pre")
        
        # Start timer-based fallback
        cls.start_live_update_timer()
        
        # Verify handler is actually in the list
        if cls.live_color_update_handler in bpy.app.handlers.frame_change_post:
            print("[DEBUG] Handler verification: FOUND in frame_change_post")
        else:
            print("[DEBUG] Handler verification: NOT FOUND in frame_change_post")


    # Timer-based fallback for live updates
    _live_update_timer = None
    _last_frame = -1

    @classmethod
    def start_live_update_timer(cls):
        """Start a timer to check for frame changes as fallback"""
        if cls._live_update_timer:
            return  # Timer already running
            
        def timer_callback():
            try:
                current_frame = bpy.context.scene.frame_current
                if current_frame != cls._last_frame:
                    cls._last_frame = current_frame
                    cls.live_color_update_handler(bpy.context.scene)
                    print(f"[DEBUG] Timer-based update for frame {current_frame}")
                return 0.1  # Check every 100ms
            except Exception as e:
                print(f"[DEBUG] Timer error: {e}")
                return None  # Stop timer on error
                
        cls._live_update_timer = bpy.app.timers.register(timer_callback)
        print("[DEBUG] Live update timer started")


    @classmethod
    def stop_live_update_timer(cls):
        """Stop the timer-based fallback"""
        if cls._live_update_timer:
            try:
                bpy.app.timers.unregister(cls._live_update_timer)
            except:
                pass
            cls._live_update_timer = None
            print("[DEBUG] Live update timer stopped")

    @classmethod
    def unregister_live_color_update_handler(cls):
        # Stop timer
        cls.stop_live_update_timer()
        
        # Remove from handlers
        if cls._live_color_update_handler and cls._live_color_update_handler in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.remove(cls._live_color_update_handler)
        if cls._live_color_update_handler and cls._live_color_update_handler in bpy.app.handlers.frame_change_pre:
            bpy.app.handlers.frame_change_pre.remove(cls._live_color_update_handler)
            
        cls._live_color_update_handler = None
        if bpy.context.scene.get('BIM_LiveUpdateProductFrames'):
            del bpy.context.scene['BIM_LiveUpdateProductFrames']
            print("[DEBUG] Removed BIM_LiveUpdateProductFrames from scene")

            # === Multi-Text 4D Display System ===
            _frame_change_handler = None












