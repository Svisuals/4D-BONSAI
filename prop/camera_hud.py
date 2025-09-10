# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2020, 2021 Dion Moult <dion@thinkmoult.com>
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
import bonsai.tool as tool
from bpy.types import PropertyGroup
from bpy.props import (
    PointerProperty,
    StringProperty,
    EnumProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
    CollectionProperty,
)
from typing import TYPE_CHECKING

# Import callback functions
from .callbacks_prop import toggle_3d_text_visibility
from . import callbacks_prop

# ============================================================================
# CAMERA AND HUD CALLBACK FUNCTIONS
# ============================================================================

def update_schedule_display_parent_constraint(context):
    """
    Finds the 'Schedule_Display_Parent' empty and updates its rotation and location constraints.
    Rotation and location can follow the active camera or custom targets.
    """
    import bpy
    import bonsai.tool as tool
    parent_name = "Schedule_Display_Parent"
    parent_empty = bpy.data.objects.get(parent_name)

    if not parent_empty:
        return

    # --- WORLD ORIGIN ANCHOR (Snapshot / Forced) ---
    # Respect persistent anchor mode even across resets.
    scene = getattr(context, 'scene', None)
    if scene is None:
        import bpy as _bpy
        scene = _bpy.context.scene

    force_world_origin = False
    try:
        # Explicit object-level override
        if parent_empty.get('anchor_mode') == 'WORLD_ORIGIN':
            force_world_origin = True
        # Scene-level persistence (survives object deletion/recreation)
        elif scene and scene.get('hud_anchor_mode') == 'WORLD_ORIGIN':
            force_world_origin = True
        else:
            # Heuristic: active camera is a snapshot camera
            active_cam = getattr(scene, 'camera', None)
            if active_cam and (active_cam.get('is_snapshot_camera') or
                               active_cam.get('camera_context') == 'snapshot' or
                               'Snapshot_Camera' in getattr(active_cam, 'name', '')):
                force_world_origin = True
    except Exception:
        pass
        
    # Also check for persistent world origin anchor mode
    try:
        camera_props = tool.Sequence.get_camera_orbit_props()
        if getattr(camera_props, 'force_world_origin_anchor', False):
            force_world_origin = True
            print("🔒 Persistent anchor mode active - forcing world origin anchoring")
    except Exception:
        pass

    # Clear all existing constraints on the parent empty
    parent_empty.constraints.clear()

    if force_world_origin:
        # Clear constraints and pin to world origin
        try:
            parent_empty.constraints.clear()
        except Exception:
            try:
                for c in list(parent_empty.constraints):
                    parent_empty.constraints.remove(c)
            except Exception:
                pass
        try:
            parent_empty.location = (0.0, 0.0, 0.0)
            parent_empty.rotation_euler = (0.0, 0.0, 0.0)
            parent_empty.scale = (1.0, 1.0, 1.0)
        except Exception:
            pass
        # Persist intent
        try:
            parent_empty['anchor_mode'] = 'WORLD_ORIGIN'
            if scene is not None:
                scene['hud_anchor_mode'] = 'WORLD_ORIGIN'
        except Exception:
            pass
        print("🌍 Schedule Display Parent: Anchored to world origin (0,0,0)")
        return

    # Get active camera from camera settings
    active_camera = None
    try:
        camera_props = tool.Sequence.get_camera_orbit_props()
        active_camera = getattr(camera_props, 'active_animation_camera', None)
    except Exception:
        pass

    # Fallback to scene camera if no active animation camera
    if not active_camera:
        active_camera = scene.camera

    if not active_camera:
        print("⚠️ No active camera found for Schedule Display Parent constraints")
        return

    # Add rotation constraint (always follow camera)
    rotation_constraint = parent_empty.constraints.new(type='COPY_ROTATION')
    rotation_constraint.target = active_camera
    rotation_constraint.name = "Follow_Camera_Rotation"

    # Add location constraint
    location_constraint = parent_empty.constraints.new(type='COPY_LOCATION')
    location_constraint.target = active_camera
    location_constraint.name = "Follow_Camera_Location"

    print(f"✅ Schedule Display Parent constraints updated to follow camera: {active_camera.name}")

def update_gpu_hud_visibility(self, context):
    """
    Smart callback to register/unregister the main GPU HUD handler.
    The handler is active if ANY of the HUD components are enabled.
    """
    try:
        is_any_hud_enabled = (
            getattr(self, "enable_text_hud", False) or
            getattr(self, "enable_timeline_hud", False) or
            getattr(self, "enable_legend_hud", False) or
            getattr(self, "enable_3d_legend_hud", False)
        )

        from .. import hud as hud_overlay

        def deferred_update():
            try:
                if is_any_hud_enabled:
                    if not hud_overlay.is_hud_enabled():
                        hud_overlay.register_hud_handler()
                else:
                    if hud_overlay.is_hud_enabled():
                        hud_overlay.unregister_hud_handler()
                
                # Force HUD refresh if enabled
                if is_any_hud_enabled:
                    try:
                        # Update 3D objects if 3D Legend HUD is active
                        if getattr(self, "enable_3d_legend_hud", False):
                            print("📋 3D Legend HUD is enabled - updating 3D objects")
                        hud_overlay.refresh_hud()
                    except Exception as e:
                        print(f"Error refreshing HUD: {e}")
                
                # Also refresh force_hud_refresh if enabled
                force_hud_refresh(self, context)
            except Exception as e:
                print(f"Deferred HUD update failed: {e}")
            return None
        if not bpy.app.timers.is_registered(deferred_update):
            bpy.app.timers.register(deferred_update, first_interval=0.05)
    except Exception as e:
        print(f"HUD visibility callback error: {e}")

def update_hud_gpu(self, context):
    """Callback to update GPU HUD"""
    try:
        if getattr(self, "enable_text_hud", False):
            def refresh_hud():
                try:
                    bpy.ops.bim.refresh_schedule_hud()
                except Exception:
                    pass
            bpy.app.timers.register(refresh_hud, first_interval=0.05)
    except Exception:
        pass

def force_hud_refresh(self, context):
    """Improved callback that forces HUD update with delay"""
    try:
        def delayed_refresh():
            try:
                # Ensure handlers are registered
                from .. import hud as hud_overlay
                
                # CRITICAL: Also update 3D Legend HUD when Legend HUD settings change
                try:
                    print(f"🔍 Checking if 3D Legend HUD should auto-update...")
                    enable_3d_legend = getattr(self, 'enable_3d_legend_hud', False)
                    print(f"  📋 enable_3d_legend_hud: {enable_3d_legend}")
                    
                    if enable_3d_legend:
                        # Check if 3D Legend HUD exists
                        hud_exists = any(obj.get("is_3d_legend_hud", False) for obj in bpy.data.objects)
                        print(f"  📋 3D Legend HUD exists in scene: {hud_exists}")
                        
                        if hud_exists:
                            print("🔄 AUTO-UPDATING 3D Legend HUD due to Legend HUD setting change")
                            try:
                                bpy.ops.bim.setup_3d_legend_hud()
                                print("✅ 3D Legend HUD auto-updated successfully")
                            except Exception as e:
                                print(f"⚠️ Could not auto-update 3D Legend HUD: {e}")
                        else:
                            print("ℹ️ 3D Legend HUD enabled but doesn't exist - will be created when needed")
                    else:
                        print("ℹ️ 3D Legend HUD is disabled - no auto-update needed")
                except Exception as e:
                    print(f"⚠️ Error checking 3D Legend HUD auto-update: {e}")
                
                # Rest of the refresh logic
                if hasattr(hud_overlay, 'refresh_hud'):
                    hud_overlay.refresh_hud()
                elif hasattr(hud_overlay, 'schedule_hud'):
                    hud_overlay.schedule_hud.invalidate_cache()
                    
            except Exception as e:
                print(f"❌ Error in delayed HUD refresh: {e}")
                import traceback
                traceback.print_exc()
            return None
            
        if not bpy.app.timers.is_registered(delayed_refresh):
            bpy.app.timers.register(delayed_refresh, first_interval=0.1)
    except Exception as e:
        print(f"❌ Error scheduling HUD refresh: {e}")

