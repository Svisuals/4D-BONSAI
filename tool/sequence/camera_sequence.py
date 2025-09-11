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
import math
import mathutils
import traceback
from mathutils import Vector

from .props_sequence import PropsSequence
from .ifc_data_sequence import IFCDataSequence
import bonsai.tool as tool

class CameraSequence(PropsSequence):
    """Manejo de cámaras para animación 4D y snapshots."""


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
        print(f"🎥 Call stack: {traceback.format_stack()[-3:-1]}")  
       
        anim = cls.get_animation_props()
        camera_props = anim.camera_orbit  
        ws_props = cls.get_work_schedule_props()
        
        current_orbit_mode = getattr(camera_props, 'orbit_mode', 'NONE')
        existing_camera = bpy.context.scene.camera
        
        print(f"🎥 Current orbit_mode: {current_orbit_mode}")
        print(f"🎥 Existing scene camera: {existing_camera.name if existing_camera else 'None'}")

        print("🎥 Creating 4D Animation Camera...")

      
        center, dims, _ = cls._get_active_schedule_bbox()

        cam_data = bpy.data.cameras.new("4D_Animation_Camera")
        cam_data.lens = camera_props.camera_focal_mm
        cam_data.clip_start = max(0.0001, camera_props.camera_clip_start)
       
        clip_end = camera_props.camera_clip_end
        auto_scale = max(dims.x, dims.y, dims.z) * 5.0  
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

        target_name = f"4D_OrbitTarget_for_{{cam_obj.name}}"
        # Target (auto u objeto)
        if camera_props.look_at_mode == "OBJECT" and camera_props.look_at_object:
            target = camera_props.look_at_object
            print(f"📍 Using custom target: {{target.name}}")
        else:
            target = cls._get_or_create_target(center, target_name)
            print(f"📍 Created/using auto target '{{target_name}}' at: {{center}}")

       
        if camera_props.orbit_radius_mode == "AUTO":
           
            base = max(dims.x, dims.y)
            if base > 0:
                r = base * 1.5  
            else:
                r = 15.0  # Fallback más grande
            print(f"📐 Auto radius calculated: {{r:.2f}}m (from bbox: {{dims}})")
        else:
            r = max(0.01, camera_props.orbit_radius)
            print(f"📐 Manual radius: {{r:.2f}}m")

        z = center.z + camera_props.orbit_height
        angle0 = math.radians(camera_props.orbit_start_angle_deg)
        sign = -1.0 if camera_props.orbit_direction == "CW" else 1.0

       
        initial_x = center.x + r * math.cos(angle0)
        initial_y = center.y + r * math.sin(angle0)
        cam_obj.location = Vector((initial_x, initial_y, z))
        print(f"📍 Initial camera position: ({{initial_x:.2f}}, {{initial_y:.2f}}, {{z:.2f}})")

       
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


        if camera_props.orbit_use_4d_duration:
            end_frame = start_frame + max(1, total_frames_4d - 1)
        else:
            end_frame = start_frame + int(max(1, camera_props.orbit_duration_frames))

        dur = max(1, end_frame - start_frame)
        print(f"⏱️ Animation timeline: frames {{start_frame}} to {{end_frame}} (duration: {{dur}})")

      
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












