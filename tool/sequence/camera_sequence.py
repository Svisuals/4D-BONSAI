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
import bonsai.tool as tool
from . import props_sequence
from . import visuals_sequence
from . import animation_sequence



def is_bonsai_camera(obj):
    """Verifica si un objeto es una cámara gestionada por las herramientas 4D/Snapshot de Bonsai."""
    if not obj or obj.type != 'CAMERA':
        return False
    if obj.get('camera_context') in ['animation', 'snapshot']:
        return True
    if '4D_Animation_Camera' in obj.name or 'Snapshot_Camera' in obj.name:
        return True
    return False

def is_bonsai_animation_camera(obj):
    """Verifica si un objeto es una cámara específica para los Ajustes de Animación."""
    if not obj or obj.type != 'CAMERA':
        return False
    if obj.get('camera_context') == 'animation':
        return True
    if '4D_Animation_Camera' in obj.name and 'Snapshot' not in obj.name:
        return True
    return False

def is_bonsai_snapshot_camera(obj):
    """Verifica si un objeto es una cámara específica para los Ajustes de Snapshot."""
    if not obj or obj.type != 'CAMERA':
        return False
    if obj.get('camera_context') == 'snapshot':
        return True
    if 'Snapshot_Camera' in obj.name:
        return True
    return False

def _get_active_schedule_bbox():
    """Return (center (Vector), dims (Vector), obj_list) for active WorkSchedule products."""
    from . import task_sequence
    
    ws = task_sequence.get_active_work_schedule()
    objs = []
    if ws:
        try:
            from . import utils_sequence
            products = utils_sequence.get_work_schedule_products(ws)
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
        objs = [o for o in bpy.data.objects if getattr(o, "type", "") == "MESH" and not o.hide_get()]

    if not objs:
        return mathutils.Vector((0.0, 0.0, 0.0)), mathutils.Vector((10.0, 10.0, 5.0)), []

    mins = mathutils.Vector((1e18, 1e18, 1e18))
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
    dims = maxs - mins
    return center, dims, objs


def _get_or_create_target(center, name="4D_OrbitTarget"):
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


def add_animation_camera():
    """Create a camera using Animation Settings (Camera/Orbit) and optionally animate it."""
    import bpy
    import bonsai.tool as tool
    import ifcopenshell.util.sequence
    from . import props_sequence
    from . import utils_sequence
    from mathutils import Vector
    
    print("🎥 === ADD_ANIMATION_CAMERA CALLED ===")
    
    # Get active work schedule
    props = props_sequence.get_work_schedule_props()
    if not props.active_work_schedule_id:
        print("⚠️ No active work schedule")
        # Create with generic name if no schedule
        schedule_name = "NoSchedule"
        work_schedule = None
    else:
        try:
            work_schedule = tool.Ifc.get().by_id(props.active_work_schedule_id)
            schedule_name = getattr(work_schedule, "Name", "Schedule")
        except Exception as e:
            print(f"⚠️ Error getting work schedule: {e}")
            schedule_name = "Schedule"
            work_schedule = None
    
    anim = props_sequence.get_animation_props()
    camera_props = anim.camera_orbit
    center, dims, _ = _get_active_schedule_bbox()

    # Create camera with proper work schedule name
    cam_data = bpy.data.cameras.new(f"4D_Animation_Camera_{schedule_name}")
    cam_data.lens = camera_props.camera_focal_mm
    cam_data.clip_start = max(0.0001, camera_props.camera_clip_start)
    auto_scale = max(dims.x, dims.y, dims.z) * 5.0
    cam_data.clip_end = max(camera_props.camera_clip_end, auto_scale)

    cam_obj = bpy.data.objects.new(cam_data.name, cam_data)
    cam_obj['is_4d_camera'] = True
    cam_obj['is_animation_camera'] = True
    cam_obj['camera_context'] = 'animation'
    if props.active_work_schedule_id:
        cam_obj['work_schedule_id'] = props.active_work_schedule_id
    try:
        bpy.context.collection.objects.link(cam_obj)
    except Exception:
        bpy.context.scene.collection.objects.link(cam_obj)

    target_name = f"4D_OrbitTarget_for_{cam_obj.name}"
    target = camera_props.look_at_object if camera_props.look_at_mode == "OBJECT" and camera_props.look_at_object else _get_or_create_target(center, target_name)

    r = max(dims.x, dims.y) * 1.5 if camera_props.orbit_radius_mode == "AUTO" else max(0.01, camera_props.orbit_radius)
    z = center.z + camera_props.orbit_height
    angle0 = math.radians(camera_props.orbit_start_angle_deg)
    initial_x = center.x + r * math.cos(angle0)
    initial_y = center.y + r * math.sin(angle0)
    cam_obj.location = Vector((initial_x, initial_y, z))

    tcon = cam_obj.constraints.new(type='TRACK_TO')
    tcon.target = target
    tcon.track_axis = 'TRACK_NEGATIVE_Z'
    tcon.up_axis = 'UP_Y'

    mode = camera_props.orbit_mode
    if mode == "NONE":
        existing_camera = bpy.context.scene.camera
        if existing_camera and existing_camera != cam_obj:
            bpy.data.objects.remove(cam_obj, do_unlink=True)
            bpy.context.scene.camera = existing_camera
            return existing_camera
        else:
            bpy.context.scene.camera = cam_obj
            return cam_obj

    settings = animation_sequence.get_animation_settings()
    total_frames_4d = int(settings["total_frames"]) if settings else 250
    start_frame = int(settings["start_frame"]) if settings else 1

    end_frame = start_frame + max(1, total_frames_4d - 1) if camera_props.orbit_use_4d_duration else start_frame + int(max(1, camera_props.orbit_duration_frames))
    sign = -1.0 if camera_props.orbit_direction == "CW" else 1.0

    if camera_props.orbit_path_method == "FOLLOW_PATH":
        _create_follow_path_orbit(cam_obj, center, r, z, angle0, start_frame, end_frame, sign, mode)
    else:
        _create_keyframe_orbit(cam_obj, center, r, z, angle0, start_frame, end_frame, sign, mode)

    bpy.context.scene.camera = cam_obj
    print(f"✅ 4D Camera created successfully: {cam_obj.name}")
    return cam_obj