def update_animation_camera_visibility(self, context):
    """Toggles the visibility of animation cameras and their related objects in the viewport."""
    try:
        # Find animation cameras using simple checks
        cameras_to_toggle = []
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA':
                # Check if it's an animation camera
                if (obj.get('is_animation_camera') or 
                    obj.get('camera_context') == 'animation' or 
                    ('4D_Animation_Camera' in obj.name and 'Snapshot' not in obj.name)):
                    cameras_to_toggle.append(obj)

        objects_to_toggle = []
        for cam_obj in cameras_to_toggle:
            objects_to_toggle.append(cam_obj)

            # Find associated path and target objects by name convention
            path_name = f"4D_OrbitPath_for_{cam_obj.name}"
            target_name = f"4D_OrbitTarget_for_{cam_obj.name}"

            path_obj = bpy.data.objects.get(path_name)
            target_obj = bpy.data.objects.get(target_name)

            if path_obj:
                objects_to_toggle.append(path_obj)
            if target_obj:
                objects_to_toggle.append(target_obj)

        # Toggle visibility
        is_visible = self.show_animation_cameras
        for obj in objects_to_toggle:
            obj.hide_viewport = not is_visible

        print(f"{'Shown' if is_visible else 'Hidden'} {len(cameras_to_toggle)} animation cameras and {len(objects_to_toggle) - len(cameras_to_toggle)} related objects")

    except Exception as e:
        print(f"Error toggling animation camera visibility: {e}")

def update_snapshot_camera_visibility(self, context):
    """Toggles the visibility of snapshot cameras and their related objects in the viewport."""
    try:
        # Find snapshot cameras using simple checks
        cameras_to_toggle = []
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA':
                # Check if it's a snapshot camera
                if (obj.get('is_snapshot_camera') or 
                    obj.get('camera_context') == 'snapshot' or 
                    'Snapshot_Camera' in obj.name):
                    cameras_to_toggle.append(obj)

        objects_to_toggle = []
        for cam_obj in cameras_to_toggle:
            objects_to_toggle.append(cam_obj)

            # Find associated target objects
            target_name = f"Snapshot_Target"
            target_obj = bpy.data.objects.get(target_name)
            if target_obj:
                objects_to_toggle.append(target_obj)

        # Toggle visibility
        is_visible = self.show_snapshot_cameras
        for obj in objects_to_toggle:
            obj.hide_viewport = not is_visible

        print(f"{'Shown' if is_visible else 'Hidden'} {len(cameras_to_toggle)} snapshot cameras and {len(objects_to_toggle) - len(cameras_to_toggle)} related objects")

    except Exception as e:
        print(f"Error toggling snapshot camera visibility: {e}")

def force_hud_refresh(self, context):
    """Improved callback that forces HUD update with delay"""
    try:
        def delayed_refresh():
            try:
                # Ensure handlers are registered
                from .. import hud as hud_overlay
                
                # CRITICAL: Also update 3D Legend HUD when Legend HUD settings change
                try:
                    print(f"🔍 Checking if 3D Legend HUD should auto-update...")
                    enable_3d_legend = getattr(self, 'enable_3d_legend_hud', False)
                    print(f"  📋 enable_3d_legend_hud: {enable_3d_legend}")
                    
                    if enable_3d_legend:
                        # Check if 3D Legend HUD exists
                        hud_exists = any(obj.get("is_3d_legend_hud", False) for obj in bpy.data.objects)
                        print(f"  📋 3D Legend HUD exists in scene: {hud_exists}")
                        
                        if hud_exists:
                            print("🔄 AUTO-UPDATING 3D Legend HUD due to Legend HUD setting change")
                            try:
                                bpy.ops.bim.setup_3d_legend_hud()
                                print("✅ 3D Legend HUD auto-updated successfully")
                            except Exception as e:
                                print(f"⚠️ Could not auto-update 3D Legend HUD: {e}")
                        else:
                            print("ℹ️ 3D Legend HUD enabled but doesn't exist - will be created when needed")
                    else:
                        print("ℹ️ 3D Legend HUD is disabled - no auto-update needed")
                except Exception as e:
                    print(f"⚠️ Error checking 3D Legend HUD auto-update: {e}")
                
                # Legacy GPU HUD refresh
                hud_overlay.refresh_hud()
                print("🔄 GPU HUD refreshed via force_hud_refresh callback")
            except Exception as e:
                print(f"❌ Error in delayed_refresh: {e}")
            return None

        if not bpy.app.timers.is_registered(delayed_refresh):
            bpy.app.timers.register(delayed_refresh, first_interval=0.01)

    except Exception as e:
        print(f"Error scheduling HUD refresh: {e}")

def update_active_animation_camera(self, context):
    """
    Callback para establecer la cámara de animación como activa en la escena.
    """
    camera_obj = self.active_animation_camera
    if not camera_obj:
        return

    def set_camera_deferred():
        try:
            if camera_obj and bpy.context.scene:
                bpy.context.scene.camera = camera_obj
                print(f"✅ Animation camera '{camera_obj.name}' set as active")
                
                # Forzar actualización de la UI
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
        except Exception as e:
            print(f"❌ Error setting animation camera: {e}")
        return None

    bpy.app.timers.register(set_camera_deferred, first_interval=0.1)

def update_active_snapshot_camera(self, context):
    """
    Callback para establecer la cámara de snapshot como activa en la escena.
    """
    camera_obj = self.active_snapshot_camera
    if not camera_obj:
        return

    def set_camera_deferred():
        try:
            if camera_obj and bpy.context.scene:
                bpy.context.scene.camera = camera_obj
                print(f"✅ Snapshot camera '{camera_obj.name}' set as active")
                
                # Forzar actualización de la UI
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
        except Exception as e:
            print(f"❌ Error setting snapshot camera: {e}")
        return None

    bpy.app.timers.register(set_camera_deferred, first_interval=0.1)

def update_active_4d_camera(self, context):
    """
    Callback legacy para establecer la cámara de la escena cuando cambia la cámara 4D activa.
    Usa un temporizador para evitar problemas de contexto al modificar `scene.camera`.
    """
    camera_name = self.active_4d_camera.name if self.active_4d_camera else None
    if not camera_name:
        return

    def set_camera_deferred():
        try:
            if bpy.context.scene and self.active_4d_camera:
                bpy.context.scene.camera = self.active_4d_camera
                print(f"✅ 4D camera '{camera_name}' set as active scene camera")
                # Force UI refresh
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
        except Exception as e:
            print(f"❌ Error setting 4D camera: {e}")
        return None

    bpy.app.timers.register(set_camera_deferred, first_interval=0.01)

