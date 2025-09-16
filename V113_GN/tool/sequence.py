# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>
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
import os
import re
import bpy
import time  # For performance timing
from bonsai.bim.module.sequence import data as _seq_data
from bonsai.bim.module.sequence.data import SequenceCache  # Import the new cache
import json
import base64
import ifcopenshell.api.sequence
import pystache
import mathutils
import webbrowser
import isodate
from typing import List  # For type hints
import ifcopenshell
import ifcopenshell.api.group
import ifcopenshell.ifcopenshell_wrapper as W
import ifcopenshell.util.date
import ifcopenshell.util.selector
import ifcopenshell.util.sequence
import bonsai.core.tool
import bonsai.tool as tool
import bonsai.bim.helper
from dateutil import parser
from datetime import datetime
from datetime import time as datetime_time
from typing import Optional, Any, Union, Literal, TYPE_CHECKING
from typing import Union
from collections.abc import Iterable
from mathutils import Color

# Import snapshot functions from operator module
try:
    from ..operator import snapshot_all_ui_state, restore_all_ui_state
except ImportError:
    # Fallback if import fails
    def snapshot_all_ui_state(context):
        pass
    def restore_all_ui_state(context):
        pass

if TYPE_CHECKING:
    from bonsai.bim.prop import Attribute
    from bonsai.bim.module.sequence.prop import (
        BIMAnimationProperties,
        BIMStatusProperties,
        BIMTaskTreeProperties,
        BIMWorkCalendarProperties,
        BIMWorkPlanProperties,
        BIMWorkScheduleProperties,
    )