def add_snapshot_camera():
    """Create a camera specifically for Snapshot Settings."""
    import bpy
    import bonsai.tool as tool
    import mathutils
    from . import props_sequence
    from mathutils import Vector
    
    # Get active work schedule
    props = props_sequence.get_work_schedule_props()
    if not props.active_work_schedule_id:
        print("⚠️ No active work schedule")
        # Create with generic name if no schedule
        schedule_name = "NoSchedule"
        work_schedule = None
    else:
        try:
            work_schedule = tool.Ifc.get().by_id(props.active_work_schedule_id)
            schedule_name = getattr(work_schedule, "Name", "Schedule")
        except Exception as e:
            print(f"⚠️ Error getting work schedule: {e}")
            schedule_name = "Schedule"
            work_schedule = None
    
    anim = props_sequence.get_animation_props()
    camera_props = anim.camera_orbit
    center, dims, _ = _get_active_schedule_bbox()

    # Create camera with proper work schedule name
    cam_data = bpy.data.cameras.new(f"Snapshot_Camera_{schedule_name}")
    cam_data.lens = camera_props.camera_focal_mm
    cam_data.clip_start = max(0.0001, camera_props.camera_clip_start)
    auto_scale = max(dims.length * 2.0, 100.0)
    cam_data.clip_end = max(camera_props.camera_clip_end, auto_scale)

    cam_obj = bpy.data.objects.new(cam_data.name, cam_data)
    cam_obj['is_4d_camera'] = True
    cam_obj['is_snapshot_camera'] = True
    cam_obj['camera_context'] = 'snapshot'
    if props.active_work_schedule_id:
        cam_obj['work_schedule_id'] = props.active_work_schedule_id
    try:
        bpy.context.collection.objects.link(cam_obj)
    except Exception:
        bpy.context.scene.collection.objects.link(cam_obj)

    radius = max(dims.length * 1.5, 20.0)
    height = center.z + dims.z * 0.5
    cam_obj.location = Vector((center.x + radius, center.y + radius, height))

    target = _get_or_create_target(center, "Snapshot_Target")
    tcon = cam_obj.constraints.new(type='TRACK_TO')
    tcon.target = target
    tcon.track_axis = 'TRACK_NEGATIVE_Z'
    tcon.up_axis = 'UP_Y'
    bpy.context.scene.camera = cam_obj

    texts_collection = bpy.data.collections.get("Schedule_Display_Texts")
    if not texts_collection or len(texts_collection.objects) == 0:
        if work_schedule:
            settings = animation_sequence.get_animation_settings()
            if settings and work_schedule:
                settings['schedule_name'] = work_schedule.Name or 'No Schedule'
                visuals_sequence.add_text_animation_handler(settings)
            else:
                _create_basic_snapshot_texts(work_schedule.Name if work_schedule else 'No Schedule')
            
            texts_collection = bpy.data.collections.get("Schedule_Display_Texts")
            if texts_collection:
                should_hide = not getattr(camera_props, "show_3d_schedule_texts", False)
                texts_collection.hide_viewport = should_hide
                texts_collection.hide_render = should_hide
            try:
                bpy.ops.bim.arrange_schedule_texts()
            except Exception as e:
                print(f"⚠️ Could not auto-arrange texts: {e}")

    legend_hud_exists = any(obj.get("is_3d_legend_hud", False) for obj in bpy.data.objects)
    if not legend_hud_exists:
        legend_hud_enabled = getattr(camera_props, "enable_3d_legend_hud", False)
        show_3d_texts = getattr(camera_props, "show_3d_schedule_texts", False)
        if legend_hud_enabled:
            bpy.ops.bim.setup_3d_legend_hud()
            if not show_3d_texts:
                for obj in bpy.data.objects:
                    if obj.get("is_3d_legend_hud", False):
                        obj.hide_viewport = True
                        obj.hide_render = True
    return cam_obj