def update_legend_3d_hud_constraint(context):
    """
    Finds the 'HUD_3D_Legend' empty and updates its rotation and location constraints.
    Rotation and location can follow the active camera or custom targets.
    """
    import bpy
    import bonsai.tool as tool
    
    hud_empty = None
    for obj in bpy.data.objects:
        if obj.get("is_3d_legend_hud", False):
            hud_empty = obj
            break
    
    if not hud_empty:
        return

    # --- WORLD ORIGIN ANCHOR (Snapshot / Forced) ---
    scene = getattr(context, 'scene', None)
    if scene is None:
        import bpy as _bpy
        scene = _bpy.context.scene

    force_world_origin = False
    try:
        # Explicit object-level override
        if hud_empty.get('anchor_mode') == 'WORLD_ORIGIN':
            force_world_origin = True
        # Scene-level persistence (survives object deletion/recreation)
        elif scene and scene.get('hud_anchor_mode') == 'WORLD_ORIGIN':
            force_world_origin = True
        else:
            # Heuristic: active camera is a snapshot camera
            active_cam = getattr(scene, 'camera', None)
            if active_cam and (active_cam.get('is_snapshot_camera') or
                               active_cam.get('camera_context') == 'snapshot' or
                               'Snapshot_Camera' in getattr(active_cam, 'name', '')):
                force_world_origin = True
    except Exception:
        pass
        
    # Also check for persistent world origin anchor mode
    try:
        camera_props = tool.Sequence.get_camera_orbit_props()
        if getattr(camera_props, 'force_world_origin_anchor', False):
            force_world_origin = True
            print("🔒 Persistent anchor mode active - forcing world origin anchoring for 3D Legend HUD")
    except Exception:
        pass

    # Clear all existing constraints on the 3D legend HUD
    hud_empty.constraints.clear()

    if force_world_origin:
        # Clear constraints and pin to world origin
        try:
            hud_empty.constraints.clear()
        except Exception:
            try:
                for c in list(hud_empty.constraints):
                    hud_empty.constraints.remove(c)
            except Exception:
                pass
        try:
            hud_empty.location = (0.0, 0.0, 0.0)
            hud_empty.rotation_euler = (0.0, 0.0, 0.0)
            hud_empty.scale = (1.0, 1.0, 1.0)
        except Exception:
            pass
        # Persist intent
        try:
            hud_empty['anchor_mode'] = 'WORLD_ORIGIN'
            if scene is not None:
                scene['hud_anchor_mode'] = 'WORLD_ORIGIN'
        except Exception:
            pass
        print("🌍 3D Legend HUD: Anchored to world origin (0,0,0)")
        return

    # Get active camera from camera settings
    active_camera = None
    try:
        camera_props = tool.Sequence.get_camera_orbit_props()
        active_camera = getattr(camera_props, 'active_animation_camera', None)
    except Exception:
        pass

    # Fallback to scene camera if no active animation camera
    if not active_camera:
        active_camera = scene.camera

    if not active_camera:
        print("⚠️ No active camera found for 3D Legend HUD constraints")
        return

    # Get custom targets from camera properties
    try:
        camera_props = tool.Sequence.get_camera_orbit_props()
        use_custom_rotation = getattr(camera_props, 'legend_3d_hud_use_custom_rotation_target', False)
        rotation_target = getattr(camera_props, 'legend_3d_hud_rotation_target', None) if use_custom_rotation else None
        use_custom_location = getattr(camera_props, 'legend_3d_hud_use_custom_location_target', False)
        location_target = getattr(camera_props, 'legend_3d_hud_location_target', None) if use_custom_location else None
    except Exception:
        rotation_target = None
        location_target = None

    # Add rotation constraint
    final_rotation_target = rotation_target if rotation_target else active_camera
    if final_rotation_target:
        rotation_constraint = hud_empty.constraints.new(type='COPY_ROTATION')
        rotation_constraint.target = final_rotation_target
        rotation_constraint.name = "Follow_Rotation"
        print(f"✅ 3D Legend HUD rotation follows: {final_rotation_target.name}")

    # Add location constraint  
    final_location_target = location_target if location_target else active_camera
    if final_location_target:
        location_constraint = hud_empty.constraints.new(type='COPY_LOCATION')
        location_constraint.target = final_location_target
        location_constraint.name = "Follow_Location"
        print(f"✅ 3D Legend HUD location follows: {final_location_target.name}")

# ============================================================================
# CAMERA AND HUD PROPERTY GROUP CLASSES
# ============================================================================

