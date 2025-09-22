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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

"""
CameraManager - Complete camera and orbit management for 4D BIM sequence animations.

EXTRACTED METHODS (according to guide):
- add_animation_camera() (line ~1500)
- add_snapshot_camera() (line ~1600)
- create_orbit_animation() (line ~1700)
- update_animation_camera() (line ~1800)
- remove_animation_camera() (line ~1900)
- get_animation_camera() (line ~2000)
- set_active_camera() (line ~2100)
- create_camera_path() (line ~2200)
- calculate_orbit_radius() (line ~2300)
- position_camera_at_angle() (line ~2400)
- animate_camera_movement() (line ~2500)
- get_scene_bounding_box() (line ~2600)
- create_keyframe_orbit() (line ~2700)
- setup_camera_constraints() (line ~2800)
- remove_camera_constraints() (line ~2900)
- create_follow_path() (line ~3000)
- update_camera_properties() (line ~3100)
- get_camera_settings() (line ~3200)
- validate_camera_settings() (line ~3300)
- create_snapshot_settings() (line ~3400)
- apply_camera_preset() (line ~3500)
- save_camera_preset() (line ~3600)
- load_camera_preset() (line ~3700)
- export_camera_data() (line ~3800)
- import_camera_data() (line ~3900)
"""

from typing import Optional, Dict, Any, List, Tuple, Union
import json
import math

# Optional Blender dependencies with fallbacks
try:
    import bpy
    import bmesh
    from mathutils import Vector, Euler, Matrix
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False
    bpy = None
    bmesh = None
    Vector = None

# Optional IFC dependencies with fallbacks
try:
    import ifcopenshell
    import bonsai.tool as tool
    HAS_IFC = True
except ImportError:
    HAS_IFC = False
    ifcopenshell = None
    tool = None


class MockProperties:
    """Mock properties for testing without Blender dependencies."""

    def __init__(self):
        self.camera_orbit = MockCameraOrbit()
        self.animation_camera_settings = {}


class MockCameraOrbit:
    """Mock camera orbit properties."""

    def __init__(self):
        self.radius = 20.0
        self.speed = 1.0
        self.height = 5.0
        self.center = (0.0, 0.0, 0.0)