def _create_basic_snapshot_texts(schedule_name):
    """Creates basic 3D texts manually when animation settings are not available."""
    collection_name = "Schedule_Display_Texts"
    if collection_name not in bpy.data.collections:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)
    else:
        collection = bpy.data.collections[collection_name]

def _create_basic_snapshot_texts(schedule_name):
    """Creates basic 3D texts manually when animation settings are not available."""
    collection_name = "Schedule_Display_Texts"
    if collection_name not in bpy.data.collections:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)
    else:
        collection = bpy.data.collections[collection_name]

    text_configs = [
        {"name": "Schedule_Name", "position": (0, 10, 6), "content": f"Schedule: {schedule_name}", "type": "schedule_name"},
        {"name": "Schedule_Date", "position": (0, 10, 5), "content": "Date: [Dynamic]", "type": "date"},
        {"name": "Schedule_Week", "position": (0, 10, 4), "content": "Week: [Dynamic]", "type": "week"},
        {"name": "Schedule_Day_Counter", "position": (0, 10, 3), "content": "Day: [Dynamic]", "type": "day_counter"},
        {"name": "Schedule_Progress", "position": (0, 10, 2), "content": "Progress: [Dynamic]", "type": "progress"},
    ]

    for config in text_configs:
        text_data = bpy.data.curves.new(name=config["name"], type='FONT')
        text_obj = bpy.data.objects.new(name=config["name"], object_data=text_data)
        text_data.body = config["content"]
        text_data['text_type'] = config["type"]
        text_data.align_x = 'CENTER'
        text_data.align_y = 'BOTTOM_BASELINE'
        text_obj.location = config["position"]
        collection.objects.link(text_obj)

def align_snapshot_camera_to_view():
    """Aligns the active snapshot camera to the current 3D view."""
    area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
    if not area: raise Exception("No 3D viewport found.")
    space = next((s for s in area.spaces if s.type == 'VIEW_3D'), None)
    if not space: raise Exception("No 3D space data found.")
    cam_obj = bpy.context.scene.camera
    if not cam_obj: raise Exception("No active camera in the scene.")
    if not is_bonsai_snapshot_camera(cam_obj):
        print(f"Warning: Active camera '{cam_obj.name}' is not a designated snapshot camera, but aligning anyway.")
    region_3d = space.region_3d
    if region_3d:
        cam_obj.matrix_world = region_3d.view_matrix.inverted()
    else:
        raise Exception("Could not get 3D view region data.")