class Sequence(bonsai.core.tool.Sequence):

    ELEMENT_STATUSES = ("NEW", "EXISTING", "DEMOLISH", "TEMPORARY", "OTHER", "NOTKNOWN", "UNSET")

    # === START OF ADDED CODE ===
    @classmethod
    def apply_selection_from_checkboxes(cls):
        """
        Selecciona en el viewport los objetos 3D de todas las tareas marcadas con el checkbox.
        Deselecciona todo lo demás.
        Selects the 3D objects of all tasks marked with the checkbox in the viewport. Deselects everything else.
        """
        try:
            tprops = cls.get_task_tree_props()
            if not tprops:
                return

            # 1. Obtener todas las tareas que están marcadas con el checkbox
            # 1. Get all tasks that are marked with the checkbox
            selected_tasks_pg = [task_pg for task_pg in tprops.tasks if getattr(task_pg, 'is_selected', False)]

            # 2. Deselect everything in the scene
            bpy.ops.object.select_all(action='DESELECT')

            # 3. If no tasks are marked, finish
            if not selected_tasks_pg:
                return

            # 4. Collect all objects to select
            objects_to_select = []
            for task_pg in selected_tasks_pg:
                task_ifc = tool.Ifc.get().by_id(task_pg.ifc_definition_id)
                if not task_ifc:
                    continue
                
                outputs = cls.get_task_outputs(task_ifc)
                for product in outputs:
                    obj = tool.Ifc.get_object(product)
                    if obj:
                        objects_to_select.append(obj)

            # 5. Select all collected objects
            if objects_to_select:
                for obj in objects_to_select:
                    obj.select_set(True)
                # Make the first object in the list the active one
                bpy.context.view_layer.objects.active = objects_to_select[0]

        except Exception as e:
            print(f"Error applying selection from checkboxes: {e}")
   

    @classmethod
    def is_bonsai_camera(cls, obj):
        """Verifica si un objeto es una cámara gestionada por las herramientas 4D/Snapshot de Bonsai."""
        if not obj or obj.type != 'CAMERA':
            return False
        # La forma más fiable es verificar la propiedad personalizada.
        if obj.get('camera_context') in ['animation', 'snapshot']:
            return True
        # Fallback a convenciones de nombre por compatibilidad.
        if '4D_Animation_Camera' in obj.name or 'Snapshot_Camera' in obj.name:
            return True
        return False

    @classmethod
    def is_bonsai_animation_camera(cls, obj):
        """Verifica si un objeto es una cámara específica para los Ajustes de Animación."""
        if not obj or obj.type != 'CAMERA':
            return False
        # La identificación principal es a través de la propiedad personalizada.
        if obj.get('camera_context') == 'animation':
            return True
        # Fallback a convención de nombre (asegurándose de que no sea una de snapshot).
        if '4D_Animation_Camera' in obj.name and 'Snapshot' not in obj.name:
            return True
        return False

    @classmethod
    def is_bonsai_snapshot_camera(cls, obj):
        """Verifica si un objeto es una cámara específica para los Ajustes de Snapshot."""
        if not obj or obj.type != 'CAMERA':
            return False
        # La identificación principal es a través de la propiedad personalizada.
        if obj.get('camera_context') == 'snapshot':
            return True
        # Fallback a convención de nombre.
        if 'Snapshot_Camera' in obj.name:
            return True
        return False




    @classmethod
    def add_text_animation_handler(cls, settings):
        """Crea múltiples objetos de texto animados con soporte para HUD.
        Esta es una implementación de respaldo: intenta llamar a la versión existente si está disponible.
        """
        created_texts = []
        # ... aquí iría el código existente para crear textos ...
        try:
            base_impl = getattr(super(), "add_text_animation_handler", None)
            if callable(base_impl):
                created_texts = base_impl(settings)
        except Exception as e:
            print(f"Fallback add_text_animation_handler error: {e}")

        
        try:
            cls._register_multi_text_handler(settings)
        except Exception as e:
            print(f"Error registering multi text handler: {e}")

        # --- AUTOMATIC GPU HUD CONFIGURATION ---
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            # Auto-habilitar HUD GPU si hay cronograma válido
            if settings and settings.get("start") and settings.get("finish"):
                print("🎯 Auto-enabling GPU HUD for 4D animation...")
                # Enable GPU HUD automatically
                bpy.ops.bim.enable_schedule_hud()
                print("✅ GPU HUD auto-configured successfully")

        except Exception as e:
            print(f"⚠️ Auto-setup of GPU HUD failed: {e}")
        return created_texts


    @classmethod
    def load_ColorType_group_data(cls, group_name):
        """Loads data from a specific profile group"""
        import bpy, json
        scene = bpy.context.scene
        raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
            return data.get(group_name, {})
        except Exception:
            return {}

    @classmethod
    def get_all_ColorType_groups(cls):
        """Gets all available profile groups"""
        import bpy
        return UnifiedColorTypeManager.get_all_groups(bpy.context)

    @classmethod
    def get_custom_ColorType_groups(cls):
        """Gets only custom groups (without DEFAULT)"""
        import bpy
        return UnifiedColorTypeManager.get_user_created_groups(bpy.context)
    @classmethod
    def update_task_ICOM(cls, task: Union[ifcopenshell.entity_instance, None]) -> None:
        """Refreshes the ICOM data (Outputs, Inputs, Resources) of the panel for the active task.
        If there is no task, it clears the lists to avoid remnants of the previous task."""
        props = cls.get_work_schedule_props()
        if task:
            # Outputs
            outputs = cls.get_task_outputs(task) or []
            cls.load_task_outputs(outputs)
            # Inputs
            inputs = cls.get_task_inputs(task) or []
            cls.load_task_inputs(inputs)
            # Resources
            cls.load_task_resources(task)
        else:
            props.task_outputs.clear()
            props.task_inputs.clear()
            props.task_resources.clear()


    @classmethod
    def _get_active_schedule_bbox(cls):
        """Return (center (Vector), dims (Vector), obj_list) for active WorkSchedule products.
        Fallbacks to visible mesh objects if empty."""
        import bpy, mathutils
        ws = cls.get_active_work_schedule()
        objs = []
        if ws:
            try:
                products = cls.get_work_schedule_products(ws)  # IFC entities
                want_ids = {p.id() for p in products if hasattr(p, "id")}
                for obj in bpy.data.objects:
                    try:
                        if not hasattr(obj, "type") or obj.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
                            continue
                        if (ifc_id := tool.Blender.get_ifc_definition_id(obj)) and ifc_id in want_ids:
                            objs.append(obj)
                    except Exception:
                        continue
            except Exception:
                pass

        if not objs:
            # Fallback: all visible mesh objs
            objs = [o for o in bpy.data.objects if getattr(o, "type", "") == "MESH" and not o.hide_get()]

        if not objs:
            c = mathutils.Vector((0.0, 0.0, 0.0))
            d = mathutils.Vector((10.0, 10.0, 5.0))
            return c, d, []

        mins = mathutils.Vector(( 1e18,  1e18,  1e18))
        maxs = mathutils.Vector((-1e18, -1e18, -1e18))
        for o in objs:
            try:
                for corner in o.bound_box:
                    wc = o.matrix_world @ mathutils.Vector(corner)
                    mins.x = min(mins.x, wc.x); mins.y = min(mins.y, wc.y); mins.z = min(mins.z, wc.z)
                    maxs.x = max(maxs.x, wc.x); maxs.y = max(maxs.y, wc.y); maxs.z = max(maxs.z, wc.z)
            except Exception:
                continue
        center = (mins + maxs) * 0.5
        dims = (maxs - mins)
        return center, dims, objs

    @classmethod
    def _get_or_create_target(cls, center, name="4D_OrbitTarget"):


        name = name or "4D_OrbitTarget"
        obj = bpy.data.objects.get(name)
        if obj is None:
            obj = bpy.data.objects.new(name, None)
            obj.empty_display_type = 'PLAIN_AXES'
            try:
                bpy.context.collection.objects.link(obj)
            except Exception:
                bpy.context.scene.collection.objects.link(obj)
        obj.location = center
        return obj

    @classmethod
    def add_animation_camera(cls):
        """Create a camera using Animation Settings (Camera/Orbit) and optionally animate it."""
        import bpy, math, mathutils
        from mathutils import Vector
        import traceback

        print("🎥 === ADD_ANIMATION_CAMERA CALLED ===")
        print(f"🎥 Call stack: {traceback.format_stack()[-3:-1]}")  # Show who called this function
        
        # Props - CORREGIDO: usar la nueva estructura
        anim = cls.get_animation_props()
        camera_props = anim.camera_orbit  # NUEVO: acceso a propiedades de cámara
        ws_props = cls.get_work_schedule_props()
        
        current_orbit_mode = getattr(camera_props, 'orbit_mode', 'NONE')
        existing_camera = bpy.context.scene.camera
        
        print(f"🎥 Current orbit_mode: {current_orbit_mode}")
        print(f"🎥 Existing scene camera: {existing_camera.name if existing_camera else 'None'}")

        print("🎥 Creating 4D Animation Camera...")

        # --- ADDED LINE ---
        # CORRECTION: Get the dimensions and center of the scene BEFORE using them.
        center, dims, _ = cls._get_active_schedule_bbox()
        # ---------------------

        # Camera data - CORRECTED
        cam_data = bpy.data.cameras.new("4D_Animation_Camera")
        cam_data.lens = camera_props.camera_focal_mm
        cam_data.clip_start = max(0.0001, camera_props.camera_clip_start)

        # CORREGIDO: Escalar clip_end con el tamaño de la escena
        clip_end = camera_props.camera_clip_end
        auto_scale = max(dims.x, dims.y, dims.z) * 5.0  # Factor más conservador
        cam_data.clip_end = max(clip_end, auto_scale)

        print(f"📷 Camera settings: focal={{cam_data.lens}}mm, clip={{cam_data.clip_start}}-{{cam_data.clip_end}}")

        cam_obj = bpy.data.objects.new("4D_Animation_Camera", cam_data)
        cam_obj['is_4d_camera'] = True
        cam_obj['is_animation_camera'] = True
        cam_obj['camera_context'] = 'animation'
        try:
            bpy.context.collection.objects.link(cam_obj)
        except Exception:
            bpy.context.scene.collection.objects.link(cam_obj)

        # CORRECTION: Unique names for auxiliary objects
        target_name = f"4D_OrbitTarget_for_{{cam_obj.name}}"
        # Target (auto u objeto)
        if camera_props.look_at_mode == "OBJECT" and camera_props.look_at_object:
            target = camera_props.look_at_object
            print(f"📍 Using custom target: {{target.name}}")
        else:
            target = cls._get_or_create_target(center, target_name)
            print(f"📍 Created/using auto target '{{target_name}}' at: {{center}}")

        # CORRECTED: Compute radius & start angle
        if camera_props.orbit_radius_mode == "AUTO":
            # IMPROVED: Smarter radius calculation
            base = max(dims.x, dims.y)
            if base > 0:
                r = base * 1.5  # Factor más generoso
            else:
                r = 15.0  # Fallback más grande
            print(f"📐 Auto radius calculated: {{r:.2f}}m (from bbox: {{dims}})")
        else:
            r = max(0.01, camera_props.orbit_radius)
            print(f"📐 Manual radius: {{r:.2f}}m")

        z = center.z + camera_props.orbit_height
        angle0 = math.radians(camera_props.orbit_start_angle_deg)
        sign = -1.0 if camera_props.orbit_direction == "CW" else 1.0

        # CORRECTED: Initial placement
        initial_x = center.x + r * math.cos(angle0)
        initial_y = center.y + r * math.sin(angle0)
        cam_obj.location = Vector((initial_x, initial_y, z))
        print(f"📍 Initial camera position: ({{initial_x:.2f}}, {{initial_y:.2f}}, {{z:.2f}})")

        # CORRECTED: Always track target
        tcon = cam_obj.constraints.new(type='TRACK_TO')
        tcon.target = target
        tcon.track_axis = 'TRACK_NEGATIVE_Z'
        tcon.up_axis = 'UP_Y'
        print(f"🎯 Tracking target: {{target.name}}")

        # VERIFICAR: Orbit animation
        mode = camera_props.orbit_mode
        print(f"🎥 Checking orbit mode: {mode}")
        
        if mode == "NONE":
            print("🚫 Static camera mode - checking for existing aligned camera")
            
            # Si ya hay una cámara activa en la escena, usarla en lugar de la recién creada
            existing_camera = bpy.context.scene.camera
            print(f"🎥 Existing camera: {existing_camera.name if existing_camera else 'None'}")
            print(f"🎥 New camera: {cam_obj.name}")
            
            if existing_camera and existing_camera != cam_obj:
                print(f"📍 PRESERVING existing aligned camera: {existing_camera.name}")
                # Remover la cámara recién creada ya que no la necesitamos
                print(f"🗑️ DELETING newly created camera: {cam_obj.name}")
                bpy.data.objects.remove(cam_obj, do_unlink=True)
                # Usar la cámara existente
                bpy.context.scene.camera = existing_camera
                print(f"✅ Scene camera set to: {existing_camera.name}")
                return existing_camera
            else:
                print("📍 Using newly created static camera (no existing camera found)")
                bpy.context.scene.camera = cam_obj
                return cam_obj

        # CORRECTED: Determine timeline
        try:
            settings = cls.get_animation_settings()
            if settings:
                total_frames_4d = int(settings["total_frames"])
                start_frame = int(settings["start_frame"])
            else:
                raise Exception("No animation settings")
        except Exception as e:
            print(f"⚠️ Using fallback timeline: {{e}}")
            total_frames_4d = 250
            start_frame = 1

        # CORRECTED: Timeline calculation
        if camera_props.orbit_use_4d_duration:
            end_frame = start_frame + max(1, total_frames_4d - 1)
        else:
            end_frame = start_frame + int(max(1, camera_props.orbit_duration_frames))

        dur = max(1, end_frame - start_frame)
        print(f"⏱️ Animation timeline: frames {{start_frame}} to {{end_frame}} (duration: {{dur}})")

        # CORRECTED: Orbit animation implementation
        # RESTAURADO: Mantener método original pero con mejoras de fluidez
        if camera_props.orbit_path_method == "FOLLOW_PATH":
            print("🛤️ Creating OPTIMIZED Follow Path animation...")
            cls._create_follow_path_orbit(cam_obj, center, r, z, angle0, start_frame, end_frame, sign, mode)
        else:
            print("🔑 Creating OPTIMIZED Keyframe animation...")
            cls._create_keyframe_orbit(cam_obj, center, r, z, angle0, start_frame, end_frame, sign, mode)

        bpy.context.scene.camera = cam_obj
        print(f"✅ 4D Camera created successfully: {{cam_obj.name}}")
        return cam_obj

    @classmethod
    def add_snapshot_camera(cls):
        """Create a camera specifically for Snapshot Settings."""
        import bpy, math, mathutils
        from mathutils import Vector

        # Props - usar la estructura de animación para configuración básica
        anim = cls.get_animation_props()
        camera_props = anim.camera_orbit

        print("📷 Creating Snapshot Camera...")

        # Get scene bounding box
        center, dims, _ = cls._get_active_schedule_bbox()

        # Camera data
        cam_data = bpy.data.cameras.new("Snapshot_Camera")
        cam_data.lens = camera_props.camera_focal_mm
        cam_data.clip_start = max(0.0001, camera_props.camera_clip_start)

        # Scale clip_end with scene size
        clip_end = camera_props.camera_clip_end
        auto_scale = max(dims.length * 2.0, 100.0)
        cam_data.clip_end = max(clip_end, auto_scale)

        print(f"📷 Snapshot Camera settings: focal={cam_data.lens}mm, clip={cam_data.clip_start}-{cam_data.clip_end}")

        cam_obj = bpy.data.objects.new("Snapshot_Camera", cam_data)
        cam_obj['is_4d_camera'] = True
        cam_obj['is_snapshot_camera'] = True
        cam_obj['camera_context'] = 'snapshot'
        
        try:
            bpy.context.collection.objects.link(cam_obj)
        except Exception:
            bpy.context.scene.collection.objects.link(cam_obj)

        # Position camera at a reasonable distance from scene center
        radius = max(dims.length * 1.5, 20.0)
        height = center.z + dims.z * 0.5
        
        cam_obj.location = Vector((center.x + radius, center.y + radius, height))
        
        # Create and track target
        target = cls._get_or_create_target(center, "Snapshot_Target")
        tcon = cam_obj.constraints.new(type='TRACK_TO')
        tcon.target = target
        tcon.track_axis = 'TRACK_NEGATIVE_Z'
        tcon.up_axis = 'UP_Y'
        
        bpy.context.scene.camera = cam_obj
        print(f"✅ Snapshot Camera created successfully: {cam_obj.name}")
        
        # --- CREAR TEXTOS 3D SI NO EXISTEN ---
        # Verificar si ya existe la colección de textos 3D
        texts_collection = bpy.data.collections.get("Schedule_Display_Texts")
        if not texts_collection or len(texts_collection.objects) == 0:
            print("📝 Creating 3D texts for snapshot display...")
            try:
                # Obtener configuraciones básicas para los textos
                ws_props = cls.get_work_schedule_props()
                active_schedule_id = getattr(ws_props, "active_work_schedule_id", None)
                
                if active_schedule_id:
                    import bonsai.tool as tool
                    work_schedule = tool.Ifc.get().by_id(active_schedule_id)
                    schedule_name = work_schedule.Name if work_schedule and hasattr(work_schedule, 'Name') else 'No Schedule'
                    
                    # --- USAR EL MISMO ENFOQUE QUE LA ANIMACIÓN PRINCIPAL ---
                    # Obtener configuraciones completas de animación
                    try:
                        settings = cls.get_animation_settings()
                        if settings and work_schedule:
                            settings['schedule_name'] = schedule_name
                            
                            # Crear los textos 3D usando la función existente
                            cls.add_text_animation_handler(settings)
                            print("✅ 3D texts created using animation settings")
                        else:
                            # Fallback: crear manualmente si no hay settings
                            raise Exception("No animation settings available, using manual creation")
                            
                    except Exception as settings_error:
                        print(f"⚠️ Using fallback manual text creation: {settings_error}")
                        # FALLBACK: Crear manualmente los textos básicos
                        cls._create_basic_snapshot_texts(schedule_name)
                    
                    # --- APLICAR VISIBILIDAD SEGÚN CHECKBOX ---
                    anim_props = cls.get_animation_props()
                    camera_props = anim_props.camera_orbit
                    should_hide = not getattr(camera_props, "show_3d_schedule_texts", False)
                    
                    # Actualizar la colección después de crearla
                    texts_collection = bpy.data.collections.get("Schedule_Display_Texts")
                    if texts_collection:
                        texts_collection.hide_viewport = should_hide
                        texts_collection.hide_render = should_hide
                        print(f"✅ 3D texts created and visibility set (hidden: {should_hide})")
                    
                    # Auto-arrange texts para posicionamiento por defecto
                    try:
                        bpy.ops.bim.arrange_schedule_texts()
                        print("✅ 3D texts auto-arranged")
                    except Exception as e:
                        print(f"⚠️ Could not auto-arrange texts: {e}")
                        
                else:
                    print("⚠️ No active work schedule found, skipping 3D text creation")
                    
            except Exception as e:
                print(f"⚠️ Could not create 3D texts for snapshot camera: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("✅ 3D texts already exist, skipping creation")
        
        # --- CREAR 3D LEGEND HUD SI NO EXISTE ---
        # Verificar si ya existe el 3D Legend HUD
        legend_hud_exists = any(obj.get("is_3d_legend_hud", False) for obj in bpy.data.objects)
        if not legend_hud_exists:
            print("📊 Creating 3D Legend HUD for snapshot display...")
            try:
                anim_props = cls.get_animation_props()
                camera_props = anim_props.camera_orbit
                
                # Verificar si el 3D Legend HUD está habilitado
                legend_hud_enabled = getattr(camera_props, "enable_3d_legend_hud", False)
                show_3d_texts = getattr(camera_props, "show_3d_schedule_texts", False)
                
                if legend_hud_enabled and show_3d_texts:
                    # Crear el 3D Legend HUD
                    bpy.ops.bim.setup_3d_legend_hud()
                    print("✅ 3D Legend HUD created and configured")
                elif legend_hud_enabled and not show_3d_texts:
                    # Crear pero mantener oculto porque 3D HUD Render está desactivado
                    bpy.ops.bim.setup_3d_legend_hud()
                    # Ocultar inmediatamente
                    for obj in bpy.data.objects:
                        if obj.get("is_3d_legend_hud", False):
                            obj.hide_viewport = True
                            obj.hide_render = True
                    print("✅ 3D Legend HUD created but hidden (3D HUD Render disabled)")
                else:
                    print("📊 3D Legend HUD not enabled, skipping creation")
                    
            except Exception as e:
                print(f"⚠️ Could not create 3D Legend HUD for snapshot camera: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("✅ 3D Legend HUD already exists, skipping creation")
        
        return cam_obj

    @classmethod
    def _create_basic_snapshot_texts(cls, schedule_name):
        """Creates basic 3D texts manually when animation settings are not available."""
        import bpy
        
        # Create or get collection
        collection_name = "Schedule_Display_Texts"
        if collection_name not in bpy.data.collections:
            collection = bpy.data.collections.new(collection_name)
            try:
                bpy.context.scene.collection.children.link(collection)
            except Exception:
                pass
        else:
            collection = bpy.data.collections[collection_name]
        
        # Basic text configurations for snapshot
        text_configs = [
            {"name": "Schedule_Name", "position": (0, 10, 6), "content": f"Schedule: {schedule_name}", "type": "schedule_name"},
            {"name": "Schedule_Date", "position": (0, 10, 5), "content": "Date: [Dynamic]", "type": "date"},
            {"name": "Schedule_Week", "position": (0, 10, 4), "content": "Week: [Dynamic]", "type": "week"},
            {"name": "Schedule_Day_Counter", "position": (0, 10, 3), "content": "Day: [Dynamic]", "type": "day_counter"},
            {"name": "Schedule_Progress", "position": (0, 10, 2), "content": "Progress: [Dynamic]", "type": "progress"},
        ]
        
        for config in text_configs:
            try:
                # Create text data
                text_data = bpy.data.curves.new(name=config["name"], type='FONT')
                text_obj = bpy.data.objects.new(name=config["name"], object_data=text_data)
                
                # Set content and properties
                text_data.body = config["content"]
                text_data['text_type'] = config["type"]
                
                # Set alignment for consistent positioning
                if hasattr(text_data, 'align_x'):
                    text_data.align_x = 'CENTER'
                if hasattr(text_data, 'align_y'):
                    text_data.align_y = 'BOTTOM_BASELINE'
                
                # Position the text
                text_obj.location = config["position"]
                
                # Add to collection
                collection.objects.link(text_obj)
                
                print(f"✅ Created basic text: {config['name']}")
                
            except Exception as e:
                print(f"⚠️ Failed to create text {config['name']}: {e}")
        
        print("✅ Basic snapshot texts created manually")

    @classmethod
    def align_snapshot_camera_to_view(cls):
        """Aligns the active snapshot camera to the current 3D view."""
        import bpy

        # 1. Encontrar la ventana 3D activa
        area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
        if not area:
            raise Exception("No 3D viewport found.")

        space = next((s for s in area.spaces if s.type == 'VIEW_3D'), None)
        if not space:
            raise Exception("No 3D space data found.")

        # 2. Obtener la cámara activa de la escena
        cam_obj = bpy.context.scene.camera
        if not cam_obj:
            raise Exception("No active camera in the scene.")

        # 3. (Opcional) Verificar que es una cámara de snapshot
        if not cls.is_bonsai_snapshot_camera(cam_obj):
            print(f"Warning: Active camera '{cam_obj.name}' is not a designated snapshot camera, but aligning anyway.")

        # 4. Obtener la matriz de la vista y aplicarla a la cámara
        # La matriz de la vista nos da la transformación desde la perspectiva de la vista.
        # Necesitamos su inversa para posicionar la cámara correctamente en el mundo.
        region_3d = space.region_3d
        if region_3d:
            cam_obj.matrix_world = region_3d.view_matrix.inverted()
        else:
            raise Exception("Could not get 3D view region data.")
        

    @classmethod
    def align_animation_camera_to_view(cls):
        """
        Alinea la cámara de animación activa a la vista 3D y la convierte en estática.
        """
        import bpy

        area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
        space = next((s for s in area.spaces if s.type == 'VIEW_3D'), None) if area else None
        cam_obj = bpy.context.scene.camera

        if not all([area, space, cam_obj]):
            raise Exception("No se encontró la cámara o la vista 3D.")

        # Limpiar la animación y restricciones de la cámara para detener la órbita
        if cam_obj.animation_data:
            cam_obj.animation_data_clear()
        for c in list(cam_obj.constraints):
            cam_obj.constraints.remove(c)

        # Mover la cámara a la posición de la vista
        region_3d = space.region_3d
        if region_3d:
            cam_obj.matrix_world = region_3d.view_matrix.inverted()
        else:
            raise Exception("No se pudieron obtener los datos de la región 3D.")

        # (Paso Clave) Actualizar la UI para que el modo de órbita sea "Static"
        try:
            anim_props = cls.get_animation_props()
            camera_props = anim_props.camera_orbit
            camera_props.orbit_mode = 'NONE' # 'NONE' se muestra como "Static" en la UI
        except Exception as e:
            print(f"No se pudo actualizar la UI del modo de órbita: {e}")

    @classmethod
    def update_animation_camera(cls, cam_obj):
        """
        Actualiza una cámara 4D existente. Limpia sus datos viejos y aplica
        la configuración actual de la UI.
        """
        import bpy, math, mathutils
        from mathutils import Vector

        # 1. Completely clear the previous camera configuration
        if cam_obj.animation_data:
            cam_obj.animation_data_clear()

        for c in list(cam_obj.constraints):
            cam_obj.constraints.remove(c)

        # Clear the orbit path and target if they exist (unique names per camera)
        path_name = f"4D_OrbitPath_for_{cam_obj.name}"
        path_obj = bpy.data.objects.get(path_name)
        if path_obj:
            bpy.data.objects.remove(path_obj, do_unlink=True)
        # ARREGLADO: Usar nombres correctos de target
        target_name = f"4D_Target_for_{cam_obj.name}"
        tgt_obj = bpy.data.objects.get(target_name)
        if tgt_obj:
            bpy.data.objects.remove(tgt_obj, do_unlink=True)

        print(f"⚙️ Updating existing camera '{cam_obj.name}'...")

        # 2. Re-apply all settings, using the logic of add_animation_camera
        anim = cls.get_animation_props()
        camera_props = anim.camera_orbit

        # Recalculate target and dimensions
        center, dims, _ = cls._get_active_schedule_bbox()
        target_name = f"4D_OrbitTarget_for_{cam_obj.name}"

        if camera_props.look_at_mode == "OBJECT" and camera_props.look_at_object:
            target = camera_props.look_at_object
        else:
            target = cls._get_or_create_target(center, target_name)

        # Reconfigure camera data (lens, clipping)
        cam_data = cam_obj.data
        cam_data.lens = camera_props.camera_focal_mm
        cam_data.clip_start = camera_props.camera_clip_start
        cam_data.clip_end = max(camera_props.camera_clip_end, max(dims.x, dims.y, dims.z) * 5.0)

        # Check if we're in static mode BEFORE repositioning the camera
        mode = camera_props.orbit_mode
        
        if mode == "NONE":
            print(f"🔒 Static mode detected - PRESERVING camera position for '{cam_obj.name}'")
            # In static mode, do NOT reposition the camera or add tracking constraints
            # Keep the manually aligned position intact
        else:
            print(f"🔄 Orbit mode detected - repositioning camera for '{cam_obj.name}'")
            # Recalculate position only for non-static modes
            if camera_props.orbit_radius_mode == "AUTO":
                r = max(dims.x, dims.y) * 1.5 if max(dims.x, dims.y) > 0 else 15.0
            else:
                r = max(0.01, camera_props.orbit_radius)

            z = center.z + camera_props.orbit_height
            angle0 = math.radians(camera_props.orbit_start_angle_deg)
            cam_obj.location = Vector((center.x + r * math.cos(angle0), center.y + r * math.sin(angle0), z))

            # Re-create tracking constraint only for non-static modes
            tcon = cam_obj.constraints.new(type='TRACK_TO')
            tcon.target = target
            tcon.track_axis = 'TRACK_NEGATIVE_Z'
            tcon.up_axis = 'UP_Y'

        # Re-create orbit animation if configured
        if mode != "NONE":
            settings = cls.get_animation_settings()
            start_frame = settings["start_frame"]

            if camera_props.orbit_use_4d_duration:
                end_frame = start_frame + settings["total_frames"] -1
            else:
                end_frame = start_frame + int(camera_props.orbit_duration_frames)

            sign = -1.0 if camera_props.orbit_direction == "CW" else 1.0

            if camera_props.orbit_path_method == "FOLLOW_PATH":
                cls._create_follow_path_orbit(cam_obj, center, r, z, angle0, start_frame, end_frame, sign, mode)
            else:
                cls._create_keyframe_orbit(cam_obj, center, r, z, angle0, start_frame, end_frame, sign, mode)

        bpy.context.scene.camera = cam_obj
        print(f"✅ Camera '{cam_obj.name}' updated successfully.")
        return cam_obj
    # [[----- INICIO DEL CÓDIGO A AÑADIR -----]]
    # [[----- START OF CODE TO ADD -----]]
    @classmethod
    def clear_camera_animation(cls, cam_obj):
        """
        Limpia de forma robusta la animación y las restricciones de una cámara,
        incluyendo su trayectoria y objetivo asociados.
        """
        import bpy
        if not cam_obj:
            return

        try:
            # 1. Clear animation data (keyframes)
            if getattr(cam_obj, "animation_data", None):
                cam_obj.animation_data_clear()

            # 2. Clear all constraints
            for c in list(getattr(cam_obj, "constraints", [])):
                try:
                    cam_obj.constraints.remove(c)
                except Exception:
                    pass

            # 3. Clear auxiliary objects (path and target)
            path_name = f"4D_OrbitPath_for_{cam_obj.name}"
            path_obj = bpy.data.objects.get(path_name)
            if path_obj:
                bpy.data.objects.remove(path_obj, do_unlink=True)

            target_name = f"4D_OrbitTarget_for_{cam_obj.name}"
            tgt_obj = bpy.data.objects.get(target_name)
            if tgt_obj:
                bpy.data.objects.remove(tgt_obj, do_unlink=True)

            print(f"✅ Animation cleared for camera '{cam_obj.name}'")
        except Exception as e:
            print(f"⚠️ Error clearing camera animation: {e}")

    @classmethod
    def _create_follow_path_orbit(cls, cam_obj, center, radius, z, angle0, start_frame, end_frame, sign, mode):
        import bpy, math, mathutils
        anim = cls.get_animation_props()
        camera_props = anim.camera_orbit
        path_object = None

        if camera_props.orbit_path_shape == 'CUSTOM' and camera_props.custom_orbit_path:
            path_object = camera_props.custom_orbit_path
            path_object.hide_viewport = camera_props.hide_orbit_path
            path_object.hide_render = camera_props.hide_orbit_path
            print(f"🛤️ Using custom path: '{path_object.name}'")
        else:
            path_name = f"4D_OrbitPath_for_{cam_obj.name}"
            curve = bpy.data.curves.new(path_name, type='CURVE')
            curve.dimensions = '3D'
            curve.resolution_u = 64
            path_object = bpy.data.objects.new(path_name, curve)
            path_object.hide_viewport = camera_props.hide_orbit_path
            path_object.hide_render = camera_props.hide_orbit_path
            try:
                bpy.context.collection.objects.link(path_object)
            except Exception:
                bpy.context.scene.collection.objects.link(path_object)

            # MEJORA: Perfect circle with only 4 points (mathematical perfection)
            spline = curve.splines.new('BEZIER')
            spline.bezier_points.add(3)  # 4 points total (0,1,2,3)
            
            # Calculate perfect circle control points (4-point Bezier circle)
            kappa = 4 * (math.sqrt(2) - 1) / 3  # Magic number for perfect Bezier circle
            
            points = [
                (radius, 0),          # Right
                (0, radius),          # Top  
                (-radius, 0),         # Left
                (0, -radius)          # Bottom
            ]
            
            for i, (x, y) in enumerate(points):
                bp = spline.bezier_points[i]
                bp.co = mathutils.Vector((center.x + x, center.y + y, z))
                bp.handle_left_type = 'ALIGNED'
                bp.handle_right_type = 'ALIGNED'
                
                # Perfect circle handles using kappa constant
                if i == 0:    # Right point
                    bp.handle_left = mathutils.Vector((center.x + x, center.y + y - radius * kappa, z))
                    bp.handle_right = mathutils.Vector((center.x + x, center.y + y + radius * kappa, z))
                elif i == 1:  # Top point  
                    bp.handle_left = mathutils.Vector((center.x + x + radius * kappa, center.y + y, z))
                    bp.handle_right = mathutils.Vector((center.x + x - radius * kappa, center.y + y, z))
                elif i == 2:  # Left point
                    bp.handle_left = mathutils.Vector((center.x + x, center.y + y + radius * kappa, z))
                    bp.handle_right = mathutils.Vector((center.x + x, center.y + y - radius * kappa, z))
                else:         # Bottom point
                    bp.handle_left = mathutils.Vector((center.x + x - radius * kappa, center.y + y, z))
                    bp.handle_right = mathutils.Vector((center.x + x + radius * kappa, center.y + y, z))
                    
            spline.use_cyclic_u = True
            print(f"🛤️ Generated PERFECT 4-point circular path: '{path_object.name}'")

        fcon = cam_obj.constraints.new(type='FOLLOW_PATH')
        fcon.target = path_object
        # RESTAURADO: Settings que funcionaban bien con tracking
        fcon.use_curve_follow = True   # Permite seguir la curva
        fcon.use_fixed_location = True  # Mantiene posición en el path

        def key_offset(offset, frame):
            fcon.offset_factor = offset
            fcon.keyframe_insert("offset_factor", frame=frame)

        # RESTAURADO: Calculate starting offset based on angle0
        angle_normalized = (angle0 % (2 * math.pi)) / (2 * math.pi)  # Convert to 0-1 range
        if sign > 0:  # Counter-clockwise
            s0, s1 = angle_normalized, angle_normalized + 1.0
        else:  # Clockwise  
            s0, s1 = angle_normalized, angle_normalized - 1.0

        if mode == "CIRCLE_360":
            # SIMPLE METHOD: Only 2 keyframes for perfectly smooth rotation
            key_offset(s0, start_frame)
            key_offset(s1, end_frame)
        elif mode == "PINGPONG":
            # SIMPLE PINGPONG: Only 3 keyframes for smooth constant velocity
            mid_frame = start_frame + (end_frame - start_frame) // 2
            
            # Go from start angle to 180° and back - perfectly linear
            key_offset(s0, start_frame)                    # Start position
            key_offset(s0 + (s1 - s0) * 0.5, mid_frame)   # Opposite side (180°)
            key_offset(s0, end_frame)                      # Back to start

        # AGGRESSIVE FORCE: Always LINEAR for 360° (ignore all user settings)
        if cam_obj.animation_data and cam_obj.animation_data.action:
            for fcurve in cam_obj.animation_data.action.fcurves:
                if "offset_factor" in fcurve.data_path:
                    if mode == "CIRCLE_360":
                        # Force LINEAR for all keyframes - no exceptions
                        for kf in fcurve.keyframe_points:
                            kf.interpolation = 'LINEAR'
                            # Also reset handles to avoid any Bezier remnants
                            kf.handle_left_type = 'AUTO'
                            kf.handle_right_type = 'AUTO'
                        fcurve.update()
                        print(f"🔧 FORCED LINEAR interpolation on {len(fcurve.keyframe_points)} keyframes")
                    else:
                        # PINGPONG: Always use LINEAR for consistency and smoothness
                        for kf in fcurve.keyframe_points:
                            kf.interpolation = 'LINEAR'

        # RESTAURADO: Add Track-To constraint for proper camera aiming
        target_name = f"4D_Target_for_{cam_obj.name}"
        target_obj = bpy.data.objects.get(target_name)
        if target_obj:
            tcon = cam_obj.constraints.new(type='TRACK_TO')
            tcon.target = target_obj
            tcon.track_axis = 'TRACK_NEGATIVE_Z'
            tcon.up_axis = 'UP_Y'
            print(f"🎯 Camera tracking target: {target_obj.name}")

        print(f"✅ Follow Path orbit created: {mode} from {start_frame} to {end_frame} with LINEAR interpolation (forced)")

    @classmethod
    def _create_empty_pivot_orbit(cls, cam_obj, center, radius, z, angle0, start_frame, end_frame, sign):
        """OPTIMIZED method for 360° orbit using Empty pivot - maximum smoothness"""
        import bpy, math
        
        # 1. Create Empty pivot at center
        empty_name = f"Camera_Pivot_{cam_obj.name}"
        
        # Remove existing pivot if it exists
        if empty_name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[empty_name], do_unlink=True)
        
        # Create new empty at center
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=center)
        pivot = bpy.context.active_object
        pivot.name = empty_name
        
        # 2. Clear any existing camera constraints to avoid conflicts
        for constraint in list(cam_obj.constraints):
            cam_obj.constraints.remove(constraint)
        
        # 3. Parent camera to empty and position it
        cam_obj.parent = pivot
        cam_obj.parent_type = 'OBJECT'
        cam_obj.location = (radius, 0, z - center.z)  # Relative to pivot
        
        # 4. Set initial rotation for starting angle
        pivot.rotation_euler[2] = angle0
        
        # 5. Animate pivot rotation with only 2 keyframes (PERFECTION!)
        pivot.rotation_euler[2] = angle0
        pivot.keyframe_insert("rotation_euler", index=2, frame=start_frame)
        
        pivot.rotation_euler[2] = angle0 + sign * 2 * math.pi
        pivot.keyframe_insert("rotation_euler", index=2, frame=end_frame)
        
        # 6. FORCE LINEAR interpolation for constant velocity + micro-jitter elimination
        if pivot.animation_data and pivot.animation_data.action:
            for fcurve in pivot.animation_data.action.fcurves:
                if fcurve.data_path == "rotation_euler" and fcurve.array_index == 2:
                    for kf in fcurve.keyframe_points:
                        kf.interpolation = 'LINEAR'
                        kf.handle_left_type = 'AUTO'
                        kf.handle_right_type = 'AUTO'
                    fcurve.update()
                    
                    # MEJORA: Lock other rotation axes to prevent micro-jitter
                    pivot.lock_rotation[0] = True  # Lock X rotation
                    pivot.lock_rotation[1] = True  # Lock Y rotation
                    # Z rotation remains unlocked for animation
                    
                    print(f"🔧 FORCED LINEAR + locked axes for perfect rotation: {len(fcurve.keyframe_points)} keyframes")
                    
        # 7. Add Track-To constraint to camera for proper aim
        tcon = cam_obj.constraints.new(type='TRACK_TO')
        tcon.target = bpy.data.objects.get(f"4D_Target_for_{cam_obj.name}")  # Use existing target
        if tcon.target:
            tcon.track_axis = 'TRACK_NEGATIVE_Z'
            tcon.up_axis = 'UP_Y'
            print(f"🎯 Camera tracking target: {tcon.target.name}")
        
        print(f"✅ OPTIMAL Empty Pivot orbit created: 360° from {start_frame} to {end_frame} with LINEAR interpolation")

    @classmethod
    def _create_keyframe_orbit(cls, cam_obj, center, radius, z, angle0, start_frame, end_frame, sign, mode):
        import math, mathutils
        anim = cls.get_animation_props()
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
                        print(f"🔧 FORCED LINEAR on Empty pivot rotation: {len(fcurve.keyframe_points)} keyframes")
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
                        print(f"🔧 FORCED LINEAR on camera location: {len(fcurve.keyframe_points)} keyframes")
                    else:
                        # PINGPONG: Always use LINEAR for consistency
                        for kp in fcurve.keyframe_points:
                            kp.interpolation = 'LINEAR'

        print(f"✅ Keyframe orbit created: {mode} from {start_frame} to {end_frame} with LINEAR interpolation (forced)")
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
    def get_task_bar_list(cls) -> list[int]:
        """
        Obtiene la lista de IDs de tareas que deben mostrar barra visual.
        Retorna una lista de IDs de tareas.
        """
        props = cls.get_work_schedule_props()
        try:
            task_bars = json.loads(props.task_bars)
            return task_bars if isinstance(task_bars, list) else []
        except Exception:
            return []

    @classmethod
    def add_task_bar(cls, task_id: int) -> None:
        """Agrega una tarea a la lista de barras visuales."""
        props = cls.get_work_schedule_props()
        try:
            task_bars = json.loads(props.task_bars)
        except Exception:
            task_bars = []
        if task_id not in task_bars:
            task_bars.append(task_id)
            props.task_bars = json.dumps(task_bars)
            print(f"✅ Task {task_id} added to visual bars list")

    @classmethod
    def remove_task_bar(cls, task_id: int) -> None:
        """Remueve una tarea de la lista de barras visuales."""
        props = cls.get_work_schedule_props()
        try:
            task_bars = json.loads(props.task_bars)
        except Exception:
            task_bars = []
        if task_id in task_bars:
            task_bars.remove(task_id)
            props.task_bars = json.dumps(task_bars)
            print(f"❌ Task {task_id} removed from visual bars list")

    @classmethod
    def get_animation_bar_tasks(cls) -> list:
        """Obtiene las tareas IFC que tienen barras visuales habilitadas."""
        task_ids = cls.get_task_bar_list()
        tasks = []
        ifc_file = tool.Ifc.get()
        if ifc_file:
            for task_id in task_ids:
                try:
                    task = ifc_file.by_id(task_id)
                    if task and cls.validate_task_object(task, "get_animation_bar_tasks"):
                        tasks.append(task)
                except Exception as e:
                    print(f"⚠️ Error getting task {task_id}: {e}")
        return tasks

    @classmethod
    def refresh_task_bars(cls) -> None:
        """Actualiza la visualización de las barras de tareas en el viewport."""
        tasks = cls.get_animation_bar_tasks()
        if not tasks:
            print("⚠️ No tasks selected for bar visualization")
            if "Bar Visual" in bpy.data.collections:
                collection = bpy.data.collections["Bar Visual"]
                for obj in list(collection.objects):
                    bpy.data.objects.remove(obj)
            return
        cls.create_bars(tasks)
        print(f"✅ Created bars for {len(tasks)} tasks")


    @classmethod
    def clear_task_bars(cls) -> None:
        """
        Limpia y elimina todas las barras de tareas 3D y resetea el estado en la UI.
        """
        import bpy

        # 1. Limpiar la lista de tareas marcadas para tener barras.
        props = cls.get_work_schedule_props()
        props.task_bars = "[]"  # Resetear a una lista JSON vacía.

        # 2. Desmarcar todos los checkboxes en la interfaz de usuario.
        tprops = cls.get_task_tree_props()
        for task in getattr(tprops, "tasks", []):
            if getattr(task, "has_bar_visual", False):
                task.has_bar_visual = False

        # 3. Eliminar la colección de objetos 3D de las barras.
        collection_name = "Bar Visual"
        if collection_name in bpy.data.collections:
            collection = bpy.data.collections[collection_name]
            # Eliminar todos los objetos dentro de la colección.
            for obj in list(collection.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            # Eliminar la colección vacía.
            bpy.data.collections.remove(collection)
            print("✅ Barras de tareas y su colección eliminadas.")


    @classmethod
    def get_work_schedule_props(cls) -> BIMWorkScheduleProperties:
        assert (scene := bpy.context.scene)
        return scene.BIMWorkScheduleProperties  # pyright: ignore[reportAttributeAccessIssue]
    @classmethod
    def get_task_tree_props(cls) -> BIMTaskTreeProperties:
        assert (scene := bpy.context.scene)
        return scene.BIMTaskTreeProperties  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def get_animation_props(cls) -> BIMAnimationProperties:
        assert (scene := bpy.context.scene)
        return scene.BIMAnimationProperties  # pyright: ignore[reportAttributeAccessIssue]



    @classmethod
    def get_status_props(cls) -> BIMStatusProperties:
        assert (scene := bpy.context.scene)
        return scene.BIMStatusProperties  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def set_visibility_by_status(cls, visible_statuses: set[str]) -> None:
        """
        Hides or shows objects based on their IFC status property.
        """
        import bpy
        import ifcopenshell.util.element
        import bonsai.tool as tool

        ifc_file = tool.Ifc.get()
        if not ifc_file:
            return

        all_products = ifc_file.by_type("IfcProduct")
        for product in all_products:
            obj = tool.Ifc.get_object(product)
            if not obj:
                continue

            current_status = "No Status"
            psets = ifcopenshell.util.element.get_psets(product)
            for pset_name, pset_props in psets.items():
                if "Status" in pset_props:
                    if pset_name.startswith("Pset_") and pset_name.endswith("Common"):
                        current_status = pset_props["Status"]
                        break
                    elif pset_name == "EPset_Status":
                        current_status = pset_props["Status"]
                        break
            
            obj.hide_viewport = current_status not in visible_statuses
            obj.hide_render = current_status not in visible_statuses


    @classmethod
    def get_work_plan_props(cls) -> BIMWorkPlanProperties:
        assert (scene := bpy.context.scene)
        return scene.BIMWorkPlanProperties  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def get_work_calendar_props(cls) -> BIMWorkCalendarProperties:
        assert (scene := bpy.context.scene)
        return scene.BIMWorkCalendarProperties  # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def get_work_plan_attributes(cls) -> dict[str, Any]:
        import bonsai.bim.module.sequence.helper as helper

        def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
            if "Date" in prop.name or "Time" in prop.name:
                if prop.is_null:
                    attributes[prop.name] = None
                    return True
                attributes[prop.name] = helper.parse_datetime(prop.string_value)
                return True
            elif prop.name == "Duration" or prop.name == "TotalFloat":
                if prop.is_null:
                    attributes[prop.name] = None
                    return True
                attributes[prop.name] = helper.parse_duration(prop.string_value)
                return True
            return False

        props = cls.get_work_plan_props()
        return bonsai.bim.helper.export_attributes(props.work_plan_attributes, callback)

    @classmethod
    def load_work_plan_attributes(cls, work_plan: ifcopenshell.entity_instance) -> None:
        def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
            if name in ["CreationDate", "StartTime", "FinishTime"]:
                assert prop
                prop.string_value = "" if prop.is_null else data[name]
                return True

        props = cls.get_work_plan_props()
        props.work_plan_attributes.clear()
        bonsai.bim.helper.import_attributes(work_plan, props.work_plan_attributes, callback)

    @classmethod
    def enable_editing_work_plan(cls, work_plan: Union[ifcopenshell.entity_instance, None]) -> None:
        if work_plan:
            props = cls.get_work_plan_props()
            props.active_work_plan_id = work_plan.id()
            props.editing_type = "ATTRIBUTES"

    @classmethod
    def disable_editing_work_plan(cls) -> None:
        props = cls.get_work_plan_props()
        props.active_work_plan_id = 0

    @classmethod
    def enable_editing_work_plan_schedules(cls, work_plan: Union[ifcopenshell.entity_instance, None]) -> None:
        if work_plan:
            props = cls.get_work_plan_props()
            props.active_work_plan_id = work_plan.id()
            props.editing_type = "SCHEDULES"

    @classmethod
    def get_work_schedule_attributes(cls) -> dict[str, Any]:
        import bonsai.bim.module.sequence.helper as helper

        def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
            if "Date" in prop.name or "Time" in prop.name:
                if prop.is_null:
                    attributes[prop.name] = None
                    return True
                attributes[prop.name] = helper.parse_datetime(prop.string_value)
                return True
            elif prop.special_type == "DURATION":
                return cls.export_duration_prop(prop, attributes)
            return False

        props = cls.get_work_schedule_props()
        return bonsai.bim.helper.export_attributes(props.work_schedule_attributes, callback)

    @classmethod
    def load_work_schedule_attributes(cls, work_schedule: ifcopenshell.entity_instance) -> None:
        schema = tool.Ifc.schema()
        entity = schema.declaration_by_name("IfcWorkSchedule").as_entity()
        assert entity

        def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
            if name in ["CreationDate", "StartTime", "FinishTime"]:
                assert prop
                prop.string_value = "" if prop.is_null else data[name]
                return True
            else:
                attr = entity.attribute_by_index(entity.attribute_index(name))
                if not attr.type_of_attribute()._is("IfcDuration"):
                    return
                assert prop
                cls.add_duration_prop(prop, data[name])

        props = cls.get_work_schedule_props()
        props.work_schedule_attributes.clear()
        bonsai.bim.helper.import_attributes(work_schedule, props.work_schedule_attributes, callback)

    @classmethod
    def copy_work_schedule(cls, work_schedule: ifcopenshell.entity_instance) -> None:
        """Creates a deep copy of the given work schedule, including all its tasks and relationships."""
        import ifcopenshell
        import ifcopenshell.api
        import ifcopenshell.util.sequence
        import ifcopenshell.guid
        file = tool.Ifc.get()
        if not work_schedule or not file:
            print("Error: Invalid work schedule or IFC file.")
            return

        # --- PRIMARY METHOD: Use the modern clone API if available ---
        try:
            import ifcopenshell.api.clone
            new_schedule = ifcopenshell.api.run("clone.clone_deep", file, element=work_schedule)
            original_name = getattr(work_schedule, "Name", "Unnamed Schedule")
            new_schedule.Name = f"Copy of {original_name}"
            print(f"Bonsai INFO: Successfully copied schedule using modern clone.clone_deep API.")
            return
        except (ImportError, ModuleNotFoundError) as e:
            print(f"Bonsai WARNING: clone.clone_deep not available ('{e}'). This may be due to an outdated IfcOpenShell version. Falling back to a basic manual copy.")
        except Exception as e:
            print(f"Bonsai WARNING: An unexpected error occurred with clone.clone_deep ('{e}'). Falling back to manual copy.")

        # --- FALLBACK METHOD: Manual deep copy for very old IfcOpenShell versions ---
        def _create_entity_copy(ifc_file, entity: ifcopenshell.entity_instance):
            """Creates a TRUE copy of an IFC entity with a new unique ID."""
            if not entity:
                return None
            try:
                # CRÍTICO: Usar create_entity para crear una nueva entidad con nuevo ID
                # NO usar .add() que solo reutiliza la entidad existente
                entity_info = entity.get_info()
                
                # Remover campos que deben ser únicos para la nueva entidad
                if 'id' in entity_info:
                    del entity_info['id']
                if 'GlobalId' in entity_info:
                    entity_info['GlobalId'] = ifcopenshell.guid.new()
                
                # Crear nueva entidad con los datos copiados
                new_entity = ifc_file.create_entity(entity.is_a(), **entity_info)
                print(f"✅ Tarea copiada: '{entity.Name}' - Original ID: {entity.id()} → Nuevo ID: {new_entity.id()}")
                return new_entity
                
            except Exception as e:
                print(f"❌ Error copiando entidad {entity} - {e}")
                # Fallback: intentar con método API si está disponible
                try:
                    if entity.is_a("IfcTask"):
                        # Para tareas, usar la API específica si está disponible
                        work_schedule = None  # Se asignará después
                        new_task = ifcopenshell.api.run("sequence.add_task", ifc_file, parent_task=None, work_schedule=work_schedule)
                        
                        # Copiar atributos importantes
                        if hasattr(entity, 'Name') and entity.Name:
                            new_task.Name = entity.Name
                        if hasattr(entity, 'Description') and entity.Description:
                            new_task.Description = entity.Description
                        if hasattr(entity, 'Identification') and entity.Identification:
                            new_task.Identification = entity.Identification
                        if hasattr(entity, 'PredefinedType') and entity.PredefinedType:
                            new_task.PredefinedType = entity.PredefinedType
                            
                        print(f"✅ Tarea creada con API: '{entity.Name}' - Original ID: {entity.id()} → Nuevo ID: {new_task.id()}")
                        return new_task
                except Exception as api_error:
                    print(f"❌ También falló el método API: {api_error}")
                
                return None

        try:
            old_to_new_tasks = {}  # Map old task IDs to new task entities
            cls.last_duplication_mapping = {}  # Para uso posterior en ColorType

            def _copy_task_recursive(old_task, new_parent):
                # 1. Crear una tarea completamente nueva con ID único
                try:
                    if new_parent.is_a("IfcWorkSchedule"):
                        # Para tareas raíz, usar la API con work_schedule
                        new_task = ifcopenshell.api.run("sequence.add_task", file, 
                                                       work_schedule=new_parent, 
                                                       parent_task=None)
                    else:
                        # Para tareas anidadas, usar la API con parent_task
                        work_schedule = ifcopenshell.util.sequence.get_task_work_schedule(new_parent)
                        new_task = ifcopenshell.api.run("sequence.add_task", file,
                                                       work_schedule=work_schedule,
                                                       parent_task=new_parent)
                    
                    # Copiar todos los atributos importantes
                    if hasattr(old_task, 'Name') and old_task.Name:
                        new_task.Name = old_task.Name
                    if hasattr(old_task, 'Description') and old_task.Description:
                        new_task.Description = old_task.Description
                    if hasattr(old_task, 'Identification') and old_task.Identification:
                        new_task.Identification = old_task.Identification
                    if hasattr(old_task, 'PredefinedType') and old_task.PredefinedType:
                        new_task.PredefinedType = old_task.PredefinedType
                    if hasattr(old_task, 'Priority') and old_task.Priority:
                        new_task.Priority = old_task.Priority
                    if hasattr(old_task, 'Status') and old_task.Status:
                        new_task.Status = old_task.Status
                    if hasattr(old_task, 'WorkMethod') and old_task.WorkMethod:
                        new_task.WorkMethod = old_task.WorkMethod
                    if hasattr(old_task, 'IsMilestone') and old_task.IsMilestone is not None:
                        new_task.IsMilestone = old_task.IsMilestone
                        
                    print(f"✅ NUEVA TAREA CREADA: '{old_task.Name}' - Original ID: {old_task.id()} → Nuevo ID: {new_task.id()}")
                    
                except Exception as api_error:
                    print(f"❌ Error con API, intentando método directo: {api_error}")
                    # Fallback al método de copia de entidad
                    new_task = _create_entity_copy(file, old_task)
                    if not new_task:
                        print(f"❌ FALLO TOTAL: No se pudo copiar tarea {getattr(old_task, 'id', 'N/A')}. Saltando.")
                        return

                # 2. Copiar TaskTime si existe
                if old_task.TaskTime:
                    try:
                        # Crear nuevo TaskTime usando API
                        new_task_time = ifcopenshell.api.run("sequence.add_task_time", file, task=new_task)
                        
                        # Copiar atributos de tiempo
                        old_time = old_task.TaskTime
                        if hasattr(old_time, 'DurationType') and old_time.DurationType:
                            new_task_time.DurationType = old_time.DurationType
                        if hasattr(old_time, 'ScheduleDuration') and old_time.ScheduleDuration:
                            new_task_time.ScheduleDuration = old_time.ScheduleDuration
                        if hasattr(old_time, 'ScheduleStart') and old_time.ScheduleStart:
                            new_task_time.ScheduleStart = old_time.ScheduleStart
                        if hasattr(old_time, 'ScheduleFinish') and old_time.ScheduleFinish:
                            new_task_time.ScheduleFinish = old_time.ScheduleFinish
                        if hasattr(old_time, 'ActualStart') and old_time.ActualStart:
                            new_task_time.ActualStart = old_time.ActualStart
                        if hasattr(old_time, 'ActualFinish') and old_time.ActualFinish:
                            new_task_time.ActualFinish = old_time.ActualFinish
                            
                        print(f"✅ TaskTime copiado para tarea '{new_task.Name}'")
                        
                    except Exception as time_error:
                        print(f"⚠️ Error copiando TaskTime: {time_error}")
                        # Fallback: copiar TaskTime con método directo
                        try:
                            new_task.TaskTime = _create_entity_copy(file, old_task.TaskTime)
                        except:
                            print(f"⚠️ No se pudo copiar TaskTime para '{new_task.Name}'")
                
                old_to_new_tasks[old_task.id()] = new_task
                cls.last_duplication_mapping[old_task.id()] = new_task.id()

                # 3. Las relaciones ya se crearon automáticamente con la API
                # Copiar productos y recursos a la nueva tarea
                for product in ifcopenshell.util.sequence.get_task_outputs(old_task):
                    ifcopenshell.api.run("sequence.assign_product", file, relating_product=product, related_object=new_task)
                for product_input in ifcopenshell.util.sequence.get_task_inputs(old_task):
                    ifcopenshell.api.run("sequence.assign_process", file, relating_process=new_task, related_object=product_input)
                for resource in ifcopenshell.util.sequence.get_task_resources(old_task):
                    ifcopenshell.api.run("sequence.assign_process", file, relating_process=new_task, related_object=resource)
                
                # 4. Recursively copy nested tasks
                for child_task in ifcopenshell.util.sequence.get_nested_tasks(old_task):
                    _copy_task_recursive(child_task, new_task)

            # 1. Create the new, empty work schedule
            new_schedule = ifcopenshell.api.run("sequence.add_work_schedule", file, name=f"Copy of {getattr(work_schedule, 'Name', 'Unnamed')}")

            # 2. Start the recursive copy from the root tasks
            for root_task in ifcopenshell.util.sequence.get_root_tasks(work_schedule):
                _copy_task_recursive(root_task, new_schedule)
                
            # 3. Re-link predecessors and successors
            for old_id, new_task in old_to_new_tasks.items():
                old_task = file.by_id(old_id)
                for rel in getattr(old_task, 'IsSuccessorFrom', []):
                    old_predecessor = rel.RelatingProcess
                    if old_predecessor.id() in old_to_new_tasks:
                        new_predecessor = old_to_new_tasks[old_predecessor.id()]
                        time_lag = _create_entity_copy(file, rel.TimeLag) if getattr(rel, 'TimeLag', None) else None
                        # The 'time_lag' argument is not supported in older ifcopenshell API versions.
                        # We create the relationship first, then assign the time lag manually for compatibility.
                        new_rel = ifcopenshell.api.run(
                            "sequence.assign_sequence",
                            file,
                            relating_process=new_predecessor,
                            related_process=new_task,
                            sequence_type=rel.SequenceType,
                        )
                        if time_lag:
                            new_rel.TimeLag = time_lag
            
            print(f"Bonsai INFO: Successfully copied schedule using manual fallback method.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error during manual schedule copy: {e}")

    @classmethod
    def add_duration_prop(cls, prop: Attribute, duration_value: Union[str, None]) -> None:
        import bonsai.bim.module.sequence.helper as helper

        props = cls.get_work_schedule_props()
        prop.special_type = "DURATION"
        duration_props = props.durations_attributes.add()
        duration_props.name = prop.name
        if duration_value is None:
            return
        for key, value in helper.parse_duration_as_blender_props(duration_value).items():
            setattr(duration_props, key, value)

    @classmethod
    def export_duration_prop(cls, prop: Attribute, out_attributes: dict[str, Any]) -> Literal[True]:
        import bonsai.bim.module.sequence.helper as helper

        props = cls.get_work_schedule_props()
        if prop.is_null:
            out_attributes[prop.name] = None
        else:
            duration_type = out_attributes["DurationType"] if "DurationType" in out_attributes else None
            time_split_iso_duration = helper.blender_props_to_iso_duration(
                props.durations_attributes, duration_type, prop.name
            )
            out_attributes[prop.name] = time_split_iso_duration
        return True

    @classmethod
    def enable_editing_work_schedule(cls, work_schedule: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_work_schedule_id = work_schedule.id()
        props.editing_type = "WORK_SCHEDULE"

    @classmethod
    def disable_editing_work_schedule(cls) -> None:
        props = cls.get_work_schedule_props()
        props.active_work_schedule_id = 0

    @classmethod
    def enable_editing_work_schedule_tasks(cls, work_schedule: Union[ifcopenshell.entity_instance, None]) -> None:
        if work_schedule:
            props = cls.get_work_schedule_props()
            props.active_work_schedule_id = work_schedule.id()
            props.editing_type = "TASKS"

    
    
    @classmethod
    def load_task_tree(cls, work_schedule: ifcopenshell.entity_instance) -> None:
        props = cls.get_task_tree_props()

        props.tasks.clear()
        schedule_props = cls.get_work_schedule_props()
        cls.contracted_tasks = json.loads(schedule_props.contracted_tasks)

        # 1. Obtener TODAS las tareas raíz, como antes
        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
        
        # 2. APLICAR FILTRO: Pasar la lista de tareas raíz a nuestra nueva función de filtrado
        filtered_root_tasks = cls.get_filtered_tasks(root_tasks)

        # 3. Ordenar solo las tareas que pasaron el filtro
        related_objects_ids = cls.get_sorted_tasks_ids(filtered_root_tasks)
        
        # 4. Crear los elementos de la UI solo para las tareas filtradas y ordenadas
        for related_object_id in related_objects_ids:
            cls.create_new_task_li(related_object_id, 0)

    @classmethod
    def get_sorted_tasks_ids(cls, tasks: list[ifcopenshell.entity_instance]) -> list[int]:
        props = cls.get_work_schedule_props()

        def get_sort_key(task):
            # Sorting only applies to actual tasks, not the WBS
            # for rel in task.IsNestedBy:
            #     for object in rel.RelatedObjects:
            #         if object.is_a("IfcTask"):
            #             return "0000000000" + (task.Identification or "")
            column_type, name = props.sort_column.split(".")
            if column_type == "IfcTask":
                return task.get_info(task)[name] or ""
            elif column_type == "IfcTaskTime" and task.TaskTime:
                return task.TaskTime.get_info(task)[name] if task.TaskTime.get_info(task)[name] else ""
            return task.Identification or ""

        def natural_sort_key(i, _nsre=re.compile("([0-9]+)")):
            s = sort_keys[i]
            return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]

        if props.sort_column:
            sort_keys = {task.id(): get_sort_key(task) for task in tasks}
            related_object_ids = sorted(sort_keys, key=natural_sort_key)
        else:
            related_object_ids = [task.id() for task in tasks]
        if props.is_sort_reversed:
            related_object_ids.reverse()
        return related_object_ids

    

    @classmethod
    def get_filtered_tasks(cls, tasks: list[ifcopenshell.entity_instance]) -> list[ifcopenshell.entity_instance]:
        """
        Filtra una lista de tareas (y sus hijos) basándose en las reglas activas.
        Si una tarea padre no cumple el filtro, sus hijos tampoco se mostrarán.
        """
        props = cls.get_work_schedule_props()
        try:
            filter_rules = [r for r in getattr(props, "filters").rules if r.is_active]
        except Exception:
            return tasks

        if not filter_rules:
            return tasks

        filter_logic_is_and = getattr(props.filters, "logic", 'AND') == 'AND'
        
        def get_task_value(task, column_identifier):
            """Función auxiliar mejorada para obtener el valor de una columna para una tarea."""
            if not task or not column_identifier:
                return None
            
            column_name = column_identifier.split('||')[0]

            if column_name == "Special.OutputsCount":
                try:
                    # Usa la función de utilidad de ifcopenshell para obtener los outputs
                    return len(ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False))
                except Exception:
                    return 0

            if column_name in ("Special.VarianceStatus", "Special.VarianceDays"):
                ws_props = tool.Sequence.get_work_schedule_props()
                source_a = ws_props.variance_source_a
                source_b = ws_props.variance_source_b

                if source_a == source_b:
                    return None

                finish_attr_a = f"{source_a.capitalize()}Finish"
                finish_attr_b = f"{source_b.capitalize()}Finish"

                date_a = ifcopenshell.util.sequence.derive_date(task, finish_attr_a, is_latest=True)
                date_b = ifcopenshell.util.sequence.derive_date(task, finish_attr_b, is_latest=True)

                if date_a and date_b:
                    delta = date_b.date() - date_a.date()
                    variance_days = delta.days
                    if column_name == "Special.VarianceDays":
                        return variance_days
                    else:  # VarianceStatus
                        if variance_days > 0:
                            return f"Delayed (+{variance_days}d)"
                        elif variance_days < 0:
                            return f"Ahead ({variance_days}d)"
                        else:
                            return "On Time"
                return "N/A"

            try:
                ifc_class, attr_name = column_name.split('.', 1)
                if ifc_class == "IfcTask":
                    return getattr(task, attr_name, None)
                elif ifc_class == "IfcTaskTime":
                    task_time = getattr(task, "TaskTime", None)
                    return getattr(task_time, attr_name, None) if task_time else None
            except Exception:
                return None
            return None

        def task_matches_filters(task):
            """Comprueba si una única tarea cumple con el conjunto de filtros."""
            results = []
            for rule in filter_rules:
                task_value = get_task_value(task, rule.column)
                data_type = getattr(rule, 'data_type', 'string')
                op = rule.operator
                match = False

                if op == 'EMPTY':
                    match = task_value is None or str(task_value).strip() == ""
                elif op == 'NOT_EMPTY':
                    match = task_value is not None and str(task_value).strip() != ""
                else:
                    try:
                        if data_type == 'integer':
                            rule_value = rule.value_integer
                            task_value_num = int(task_value)
                            if op == 'EQUALS': match = task_value_num == rule_value
                            elif op == 'NOT_EQUALS': match = task_value_num != rule_value
                            elif op == 'GREATER': match = task_value_num > rule_value
                            elif op == 'LESS': match = task_value_num < rule_value
                            elif op == 'GTE': match = task_value_num >= rule_value
                            elif op == 'LTE': match = task_value_num <= rule_value
                        elif data_type in ('float', 'real'):
                            rule_value = rule.value_float
                            task_value_num = float(task_value)
                            if op == 'EQUALS': match = task_value_num == rule_value
                            elif op == 'NOT_EQUALS': match = task_value_num != rule_value
                            elif op == 'GREATER': match = task_value_num > rule_value
                            elif op == 'LESS': match = task_value_num < rule_value
                            elif op == 'GTE': match = task_value_num >= rule_value
                            elif op == 'LTE': match = task_value_num <= rule_value
                        elif data_type == 'boolean':
                            rule_value = bool(rule.value_boolean)
                            task_value_bool = bool(task_value)
                            if op == 'EQUALS': match = task_value_bool == rule_value
                            elif op == 'NOT_EQUALS': match = task_value_bool != rule_value
                        elif data_type == 'date':
                            task_date = bonsai.bim.module.sequence.helper.parse_datetime(str(task_value))
                            rule_date = bonsai.bim.module.sequence.helper.parse_datetime(rule.value_string)
                            if task_date and rule_date:
                                if op == 'EQUALS': match = task_date.date() == rule_date.date()
                                elif op == 'NOT_EQUALS': match = task_date.date() != rule_date.date()
                                elif op == 'GREATER': match = task_date > rule_date
                                elif op == 'LESS': match = task_date < rule_date
                                elif op == 'GTE': match = task_date >= rule_date
                                elif op == 'LTE': match = task_date <= rule_date
                        elif data_type == 'variance_status':
                            # Special handling for variance status filtering
                            rule_value = rule.value_variance_status
                            task_value_str = str(task_value) if task_value is not None else ""
                            if op == 'EQUALS': match = rule_value in task_value_str
                            elif op == 'NOT_EQUALS': match = rule_value not in task_value_str
                            elif op == 'CONTAINS': match = rule_value in task_value_str
                            elif op == 'NOT_CONTAINS': match = rule_value not in task_value_str
                        else: # string, enums, etc.
                            rule_value = (rule.value_string or "").lower()
                            task_value_str = (str(task_value) if task_value is not None else "").lower()
                            if op == 'CONTAINS': match = rule_value in task_value_str
                            elif op == 'NOT_CONTAINS': match = rule_value not in task_value_str
                            elif op == 'EQUALS': match = rule_value == task_value_str
                            elif op == 'NOT_EQUALS': match = rule_value != task_value_str
                    except (ValueError, TypeError, AttributeError):
                        match = False
                results.append(match)

            if not results: 
                return True
            return all(results) if filter_logic_is_and else any(results)

        filtered_list = []
        for task in tasks:
            nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
            filtered_children = cls.get_filtered_tasks(nested_tasks) if nested_tasks else []

            if task_matches_filters(task) or len(filtered_children) > 0:
                filtered_list.append(task)
                
        return filtered_list

    @classmethod
    def create_new_task_li(cls, related_object_id: int, level_index: int) -> None:
        task = tool.Ifc.get().by_id(related_object_id)
        props = cls.get_task_tree_props()
        new = props.tasks.add()
        new.ifc_definition_id = related_object_id
        new.is_expanded = related_object_id not in cls.contracted_tasks
        new.level_index = level_index
        if task.IsNestedBy:
            new.has_children = True
            if new.is_expanded:
                for related_object_id in cls.get_sorted_tasks_ids(ifcopenshell.util.sequence.get_nested_tasks(task)):
                    cls.create_new_task_li(related_object_id, level_index + 1)

    # TODO: task argument is never used?
    @classmethod
    def _load_task_date_properties(cls, item, task, date_type_prefix):
        """Helper to load a pair of dates (e.g., ScheduleStart/Finish) for a task item."""
        prop_prefix = date_type_prefix.lower()
        start_attr, finish_attr = f"{date_type_prefix}Start", f"{date_type_prefix}Finish"

        # Map 'schedule' to the old property names for compatibility
        if prop_prefix == "schedule":
            item_start, item_finish = "start", "finish"
        else:
            item_start, item_finish = f"{prop_prefix}_start", f"{prop_prefix}_finish"

        derived_start, derived_finish = f"derived_{item_start}", f"derived_{item_finish}"

        task_time = getattr(task, "TaskTime", None)
        if task_time and (getattr(task_time, start_attr, None) or getattr(task_time, finish_attr, None)):
            start_val = getattr(task_time, start_attr, None)
            finish_val = getattr(task_time, finish_attr, None)
            setattr(item, item_start, ifcopenshell.util.date.canonicalise_time(ifcopenshell.util.date.ifc2datetime(start_val)) if start_val else "-")
            setattr(item, item_finish, ifcopenshell.util.date.canonicalise_time(ifcopenshell.util.date.ifc2datetime(finish_val)) if finish_val else "-")
            setattr(item, derived_start, "")
            setattr(item, derived_finish, "")
        else:
            d_start = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
            d_finish = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
            setattr(item, derived_start, ifcopenshell.util.date.canonicalise_time(d_start) if d_start else "")
            setattr(item, derived_finish, ifcopenshell.util.date.canonicalise_time(d_finish) if d_finish else "")
            setattr(item, item_start, "-")
            setattr(item, item_finish, "-")

    @classmethod
    def load_task_properties(cls, task: Optional[ifcopenshell.entity_instance] = None) -> None:
        props = cls.get_work_schedule_props()
        task_props = cls.get_task_tree_props()
        tasks_with_visual_bar = cls.get_task_bar_list()
        props.is_task_update_enabled = False

        for item in task_props.tasks:
            task = tool.Ifc.get().by_id(item.ifc_definition_id)
            item.name = task.Name or "Unnamed"
            item.identification = task.Identification or "XXX"
            item.has_bar_visual = item.ifc_definition_id in tasks_with_visual_bar
            if props.highlighted_task_id:
                item.is_predecessor = props.highlighted_task_id in [
                    rel.RelatedProcess.id() for rel in task.IsPredecessorTo
                ]
                item.is_successor = props.highlighted_task_id in [
                    rel.RelatingProcess.id() for rel in task.IsSuccessorFrom
                ]
            calendar = ifcopenshell.util.sequence.derive_calendar(task)
            if ifcopenshell.util.sequence.get_calendar(task):
                item.calendar = calendar.Name or "Unnamed" if calendar else ""
            else:
                item.calendar = ""
                item.derived_calendar = calendar.Name or "Unnamed" if calendar else ""

            # Load all date pairs using the helper
            cls._load_task_date_properties(item, task, "Schedule")
            cls._load_task_date_properties(item, task, "Actual")
            cls._load_task_date_properties(item, task, "Early")
            cls._load_task_date_properties(item, task, "Late")

            # Duration logic (remains the same, based on Schedule dates)
            task_time = task.TaskTime
            if task_time and task_time.ScheduleDuration:
                item.duration = str(ifcopenshell.util.date.readable_ifc_duration(task_time.ScheduleDuration))
            else:
                derived_start = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
                derived_finish = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
                if derived_start and derived_finish:
                    derived_duration = ifcopenshell.util.sequence.count_working_days(
                        derived_start, derived_finish, calendar
                    )
                    item.derived_duration = str(ifcopenshell.util.date.readable_ifc_duration(f"P{derived_duration}D"))
                else:
                    item.derived_duration = ""
                item.duration = "-"

        # After processing all tasks, refresh the Outputs count so UI stays accurate.
        try:
            cls.refresh_task_output_counts()
        except Exception:
            # Be defensive; never break UI loading if counting fails.
            pass

        props.is_task_update_enabled = True

    @classmethod
    def refresh_task_output_counts(cls) -> None:
        """
        Recalcula y guarda (si existe) el conteo de Outputs por tarea en el árbol actual.
        Es seguro: si los atributos/propiedades no existen, simplemente no hace nada.
        """
        try:
            tprops = cls.get_task_tree_props()
        except Exception:
            return
        try:
            from bonsai import tool as _tool
            import ifcopenshell  # type: ignore
        except Exception:
            # Si los módulos no están disponibles en este contexto, salimos silenciosamente.
            return
        for item in getattr(tprops, "tasks", []):
            try:
                task = _tool.Ifc.get().by_id(item.ifc_definition_id)
                count = len(ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)) if task else 0
                if hasattr(item, "outputs_count"):
                    # Algunas builds definen este atributo en el item del árbol
                    setattr(item, "outputs_count", count)
                # En otros casos el recuento se utiliza de forma dinámica (p.ej. en columnas),
                # por lo que no es necesario almacenar nada; el cálculo anterior actúa como verificación.
            except Exception:
                # Nunca interrumpir la UI por errores de tareas individuales.
                continue


    @classmethod
    def get_active_work_schedule(cls) -> Union[ifcopenshell.entity_instance, None]:
        props = cls.get_work_schedule_props()
        if not props.active_work_schedule_id:
            return None
        return tool.Ifc.get().by_id(props.active_work_schedule_id)

    @classmethod
    def expand_task(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        contracted_tasks = json.loads(props.contracted_tasks)
        contracted_tasks.remove(task.id())
        props.contracted_tasks = json.dumps(contracted_tasks)

    @classmethod
    def expand_all_tasks(cls) -> None:
        props = cls.get_work_schedule_props()
        props.contracted_tasks = json.dumps([])

    @classmethod
    def contract_all_tasks(cls) -> None:
        props = cls.get_work_schedule_props()
        tprops = cls.get_task_tree_props()
        contracted_tasks = json.loads(props.contracted_tasks)
        for task_item in tprops.tasks:
            if task_item.is_expanded:
                contracted_tasks.append(task_item.ifc_definition_id)
        props.contracted_tasks = json.dumps(contracted_tasks)

    @classmethod
    def contract_task(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        contracted_tasks = json.loads(props.contracted_tasks)
        contracted_tasks.append(task.id())
        props.contracted_tasks = json.dumps(contracted_tasks)

    @classmethod
    def disable_work_schedule(cls) -> None:
        props = cls.get_work_schedule_props()
        props.active_work_schedule_id = 0

    @classmethod
    def disable_selecting_deleted_task(cls) -> None:
        props = cls.get_work_schedule_props()
        if props.active_task_id not in [
            task.ifc_definition_id for task in cls.get_task_tree_props().tasks
        ]:  # Task was deleted
            props.active_task_id = 0
            props.active_task_time_id = 0

    @classmethod
    def get_checked_tasks(cls) -> list[ifcopenshell.entity_instance]:
        return [
            tool.Ifc.get().by_id(task.ifc_definition_id) for task in cls.get_task_tree_props().tasks if task.is_selected
        ] or []

    @classmethod
    def get_task_attribute_value(cls, attribute_name: str) -> Any:
        props = cls.get_work_schedule_props()
        return props.task_attributes[attribute_name].get_value()

    @classmethod
    def get_active_task(cls) -> ifcopenshell.entity_instance:
        props = cls.get_work_schedule_props()
        return tool.Ifc.get().by_id(props.active_task_id)

    @classmethod
    def get_active_work_time(cls) -> ifcopenshell.entity_instance:
        props = cls.get_work_calendar_props()
        return tool.Ifc.get().by_id(props.active_work_time_id)

    @classmethod
    def get_task_time(cls, task: ifcopenshell.entity_instance) -> Union[ifcopenshell.entity_instance, None]:
        return task.TaskTime or None

    @classmethod
    def load_task_attributes(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.task_attributes.clear()
        bonsai.bim.helper.import_attributes(task, props.task_attributes)

    @classmethod
    def enable_editing_task_attributes(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_task_id = task.id()
        props.editing_task_type = "ATTRIBUTES"

    @classmethod
    def get_task_attributes(cls) -> dict[str, Any]:
        props = cls.get_work_schedule_props()
        return bonsai.bim.helper.export_attributes(props.task_attributes)

    @classmethod
    def load_task_time_attributes(cls, task_time: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        schema = tool.Ifc.schema()
        entity = schema.declaration_by_name("IfcTaskTime").as_entity()
        assert entity

        def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> Union[bool, None]:
            attr = entity.attribute_by_index(entity.attribute_index(name))
            if attr.type_of_attribute()._is("IfcDuration"):
                assert prop
                cls.add_duration_prop(prop, data[name])
            if isinstance(data[name], datetime):
                assert prop
                prop.string_value = "" if prop.is_null else data[name].isoformat()
                return True

        props.task_time_attributes.clear()
        props.durations_attributes.clear()
        bonsai.bim.helper.import_attributes(task_time, props.task_time_attributes, callback)

    @classmethod
    def enable_editing_task_time(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_task_id = task.id()
        props.active_task_time_id = task.TaskTime.id()
        props.editing_task_type = "TASKTIME"

    @classmethod
    def disable_editing_task(cls) -> None:
        props = cls.get_work_schedule_props()
        props.active_task_id = 0
        props.active_task_time_id = 0
        props.editing_task_type = ""

    @classmethod
    def get_task_time_attributes(cls) -> dict[str, Any]:
        import bonsai.bim.module.sequence.helper as helper

        props = cls.get_work_schedule_props()

        def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
            if "Start" in prop.name or "Finish" in prop.name or prop.name == "StatusTime":
                if prop.is_null:
                    attributes[prop.name] = None
                    return True
                attributes[prop.name] = helper.parse_datetime(prop.string_value)
                return True
            elif prop.special_type == "DURATION":
                return cls.export_duration_prop(prop, attributes)
            return False

        return bonsai.bim.helper.export_attributes(props.task_time_attributes, callback)

    @classmethod
    def load_task_resources(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        rprops = tool.Resource.get_resource_props()
        props.task_resources.clear()
        rprops.is_resource_update_enabled = False
        for resource in cls.get_task_resources(task) or []:
            new = props.task_resources.add()
            new.ifc_definition_id = resource.id()
            new.name = resource.Name or "Unnamed"
            new.schedule_usage = resource.Usage.ScheduleUsage or 0 if resource.Usage else 0
        rprops.is_resource_update_enabled = True

    @classmethod
    def get_task_inputs(cls, task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
        props = cls.get_work_schedule_props()
        is_deep = props.show_nested_inputs
        return ifcopenshell.util.sequence.get_task_inputs(task, is_deep)

    @classmethod
    def get_task_outputs(cls, task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
        props = cls.get_work_schedule_props()
        is_deep = props.show_nested_outputs
        return ifcopenshell.util.sequence.get_task_outputs(task, is_deep)

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
    def get_task_resources(
        cls, task: Union[ifcopenshell.entity_instance, None]
    ) -> Union[list[ifcopenshell.entity_instance], None]:
        if not task:
            return
        props = cls.get_work_schedule_props()
        is_deep = props.show_nested_resources
        return ifcopenshell.util.sequence.get_task_resources(task, is_deep)

    @classmethod
    def load_task_inputs(cls, inputs: list[ifcopenshell.entity_instance]) -> None:
        props = cls.get_work_schedule_props()
        props.task_inputs.clear()
        for input in inputs:
            new = props.task_inputs.add()
            new.ifc_definition_id = input.id()
            new.name = input.Name or "Unnamed"

    @classmethod
    def load_task_outputs(cls, outputs: list[ifcopenshell.entity_instance]) -> None:
        props = cls.get_work_schedule_props()
        props.task_outputs.clear()
        if outputs:
            for output in outputs:
                new = props.task_outputs.add()
                new.ifc_definition_id = output.id()
                new.name = output.Name or "Unnamed"

    @classmethod
    def get_highlighted_task(cls) -> Union[ifcopenshell.entity_instance, None]:
        tasks = cls.get_task_tree_props().tasks
        props = cls.get_work_schedule_props()
        if len(tasks) and len(tasks) > props.active_task_index:
            return tool.Ifc.get().by_id(tasks[props.active_task_index].ifc_definition_id)

    @classmethod
    def get_direct_nested_tasks(cls, task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
        return ifcopenshell.util.sequence.get_nested_tasks(task)

    @classmethod
    def get_direct_task_outputs(cls, task: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
        return ifcopenshell.util.sequence.get_direct_task_outputs(task)

    @classmethod
    def enable_editing_work_calendar_times(cls, work_calendar: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_calendar_props()
        props.active_work_calendar_id = work_calendar.id()
        props.editing_type = "WORKTIMES"

    @classmethod
    def load_work_calendar_attributes(cls, work_calendar: ifcopenshell.entity_instance) -> dict[str, Any]:
        props = cls.get_work_calendar_props()
        props.work_calendar_attributes.clear()
        return bonsai.bim.helper.import_attributes(work_calendar, props.work_calendar_attributes)

    @classmethod
    def enable_editing_work_calendar(cls, work_calendar: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_calendar_props()
        props.active_work_calendar_id = work_calendar.id()
        props.editing_type = "ATTRIBUTES"

    @classmethod
    def disable_editing_work_calendar(cls) -> None:
        props = cls.get_work_calendar_props()
        props.active_work_calendar_id = 0

    @classmethod
    def get_work_calendar_attributes(cls) -> dict[str, Any]:
        props = cls.get_work_calendar_props()
        return bonsai.bim.helper.export_attributes(props.work_calendar_attributes)

    @classmethod
    def load_work_time_attributes(cls, work_time: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_calendar_props()
        props.work_time_attributes.clear()

        bonsai.bim.helper.import_attributes(work_time, props.work_time_attributes)

    @classmethod
    def enable_editing_work_time(cls, work_time: ifcopenshell.entity_instance) -> None:
        def initialise_recurrence_components(props):
            if len(props.day_components) == 0:
                for i in range(0, 31):
                    new = props.day_components.add()
                    new.name = str(i + 1)
            if len(props.weekday_components) == 0:
                for d in ["M", "T", "W", "T", "F", "S", "S"]:
                    new = props.weekday_components.add()
                    new.name = d
            if len(props.month_components) == 0:
                for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]:
                    new = props.month_components.add()
                    new.name = m

        def load_recurrence_pattern_data(work_time, props):
            props.position = 0
            props.interval = 0
            props.occurrences = 0
            props.start_time = ""
            props.end_time = ""
            for component in props.day_components:
                component.is_specified = False
            for component in props.weekday_components:
                component.is_specified = False
            for component in props.month_components:
                component.is_specified = False
            if not work_time.RecurrencePattern:
                return
            recurrence_pattern = work_time.RecurrencePattern
            for attribute in ["Position", "Interval", "Occurrences"]:
                if getattr(recurrence_pattern, attribute):
                    setattr(props, attribute.lower(), getattr(recurrence_pattern, attribute))
            for component in recurrence_pattern.DayComponent or []:
                props.day_components[component - 1].is_specified = True
            for component in recurrence_pattern.WeekdayComponent or []:
                props.weekday_components[component - 1].is_specified = True
            for component in recurrence_pattern.MonthComponent or []:
                props.month_components[component - 1].is_specified = True

        props = cls.get_work_calendar_props()
        initialise_recurrence_components(props)
        load_recurrence_pattern_data(work_time, props)
        props.active_work_time_id = work_time.id()
        props.editing_type = "WORKTIMES"

    @classmethod
    def get_work_time_attributes(cls) -> dict[str, Any]:
        import bonsai.bim.module.sequence.helper as helper

        def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
            if "Start" in prop.name or "Finish" in prop.name:
                if prop.is_null:
                    attributes[prop.name] = None
                    return True
                attributes[prop.name] = helper.parse_datetime(prop.string_value)
                return True
            return False

        props = cls.get_work_calendar_props()
        return bonsai.bim.helper.export_attributes(props.work_time_attributes, callback)

    @classmethod
    def get_recurrence_pattern_attributes(cls, recurrence_pattern):
        props = cls.get_work_calendar_props()
        attributes = {
            "Interval": props.interval if props.interval > 0 else None,
            "Occurrences": props.occurrences if props.occurrences > 0 else None,
        }
        applicable_data = {
            "DAILY": ["Interval", "Occurrences"],
            "WEEKLY": ["WeekdayComponent", "Interval", "Occurrences"],
            "MONTHLY_BY_DAY_OF_MONTH": ["DayComponent", "Interval", "Occurrences"],
            "MONTHLY_BY_POSITION": ["WeekdayComponent", "Position", "Interval", "Occurrences"],
            "BY_DAY_COUNT": ["Interval", "Occurrences"],
            "BY_WEEKDAY_COUNT": ["WeekdayComponent", "Interval", "Occurrences"],
            "YEARLY_BY_DAY_OF_MONTH": ["DayComponent", "MonthComponent", "Interval", "Occurrences"],
            "YEARLY_BY_POSITION": ["WeekdayComponent", "MonthComponent", "Position", "Interval", "Occurrences"],
        }
        if "Position" in applicable_data[recurrence_pattern.RecurrenceType]:
            attributes["Position"] = props.position if props.position != 0 else None
        if "DayComponent" in applicable_data[recurrence_pattern.RecurrenceType]:
            attributes["DayComponent"] = [i + 1 for i, c in enumerate(props.day_components) if c.is_specified]
        if "WeekdayComponent" in applicable_data[recurrence_pattern.RecurrenceType]:
            attributes["WeekdayComponent"] = [i + 1 for i, c in enumerate(props.weekday_components) if c.is_specified]
        if "MonthComponent" in applicable_data[recurrence_pattern.RecurrenceType]:
            attributes["MonthComponent"] = [i + 1 for i, c in enumerate(props.month_components) if c.is_specified]
        return attributes

    @classmethod
    def disable_editing_work_time(cls) -> None:
        props = cls.get_work_calendar_props()
        props.active_work_time_id = 0

    @classmethod
    def get_recurrence_pattern_times(cls) -> Union[tuple[datetime, datetime], None]:
        props = cls.get_work_calendar_props()
        try:
            start_time = parser.parse(props.start_time)
            end_time = parser.parse(props.end_time)
            return start_time, end_time
        except:
            return  # improve UI / refactor to add user hints

    @classmethod
    def reset_time_period(cls) -> None:
        props = cls.get_work_calendar_props()
        props.start_time = ""
        props.end_time = ""

    @classmethod
    def enable_editing_task_calendar(cls, task: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_task_id = task.id()
        props.editing_task_type = "CALENDAR"

    @classmethod
    def enable_editing_task_sequence(cls) -> None:
        props = cls.get_work_schedule_props()
        props.editing_task_type = "SEQUENCE"

    @classmethod
    def disable_editing_task_time(cls) -> None:
        props = cls.get_work_schedule_props()
        props.active_task_id = 0
        props.active_task_time_id = 0

    @classmethod
    def load_rel_sequence_attributes(cls, rel_sequence: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.sequence_attributes.clear()
        bonsai.bim.helper.import_attributes(rel_sequence, props.sequence_attributes)

    @classmethod
    def enable_editing_rel_sequence_attributes(cls, rel_sequence: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_sequence_id = rel_sequence.id()
        props.editing_sequence_type = "ATTRIBUTES"

    @classmethod
    def load_lag_time_attributes(cls, lag_time: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()

        def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
            if name == "LagValue":
                prop = props.lag_time_attributes.add()
                prop.name = name
                prop.is_null = data[name] is None
                prop.is_optional = False
                prop.data_type = "string"
                prop.string_value = (
                    "" if prop.is_null else ifcopenshell.util.date.datetime2ifc(data[name].wrappedValue, "IfcDuration")
                )
                return True

        props.lag_time_attributes.clear()
        bonsai.bim.helper.import_attributes(lag_time, props.lag_time_attributes, callback)

    @classmethod
    def enable_editing_sequence_lag_time(cls, rel_sequence: ifcopenshell.entity_instance) -> None:
        props = cls.get_work_schedule_props()
        props.active_sequence_id = rel_sequence.id()
        props.editing_sequence_type = "LAG_TIME"

    @classmethod
    def get_rel_sequence_attributes(cls) -> dict[str, Any]:
        props = cls.get_work_schedule_props()
        return bonsai.bim.helper.export_attributes(props.sequence_attributes)

    @classmethod
    def disable_editing_rel_sequence(cls) -> None:
        props = cls.get_work_schedule_props()
        props.active_sequence_id = 0

    @classmethod
    def get_lag_time_attributes(cls) -> dict[str, Any]:
        props = cls.get_work_schedule_props()
        return bonsai.bim.helper.export_attributes(props.lag_time_attributes)

    @classmethod
    def select_products(cls, products: Iterable[ifcopenshell.entity_instance]) -> None:
        [obj.select_set(False) for obj in bpy.context.selected_objects]
        for product in products:
            obj = tool.Ifc.get_object(product)
            obj.select_set(True) if obj else None

    @classmethod
    def add_task_column(cls, column_type: str, name: str, data_type: str) -> None:
        props = cls.get_work_schedule_props()
        new = props.columns.add()
        new.name = f"{column_type}.{name}"
        new.data_type = data_type

    @classmethod
    def setup_default_task_columns(cls) -> None:
        props = cls.get_work_schedule_props()
        props.columns.clear()
        default_columns = ["ScheduleStart", "ScheduleFinish", "ScheduleDuration"]
        for item in default_columns:
            new = props.columns.add()
            new.name = f"IfcTaskTime.{item}"
            new.data_type = "string"

    @classmethod
    def remove_task_column(cls, name: str) -> None:
        props = cls.get_work_schedule_props()
        props.columns.remove(props.columns.find(name))
        if props.sort_column == name:
            props.sort_column = ""

    @classmethod
    def set_task_sort_column(cls, column: str) -> None:
        props = cls.get_work_schedule_props()
        props.sort_column = column

    @classmethod
    def find_related_input_tasks(cls, product):
        related_tasks = []
        for assignment in product.HasAssignments:
            if assignment.is_a("IfcRelAssignsToProcess") and assignment.RelatingProcess.is_a("IfcTask"):
                related_tasks.append(assignment.RelatingProcess)
        return related_tasks

    @classmethod
    def find_related_output_tasks(cls, product):
        related_tasks = []
        for reference in product.ReferencedBy:
            if reference.is_a("IfcRelAssignsToProduct") and reference.RelatedObjects[0].is_a("IfcTask"):
                related_tasks.append(reference.RelatedObjects[0])
        return related_tasks

    @classmethod
    def get_work_schedule(cls, task: ifcopenshell.entity_instance) -> Union[ifcopenshell.entity_instance, None]:
        for rel in task.HasAssignments or []:
            if rel.is_a("IfcRelAssignsToControl") and rel.RelatingControl.is_a("IfcWorkSchedule"):
                return rel.RelatingControl
        for rel in task.Nests or []:
            return cls.get_work_schedule(rel.RelatingObject)

    @classmethod
    def is_work_schedule_active(cls, work_schedule):
        props = cls.get_work_schedule_props()
        return True if work_schedule.id() == props.active_work_schedule_id else False

    @classmethod
    def go_to_task(cls, task):
        props = cls.get_work_schedule_props()

        def get_ancestor_ids(task):
            ids = []
            for rel in task.Nests or []:
                ids.append(rel.RelatingObject.id())
                ids.extend(get_ancestor_ids(rel.RelatingObject))
            return ids

        contracted_tasks = json.loads(props.contracted_tasks)
        for ancestor_id in get_ancestor_ids(task):
            if ancestor_id in contracted_tasks:
                contracted_tasks.remove(ancestor_id)
        props.contracted_tasks = json.dumps(contracted_tasks)

        work_schedule = cls.get_active_work_schedule()
        cls.load_task_tree(work_schedule)
        cls.load_task_properties()

        task_props = cls.get_task_tree_props()
        expanded_tasks = [item.ifc_definition_id for item in task_props.tasks]
        props.active_task_index = expanded_tasks.index(task.id()) or 0

    # TODO: proper typing
    @classmethod
    def guess_date_range(cls, work_schedule: ifcopenshell.entity_instance) -> tuple[Any, Any]:
        """
        Guesses the date range for a work schedule, respecting the date source type
        (Schedule, Actual, etc.) set in the UI. It now calculates the range based
        on ALL tasks in the schedule, ignoring any UI filters.
        """
        if not work_schedule:
            return None, None

        # --- START OF CORRECTION ---
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
        # --- END OF CORRECTION ---

        if not all_starts or not all_finishes:
            print(f"❌ GUESS_DATE_RANGE: No valid dates found for {date_source}")
            return None, None

        result_start = min(all_starts)
        result_finish = max(all_finishes)
        print(f"✅ GUESS_DATE_RANGE: Result for {date_source}: {result_start.strftime('%Y-%m-%d')} to {result_finish.strftime('%Y-%m-%d')}")
        
        return result_start, result_finish
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
    def create_bars(cls, tasks):
        full_bar_thickness = 0.2
        size = 1.0
        vertical_spacing = 3.5
        vertical_increment = 0
        size_to_duration_ratio = 1 / 30
        margin = 0.2

        # VALIDACIÓN: Filtrar tareas inválidas antes de cualquier uso
        if tasks:
            _valid = []
            for _t in tasks:
                if cls.validate_task_object(_t, "create_bars"):
                    _valid.append(_t)
                else:
                    print(f"⚠️ Skipping invalid task in create_bars: {_t}")
            if not _valid:
                print("⚠️ Warning: No valid tasks found for bar creation")
                return
            tasks = _valid
        else:
            print("⚠️ Warning: No tasks provided to create_bars")
            return


        def process_task_data(task, settings):
            # VALIDACIÓN CRÍTICA: verificar tarea válida
            if not cls.validate_task_object(task, "process_task_data"):
                return None

            try:
                task_start_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
                finish_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
            except Exception as e:
                print(f"⚠️ Error deriving dates for task {getattr(task, 'Name', 'Unknown')}: {e}")
                return None

            if not (task_start_date and finish_date):
                print(f"⚠️ Warning: Task {getattr(task, 'Name', 'Unknown')} has no valid dates")
                return None

            try:
                # CORRECTION: Use the schedule dates for calculations
                schedule_start = settings["viz_start"]
                schedule_finish = settings["viz_finish"]
                schedule_duration = schedule_finish - schedule_start

                if schedule_duration.total_seconds() <= 0:
                    print(f"⚠️ Invalid schedule duration: {schedule_duration}")
                    return None

                total_frames = settings["end_frame"] - settings["start_frame"]

                # Calculate task position within the full schedule
                task_start_progress = (task_start_date - schedule_start).total_seconds() / schedule_duration.total_seconds()
                task_finish_progress = (finish_date - schedule_start).total_seconds() / schedule_duration.total_seconds()

                # Convert to frames
                task_start_frame = round(settings["start_frame"] + (task_start_progress * total_frames))
                task_finish_frame = round(settings["start_frame"] + (task_finish_progress * total_frames))

                # Validar que los frames estén en rango válido
                task_start_frame = max(settings["start_frame"], min(settings["end_frame"], task_start_frame))
                task_finish_frame = max(settings["start_frame"], min(settings["end_frame"], task_finish_frame))

                return {
                    "name": getattr(task, "Name", "Unnamed"),
                    "start_date": task_start_date,
                    "finish_date": finish_date,
                    "start_frame": task_start_frame,
                    "finish_frame": task_finish_frame,
                }
            except Exception as e:
                print(f"⚠️ Error calculating frames for task {getattr(task, 'Name', 'Unknown')}: {e}")
                return None
        def create_task_bar_data(tasks, vertical_increment, collection):
            # CORRECTION: Use active schedule dates, NOT visualization dates
            schedule_start, schedule_finish = cls.get_schedule_date_range()

            if not (schedule_start and schedule_finish):
                # Fallback: if there are no schedule dates, show message and abort
                print("❌ No se pueden crear Task Bars: fechas del cronograma no disponibles")
                return None

            settings = {
                # CRITICAL CHANGE: Use schedule dates instead of visualization
                "viz_start": schedule_start,
                "viz_finish": schedule_finish,
                "start_frame": bpy.context.scene.frame_start,
                "end_frame": bpy.context.scene.frame_end,
            }

            print(f"🎯 Task Bars usando fechas del cronograma:")
            print(f"   Schedule Start: {schedule_start.strftime('%Y-%m-%d')}")
            print(f"   Schedule Finish: {schedule_finish.strftime('%Y-%m-%d')}")
            print(f"   Timeline: frames {settings['start_frame']} to {settings['end_frame']}")

            material_progress, material_full = get_animation_materials()
            empty = bpy.data.objects.new("collection_origin", None)
            link_collection(empty, collection)

            for task in tasks:
                task_data = process_task_data(task, settings)
                if task_data:
                    position_shift = task_data["start_frame"] * size_to_duration_ratio
                    bar_size = (task_data["finish_frame"] - task_data["start_frame"]) * size_to_duration_ratio

                    anim_props = cls.get_animation_props()
                    color_progress = anim_props.color_progress
                    bar = add_bar(
                        material=material_progress,
                        vertical_increment=vertical_increment,
                        collection=collection,
                        parent=empty,
                        task=task_data,
                        scale=True,
                        color=(color_progress[0], color_progress[1], color_progress[2], 1.0),
                        shift_x=position_shift,
                        name=task_data["name"] + "/Progress Bar",
                    )

                    color_full = anim_props.color_full
                    bar2 = add_bar(
                        material=material_full,
                        vertical_increment=vertical_increment,
                        parent=empty,
                        collection=collection,
                        task=task_data,
                        color=(color_full[0], color_full[1], color_full[2], 1.0),
                        shift_x=position_shift,
                        name=task_data["name"] + "/Full Bar",
                    )
                    bar2.color = (color_full[0], color_full[1], color_full[2], 1.0)

                    bar2.scale = (full_bar_thickness, bar_size, 1)
                    shift_object(bar2, y=((size + full_bar_thickness) / 2))

                    start_text = add_text(
                        task_data["start_date"].strftime("%d/%m/%y"),
                        0,
                        "RIGHT",
                        vertical_increment,
                        parent=empty,
                        collection=collection,
                    )
                    start_text.name = task_data["name"] + "/Start Date"
                    shift_object(start_text, x=position_shift - margin, y=-(size + full_bar_thickness))

                    task_text = add_text(
                        task_data["name"],
                        0,
                        "RIGHT",
                        vertical_increment,
                        parent=empty,
                        collection=collection,
                    )
                    task_text.name = task_data["name"] + "/Task Name"
                    shift_object(task_text, x=position_shift, y=0.2)

                    finish_text = add_text(
                        task_data["finish_date"].strftime("%d/%m/%y"),
                        bar_size,
                        "LEFT",
                        vertical_increment,
                        parent=empty,
                        collection=collection,
                    )
                    finish_text.name = task_data["name"] + "/Finish Date"
                    shift_object(finish_text, x=position_shift + margin, y=-(size + full_bar_thickness))

                vertical_increment += vertical_spacing

            return empty.select_set(True) if empty else None

        def set_material(name, r, g, b):
            material = bpy.data.materials.new(name)
            material.use_nodes = True
            tool.Blender.get_material_node(material, "BSDF_PRINCIPLED").inputs[0].default_value = (r, g, b, 1.0)
            return material

        def get_animation_materials():
            if "color_progress" in bpy.data.materials:
                material_progress = bpy.data.materials["color_progress"]
            else:
                material_progress = set_material("color_progress", 0.0, 1.0, 0.0)
            if "color_full" in bpy.data.materials:
                material_full = bpy.data.materials["color_full"]
            else:
                material_full = set_material("color_full", 1.0, 0.0, 0.0)
            return material_progress, material_full

        def animate_scale(bar, task):
            scale = (1, size_to_duration_ratio, 1)
            bar.scale = scale
            bar.keyframe_insert(data_path="scale", frame=task["start_frame"])
            scale2 = (1, (task["finish_frame"] - task["start_frame"]) * size_to_duration_ratio, 1)
            bar.scale = scale2
            bar.keyframe_insert(data_path="scale", frame=task["finish_frame"])

        def animate_color(bar, task, color):
            bar.keyframe_insert(data_path="color", frame=task["start_frame"])
            bar.color = color
            bar.keyframe_insert(data_path="color", frame=task["start_frame"] + 1)
            bar.color = color

        def place_bar(bar, vertical_increment):
            for vertex in bar.data.vertices:
                vertex.co[1] += 0.5
            bar.rotation_euler[2] = -1.5708
            shift_object(bar, y=-vertical_increment)

        def shift_object(obj, x=0.0, y=0.0, z=0.0):
            vec = mathutils.Vector((x, y, z))
            inv = obj.matrix_world.copy()
            inv.invert()
            vec_rot = vec @ inv
            obj.location = obj.location + vec_rot

        def link_collection(obj, collection):
            if collection:
                collection.objects.link(obj)
                if obj.name in bpy.context.scene.collection.objects.keys():
                    bpy.context.scene.collection.objects.unlink(obj)
            return obj

        def create_plane(material, collection, vertical_increment):
            x = 0.5
            y = 0.5
            vert = [(-x, -y, 0.0), (x, -y, 0.0), (-x, y, 0.0), (x, y, 0.0)]
            fac = [(0, 1, 3, 2)]
            mesh = bpy.data.meshes.new("PL")
            mesh.from_pydata(vert, [], fac)
            obj = bpy.data.objects.new("PL", mesh)
            obj.data.materials.append(material)
            place_bar(obj, vertical_increment)
            link_collection(obj, collection)
            return obj

        def add_text(text, x_position, align, vertical_increment, parent=None, collection=None):
            data = bpy.data.curves.new(type="FONT", name="Timeline")
            data.align_x = align
            data.align_y = "CENTER"

            data.body = text
            obj = bpy.data.objects.new(name="Unnamed", object_data=data)
            link_collection(obj, collection)
            shift_object(obj, x=x_position, y=-(vertical_increment - 1))
            if parent:
                obj.parent = parent
            return obj

        def add_bar(
            material,
            vertical_increment,
            parent=None,
            collection=None,
            task=None,
            color=False,
            scale=False,
            shift_x=None,
            name=None,
        ):
            plane = create_plane(material, collection, vertical_increment)
            if parent:
                plane.parent = parent
            if color:
                animate_color(plane, task, color)
            if scale:
                animate_scale(plane, task)
            if shift_x:
                shift_object(plane, x=shift_x)
            if name:
                plane.name = name
            return plane

        if "Bar Visual" in bpy.data.collections:
            collection = bpy.data.collections["Bar Visual"]
            for obj in collection.objects:
                bpy.data.objects.remove(obj)

        else:
            collection = bpy.data.collections.new("Bar Visual")
            bpy.context.scene.collection.children.link(collection)

        if tasks:
            create_task_bar_data(tasks, vertical_increment, collection)

    @classmethod
    def has_animation_colors(cls):
        return bpy.context.scene.BIMAnimationProperties.task_output_colors

    @classmethod
    def load_default_animation_color_scheme(cls):
        def _to_rgba(col):
            try:
                if isinstance(col, (list, tuple)):
                    if len(col) >= 4:
                        return (float(col[0]), float(col[1]), float(col[2]), float(col[3]))
                    if len(col) == 3:
                        return (float(col[0]), float(col[1]), float(col[2]), 1.0)
            except Exception:
                pass
            return (1.0, 0.0, 0.0, 1.0)

        groups = {
            "CREATION": {"PredefinedType": ["CONSTRUCTION", "INSTALLATION"], "Color": (0.0, 1.0, 0.0)},
            "OPERATION": {"PredefinedType": ["ATTENDANCE", "MAINTENANCE", "OPERATION", "RENOVATION"], "Color": (0.0, 0.0, 1.0)},
            "MOVEMENT_TO": {"PredefinedType": ["LOGISTIC", "MOVE"], "Color": (1.0, 1.0, 0.0)},
            "DESTRUCTION": {"PredefinedType": ["DEMOLITION", "DISMANTLE", "DISPOSAL", "REMOVAL"], "Color": (1.0, 0.0, 0.0)},
            "MOVEMENT_FROM": {"PredefinedType": ["LOGISTIC", "MOVE"], "Color": (1.0, 0.5, 0.0)},
            "USERDEFINED": {"PredefinedType": ["USERDEFINED", "NOTDEFINED"], "Color": (0.2, 0.2, 0.2)},
        }

        props = cls.get_animation_props()
        props.task_output_colors.clear()
        props.task_input_colors.clear()

        for group, data in groups.items():
            for predefined_type in data["PredefinedType"]:
                if group in ["CREATION", "OPERATION", "MOVEMENT_TO"]:
                    item = props.task_output_colors.add()
                elif group in ["MOVEMENT_FROM"]:
                    item = props.task_input_colors.add()
                elif group in ["USERDEFINED", "DESTRUCTION"]:
                    item = props.task_input_colors.add()
                    item2 = props.task_output_colors.add()
                    item2.name = predefined_type
                    item2.color = _to_rgba(data["Color"])
                item.name = predefined_type
                item.color = _to_rgba(data["Color"])

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
        """
        CORRECCIÓN: Procesa el estado de una tarea considerando el rango de visualización.

        Lógica corregida:
        1. Tareas que terminan antes de viz_start: outputs completados, inputs demolidos
        2. Tareas que empiezan después de viz_finish: NO aparecen (se omiten)
        3. Tareas dentro del rango: lógica normal basada en la fecha actual
        """
        # Procesar tareas anidadas recursivamente
        for rel in task.IsNestedBy or []: # type: ignore
            [cls.process_task_status(related_object, date, viz_start, viz_finish, date_source=date_source) for related_object in rel.RelatedObjects]

        # --- CORRECCIÓN: Usar la fuente de fechas seleccionada ---
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

    @classmethod
    def get_task_for_product(cls, product):
        """Obtiene la tarea asociada a un producto IFC."""
        element = tool.Ifc.get_entity(product) if hasattr(product, 'name') else product
        if not element:
            return None

        # Search in outputs
        for rel in element.ReferencedBy or []:
            if rel.is_a("IfcRelAssignsToProduct"):
                for task in rel.RelatedObjects:
                    if task.is_a("IfcTask"):
                        return task

        # Search in inputs
        for rel in element.HasAssignments or []:
            if rel.is_a("IfcRelAssignsToProcess"):
                task = rel.RelatingProcess
                if task.is_a("IfcTask"):
                    return task

        return None
    @classmethod
    def set_object_shading(cls):
            area = tool.Blender.get_view3d_area()
            if area:
                # Use area.spaces.active for stability in newer Blender versions
                space = area.spaces.active
                if space and space.type == 'VIEW_3D':
                    space.shading.color_type = "OBJECT"

    @classmethod
    def get_animation_settings(cls):
        """
        CORRECCIÓN: Asegurar que use las fechas de visualización configuradas,
        no las fechas derivadas de las tareas.
        """
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
    def create_default_ColorType_group(cls):
            """
            Automatically creates the DEFAULT group with profiles for each PredefinedType.
            This group is used when the user has not configured any profiles.
            """
            import json
            scene = bpy.context.scene
            key = "BIM_AnimationColorSchemesSets"
            raw = scene.get(key, "{}")
            try:
                data = json.loads(raw) if isinstance(raw, str) else {}
            except Exception:
                data = {}
            if "DEFAULT" not in data:
                default_ColorTypes = {
                    # Green Group (Construction)
                    "CONSTRUCTION": {"start": [1, 1, 1, 0], "active": [0, 1, 0, 1], "end": [0.3, 1, 0.3, 1]},
                    "INSTALLATION": {"start": [1, 1, 1, 0], "active": [0, 1, 0, 1], "end": [0.3, 0.8, 0.5, 1]},

                    # Red Group (Demolition)
                    "DEMOLITION": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
                    "REMOVAL": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
                    "DISPOSAL": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},
                    "DISMANTLE": {"start": [1, 1, 1, 1], "active": [1, 0, 0, 1], "end": [0, 0, 0, 0], "hide_at_end": True},

                    # Blue Group (Operation / Maintenance)
                    "OPERATION": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
                    "MAINTENANCE": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
                    "ATTENDANCE": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [1, 1, 1, 1]},
                    "RENOVATION": {"start": [1, 1, 1, 1], "active": [0, 0, 1, 1], "end": [0.9, 0.9, 0.9, 1]},

                    # Yellow Group (Logistics)
                    "LOGISTIC": {"start": [1, 1, 1, 1], "active": [1, 1, 0, 1], "end": [1, 0.8, 0.3, 1]},
                    "MOVE": {"start": [1, 1, 1, 1], "active": [1, 1, 0, 1], "end": [0.8, 0.6, 0, 1]},
                    
                    # Gray Group (Undefined / Others)
                    "NOTDEFINED": {"start": [0.7, 0.7, 0.7, 1], "active": [0.5, 0.5, 0.5, 1], "end": [0.3, 0.3, 0.3, 1]},
                    "USERDEFINED": {"start": [0.7, 0.7, 0.7, 1], "active": [0.5, 0.5, 0.5, 1], "end": [0.3, 0.3, 0.3, 1]}
                }
                ColorTypes = []
                for name, colors in default_ColorTypes.items():
                    disappears = name in ["DEMOLITION", "REMOVAL", "DISPOSAL", "DISMANTLE"]
                    ColorTypes.append({
                        "name": name,
                        "consider_start": True,
                        "consider_active": True,
                        "consider_end": True,
                        "start_color": colors["start"],
                        "in_progress_color": colors["active"],
                        "end_color": colors["end"],
                        "use_start_original_color": False,
                        "use_active_original_color": False,
                        "use_end_original_color": not disappears,
                        "start_transparency": 0.0,
                        "active_start_transparency": 0.0,
                        "active_finish_transparency": 0.0,
                        "active_transparency_interpol": 1.0,
                        "end_transparency": 0.0
                    })
                data["DEFAULT"] = {"ColorTypes": ColorTypes}
                scene[key] = json.dumps(data)

    # ==================================================================
    # === 1. FUNCIÓN CORREGIDA (PREPARACIÓN DE DATOS) ==================
    # ==================================================================
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

            # --- CORRECTION: Use the selected date source ---
            task_start = ifcopenshell.util.sequence.derive_date(task, start_date_type, is_earliest=True)
            task_finish = ifcopenshell.util.sequence.derive_date(task, finish_date_type, is_latest=True)
            if not task_start or not task_finish:
                return

            # === CAMBIO CLAVE ===
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
    def get_assigned_ColorType_for_task(cls, task: ifcopenshell.entity_instance, animation_props, active_group_name: Optional[str] = None):
        """Gets the profile for a task GIVEN a specific active group."""
        # Resolve active group if not provided
        if not active_group_name:
            try:
                ag = None
                for it in getattr(animation_props, 'animation_group_stack', []):
                    if getattr(it, 'enabled', False) and getattr(it, 'group', None):
                        ag = it.group
                        break
                if not ag:
                    ag = getattr(animation_props, 'ColorType_groups', None)
                active_group_name = ag or "DEFAULT"
            except Exception:
                active_group_name = "DEFAULT"

        # NEW: Get task configuration from the persistent cache instead of the UI list.
        # This makes the function independent of the current UI filters.
        import bpy, json
        context = bpy.context
        task_id_str = str(task.id())
        task_config = None
        
        try:
            # Try multiple possible cache keys
            cache_keys = [
                "_task_colortype_snapshot_cache_json",
                "_task_colortype_snapshot_json_WS_1224",  # The key from debug output
                "_task_colortype_snapshot_json"
            ]

            task_config = None
            for cache_key in cache_keys:
                cache_raw = context.scene.get(cache_key)
                if cache_raw:
                    print(f"   📂 Found cache data in key: {cache_key}")
                    cached_data = json.loads(cache_raw)
                    task_config = cached_data.get(task_id_str)
                    if task_config:
                        print(f"   ✅ Found config for task {task_id_str} in cache")
                        break
                    else:
                        print(f"   ⚠️ Cache key {cache_key} exists but no config for task {task_id_str}")

            if not task_config:
                print(f"   ❌ No task config found in any cache key for task {task_id_str}")

        except Exception as e:
            print(f"Bonsai WARNING: Could not read task config cache: {e}")
            task_config = None

        # 1) Specific assignment by group in the task
        if task_config:
            print(f"   📋 Found task config with {len(task_config.get('groups', []))} group assignments:")
            for i, choice in enumerate(task_config.get("groups", [])):
                is_enabled = choice.get("enabled", False)
                group_name = choice.get("group_name")
                selected_value = choice.get("selected_value") or choice.get("selected_colortype")
                print(f"     [{i}] group='{group_name}', enabled={is_enabled}, selected='{selected_value}'")
                if group_name == active_group_name and is_enabled and selected_value:
                    print(f"   🎯 MATCH! Using specific assignment: '{selected_value}' for group '{active_group_name}'")
                    ColorType = cls.load_ColorType_from_group(active_group_name, selected_value)
                    if ColorType:
                        return ColorType
        else:
            print(f"   📋 No task config found in cache for task {task.id()}")

        task_predefined_type = getattr(task, "PredefinedType", "NOTDEFINED") or "NOTDEFINED"
        task_name = getattr(task, "Name", "Unknown")

        print(f"🔍 DEBUG get_assigned_ColorType_for_task: Task '{task_name}' (ID:{task.id()})")
        print(f"   - PredefinedType: '{task_predefined_type}'")
        print(f"   - Active group: '{active_group_name}'")

        # 2) PredefinedType in active group
        ColorType = cls.load_ColorType_from_group(active_group_name, task_predefined_type)
        if ColorType:
            print(f"   ✅ Found ColorType '{task_predefined_type}' in group '{active_group_name}'")
            return ColorType
        else:
            print(f"   ❌ ColorType '{task_predefined_type}' NOT found in group '{active_group_name}'")

        # If the active group wasn't DEFAULT and we didn't find a profile,
        # explicitly fall back to the DEFAULT group. This is more predictable.
        if active_group_name != "DEFAULT":
            print(f"   🔄 Trying fallback to DEFAULT group for '{task_predefined_type}'")
            default_profile = cls.load_ColorType_from_group("DEFAULT", task_predefined_type)
            if default_profile:
                print(f"   ✅ Found '{task_predefined_type}' in DEFAULT group")
                return default_profile
            else:
                print(f"   ❌ '{task_predefined_type}' NOT found in DEFAULT group either")

        # As an absolute last resort (which should not be reached), return the "NOTDEFINED" profile.
        print(f"   ⚠️ Using NOTDEFINED fallback for task '{task_name}'")
        return cls.load_ColorType_from_group("DEFAULT", "NOTDEFINED")

    @classmethod
    def load_ColorType_from_group(cls, group_name, ColorType_name):
        import bpy, json
        scene = bpy.context.scene
        raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            data = {}
        group_data = data.get(group_name, {})

        # DEBUG: Show available ColorTypes in the group
        available_types = [prof_data.get("name", "") for prof_data in group_data.get("ColorTypes", [])]
        print(f"🔍 DEBUG load_ColorType_from_group: Looking for '{ColorType_name}' in group '{group_name}'")
        print(f"   Available ColorTypes in '{group_name}': {available_types}")

        for prof_data in group_data.get("ColorTypes", []):
            if prof_data.get("name") == ColorType_name:
                print(f"   ✅ Found ColorType '{ColorType_name}' in group '{group_name}'")
                return type('AnimationColorSchemes', (object,), {
                    'name': prof_data.get("name", ""),
                    'consider_start': prof_data.get("consider_start", True),
                    'consider_active': prof_data.get("consider_active", True),
                    'consider_end': prof_data.get("consider_end", True),
                    'start_color': prof_data.get("start_color", [1,1,1,1]),
                    'in_progress_color': prof_data.get("in_progress_color", [1,1,0,1]),
                    'end_color': prof_data.get("end_color", [0,1,0,1]),
                    'use_start_original_color': prof_data.get("use_start_original_color", False),
                    'use_active_original_color': prof_data.get("use_active_original_color", False),
                    'use_end_original_color': prof_data.get("use_end_original_color", True),
                    'start_transparency': prof_data.get("start_transparency", 0.0),
                    'active_start_transparency': prof_data.get("active_start_transparency", 0.0),
                    'active_finish_transparency': prof_data.get("active_finish_transparency", 0.0),
                    'active_transparency_interpol': prof_data.get("active_transparency_interpol", 1.0),
                    'end_transparency': prof_data.get("end_transparency", 0.0),
                    'hide_at_end': bool(prof_data.get("hide_at_end", prof_data.get("name") in {"DEMOLITION","REMOVAL","DISPOSAL","DISMANTLE"})),
                })()

        print(f"   ❌ ColorType '{ColorType_name}' NOT FOUND in group '{group_name}'")
        return None

    @classmethod
    def sync_active_group_to_json(cls):
        """Sincroniza los perfiles del grupo activo de la UI al JSON de la escena"""
        import bpy, json
        scene = bpy.context.scene
        anim_props = cls.get_animation_props()
        active_group = getattr(anim_props, "ColorType_groups", None)
        if not active_group:
            return

        # --- INICIO DE LA CORRECCIÓN ---
        if active_group == "DEFAULT":
            # El grupo DEFAULT es de solo lectura y se gestiona automáticamente.
            # Esto previene que perfiles personalizados se guarden en él por error.
            print("Bonsai INFO: The 'DEFAULT' group is read-only and cannot be modified from the UI.")
            return
        # --- FIN DE LA CORRECCIÓN ---
        raw = scene.get("BIM_AnimationColorSchemesSets", "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            data = {}
        ColorTypes_data = []
        for ColorType in getattr(anim_props, "ColorTypes", []):
            try:
                ColorTypes_data.append({
                    "name": ColorType.name,
                    "consider_start": bool(getattr(ColorType, "consider_start", True)),
                    "consider_active": bool(getattr(ColorType, "consider_active", True)),
                    "consider_end": bool(getattr(ColorType, "consider_end", True)),
                    "start_color": list(getattr(ColorType, "start_color", [1,1,1,1])),
                    "in_progress_color": list(getattr(ColorType, "in_progress_color", [1,1,0,1])),
                    "end_color": list(getattr(ColorType, "end_color", [0,1,0,1])),
                    "use_start_original_color": bool(getattr(ColorType, "use_start_original_color", False)),
                    "use_active_original_color": bool(getattr(ColorType, "use_active_original_color", False)),
                    "use_end_original_color": bool(getattr(ColorType, "use_end_original_color", True)),
                    "start_transparency": float(getattr(ColorType, "start_transparency", 0.0)),
                    "active_start_transparency": float(getattr(ColorType, "active_start_transparency", 0.0)),
                    "active_finish_transparency": float(getattr(ColorType, "active_finish_transparency", 0.0)),
                    "active_transparency_interpol": float(getattr(ColorType, "active_transparency_interpol", 1.0)),
                    "end_transparency": float(getattr(ColorType, "end_transparency", 0.0)),
                    "hide_at_end": bool(getattr(ColorType, "hide_at_end", getattr(ColorType, "name", "") in {"DEMOLITION","REMOVAL","DISPOSAL","DISMANTLE"})),
                })
            except Exception:
                pass
        data[active_group] = {"ColorTypes": ColorTypes_data}
        scene["BIM_AnimationColorSchemesSets"] = json.dumps(data)
    @classmethod
    def animate_objects_with_ColorTypes(cls, settings, product_frames):
        # --- START OF CORRECTION: Restore initialization of local variables ---
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
        # --- END OF CORRECTION ---
        # --- REFACTORED: Separated logic for baking vs. live updates ---
        for obj in bpy.data.objects:
            element = tool.Ifc.get_entity(obj)
            if not element or element.is_a("IfcSpace"):
                if element and element.is_a("IfcSpace"): cls.hide_object(obj)
                continue

            if element.id() not in product_frames:
                obj.hide_viewport = True
                obj.hide_render = True
                continue

            # CORRECCIÓN PRINCIPAL: Para objetos que SÍ van a ser animados, 
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
            # CORRECCIÓN 1: Convertir las claves de product_frames a string para el almacenamiento en la escena
            string_keyed_product_frames = {str(k): v for k, v in product_frames.items()}

            # CORRECCIÓN 2: Crear una versión serializable de los datos de frames
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

    # ==================================================================
    # === 2. (APLICACIÓN DE COLOR TYPE) ==================
    # ==================================================================
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

        # CORRECCIÓN: NO cambiar la visibilidad del objeto inmediatamente.
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
            # CORRECCIÓN: Preparar keyframes sin cambiar estado actual
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

            # CORRECCIÓN: Preparar keyframes sin cambiar estado actual
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
                from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
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
    def _get_best_ColorType_for_task(cls, task, anim_props):
            """Determina el perfil más apropiado para una tarea considerando la pila de grupos y elección por tarea."""
            """Determines the most appropriate profile for a task considering the group stack and choice per task."""
            try:
                # Determine the active group (first enabled group in the stack) or DEFAULT
                agn = None
                for it in getattr(anim_props, 'animation_group_stack', []):
                    if getattr(it, 'enabled', False) and getattr(it, 'group', None):
                        agn = it.group
                        break
                if not agn:
                    agn = 'DEFAULT'
                ColorType = cls.get_assigned_ColorType_for_task(task, anim_props, agn)
                if ColorType:
                    return ColorType
            except Exception:
                pass
            predefined_type = task.PredefinedType or "NOTDEFINED"
            # Try in DEFAULT
            try:
                prof = cls.load_ColorType_from_group("DEFAULT", predefined_type)
                if prof:
                    return prof
            except Exception:
                pass
            # Fallback to the NOTDEFINED profile from the DEFAULT group.
            return cls.load_ColorType_from_group("DEFAULT", "NOTDEFINED")

    @classmethod
    def _task_has_consider_start_ColorType(cls, task):
        """Helper to check if a task's resolved ColorType has consider_start=True."""
        try:
            # Re-use existing logic to find the best ColorType for the task
            anim_props = cls.get_animation_props()
            ColorType = cls._get_best_ColorType_for_task(task, anim_props)
            return getattr(ColorType, 'consider_start', False)
        except Exception as e:
            print(f"⚠️ Error in _task_has_consider_start_ColorType for task {getattr(task, 'Name', 'N/A')}: {e}")
            return False

    @classmethod
    def _apply_ColorType_to_object(cls, obj, frame_data, ColorType, original_color, settings):
            for state_name, (start_f, end_f) in frame_data["states"].items():
                if end_f < start_f:
                    continue
                if state_name == "before_start":
                    state = "start"
                elif state_name == "active":
                    state = "in_progress"
                elif state_name == "after_end":
                    state = "end"
                else:
                    continue
                if state == "start" and not getattr(ColorType, 'consider_start', True):
                    if frame_data.get("relationship") == "output":
                        obj.hide_viewport = True
                        obj.hide_render = True
                        obj.keyframe_insert(data_path="hide_viewport", frame=start_f)
                        obj.keyframe_insert(data_path="hide_render", frame=start_f)
                    return
                elif state == "in_progress" and not getattr(ColorType, 'consider_active', True):
                    return
                elif state == "end" and not getattr(ColorType, 'consider_end', True):
                    return
                cls.apply_state_appearance(obj, ColorType, state, start_f, end_f, original_color, frame_data)
                # Transparency: fade during active stretch
                try:
                    if state == 'in_progress':
                        vals0 = _seq_data.interpolate_ColorType_values(ColorType, 'in_progress', 0.0)
                        vals1 = _seq_data.interpolate_ColorType_values(ColorType, 'in_progress', 1.0)
                        a0 = float(vals0.get('alpha', obj.color[3] if len(obj.color) >= 4 else 1.0))
                        a1 = float(vals1.get('alpha', a0))
                        # Keyframes at the beginning and end of the active stretch
                        c = list(obj.color)
                        if len(c) < 4:
                            c = [c[0], c[1], c[2], 1.0]
                        c[3] = a0
                        obj.color = c
                        obj.keyframe_insert(data_path='color', frame=int(start_f))
                        c[3] = a1
                        obj.color = c
                        obj.keyframe_insert(data_path='color', frame=int(end_f))
                except Exception:
                    pass

    # --- NEW: Live Color Update Handler ---
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
                
            # CORRECCIÓN: Usar claves de string para buscar en el caché
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

    @classmethod
    def add_text_animation_handler(cls, settings):
            """Creates multiple animated text objects to display schedule information"""

            from datetime import timedelta

            collection_name = "Schedule_Display_Texts"
            if collection_name in bpy.data.collections:
                collection = bpy.data.collections[collection_name]
                # Limpiar objetos anteriores
                # Clear previous objects
                for obj in list(collection.objects):
                    try:
                        bpy.data.objects.remove(obj, do_unlink=True)
                    except Exception:
                        pass
            else:
                collection = bpy.data.collections.new(collection_name)
                try:
                    bpy.context.scene.collection.children.link(collection)
                except Exception:
                    pass

            text_configs = [
                {"name": "Schedule_Date", "position": (0, 10, 5), "size": 1.2, "align": "CENTER", "color": (1, 1, 1, 1), "type": "date"},
                {"name": "Schedule_Week", "position": (0, 10, 4), "size": 1.0, "align": "CENTER", "color": (1, 1, 1, 1), "type": "week"},
                {"name": "Schedule_Day_Counter", "position": (0, 10, 3), "size": 0.8, "align": "CENTER", "color": (1, 1, 1, 1), "type": "day_counter"},
                {"name": "Schedule_Progress", "position": (0, 10, 2), "size": 1.0, "align": "CENTER", "color": (1, 1, 1, 1), "type": "progress"},
            ]

            created_texts = []
            for config in text_configs:
                text_obj = cls._create_animated_text(config, settings, collection)
                created_texts.append(text_obj)

            # Auto-configure HUD if there is an active 4D camera
            try:
                scene = bpy.context.scene
                if scene.camera and "4D_Animation_Camera" in scene.camera.name:
                    anim_props = cls.get_animation_props()
                    camera_props = anim_props.camera_orbit

                    # Only auto-enable if not already configured
                    if not getattr(camera_props, "enable_text_hud", False):
                        print("🎯 Auto-enabling HUD for new schedule texts...")
                        camera_props.enable_text_hud = True

                        # Setup diferido para asegurar que los textos estén completamente creados
                        def setup_hud_deferred():
                            try:
                                bpy.ops.bim.setup_text_hud()
                                print("✅ Deferred HUD setup completed")
                            except Exception as e:
                                print(f"Deferred HUD setup failed: {e}")

                        bpy.app.timers.register(setup_hud_deferred, first_interval=0.3)
                    else:
                        # If already enabled, just update positions
                        def update_hud_deferred():
                            try:
                                bpy.ops.bim.update_text_hud_positions()
                            except Exception as e:
                                print(f"HUD position update failed: {e}")

                        bpy.app.timers.register(update_hud_deferred, first_interval=0.1)

            except Exception as e:
                print(f"Error in auto-HUD setup: {e}")
            cls._register_multi_text_handler(settings)
            return created_texts

    @classmethod
    def create_text_objects_static(cls, settings):
        """Creates static 3D text objects for snapshot mode (NO animation handler registration)"""
        from datetime import timedelta
        print("📸 Creating STATIC 3D text objects for snapshot mode")

        collection_name = "Schedule_Display_Texts"
        if collection_name in bpy.data.collections:
            collection = bpy.data.collections[collection_name]
            # Clear previous objects
            for obj in list(collection.objects):
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception:
                    pass
        else:
            collection = bpy.data.collections.new(collection_name)
            try:
                bpy.context.scene.collection.children.link(collection)
            except Exception:
                pass

        text_configs = [
                {"name": "Schedule_Date", "position": (0, 10, 5), "size": 1.2, "align": "CENTER", "color": (1, 1, 1, 1), "type": "date"},
                {"name": "Schedule_Week", "position": (0, 10, 4), "size": 1.0, "align": "CENTER", "color": (1, 1, 1, 1), "type": "week"},
                {"name": "Schedule_Day_Counter", "position": (0, 10, 3), "size": 0.8, "align": "CENTER", "color": (1, 1, 1, 1), "type": "day_counter"},
                {"name": "Schedule_Progress", "position": (0, 10, 2), "size": 1.0, "align": "CENTER", "color": (1, 1, 1, 1), "type": "progress"},
            ]

        created_texts = []
        for config in text_configs:
            text_obj = cls._create_static_text(config, settings, collection)
            created_texts.append(text_obj)

        print(f"✅ Created {len(created_texts)} static 3D text objects for snapshot mode")
        return created_texts

    @classmethod
    def _create_static_text(cls, config, settings, collection):
        """Creates a single static 3D text object with fixed content based on snapshot date"""
        text_curve = bpy.data.curves.new(name=config["name"], type='FONT')
        text_curve.size = config["size"]
        text_curve.align_x = config["align"]
        text_curve.align_y = 'CENTER'
        text_curve["text_type"] = config["type"]

        # Get the snapshot date from settings
        snapshot_date = settings.get("start") if isinstance(settings, dict) else getattr(settings, "start", None)

        # Set the text content based on the type and snapshot date
        text_type = config["type"].lower()
        if text_type == "date":
            if snapshot_date:
                try:
                    text_curve.body = snapshot_date.strftime("%d/%m/%Y")
                except Exception:
                    text_curve.body = str(snapshot_date).split("T")[0]
            else:
                text_curve.body = "Date: --"

        elif text_type == "week":
            text_curve.body = cls._calculate_static_week_text(snapshot_date)
        elif text_type == "day_counter":
            text_curve.body = cls._calculate_static_day_text(snapshot_date)
        elif text_type == "progress":
            text_curve.body = cls._calculate_static_progress_text(snapshot_date)
        else:
            text_curve.body = f"Static {config['type']}"

        # Create the text object
        text_obj = bpy.data.objects.new(config["name"], text_curve)
        text_obj.location = config["position"]

        # Set color if available
        if "color" in config:
            color = config["color"]
            if hasattr(text_obj, "color"):
                text_obj.color = color

        collection.objects.link(text_obj)

        print(f"📝 Created static text: {config['name']} = '{text_curve.body}'")
        return text_obj

    @classmethod
    def _calculate_static_week_text(cls, snapshot_date):
        """Calculate static week text for snapshot mode"""
        try:
            if not snapshot_date:
                return "Week --"

            # Get schedule range for week calculation
            sch_start, sch_finish = cls.get_schedule_date_range()
            if not sch_start:
                return "Week --"

            cd_d = snapshot_date.date()
            fss_d = sch_start.date()
            delta_days = (cd_d - fss_d).days

            if cd_d < fss_d:
                week_number = 0
            else:
                week_number = max(1, (delta_days // 7) + 1)

            return f"Week {week_number}"
        except Exception as e:
            print(f"❌ Error calculating static week: {e}")
            return "Week --"

    @classmethod
    def _calculate_static_day_text(cls, snapshot_date):
        """Calculate static day text for snapshot mode"""
        try:
            if not snapshot_date:
                return "Day --"

            # Get schedule range for day calculation
            sch_start, sch_finish = cls.get_schedule_date_range()
            if not sch_start:
                return "Day --"

            cd_d = snapshot_date.date()
            fss_d = sch_start.date()
            delta_days = (cd_d - fss_d).days

            if cd_d < fss_d:
                day_number = 0
            else:
                day_number = max(1, delta_days + 1)

            return f"Day {day_number}"
        except Exception as e:
            print(f"❌ Error calculating static day: {e}")
            return "Day --"

    @classmethod
    def _calculate_static_progress_text(cls, snapshot_date):
        """Calculate static progress text for snapshot mode"""
        try:
            if not snapshot_date:
                return "Progress: --%"

            # Get schedule range for progress calculation
            sch_start, sch_finish = cls.get_schedule_date_range()
            if not (sch_start and sch_finish):
                return "Progress: --%"

            cd_d = snapshot_date.date()
            fss_d = sch_start.date()
            fse_d = sch_finish.date()

            if cd_d < fss_d:
                progress_pct = 0
            elif cd_d >= fse_d:
                progress_pct = 100
            else:
                total_schedule_days = (fse_d - fss_d).days
                if total_schedule_days <= 0:
                    progress_pct = 100
                else:
                    delta_days = (cd_d - fss_d).days
                    progress_pct = (delta_days / total_schedule_days) * 100
                    progress_pct = round(progress_pct)
                    progress_pct = max(0, min(100, progress_pct))

            return f"Progress: {progress_pct}%"
        except Exception as e:
            print(f"❌ Error calculating static progress: {e}")
            return "Progress: --%"

    @classmethod
    def _create_animated_text(cls, config, settings, collection):

            text_curve = bpy.data.curves.new(name=config["name"], type='FONT')
            text_curve.size = config["size"]
            text_curve.align_x = config["align"]
            text_curve.align_y = 'CENTER'

            text_curve["text_type"] = config["type"]
            # Save some primitive fields (not complex objects)
            try:
                start = settings.get("start") if isinstance(settings, dict) else getattr(settings, "start", None)
                finish = settings.get("finish") if isinstance(settings, dict) else getattr(settings, "finish", None)
                start_frame = int(settings.get("start_frame", 1)) if isinstance(settings, dict) else int(getattr(settings, "start_frame", 1))
                total_frames = int(settings.get("total_frames", 250)) if isinstance(settings, dict) else int(getattr(settings, "total_frames", 250))
                # Convert datetime to ISO if necessary
                if hasattr(start, "isoformat"):
                    start_iso = start.isoformat()
                else:
                    start_iso = str(start)
                if hasattr(finish, "isoformat"):
                    finish_iso = finish.isoformat()
                else:
                    finish_iso = str(finish)
            except Exception:
                start_iso = ""
            text_curve["animation_settings"] = {
                "start_frame": start_frame,
                "total_frames": total_frames,
                "start_date": start_iso,
                "finish_date": finish_iso,
            }

            text_obj = bpy.data.objects.new(name=config["name"], object_data=text_curve)
            try:
                collection.objects.link(text_obj)
            except Exception:
                try:
                    bpy.context.scene.collection.objects.link(text_obj)
                except Exception:
                    pass
            text_obj.location = config["position"]
            cls._setup_text_material_colored(text_obj, config["color"], config["name"])
            cls._animate_text_by_type(text_obj, config["type"], settings)
            return text_obj

    @classmethod
    def _setup_text_material_colored(cls, text_obj, color, mat_name_suffix):

            mat_name = f"Schedule_Text_Mat_{mat_name_suffix}"
            mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(name=mat_name)
            try:
                mat.use_nodes = True
                nt = mat.node_tree
                bsdf = nt.nodes.get("Principled BSDF")
                if bsdf:
                    bsdf.inputs["Base Color"].default_value = tuple(list(color[:3]) + [1.0])
                    bsdf.inputs["Emission"].default_value = tuple(list(color[:3]) + [1.0])
                    bsdf.inputs["Emission Strength"].default_value = 1.5
            except Exception:
                pass
            try:
                text_obj.data.materials.clear()
                text_obj.data.materials.append(mat)
            except Exception:
                pass

    @classmethod
    def _animate_text_by_type(cls, text_obj, text_type, settings):

            from datetime import timedelta, datetime as _dt

            start_date = settings.get("start") if isinstance(settings, dict) else getattr(settings, "start", None)
            finish_date = settings.get("finish") if isinstance(settings, dict) else getattr(settings, "finish", None)
            start_frame = int(settings.get("start_frame", 1)) if isinstance(settings, dict) else int(getattr(settings, "start_frame", 1))
            total_frames = int(settings.get("total_frames", 250)) if isinstance(settings, dict) else int(getattr(settings, "total_frames", 250))

            if isinstance(start_date, str):
                try:
                    from dateutil import parser as _parser
                    start_date = _dt.fromisoformat(start_date.replace(' ', 'T')[:19]) if '-' in start_date else _parser.parse(start_date, yearfirst=True)
                except Exception:
                    start_date = _dt.now()
            if isinstance(finish_date, str):
                try:
                    from dateutil import parser as _parser
                    finish_date = _dt.fromisoformat(finish_date.replace(' ', 'T')[:19]) if '-' in finish_date else _parser.parse(finish_date, yearfirst=True)
                except Exception:
                    finish_date = start_date

            duration = finish_date - start_date
            step_days = 7 if duration.days > 365 else (3 if duration.days > 90 else 1)

            current_date = start_date
            while current_date <= finish_date:
                if duration.total_seconds() > 0:
                    progress = (current_date - start_date).total_seconds() / duration.total_seconds()
                else:
                    progress = 0.0
                frame = start_frame + (progress * total_frames)

                if text_type == "date":
                    text_content = cls._format_date(current_date)
                elif text_type == "week":
                    text_content = cls._format_week(current_date, start_date)
                elif text_type == "day_counter":
                    text_content = cls._format_day_counter(current_date, start_date, finish_date)
                elif text_type == "progress":
                    text_content = cls._format_progress(current_date, start_date, finish_date)
                else:
                    text_content = ""

                text_obj.data.body = text_content
                try:
                    text_obj.data.keyframe_insert(data_path="body", frame=int(frame))
                except Exception:
                    pass

                current_date += timedelta(days=step_days)
                if current_date > finish_date and current_date - timedelta(days=step_days) < finish_date:
                    current_date = finish_date

    @classmethod
    def _format_date(cls, current_date):
            try:
                return current_date.strftime("%d/%m/%Y")
            except Exception:
                return str(current_date)

    @classmethod
    def _format_week(cls, current_date, start_date):
            try:
                # Get full schedule dates (same as HUD logic)
                try:
                    sch_start, sch_finish = cls.get_schedule_date_range()
                    if sch_start and sch_finish:
                        # Use same logic as HUD Schedule
                        cd_d = current_date.date()
                        fss_d = sch_start.date()
                        delta_days = (cd_d - fss_d).days
                        
                        if cd_d < fss_d:
                            week_number = 0
                        else:
                            week_number = max(1, (delta_days // 7) + 1)
                        
                        print(f"📊 3D Week: current={cd_d}, schedule_start={fss_d}, week={week_number}")
                        return f"Week {week_number}"
                except Exception as e:
                    print(f"⚠️ 3D Week: Could not get schedule dates, using animation range: {e}")
                
                # Fallback: use animation range
                days_elapsed = (current_date - start_date).days
                current_week = (days_elapsed // 7) + 1
                return f"Week {current_week}"
            except Exception:
                return "Week ?"

    @classmethod
    def _format_day_counter(cls, current_date, start_date, finish_date):
            try:
                # Get full schedule dates (same as HUD logic)
                try:
                    sch_start, sch_finish = cls.get_schedule_date_range()
                    if sch_start and sch_finish:
                        # Use same logic as HUD Schedule
                        cd_d = current_date.date()
                        fss_d = sch_start.date()
                        delta_days = (cd_d - fss_d).days
                        
                        if cd_d < fss_d:
                            day_from_schedule = 0
                        else:
                            day_from_schedule = max(1, delta_days + 1)
                        
                        print(f"📊 3D Day: current={cd_d}, schedule_start={fss_d}, day={day_from_schedule}")
                        return f"Day {day_from_schedule}"
                except Exception as e:
                    print(f"⚠️ 3D Day: Could not get schedule dates, using animation range: {e}")
                
                # Fallback: use animation range
                days_elapsed = (current_date - start_date).days + 1
                return f"Day {days_elapsed}"
            except Exception:
                return "Day ?"

    @classmethod
    def _format_progress(cls, current_date, start_date, finish_date):
            try:
                # Get full schedule dates (same as HUD logic)
                try:
                    sch_start, sch_finish = cls.get_schedule_date_range()
                    if sch_start and sch_finish:
                        # Use same logic as HUD Schedule
                        cd_d = current_date.date()
                        fss_d = sch_start.date()
                        fse_d = sch_finish.date()
                        
                        if cd_d < fss_d:
                            progress_pct = 0
                        elif cd_d >= fse_d:
                            progress_pct = 100
                        else:
                            total_schedule_days = (fse_d - fss_d).days
                            if total_schedule_days <= 0:
                                progress_pct = 100
                            else:
                                delta_days = (cd_d - fss_d).days
                                progress_pct = (delta_days / total_schedule_days) * 100
                                progress_pct = round(progress_pct)
                                progress_pct = max(0, min(100, progress_pct))
                        
                        print(f"📊 3D Progress: current={cd_d}, schedule_start={fss_d}, end={fse_d}, progress={progress_pct}%")
                        return f"Progress: {progress_pct}%"
                except Exception as e:
                    print(f"⚠️ 3D Progress: Could not get schedule dates, using animation range: {e}")
                
                # Fallback: use animation range
                total = (finish_date - start_date).days
                if total > 0:
                    progress = ((current_date - start_date).days / total) * 100.0
                else:
                    progress = 100.0
                return f"Progress: {progress:.0f}%"
            except Exception:
                return "Progress: ?%"

    @classmethod
    def _register_multi_text_handler(cls, settings):

            from datetime import datetime as _dt

            cls._unregister_frame_change_handler()

            def update_all_schedule_texts(scene):
                print("🎬 3D Text Handler (main): Starting update...")
                collection_name = "Schedule_Display_Texts"
                coll = bpy.data.collections.get(collection_name)
                if not coll:
                    print("⚠️ 3D Text Handler (main): No 'Schedule_Display_Texts' collection found")
                    return
                print(f"📝 3D Text Handler (main): Found collection with {len(coll.objects)} objects")
                current_frame = int(scene.frame_current)
                for text_obj in list(coll.objects):
                    anim_settings = text_obj.data.get("animation_settings") if getattr(text_obj, "data", None) else None
                    if not anim_settings:
                        continue
                    start_frame = int(anim_settings.get("start_frame", 1))
                    total_frames = int(anim_settings.get("total_frames", 250))
                    if current_frame < start_frame:
                        progress = 0.0
                    elif current_frame > start_frame + total_frames:
                        progress = 1.0
                    else:
                        progress = (current_frame - start_frame) / float(total_frames or 1)

                    try:
                        start_date = _dt.fromisoformat(anim_settings.get("start_date"))
                        finish_date = _dt.fromisoformat(anim_settings.get("finish_date"))
                    except Exception:
                        continue
                    duration = finish_date - start_date
                    current_date = start_date + (duration * progress)

                    ttype = text_obj.data.get("text_type", "date")
                    if ttype == "date":
                        text_obj.data.body = cls._format_date(current_date)
                    elif ttype == "week":
                        text_obj.data.body = cls._format_week(current_date, start_date)
                    elif ttype == "day_counter":
                        text_obj.data.body = cls._format_day_counter(current_date, start_date, finish_date)
                    elif ttype == "progress":
                        text_obj.data.body = cls._format_progress(current_date, start_date, finish_date)

            bpy.app.handlers.frame_change_post.append(update_all_schedule_texts)
            cls._frame_change_handler = update_all_schedule_texts

    @classmethod
    def _unregister_frame_change_handler(cls):
            try:

                if getattr(cls, "_frame_change_handler", None) in bpy.app.handlers.frame_change_post:
                    bpy.app.handlers.frame_change_post.remove(cls._frame_change_handler)
            except Exception:
                pass
            cls._frame_change_handler = None

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
    def get_tasks_for_product(cls, product, work_schedule=None):
        """
        Obtiene las tareas de entrada y salida para un producto específico.

        Args:
            product: El producto IFC
            work_schedule: El cronograma de trabajo (opcional)

        Returns:
            tuple: (task_inputs, task_outputs)
        """
        try:
            # Usar los métodos existentes para encontrar tareas relacionadas
            input_tasks = cls.find_related_input_tasks(product)
            output_tasks = cls.find_related_output_tasks(product)

            # Si se proporciona work_schedule, filtrar solo las tareas de ese cronograma
            if work_schedule:
                # Obtener todas las tareas controladas por el work_schedule
                controlled_task_ids = set()
                for rel in work_schedule.Controls or []:
                    for obj in rel.RelatedObjects:
                        if obj.is_a("IfcTask"):
                            controlled_task_ids.add(obj.id())

                # Filtrar las tareas de entrada
                filtered_input_tasks = []
                for task in input_tasks:
                    if task.id() in controlled_task_ids:
                        filtered_input_tasks.append(task)

                # Filtrar las tareas de salida
                filtered_output_tasks = []
                for task in output_tasks:
                    if task.id() in controlled_task_ids:
                        filtered_output_tasks.append(task)

                return filtered_input_tasks, filtered_output_tasks

            return input_tasks, output_tasks

        except Exception as e:
            print(f"Error en get_tasks_for_product: {e}")
            return [], []

    @classmethod
    def load_product_related_tasks(cls, product):
        """
        Carga las tareas relacionadas con un producto y las muestra en la UI.

        Args:
            product: El producto IFC para el cual buscar tareas

        Returns:
            str: Mensaje de resultado o lista de tareas
        """
        try:
            props = cls.get_work_schedule_props()

            # Obtener el work_schedule activo si existe
            active_work_schedule = None
            if props.active_work_schedule_id:
                active_work_schedule = tool.Ifc.get().by_id(props.active_work_schedule_id)

            # Llamar al método con el work_schedule
            task_inputs, task_outputs = cls.get_tasks_for_product(product, active_work_schedule)

            # Limpiar las listas existentes
            props.product_input_tasks.clear()
            props.product_output_tasks.clear()

            # Cargar tareas de entrada
            for task in task_inputs:
                new_input = props.product_input_tasks.add()
                new_input.ifc_definition_id = task.id()
                new_input.name = task.Name or "Unnamed"

            # Cargar tareas de salida
            for task in task_outputs:
                new_output = props.product_output_tasks.add()
                new_output.ifc_definition_id = task.id()
                new_output.name = task.Name or "Unnamed"

            total_tasks = len(task_inputs) + len(task_outputs)

            if total_tasks == 0:
                return "No related tasks found for this product"

            return f"Found {len(task_inputs)} input tasks and {len(task_outputs)} output tasks"

        except Exception as e:
            print(f"Error in load_product_related_tasks: {e}")
            return f"Error loading tasks: {str(e)}"

    @classmethod
    def validate_task_object(cls, task, operation_name="operation"):
        """
        Valida que un objeto tarea sea válido antes de procesarlo.

        Args:
            task: El objeto tarea a validar
            operation_name: Nombre de la operación para logging

        Returns:
            bool: True si la tarea es válida, False en caso contrario
        """
        if task is None:
            print(f"⚠️ Warning: None task in {operation_name}")
            return False

        if not hasattr(task, 'id') or not callable(getattr(task, 'id', None)):
            print(f"⚠️ Warning: Invalid task object in {operation_name}: {task}")
            return False

        try:
            task_id = task.id()
            if task_id is None or task_id <= 0:
                print(f"⚠️ Warning: Invalid task ID in {operation_name}: {task_id}")
                return False
        except Exception as e:
            print(f"⚠️ Error getting task ID in {operation_name}: {e}")
            return False

        return True


    @classmethod
    def get_work_schedule_products(cls, work_schedule: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
        """
        Obtiene todos los productos asociados a un cronograma de trabajo.

        Args:
            work_schedule: El cronograma de trabajo IFC

        Returns:
            Lista de productos IFC (puede ser vacía)
        """
        try:
            products: list[ifcopenshell.entity_instance] = []

            # Obtener todas las tareas del cronograma
            if hasattr(work_schedule, 'Controls') and work_schedule.Controls:
                for rel in work_schedule.Controls:
                    for task in rel.RelatedObjects:
                        if task.is_a("IfcTask"):
                            # Obtener productos de salida (outputs)
                            task_outputs = cls.get_task_outputs(task) or []
                            products.extend(task_outputs)

                            # Obtener productos de entrada (inputs)
                            task_inputs = cls.get_task_inputs(task) or []
                            products.extend(task_inputs)

            # Eliminar duplicados manteniendo el orden
            seen: set[int] = set()
            unique_products: list[ifcopenshell.entity_instance] = []
            for product in products:
                try:
                    pid = product.id()
                except Exception:
                    pid = None
                if pid and pid not in seen:
                    seen.add(pid)
                    unique_products.append(product)

            return unique_products

        except Exception as e:
            print(f"Error getting work schedule products: {e}")
            return []

    @classmethod
    def select_work_schedule_products(cls, work_schedule: ifcopenshell.entity_instance) -> str:
        """
        Selecciona todos los productos asociados a un cronograma de trabajo.

        Args:
            work_schedule: El cronograma de trabajo IFC

        Returns:
            Mensaje de resultado
        """
        try:
            products = cls.get_work_schedule_products(work_schedule)

            if not products:
                return "No products found in work schedule"

            # Usar la función segura de spatial para seleccionar productos
            tool.Spatial.select_products(products)

            return f"Selected {len(products)} products from work schedule"

        except Exception as e:
            print(f"Error selecting work schedule products: {e}")
            return f"Error selecting products: {str(e)}"

    @classmethod
    def select_unassigned_work_schedule_products(cls) -> str:
        """
        Selecciona productos que no están asignados a ningún cronograma de trabajo.

        Returns:
            Mensaje de resultado
        """
        try:
            ifc_file = tool.Ifc.get()
            if not ifc_file:
                return "No IFC file loaded"

            # Obtener todos los productos
            all_products = list(ifc_file.by_type("IfcProduct"))

            # Obtener productos asignados a cronogramas
            schedule_products: set[int] = set()
            for work_schedule in ifc_file.by_type("IfcWorkSchedule"):
                ws_products = cls.get_work_schedule_products(work_schedule) or []
                for product in ws_products:
                    try:
                        pid = product.id()
                    except Exception:
                        pid = None
                    if pid:
                        schedule_products.add(pid)

            # Filtrar productos no asignados
            unassigned_products: list[ifcopenshell.entity_instance] = []
            for product in all_products:
                try:
                    pid = product.id()
                except Exception:
                    pid = None
                if pid and pid not in schedule_products:
                    # Verificar que no sea un elemento espacial
                    try:
                        is_spatial = tool.Root.is_spatial_element(product)
                    except Exception:
                        is_spatial = False
                    if not is_spatial:
                        unassigned_products.append(product)

            if not unassigned_products:
                return "No unassigned products found"

            # Seleccionar productos no asignados
            tool.Spatial.select_products(unassigned_products)

            return f"Selected {len(unassigned_products)} unassigned products"

        except Exception as e:
            print(f"Error selecting unassigned products: {e}")
            return f"Error selecting unassigned products: {str(e)}"

    # --- INICIO: LÓGICA DE IMPORT/EXPORT DE CONFIGURACIÓN DE CRONOGRAMA ---

    @classmethod
    def _force_complete_task_snapshot(cls, context, work_schedule):
        """
        Fuerza una captura completa de TODAS las tareas del cronograma especificado,
        no solo las visibles en la UI. Esto asegura que Copy3D capture configuraciones
        de todas las tareas, no solo las actualmente mostradas en el task tree.
        """
        import json
        try:
            print(f"🔄 Copy3D: Forcing complete task snapshot for schedule '{work_schedule.Name}'...")
            
            # Obtener todas las tareas del cronograma directamente del IFC
            def get_all_tasks_recursive(tasks):
                all_tasks = []
                for task in tasks:
                    all_tasks.append(task)
                    nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested:
                        all_tasks.extend(get_all_tasks_recursive(nested))
                return all_tasks
            
            root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
            all_schedule_tasks = get_all_tasks_recursive(root_tasks)
            
            print(f"🔄 Copy3D: Found {len(all_schedule_tasks)} total tasks in schedule")
            
            # Crear un snapshot manual de todas las tareas del cronograma
            # Esto se hace ANTES de snapshot_all_ui_state para poblar el caché
            
            # Obtener datos actuales del caché si existen
            cache_key = "_task_colortype_snapshot_cache_json"
            cache_raw = context.scene.get(cache_key, "{}")
            try:
                cache_data = json.loads(cache_raw) if cache_raw else {}
            except:
                cache_data = {}
            
            # Para cada tarea del cronograma, asegurar que tenga entrada en el caché
            tasks_added_to_cache = 0
            for task in all_schedule_tasks:
                tid = str(task.id())
                if tid == "0":
                    continue
                    
                # Si la tarea ya está en el caché, conservar sus datos actuales
                if tid in cache_data:
                    continue
                    
                # Si no está en caché, crear entrada por defecto
                # Esto permitirá que export_schedule_configuration la encuentre
                cache_data[tid] = {
                    "active": False,
                    "selected_active_colortype": "",
                    "animation_color_schemes": "",
                    "groups": [],
                }
                tasks_added_to_cache += 1
            
            # Actualizar el caché
            if tasks_added_to_cache > 0:
                context.scene[cache_key] = json.dumps(cache_data)
                print(f"🔄 Copy3D: Added {tasks_added_to_cache} uncached tasks to snapshot cache")
            
            print(f"✅ Copy3D: Complete task snapshot forced - {len(cache_data)} tasks ready for export")
            
        except Exception as e:
            print(f"❌ Copy3D: Error forcing complete task snapshot: {e}")

    @classmethod
    def _sync_source_animation_color_schemes(cls, context):
        """
        Sincroniza el campo animation_color_schemes en tareas que tienen grupo activo
        ANTES de hacer el snapshot. Esto asegura que Copy3D capture el valor correcto.
        """
        try:
            print(f"🔄 Copy3D: Syncing animation_color_schemes in source schedule...")
            
            tprops = cls.get_task_tree_props()
            tasks_synced = 0
            
            for task in getattr(tprops, 'tasks', []):
                try:
                    # Solo procesar tareas que tienen grupo activo
                    if getattr(task, 'use_active_colortype_group', False):
                        current_animation_schemes = getattr(task, 'animation_color_schemes', '')
                        
                        # Encontrar el grupo activo y obtener su selected_colortype
                        selected_colortype = ''
                        
                        # Buscar en los grupos de la tarea directamente (más confiable)
                        group_choices = getattr(task, 'colortype_group_choices', [])
                        for choice in group_choices:
                            group_name = getattr(choice, 'group_name', '')
                            enabled = getattr(choice, 'enabled', False)
                            choice_colortype = getattr(choice, 'selected_colortype', '')
                            
                            # Encontrar el grupo activo (enabled=True) que no sea DEFAULT
                            if enabled and group_name != 'DEFAULT' and choice_colortype:
                                selected_colortype = choice_colortype
                                print(f"🔍 Copy3D SYNC: Task {task.ifc_definition_id} - Found active group '{group_name}' with colortype '{selected_colortype}'")
                                break
                        
                        # Si el grupo activo tiene un ColorType pero animation_color_schemes no coincide
                        if selected_colortype and selected_colortype != current_animation_schemes:
                            print(f"🔄 Copy3D SYNC: Task {task.ifc_definition_id} - '{current_animation_schemes}' -> '{selected_colortype}'")
                            
                            # Usar la función segura para asignar
                            from ..prop import safe_set_animation_color_schemes
                            safe_set_animation_color_schemes(task, selected_colortype)
                            tasks_synced += 1
                        elif selected_colortype:
                            print(f"✅ Copy3D SYNC: Task {task.ifc_definition_id} already synced: '{selected_colortype}'")
                        else:
                            print(f"⚠️ Copy3D SYNC: Task {task.ifc_definition_id} has active group but no selected colortype")
                            
                except Exception as e:
                    print(f"❌ Copy3D SYNC: Error syncing task {getattr(task, 'ifc_definition_id', '?')}: {e}")
                    continue
            
            print(f"✅ Copy3D: Synced animation_color_schemes for {tasks_synced} tasks with active groups")
            
        except Exception as e:
            print(f"❌ Copy3D: Error syncing source animation_color_schemes: {e}")

    @classmethod
    def _force_fresh_snapshot_from_ui(cls, context):
        """
        Fuerza un snapshot fresco basado en el estado actual de la UI,
        no en datos antiguos del caché. Esto asegura que Copy3D capture
        los valores reales de los dropdowns.
        """
        try:
            import json
            
            tprops = cls.get_task_tree_props()
            if not tprops or not hasattr(tprops, 'tasks'):
                return
            
            # Obtener cronograma activo
            ws = cls.get_active_work_schedule()
            if not ws:
                return
            
            fresh_snapshot = {}
            
            for task in tprops.tasks:
                tid = str(getattr(task, 'ifc_definition_id', 0))
                if not tid or tid == '0':
                    continue
                
                # Capturar estado actual directamente de la UI
                use_active = getattr(task, 'use_active_colortype_group', False)
                selected_active = getattr(task, 'selected_colortype_in_active_group', '')
                animation_schemes = getattr(task, 'animation_color_schemes', '')
                
                # Capturar grupos directamente del estado UI actual
                groups_data = []
                group_choices = getattr(task, 'colortype_group_choices', [])
                for choice in group_choices:
                    group_name = getattr(choice, 'group_name', '')
                    enabled = getattr(choice, 'enabled', False)
                    selected_colortype = getattr(choice, 'selected_colortype', '')
                    
                    groups_data.append({
                        "group_name": group_name,
                        "enabled": enabled,
                        "selected_value": selected_colortype,  # Usar selected_value para consistencia
                    })
                    
                    # DEBUG: Mostrar qué se está capturando desde la UI
                    if group_name == 'Group 2' and enabled:
                        print(f"🔥 FRESH CAPTURE: Task {tid} - Group '{group_name}' enabled={enabled}, selected_colortype='{selected_colortype}'")
                
                fresh_snapshot[tid] = {
                    "active": use_active,
                    "selected_active_colortype": selected_active,
                    "animation_color_schemes": animation_schemes,
                    "groups": groups_data,
                }
            
            # Sobrescribir el snapshot con los datos frescos
            snap_key = f"_task_colortype_snapshot_json_WS_{ws.id()}"
            context.scene[snap_key] = json.dumps(fresh_snapshot)
            
            print(f"✅ Copy3D: Fresh snapshot created with {len(fresh_snapshot)} tasks from current UI state")
            
        except Exception as e:
            print(f"❌ Copy3D: Error creating fresh snapshot: {e}")

    @classmethod
    def export_schedule_configuration(cls, work_schedule):
        """
        Gathers all relevant configuration from a work schedule and returns it as a dictionary.
        This includes task assignments (ICOM), ColorType libraries, and ColorType assignments.
        """
        ifc_file = tool.Ifc.get()
        context = bpy.context

        # 1. Get all tasks from the schedule from the IFC data to ensure completeness
        def get_all_tasks_recursive(tasks):
            all_tasks_list = []
            for task in tasks:
                all_tasks_list.append(task)
                nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                if nested_tasks:
                    all_tasks_list.extend(get_all_tasks_recursive(nested_tasks))
            return all_tasks_list

        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
        all_tasks_in_schedule = get_all_tasks_recursive(root_tasks)
        if not all_tasks_in_schedule:
            return {}

        # 2. Get ColorType assignments from the UI snapshot created by the operator.
        task_ColorType_snapshot = {}
        
        # First try schedule-specific snapshot key
        specific_snapshot_key = f"_task_colortype_snapshot_json_WS_{work_schedule.id()}"
        generic_snapshot_key = "_task_colortype_snapshot_json"
        
        snapshot_found = False
        if context.scene.get(specific_snapshot_key):
            try:
                task_ColorType_snapshot = json.loads(context.scene[specific_snapshot_key])
                print(f"✅ DEBUG EXPORT: Cargados {len(task_ColorType_snapshot)} perfiles desde clave específica WS_{work_schedule.id()}")
                snapshot_found = True
            except Exception as e:
                print(f"❌ DEBUG EXPORT: Error cargando perfiles desde clave específica: {e}")
        
        # Fallback to generic snapshot key if specific not found
        if not snapshot_found and context.scene.get(generic_snapshot_key):
            try:
                task_ColorType_snapshot = json.loads(context.scene[generic_snapshot_key])
                print(f"✅ DEBUG EXPORT: Cargados {len(task_ColorType_snapshot)} perfiles desde clave genérica (fallback)")
            except Exception as e:
                print(f"❌ DEBUG EXPORT: Error cargando perfiles desde clave genérica: {e}")
        
        if not snapshot_found and not context.scene.get(generic_snapshot_key):
            print("❌ DEBUG EXPORT: No se encontraron datos de perfiles en ninguna clave")
        
        # Clean problematic values before processing
        if task_ColorType_snapshot:
            task_ColorType_snapshot = cls._clean_ColorType_snapshot_data(task_ColorType_snapshot)

        # 3. Export ColorType Groups library from the scene property
        ColorType_groups_data = {}
        try:
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
            ColorType_groups_data = UnifiedColorTypeManager._read_sets_json(bpy.context)
        except Exception as e:
            print(f"Could not export ColorType groups: {e}")

        # 4. Export task-specific configurations
        task_configs = []
        for task in all_tasks_in_schedule:
            task_identification = getattr(task, "Identification", None)
            if not task_identification:
                print(f"Bonsai WARNING: Skipping task {task.id()} from config export as it has no 'Identification' attribute.")
                continue

            task_id_str = str(task.id())
            
            task_config = {
                "task_identification": task_identification,
                "predefined_type": getattr(task, "PredefinedType", None),
            }

            # ICOM Data (using GlobalId for stable mapping)
            inputs = ifcopenshell.util.sequence.get_task_inputs(task, is_deep=False)
            outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
            resources = ifcopenshell.util.sequence.get_task_resources(task, is_deep=False)
            task_config["inputs"] = [p.GlobalId for p in inputs if hasattr(p, 'GlobalId')]
            task_config["outputs"] = [p.GlobalId for p in outputs if hasattr(p, 'GlobalId')]
            task_config["resources"] = [r.GlobalId for r in resources if hasattr(r, 'GlobalId')]

            # ColorType Assignments from the snapshot (ALWAYS include, even if empty)
            ColorType_assignments = {
                "use_active_ColorType_group": False,
                "selected_ColorType_in_active_group": "",
                "animation_color_schemes": "",
                "choices": [],
            }
            
            # If task has configured ColorTypes, use them; otherwise use empty defaults
            if task_id_str in task_ColorType_snapshot:
                snap_data = task_ColorType_snapshot[task_id_str]
                choices = []
                for g_data in snap_data.get("groups", []):
                    # Buscar el valor del ColorType usando todas las claves posibles
                    colortype_value = (
                        g_data.get("selected_ColorType") or 
                        g_data.get("selected_value") or 
                        g_data.get("selected_colortype") or
                        ""
                    )
                    choices.append({
                        "group_name": g_data.get("group_name", ""),
                        "enabled": g_data.get("enabled", False),
                        "selected_ColorType": colortype_value,
                    })
                    
                    # DEBUG: Mostrar qué se está capturando
                    print(f"📤 DEBUG EXPORT: Group '{g_data.get('group_name')}' - enabled={g_data.get('enabled')}, colortype='{colortype_value}'")
                
                ColorType_assignments = {
                    "use_active_ColorType_group": snap_data.get("active", False),
                    "selected_ColorType_in_active_group": snap_data.get("selected_active_ColorType", ""),
                    "animation_color_schemes": snap_data.get("animation_color_schemes", ""),
                    "choices": choices,
                }
            else:
                # Task has no configured ColorTypes - export empty but valid structure
                # Get all available ColorType groups and create empty entries
                try:
                    from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                    available_groups = UnifiedColorTypeManager._read_sets_json(bpy.context) or {}
                    choices = []
                    for group_name in available_groups.keys():
                        choices.append({
                            "group_name": group_name,
                            "enabled": False,  # Not configured yet
                            "selected_ColorType": "",  # No ColorType selected yet
                        })
                    ColorType_assignments["choices"] = choices
                except Exception as e:
                    print(f"Warning: Could not load ColorType groups for unconfigured task {task_identification}: {e}")
            
            task_config["ColorType_assignments"] = ColorType_assignments
            task_configs.append(task_config)

        # 5. Assemble final JSON
        anim_props = cls.get_animation_props()
        export_data = {
            "version": "1.3",
            "schedule_name": work_schedule.Name,
            "ColorType_groups": ColorType_groups_data,
            "ui_settings": {
                "task_ColorType_group_selector": getattr(anim_props, "task_ColorType_group_selector", ""),
                "animation_group_stack": [
                    {"group": getattr(item, "group", ""), "enabled": bool(getattr(item, "enabled", False))}
                    for item in getattr(anim_props, "animation_group_stack", [])
                ]
            },
            "task_configurations": task_configs,
        }
        return export_data

    @classmethod
    def import_schedule_configuration(cls, data):
        """
        Applies a saved schedule configuration from a dictionary to the current IFC file.
        This function is non-destructive to the UI state.
        """
        ifc_file = tool.Ifc.get()
        work_schedule = cls.get_active_work_schedule()
        if not work_schedule:
            print("Import failed: No active work schedule.")
            return

        # 1. Import data and modify IFC
        if "ColorType_groups" in data:
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
            UnifiedColorTypeManager._write_sets_json(bpy.context, data["ColorType_groups"])

        if "ui_settings" in data:
            anim_props = cls.get_animation_props()
            anim_props.task_ColorType_group_selector = data["ui_settings"].get("task_ColorType_group_selector", "")
            
            # Import animation group stack
            if "animation_group_stack" in data["ui_settings"]:
                anim_props.animation_group_stack.clear()
                for item_data in data["ui_settings"]["animation_group_stack"]:
                    item = anim_props.animation_group_stack.add()
                    item.group = item_data.get("group", "")
                    if hasattr(item, "enabled"):
                        item.enabled = bool(item_data.get("enabled", False))

        guid_map = {p.GlobalId: p.id() for p in ifc_file.by_type("IfcProduct") if hasattr(p, 'GlobalId')}
        guid_map.update({r.GlobalId: r.id() for r in ifc_file.by_type("IfcResource") if hasattr(r, 'GlobalId')})

        # Create a map from Identification to task entity for the current file
        task_identification_map = {t.Identification: t for t in ifc_file.by_type("IfcTask") if getattr(t, 'Identification', None)}

        ColorType_assignments_to_restore = {}
        if "task_configurations" in data:
            for task_config in data["task_configurations"]:
                task_identification = task_config.get("task_identification")
                if not task_identification:
                    continue
                
                task = task_identification_map.get(task_identification)
                if not task: 
                    print(f"Bonsai WARNING: Task with Identification '{task_identification}' not found in current IFC file. Skipping.")
                    continue

                ifcopenshell.api.run("sequence.edit_task", ifc_file, task=task, attributes={"PredefinedType": task_config.get("predefined_type")})

                for product in ifcopenshell.util.sequence.get_task_outputs(task):
                    ifcopenshell.api.run("sequence.unassign_product", ifc_file, relating_product=product, related_object=task)
                for product_input in ifcopenshell.util.sequence.get_task_inputs(task):
                    ifcopenshell.api.run("sequence.unassign_process", ifc_file, relating_process=task, related_object=product_input)
                for resource in ifcopenshell.util.sequence.get_task_resources(task):
                    ifcopenshell.api.run("sequence.unassign_process", ifc_file, relating_process=task, related_object=resource)

                input_ids = [guid_map[guid] for guid in task_config.get("inputs", []) if guid in guid_map]
                output_ids = [guid_map[guid] for guid in task_config.get("outputs", []) if guid in guid_map]
                resource_ids = [guid_map[guid] for guid in task_config.get("resources", []) if guid in guid_map]

                if input_ids: ifcopenshell.api.run("sequence.assign_process", ifc_file, relating_process=task, products=[ifc_file.by_id(i) for i in input_ids])
                if output_ids:
                    for product_id in output_ids: ifcopenshell.api.run("sequence.assign_product", ifc_file, relating_product=ifc_file.by_id(product_id), related_object=task)
                if resource_ids: ifcopenshell.api.run("sequence.assign_process", ifc_file, relating_process=task, resources=[ifc_file.by_id(i) for i in resource_ids])
                
                if "ColorType_assignments" in task_config:
                    # Translate from the JSON file structure to the internal snapshot format
                    # that restore_all_ui_state() expects.
                    pa = task_config["ColorType_assignments"]
                    groups_to_restore = []
                    for choice in pa.get("choices", []):
                        groups_to_restore.append({
                            "group_name": choice.get("group_name"),
                            "enabled": choice.get("enabled"),
                            "selected_value": choice.get("selected_ColorType"), # Map key
                        })
                    translated_pa = {
                        "active": pa.get("use_active_ColorType_group"), # Map key
                        "selected_active_ColorType": pa.get("selected_ColorType_in_active_group"), # Map key
                        "animation_color_schemes": pa.get("animation_color_schemes", ""), # MISSING: Main ColorType field
                        "groups": groups_to_restore # Map key
                    }
                    ColorType_assignments_to_restore[str(task.id())] = translated_pa

        # 2. Store the ColorType data in a temporary property.
        # The restore_all_ui_state function (called by the operator) will use this
        # to apply the ColorType data after the UI has been reloaded.
        if ColorType_assignments_to_restore:
            # --- CORRECCIÓN: Usar la clave específica del cronograma para el snapshot ---
            snap_key_specific = f"_task_colortype_snapshot_json_WS_{work_schedule.id()}"
            bpy.context.scene[snap_key_specific] = json.dumps(ColorType_assignments_to_restore)
            print(f"Bonsai INFO: Stored {len(ColorType_assignments_to_restore)} ColorType assignments for restore under key {snap_key_specific}")


    @classmethod
    def _debug_copy3d_state(cls, stage, schedule_name="", task_count=0):
        """
        DEBUG: Internal testing function to verify Copy3D state at different stages
        """
        print(f"\n🔍 COPY3D DEBUG [{stage}] - Schedule: {schedule_name}, Tasks: {task_count}")
        
        try:
            tprops = cls.get_task_tree_props()
            if not tprops or not hasattr(tprops, 'tasks'):
                print("❌ No task properties available")
                return
                
            # Sample first 3 tasks for detailed inspection
            sample_tasks = list(tprops.tasks)[:3] if hasattr(tprops, 'tasks') else []
            
            for i, task in enumerate(sample_tasks):
                tid = getattr(task, 'ifc_definition_id', '?')
                name = getattr(task, 'name', 'Unnamed')[:30]
                
                # Core properties
                use_active = getattr(task, 'use_active_colortype_group', False)
                colortype_groups = getattr(task, 'ColorType_groups', '')
                animation_schemes = getattr(task, 'animation_color_schemes', '')
                selected_active = getattr(task, 'selected_colortype_in_active_group', '')
                
                # Group choices
                group_choices = getattr(task, 'colortype_group_choices', [])
                group_info = []
                for choice in group_choices:
                    enabled = getattr(choice, 'enabled', False)
                    group_name = getattr(choice, 'group_name', '')
                    selected_colortype = getattr(choice, 'selected_colortype', '')
                    group_info.append(f"{group_name}:{selected_colortype}({enabled})")
                
                print(f"  Task {tid} ({name}):")
                print(f"    use_active: {use_active}")
                print(f"    ColorType_groups: '{colortype_groups}'")
                print(f"    animation_color_schemes: '{animation_schemes}'")
                print(f"    selected_active: '{selected_active}'")
                print(f"    groups: [{', '.join(group_info)}]")
                
        except Exception as e:
            print(f"❌ Debug state error: {e}")
        
        print(f"🔍 END COPY3D DEBUG [{stage}]\n")

    @classmethod
    def _test_copy3d_results(cls, copied_schedules, total_matches):
        """
        TEST: Comprehensive verification of Copy3D results
        """
        print(f"\n🧪 COPY3D RESULT TEST: Verifying {copied_schedules} schedules with {total_matches} matches")
        
        try:
            # Test 1: Check if active schedule has proper ColorType data
            tprops = cls.get_task_tree_props()
            if not tprops or not hasattr(tprops, 'tasks'):
                print("❌ TEST FAIL: No task properties available for verification")
                return False
            
            test_results = {
                "tasks_with_active_groups": 0,
                "tasks_with_animation_schemes": 0,
                "tasks_with_group_choices": 0,
                "tasks_with_empty_configs": 0,
                "total_tested": 0
            }
            
            # Sample testing on first 5 tasks
            sample_tasks = list(tprops.tasks)[:5] if hasattr(tprops, 'tasks') else []
            
            for task in sample_tasks:
                test_results["total_tested"] += 1
                tid = getattr(task, 'ifc_definition_id', '?')
                name = getattr(task, 'name', 'Unnamed')[:20]
                
                # Test properties
                use_active = getattr(task, 'use_active_colortype_group', False)
                animation_schemes = getattr(task, 'animation_color_schemes', '')
                group_choices = list(getattr(task, 'colortype_group_choices', []))
                
                # Count configurations
                if use_active:
                    test_results["tasks_with_active_groups"] += 1
                if animation_schemes:
                    test_results["tasks_with_animation_schemes"] += 1
                if group_choices:
                    test_results["tasks_with_group_choices"] += 1
                if not use_active and not animation_schemes and not group_choices:
                    test_results["tasks_with_empty_configs"] += 1
                
                # Detailed result for this task
                status = "✅" if (use_active or animation_schemes or group_choices) else "❌"
                print(f"  {status} Task {tid} ({name}): active={use_active}, schemes='{animation_schemes}', groups={len(group_choices)}")
            
            # Summary
            print(f"\n🧪 TEST SUMMARY:")
            print(f"  Total tested: {test_results['total_tested']}")
            print(f"  With active groups: {test_results['tasks_with_active_groups']}")
            print(f"  With animation schemes: {test_results['tasks_with_animation_schemes']}")
            print(f"  With group choices: {test_results['tasks_with_group_choices']}")
            print(f"  Completely empty: {test_results['tasks_with_empty_configs']}")
            
            # Test outcome
            configured_tasks = (test_results['tasks_with_active_groups'] + 
                              test_results['tasks_with_animation_schemes'] + 
                              test_results['tasks_with_group_choices'])
            
            if configured_tasks > 0:
                success_rate = (configured_tasks / test_results['total_tested']) * 100
                print(f"✅ COPY3D TEST RESULT: {success_rate:.1f}% tasks have ColorType configurations")
                return success_rate > 50  # At least half should be configured
            else:
                print(f"❌ COPY3D TEST RESULT: NO tasks have ColorType configurations - Copy3D failed!")
                return False
                
        except Exception as e:
            print(f"❌ COPY3D TEST ERROR: {e}")
            return False

    @classmethod
    def copy_3d_configuration(cls, source_schedule):
        """
        Copy configuration from source schedule to all other schedules with matching task indicators.
        Returns a dict with success status and copy statistics.
        """
        print(f"\n🚀 COPY3D TEST: Starting comprehensive Copy3D testing")
        cls._debug_copy3d_state("BEFORE_COPY3D_START", source_schedule.Name if source_schedule else "?", 0)
        
        try:
            print(f"🚀 Copy3D: Starting copy from schedule '{source_schedule.Name}' (ID: {source_schedule.id()})")
            
            ifc_file = tool.Ifc.get()
            if not ifc_file:
                return {"success": False, "error": "No IFC file loaded"}

            # Get source schedule configuration
            print("📤 Copy3D: Capturing source schedule configuration...")
            cls._debug_copy3d_state("BEFORE_FORCE_SNAPSHOT", source_schedule.Name, 0)
            
            # FORZAR captura completa de TODAS las tareas del cronograma, no solo las visibles
            cls._force_complete_task_snapshot(bpy.context, source_schedule)
            cls._debug_copy3d_state("AFTER_FORCE_SNAPSHOT", source_schedule.Name, 0)
            
            # SINCRONIZAR animation_color_schemes en tareas activas ANTES del snapshot
            cls._sync_source_animation_color_schemes(bpy.context)
            cls._debug_copy3d_state("AFTER_SYNC_SOURCE", source_schedule.Name, 0)
            
            # FORZAR snapshot FRESCO basado en el estado UI actual (no datos antiguos)
            print("🔄 Copy3D: Forcing fresh snapshot from current UI state...")
            cls._force_fresh_snapshot_from_ui(bpy.context)
            
            snapshot_all_ui_state(bpy.context)
            cls._debug_copy3d_state("AFTER_SNAPSHOT_UI", source_schedule.Name, 0)
            
            try:
                config_data = cls.export_schedule_configuration(source_schedule)
                print(f"📊 COPY3D TEST: Exported config has {len(config_data.get('task_configurations', []))} task configurations")
            finally:
                restore_all_ui_state(bpy.context)
                cls._debug_copy3d_state("AFTER_RESTORE_UI", source_schedule.Name, 0)
            
            print(f"📊 Copy3D: Exported {len(config_data.get('task_configurations', []))} task configurations")

            if not config_data or not config_data.get("task_configurations"):
                return {"success": False, "error": "No configuration data to copy"}

            # Get all work schedules except the source
            all_schedules = [ws for ws in ifc_file.by_type("IfcWorkSchedule") 
                           if ws.id() != source_schedule.id()]
            
            print(f"🎯 Copy3D: Found {len(all_schedules)} target schedules to copy to:")
            for ws in all_schedules:
                print(f"  - '{ws.Name}' (ID: {ws.id()})")
            
            if not all_schedules:
                return {"success": False, "error": "No other schedules found to copy to"}

            copied_schedules = 0
            total_task_matches = 0

            # For each target schedule, find matching tasks and copy configuration
            for target_schedule in all_schedules:
                print(f"📋 Copy3D: Processing target schedule '{target_schedule.Name}' (ID: {target_schedule.id()})")
                
                # Switch to target schedule for UI state  
                ws_props = cls.get_work_schedule_props()
                if ws_props:
                    ws_props.active_work_schedule_id = target_schedule.id()
                
                cls._debug_copy3d_state("BEFORE_TARGET_PROCESSING", target_schedule.Name, 0)
                target_task_map = {}
                
                # Build map of task identifications for target schedule
                def get_all_tasks_recursive(tasks):
                    all_tasks_list = []
                    for task in tasks:
                        all_tasks_list.append(task)
                        nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                        if nested_tasks:
                            all_tasks_list.extend(get_all_tasks_recursive(nested_tasks))
                    return all_tasks_list

                root_tasks = ifcopenshell.util.sequence.get_root_tasks(target_schedule)
                all_target_tasks = get_all_tasks_recursive(root_tasks)
                
                for task in all_target_tasks:
                    identification = getattr(task, "Identification", None)
                    if identification:
                        target_task_map[identification] = task

                print(f"📋 Copy3D: Target schedule has {len(target_task_map)} tasks with identifications")
                
                if not target_task_map:
                    print("⚠️ Copy3D: No tasks with identifications in target schedule, skipping")
                    continue

                # Copy matching configurations
                schedule_matches = 0
                matched_identifications = []
                
                for task_config in config_data["task_configurations"]:
                    task_identification = task_config.get("task_identification")
                    if not task_identification:
                        continue

                    target_task = target_task_map.get(task_identification)
                    if not target_task:
                        continue
                    
                    matched_identifications.append(task_identification)
                    print(f"✅ Copy3D: Found matching task '{task_identification}' -> ID {target_task.id()}")

                    # Copy PredefinedType
                    predefined_type = task_config.get("predefined_type")
                    if predefined_type is not None:
                        ifcopenshell.api.run("sequence.edit_task", ifc_file, 
                                           task=target_task, 
                                           attributes={"PredefinedType": predefined_type})

                    # Copy ICOM data
                    guid_map = {p.GlobalId: p for p in ifc_file.by_type("IfcProduct") if hasattr(p, 'GlobalId')}
                    guid_map.update({r.GlobalId: r for r in ifc_file.by_type("IfcResource") if hasattr(r, 'GlobalId')})

                    # Clear existing assignments
                    for product in ifcopenshell.util.sequence.get_task_outputs(target_task):
                        ifcopenshell.api.run("sequence.unassign_product", ifc_file, 
                                           relating_product=product, related_object=target_task)
                    for product_input in ifcopenshell.util.sequence.get_task_inputs(target_task):
                        ifcopenshell.api.run("sequence.unassign_process", ifc_file, 
                                           relating_process=target_task, related_object=product_input)
                    for resource in ifcopenshell.util.sequence.get_task_resources(target_task):
                        ifcopenshell.api.run("sequence.unassign_process", ifc_file, 
                                           relating_process=target_task, related_object=resource)

                    # Assign new inputs, outputs, resources
                    inputs = [guid_map[guid] for guid in task_config.get("inputs", []) if guid in guid_map]
                    outputs = [guid_map[guid] for guid in task_config.get("outputs", []) if guid in guid_map]
                    resources = [guid_map[guid] for guid in task_config.get("resources", []) if guid in guid_map]

                    if inputs:
                        ifcopenshell.api.run("sequence.assign_process", ifc_file, 
                                           relating_process=target_task, products=inputs)
                    if outputs:
                        for product in outputs:
                            ifcopenshell.api.run("sequence.assign_product", ifc_file, 
                                               relating_product=product, related_object=target_task)
                    if resources:
                        ifcopenshell.api.run("sequence.assign_process", ifc_file, 
                                           relating_process=target_task, resources=resources)

                    schedule_matches += 1

                print(f"📊 Copy3D: Completed target schedule - {schedule_matches} task matches")
                print(f"  Matched tasks: {', '.join(matched_identifications) if matched_identifications else 'None'}")
                
                if schedule_matches > 0:
                    copied_schedules += 1
                    total_task_matches += schedule_matches

            # Copy ColorType groups library
            if config_data.get("ColorType_groups"):
                from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                UnifiedColorTypeManager._write_sets_json(bpy.context, config_data["ColorType_groups"])

            # Copy UI settings
            if config_data.get("ui_settings"):
                anim_props = cls.get_animation_props()
                anim_props.task_ColorType_group_selector = config_data["ui_settings"].get("task_ColorType_group_selector", "")
                
                # Copy animation group stack
                if "animation_group_stack" in config_data["ui_settings"]:
                    anim_props.animation_group_stack.clear()
                    for item_data in config_data["ui_settings"]["animation_group_stack"]:
                        item = anim_props.animation_group_stack.add()
                        item.group = item_data.get("group", "")
                        if hasattr(item, "enabled"):
                            item.enabled = bool(item_data.get("enabled", False))
                    print(f"📋 Copy3D: Copied {len(config_data['ui_settings']['animation_group_stack'])} animation group stack items")

            # Copy ColorType assignments to all target schedules
            print("👥 Copy3D: Starting ColorType assignments copy...")
            if config_data.get("task_configurations"):
                ColorType_assignments_data = {}
                
                # Extract ColorType assignments from source config
                print("📤 Copy3D: Extracting ColorType assignments from source...")
                for task_config in config_data["task_configurations"]:
                    if "ColorType_assignments" in task_config:
                        task_identification = task_config.get("task_identification")
                        if task_identification:
                            # Convert from export format to internal snapshot format
                            pa = task_config["ColorType_assignments"]
                            groups_data = []
                            for choice in pa.get("choices", []):
                                # Clean and validate ColorType values
                                group_name = choice.get("group_name", "")
                                enabled = bool(choice.get("enabled", False))
                                selected_ColorType = choice.get("selected_ColorType", "")
                                
                                # Add all groups (even if not configured)
                                if group_name:
                                    groups_data.append({
                                        "group_name": group_name,
                                        "enabled": enabled,
                                        "selected_value": selected_ColorType if selected_ColorType else "",
                                    })
                            
                            # Always store ColorType assignments (even if empty/unconfigured)
                            selected_active_ColorType = pa.get("selected_ColorType_in_active_group", "")
                            
                            # LIMPIEZA CONSERVADORA: Solo limpiar valores claramente inválidos
                            if selected_active_ColorType in [None, "0", 0, "None"]:
                                selected_active_ColorType = ""
                            # Nota: NO limpiamos strings vacíos "" porque podrían ser valores válidos
                            
                            ColorType_assignments_data[task_identification] = {
                                "active": bool(pa.get("use_active_ColorType_group", False)),
                                "selected_active_ColorType": selected_active_ColorType,
                                "animation_color_schemes": pa.get("animation_color_schemes", ""),
                                "groups": groups_data  # Can be empty for unconfigured tasks
                            }
                            
                            # DEBUG: Show extracted data
                            print(f"📤 Copy3D EXTRACT DEBUG: Task '{task_identification}'")
                            print(f"    Source Active: {pa.get('use_active_ColorType_group', False)}")
                            print(f"    Source Selected Active: '{pa.get('selected_ColorType_in_active_group', '')}'")
                            print(f"    Source Animation Color Schemes: '{pa.get('animation_color_schemes', '')}'")
                            print(f"    Source Groups: {len(pa.get('choices', []))} choices")
                            
                            if groups_data:
                                print(f"📝 Copy3D: Extracted ColorTypes for task '{task_identification}': {len(groups_data)} groups")
                            else:
                                print(f"📝 Copy3D: Task '{task_identification}' has no configured ColorTypes (will copy empty structure)")
                
                print(f"📋 Copy3D: Total ColorType assignments extracted: {len(ColorType_assignments_data)} tasks")

                # Apply ColorType assignments to each target schedule that had task matches
                for target_schedule in all_schedules:
                    target_task_map = {}
                    
                    # Build task identification map for this target schedule
                    def get_all_tasks_recursive_target(tasks):
                        all_tasks_list = []
                        for task in tasks:
                            all_tasks_list.append(task)
                            nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                            if nested_tasks:
                                all_tasks_list.extend(get_all_tasks_recursive_target(nested_tasks))
                        return all_tasks_list

                    root_tasks = ifcopenshell.util.sequence.get_root_tasks(target_schedule)
                    all_target_tasks = get_all_tasks_recursive_target(root_tasks)
                    
                    for task in all_target_tasks:
                        identification = getattr(task, "Identification", None)
                        if identification:
                            target_task_map[identification] = task

                    if not target_task_map:
                        continue

                    # Check if this schedule has matching tasks
                    has_matches = any(task_id in target_task_map for task_id in ColorType_assignments_data.keys())
                    
                    if has_matches:
                        # Get available ColorType groups to validate against
                        available_groups = {}
                        try:
                            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                            available_groups = UnifiedColorTypeManager._read_sets_json(bpy.context) or {}
                        except Exception as e:
                            print(f"Warning: Could not load ColorType groups for validation: {e}")
                        
                        # Create ColorType assignments for matching tasks only
                        target_ColorType_assignments = {}
                        for task_identification, ColorType_data in ColorType_assignments_data.items():
                            if task_identification in target_task_map:
                                target_task = target_task_map[task_identification]
                                
                                # Validate and clean ColorType data
                                validated_groups = []
                                for group_data in ColorType_data.get("groups", []):
                                    group_name = group_data.get("group_name", "")
                                    selected_ColorType = group_data.get("selected_value", "")
                                    
                                    # Check if group exists in available groups
                                    if group_name in available_groups:
                                        group_ColorTypes = available_groups[group_name].get("ColorTypes", [])
                                        ColorType_names = [p.get("name", "") for p in group_ColorTypes]
                                        
                                        # Validate selected ColorType exists in group - pero ser conservador
                                        if selected_ColorType and selected_ColorType not in ColorType_names:
                                            # If ColorType doesn't exist, warn but keep it (could be user defined)
                                            print(f"Warning: ColorType '{selected_ColorType}' not found in group '{group_name}', keeping anyway")
                                            # selected_ColorType = ""  # Comentado para ser menos agresivo
                                        
                                        validated_groups.append({
                                            "group_name": group_name,
                                            "enabled": group_data.get("enabled", False),
                                            "selected_value": selected_ColorType,
                                        })
                                    else:
                                        # Group doesn't exist, skip it
                                        print(f"Warning: ColorType group '{group_name}' not found, skipping for task '{task_identification}'")
                                
                                # Always store ColorType assignments (even if empty for unconfigured tasks)
                                # Also validate selected_active_ColorType against available ColorTypes
                                selected_active_ColorType = ColorType_data.get("selected_active_ColorType", "")
                                # Clean only clearly problematic values
                                if selected_active_ColorType in [None, "0", 0, "None"]:
                                    selected_active_ColorType = ""
                                # Nota: NO limpiamos strings vacíos porque pueden ser válidos
                                
                                # Additional validation: ensure selected_active_ColorType exists in available groups
                                if selected_active_ColorType and available_groups:
                                    # Check if the selected ColorType exists in any group
                                    ColorType_exists = False
                                    for group_name, group_data in available_groups.items():
                                        group_ColorTypes = group_data.get("ColorTypes", [])
                                        ColorType_names = [p.get("name", "") for p in group_ColorTypes]
                                        if selected_active_ColorType in ColorType_names:
                                            ColorType_exists = True
                                            break
                                    
                                    if not ColorType_exists:
                                        print(f"Warning: Selected active ColorType '{selected_active_ColorType}' not found in any group, keeping anyway for task '{task_identification}'")
                                        # selected_active_ColorType = ""  # Comentado para ser menos agresivo
                                
                                target_ColorType_assignments[str(target_task.id())] = {
                                    "active": ColorType_data.get("active", False),
                                    "selected_active_ColorType": selected_active_ColorType,
                                    "animation_color_schemes": ColorType_data.get("animation_color_schemes", ""),
                                    "groups": validated_groups  # Can be empty for unconfigured tasks
                                }
                                
                                # DEBUG: Show exactly what data is being stored
                                print(f"🔍 Copy3D DEBUG: Task '{task_identification}' (ID: {target_task.id()})")
                                print(f"    Active: {ColorType_data.get('active', False)}")
                                print(f"    Selected Active ColorType: '{selected_active_ColorType}'")
                                print(f"    Animation Color Schemes: '{ColorType_data.get('animation_color_schemes', '')}'")
                                print(f"    Groups: {len(validated_groups)} groups")
                                
                                if validated_groups:
                                    print(f"👤 Copy3D: Copied {len(validated_groups)} ColorType groups for task '{task_identification}'")
                                else:
                                    print(f"👤 Copy3D: Copied empty ColorType structure for unconfigured task '{task_identification}'")

                        # Store ColorType assignments for this target schedule
                        if target_ColorType_assignments:
                            target_snap_key = f"_task_colortype_snapshot_json_WS_{target_schedule.id()}"
                            bpy.context.scene[target_snap_key] = json.dumps(target_ColorType_assignments)
                            
                            # Also update the persistent cache to maintain ColorType data when switching schedules
                            cache_key = "_task_colortype_snapshot_cache_json"
                            cache_raw = bpy.context.scene.get(cache_key, "{}")
                            try:
                                cache_data = json.loads(cache_raw) if cache_raw else {}
                            except:
                                cache_data = {}
                            
                            # Merge target ColorType assignments into cache
                            cache_data.update(target_ColorType_assignments)
                            bpy.context.scene[cache_key] = json.dumps(cache_data)
                            
                            print(f"Bonsai INFO: Stored {len(target_ColorType_assignments)} ColorType assignments for schedule '{target_schedule.Name}' (ID: {target_schedule.id()})")
                            
                            # Debug: Show what ColorType assignments were copied
                            for task_id, ColorType_data in target_ColorType_assignments.items():
                                groups_info = ", ".join([f"{g['group_name']}:{g['selected_value']}" for g in ColorType_data.get('groups', [])])
                                print(f"  📋 Copy3D: Task {task_id}: active={ColorType_data.get('active')}, selected_active='{ColorType_data.get('selected_active_ColorType')}', groups=[{groups_info}]")
                            
                            # VERIFICACIÓN CRÍTICA: Comprobar que los datos se guardaron correctamente
                            verification_data = bpy.context.scene.get(target_snap_key)
                            if verification_data:
                                try:
                                    parsed_data = json.loads(verification_data)
                                    print(f"✅ Copy3D: VERIFICACIÓN - {len(parsed_data)} asignaciones guardadas correctamente en {target_snap_key}")
                                except Exception as e:
                                    print(f"❌ Copy3D: VERIFICACIÓN ERROR - No se pudo parsear datos guardados: {e}")
                            else:
                                print(f"❌ Copy3D: VERIFICACIÓN ERROR - No se encontraron datos en {target_snap_key}")
                            
                            
                            # Extra debug: Show what task IDs we're storing vs task names
                            print(f"🔍 Copy3D: ColorType snapshot keys being stored:")
                            try:
                                for task_identification, target_task in target_task_map.items():
                                    if task_identification in ColorType_assignments_data:
                                        print(f"  Task identification '{task_identification}' -> Task ID {target_task.id()} (Name: {target_task.Name})")
                            except Exception as e:
                                print(f"  Error in debug mapping: {e}")

            # FINAL VERIFICATION TEST: Check current UI state after Copy3D
            print(f"\n🔍 COPY3D FINAL VERIFICATION TEST")
            
            # CRÍTICO: Forzar reload completo de la UI desde el cronograma destino
            # para verificar que los datos se copiaron correctamente
            print("🔄 Copy3D: Forcing complete UI reload from destination schedule data...")
            restore_all_ui_state(bpy.context)
            
            # Forzar refresh completo de la UI y re-trigger de todas las funciones de update
            print("🔄 Copy3D: Forcing complete UI refresh...")
            for area in bpy.context.screen.areas:
                area.tag_redraw()
            
            # CRÍTICO: Verificar estado de task_colortype_group_selector después de Copy3D
            print("🔍 Copy3D: Checking task_colortype_group_selector state...")
            try:
                anim_props = tool.Sequence.get_animation_props()
                current_group = getattr(anim_props, "task_colortype_group_selector", "")
                print(f"🔍 Current task_colortype_group_selector: '{current_group}'")
                
                if not current_group or current_group == "DEFAULT":
                    print("⚠️ PROBLEM: task_colortype_group_selector is empty or DEFAULT - dropdown will be empty!")
                    
                    # Try to find and set a valid group from copied data
                    from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                    all_sets = UnifiedColorTypeManager._read_sets_json(bpy.context)
                    available_groups = [k for k in all_sets.keys() if k != "DEFAULT"]
                    if available_groups:
                        first_group = available_groups[0]
                        anim_props.task_colortype_group_selector = first_group
                        print(f"🔄 Auto-set task_colortype_group_selector to: '{first_group}'")
                else:
                    print(f"✅ task_colortype_group_selector is set to valid group: '{current_group}'")
                    
                # Verify ColorType data exists for the selected group
                from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
                all_sets = UnifiedColorTypeManager._read_sets_json(bpy.context)
                if current_group in all_sets:
                    group_data = all_sets[current_group]
                    colortypes_list = group_data.get("ColorTypes", [])
                    colortype_names = [ct.get("name", "") for ct in colortypes_list if isinstance(ct, dict)]
                    print(f"🔍 Available ColorTypes in '{current_group}': {colortype_names}")
                    
                    if not colortype_names:
                        print("⚠️ PROBLEM: No ColorTypes found in selected group - data may not have been copied properly!")
                else:
                    print(f"⚠️ PROBLEM: Group '{current_group}' not found in ColorType data!")
                    
            except Exception as e:
                print(f"⚠️ Error checking task_colortype_group_selector: {e}")
            
            # CRÍTICO: Forzar refresh de EnumProperty items functions después de Copy3D
            print("🔄 Copy3D: Forcing EnumProperty items refresh...")
            try:
                tprops = tool.Blender.get_active_tasks_props(bpy.context)
                if tprops and tprops.tasks:
                    for task in tprops.tasks:
                        if hasattr(task, 'selected_colortype_in_active_group'):
                            # Trigger items function refresh by accessing and reassigning the property
                            current_val = task.selected_colortype_in_active_group
                            # Force items function re-evaluation
                            task.property_unset("selected_colortype_in_active_group")
                            task.selected_colortype_in_active_group = current_val
                            print(f"🔄 Refreshed dropdown items for task {getattr(task, 'ifc_definition_id', 'unknown')}")
            except Exception as e:
                print(f"⚠️ Error refreshing EnumProperty items: {e}")
            
            # Forzar snapshot fresco después de la restauración para asegurar consistencia
            snapshot_all_ui_state(bpy.context)
            
            cls._debug_copy3d_state("AFTER_COPY3D_COMPLETE", "Current_Active", copied_schedules)
            
            # Test verification function
            cls._test_copy3d_results(copied_schedules, total_task_matches)
            
            return {
                "success": True,
                "copied_schedules": copied_schedules,
                "task_matches": total_task_matches
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def sync_3d_elements(cls, work_schedule, property_set_name):
        """
        Sync IFC elements to tasks based on property set values matching task indicators.
        Returns a dict with success status and sync statistics.
        """
        try:
            ifc_file = tool.Ifc.get()
            if not ifc_file:
                return {"success": False, "error": "No IFC file loaded"}

            # Get all tasks from the schedule
            def get_all_tasks_recursive(tasks):
                all_tasks_list = []
                for task in tasks:
                    all_tasks_list.append(task)
                    nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested_tasks:
                        all_tasks_list.extend(get_all_tasks_recursive(nested_tasks))
                return all_tasks_list

            root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
            all_tasks = get_all_tasks_recursive(root_tasks)
            
            if not all_tasks:
                return {"success": False, "error": "No tasks found in schedule"}

            # Build task indicator map
            task_indicators = {}
            for task in all_tasks:
                identification = getattr(task, "Identification", None)
                if identification:
                    task_indicators[identification] = task

            print(f"🎯 Sync3D: Encontradas {len(task_indicators)} tareas con identificación:")
            for identification, task in list(task_indicators.items())[:5]:  # Show first 5
                print(f"  📋 Task ID {task.id()}: '{identification}'")

            if not task_indicators:
                return {"success": False, "error": "No task identifications found"}

            # Get all IFC elements with the specified property set
            matched_elements = 0
            processed_tasks = 0
            elements_checked = 0
            elements_with_pset = 0

            print(f"🔍 Sync3D: Buscando property set '{property_set_name}' en elementos IFC...")

            for element in ifc_file.by_type("IfcProduct"):
                if not hasattr(element, 'GlobalId'):
                    continue
                
                elements_checked += 1

                # Look for the property set
                property_set = None
                if hasattr(element, 'IsDefinedBy') and element.IsDefinedBy:
                    for rel in element.IsDefinedBy:
                        if hasattr(rel, 'RelatingPropertyDefinition'):
                            prop_def = rel.RelatingPropertyDefinition
                            if hasattr(prop_def, 'Name') and prop_def.Name == property_set_name:
                                property_set = prop_def
                                elements_with_pset += 1
                                if elements_with_pset <= 3:  # Log first 3
                                    element_type = getattr(element, 'is_a', lambda: 'Unknown')()
                                    print(f"  ✅ Sync3D: Elemento {element_type} (ID: {element.id()}) tiene property set '{property_set_name}'")
                                break

                if not property_set:
                    continue

                # Get property value that matches a task indicator
                if hasattr(property_set, 'HasProperties'):
                    for prop in property_set.HasProperties:
                        if hasattr(prop, 'NominalValue') and hasattr(prop.NominalValue, 'wrappedValue'):
                            prop_value = str(prop.NominalValue.wrappedValue)
                            prop_name = getattr(prop, 'Name', 'Unknown')
                            
                            if matched_elements < 3:  # Log first few mappings
                                print(f"  🔗 Sync3D: Property '{prop_name}' = '{prop_value}' en elemento {element.id()}")
                            
                            # Find matching task
                            matching_task = task_indicators.get(prop_value)
                            if matching_task:
                                element_type = getattr(element, 'is_a', lambda: 'Unknown')()
                                print(f"  ✅ Sync3D: MATCH! Asignando {element_type} (ID: {element.id()}) → Task '{prop_value}' (ID: {matching_task.id()})")
                                
                                # Assign element to task as output
                                try:
                                    ifcopenshell.api.run("sequence.assign_product", ifc_file,
                                                       relating_product=element, 
                                                       related_object=matching_task)
                                    matched_elements += 1
                                    print(f"  🎯 Sync3D: Asignación exitosa #{matched_elements}")
                                except Exception as e:
                                    print(f"  ❌ Sync3D: Error asignando elemento: {e}")
                                break
                            else:
                                if matched_elements < 5:  # Log first few no-matches
                                    print(f"  ⚠️ Sync3D: No se encontró tarea para valor '{prop_value}'")

            # Count processed tasks
            for task in task_indicators.values():
                outputs = ifcopenshell.util.sequence.get_task_outputs(task, is_deep=False)
                if outputs:
                    processed_tasks += 1

            print(f"📊 Sync3D: RESUMEN:")
            print(f"  - Elementos revisados: {elements_checked}")
            print(f"  - Elementos con property set '{property_set_name}': {elements_with_pset}")
            print(f"  - Elementos asignados a tareas: {matched_elements}")
            print(f"  - Tareas con elementos asignados: {processed_tasks}")

            # CRÍTICO: Limpiar datos de perfiles corruptos antes del retorno
            # Esto asegura que cuando restore_all_ui_state() se ejecute, 
            # no restaure valores '0' problemáticos
            print(f"🧹 Sync3D: Limpiando datos de perfiles corruptos en cronograma")
            cls._clean_and_update_ColorType_snapshot_for_schedule(work_schedule)
            
            return {
                "success": True,
                "matched_elements": matched_elements,
                "processed_tasks": processed_tasks
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def _clean_and_update_ColorType_snapshot_for_schedule(cls, work_schedule):
        """
        Limpia específicamente los datos de perfiles corruptos del cronograma dado
        y actualiza el snapshot para evitar restaurar valores '0' problemáticos.
        """
        try:
            import json
            
            # Obtener la clave específica del cronograma
            ws_id = work_schedule.id()
            snapshot_key_specific = f"_task_colortype_snapshot_json_WS_{ws_id}"
            
            # Leer datos actuales del snapshot
            snapshot_raw = bpy.context.scene.get(snapshot_key_specific)
            if not snapshot_raw:
                print(f"🧹 Sync3D: No hay snapshot para limpiar en cronograma {ws_id}")
                return
            
            try:
                snapshot_data = json.loads(snapshot_raw)
                print(f"🧹 Sync3D: Limpiando {len(snapshot_data)} tareas en snapshot")
            except Exception as e:
                print(f"❌ Sync3D: Error parseando snapshot: {e}")
                return
            
            # Limpiar datos usando la función existente
            cleaned_data = cls._clean_ColorType_snapshot_data(snapshot_data)
            
            # Actualizar el snapshot con datos limpios
            bpy.context.scene[snapshot_key_specific] = json.dumps(cleaned_data)
            print(f"✅ Sync3D: Datos de perfiles limpiados en cronograma {ws_id}")
            
        except Exception as e:
            print(f"❌ Sync3D: Error en limpieza de perfiles: {e}")

    @classmethod
    def _clean_ColorType_snapshot_data(cls, snapshot_data):
        """
        Clean ColorType snapshot data by removing invalid enum values and ensuring data consistency.
        """
        if not isinstance(snapshot_data, dict):
            return {}
        
        cleaned_data = {}
        for task_id, task_data in snapshot_data.items():
            if not isinstance(task_data, dict):
                continue
                
            cleaned_task_data = {
                "active": bool(task_data.get("active", False)),
                "selected_active_ColorType": "",  # Always reset problematic values
                "groups": []
            }
            
            # Clean selected_active_ColorType - remove '0' and other invalid values
            selected_active = task_data.get("selected_active_ColorType", "")
            # Be more aggressive in cleaning problematic values
            problematic_values = ["0", 0, None, "", "None", "null", "undefined"]
            if selected_active and selected_active not in problematic_values:
                # Additional check: ensure it's a meaningful string
                selected_active_str = str(selected_active).strip()
                if selected_active_str and selected_active_str not in [str(v) for v in problematic_values]:
                    cleaned_task_data["selected_active_ColorType"] = selected_active_str
            
            # Clean groups data
            for group_data in task_data.get("groups", []):
                if isinstance(group_data, dict) and group_data.get("group_name"):
                    selected_value = group_data.get("selected_value", "")
                    # Clean selected_value - remove '0' and other invalid values
                    problematic_group_values = ["0", 0, None, "", "None", "null", "undefined"]
                    if selected_value in problematic_group_values:
                        selected_value = ""
                    else:
                        # Ensure it's a clean string
                        selected_value = str(selected_value).strip() if selected_value else ""
                        if selected_value in [str(v) for v in problematic_group_values]:
                            selected_value = ""
                    
                    cleaned_group = {
                        "group_name": str(group_data["group_name"]),
                        "enabled": bool(group_data.get("enabled", False)),
                        "selected_value": str(selected_value) if selected_value else ""
                    }
                    cleaned_task_data["groups"].append(cleaned_group)
            
            # Always store task data (even if no groups - represents unconfigured tasks)
            cleaned_data[task_id] = cleaned_task_data
        
        return cleaned_data

    # --- FIN: LÓGICA DE IMPORT/EXPORT DE CONFIGURACIÓN DE CRONOGRAMA ---

    @classmethod
    def create_tasks_json(cls, work_schedule: ifcopenshell.entity_instance) -> list[dict[str, Any]]:
        sequence_type_map = {
            None: "FS",
            "START_START": "SS",
            "START_FINISH": "SF",
            "FINISH_START": "FS",
            "FINISH_FINISH": "FF",
            "USERDEFINED": "FS",
            "NOTDEFINED": "FS",
        }
        is_baseline = False
        if work_schedule.PredefinedType == "BASELINE":
            is_baseline = True
            relating_work_schedule = work_schedule.IsDeclaredBy[0].RelatingObject
            work_schedule = relating_work_schedule
        tasks_json = []
        for task in ifcopenshell.util.sequence.get_root_tasks(work_schedule):
            if is_baseline:
                cls.create_new_task_json(task, tasks_json, sequence_type_map, baseline_schedule=work_schedule)
            else:
                cls.create_new_task_json(task, tasks_json, sequence_type_map)
        return tasks_json

    @classmethod
    def create_new_task_json(cls, task, json, type_map=None, baseline_schedule=None):
        task_time = task.TaskTime
        resources = ifcopenshell.util.sequence.get_task_resources(task, is_deep=False)

        string_resources = ""
        resources_usage = ""
        for resource in resources:
            string_resources += resource.Name + ", "
            resources_usage += str(resource.Usage.ScheduleUsage) + ", " if resource.Usage else "-, "

        schedule_start = task_time.ScheduleStart if task_time else ""
        schedule_finish = task_time.ScheduleFinish if task_time else ""

        baseline_task = None
        if baseline_schedule:
            for rel in task.Declares:
                for baseline_task in rel.RelatedObjects:
                    if baseline_schedule.id() == ifcopenshell.util.sequence.get_task_work_schedule(baseline_task).id():
                        baseline_task = task
                        break

        if baseline_task and baseline_task.TaskTime:
            compare_start = baseline_task.TaskTime.ScheduleStart
            compare_finish = baseline_task.TaskTime.ScheduleFinish
        else:
            compare_start = schedule_start
            compare_finish = schedule_finish
        task_name = task.Name or "Unnamed"
        task_name = task_name.replace("\n", "")
        data = {
            "pID": task.id(),
            "pName": task_name,
            "pCaption": task_name,
            "pStart": schedule_start,
            "pEnd": schedule_finish,
            "pPlanStart": compare_start,
            "pPlanEnd": compare_finish,
            "pMile": 1 if task.IsMilestone else 0,
            "pRes": string_resources,
            "pComp": 0,
            "pGroup": 1 if task.IsNestedBy else 0,
            "pParent": task.Nests[0].RelatingObject.id() if task.Nests else 0,
            "pOpen": 1,
            "pCost": 1,
            "ifcduration": (
                str(ifcopenshell.util.date.ifc2datetime(task_time.ScheduleDuration))
                if (task_time and task_time.ScheduleDuration)
                else ""
            ),
            "resourceUsage": resources_usage,
        }
        if task_time and task_time.IsCritical:
            data["pClass"] = "gtaskred"
        elif data["pGroup"]:
            data["pClass"] = "ggroupblack"
        elif data["pMile"]:
            data["pClass"] = "gmilestone"
        else:
            data["pClass"] = "gtaskblue"

        data["pDepend"] = ",".join(
            [f"{rel.RelatingProcess.id()}{type_map[rel.SequenceType]}" for rel in task.IsSuccessorFrom or []]
        )
        json.append(data)
        for nested_task in ifcopenshell.util.sequence.get_nested_tasks(task):
            cls.create_new_task_json(nested_task, json, type_map, baseline_schedule)

    @classmethod
    def generate_gantt_browser_chart(
        cls, task_json: list[dict[str, Any]], work_schedule: ifcopenshell.entity_instance
    ) -> None:
        if not bpy.context.scene.WebProperties.is_connected:
            bpy.ops.bim.connect_websocket_server(page="sequencing")
        gantt_data = {"tasks": task_json, "work_schedule": work_schedule.get_info(recursive=True)}
        tool.Web.send_webui_data(data=gantt_data, data_key="gantt_data", event="gantt_data")

    # === VARIANCE COLOR MODE METHODS (INDIVIDUAL TASK APPROACH) ===
    
    @classmethod
    def has_variance_calculation_in_tasks(cls):
        """
        Verifica si hay cálculo de varianza en las tareas actuales.
        Retorna True si al menos una tarea tiene variance_status calculado.
        """
        try:
            tprops = cls.get_task_tree_props()
            if not tprops or not tprops.tasks:
                return False
            
            variance_count = 0
            for task in tprops.tasks:
                variance_status = getattr(task, 'variance_status', '')
                if variance_status and variance_status.strip():
                    variance_count += 1
            
            print(f"🔍 Found {variance_count} tasks with variance calculation out of {len(tprops.tasks)} total tasks")
            return variance_count > 0
            
        except Exception as e:
            print(f"❌ Error checking variance calculation: {e}")
            return False
    
    @classmethod
    def clear_variance_colors_only(cls):
        """
        Limpia SOLO los colores 3D de varianza, SIN tocar checkboxes.
        Se usa cuando cambian filtros y no hay cálculo de varianza.
        """
        try:
            print("🧹 Clearing variance 3D colors only (keeping checkboxes)...")
            
            # Restaurar colores originales si están guardados
            if hasattr(cls, '_original_colors') and cls._original_colors:
                restored_count = 0
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                        if obj.name in cls._original_colors and hasattr(obj, 'color'):
                            try:
                                original_color = cls._original_colors[obj.name]
                                obj.color = original_color
                                restored_count += 1
                                print(f"🔄 Restored color for {obj.name}")
                            except Exception as e:
                                print(f"❌ Error restoring color for {obj.name}: {e}")
                
                print(f"✅ Restored {restored_count} objects to original colors")
                
                # Forzar actualización del viewport
                bpy.context.view_layer.update()
            else:
                print("ℹ️ No original colors to restore")
                
        except Exception as e:
            print(f"❌ Error clearing variance colors only: {e}")
            import traceback
            traceback.print_exc()

    @classmethod
    def clear_variance_color_mode(cls):
        """
        Limpia el modo de color de varianza y restaura colores originales.
        Se llama cuando se limpia varianza o cambia tipo de cronograma.
        """
        try:
            print("🧹 CLEAR_VARIANCE_COLOR_MODE: Starting cleanup process...")
            
            # Desactivar todos los checkboxes de varianza
            tprops = cls.get_task_tree_props()
            if tprops:
                cleared_checkboxes = 0
                total_tasks = len(tprops.tasks)
                print(f"🔍 Found {total_tasks} total tasks")
                
                for task in tprops.tasks:
                    if getattr(task, 'is_variance_color_selected', False):
                        task.is_variance_color_selected = False
                        cleared_checkboxes += 1
                        print(f"✅ Cleared checkbox for task {task.ifc_definition_id}")
                        
                print(f"✅ Cleared {cleared_checkboxes} variance checkboxes out of {total_tasks} tasks")
            else:
                print("❌ No task tree properties found")
            
            # COMPREHENSIVE COLOR RESTORATION
            restored_count = 0
            
            # Method 1: Try to restore from cached original colors
            if hasattr(cls, '_original_colors') and cls._original_colors:
                print(f"🔄 Attempting to restore from cached colors ({len(cls._original_colors)} stored)")
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                        if obj.name in cls._original_colors and hasattr(obj, 'color'):
                            try:
                                original_color = cls._original_colors[obj.name]
                                obj.color = original_color
                                restored_count += 1
                                print(f"✅ Restored cached color for {obj.name}")
                            except Exception as e:
                                print(f"❌ Error restoring cached color for {obj.name}: {e}")
                
                # Limpiar cache de colores originales
                cls._original_colors = {}
                print("🧹 Cleared original colors cache")
            
            # Method 2: If no cached colors or insufficient restoration, reset to default colors
            if restored_count == 0:
                print("🔄 No cached colors found, resetting all IFC objects to default gray")
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                        try:
                            # Reset to default gray color
                            obj.color = (0.8, 0.8, 0.8, 1.0)
                            obj.hide_viewport = False
                            obj.hide_render = False
                            restored_count += 1
                        except Exception as e:
                            print(f"❌ Error resetting color for {obj.name}: {e}")
            
            print(f"✅ Total objects reset: {restored_count}")
            
            # Method 3: Force complete viewport refresh
            try:
                # Clear animation data that might be affecting colors
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and obj.animation_data:
                        obj.animation_data_clear()
                
                # Force viewport update
                bpy.context.view_layer.update()
                
                # Force redraw of all 3D viewports
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.shading.color_type = 'OBJECT'  # Ensure object colors are visible
                
                print("🔄 Forced complete viewport refresh")
                
            except Exception as e:
                print(f"⚠️ Error during viewport refresh: {e}")
                
        except Exception as e:
            print(f"❌ Error clearing variance color mode: {e}")
            import traceback
            traceback.print_exc()
    @classmethod 
    def update_individual_variance_colors(cls):
        """
        Actualiza colores basado en checkboxes individuales de cada tarea.
        Cada tarea funciona independientemente.
        """
        try:
            print("🎯 Updating individual variance colors...")
            
            # Asegurar viewport correcto
            cls._ensure_viewport_shading()
            
            # Obtener tareas
            tprops = cls.get_task_tree_props()
            if not tprops:
                print("❌ No task tree properties found")
                return
            
            # Guardar colores originales la primera vez (si no están guardados)
            if not hasattr(cls, '_original_colors'):
                cls._original_colors = {}
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                        if hasattr(obj, 'color'):
                            cls._original_colors[obj.name] = tuple(obj.color)
                print(f"💾 Saved original colors for {len(cls._original_colors)} objects")
            
            # Identificar tareas con checkbox activo
            variance_selected_tasks = [t for t in tprops.tasks if getattr(t, 'is_variance_color_selected', False)]
            
            print(f"🔍 Found {len(variance_selected_tasks)} tasks with active variance checkbox")
            if variance_selected_tasks:
                for task in variance_selected_tasks:
                    print(f"  📋 Task {task.ifc_definition_id}: {task.name} (Status: {getattr(task, 'variance_status', 'No status')})")
            else:
                print("🎯 No active checkboxes → restoring original colors")
                # Restaurar colores originales de todos los objetos IFC
                mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
                restored_count = 0
                
                for obj in mesh_objects:
                    element = tool.Ifc.get_entity(obj)
                    if element and hasattr(obj, 'color'):
                        try:
                            # Usar color guardado o blanco por defecto
                            if hasattr(cls, '_original_colors') and obj.name in cls._original_colors:
                                original_color = cls._original_colors[obj.name]
                                print(f"🔄 Restoring saved color for {obj.name}: {original_color}")
                            else:
                                original_color = (1.0, 1.0, 1.0, 1.0)  # Blanco por defecto
                                print(f"🔄 Using default color for {obj.name}")
                            
                            obj.color = original_color
                            restored_count += 1
                            
                        except Exception as e:
                            print(f"❌ Error restoring color for {obj.name}: {e}")
                
                print(f"✅ Restored {restored_count} objects to original colors")
                
                # No limpiar cache aquí - mantener colores guardados para futuros usos
                
                # Forzar actualización del viewport
                bpy.context.view_layer.update()
                return
            
            # Crear mapeo de objetos a tareas
            object_to_task_map = cls._build_object_task_mapping(tprops.tasks)
            
            # Contar objetos mesh en la escena
            mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
            ifc_objects = []
            
            for obj in mesh_objects:
                element = tool.Ifc.get_entity(obj)
                if element:
                    ifc_objects.append(obj)
            
            print(f"🔍 Scene analysis: {len(mesh_objects)} mesh objects, {len(ifc_objects)} have IFC data, {len(object_to_task_map)} task mappings")
            
            # Procesar cada objeto en la escena
            processed_count = 0
            colored_count = 0
            
            for obj in mesh_objects:
                element = tool.Ifc.get_entity(obj)
                if not element:
                    print(f"⚠️ {obj.name} → No IFC element → SKIP")
                    continue
                
                processed_count += 1
                
                # Usar el nuevo método para determinar color
                color = cls._get_variance_color_for_object_real(obj, element, object_to_task_map, variance_selected_tasks)
                
                if color is None:
                    # No cambiar color (sin checkboxes activos)
                    continue
                
                # Aplicar color al objeto
                cls._apply_color_to_object_simple(obj, color)
                colored_count += 1
            
            print(f"📊 SUMMARY: Processed {processed_count} objects, {colored_count} got variance colors")
            
            # Forzar actualización del viewport
            bpy.context.view_layer.update()
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            
            print("✅ Individual variance colors updated successfully")
            
        except Exception as e:
            print(f"❌ Error updating individual variance colors: {e}")
            import traceback
            traceback.print_exc()

    # === VARIANCE COLOR MODE METHODS (INTEGRATED WITH EXISTING SYSTEM) ===
    @classmethod
    def activate_variance_color_mode(cls):
        """
        Activa el modo de color de varianza integrándose con el sistema existente de ColorTypes
        """
        try:
            print("🎨 Activating variance color mode...")
            
            # Guardar colores originales de objetos antes de cambiarlos
            cls._save_original_object_colors()
            
            # Marcar que el modo varianza está activo
            bpy.context.scene['BIM_VarianceColorModeActive'] = True
            
            # Crear un ColorType group especial para varianza
            cls._create_variance_colortype_group()
            
            # Activar el live color update system
            anim_props = cls.get_animation_props()
            anim_props.enable_live_color_updates = True
            
            # Registrar el handler si no está registrado
            cls.register_live_color_update_handler()
            
            # Trigger immediate color update
            cls._trigger_variance_color_update()
            
            print("✅ Variance color mode activated successfully")
            
        except Exception as e:
            print(f"❌ Error activating variance color mode: {e}")
            import traceback
            traceback.print_exc()
    
    @classmethod
    def _save_original_object_colors(cls):
        """Guardar los colores originales de todos los objetos"""
        try:
            original_colors = {}
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and hasattr(obj, 'color'):
                    original_colors[obj.name] = tuple(obj.color)
            
            bpy.context.scene['BIM_VarianceOriginalObjectColors'] = original_colors
            print(f"🔄 Saved original colors for {len(original_colors)} objects")
            
        except Exception as e:
            print(f"❌ Error saving original object colors: {e}")

    @classmethod
    def _restore_original_object_colors(cls):
        """Restaurar los colores originales de todos los objetos"""
        try:
            original_colors = bpy.context.scene.get('BIM_VarianceOriginalObjectColors', {})
            restored_count = 0
            
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and hasattr(obj, 'color') and obj.name in original_colors:
                    obj.color = original_colors[obj.name]
                    restored_count += 1
            
            # Limpiar los datos guardados
            if 'BIM_VarianceOriginalObjectColors' in bpy.context.scene:
                del bpy.context.scene['BIM_VarianceOriginalObjectColors']
                
            print(f"✅ Restored original colors for {restored_count} objects")
            
        except Exception as e:
            print(f"❌ Error restoring original object colors: {e}")

    @classmethod
    def deactivate_variance_color_mode(cls):
        """
        Desactiva el modo de color de varianza y restaura los colores originales
        """
        try:
            print("🔄 Deactivating variance color mode...")
            
            # Restaurar colores originales de objetos
            cls._restore_original_object_colors()
            
            # Desmarcar que el modo varianza está activo
            if 'BIM_VarianceColorModeActive' in bpy.context.scene:
                del bpy.context.scene['BIM_VarianceColorModeActive']
            
            # Limpiar datos de varianza
            if 'BIM_VarianceColorTypes' in bpy.context.scene:
                del bpy.context.scene['BIM_VarianceColorTypes']
            
            # Forzar actualización del viewport
            bpy.context.view_layer.update()
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            
            print("✅ Variance color mode deactivated successfully")
            
        except Exception as e:
            print(f"❌ Error deactivating variance color mode: {e}")
            import traceback
            traceback.print_exc()

    @classmethod
    def _create_variance_colortype_group(cls):
        """Crea un grupo de ColorTypes especial para varianza"""
        try:
            # Definir los ColorTypes de varianza
            variance_colortypes = {
                "DELAYED": {
                    "Color": (1.0, 0.2, 0.2),
                    "Transparency": 0.0,
                    "Description": "Tasks that are delayed"
                },
                "AHEAD": {
                    "Color": (0.2, 1.0, 0.2), 
                    "Transparency": 0.0,
                    "Description": "Tasks that are ahead of schedule"
                },
                "ONTIME": {
                    "Color": (0.2, 0.2, 1.0),
                    "Transparency": 0.0, 
                    "Description": "Tasks that are on time"
                },
                "UNSELECTED": {
                    "Color": (0.8, 0.8, 0.8),
                    "Transparency": 0.7,
                    "Description": "Tasks not selected for variance view"
                }
            }
            
            # Crear el archivo de configuración del grupo
            variance_group_data = {
                "name": "VARIANCE_MODE",
                "description": "Special ColorType group for variance analysis mode",
                "ColorTypes": variance_colortypes
            }
            
            # Almacenar en memoria para uso inmediato - convertir a formato serializable
            serializable_colortypes = {}
            for name, data in variance_colortypes.items():
                serializable_colortypes[name] = {
                    "Color": tuple(data["Color"]),  # Asegurar que sea tupla
                    "Transparency": float(data["Transparency"]),
                    "Description": str(data["Description"])
                }
            
            bpy.context.scene['BIM_VarianceColorTypes'] = serializable_colortypes
            
            print("✅ Created variance ColorType group")
            
        except Exception as e:
            print(f"❌ Error creating variance ColorType group: {e}")

    @classmethod  
    def _trigger_variance_color_update(cls):
        """Fuerza una actualización de colores usando el sistema existente"""
        try:
            # Usar el live color update handler existente pero con lógica de varianza
            cls._variance_aware_color_update()
            
        except Exception as e:
            print(f"❌ Error triggering variance color update: {e}")

    @classmethod
    def _variance_aware_color_update(cls):
        """Actualización de colores que tiene en cuenta el modo de varianza"""
        try:
            is_variance_mode = bpy.context.scene.get('BIM_VarianceColorModeActive', False)
            
            if not is_variance_mode:
                # Si no está en modo varianza, usar el sistema normal
                return
            
            print("🎯 Applying variance-aware color update...")
            
            # IMPORTANT: Asegurar que el viewport está en modo Material Preview o Rendered
            cls._ensure_viewport_shading()
            
            # Obtener tareas con varianza seleccionadas
            tprops = cls.get_task_tree_props()
            if not tprops:
                return
                
            variance_selected_tasks = [
                task for task in tprops.tasks 
                if getattr(task, 'is_variance_color_selected', False) and task.variance_status
            ]
            
            variance_colortypes = bpy.context.scene.get('BIM_VarianceColorTypes', {})
            
            # Crear mapeo de objetos IFC a tareas reales
            object_to_task_map = cls._build_object_task_mapping(tprops.tasks)
            
            # Iterar sobre todos los objetos y aplicar colores de varianza
            for obj in bpy.context.scene.objects:
                if obj.type != 'MESH':
                    continue
                    
                element = tool.Ifc.get_entity(obj)
                if not element:
                    continue
                
                # Determinar el color basado en la relación real tarea-objeto
                color = cls._get_variance_color_for_object_real(obj, element, object_to_task_map, variance_selected_tasks)
                
                if color:
                    cls._apply_color_to_object_simple(obj, color)
            
            # Forzar actualización del viewport
            bpy.context.view_layer.update()
            
            # También actualizar el depsgraph
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            
        except Exception as e:
            print(f"❌ Error in variance aware color update: {e}")
            
    @classmethod
    def _ensure_viewport_shading(cls):
        """Asegurar que el viewport esté en modo Solid con colores de objeto"""
        try:
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            current_shading = space.shading.type
                            print(f"🔍 Current viewport shading: {current_shading}")
                            
                            # Asegurar modo Solid con colores de objeto
                            if current_shading != 'SOLID':
                                space.shading.type = 'SOLID'
                                print("🔄 Changed viewport to Solid mode")
                            
                            if hasattr(space.shading, 'color_type'):
                                space.shading.color_type = 'OBJECT'
                                print("🎨 Set solid shading to OBJECT color mode")
                            break
        except Exception as e:
            print(f"⚠️ Could not ensure viewport shading: {e}")

    @classmethod
    def _build_object_task_mapping(cls, all_tasks):
        """Construye mapeo usando el sistema correcto de Bonsai"""
        object_task_map = {}
        
        print(f"🔍 Building object-task mapping for {len(all_tasks)} tasks using Bonsai system...")
        
        # Usar el método correcto de Bonsai para obtener outputs
        ifc_file = tool.Ifc.get()
        if not ifc_file:
            print("❌ No IFC file available")
            return object_task_map
        
        for task_pg in all_tasks:
            try:
                task_ifc = ifc_file.by_id(task_pg.ifc_definition_id)
                if not task_ifc:
                    continue
                    
                # Usar el método correcto de Bonsai para obtener outputs
                outputs = cls.get_task_outputs(task_ifc)
                
                if outputs:
                    print(f"📋 Task {task_pg.ifc_definition_id} ({task_pg.name}) has {len(outputs)} outputs:")
                    for output in outputs:
                        object_task_map[output.id()] = task_pg
                        print(f"  → Output {output.id()} ({output.Name}) assigned to task")
                else:
                    print(f"❌ Task {task_pg.ifc_definition_id} ({task_pg.name}) has no outputs")
                        
            except Exception as e:
                print(f"❌ Error mapping task {task_pg.ifc_definition_id}: {e}")
                continue
        
        print(f"✅ Built mapping: {len(object_task_map)} object-task relationships")
        return object_task_map

    @classmethod
    def _get_variance_color_for_object_real(cls, obj, element, object_task_map, variance_selected_tasks):
        """Determina color simple y directo"""
        try:
            element_id = element.id()
            assigned_task = object_task_map.get(element_id)
            
            # Si este objeto pertenece a una tarea con checkbox activo
            if assigned_task and getattr(assigned_task, 'is_variance_color_selected', False):
                variance_status = getattr(assigned_task, 'variance_status', '')
                
                # Colorear según status de varianza
                if "Delayed" in variance_status:
                    print(f"🔴 {obj.name} → Task {assigned_task.ifc_definition_id} → DELAYED")
                    return (1.0, 0.2, 0.2, 1.0)  # Rojo
                elif "Ahead" in variance_status:
                    print(f"🟢 {obj.name} → Task {assigned_task.ifc_definition_id} → AHEAD") 
                    return (0.2, 1.0, 0.2, 1.0)  # Verde
                elif "On Time" in variance_status:
                    print(f"🔵 {obj.name} → Task {assigned_task.ifc_definition_id} → ONTIME")
                    return (0.2, 0.2, 1.0, 1.0)  # Azul
                else:
                    print(f"❓ {obj.name} → Task {assigned_task.ifc_definition_id} → Unknown status: '{variance_status}'")
                    return (0.8, 0.8, 0.8, 0.3)  # Gris transparente
            else:
                # Objeto sin tarea seleccionada → gris transparente
                return (0.8, 0.8, 0.8, 0.3)
                
        except Exception as e:
            print(f"❌ Error getting color for object {obj.name}: {e}")
            return (0.8, 0.8, 0.8, 0.3)


    @classmethod
    def _apply_color_to_object_simple(cls, obj, color):
        """Aplicar color solo al objeto (para viewport Solid)"""
        try:
            print(f"🎨 Applying variance color {color} to {obj.name}")
            
            # SOLO aplicar color del objeto (para modo Solid > Object)
            if hasattr(obj, 'color'):
                obj.color = color[:4] if len(color) >= 4 else color[:3] + (1.0,)
                print(f"✅ Set object color for {obj.name}: {obj.color}")
            else:
                print(f"⚠️ Object {obj.name} does not have color property")
                        
        except Exception as e:
            print(f"❌ Error applying simple color to {obj.name}: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def add_group_to_animation_stack():
        """Add a new group to the animation group stack"""
        try:
            anim_props = tool.Sequence.get_animation_props()
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
            anim_props = tool.Sequence.get_animation_props()
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
            anim_props = tool.Sequence.get_animation_props()
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

    @classmethod
    def clear_schedule_variance(cls):
        """
        Clear schedule variance data, colors and reset objects to their original state.
        Called when clearing variance or switching schedule types.
        """
        try:
            print("🧹 CLEAR_SCHEDULE_VARIANCE: Starting comprehensive cleanup process...")
            
            # STEP 1: Clear variance DATA from all tasks (this was missing!)
            tprops = cls.get_task_tree_props()
            if tprops and tprops.tasks:
                cleared_tasks = 0
                print(f"🧹 CLEAR_SCHEDULE_VARIANCE: Found {len(tprops.tasks)} tasks to clean")
                
                for task in tprops.tasks:
                    # CRITICAL: Clear the variance data properties set by CalculateScheduleVariance
                    if hasattr(task, 'variance_days'):
                        task.variance_days = 0
                        cleared_tasks += 1
                        
                    if hasattr(task, 'variance_status'):
                        task.variance_status = ""
                        
                    # Clear variance color selection checkbox
                    if hasattr(task, 'is_variance_color_selected'):
                        task.is_variance_color_selected = False
                        
                print(f"✅ CLEAR_SCHEDULE_VARIANCE: Cleared variance data from {cleared_tasks} tasks")
            else:
                print("⚠️ CLEAR_SCHEDULE_VARIANCE: No task properties found")
            
            # STEP 2: Clear variance color mode and restore original colors
            print("🧹 CLEAR_SCHEDULE_VARIANCE: Clearing variance color mode...")
            cls.clear_variance_color_mode()
            
            # STEP 3: Remove variance mode flags from scene
            scene_flags_cleared = 0
            if hasattr(bpy.context.scene, 'BIM_VarianceColorModeActive'):
                del bpy.context.scene['BIM_VarianceColorModeActive']
                scene_flags_cleared += 1
                print("🧹 Removed BIM_VarianceColorModeActive flag from scene")
                
            # Clear any other variance-related scene properties
            variance_keys = [key for key in bpy.context.scene.keys() if 'variance' in key.lower()]
            for key in variance_keys:
                try:
                    del bpy.context.scene[key]
                    scene_flags_cleared += 1
                    print(f"🧹 Removed scene property: {key}")
                except Exception as e:
                    print(f"⚠️ Could not remove scene property {key}: {e}")
            
            print(f"✅ CLEAR_SCHEDULE_VARIANCE: Cleared {scene_flags_cleared} scene flags")
            
            # STEP 4: Reset ALL IFC objects to default appearance (comprehensive reset)
            print("🧹 CLEAR_SCHEDULE_VARIANCE: Resetting all IFC objects to default state...")
            reset_objects = 0
            
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                    try:
                        # Reset color to default gray
                        obj.color = (0.8, 0.8, 0.8, 1.0)
                        
                        # Reset visibility
                        obj.hide_viewport = False
                        obj.hide_render = False
                        
                        # Clear any animation data that might be affecting appearance
                        if obj.animation_data:
                            obj.animation_data_clear()
                        
                        # Reset material overrides if any
                        if obj.material_slots:
                            for slot in obj.material_slots:
                                if slot.material:
                                    slot.material.diffuse_color = (0.8, 0.8, 0.8, 1.0)
                        
                        reset_objects += 1
                        
                    except Exception as e:
                        print(f"⚠️ Error resetting object {obj.name}: {e}")
            
            print(f"✅ CLEAR_SCHEDULE_VARIANCE: Reset {reset_objects} objects to default state")
            
            # STEP 5: Force complete viewport refresh
            print("🧹 CLEAR_SCHEDULE_VARIANCE: Forcing viewport refresh...")
            try:
                # Update view layer
                bpy.context.view_layer.update()
                
                # Force redraw of all 3D viewports
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                # Ensure object colors are visible
                                if hasattr(space.shading, 'color_type'):
                                    space.shading.color_type = 'OBJECT'
                                    
                print("✅ CLEAR_SCHEDULE_VARIANCE: Viewport refresh completed")
                
            except Exception as e:
                print(f"⚠️ Error during viewport refresh: {e}")
            
            print("✅ CLEAR_SCHEDULE_VARIANCE: Comprehensive cleanup completed successfully")
            
        except Exception as e:
            print(f"❌ Error in clear_schedule_variance: {e}")
            import traceback
            traceback.print_exc()


class SearchCustomColorTypeGroup(bpy.types.Operator):
    bl_idname = "bim.search_custom_ColorType_group"
    bl_label = "Search Custom ColorType Group"
    bl_description = "Search and filter custom ColorType groups"
    bl_options = {"REGISTER", "UNDO"}

    search_term: bpy.props.StringProperty(name="Search", default="")

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        if not self.search_term:
            self.report({'INFO'}, "Enter search term")
            return {'CANCELLED'}

        # Buscar en grupos disponibles
        from bonsai.bim.module.sequence.prop import get_user_created_groups_enum
        items = get_user_created_groups_enum(None, context)

        matches = [item for item in items if self.search_term.lower() in item[1].lower()]

        if matches:
            # Seleccionar el primer match
            props.task_ColorType_group_selector = matches[0][0]
            self.report({'INFO'}, f"Found and selected: {matches[0][1]}")
        else:
            self.report({'WARNING'}, f"No groups found matching: {self.search_term}")

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "search_term")

class CopyCustomColorTypeGroup(bpy.types.Operator):
    bl_idname = "bim.copy_custom_ColorType_group"
    bl_label = "Copy Custom ColorType Group"
    bl_description = "Copy current custom ColorType group to clipboard"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        current_value = getattr(props, "task_ColorType_group_selector", "")

        if current_value:
            context.window_manager.clipboard = current_value
            self.report({'INFO'}, f"Copied to clipboard: {current_value}")
        else:
            self.report({'WARNING'}, "No custom ColorType group selected to copy")

        return {'FINISHED'}

class PasteCustomColorTypeGroup(bpy.types.Operator):
    bl_idname = "bim.paste_custom_ColorType_group"
    bl_label = "Paste Custom ColorType Group"
    bl_description = "Paste custom ColorType group from clipboard"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        clipboard_value = context.window_manager.clipboard.strip()

        if not clipboard_value:
            self.report({'WARNING'}, "Clipboard is empty")
            return {'CANCELLED'}

        # Verificar que el valor existe en los grupos disponibles
        from bonsai.bim.module.sequence.prop import get_user_created_groups_enum
        items = get_user_created_groups_enum(None, context)
        valid_values = [item[0] for item in items]

        if clipboard_value in valid_values:
            props.task_ColorType_group_selector = clipboard_value
            self.report({'INFO'}, f"Pasted from clipboard: {clipboard_value}")
        else:
            self.report({'WARNING'}, f"Invalid group in clipboard: {clipboard_value}")

        return {'FINISHED'}

class SetCustomColorTypeGroupNull(bpy.types.Operator):
    bl_idname = "bim.set_custom_ColorType_group_null"
    bl_label = "Set Custom ColorType Group to Null"
    bl_description = "Clear custom ColorType group selection (set to null)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()

        # Limpiar la selección
        props.task_ColorType_group_selector = ""

        # También limpiar el perfil seleccionado en la tarea activa si existe
        try:
            tprops = tool.Sequence.get_task_tree_props()
            wprops = tool.Sequence.get_work_schedule_props()
            if tprops.tasks and wprops.active_task_index < len(tprops.tasks):
                task = tprops.tasks[wprops.active_task_index]
                task.selected_ColorType_in_active_group = ""
                task.use_active_ColorType_group = False
        except Exception:
            pass

        self.report({'INFO'}, "Custom ColorType group cleared (set to null)")
        return {'FINISHED'}

class ShowCustomColorTypeGroupInfo(bpy.types.Operator):
    bl_idname = "bim.show_custom_ColorType_group_info"
    bl_label = "Custom ColorType Group Info"
    bl_description = "Show information about the current custom ColorType group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        current_value = getattr(props, "task_ColorType_group_selector", "")

        if current_value:
            # Obtener información del grupo
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
            ColorTypes = UnifiedColorTypeManager.get_group_ColorTypes(context, current_value)

            info_text = f"Group: {current_value}\n"
            info_text += f"ColorTypes: {len(ColorTypes)}\n"
            if ColorTypes:
                info_text += f"Available: {', '.join(ColorTypes.keys())}"

            self.report({'INFO'}, info_text)
        else:
            self.report({'INFO'}, "No custom ColorType group selected")

        return {'FINISHED'}
    
def get_unified_date_range(self, work_schedule):
    """
    Calcula el rango de fechas unificado analizando TODOS los 4 tipos de cronograma.
    Devuelve el inicio más temprano y el fin más tardío de todos ellos.
    """
    if not work_schedule:
        return None, None

    all_starts = []
    all_finishes = []

    for schedule_type in ["SCHEDULE", "ACTUAL", "EARLY", "LATE"]:
        start_attr = f"{schedule_type.capitalize()}Start"
        finish_attr = f"{schedule_type.capitalize()}Finish"

        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)

        def get_all_tasks_recursive(tasks):
            result = []
            for task in tasks:
                result.append(task)
                nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                if nested:
                    result.extend(get_all_tasks_recursive(nested))
            return result

        all_tasks = get_all_tasks_recursive(root_tasks)

        for task in all_tasks:
            start_date = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
            if start_date:
                all_starts.append(start_date)

            finish_date = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
            if finish_date:
                all_finishes.append(finish_date)

    if not all_starts or not all_finishes:
        return None, None

    unified_start = min(all_starts)
    unified_finish = max(all_finishes)

    return unified_start, unified_finish

    @classmethod
    def copy_task_colortype_config(cls):
        """
        Copy ColorType configuration from the active task to selected tasks.
        """
        try:
            # Get task tree properties
            tprops = cls.get_task_tree_props()
            if not tprops or not tprops.tasks:
                print("Warning: No task tree properties found")
                return

            # Get work schedule properties to find active task
            ws_props = cls.get_work_schedule_props()
            if not ws_props or ws_props.active_task_index < 0 or ws_props.active_task_index >= len(tprops.tasks):
                print("Warning: No active task found")
                return

            # Get the source task (active task)
            source_task = tprops.tasks[ws_props.active_task_index]
            print(f"Source task: {getattr(source_task, 'name', 'Unknown')} (ID: {source_task.ifc_definition_id})")

            # Get selected tasks (tasks with is_selected = True)
            selected_tasks = [task for task in tprops.tasks if getattr(task, 'is_selected', False)]
            if not selected_tasks:
                print("Warning: No tasks selected to copy to")
                return

            print(f"Found {len(selected_tasks)} selected tasks to copy to")

            # Copy configuration from source to selected tasks
            copied_count = 0
            for target_task in selected_tasks:
                if target_task.ifc_definition_id == source_task.ifc_definition_id:
                    continue  # Skip copying to self

                try:
                    # Copy main colortype settings
                    target_task.use_active_colortype_group = getattr(source_task, 'use_active_colortype_group', False)
                    target_task.selected_colortype_in_active_group = getattr(source_task, 'selected_colortype_in_active_group', "")
                    
                    # Copy animation_color_schemes if it exists
                    if hasattr(target_task, 'animation_color_schemes') and hasattr(source_task, 'animation_color_schemes'):
                        target_task.animation_color_schemes = source_task.animation_color_schemes

                    # Copy colortype group choices
                    target_task.colortype_group_choices.clear()
                    for source_group in source_task.colortype_group_choices:
                        target_group = target_task.colortype_group_choices.add()
                        target_group.group_name = source_group.group_name
                        target_group.enabled = source_group.enabled
                        
                        # Copy the selected value using the appropriate attribute
                        for attr_candidate in ("selected_colortype", "selected", "active_colortype", "colortype"):
                            if hasattr(source_group, attr_candidate) and hasattr(target_group, attr_candidate):
                                setattr(target_group, attr_candidate, getattr(source_group, attr_candidate))
                                break

                    copied_count += 1
                    print(f"Copied configuration to task: {getattr(target_task, 'name', 'Unknown')} (ID: {target_task.ifc_definition_id})")

                except Exception as e:
                    print(f"Error copying to task {target_task.ifc_definition_id}: {e}")

            print(f"Successfully copied ColorType configuration to {copied_count} tasks")

        except Exception as e:
            print(f"Error in copy_task_colortype_config: {e}")
            import traceback
            traceback.print_exc()