class BIMCameraOrbitProperties(PropertyGroup):
    """Properties for camera orbit, HUD display, and 3D timeline management"""
    
    # =====================
    # Camera settings
    # =====================
    camera_focal_mm: FloatProperty(
        name="Focal (mm)",
        default=35.0,
        min=1.0,
        max=300.0,
        description="Camera focal length in millimeters",
    )
    camera_clip_start: FloatProperty(
        name="Clip Start",
        default=0.1,
        min=0.0001,
        description="Camera near clipping distance",
    )
    camera_clip_end: FloatProperty(
        name="Clip End",
        default=10000.0,
        min=1.0,
        description="Camera far clipping distance",
    )
    
    # Camera look at settings
    look_at_mode: EnumProperty(
        name="Look At",
        items=[
            ("AUTO", "Auto (active WorkSchedule area)", "Use bbox center of active WorkSchedule"),
            ("OBJECT", "Object", "Select object/Empty as target"),
        ],
        default="AUTO",
    )
    look_at_object: PointerProperty(
        name="Target",
        type=bpy.types.Object,
        description="Object to look at during camera animation",
    )

    # Animation and snapshot camera selection
    active_animation_camera: PointerProperty(
        type=bpy.types.Object,
        name="Animation Camera",
        description="Camera used for 4D animation sequences",
        poll=lambda self, obj: obj.type == 'CAMERA',
        update=update_active_animation_camera,
    )
    active_snapshot_camera: PointerProperty(
        type=bpy.types.Object,
        name="Snapshot Camera",
        description="Camera used for schedule snapshots",
        poll=lambda self, obj: obj.type == 'CAMERA',
        update=update_active_snapshot_camera,
    )
    
    # Legacy 4D camera property for backward compatibility
    active_4d_camera: PointerProperty(
        type=bpy.types.Object,
        name="4D Camera",
        description="Legacy camera property for 4D animation sequences",
        poll=lambda self, obj: obj.type == 'CAMERA',
        update=update_active_4d_camera,
    )

    # Camera visibility controls
    show_animation_cameras: BoolProperty(
        name="Show Animation Cameras",
        description="Toggle visibility of animation cameras and related objects in viewport",
        default=True,
        update=update_animation_camera_visibility,
    )
    show_snapshot_cameras: BoolProperty(
        name="Show Snapshot Cameras", 
        description="Toggle visibility of snapshot cameras and related objects in viewport",
        default=True,
        update=update_snapshot_camera_visibility,
    )
    show_camera_orbit_settings: BoolProperty(
        name="Show Camera & Orbit Settings",
        description="Toggle visibility of camera and orbit configuration settings",
        default=False,
    )

    # =====================
    # HUD System
    # =====================
    # Global HUD toggle
    enable_text_hud: BoolProperty(
        name="Enable Schedule HUD",
        description="Display schedule information as an overlay in the viewport",
        default=False,
        update=update_gpu_hud_visibility,
    )
    
    # 3D HUD Render toggle
    show_3d_schedule_texts: BoolProperty(
        name="Show 3D HUD Render",
        description="Toggle visibility of the 3D objects used as a Heads-Up Display (HUD) for rendering",
        default=False,
        update=lambda self, context: toggle_3d_text_visibility(self, context),
    )
    
    # 3D HUD Render expandable section
    expand_3d_hud_render: BoolProperty(
        name="Expand 3D HUD Render",
        default=False,
        description="Show/hide 3D HUD Render settings"
    )
    
    # HUD content toggles
    hud_show_date: BoolProperty(
        name="Date", 
        description="Show date information in HUD",
        default=True, 
        update=update_hud_gpu
    )
    hud_show_week: BoolProperty(
        name="Week", 
        description="Show week information in HUD",
        default=True, 
        update=update_hud_gpu
    )
    hud_show_day: BoolProperty(
        name="Day", 
        description="Show day information in HUD",
        default=False, 
        update=update_hud_gpu
    )
    hud_show_progress: BoolProperty(
        name="Progress", 
        description="Show progress information in HUD",
        default=False, 
        update=update_hud_gpu
    )
    expand_hud_settings: BoolProperty(
        name="Expand HUD Settings",
        description="Show/hide detailed HUD configuration options",
        default=False,
    )
    expand_schedule_hud: BoolProperty(
        name="Expand Schedule HUD",
        default=False,
        description="Show/hide Schedule HUD settings"
    )
    
    # Schedule HUD content controls (from v57)
    hud_show_date: BoolProperty(
        name="Date", 
        default=True, 
        update=force_hud_refresh
    )
    hud_show_week: BoolProperty(
        name="Week", 
        default=True, 
        update=force_hud_refresh
    )
    hud_show_day: BoolProperty(
        name="Day", 
        default=False, 
        update=force_hud_refresh
    )
    hud_show_progress: BoolProperty(
        name="Progress", 
        default=False, 
        update=force_hud_refresh
    )
    expand_timeline_hud: BoolProperty(
        name="Expand Timeline HUD",
        default=False,
        description="Show/hide Timeline HUD settings"
    )
    expand_legend_hud: BoolProperty(
        name="Expand Legend HUD",
        default=False,
        description="Show/hide Legend HUD settings"
    )

    # Position and layout
    hud_position: EnumProperty(
        name="Position",
        items=[
            ("TOP_RIGHT", "Top Right", ""),
            ("TOP_LEFT", "Top Left", ""),
            ("BOTTOM_RIGHT", "Bottom Right", ""),
            ("BOTTOM_LEFT", "Bottom Left", ""),
        ],
        default="BOTTOM_LEFT",
        update=force_hud_refresh,
    )
    hud_scale_factor: FloatProperty(
        name="Scale",
        default=1.0,
        min=0.1,
        max=5.0,
        precision=2,
        update=force_hud_refresh,
    )
    hud_margin_horizontal: FloatProperty(
        name="H-Margin",
        default=0.05,
        min=0.0,
        max=0.3,
        precision=3,
        update=force_hud_refresh,
    )
    hud_margin_vertical: FloatProperty(
        name="V-Margin",
        default=0.05,
        min=0.0,
        max=0.3,
        precision=3,
        update=force_hud_refresh,
    )

    # Base colors (RGBA)
    hud_text_color: FloatVectorProperty(
        name="Text Color",
        subtype="COLOR",
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )
    hud_background_color: FloatVectorProperty(
        name="Background Color",
        subtype="COLOR",
        size=4,
        default=(0.09, 0.114, 0.102, 0.102),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )

    # =====================
    # HUD VISUAL ENHANCEMENTS
    # =====================
    # Spacing & alignment
    hud_text_spacing: FloatProperty(
        name="Line Spacing",
        description="Vertical spacing between HUD text lines",
        default=0.02,
        min=0.0,
        max=0.3,
        precision=3,
        update=force_hud_refresh,
    )
    hud_text_alignment: EnumProperty(
        name="Text Alignment",
        items=[
            ("LEFT", "Left", "Align text to the left"),
            ("CENTER", "Center", "Center align text"),
            ("RIGHT", "Right", "Align text to the right"),
        ],
        default="LEFT",
        update=force_hud_refresh,
    )

    # Panel padding
    hud_padding_horizontal: FloatProperty(
        name="H-Padding",
        description="Horizontal padding inside the HUD panel",
        default=10.0,
        min=0.0,
        max=50.0,
        update=force_hud_refresh,
    )
    hud_padding_vertical: FloatProperty(
        name="V-Padding",
        description="Vertical padding inside the HUD panel",
        default=8.0,
        min=0.0,
        max=50.0,
        update=force_hud_refresh,
    )

    # Borders
    hud_border_radius: FloatProperty(
        name="Border Radius",
        description="Corner rounding of the HUD background",
        default=20.0,
        min=0.0,
        max=50.0,
        update=force_hud_refresh,
    )
    hud_border_width: FloatProperty(
        name="Border Width",
        description="Width of the HUD border",
        default=0.0,
        min=0.0,
        max=5.0,
        update=force_hud_refresh,
    )
    hud_border_color: FloatVectorProperty(
        name="Border Color",
        subtype="COLOR",
        size=4,
        default=(1.0, 1.0, 1.0, 0.5),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )

    # Text shadow
    hud_text_shadow_enabled: BoolProperty(
        name="Text Shadow",
        description="Enable text shadow for better readability",
        default=True,
        update=force_hud_refresh,
    )
    hud_text_shadow_offset_x: FloatProperty(
        name="Shadow Offset X",
        description="Horizontal offset of text shadow",
        default=1.0,
        min=-10.0,
        max=10.0,
        update=force_hud_refresh,
    )
    hud_text_shadow_offset_y: FloatProperty(
        name="Shadow Offset Y",
        description="Vertical offset of text shadow",
        default=-1.0,
        min=-10.0,
        max=10.0,
        update=force_hud_refresh,
    )
    hud_text_shadow_color: FloatVectorProperty(
        name="Shadow Color",
        subtype="COLOR",
        size=4,
        default=(0.0, 0.0, 0.0, 0.8),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )

    # Background drop shadow
    hud_background_shadow_enabled: BoolProperty(
        name="Background Shadow",
        description="Enable drop shadow for the HUD background",
        default=False,
        update=force_hud_refresh,
    )
    hud_background_shadow_offset_x: FloatProperty(
        name="BG Shadow Offset X",
        default=3.0,
        min=-20.0,
        max=20.0,
        update=force_hud_refresh,
    )
    hud_background_shadow_offset_y: FloatProperty(
        name="BG Shadow Offset Y",
        default=-3.0,
        min=-20.0,
        max=20.0,
        update=force_hud_refresh,
    )
    hud_background_shadow_blur: FloatProperty(
        name="BG Shadow Blur",
        description="Blur radius of the background shadow",
        default=5.0,
        min=0.0,
        max=20.0,
        update=force_hud_refresh,
    )
    hud_background_shadow_color: FloatVectorProperty(
        name="BG Shadow Color",
        subtype="COLOR",
        size=4,
        default=(0.0, 0.0, 0.0, 0.6),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )

    # Typography
    hud_font_weight: EnumProperty(
        name="Font Weight",
        items=[
            ("NORMAL", "Normal", "Normal font weight"),
            ("BOLD", "Bold", "Bold font weight"),
        ],
        default="NORMAL",
        update=force_hud_refresh,
    )
    hud_letter_spacing: FloatProperty(
        name="Letter Spacing",
        description="Spacing between characters (tracking)",
        default=0.0,
        min=-2.0,
        max=5.0,
        precision=2,
        update=force_hud_refresh,
    )

    # Background gradient
    hud_background_gradient_enabled: BoolProperty(
        name="Background Gradient",
        description="Enable gradient background instead of solid color",
        default=False,
        update=force_hud_refresh,
    )
    hud_background_gradient_color: FloatVectorProperty(
        name="Gradient Color",
        subtype="COLOR",
        size=4,
        default=(0.1, 0.1, 0.1, 0.9),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )
    hud_gradient_direction: EnumProperty(
        name="Gradient Direction",
        items=[
            ("VERTICAL", "Vertical", "Top to bottom gradient"),
            ("HORIZONTAL", "Horizontal", "Left to right gradient"),
            ("DIAGONAL", "Diagonal", "Diagonal gradient"),
        ],
        default="VERTICAL",
        update=force_hud_refresh,
    )

    # ==========================================
    # === TIMELINE HUD (GPU) - PROPIEDADES NUEVAS ===
    # ==========================================
    enable_timeline_hud: BoolProperty(
        name="Enable Timeline HUD",
        description="Show a graphical timeline at the bottom/top of the viewport",
        default=False,
        update=update_gpu_hud_visibility,
    )
    timeline_hud_position: EnumProperty(
        name="Timeline Position",
        items=[
            ('BOTTOM', "Bottom", "Place the timeline at the bottom"),
            ('TOP', "Top", "Place the timeline at the top"),
        ],
        default='BOTTOM',
        update=force_hud_refresh,
    )
    timeline_hud_margin_vertical: FloatProperty(
        name="V-Margin",
        description="Vertical margin from the viewport edge, as a percentage of viewport height",
        default=0.05,
        min=0.0,
        max=0.45,
        subtype='FACTOR',
        precision=3,
        update=force_hud_refresh,
    )
    timeline_hud_margin_horizontal: FloatProperty(
        name="H-Margin",
        description="Horizontal offset from the center, as a percentage of viewport width. 0 is center.",
        default=0.055,
        min=-0.4,
        max=0.4,
        subtype='FACTOR',
        precision=3,
        update=force_hud_refresh,
    )
    timeline_hud_zoom_level: EnumProperty(
        name="Timeline Zoom",
        items=[
            ('MONTHS', "Months", "Show years and months"),
            ('WEEKS', "Weeks", "Show weeks and days"),
            ('DAYS', "Days", "Show individual days"),
        ],
        default='MONTHS',
        update=force_hud_refresh,
    )
    timeline_hud_height: FloatProperty(
        name="Height (px)",
        description="Height of the timeline bar in pixels",
        default=40.0,
        min=20.0,
        max=100.0,
        update=force_hud_refresh,
    )
    timeline_hud_color_inactive_range: FloatVectorProperty(
        name="Inactive Range Color",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(0.588, 0.953, 0.745, 0.1),
        update=force_hud_refresh,
    )
    timeline_hud_color_active_range: FloatVectorProperty(
        name="Active Range Color",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(0.588, 0.953, 0.745, 0.1),
        update=force_hud_refresh,
    )
    timeline_hud_color_progress: FloatVectorProperty(
        name="Progress Bar Color",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(0.122, 0.663, 0.976, 0.102),  # #1FA9F91A
        update=force_hud_refresh,
    )
    timeline_hud_color_text: FloatVectorProperty(
        name="Timeline Text Color",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(1.0, 1.0, 1.0, 1.0),
        update=force_hud_refresh,
    )
    timeline_hud_border_radius: FloatProperty(
        name="Timeline Border Radius",
        description="Round corner radius for timeline HUD",
        default=10.0, min=0.0, max=50.0,
        update=force_hud_refresh,
    )
    timeline_hud_show_progress_bar: BoolProperty(
        name="Show Progress Bar",
        description="Display progress bar in timeline HUD",
        default=True,
        update=force_hud_refresh,
    )

    # ==================== LEGEND HUD PROPERTIES ====================
    
    enable_legend_hud: BoolProperty(
        name="Enable Legend HUD",
        description="Display legend HUD with active animation colortypes and their colors",
        default=False,
        update=update_gpu_hud_visibility,
    )
    
    legend_hud_position: EnumProperty(
        name="Position",
        description="Screen position of the legend HUD",
        items=[
            ('TOP_LEFT', "Top Left", "Position at the top-left corner"),
            ('TOP_RIGHT', "Top Right", "Position at the top-right corner"),
            ('BOTTOM_LEFT', "Bottom Left", "Position at the bottom-left corner"),
            ('BOTTOM_RIGHT', "Bottom Right", "Position at the bottom-right corner"),
            ('CENTER_LEFT', "Center Left", "Position at the center-left side"),
            ('CENTER_RIGHT', "Center Right", "Position at the center-right side"),
        ],
        default='TOP_RIGHT',
        update=force_hud_refresh,
    )
    
    legend_hud_margin_horizontal: FloatProperty(
        name="H-Margin",
        description="Horizontal margin from screen edge",
        default=0.02,
        min=0.0,
        max=0.45,
        precision=3,
        update=force_hud_refresh,
    )
    
    legend_hud_margin_vertical: FloatProperty(
        name="V-Margin", 
        description="Vertical margin from screen edge",
        default=0.02,
        min=0.0,
        max=0.45,
        precision=3,
        update=force_hud_refresh,
    )

    legend_hud_scale_factor: FloatProperty(
        name="Scale",
        description="Scale factor for the legend HUD",
        default=1.0,
        min=0.3,
        max=3.0,
        precision=2,
        update=force_hud_refresh,
    )

    # Legend visual properties
    legend_hud_background_color: FloatVectorProperty(
        name="Background Color",
        subtype='COLOR',
        size=4,
        default=(0.0, 0.0, 0.0, 0.7),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )

    legend_hud_text_color: FloatVectorProperty(
        name="Text Color",
        subtype='COLOR',
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        update=force_hud_refresh,
    )

    legend_hud_padding: FloatProperty(
        name="Padding",
        description="Internal padding of the legend panel",
        default=10.0,
        min=0.0,
        max=50.0,
        update=force_hud_refresh,
    )

    legend_hud_border_radius: FloatProperty(
        name="Border Radius",
        description="Corner radius of the legend background",
        default=8.0,
        min=0.0,
        max=20.0,
        update=force_hud_refresh,
    )

    legend_hud_item_spacing: FloatProperty(
        name="Item Spacing",
        description="Spacing between legend items",
        default=2.0,
        min=0.0,
        max=20.0,
        update=force_hud_refresh,
    )

    legend_hud_color_box_size: FloatProperty(
        name="Color Box Size",
        description="Size of the color indicator boxes",
        default=12.0,
        min=4.0,
        max=30.0,
        update=force_hud_refresh,
    )

    # Advanced legend options
    legend_hud_show_task_count: BoolProperty(
        name="Show Task Count",
        description="Display the number of tasks for each colortype",
        default=True,
        update=force_hud_refresh,
    )

    legend_hud_show_inactive_types: BoolProperty(
        name="Show Inactive Types",
        description="Include colortypes that are not currently active in the legend",
        default=False,
        update=force_hud_refresh,
    )

    legend_hud_max_items: IntProperty(
        name="Max Items",
        description="Maximum number of legend items to display",
        default=15,
        min=1,
        max=50,
        update=force_hud_refresh,
    )

    # ==================== 3D LEGEND HUD PROPERTIES ====================
    
    enable_3d_legend_hud: BoolProperty(
        name="Enable 3D Legend HUD",
        description="Create 3D text objects in the scene for the legend instead of GPU overlay",
        default=False,
        update=lambda self, context: callbacks_prop.update_gpu_hud_visibility(self, context),
    )

    # 3D Legend positioning
    legend_3d_location: FloatVectorProperty(
        name="3D Location",
        description="World space location for the 3D legend",
        subtype='TRANSLATION',
        size=3,
        default=(10.0, 0.0, 5.0),
        update=force_hud_refresh,
    )

    legend_3d_scale: FloatProperty(
        name="3D Scale",
        description="Scale factor for 3D legend text objects",
        default=1.0,
        min=0.1,
        max=10.0,
        precision=2,
        update=force_hud_refresh,
    )

    legend_3d_spacing: FloatProperty(
        name="3D Spacing",
        description="Vertical spacing between 3D legend items",
        default=2.0,
        min=0.1,
        max=10.0,
        precision=2,
        update=force_hud_refresh,
    )

    legend_3d_always_face_camera: BoolProperty(
        name="Always Face Camera",
        description="Make 3D legend text always face the active camera",
        default=True,
        update=force_hud_refresh,
    )

    legend_3d_hud_distance: FloatProperty(
        name="3D HUD Distance",
        description="Distance from camera to place 3D Legend HUD elements",
        default=2.2,
        min=0.1,
        max=20.0,
        precision=2,
        update=force_hud_refresh,
    )

    legend_hud_scale: FloatProperty(
        name="Legend HUD Scale",
        description="Scale factor for 3D Legend HUD elements",
        default=1.0,
        min=0.1,
        max=5.0,
        precision=2,
        update=force_hud_refresh,
    )

    legend_3d_hud_pos_x: FloatProperty(
        name="HUD Position X",
        description="Horizontal position in camera space",
        default=-3.6,
        min=-10.0,
        max=10.0,
        precision=2,
        update=force_hud_refresh,
    )
    
    legend_3d_hud_pos_y: FloatProperty(
        name="HUD Position Y", 
        description="Vertical position in camera space",
        default=1.4,
        min=-10.0,
        max=10.0,
        precision=2,
        update=force_hud_refresh,
    )

    legend_3d_hud_scale: FloatProperty(
        name="HUD Scale",
        description="Overall scale of the 3D Legend HUD",
        default=1.0,
        min=0.1,
        max=5.0,
        precision=2,
        update=force_hud_refresh,
    )
    
    # Panel Settings
    legend_3d_panel_width: FloatProperty(
        name="Panel Width",
        description="Width of the legend panel",
        default=2.2,
        min=0.5,
        max=10.0,
        precision=2,
        update=force_hud_refresh,
    )

    # Anchor system for displaying schedules and HUD elements
    force_world_origin_anchor: BoolProperty(
        name="Force World Origin Anchor",
        description="Force all HUD and schedule displays to anchor at world origin instead of following camera",
        default=False,
        update=lambda self, context: update_schedule_display_parent_constraint(context),
    )
    
    # =============================
    # CUSTOM CONSTRAINT TARGETS FOR SCHEDULE DISPLAY PARENT
    # =============================
    use_custom_rotation_target: BoolProperty(
        name="Use Custom Rotation Target",
        description="Override the default camera tracking and constrain the rotation of the 3D text group to a specific object",
        default=False,
        update=lambda self, context: update_schedule_display_parent_constraint(context)
    )
    schedule_display_rotation_target: PointerProperty(
        name="Rotation Target",
        type=bpy.types.Object,
        description="Object to which the 3D text group's rotation will be constrained",
        poll=lambda self, obj: obj.type in {'CAMERA', 'EMPTY'},
        update=lambda self, context: update_schedule_display_parent_constraint(context)
    )
    use_custom_location_target: BoolProperty(
        name="Use Custom Location Target",
        description="Override the default camera tracking and constrain the location of the 3D text group to a specific object",
        default=False,
        update=lambda self, context: update_schedule_display_parent_constraint(context)
    )
    schedule_display_location_target: PointerProperty(
        name="Location Target",
        type=bpy.types.Object,
        description="Object to which the 3D text group's location will be constrained",
        poll=lambda self, obj: obj.type in {'CAMERA', 'EMPTY'},
        update=lambda self, context: update_schedule_display_parent_constraint(context)
    )
    
    # =============================
    # CUSTOM CONSTRAINT TARGETS FOR 3D LEGEND HUD
    # =============================
    legend_3d_hud_use_custom_rotation_target: BoolProperty(
        name="Use Custom Rotation Target",
        description="Override the default camera tracking and constrain the rotation of the 3D Legend HUD to a specific object",
        default=False,
        update=lambda self, context: update_legend_3d_hud_constraint(context)
    )
    legend_3d_hud_rotation_target: PointerProperty(
        name="Rotation Target",
        type=bpy.types.Object,
        description="Object to which the 3D Legend HUD's rotation will be constrained",
        poll=lambda self, obj: obj.type in {'CAMERA', 'EMPTY'},
        update=lambda self, context: update_legend_3d_hud_constraint(context)
    )
    legend_3d_hud_use_custom_location_target: BoolProperty(
        name="Use Custom Location Target",
        description="Override the default camera tracking and constrain the location of the 3D Legend HUD to a specific object",
        default=False,
        update=lambda self, context: update_legend_3d_hud_constraint(context)
    )
    legend_3d_hud_location_target: PointerProperty(
        name="Location Target",
        type=bpy.types.Object,
        description="Object to which the 3D Legend HUD's location will be constrained",
        poll=lambda self, obj: obj.type in {'CAMERA', 'EMPTY'},
        update=lambda self, context: update_legend_3d_hud_constraint(context)
    )

    # ==================== LEGEND HUD PROPERTIES (from v57) ====================
    expand_legend_hud: BoolProperty(
        name="Expand Legend HUD",
        description="Show/hide Legend HUD settings",
        default=False
    )
    
    enable_legend_hud: BoolProperty(
        name="Enable Legend HUD",
        description="Display legend HUD with active animation colortypes and their colors",
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_position: EnumProperty(
        name="Position",
        description="Screen position of the legend HUD",
        items=[
            ('TOP_LEFT', "Top Left", "Position at the top-left corner"),
            ('TOP_RIGHT', "Top Right", "Position at the top-right corner"),
            ('BOTTOM_LEFT', "Bottom Left", "Position at the bottom-left corner"),
            ('BOTTOM_RIGHT', "Bottom Right", "Position at the bottom-right corner"),
        ],
        default="TOP_LEFT",
        update=force_hud_refresh,
    )
    
    legend_hud_margin_horizontal: FloatProperty(
        name="Horizontal Margin",
        description="Horizontal margin from screen edges",
        default=0.05,
        min=0.0,
        max=0.5,
        update=force_hud_refresh,
    )
    
    legend_hud_margin_vertical: FloatProperty(
        name="Vertical Margin",
        description="Vertical margin from screen edges",
        default=0.5,
        min=0.0,
        max=0.5,
        update=force_hud_refresh,
    )
    
    legend_hud_orientation: EnumProperty(
        name="Orientation",
        description="Layout orientation of legend items",
        items=[
            ("VERTICAL", "Vertical", "Stack items vertically"),
            ("HORIZONTAL", "Horizontal", "Arrange items horizontally"),
        ],
        default="VERTICAL",
        update=force_hud_refresh,
    )
    
    legend_hud_scale: FloatProperty(
        name="Scale",
        description="Overall scale factor for legend HUD",
        default=1.0,
        min=0.1,
        max=3.0,
        update=force_hud_refresh,
    )
    
    legend_hud_background_color: FloatVectorProperty(
        name="Background Color",
        description="Background color of legend HUD",
        default=(0.0, 0.0, 0.0, 0.8),
        min=0.0,
        max=1.0,
        size=4,
        subtype="COLOR",
        update=force_hud_refresh,
    )
    
    legend_hud_border_radius: FloatProperty(
        name="Border Radius",
        description="Corner rounding radius for legend background",
        default=5.0,
        min=0.0,
        max=50.0,
        update=force_hud_refresh,
    )
    
    legend_hud_padding_horizontal: FloatProperty(
        name="Horizontal Padding",
        description="Horizontal padding inside legend background",
        default=12.0,
        min=0.0,
        max=50.0,
        update=force_hud_refresh,
    )
    
    legend_hud_padding_vertical: FloatProperty(
        name="Vertical Padding",
        description="Vertical padding inside legend background",
        default=8.0,
        min=0.0,
        max=50.0,
        update=force_hud_refresh,
    )
    
    legend_hud_item_spacing: FloatProperty(
        name="Item Spacing",
        description="Spacing between legend items",
        default=8.0,
        min=0.0,
        max=30.0,
        update=force_hud_refresh,
    )
    
    legend_hud_text_color: FloatVectorProperty(
        name="Text Color",
        description="Color of legend text",
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        size=4,
        subtype="COLOR",
        update=force_hud_refresh,
    )
    
    legend_hud_show_title: BoolProperty(
        name="Show Title",
        description="Display title at the top of legend",
        default=True,
        update=force_hud_refresh,
    )
    
    legend_hud_title_text: StringProperty(
        name="Title Text",
        description="Text to display as legend title",
        default="Legend",
        update=force_hud_refresh,
    )
    
    legend_hud_title_color: FloatVectorProperty(
        name="Title Color",
        description="Color of legend title text",
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        size=4,
        subtype="COLOR",
        update=force_hud_refresh,
    )
    
    legend_hud_color_indicator_size: FloatProperty(
        name="Color Indicator Size",
        description="Size of color indicator squares",
        default=12.0,
        min=4.0,
        max=32.0,
        update=force_hud_refresh,
    )
    
    legend_hud_text_shadow_enabled: BoolProperty(
        name="Text Shadow",
        description="Enable text shadow for better visibility",
        default=True,
        update=force_hud_refresh,
    )
    
    legend_hud_text_shadow_color: FloatVectorProperty(
        name="Shadow Color",
        description="Color of text shadow",
        default=(0.0, 0.0, 0.0, 0.8),
        min=0.0,
        max=1.0,
        size=4,
        subtype="COLOR",
        update=force_hud_refresh,
    )
    
    legend_hud_text_shadow_offset_x: FloatProperty(
        name="Shadow Offset X",
        description="Horizontal offset of text shadow",
        default=1.0,
        min=-10.0,
        max=10.0,
        update=force_hud_refresh,
    )
    
    legend_hud_text_shadow_offset_y: FloatProperty(
        name="Shadow Offset Y",
        description="Vertical offset of text shadow",
        default=-1.0,
        min=-10.0,
        max=10.0,
        update=force_hud_refresh,
    )
    
    legend_hud_auto_scale: BoolProperty(
        name="Auto Scale",
        description="Automatically scale legend to fit content",
        default=True,
        update=force_hud_refresh,
    )
    
    legend_hud_max_width: FloatProperty(
        name="Max Width",
        description="Maximum width as proportion of viewport width",
        default=0.3,
        min=0.1,
        max=0.8,
        update=force_hud_refresh,
    )
    
    # ==================== LEGEND HUD COLOR COLUMNS ====================
    legend_hud_show_start_column: BoolProperty(
        name="Show Start Colors",
        description="Display start state colors column",
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_show_active_column: BoolProperty(
        name="Show Active Colors",
        description="Display active/in-progress state colors column",
        default=True,
        update=force_hud_refresh,
    )
    
    legend_hud_show_end_column: BoolProperty(
        name="Show End Colors",
        description="Display end/finished state colors column",
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_show_start_title: BoolProperty(
        name="Show 'Start' Title",
        description="Display 'Start' column title",
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_show_active_title: BoolProperty(
        name="Show 'Active' Title", 
        description="Display 'Active' column title",
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_show_end_title: BoolProperty(
        name="Show 'End' Title",
        description="Display 'End' column title", 
        default=False,
        update=force_hud_refresh,
    )
    
    legend_hud_column_spacing: FloatProperty(
        name="Column Spacing",
        description="Spacing between color columns",
        default=16.0,
        min=4.0,
        max=50.0,
        update=force_hud_refresh,
    )
    
    legend_hud_title_font_size: FloatProperty(
        name="Title Font Size",
        description="Font size for the legend title",
        default=16.0,
        min=8.0,
        max=48.0,
        update=force_hud_refresh,
    )
    
    legend_hud_visible_colortypes: StringProperty(
        name="Hidden colortypes",
        description="Comma-separated list of colortype names to hide in legend (all colortypes visible by default)",
        default="",
        update=force_hud_refresh,
    )
    
    legend_hud_colortype_scroll_offset: IntProperty(
        name="colortype List Scroll Offset",
        description="Current scroll position in the colortype list",
        default=0,
        min=0,
    )

    # Camera orbit controls
    orbit_speed: FloatProperty(
        name="Orbit Speed",
        description="Speed of camera orbit animation",
        default=1.0,
        min=0.1,
        max=5.0,
        precision=2,
    )
    
    orbit_radius: FloatProperty(
        name="Orbit Radius", 
        description="Radius of camera orbit path",
        default=10.0,
        min=1.0,
        max=100.0,
        precision=1,
    )
    
    orbit_radius_mode: EnumProperty(
        name="Radius Mode",
        items=[
            ("AUTO", "Auto (from bbox)", "Compute radius from WorkSchedule bbox"),
            ("MANUAL", "Manual", "Use manual radius value")
        ],
        default="AUTO",
        description="Mode for determining camera orbit radius",
    )
    
    # Additional orbit properties
    orbit_mode: EnumProperty(
        name="Orbit Mode",
        items=[
            ("NONE", "None (Static)", "No orbit animation"),
            ("CIRCLE_360", "Circle 360°", "Full circular orbit"),
            ("PINGPONG", "Ping-Pong", "Back and forth over an arc"),
        ],
        default="CIRCLE_360",
        description="Type of orbit animation to perform",
    )
    
    orbit_height: FloatProperty(
        name="Height (Z offset)",
        description="Height offset for camera orbit path",
        default=8.0,
        min=-100.0,
        max=100.0,
        precision=2,
    )
    
    orbit_start_angle_deg: FloatProperty(
        name="Start Angle (deg)",
        description="Starting angle for orbit animation in degrees",
        default=0.0,
        min=0.0,
        max=360.0,
        precision=1,
    )
    
    orbit_direction: EnumProperty(
        name="Direction",
        items=[
            ("CCW", "CCW", "Counter-clockwise"),
            ("CW", "CW", "Clockwise")
        ],
        default="CCW",
        description="Direction of orbit rotation",
    )
    
    # Path shape and custom path properties
    orbit_path_shape: EnumProperty(
        name="Path Shape",
        items=[
            ('CIRCLE', "Circle (Generated)", "The add-on creates a perfect circle"),
            ('CUSTOM', "Custom Path", "Use your own curve object as the path"),
        ],
        default='CIRCLE',
        description="Shape of the orbit path",
    )
    
    custom_orbit_path: PointerProperty(
        name="Custom Path",
        type=bpy.types.Object,
        description="Custom curve object to use as orbit path",
        poll=lambda self, obj: obj.type == 'CURVE',
    )
    
    # Interpolation properties
    interpolation_mode: EnumProperty(
        name="Interpolation",
        items=[
            ('LINEAR', "Linear (Constant Speed)", "Constant, mechanical speed"),
            ('BEZIER', "Bezier (Smooth)", "Smooth ease-in and ease-out for a natural feel"),
        ],
        default='LINEAR',
        description="Interpolation method for camera movement",
    )
    
    bezier_smoothness_factor: FloatProperty(
        name="Smoothness Factor",
        description="Controls the intensity of the ease-in/ease-out. Higher values create a more gradual transition",
        default=0.35,
        min=0.0,
        max=2.0,
        precision=3,
    )
    
    # Animation method and duration
    orbit_path_method: EnumProperty(
        name="Path Method",
        items=[
            ("FOLLOW_PATH", "Follow Path (editable)", "Bezier circle + Follow Path"),
            ("KEYFRAMES", "Keyframes (lightweight)", "Animate location directly")
        ],
        default="FOLLOW_PATH",
        description="Method used to animate camera along orbit path",
    )
    
    orbit_use_4d_duration: BoolProperty(
        name="Use 4D total frames",
        description="If enabled, orbit spans the whole 4D animation range",
        default=True,
    )
    
    orbit_duration_frames: FloatProperty(
        name="Orbit Duration (frames)",
        description="Duration of orbit animation in frames",
        default=250.0,
        min=1.0,
        max=10000.0,
    )
    
    # UI and visibility toggles
    hide_orbit_path: BoolProperty(
        name="Hide Orbit Path",
        description="Hide the visible orbit path (Bezier Circle) in the viewport and render",
        default=False,
    )
    
    hide_all_animation_cameras: BoolProperty(
        name="Hide All Animation Cameras",
        description="Hide all animation cameras in the viewport",
        default=False,
    )
    
    hide_all_snapshot_cameras: BoolProperty(
        name="Hide All Snapshot Cameras", 
        description="Hide all snapshot cameras in the viewport",
        default=False,
    )
    
    # HUD distance property
    hud_distance: FloatProperty(
        name="Distance",
        description="Distance from camera to place HUD elements",
        default=3.0,
        min=0.5,
        max=50.0,
        precision=1,
    )
    
    # Legend HUD scroll and visibility properties
    legend_hud_colortype_scroll_offset: IntProperty(
        name="Legend Scroll Offset",
        description="Scroll offset for legend colortype display",
        default=0,
        min=0,
    )
    
    legend_hud_visible_colortypes: StringProperty(
        name="Visible Colortypes",
        description="Comma-separated list of visible colortype names",
        default="",
    )

    # Type checking
    if TYPE_CHECKING:
        camera_focal_mm: float
        camera_clip_start: float
        camera_clip_end: float
        active_animation_camera: bpy.types.Object
        active_snapshot_camera: bpy.types.Object
        show_animation_cameras: bool
        show_snapshot_cameras: bool
        show_camera_orbit_settings: bool
        enable_text_hud: bool
        expand_hud_settings: bool
        expand_schedule_hud: bool
        expand_timeline_hud: bool
        expand_legend_hud: bool
        hud_show_date: bool
        hud_show_week: bool
        hud_show_day: bool
        hud_show_progress: bool
        hud_position: str
        hud_scale_factor: float
        hud_margin_horizontal: float
        hud_margin_vertical: float
        hud_text_color: tuple[float, float, float, float]
        hud_background_color: tuple[float, float, float, float]
        hud_text_spacing: float
        hud_text_alignment: str
        hud_padding_horizontal: float
        hud_padding_vertical: float
        hud_border_radius: float
        hud_border_width: float
        hud_border_color: tuple[float, float, float, float]
        hud_text_shadow_enabled: bool
        hud_text_shadow_offset_x: float
        hud_text_shadow_offset_y: float
        hud_text_shadow_color: tuple[float, float, float, float]
        hud_background_shadow_enabled: bool
        hud_background_shadow_offset_x: float
        hud_background_shadow_offset_y: float
        hud_background_shadow_blur: float
        hud_background_shadow_color: tuple[float, float, float, float]
        hud_font_weight: str
        hud_letter_spacing: float
        hud_background_gradient_enabled: bool
        hud_background_gradient_color: tuple[float, float, float, float]
        hud_gradient_direction: str
        enable_timeline_hud: bool
        timeline_hud_position: str
        timeline_hud_margin_vertical: float
        timeline_hud_margin_horizontal: float
        timeline_hud_zoom_level: str
        timeline_hud_height: float
        timeline_hud_color_inactive_range: tuple[float, float, float, float]
        timeline_hud_color_active_range: tuple[float, float, float, float]
        timeline_hud_color_progress: tuple[float, float, float, float]
        timeline_hud_color_text: tuple[float, float, float, float]
        timeline_hud_border_radius: float
        timeline_hud_show_progress_bar: bool
        enable_legend_hud: bool
        legend_hud_position: str
        legend_hud_margin_horizontal: float
        legend_hud_margin_vertical: float
        legend_hud_scale_factor: float
        legend_hud_background_color: tuple[float, float, float, float]
        legend_hud_text_color: tuple[float, float, float, float]
        legend_hud_padding: float
        legend_hud_border_radius: float
        legend_hud_item_spacing: float
        legend_hud_color_box_size: float
        legend_hud_show_task_count: bool
        legend_hud_show_inactive_types: bool
        legend_hud_max_items: int
        enable_3d_legend_hud: bool
        legend_3d_location: tuple[float, float, float]
        legend_3d_scale: float
        legend_3d_spacing: float
        legend_3d_always_face_camera: bool
        legend_3d_hud_distance: float
        legend_hud_scale: float
        legend_3d_hud_pos_x: float
        legend_3d_hud_pos_y: float
        legend_3d_hud_scale: float
        legend_3d_panel_width: float
        force_world_origin_anchor: bool
        orbit_speed: float
        orbit_radius: float
        orbit_radius_mode: str
        orbit_mode: str
        orbit_height: float
        orbit_start_angle_deg: float
        orbit_direction: str
        orbit_path_shape: str
        custom_orbit_path: bpy.types.Object
        interpolation_mode: str
        bezier_smoothness_factor: float
        orbit_path_method: str
        orbit_use_4d_duration: bool
        orbit_duration_frames: float
        hide_orbit_path: bool
        hide_all_animation_cameras: bool
        hide_all_snapshot_cameras: bool
        hud_distance: float
        legend_hud_colortype_scroll_offset: int
        legend_hud_visible_colortypes: str
        
        # Legend HUD properties from v57
        enable_legend_hud: bool
        legend_hud_position: str
        legend_hud_margin_horizontal: float
        legend_hud_margin_vertical: float
        legend_hud_orientation: str
        legend_hud_background_color: tuple[float, float, float, float]
        legend_hud_border_radius: float
        legend_hud_padding_horizontal: float
        legend_hud_padding_vertical: float
        legend_hud_item_spacing: float
        legend_hud_text_color: tuple[float, float, float, float]
        legend_hud_show_title: bool
        legend_hud_title_text: str
        legend_hud_title_color: tuple[float, float, float, float]
        legend_hud_color_indicator_size: float
        legend_hud_text_shadow_enabled: bool
        legend_hud_text_shadow_color: tuple[float, float, float, float]
        legend_hud_text_shadow_offset_x: float
        legend_hud_text_shadow_offset_y: float
        legend_hud_auto_scale: bool
        legend_hud_max_width: float
        legend_hud_show_start_column: bool
        legend_hud_show_active_column: bool
        legend_hud_show_end_column: bool
        legend_hud_show_start_title: bool
        legend_hud_show_active_title: bool
        legend_hud_show_end_title: bool
        legend_hud_column_spacing: float
        legend_hud_title_font_size: float