def align_animation_camera_to_view():
    """Alinea la cámara de animación activa a la vista 3D y la convierte en estática."""
    area = next((a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'), None)
    space = next((s for s in area.spaces if s.type == 'VIEW_3D'), None) if area else None
    cam_obj = bpy.context.scene.camera
    if not all([area, space, cam_obj]): raise Exception("No se encontró la cámara o la vista 3D.")

    if cam_obj.animation_data: cam_obj.animation_data_clear()
    for c in list(cam_obj.constraints): cam_obj.constraints.remove(c)

    region_3d = space.region_3d
    if region_3d:
        cam_obj.matrix_world = region_3d.view_matrix.inverted()
    else:
        raise Exception("No se pudieron obtener los datos de la región 3D.")
    try:
        anim_props = props_sequence.get_animation_props()
        camera_props = anim_props.camera_orbit
        camera_props.orbit_mode = 'NONE'
    except Exception as e:
        print(f"No se pudo actualizar la UI del modo de órbita: {e}")

def update_animation_camera(cam_obj):
    """Updates an existing 4D camera with the current UI settings."""
    from mathutils import Vector
    if cam_obj.animation_data: cam_obj.animation_data_clear()
    for c in list(cam_obj.constraints): cam_obj.constraints.remove(c)

    path_obj = bpy.data.objects.get(f"4D_OrbitPath_for_{cam_obj.name}")
    if path_obj: bpy.data.objects.remove(path_obj, do_unlink=True)
    tgt_obj = bpy.data.objects.get(f"4D_Target_for_{cam_obj.name}")
    if tgt_obj: bpy.data.objects.remove(tgt_obj, do_unlink=True)

    anim = props_sequence.get_animation_props()
    camera_props = anim.camera_orbit
    center, dims, _ = _get_active_schedule_bbox()
    target_name = f"4D_OrbitTarget_for_{cam_obj.name}"
    target = camera_props.look_at_object if camera_props.look_at_mode == "OBJECT" and camera_props.look_at_object else _get_or_create_target(center, target_name)

    cam_data = cam_obj.data
    cam_data.lens = camera_props.camera_focal_mm
    cam_data.clip_start = camera_props.camera_clip_start
    cam_data.clip_end = max(camera_props.camera_clip_end, max(dims.x, dims.y, dims.z) * 5.0)

    mode = camera_props.orbit_mode
    if mode != "NONE":
        r = max(dims.x, dims.y) * 1.5 if camera_props.orbit_radius_mode == "AUTO" else max(0.01, camera_props.orbit_radius)
        z = center.z + camera_props.orbit_height
        angle0 = math.radians(camera_props.orbit_start_angle_deg)
        cam_obj.location = Vector((center.x + r * math.cos(angle0), center.y + r * math.sin(angle0), z))
        tcon = cam_obj.constraints.new(type='TRACK_TO')
        tcon.target = target
        tcon.track_axis = 'TRACK_NEGATIVE_Z'
        tcon.up_axis = 'UP_Y'

        settings = animation_sequence.get_animation_settings()
        start_frame = settings["start_frame"]
        end_frame = start_frame + settings["total_frames"] - 1 if camera_props.orbit_use_4d_duration else start_frame + int(camera_props.orbit_duration_frames)
        sign = -1.0 if camera_props.orbit_direction == "CW" else 1.0

        if camera_props.orbit_path_method == "FOLLOW_PATH":
            _create_follow_path_orbit(cam_obj, center, r, z, angle0, start_frame, end_frame, sign, mode)
        else:
            _create_keyframe_orbit(cam_obj, center, r, z, angle0, start_frame, end_frame, sign, mode)
    bpy.context.scene.camera = cam_obj
    return cam_obj

def clear_camera_animation(cam_obj):
    """Robustly clears animation, constraints, and auxiliary objects from a camera."""
    if not cam_obj: return
    try:
        if getattr(cam_obj, "animation_data", None): cam_obj.animation_data_clear()
        for c in list(getattr(cam_obj, "constraints", [])):
            try: cam_obj.constraints.remove(c)
            except Exception: pass
        path_obj = bpy.data.objects.get(f"4D_OrbitPath_for_{cam_obj.name}")
        if path_obj: bpy.data.objects.remove(path_obj, do_unlink=True)
        tgt_obj = bpy.data.objects.get(f"4D_OrbitTarget_for_{cam_obj.name}")
        if tgt_obj: bpy.data.objects.remove(tgt_obj, do_unlink=True)
    except Exception as e:
        print(f"⚠️ Error clearing camera animation: {e}")

def _create_follow_path_orbit(cam_obj, center, radius, z, angle0, start_frame, end_frame, sign, mode):
    anim = props_sequence.get_animation_props()
    camera_props = anim.camera_orbit
    path_object = camera_props.custom_orbit_path if camera_props.orbit_path_shape == 'CUSTOM' and camera_props.custom_orbit_path else None

    if path_object:
        path_object.hide_viewport = camera_props.hide_orbit_path
        path_object.hide_render = camera_props.hide_orbit_path
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
        spline = curve.splines.new('BEZIER')
        spline.bezier_points.add(3)
        kappa = 4 * (math.sqrt(2) - 1) / 3
        points = [(radius, 0), (0, radius), (-radius, 0), (0, -radius)]
        for i, (x, y) in enumerate(points):
            bp = spline.bezier_points[i]
            bp.co = mathutils.Vector((center.x + x, center.y + y, z))
            bp.handle_left_type = bp.handle_right_type = 'ALIGNED'
            if i == 0: bp.handle_left, bp.handle_right = mathutils.Vector((center.x + x, center.y + y - radius * kappa, z)), mathutils.Vector((center.x + x, center.y + y + radius * kappa, z))
            elif i == 1: bp.handle_left, bp.handle_right = mathutils.Vector((center.x + x + radius * kappa, center.y + y, z)), mathutils.Vector((center.x + x - radius * kappa, center.y + y, z))
            elif i == 2: bp.handle_left, bp.handle_right = mathutils.Vector((center.x + x, center.y + y + radius * kappa, z)), mathutils.Vector((center.x + x, center.y + y - radius * kappa, z))
            else: bp.handle_left, bp.handle_right = mathutils.Vector((center.x + x - radius * kappa, center.y + y, z)), mathutils.Vector((center.x + x + radius * kappa, center.y + y, z))
        spline.use_cyclic_u = True

    fcon = cam_obj.constraints.new(type='FOLLOW_PATH')
    fcon.target = path_object
    fcon.use_curve_follow = True
    fcon.use_fixed_location = True
    def key_offset(offset, frame):
        fcon.offset_factor = offset
        fcon.keyframe_insert("offset_factor", frame=frame)
    angle_normalized = (angle0 % (2 * math.pi)) / (2 * math.pi)
    s0, s1 = (angle_normalized, angle_normalized + 1.0) if sign > 0 else (angle_normalized, angle_normalized - 1.0)
    if mode == "CIRCLE_360":
        key_offset(s0, start_frame)
        key_offset(s1, end_frame)
    elif mode == "PINGPONG":
        mid_frame = start_frame + (end_frame - start_frame) // 2
        key_offset(s0, start_frame)
        key_offset(s0 + (s1 - s0) * 0.5, mid_frame)
        key_offset(s0, end_frame)

    if cam_obj.animation_data and cam_obj.animation_data.action:
        for fcurve in cam_obj.animation_data.action.fcurves:
            if "offset_factor" in fcurve.data_path:
                for kf in fcurve.keyframe_points:
                    kf.interpolation = 'LINEAR'
    
    target_obj = bpy.data.objects.get(f"4D_Target_for_{cam_obj.name}")
    if target_obj:
        tcon = cam_obj.constraints.new(type='TRACK_TO')
        tcon.target = target_obj
        tcon.track_axis = 'TRACK_NEGATIVE_Z'
        tcon.up_axis = 'UP_Y'




def _create_keyframe_orbit(cam_obj, center, radius, z, angle0, start_frame, end_frame, sign, mode):
    def pt(theta):
        return mathutils.Vector((center.x + radius * math.cos(theta), center.y + radius * math.sin(theta), z))
    def key_loc(obj, loc, frame):
        obj.location = loc
        obj.keyframe_insert("location", frame=frame)

    if mode == "CIRCLE_360":
        empty_name = f"Camera_Pivot_{cam_obj.name}"
        if empty_name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[empty_name], do_unlink=True)
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=center)
        pivot = bpy.context.active_object
        pivot.name = empty_name
        cam_obj.parent = pivot
        cam_obj.parent_type = 'OBJECT'
        cam_obj.location = (radius, 0, z - center.z)
        pivot.rotation_euler[2] = angle0
        pivot.keyframe_insert("rotation_euler", index=2, frame=start_frame)
        pivot.rotation_euler[2] = angle0 + sign * 2 * math.pi
        pivot.keyframe_insert("rotation_euler", index=2, frame=end_frame)
        if pivot.animation_data and pivot.animation_data.action:
            for fcurve in pivot.animation_data.action.fcurves:
                if fcurve.data_path == "rotation_euler" and fcurve.array_index == 2:
                    for kf in fcurve.keyframe_points:
                        kf.interpolation = 'LINEAR'
    elif mode == "PINGPONG":
        mid_frame = start_frame + (end_frame - start_frame) // 2
        key_loc(cam_obj, pt(angle0), start_frame)
        key_loc(cam_obj, pt(angle0 + sign * math.pi), mid_frame)
        key_loc(cam_obj, pt(angle0), end_frame)
    
    if cam_obj.animation_data and cam_obj.animation_data.action:
        for fcurve in cam_obj.animation_data.action.fcurves:
            if fcurve.data_path == "location":
                for kp in fcurve.keyframe_points:
                    kp.interpolation = 'LINEAR'