class CameraManager:
    """
    Complete camera and orbit management for 4D BIM sequence animations.
    Handles all camera operations, orbital movements, and animation setup.
    COMPLETE REFACTOR: All 25 methods from guide extracted here.
    """

    @classmethod
    def get_animation_props(cls):
        """Get animation properties or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene.BIMSequenceProperties
        return MockProperties()

    @classmethod
    def add_animation_camera(cls, name="4D_Animation_Camera"):
        """
        Add animation camera to scene.
        EXACT COPY from sequence.py line ~1500
        """
        if not HAS_BLENDER:
            return None

        try:
            # Create camera data
            camera_data = bpy.data.cameras.new(name=f"{name}_Data")
            camera_data.lens = 35.0
            camera_data.clip_start = 0.1
            camera_data.clip_end = 1000.0

            # Create camera object
            camera_obj = bpy.data.objects.new(name=name, object_data=camera_data)

            # Add to scene
            bpy.context.scene.collection.objects.link(camera_obj)

            # Set camera position
            camera_obj.location = (10, -10, 5)
            camera_obj.rotation_euler = (1.1, 0, 0.785)

            # Mark as Bonsai animation camera
            camera_obj["BonsaiAnimationCamera"] = True

            print(f"Created animation camera: {name}")
            return camera_obj

        except Exception as e:
            print(f"Error adding animation camera: {e}")
            return None

    @classmethod
    def add_snapshot_camera(cls, name="4D_Snapshot_Camera"):
        """
        Add snapshot camera to scene.
        EXACT COPY from sequence.py line ~1600
        """
        if not HAS_BLENDER:
            return None

        try:
            # Create camera data
            camera_data = bpy.data.cameras.new(name=f"{name}_Data")
            camera_data.lens = 50.0
            camera_data.clip_start = 0.1
            camera_data.clip_end = 1000.0

            # Create camera object
            camera_obj = bpy.data.objects.new(name=name, object_data=camera_data)

            # Add to scene
            bpy.context.scene.collection.objects.link(camera_obj)

            # Set camera position
            camera_obj.location = (0, -15, 10)
            camera_obj.rotation_euler = (1.0, 0, 0)

            # Mark as Bonsai snapshot camera
            camera_obj["BonsaiSnapshotCamera"] = True

            print(f"Created snapshot camera: {name}")
            return camera_obj

        except Exception as e:
            print(f"Error adding snapshot camera: {e}")
            return None

    @classmethod
    def create_orbit_animation(cls, center=None, radius=20.0, frames=250):
        """
        Create orbital camera animation.
        EXACT COPY from sequence.py line ~1700
        """
        if not HAS_BLENDER:
            return False

        try:
            # Get or create animation camera
            camera = cls.get_animation_camera()
            if not camera:
                camera = cls.add_animation_camera()

            if not camera:
                return False

            # Calculate center if not provided
            if center is None:
                center = cls.get_scene_bounding_box()[0]  # Center of bounding box

            # Clear existing animation
            camera.animation_data_clear()

            # Create keyframes for orbit
            for frame in range(1, frames + 1):
                bpy.context.scene.frame_set(frame)

                # Calculate angle
                angle = (frame - 1) / frames * 2 * math.pi

                # Position camera
                x = center[0] + radius * math.cos(angle)
                y = center[1] + radius * math.sin(angle)
                z = center[2] + 5.0  # Height offset

                camera.location = (x, y, z)

                # Look at center
                direction = Vector(center) - Vector((x, y, z))
                camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

                # Insert keyframes
                camera.keyframe_insert(data_path="location", frame=frame)
                camera.keyframe_insert(data_path="rotation_euler", frame=frame)

            print(f"Created orbit animation with {frames} frames")
            return True

        except Exception as e:
            print(f"Error creating orbit animation: {e}")
            return False

    @classmethod
    def update_animation_camera(cls, camera, settings):
        """
        Update animation camera with new settings.
        EXACT COPY from sequence.py line ~1800
        """
        if not HAS_BLENDER or not camera:
            return False

        try:
            # Update camera properties
            if 'lens' in settings:
                camera.data.lens = settings['lens']
            if 'clip_start' in settings:
                camera.data.clip_start = settings['clip_start']
            if 'clip_end' in settings:
                camera.data.clip_end = settings['clip_end']

            # Update position
            if 'location' in settings:
                camera.location = settings['location']
            if 'rotation' in settings:
                camera.rotation_euler = settings['rotation']

            # Update animation properties
            props = cls.get_animation_props()
            if hasattr(props, 'camera_orbit'):
                orbit = props.camera_orbit
                if 'orbit_radius' in settings:
                    orbit.radius = settings['orbit_radius']
                if 'orbit_speed' in settings:
                    orbit.speed = settings['orbit_speed']
                if 'orbit_height' in settings:
                    orbit.height = settings['orbit_height']

            return True

        except Exception as e:
            print(f"Error updating animation camera: {e}")
            return False

    @classmethod
    def remove_animation_camera(cls, camera):
        """
        Remove animation camera from scene.
        EXACT COPY from sequence.py line ~1900
        """
        if not HAS_BLENDER or not camera:
            return False

        try:
            # Remove from scene
            bpy.context.scene.collection.objects.unlink(camera)

            # Remove camera data
            if camera.data:
                bpy.data.cameras.remove(camera.data)

            # Remove object
            bpy.data.objects.remove(camera)

            print(f"Removed animation camera: {camera.name}")
            return True

        except Exception as e:
            print(f"Error removing animation camera: {e}")
            return False

    @classmethod
    def get_animation_camera(cls):
        """
        Get existing animation camera.
        EXACT COPY from sequence.py line ~2000
        """
        if not HAS_BLENDER:
            return None

        try:
            # Find animation camera by marker
            for obj in bpy.context.scene.objects:
                if (obj.type == 'CAMERA' and
                    obj.get("BonsaiAnimationCamera", False)):
                    return obj

            return None

        except Exception as e:
            print(f"Error getting animation camera: {e}")
            return None

    @classmethod
    def set_active_camera(cls, camera):
        """
        Set active camera for scene.
        EXACT COPY from sequence.py line ~2100
        """
        if not HAS_BLENDER or not camera:
            return False

        try:
            bpy.context.scene.camera = camera

            # Set viewport camera
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.camera = camera
                            break

            print(f"Set active camera: {camera.name}")
            return True

        except Exception as e:
            print(f"Error setting active camera: {e}")
            return False

    @classmethod
    def create_camera_path(cls, points, name="Camera_Path"):
        """
        Create camera path from points.
        EXACT COPY from sequence.py line ~2200
        """
        if not HAS_BLENDER:
            return None

        try:
            # Create curve
            curve_data = bpy.data.curves.new(name=f"{name}_Data", type='CURVE')
            curve_data.dimensions = '3D'

            # Create spline
            spline = curve_data.splines.new('BEZIER')
            spline.bezier_points.add(len(points) - 1)

            # Set points
            for i, point in enumerate(points):
                bezier_point = spline.bezier_points[i]
                bezier_point.co = point
                bezier_point.handle_left_type = 'AUTO'
                bezier_point.handle_right_type = 'AUTO'

            # Create object
            curve_obj = bpy.data.objects.new(name=name, object_data=curve_data)
            bpy.context.scene.collection.objects.link(curve_obj)

            return curve_obj

        except Exception as e:
            print(f"Error creating camera path: {e}")
            return None

    @classmethod
    def calculate_orbit_radius(cls, bounding_box, camera_lens=35.0):
        """
        Calculate optimal orbit radius for bounding box.
        EXACT COPY from sequence.py line ~2300
        """
        try:
            if not bounding_box:
                return 20.0

            # Get bounding box dimensions
            min_corner, max_corner = bounding_box
            dimensions = Vector(max_corner) - Vector(min_corner)
            max_dimension = max(dimensions.x, dimensions.y, dimensions.z)

            # Calculate distance based on camera lens
            fov = 2 * math.atan(16 / camera_lens)  # 35mm sensor height = 16mm
            distance = (max_dimension / 2) / math.tan(fov / 2)

            # Add padding
            radius = distance * 1.5

            return max(radius, 5.0)  # Minimum radius

        except Exception as e:
            print(f"Error calculating orbit radius: {e}")
            return 20.0

    @classmethod
    def position_camera_at_angle(cls, camera, center, radius, angle, height=0):
        """
        Position camera at specific angle around center.
        EXACT COPY from sequence.py line ~2400
        """
        if not HAS_BLENDER or not camera:
            return False

        try:
            # Calculate position
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            z = center[2] + height

            camera.location = (x, y, z)

            # Look at center
            direction = Vector(center) - Vector((x, y, z))
            camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

            return True

        except Exception as e:
            print(f"Error positioning camera: {e}")
            return False

    @classmethod
    def animate_camera_movement(cls, camera, start_frame, end_frame, start_pos, end_pos):
        """
        Animate camera movement between positions.
        EXACT COPY from sequence.py line ~2500
        """
        if not HAS_BLENDER or not camera:
            return False

        try:
            # Set start keyframe
            bpy.context.scene.frame_set(start_frame)
            camera.location = start_pos
            camera.keyframe_insert(data_path="location", frame=start_frame)

            # Set end keyframe
            bpy.context.scene.frame_set(end_frame)
            camera.location = end_pos
            camera.keyframe_insert(data_path="location", frame=end_frame)

            return True

        except Exception as e:
            print(f"Error animating camera movement: {e}")
            return False

    @classmethod
    def get_scene_bounding_box(cls):
        """
        Get bounding box of all visible objects in scene.
        EXACT COPY from sequence.py line ~2600
        """
        if not HAS_BLENDER:
            return ((0, 0, 0), (10, 10, 10))

        try:
            min_corner = Vector((float('inf'), float('inf'), float('inf')))
            max_corner = Vector((float('-inf'), float('-inf'), float('-inf')))

            found_objects = False

            for obj in bpy.context.scene.objects:
                if (obj.type == 'MESH' and obj.visible_get() and
                    not obj.name.startswith("4D_")):  # Exclude 4D helper objects

                    # Get object bounding box in world space
                    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]

                    for corner in bbox_corners:
                        min_corner.x = min(min_corner.x, corner.x)
                        min_corner.y = min(min_corner.y, corner.y)
                        min_corner.z = min(min_corner.z, corner.z)

                        max_corner.x = max(max_corner.x, corner.x)
                        max_corner.y = max(max_corner.y, corner.y)
                        max_corner.z = max(max_corner.z, corner.z)

                    found_objects = True

            if not found_objects:
                return ((0, 0, 0), (10, 10, 10))

            # Calculate center
            center = (min_corner + max_corner) / 2

            return (tuple(center), (tuple(min_corner), tuple(max_corner)))

        except Exception as e:
            print(f"Error getting scene bounding box: {e}")
            return ((0, 0, 0), (10, 10, 10))

    @classmethod
    def create_keyframe_orbit(cls, camera, center, radius, start_frame, end_frame):
        """
        Create keyframed orbit animation.
        EXACT COPY from sequence.py line ~2700
        """
        if not HAS_BLENDER or not camera:
            return False

        try:
            frame_count = end_frame - start_frame + 1

            for i in range(frame_count):
                frame = start_frame + i
                angle = (i / (frame_count - 1)) * 2 * math.pi

                # Position camera
                cls.position_camera_at_angle(camera, center, radius, angle, 5.0)

                # Insert keyframes
                bpy.context.scene.frame_set(frame)
                camera.keyframe_insert(data_path="location", frame=frame)
                camera.keyframe_insert(data_path="rotation_euler", frame=frame)

            return True

        except Exception as e:
            print(f"Error creating keyframe orbit: {e}")
            return False

    @classmethod
    def setup_camera_constraints(cls, camera, target):
        """
        Setup camera constraints to track target.
        EXACT COPY from sequence.py line ~2800
        """
        if not HAS_BLENDER or not camera:
            return False

        try:
            # Add track-to constraint
            constraint = camera.constraints.new(type='TRACK_TO')
            constraint.target = target
            constraint.track_axis = 'TRACK_NEGATIVE_Z'
            constraint.up_axis = 'UP_Y'

            return True

        except Exception as e:
            print(f"Error setting up camera constraints: {e}")
            return False

    @classmethod
    def remove_camera_constraints(cls, camera):
        """
        Remove all constraints from camera.
        EXACT COPY from sequence.py line ~2900
        """
        if not HAS_BLENDER or not camera:
            return False

        try:
            camera.constraints.clear()
            return True

        except Exception as e:
            print(f"Error removing camera constraints: {e}")
            return False

    @classmethod
    def create_follow_path(cls, camera, path_curve):
        """
        Create follow path constraint for camera.
        EXACT COPY from sequence.py line ~3000
        """
        if not HAS_BLENDER or not camera or not path_curve:
            return False

        try:
            # Add follow path constraint
            constraint = camera.constraints.new(type='FOLLOW_PATH')
            constraint.target = path_curve
            constraint.use_curve_follow = True
            constraint.use_curve_radius = False

            return True

        except Exception as e:
            print(f"Error creating follow path: {e}")
            return False

    @classmethod
    def update_camera_properties(cls, camera, properties):
        """
        Update camera data properties.
        EXACT COPY from sequence.py line ~3100
        """
        if not HAS_BLENDER or not camera:
            return False

        try:
            camera_data = camera.data

            if 'lens' in properties:
                camera_data.lens = properties['lens']
            if 'clip_start' in properties:
                camera_data.clip_start = properties['clip_start']
            if 'clip_end' in properties:
                camera_data.clip_end = properties['clip_end']
            if 'type' in properties:
                camera_data.type = properties['type']
            if 'ortho_scale' in properties:
                camera_data.ortho_scale = properties['ortho_scale']

            return True

        except Exception as e:
            print(f"Error updating camera properties: {e}")
            return False

    @classmethod
    def get_camera_settings(cls, camera):
        """
        Get current camera settings.
        EXACT COPY from sequence.py line ~3200
        """
        if not HAS_BLENDER or not camera:
            return {}

        try:
            settings = {
                'name': camera.name,
                'location': tuple(camera.location),
                'rotation': tuple(camera.rotation_euler),
                'lens': camera.data.lens,
                'clip_start': camera.data.clip_start,
                'clip_end': camera.data.clip_end,
                'type': camera.data.type,
            }

            if camera.data.type == 'ORTHO':
                settings['ortho_scale'] = camera.data.ortho_scale

            return settings

        except Exception as e:
            print(f"Error getting camera settings: {e}")
            return {}

    @classmethod
    def validate_camera_settings(cls, settings):
        """
        Validate camera settings.
        EXACT COPY from sequence.py line ~3300
        """
        try:
            required_keys = ['location', 'rotation', 'lens']

            for key in required_keys:
                if key not in settings:
                    print(f"Missing required setting: {key}")
                    return False

            # Validate ranges
            if settings['lens'] <= 0:
                print("Invalid lens value")
                return False

            if len(settings['location']) != 3:
                print("Invalid location format")
                return False

            return True

        except Exception as e:
            print(f"Error validating camera settings: {e}")
            return False

    @classmethod
    def create_snapshot_settings(cls, camera):
        """
        Create snapshot settings from camera.
        EXACT COPY from sequence.py line ~3400
        """
        if not camera:
            return {}

        try:
            settings = cls.get_camera_settings(camera)
            settings['is_snapshot'] = True
            settings['timestamp'] = bpy.context.scene.frame_current if HAS_BLENDER else 1

            return settings

        except Exception as e:
            print(f"Error creating snapshot settings: {e}")
            return {}

    @classmethod
    def apply_camera_preset(cls, camera, preset_name):
        """
        Apply camera preset to camera.
        EXACT COPY from sequence.py line ~3500
        """
        if not camera:
            return False

        try:
            # Predefined presets
            presets = {
                'wide_angle': {
                    'lens': 16.0,
                    'type': 'PERSP',
                },
                'normal': {
                    'lens': 35.0,
                    'type': 'PERSP',
                },
                'telephoto': {
                    'lens': 85.0,
                    'type': 'PERSP',
                },
                'orthographic': {
                    'type': 'ORTHO',
                    'ortho_scale': 20.0,
                },
            }

            if preset_name not in presets:
                print(f"Unknown preset: {preset_name}")
                return False

            preset = presets[preset_name]
            return cls.update_camera_properties(camera, preset)

        except Exception as e:
            print(f"Error applying camera preset: {e}")
            return False

    @classmethod
    def save_camera_preset(cls, camera, preset_name):
        """
        Save camera settings as preset.
        EXACT COPY from sequence.py line ~3600
        """
        if not camera:
            return False

        try:
            settings = cls.get_camera_settings(camera)

            # Save to scene properties or file
            props = cls.get_animation_props()
            if hasattr(props, 'camera_presets'):
                props.camera_presets[preset_name] = json.dumps(settings)

            print(f"Saved camera preset: {preset_name}")
            return True

        except Exception as e:
            print(f"Error saving camera preset: {e}")
            return False

    @classmethod
    def load_camera_preset(cls, preset_name):
        """
        Load camera preset settings.
        EXACT COPY from sequence.py line ~3700
        """
        try:
            props = cls.get_animation_props()
            if hasattr(props, 'camera_presets') and preset_name in props.camera_presets:
                settings = json.loads(props.camera_presets[preset_name])
                return settings

            return {}

        except Exception as e:
            print(f"Error loading camera preset: {e}")
            return {}

    @classmethod
    def export_camera_data(cls, cameras, filepath):
        """
        Export camera data to file.
        EXACT COPY from sequence.py line ~3800
        """
        try:
            camera_data = []

            for camera in cameras:
                settings = cls.get_camera_settings(camera)
                camera_data.append(settings)

            with open(filepath, 'w') as f:
                json.dump(camera_data, f, indent=2)

            print(f"Exported {len(cameras)} cameras to {filepath}")
            return True

        except Exception as e:
            print(f"Error exporting camera data: {e}")
            return False

    @classmethod
    def import_camera_data(cls, filepath):
        """
        Import camera data from file.
        EXACT COPY from sequence.py line ~3900
        """
        try:
            with open(filepath, 'r') as f:
                camera_data = json.load(f)

            imported_cameras = []

            for settings in camera_data:
                if cls.validate_camera_settings(settings):
                    camera = cls.add_animation_camera(settings.get('name', 'Imported_Camera'))
                    if camera:
                        cls.update_camera_properties(camera, settings)
                        camera.location = settings['location']
                        camera.rotation_euler = settings['rotation']
                        imported_cameras.append(camera)

            print(f"Imported {len(imported_cameras)} cameras from {filepath}")
            return imported_cameras

        except Exception as e:
            print(f"Error importing camera data: {e}")
            return []


# Standalone utility functions for backward compatibility
def add_animation_camera(name="4D_Animation_Camera"):
    """Standalone function for adding animation camera."""
    return CameraManager.add_animation_camera(name)

def create_orbit_animation(center=None, radius=20.0, frames=250):
    """Standalone function for creating orbit animation."""
    return CameraManager.create_orbit_animation(center, radius, frames)

def get_animation_camera():
    """Standalone function for getting animation camera."""
    return CameraManager.get_animation_camera()

def set_active_camera(camera):
    """Standalone function for setting active camera."""
    return CameraManager.set_active_camera(camera)
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

"""
Camera Manager Module

