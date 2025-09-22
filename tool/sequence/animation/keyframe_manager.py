# -*- coding: utf-8 -*-
"""
Keyframe Management Module for 4D BIM Sequence Animation
=======================================================

This module handles all keyframe creation, management, and optimization operations
for 4D BIM sequence animations in Blender. It provides efficient keyframe insertion,
orbital camera animation, visibility/color animation, and batch processing.

EXTRACTED from sequence.py - 10 methods total
EXACT COPY - no modifications to preserve compatibility
"""

import bpy
import time
import json
import math
import mathutils
from datetime import datetime


class KeyframeManager:
    """
    Comprehensive keyframe management system for 4D BIM animations.
    Handles visibility keyframes, color keyframes, orbital animations, and batch operations.
    """

    @classmethod
    def _create_keyframe_orbit(cls, cam_obj, center, radius, z, angle0, start_frame, end_frame, sign, mode):
        """Create orbital camera animation keyframes. EXACT COPY from sequence.py line ~1078"""
        import math, mathutils
        # Get animation props from bpy directly to avoid circular import
        try:
            anim = bpy.context.scene.BIMAnimationProperties
        except AttributeError:
            # Fallback for mock environments
            class MockAnim:
                class camera_orbit:
                    pass
            anim = MockAnim()
        camera_props = anim.camera_orbit

        def pt(theta):
            x = center.x + radius * math.cos(theta)
            y = center.y + radius * math.sin(theta)
            return mathutils.Vector((x, y, z))

        def key_loc(obj, loc, frame):
            obj.location = loc
            obj.keyframe_insert("location", frame=frame)

        if mode == "CIRCLE_360":
            # CORRECT METHOD: Use Empty pivot with only 2 keyframes for perfect smoothness

            # 1. Create Empty pivot at center
            import bpy
            empty_name = f"Camera_Pivot_{cam_obj.name}"

            # Remove existing pivot if it exists
            if empty_name in bpy.data.objects:
                bpy.data.objects.remove(bpy.data.objects[empty_name], do_unlink=True)

            # Create new empty at center
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=center)
            pivot = bpy.context.active_object
            pivot.name = empty_name

            # 2. Parent camera to empty and position it
            cam_obj.parent = pivot
            cam_obj.parent_type = 'OBJECT'
            cam_obj.location = (radius, 0, z - center.z)  # Relative to pivot

            # 3. Set initial rotation for starting angle
            pivot.rotation_euler[2] = angle0

            # 4. Animate pivot rotation with only 2 keyframes
            pivot.rotation_euler[2] = angle0
            pivot.keyframe_insert("rotation_euler", index=2, frame=start_frame)

            pivot.rotation_euler[2] = angle0 + sign * 2 * math.pi
            pivot.keyframe_insert("rotation_euler", index=2, frame=end_frame)

            # 5. AGGRESSIVE FORCE LINEAR interpolation for constant velocity
            if pivot.animation_data and pivot.animation_data.action:
                for fcurve in pivot.animation_data.action.fcurves:
                    if fcurve.data_path == "rotation_euler" and fcurve.array_index == 2:
                        for kf in fcurve.keyframe_points:
                            kf.interpolation = 'LINEAR'
                            kf.handle_left_type = 'AUTO'
                            kf.handle_right_type = 'AUTO'
                        fcurve.update()
        elif mode == "PINGPONG":
            # SIMPLE PINGPONG: Only 3 keyframes for smooth constant velocity
            mid_frame = start_frame + (end_frame - start_frame) // 2

            # Go from start angle to 180° and back - perfectly linear
            key_loc(cam_obj, pt(angle0), start_frame)                    # Start position
            key_loc(cam_obj, pt(angle0 + sign * math.pi), mid_frame)     # Opposite side (180°)
            key_loc(cam_obj, pt(angle0), end_frame)                      # Back to start

        # AGGRESSIVE FORCE: Always LINEAR for 360° keyframe method
        if cam_obj.animation_data and cam_obj.animation_data.action:
            for fcurve in cam_obj.animation_data.action.fcurves:
                if fcurve.data_path == "location":
                    if mode == "CIRCLE_360":
                        # Force LINEAR for all keyframes - no exceptions
                        for kp in fcurve.keyframe_points:
                            kp.interpolation = 'LINEAR'
                            kp.handle_left_type = 'AUTO'
                            kp.handle_right_type = 'AUTO'
                        fcurve.update()
                    else:
                        # PINGPONG: Always use LINEAR for consistency
                        for kp in fcurve.keyframe_points:
                            kp.interpolation = 'LINEAR'

    @classmethod
    def apply_visibility_animation(cls, obj, frame_data, ColorType):
        """Applies only the visibility (hide/show) keyframes for live update mode. EXACT COPY from sequence.py line ~4641"""
        # Nota: Los keyframes en frame 0 ya se establecieron en animate_objects_with_ColorTypes

        for state_name, (start_f, end_f) in frame_data["states"].items():
            if end_f < start_f:
                continue

            # Logic for hiding objects based on state and ColorType properties
            is_hidden = False
            if state_name == "before_start" and not getattr(ColorType, 'consider_start', False) and frame_data.get("relationship") == "output":
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
        """Debug helper to verify profile application. EXACT COPY from sequence.py line ~4664"""
        print(f"[CHECK] DEBUG ColorType Application:")
        print(f"   Object: {obj.name}")
        print(f"   ColorType: {getattr(ColorType, 'name', 'Unknown')}")
        print(f"   consider_start: {getattr(ColorType, 'consider_start', False)}")
        print(f"   consider_active: {getattr(ColorType, 'consider_active', True)}")
        print(f"   consider_end: {getattr(ColorType, 'consider_end', True)}")
        print(f"   Frame states: {frame_data.get('states', {})}")
        print(f"   Relationship: {frame_data.get('relationship', 'unknown')}")

    @classmethod
    def apply_ColorType_animation(cls, obj, frame_data, ColorType, original_color, settings):
        """
        Aplica la animación a un objeto basándose en su perfil de apariencia.
        RESTAURADO: Lógica exacta de v110 para manejo de consider flags.
        EXACT COPY from sequence.py line ~4679
        """
        # Limpiar cualquier animación previa en este objeto para empezar de cero.
        if obj.animation_data:
            obj.animation_data_clear()

        # V110 LOGIC: Verificar consider_start_active (priority mode)
        if frame_data.get("consider_start_active", False):
            print(f"🔒 APPLY_COLORTYPE: {obj.name} detectado consider_start_active=True (Start prioritario)")
            start_f, end_f = frame_data["states"]["active"]
            print(f"   Range: {start_f} to {end_f}")
            print(f"   Llamando apply_state_appearance(state='start')")
            cls.apply_state_appearance(obj, ColorType, "start", start_f, end_f, original_color, frame_data)
            print(f"   Visibilidad después: viewport={not obj.hide_viewport}, render={not obj.hide_render}")
            return

        # V110 LOGIC: Verificar flags una sola vez al inicio
        has_consider_start = getattr(ColorType, 'consider_start', False)
        is_active_considered = getattr(ColorType, 'consider_active', True)
        is_end_considered = getattr(ColorType, 'consider_end', True)

        # V110 LOGIC: Procesar cada estado por separado con lógica original
        for state_name, (start_f, end_f) in frame_data["states"].items():
            if end_f < start_f:
                continue

            state_map = {"before_start": "start", "active": "in_progress", "after_end": "end"}
            state = state_map.get(state_name)
            if not state:
                continue

            # === V110 LOGIC RESTORATION ===
            # La lógica "start" está separada para manejar ocultación explícita.
            if state == "start":
                if not has_consider_start:
                    # Si 'Start' NO se considera y es un objeto de construcción ('output'),
                    # debe estar OCULTO hasta que empiece su fase 'Active'.
                    if frame_data.get("relationship") == "output":
                        obj.hide_viewport = True
                        obj.hide_render = True
                        obj.keyframe_insert(data_path="hide_viewport", frame=start_f)
                        obj.keyframe_insert(data_path="hide_render", frame=start_f)
                        if end_f > start_f:
                            obj.keyframe_insert(data_path="hide_viewport", frame=end_f)
                            obj.keyframe_insert(data_path="hide_render", frame=end_f)
                    # Para inputs (demolición), no hacer nada los mantiene visibles, lo cual es correcto.
                    continue  # Continuar al siguiente estado.
                # Si 'Start' SÍ se considera, aplicar su apariencia.
                cls.apply_state_appearance(obj, ColorType, "start", start_f, end_f, original_color, frame_data)

            elif state == "in_progress":
                if not is_active_considered:
                    continue
                cls.apply_state_appearance(obj, ColorType, "in_progress", start_f, end_f, original_color, frame_data)

            elif state == "end":
                if not is_end_considered:
                    continue
                cls.apply_state_appearance(obj, ColorType, "end", start_f, end_f, original_color, frame_data)

    @classmethod
    def apply_state_appearance(cls, obj, ColorType, state, start_frame, end_frame, original_color, frame_data=None):
        """V110 LOGIC: Apply appearance for a specific state. EXACT COPY from sequence.py line ~4742"""
        if state == "start":
            # V110: Cuando consider_start=True, el objeto debe ser siempre visible
            print(f"   📦 APPLY_STATE_APPEARANCE: Aplicando estado 'start' a {obj.name}")
            print(f"      Antes: viewport={not obj.hide_viewport}, render={not obj.hide_render}")
            obj.hide_viewport = False
            obj.hide_render = False
            print(f"      Después: viewport={not obj.hide_viewport}, render={not obj.hide_render}")
            obj.keyframe_insert(data_path="hide_viewport", frame=start_frame)
            obj.keyframe_insert(data_path="hide_render", frame=start_frame)

            use_original = getattr(ColorType, 'use_start_original_color', False)
            color = original_color if use_original else list(ColorType.start_color)
            transparency = getattr(ColorType, 'start_transparency', 0.0)
            alpha = 1.0 - transparency
            obj.color = (color[0], color[1], color[2], alpha)
            obj.keyframe_insert(data_path="color", frame=start_frame)

            if end_frame > start_frame:
                obj.keyframe_insert(data_path="hide_viewport", frame=end_frame)
                obj.keyframe_insert(data_path="hide_render", frame=end_frame)
                obj.keyframe_insert(data_path="color", frame=end_frame)

        elif state == "in_progress":
            obj.hide_viewport = False
            obj.hide_render = False
            obj.keyframe_insert(data_path="hide_viewport", frame=start_frame)
            obj.keyframe_insert(data_path="hide_render", frame=start_frame)

            use_original = getattr(ColorType, 'use_active_original_color', False)
            color = original_color if use_original else list(ColorType.in_progress_color)

            start_transparency = getattr(ColorType, 'active_start_transparency', 0.0)
            end_transparency = getattr(ColorType, 'active_finish_transparency', 0.0)
            start_alpha = 1.0 - start_transparency
            end_alpha = 1.0 - end_transparency

            obj.color = (color[0], color[1], color[2], start_alpha)
            obj.keyframe_insert(data_path="color", frame=start_frame)

            if end_frame > start_frame:
                obj.color = (color[0], color[1], color[2], end_alpha)
                obj.keyframe_insert(data_path="color", frame=end_frame)

        elif state == "end":
            should_hide_at_end = getattr(ColorType, 'hide_at_end', False)

            if should_hide_at_end:
                obj.hide_viewport = True
                obj.hide_render = True
                obj.keyframe_insert(data_path="hide_viewport", frame=start_frame)
                obj.keyframe_insert(data_path="hide_render", frame=start_frame)
            else:
                obj.hide_viewport = False
                obj.hide_render = False
                obj.keyframe_insert(data_path="hide_viewport", frame=start_frame)
                obj.keyframe_insert(data_path="hide_render", frame=start_frame)

                use_original = getattr(ColorType, 'use_end_original_color', True)
                color = original_color if use_original else list(ColorType.end_color)
                transparency = getattr(ColorType, 'end_transparency', 0.0)
                alpha = 1.0 - transparency
                obj.color = (color[0], color[1], color[2], alpha)
                obj.keyframe_insert(data_path="color", frame=start_frame)

                if end_frame > start_frame:
                    obj.keyframe_insert(data_path="hide_viewport", frame=end_frame)
                    obj.keyframe_insert(data_path="hide_render", frame=end_frame)
                    obj.keyframe_insert(data_path="color", frame=end_frame)

        # CRÍTICO: Restaurar el estado oculto después de establecer keyframes
        obj.hide_viewport = True
        obj.hide_render = True

    @classmethod
    def _add_optimized_priority_frame(cls, product_frames, product_id, task, relationship, animation_start, animation_end):
        """Add priority mode frame (START only activated) to optimized product frames. EXACT COPY from sequence.py line ~8231"""
        states = { "active": (animation_start, animation_end) }

        frame_data = {
            "task": task, "task_id": task.id(),
            "type": getattr(task, "PredefinedType", "NOTDEFINED"),
            "relationship": relationship,
            "start_date": None, "finish_date": None,  # Dates ignored in priority mode
            "STARTED": animation_start, "COMPLETED": animation_end,
            "start_frame": animation_start, "finish_frame": animation_end,
            "states": states,
            "consider_start_active": True,  # KEY FLAG for priority mode
        }

        product_frames.setdefault(product_id, []).append(frame_data)
        print(f"   🔧 Added priority frame for product {product_id}: consider_start_active={frame_data['consider_start_active']}")

    @classmethod
    def _add_optimized_product_frame(cls, product_frames, product_id, task, start_date, finish_date,
                                   start_frame, finish_frame, relationship, animation_start, animation_end,
                                   viz_start, viz_finish):
        """Optimized version of add_product_frame_enhanced. EXACT COPY from sequence.py line ~8250"""
        # Fast state calculation
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

        # Create optimized frame data
        frame_data = {
            "task": task,
            "task_id": task.id(),
            "type": getattr(task, "PredefinedType", "NOTDEFINED"),
            "relationship": relationship,
            "start_date": start_date,
            "finish_date": finish_date,
            "STARTED": int(start_frame),
            "COMPLETED": int(finish_frame),
            "start_frame": max(animation_start, int(start_frame)),
            "finish_frame": min(animation_end, int(finish_frame)),
            "states": states,
        }

        product_frames.setdefault(product_id, []).append(frame_data)

    @classmethod
    def _apply_object_animation_optimized(cls, obj, frame_data, colortype, settings, visibility_ops, color_ops):
        """
        Apply animation to object efficiently WITH CONSIDER FLAGS SUPPORT
        RESTAURADO: Lógica de v110 para consider flags pero con optimizaciones batch
        EXACT COPY from sequence.py line ~8531
        """
        states = frame_data.get("states", {})

        # V110 LOGIC: Verificar consider flags exactamente como en v110
        has_consider_start = colortype.get('consider_start', True)
        is_active_considered = colortype.get('consider_active', True)
        is_end_considered = colortype.get('consider_end', True)

        # V110 LOGIC: Procesar cada estado con consider flags
        for state_name, (start_f, end_f) in states.items():
            if end_f < start_f:
                continue

            state_map = {"before_start": "start", "active": "in_progress", "after_end": "end"}
            state = state_map.get(state_name)
            if not state:
                continue

            # === V110 LOGIC WITH BATCH OPTIMIZATION ===
            if state == "start":
                if not has_consider_start:
                    # Si 'Start' NO se considera y es un objeto de construcción ('output'),
                    # debe estar OCULTO durante toda la fase start
                    if frame_data.get("relationship") == "output":
                        visibility_ops.append({'obj': obj, 'frame': start_f, 'hide': True})
                        if end_f > start_f:
                            visibility_ops.append({'obj': obj, 'frame': end_f, 'hide': True})
                    continue  # Saltar al siguiente estado

                # Si 'Start' SÍ se considera, aplicar apariencia start
                visibility_ops.append({'obj': obj, 'frame': start_f, 'hide': False})
                if not colortype.get('use_start_original_color', False):
                    color = colortype.get('start_color', [1,1,1,1])
                    color_ops.append({'obj': obj, 'frame': start_f, 'color': tuple(color)})

            elif state == "in_progress":
                if not is_active_considered:
                    continue  # Saltar fase active

                # Aplicar apariencia active (optimizada)
                visibility_ops.append({'obj': obj, 'frame': start_f, 'hide': False})
                if not colortype.get('use_active_original_color', False):
                    color = colortype.get('in_progress_color', [0.5, 0.5, 0.5, 1])
                    color_ops.append({'obj': obj, 'frame': start_f, 'color': tuple(color)})

            elif state == "end":
                if not is_end_considered:
                    continue  # Saltar fase end

                # Aplicar apariencia end
                should_hide_at_end = colortype.get('hide_at_end', False)
                if should_hide_at_end:
                    visibility_ops.append({'obj': obj, 'frame': start_f, 'hide': True})
                else:
                    visibility_ops.append({'obj': obj, 'frame': start_f, 'hide': False})
                    if not colortype.get('use_end_original_color', True):
                        color = colortype.get('end_color', [0.3, 0.3, 0.3, 1])
                        color_ops.append({'obj': obj, 'frame': start_f, 'color': tuple(color)})

    @classmethod
    def clear_objects_animation_optimized(cls, include_blender_objects=True):
        """Optimized animation cleanup. EXACT COPY from sequence.py line ~8606"""
        import time
        start_time = time.time()

        # Use cache to avoid massive iteration - fallback implementation
        try:
            # Direct access to avoid circular import
            import bpy
            scene = bpy.context.scene

            # Check if performance cache exists in scene properties
            if hasattr(scene, 'BIMSequenceProperties') and hasattr(scene.BIMSequenceProperties, 'performance_cache'):
                cache = scene.BIMSequenceProperties.performance_cache
                if not getattr(cache, 'cache_valid', False):
                    # Trigger cache rebuild if available
                    if hasattr(cache, 'build_scene_cache'):
                        cache.build_scene_cache()
            else:
                cache = None

            # Clean only relevant IFC objects
            cleaned_objects = []
            for obj in cache.scene_objects_cache:
                if obj.type == 'MESH':
                    entity = cache.get_ifc_entity(obj)
                    if entity and not entity.is_a("IfcSpace"):
                        if obj.animation_data:
                            obj.animation_data_clear()
                        obj.hide_viewport = False
                        obj.hide_render = False
                        obj.color = (1.0, 1.0, 1.0, 1.0)
                        cleaned_objects.append(obj)

            elapsed = time.time() - start_time
            print(f"[CLEAN] OPTIMIZED CLEANUP: {len(cleaned_objects)} objects in {elapsed:.2f}s")
        except Exception as e:
            print(f"[WARNING] Performance cache not available, using fallback cleanup: {e}")
            # Fallback to basic cleanup
            cleaned_objects = []
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    if obj.animation_data:
                        obj.animation_data_clear()
                    obj.hide_viewport = False
                    obj.hide_render = False
                    obj.color = (1.0, 1.0, 1.0, 1.0)
                    cleaned_objects.append(obj)

            elapsed = time.time() - start_time
            print(f"[CLEAN] FALLBACK CLEANUP: {len(cleaned_objects)} objects in {elapsed:.2f}s")


# Compatibility function for direct access
def get_keyframe_manager():
    """Get the KeyframeManager instance"""
    return KeyframeManager