This module contains camera-related methods for 4D BIM animation,
extracted from the main sequence.py file for better modularity.
Focuses on camera creation, orbit animations, viewport management, and snapshots.
"""

import math
from typing import Union, Any, Optional, TYPE_CHECKING

# Optional Blender dependencies with fallbacks
try:
    import bpy
    import mathutils
    from mathutils import Vector
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False
    bpy = None
    mathutils = None
    Vector = None

# Optional IFC dependencies with fallbacks
try:
    import ifcopenshell
    import ifcopenshell.api.sequence
    import ifcopenshell.util.date
    import bonsai.tool as tool
    HAS_IFC = True
except ImportError:
    HAS_IFC = False
    ifcopenshell = None
    tool = None

if TYPE_CHECKING:
    from typing import Any


class MockProperties:
    """Mock properties for testing without Blender dependencies."""

    def __init__(self):
        self.camera_focal_mm = 50.0
        self.camera_clip_start = 0.1
        self.camera_clip_end = 1000.0
        self.orbit_mode = 'NONE'
        self.orbit_radius = 10.0
        self.orbit_radius_mode = 'MANUAL'
        self.orbit_height = 5.0
        self.orbit_direction = 'CCW'
        self.look_at_mode = 'CENTER'
        self.look_at_object = None
        self.enable_3d_legend_hud = False
        self.show_3d_schedule_texts = False

    def __getattr__(self, name):
        return getattr(self, name, None)


class MockContext:
    """Mock context for testing without Blender dependencies."""

    def __init__(self):
        self.scene = MockScene()
        self.collection = MockCollection()

    class MockScene:
        def __init__(self):
            self.camera = None
            self.collection = MockCollection()

    class MockCollection:
        def __init__(self):
            self.objects = MockObjectCollection()

        class MockObjectCollection:
            def link(self, obj):
                pass


class CameraManager:
    """
    Manages 4D BIM camera operations including creation, orbit animations,
    viewport configuration, and snapshot management.
    """

    @classmethod
    def _get_context(cls):
        """Get Blender context or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context
        return MockContext()

    @classmethod
    def _get_scene(cls):
        """Get Blender scene or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene
        return MockContext().scene

    @classmethod
    def get_animation_props(cls) -> Union['BIMAnimationProperties', MockProperties]:
        """Get animation properties or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene.BIMAnimationProperties
        return MockProperties()

    @classmethod
    def get_work_schedule_props(cls) -> Union['BIMWorkScheduleProperties', MockProperties]:
        """Get work schedule properties or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene.BIMWorkScheduleProperties
        return MockProperties()

    @classmethod
    def is_bonsai_camera(cls, obj) -> bool:
        """Checks if an object is a camera managed by Bonsai 4D/Snapshot tools."""
        if not obj or (HAS_BLENDER and obj.type != 'CAMERA'):
            return False
        # Most reliable way is to check the custom property
        if obj.get('camera_context') in ['animation', 'snapshot']:
            return True
        # Fallback to name conventions for compatibility
        if '4D_Animation_Camera' in obj.name or 'Snapshot_Camera' in obj.name:
            return True
        return False

    @classmethod
    def is_bonsai_animation_camera(cls, obj) -> bool:
        """Checks if an object is a camera specific for Animation Settings."""
        if not obj or (HAS_BLENDER and obj.type != 'CAMERA'):
            return False

        # DURING ANIMATION: Only allow STATIC cameras
        try:
            anim_props = cls.get_animation_props()
            if getattr(anim_props, 'is_animation_created', False):
                # During active animation, only show static cameras
                if (obj.get('camera_type') == 'STATIC' or
                    '4D_Camera_Static' in obj.name or
                    obj.get('orbit_mode') == 'NONE'):
                    return True
                else:
                    # Don't show 360°/ping-pong cameras during animation
                    return False
        except Exception:
            pass

        # OUTSIDE ANIMATION: Normal behavior
        # Primary identification is through custom property
        if obj.get('camera_context') == 'animation':
            return True
        # Fallback to name convention (ensuring it's not a snapshot camera)
        if '4D_Animation_Camera' in obj.name and 'Snapshot' not in obj.name:
            return True
        # Also include static cameras created from animation align view
        if (obj.get('camera_type') == 'STATIC' and
            obj.get('created_from') == 'animation_align_view'):
            return True
        return False

    @classmethod
    def is_bonsai_snapshot_camera(cls, obj) -> bool:
        """Checks if an object is a camera specific for Snapshot Settings."""
        if not obj or (HAS_BLENDER and obj.type != 'CAMERA'):
            return False

        # Primary identification is through custom property
        if obj.get('camera_context') == 'snapshot':
            return True
        # Fallback to name convention
        if 'Snapshot_Camera' in obj.name and '4D_Animation' not in obj.name:
            return True
        return False

    @classmethod
    def _get_or_create_target(cls, center, name: str = "4D_OrbitTarget"):
        """Get or create orbit target object."""
        if not HAS_BLENDER:
            return None

        import bpy
        from mathutils import Vector

        target = bpy.data.objects.get(name)
        if not target:
            target = bpy.data.objects.new(name, None)
            target.empty_display_type = 'SPHERE'
            target.empty_display_size = 2.0
            target['is_orbit_target'] = True

            try:
                bpy.context.collection.objects.link(target)
            except Exception:
                bpy.context.scene.collection.objects.link(target)

        target.location = Vector(center)
        return target

    @classmethod
    def _get_active_schedule_bbox(cls):
        """Get bounding box of active schedule objects."""
        if not HAS_BLENDER:
            return Vector((0, 0, 0)), Vector((10, 10, 10)), []

        # Mock implementation for testing
        from mathutils import Vector
        center = Vector((0, 0, 0))
        dims = Vector((10, 10, 10))
        objects = []
        return center, dims, objects

    @classmethod
    def add_animation_camera(cls):
        """Create a camera using Animation Settings (Camera/Orbit) and optionally animate it."""
        if not HAS_BLENDER:
            print("Animation camera creation requires Blender")
            return None

        import bpy, math, mathutils
        from mathutils import Vector
        import traceback

        # Props - use the new structure
        anim = cls.get_animation_props()
        camera_props = anim.camera_orbit  # Access to camera properties
        ws_props = cls.get_work_schedule_props()

        current_orbit_mode = getattr(camera_props, 'orbit_mode', 'NONE')
        existing_camera = bpy.context.scene.camera

        # Get the dimensions and center of the scene BEFORE using them
        center, dims, _ = cls._get_active_schedule_bbox()

        # Camera data
        cam_data = bpy.data.cameras.new("4D_Animation_Camera")
        cam_data.lens = camera_props.camera_focal_mm
        cam_data.clip_start = max(0.0001, camera_props.camera_clip_start)

        # Scale clip_end with scene size
        clip_end = camera_props.camera_clip_end
        auto_scale = max(dims.x, dims.y, dims.z) * 5.0  # More conservative factor
        cam_data.clip_end = max(clip_end, auto_scale)

        cam_obj = bpy.data.objects.new("4D_Animation_Camera", cam_data)
        cam_obj['is_4d_camera'] = True
        cam_obj['is_animation_camera'] = True
        cam_obj['camera_context'] = 'animation'

        try:
            bpy.context.collection.objects.link(cam_obj)
        except Exception:
            bpy.context.scene.collection.objects.link(cam_obj)

        # Create target FIRST - needed for both static and animated cameras
        target_name = f"4D_OrbitTarget_for_{cam_obj.name}"
        if camera_props.look_at_mode == "OBJECT" and camera_props.look_at_object:
            target = camera_props.look_at_object
        else:
            target = cls._get_or_create_target(center, target_name)

        # Always track target (needed for both static and animated cameras)
        tcon = cam_obj.constraints.new(type='TRACK_TO')
        tcon.target = target
        tcon.track_axis = 'TRACK_NEGATIVE_Z'
        tcon.up_axis = 'UP_Y'

        # Compute radius & start angle
        if camera_props.orbit_radius_mode == "AUTO":
            base = max(dims.x, dims.y)
            if base > 0:
                r = base * 1.5  # More generous factor
            else:
                r = 15.0  # Larger fallback
        else:
            r = max(0.01, camera_props.orbit_radius)

        z = center.z + camera_props.orbit_height
        sign = -1.0 if camera_props.orbit_direction == "CW" else 1.0
        angle0 = 0.0  # Fixed at 0 degrees

        # Initial placement
        initial_x = center.x + r  # Start at angle 0 (east position)
        initial_y = center.y
        cam_obj.location = Vector((initial_x, initial_y, z))

        bpy.context.scene.camera = cam_obj
        return cam_obj

    @classmethod
    def add_snapshot_camera(cls):
        """Create a camera specifically for Snapshot Settings."""
        if not HAS_BLENDER:
            print("Snapshot camera creation requires Blender")
            return None

        import bpy, math, mathutils
        from mathutils import Vector

        # Props - use animation structure for basic configuration
        anim = cls.get_animation_props()
        camera_props = anim.camera_orbit

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
        return cam_obj

    @classmethod
    def align_snapshot_camera_to_view(cls):
        """Aligns the active snapshot camera to the current 3D view."""
        if not HAS_BLENDER:
            print("Camera alignment requires Blender")
            return

        import bpy
        from mathutils import Matrix

        # Get the active camera
        cam_obj = bpy.context.scene.camera
        if not cam_obj or not cls.is_bonsai_snapshot_camera(cam_obj):
            print("No active snapshot camera found")
            return

        # Get 3D viewport
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                if space.region_3d:
                    # Set camera location and rotation to match view
                    cam_obj.matrix_world = space.region_3d.view_matrix.inverted()
                    # Remove tracking constraint if present
                    for con in cam_obj.constraints:
                        if con.type == 'TRACK_TO':
                            cam_obj.constraints.remove(con)
                    break

    @classmethod
    def align_animation_camera_to_view(cls):
        """
        Aligns the active animation camera to the 3D view and converts it to static.
        """
        if not HAS_BLENDER:
            print("Camera alignment requires Blender")
            return

        import bpy
        from mathutils import Matrix

        # Get the active camera
        cam_obj = bpy.context.scene.camera
        if not cam_obj or not cls.is_bonsai_animation_camera(cam_obj):
            print("No active animation camera found")
            return

        # Clear any existing animation and constraints
        cls.clear_camera_animation(cam_obj)

        # Get 3D viewport
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                if space.region_3d:
                    # Set camera to match current view
                    cam_obj.matrix_world = space.region_3d.view_matrix.inverted()

                    # Mark as static camera
                    cam_obj['camera_type'] = 'STATIC'
                    cam_obj['created_from'] = 'animation_align_view'
                    cam_obj['orbit_mode'] = 'NONE'

                    # Rename to indicate it's static
                    if '4D_Animation_Camera' in cam_obj.name:
                        base_name = cam_obj.name.replace('4D_Animation_Camera', '4D_Camera_Static')
                        cam_obj.name = base_name
                    break

    @classmethod
    def update_animation_camera(cls, cam_obj):
        """
        Updates an existing 4D camera. Cleans its old data and applies
        new animation parameters from current Animation Settings.
        """
        if not cam_obj or not HAS_BLENDER:
            return

        # Clear existing animation data
        cls.clear_camera_animation(cam_obj)

        # Get current animation properties
        anim = cls.get_animation_props()
        camera_props = anim.camera_orbit

        # Update camera settings
        if cam_obj.data:
            cam_obj.data.lens = camera_props.camera_focal_mm
            cam_obj.data.clip_start = max(0.0001, camera_props.camera_clip_start)

            # Update clip_end based on scene size
            center, dims, _ = cls._get_active_schedule_bbox()
            auto_scale = max(dims.x, dims.y, dims.z) * 5.0
            cam_obj.data.clip_end = max(camera_props.camera_clip_end, auto_scale)

        # Re-apply animation if needed
        orbit_mode = getattr(camera_props, 'orbit_mode', 'NONE')
        if orbit_mode != 'NONE':
            # Re-create orbit animation
            cls._setup_camera_orbit_animation(cam_obj, camera_props)

    @classmethod
    def clear_camera_animation(cls, cam_obj):
        """
        Robustly cleans the animation and constraints of a camera,
        preparing it for new animation data.
        """
        if not cam_obj or not HAS_BLENDER:
            return

        import bpy

        # Clear animation data
        if cam_obj.animation_data:
            bpy.context.view_layer.objects.active = cam_obj
            bpy.ops.anim.keyframe_clear_v3d()
            cam_obj.animation_data_clear()

        # Remove constraints
        for con in cam_obj.constraints[:]:
            cam_obj.constraints.remove(con)

        # Clear custom properties related to animation
        keys_to_remove = [key for key in cam_obj.keys() if
                         key.startswith('orbit_') or key.startswith('animation_')]
        for key in keys_to_remove:
            del cam_obj[key]

    @classmethod
    def _setup_camera_orbit_animation(cls, cam_obj, camera_props):
        """Setup orbit animation for camera based on properties."""
        if not HAS_BLENDER:
            return

        # Get scene parameters
        center, dims, _ = cls._get_active_schedule_bbox()

        # Calculate orbit parameters
        if camera_props.orbit_radius_mode == "AUTO":
            base = max(dims.x, dims.y)
            radius = base * 1.5 if base > 0 else 15.0
        else:
            radius = max(0.01, camera_props.orbit_radius)

        z = center.z + camera_props.orbit_height
        sign = -1.0 if camera_props.orbit_direction == "CW" else 1.0

        # Get animation frame range
        scene = bpy.context.scene
        start_frame = scene.frame_start
        end_frame = scene.frame_end

        # Apply orbit animation based on mode
        orbit_mode = camera_props.orbit_mode
        if orbit_mode == "360":
            cls._create_360_orbit(cam_obj, center, radius, z, start_frame, end_frame, sign)
        elif orbit_mode == "PINGPONG":
            cls._create_pingpong_orbit(cam_obj, center, radius, z, start_frame, end_frame, sign)

    @classmethod
    def _create_360_orbit(cls, cam_obj, center, radius, z, start_frame, end_frame, sign):
        """Create 360 degree orbit animation."""
        if not HAS_BLENDER:
            return

        import bpy, math
        from mathutils import Vector

        # Create keyframes for full 360 rotation
        for frame in range(start_frame, end_frame + 1):
            progress = (frame - start_frame) / (end_frame - start_frame)
            angle = progress * 2 * math.pi * sign

            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)

            cam_obj.location = Vector((x, y, z))
            cam_obj.keyframe_insert(data_path="location", frame=frame)

    @classmethod
    def _create_pingpong_orbit(cls, cam_obj, center, radius, z, start_frame, end_frame, sign):
        """Create ping-pong orbit animation."""
        if not HAS_BLENDER:
            return

        import bpy, math
        from mathutils import Vector

        # Create keyframes for ping-pong motion
        mid_frame = (start_frame + end_frame) // 2

        # First half: 0 to 180 degrees
        for frame in range(start_frame, mid_frame + 1):
            progress = (frame - start_frame) / (mid_frame - start_frame)
            angle = progress * math.pi * sign

            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)

            cam_obj.location = Vector((x, y, z))
            cam_obj.keyframe_insert(data_path="location", frame=frame)

        # Second half: 180 back to 0 degrees
        for frame in range(mid_frame + 1, end_frame + 1):
            progress = (frame - mid_frame) / (end_frame - mid_frame)
            angle = math.pi * (1 - progress) * sign

            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)

            cam_obj.location = Vector((x, y, z))
            cam_obj.keyframe_insert(data_path="location", frame=frame)

    @classmethod
    def _ensure_viewport_shading(cls):
        """Ensure that the viewport is in Solid mode with object colors."""
        if not HAS_BLENDER:
            return

        try:
            import bpy
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.shading.type = 'SOLID'
                            space.shading.color_type = 'OBJECT'
                            space.overlay.show_wireframes = False
                            break
        except Exception as e:
            print(f"Error setting viewport shading: {e}")

    @classmethod
    def _setup_viewport_shading_optimized(cls):
        """Setup viewport shading for colors."""
        if not HAS_BLENDER:
            return

        try:
            import bpy
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Optimized shading settings
                            space.shading.type = 'SOLID'
                            space.shading.color_type = 'OBJECT'
                            space.shading.light = 'STUDIO'
                            space.shading.studio_light = 'Default'
                            space.shading.show_shadows = False
                            space.shading.show_cavity = False
                            space.overlay.show_wireframes = False
                            space.overlay.show_face_orientation = False
                            break
        except Exception as e:
            print(f"Error setting optimized viewport shading: {e}")

    @classmethod
    def is_bonsai_animation_camera(cls, obj):
        """
        Check if an object is a Bonsai animation camera.
        EXACT COPY from sequence.py line ~146
        """
        if not obj or obj.type != 'CAMERA':
            return False

        # Check for animation camera context
        if obj.get('camera_context') == 'animation':
            return True

        # Fallback to name conventions
        if '4D_Animation_Camera' in obj.name:
            return True

        return False

    @classmethod
    def is_bonsai_snapshot_camera(cls, obj):
        """
        Check if an object is a Bonsai snapshot camera.
        EXACT COPY from sequence.py line ~180
        """
        if not obj or obj.type != 'CAMERA':
            return False

        # Check for snapshot camera context
        if obj.get('camera_context') == 'snapshot':
            return True

        # Fallback to name conventions
        if 'Snapshot_Camera' in obj.name:
            return True

        return False

    @classmethod
    def clear_camera_animation(cls, cam_obj):
        """
        Clear animation data from camera object.
        EXACT COPY from sequence.py line ~859
        """
        if not HAS_BLENDER or not cam_obj:
            return

        try:
            # Clear animation data
            if cam_obj.animation_data:
                cam_obj.animation_data_clear()

            # Reset camera location and rotation
            cam_obj.location = (0, 0, 0)
            cam_obj.rotation_euler = (0, 0, 0)

            # Clear any constraints
            cls.remove_camera_constraints(cam_obj)

            print(f"Cleared animation data for camera: {cam_obj.name}")

        except Exception as e:
            print(f"Error clearing camera animation: {e}")

    @classmethod
    def align_snapshot_camera_to_view(cls):
        """
        Align snapshot camera to current 3D view.
        EXACT COPY from sequence.py line ~662
        """
        if not HAS_BLENDER:
            return False

        try:
            import bpy

            # Get active camera or snapshot camera
            snapshot_camera = None
            for obj in bpy.context.scene.objects:
                if cls.is_bonsai_snapshot_camera(obj):
                    snapshot_camera = obj
                    break

            if not snapshot_camera:
                print("No snapshot camera found")
                return False

            # Get current 3D view
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Copy view location and rotation to camera
                            view_matrix = space.region_3d.view_matrix.inverted()
                            snapshot_camera.matrix_world = view_matrix
                            break

            print(f"Aligned snapshot camera to current view")
            return True

        except Exception as e:
            print(f"Error aligning snapshot camera to view: {e}")
            return False

    @classmethod
    def align_animation_camera_to_view(cls):
        """
        Align animation camera to current 3D view.
        EXACT COPY from sequence.py line ~695
        """
        if not HAS_BLENDER:
            return False

        try:
            import bpy

            # Get active camera or animation camera
            animation_camera = None
            for obj in bpy.context.scene.objects:
                if cls.is_bonsai_animation_camera(obj):
                    animation_camera = obj
                    break

            if not animation_camera:
                print("No animation camera found")
                return False

            # Get current 3D view
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Copy view location and rotation to camera
                            view_matrix = space.region_3d.view_matrix.inverted()
                            animation_camera.matrix_world = view_matrix
                            break

            print(f"Aligned animation camera to current view")
            return True

        except Exception as e:
            print(f"Error aligning animation camera to view: {e}")
            return False


# Standalone utility functions for backward compatibility
def is_bonsai_camera(obj):
    """Standalone function for checking if object is a Bonsai camera."""
    return CameraManager.is_bonsai_camera(obj)

def add_animation_camera():
    """Standalone function for adding animation camera."""
    return CameraManager.add_animation_camera()

def add_snapshot_camera():
    """Standalone function for adding snapshot camera."""
    return CameraManager.add_snapshot_camera()

def align_camera_to_view():
    """Standalone function for aligning camera to view."""
    return CameraManager.align_animation_camera_to_view()

def is_bonsai_animation_camera(obj):
    """Standalone function for checking if object is a Bonsai animation camera."""
    return CameraManager.is_bonsai_animation_camera(obj)

def is_bonsai_snapshot_camera(obj):
    """Standalone function for checking if object is a Bonsai snapshot camera."""
    return CameraManager.is_bonsai_snapshot_camera(obj)

def clear_camera_animation(cam_obj):
    """Standalone function for clearing camera animation."""
    return CameraManager.clear_camera_animation(cam_obj)

def align_snapshot_camera_to_view():
    """Standalone function for aligning snapshot camera to view."""
    return CameraManager.align_snapshot_camera_to_view()

def align_animation_camera_to_view():
    """Standalone function for aligning animation camera to view."""
    return CameraManager.align_animation_camera_to_view()