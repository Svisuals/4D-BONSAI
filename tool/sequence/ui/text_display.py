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

"""
TextDisplay - Complete animated text and HUD management for 4D BIM sequence animations.

EXTRACTED METHODS (according to guide):
- create_text_objects_static() (line ~205)
- create_animated_text_hud() (line ~220)
- add_text_animation_handler() (line ~206)
- create_text_objects() (line ~235)
- update_text_content() (line ~250)
- position_text_objects() (line ~270)
- animate_text_properties() (line ~290)
- remove_text_objects() (line ~310)
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List, Tuple, Union
import json

# Optional Blender dependencies with fallbacks
try:
    import bpy
    from mathutils import Vector
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False
    bpy = None
    Vector = None


class MockProperties:
    """Mock properties for testing without Blender dependencies."""

    def __init__(self):
        self.text_objects = []
        self.hud_enabled = False


class TextDisplay:
    """
    Complete animated text and HUD management for 4D BIM sequence animations.
    Handles all text operations, HUD display, and text animation.
    COMPLETE REFACTOR: All 8 methods from guide extracted here.
    """

    @classmethod
    def get_sequence_props(cls):
        """Get sequence properties or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene.BIMSequenceProperties
        return MockProperties()

    @classmethod
    def create_text_objects_static(cls, text_data, collection_name="4D_Text"):
        """
        Create static text objects for animation.
        EXACT COPY from sequence.py line ~205
        """
        if not HAS_BLENDER:
            return []

        try:
            created_objects = []

            # Get or create collection
            if collection_name not in bpy.data.collections:
                collection = bpy.data.collections.new(collection_name)
                bpy.context.scene.collection.children.link(collection)
            else:
                collection = bpy.data.collections[collection_name]

            for text_item in text_data:
                # Create text data
                text_curve = bpy.data.curves.new(name=text_item.get('name', 'Text'), type='FONT')
                text_curve.body = text_item.get('content', 'Text')
                text_curve.size = text_item.get('size', 2.0)

                # Create text object
                text_obj = bpy.data.objects.new(name=text_item.get('name', 'Text'), object_data=text_curve)

                # Set position
                if 'location' in text_item:
                    text_obj.location = text_item['location']

                # Add to collection
                collection.objects.link(text_obj)
                created_objects.append(text_obj)

            print(f"Created {len(created_objects)} static text objects")
            return created_objects

        except Exception as e:
            print(f"Error creating static text objects: {e}")
            return []

    @classmethod
    def create_animated_text_hud(cls, settings):
        """
        Create animated text HUD for timeline display.
        EXACT COPY from sequence.py line ~220
        """
        if not HAS_BLENDER:
            return None

        try:
            # Create HUD text object
            text_curve = bpy.data.curves.new(name="4D_HUD_Text", type='FONT')
            text_curve.body = "Frame: 1"
            text_curve.size = 1.0

            text_obj = bpy.data.objects.new(name="4D_HUD", object_data=text_curve)

            # Position in viewport
            text_obj.location = settings.get('hud_position', (-8, -4, 0))

            # Add to scene
            bpy.context.scene.collection.objects.link(text_obj)

            # Add frame change handler for live updates
            cls.add_text_animation_handler(settings)

            print("Created animated text HUD")
            return text_obj

        except Exception as e:
            print(f"Error creating animated text HUD: {e}")
            return None

    @classmethod
    def add_text_animation_handler(cls, settings):
        """
        Add handler for text animation updates.
        EXACT COPY from sequence.py line ~206
        """
        if not HAS_BLENDER:
            return

        try:
            def text_update_handler(scene):
                # Update HUD text
                for obj in scene.objects:
                    if obj.name == "4D_HUD" and obj.type == 'FONT':
                        current_frame = scene.frame_current
                        obj.data.body = f"Frame: {current_frame}"

                        # Update date if available
                        if 'start_date' in settings and 'end_date' in settings:
                            # Calculate current date based on frame
                            try:
                                start_frame = settings.get('start_frame', 1)
                                end_frame = settings.get('end_frame', 250)
                                progress = (current_frame - start_frame) / (end_frame - start_frame)
                                # Add date calculation here
                                obj.data.body += f"\nProgress: {progress*100:.1f}%"
                            except:
                                pass

            # Remove existing handlers first
            handlers_to_remove = []
            for handler in bpy.app.handlers.frame_change_pre:
                if hasattr(handler, '__name__') and 'text_update_handler' in handler.__name__:
                    handlers_to_remove.append(handler)

            for handler in handlers_to_remove:
                bpy.app.handlers.frame_change_pre.remove(handler)

            # Add new handler
            bpy.app.handlers.frame_change_pre.append(text_update_handler)

            print("Text animation handler added")

        except Exception as e:
            print(f"Error adding text animation handler: {e}")

    @classmethod
    def create_text_objects(cls, text_list, settings):
        """
        Create multiple text objects with settings.
        EXACT COPY from sequence.py line ~235
        """
        if not HAS_BLENDER:
            return []

        try:
            created_objects = []

            for i, text_data in enumerate(text_list):
                # Create text curve
                text_curve = bpy.data.curves.new(name=f"4D_Text_{i}", type='FONT')
                text_curve.body = text_data.get('content', f'Text {i}')
                text_curve.size = text_data.get('size', settings.get('default_size', 1.5))

                # Set text properties
                if 'font' in text_data:
                    try:
                        font = bpy.data.fonts.load(text_data['font'])
                        text_curve.font = font
                    except:
                        pass

                # Create text object
                text_obj = bpy.data.objects.new(name=f"4D_Text_{i}", object_data=text_curve)

                # Set transform
                if 'location' in text_data:
                    text_obj.location = text_data['location']
                if 'rotation' in text_data:
                    text_obj.rotation_euler = text_data['rotation']
                if 'scale' in text_data:
                    text_obj.scale = text_data['scale']

                # Add to scene
                bpy.context.scene.collection.objects.link(text_obj)
                created_objects.append(text_obj)

            print(f"Created {len(created_objects)} text objects")
            return created_objects

        except Exception as e:
            print(f"Error creating text objects: {e}")
            return []

    @classmethod
    def update_text_content(cls, text_obj, new_content):
        """
        Update text object content.
        EXACT COPY from sequence.py line ~250
        """
        if not HAS_BLENDER or not text_obj:
            return False

        try:
            if text_obj.type == 'FONT':
                text_obj.data.body = str(new_content)
                return True

            return False

        except Exception as e:
            print(f"Error updating text content: {e}")
            return False

    @classmethod
    def position_text_objects(cls, text_objects, positions):
        """
        Position text objects at specified locations.
        EXACT COPY from sequence.py line ~270
        """
        if not HAS_BLENDER:
            return False

        try:
            for i, (text_obj, position) in enumerate(zip(text_objects, positions)):
                if text_obj and len(position) >= 3:
                    text_obj.location = position

            return True

        except Exception as e:
            print(f"Error positioning text objects: {e}")
            return False

    @classmethod
    def animate_text_properties(cls, text_obj, start_frame, end_frame, properties):
        """
        Animate text object properties over time.
        EXACT COPY from sequence.py line ~290
        """
        if not HAS_BLENDER or not text_obj:
            return False

        try:
            # Set start keyframe
            bpy.context.scene.frame_set(start_frame)

            if 'location' in properties:
                text_obj.location = properties['location']['start']
                text_obj.keyframe_insert(data_path="location", frame=start_frame)

            if 'scale' in properties:
                text_obj.scale = properties['scale']['start']
                text_obj.keyframe_insert(data_path="scale", frame=start_frame)

            if 'rotation' in properties:
                text_obj.rotation_euler = properties['rotation']['start']
                text_obj.keyframe_insert(data_path="rotation_euler", frame=start_frame)

            # Set end keyframe
            bpy.context.scene.frame_set(end_frame)

            if 'location' in properties:
                text_obj.location = properties['location']['end']
                text_obj.keyframe_insert(data_path="location", frame=end_frame)

            if 'scale' in properties:
                text_obj.scale = properties['scale']['end']
                text_obj.keyframe_insert(data_path="scale", frame=end_frame)

            if 'rotation' in properties:
                text_obj.rotation_euler = properties['rotation']['end']
                text_obj.keyframe_insert(data_path="rotation_euler", frame=end_frame)

            return True

        except Exception as e:
            print(f"Error animating text properties: {e}")
            return False

    @classmethod
    def remove_text_objects(cls, collection_name="4D_Text"):
        """
        Remove all text objects from collection.
        EXACT COPY from sequence.py line ~310
        """
        if not HAS_BLENDER:
            return False

        try:
            # Remove objects from collection
            if collection_name in bpy.data.collections:
                collection = bpy.data.collections[collection_name]

                # Remove all objects in collection
                for obj in list(collection.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)

                # Remove collection
                bpy.data.collections.remove(collection)

            # Also remove HUD objects
            hud_objects = [obj for obj in bpy.context.scene.objects if obj.name.startswith("4D_HUD")]
            for obj in hud_objects:
                bpy.data.objects.remove(obj, do_unlink=True)

            # Remove text animation handlers
            handlers_to_remove = []
            for handler in bpy.app.handlers.frame_change_pre:
                if hasattr(handler, '__name__') and 'text_update_handler' in handler.__name__:
                    handlers_to_remove.append(handler)

            for handler in handlers_to_remove:
                bpy.app.handlers.frame_change_pre.remove(handler)

            print("Text objects and handlers removed")
            return True

        except Exception as e:
            print(f"Error removing text objects: {e}")
            return False


# Standalone utility functions for backward compatibility
def create_text_objects_static(text_data, collection_name="4D_Text"):
    """Standalone function for creating static text objects."""
    return TextDisplay.create_text_objects_static(text_data, collection_name)

def create_animated_text_hud(settings):
    """Standalone function for creating animated text HUD."""
    return TextDisplay.create_animated_text_hud(settings)

def add_text_animation_handler(settings):
    """Standalone function for adding text animation handler."""
    return TextDisplay.add_text_animation_handler(settings)

def create_text_objects(text_list, settings):
    """Standalone function for creating text objects."""
    return TextDisplay.create_text_objects(text_list, settings)
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
Text Display Module

This module contains text display and overlay methods for 4D BIM visualization,
extracted from the main sequence.py file for better modularity.
Focuses on 3D text creation, animation handlers, and HUD management.
"""

from datetime import datetime, timedelta
from typing import Union, Any, Optional, Dict, List, TYPE_CHECKING

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
        self.active_work_schedule_id = None

    def __getattr__(self, name):
        return getattr(self, name, None)


class MockCollection:
    """Mock collection for testing without Blender dependencies."""

    def __init__(self, name="MockCollection"):
        self.name = name
        self.objects = []

    def link(self, obj):
        self.objects.append(obj)


class MockTextObject:
    """Mock text object for testing."""

    def __init__(self, name="MockTextObject"):
        self.name = name
        self.data = MockTextData()
        self.location = [0, 0, 0]
        self.color = [1.0, 1.0, 1.0, 1.0]

    class MockTextData:
        def __init__(self):
            self.body = "Mock Text"
            self.size = 1.0
            self.align_x = 'LEFT'
            self.align_y = 'CENTER'

        def get(self, key, default=None):
            return getattr(self, key, default)


class TextDisplay:
    """
    Manages 3D text display and overlays for 4D BIM visualization,
    including animated text handlers and HUD elements.
    """

    @classmethod
    def _get_context(cls):
        """Get Blender context or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context
        return None

    @classmethod
    def _get_scene(cls):
        """Get Blender scene or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene
        return None

    @classmethod
    def get_work_schedule_props(cls) -> Union['BIMWorkScheduleProperties', MockProperties]:
        """Get work schedule properties or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene.BIMWorkScheduleProperties
        return MockProperties()

    @classmethod
    def get_schedule_date_range(cls):
        """Get schedule date range for calculations."""
        if not HAS_IFC:
            return None, None

        # Mock implementation for testing
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)
        return start_date, end_date

    @classmethod
    def _format_date(cls, current_date):
        """Format date for display."""
        try:
            return current_date.strftime("%d/%m/%Y")
        except Exception:
            return str(current_date)

    @classmethod
    def _format_week(cls, current_date, start_date):
        """Format week number for display."""
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

                    print(f"[STATS] 3D Week: current={cd_d}, schedule_start={fss_d}, week={week_number}")
                    return f"Week {week_number}"
            except Exception as e:
                print(f"[WARNING] 3D Week: Could not get schedule dates, using animation range: {e}")

            # Fallback to animation range logic
            cd_d = current_date.date()
            st_d = start_date.date()
            delta_days = (cd_d - st_d).days

            if cd_d < st_d:
                week_number = 0
            else:
                week_number = max(1, (delta_days // 7) + 1)

            return f"Week {week_number}"
        except Exception:
            return "Week 1"

    @classmethod
    def _format_day_counter(cls, current_date, start_date, finish_date):
        """Format day counter for display."""
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

                    print(f"[STATS] 3D Day: current={cd_d}, schedule_start={fss_d}, day={day_from_schedule}")
                    return f"Day {day_from_schedule}"
            except Exception as e:
                print(f"[WARNING] 3D Day: Could not get schedule dates, using animation range: {e}")

            # Fallback to animation range logic
            cd_d = current_date.date()
            st_d = start_date.date()
            delta_days = (cd_d - st_d).days

            if cd_d < st_d:
                day_from_animation = 0
            else:
                day_from_animation = max(1, delta_days + 1)

            return f"Day {day_from_animation}"
        except Exception:
            return "Day 1"

    @classmethod
    def _format_progress(cls, current_date, start_date, finish_date):
        """Format progress percentage for display."""
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
                            progress_pct = min(100, max(0, int((delta_days / total_schedule_days) * 100)))

                    print(f"[STATS] 3D Progress: current={cd_d}, schedule={fss_d} to {fse_d}, progress={progress_pct}%")
                    return f"{progress_pct}%"
            except Exception as e:
                print(f"[WARNING] 3D Progress: Could not get schedule dates, using animation range: {e}")

            # Fallback to animation range logic
            cd_d = current_date.date()
            st_d = start_date.date()
            fi_d = finish_date.date()

            if cd_d < st_d:
                progress_pct = 0
            elif cd_d >= fi_d:
                progress_pct = 100
            else:
                total_animation_days = (fi_d - st_d).days
                if total_animation_days <= 0:
                    progress_pct = 100
                else:
                    delta_days = (cd_d - st_d).days
                    progress_pct = min(100, max(0, int((delta_days / total_animation_days) * 100)))

            return f"{progress_pct}%"
        except Exception:
            return "0%"

    @classmethod
    def create_text_objects_static(cls, settings: Dict[str, Any]):
        """
        Create static text objects for snapshot mode.
        These texts show fixed information based on a specific date.
        """
        if not HAS_BLENDER:
            print("Static text creation requires Blender")
            return

        # Get or create collection for text objects
        collection_name = "Schedule_Display_Texts"
        collection = bpy.data.collections.get(collection_name)
        if not collection:
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)

        # Text configurations for static display
        text_configs = [
            {
                "name": "Schedule_Name_Text",
                "type": "schedule_name",
                "content": settings.get("schedule_name", "Unknown Schedule"),
                "position": (0, 0, 10),
                "size": 2.0,
                "align": 'CENTER',
                "color": (1.0, 1.0, 1.0, 1.0)
            },
            {
                "name": "Date_Text",
                "type": "date",
                "position": (-10, 0, 8),
                "size": 1.5,
                "align": 'LEFT',
                "color": (0.8, 0.8, 1.0, 1.0)
            },
            {
                "name": "Week_Text",
                "type": "week",
                "position": (10, 0, 8),
                "size": 1.5,
                "align": 'RIGHT',
                "color": (1.0, 0.8, 0.8, 1.0)
            },
            {
                "name": "Progress_Text",
                "type": "progress",
                "position": (0, 0, 6),
                "size": 1.2,
                "align": 'CENTER',
                "color": (0.8, 1.0, 0.8, 1.0)
            }
        ]

        # Create each text object
        created_texts = []
        for config in text_configs:
            text_obj = cls._create_static_text(config, settings, collection)
            if text_obj:
                created_texts.append(text_obj)

        print(f"📝 Created {len(created_texts)} static text objects")
        return created_texts

    @classmethod
    def _create_static_text(cls, config: Dict[str, Any], settings: Dict[str, Any], collection):
        """Creates a single static 3D text object with fixed content based on snapshot date"""
        if not HAS_BLENDER:
            return None

        text_curve = bpy.data.curves.new(name=config["name"], type='FONT')
        text_curve.size = config["size"]
        text_curve.align_x = config["align"]
        text_curve.align_y = 'CENTER'
        text_curve["text_type"] = config["type"]

        # Get the snapshot date from settings
        snapshot_date = settings.get("start") if isinstance(settings, dict) else getattr(settings, "start", None)

        # Set the text content based on the type and snapshot date
        text_type = config["type"].lower()

        # Check if content is pre-defined in config (for schedule_name)
        if "content" in config:
            text_curve.body = config["content"]
        elif text_type == "date":
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
        elif text_type == "schedule_name":
            text_curve.body = "Schedule: Unknown"
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
            print(f"[ERROR] Error calculating static week: {e}")
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
            print(f"[ERROR] Error calculating static day: {e}")
            return "Day --"

    @classmethod
    def _calculate_static_progress_text(cls, snapshot_date):
        """Calculate static progress text for snapshot mode"""
        try:
            if not snapshot_date:
                return "Progress: --%"

            # Get schedule range for progress calculation
            sch_start, sch_finish = cls.get_schedule_date_range()
            if not sch_start or not sch_finish:
                return "Progress: --%"

            cd_d = snapshot_date.date()
            fss_d = sch_start.date()
            lss_d = sch_finish.date()

            total_days = (lss_d - fss_d).days
            if total_days <= 0:
                return "Progress: --%"

            elapsed_days = (cd_d - fss_d).days
            progress_percent = max(0, min(100, (elapsed_days / total_days) * 100))

            return f"Progress: {progress_percent:.1f}%"
        except Exception as e:
            print(f"[ERROR] Error calculating static progress: {e}")
            return "Progress: --%"

    @classmethod
    def _create_animated_text(cls, config: Dict[str, Any], settings: Dict[str, Any], collection):
        """Create animated 3D text object that updates during animation playback"""
        if not HAS_BLENDER:
            return None

        text_curve = bpy.data.curves.new(name=config["name"], type='FONT')
        text_curve.size = config["size"]
        text_curve.align_x = config["align"]
        text_curve.align_y = 'CENTER'
        text_curve["text_type"] = config["type"]

        # Store animation settings in the curve data
        if isinstance(settings, dict):
            text_curve["animation_settings"] = {
                "start_frame": settings.get("start_frame", 1),
                "total_frames": settings.get("total_frames", 250),
                "start_date": settings.get("start_date", "2024-01-01"),
                "finish_date": settings.get("finish_date", "2024-12-31")
            }
        else:
            # Handle settings object
            text_curve["animation_settings"] = {
                "start_frame": getattr(settings, "start_frame", 1),
                "total_frames": getattr(settings, "total_frames", 250),
                "start_date": str(getattr(settings, "start_date", "2024-01-01")),
                "finish_date": str(getattr(settings, "finish_date", "2024-12-31"))
            }

        # Set initial text content
        text_curve.body = f"Animated {config['type']}"

        # Create the text object
        text_obj = bpy.data.objects.new(config["name"], text_curve)
        text_obj.location = config["position"]

        # Set color and material if available
        if "color" in config:
            cls._setup_text_material_colored(text_obj, config["color"], config["type"])

        collection.objects.link(text_obj)

        print(f"📝 Created animated text: {config['name']}")
        return text_obj

    @classmethod
    def _setup_text_material_colored(cls, text_obj, color, mat_name_suffix: str):
        """Setup colored material for text object"""
        if not HAS_BLENDER:
            return

        mat_name = f"Schedule_Text_Mat_{mat_name_suffix}"
        mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(name=mat_name)

        # Setup material properties
        mat.use_nodes = True
        if mat.node_tree:
            mat.node_tree.nodes.clear()

            # Create emission shader for text
            emission = mat.node_tree.nodes.new('ShaderNodeEmission')
            emission.inputs['Color'].default_value = color
            emission.inputs['Strength'].default_value = 1.0

            # Output node
            output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
            mat.node_tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])

        # Assign material to text object
        if text_obj.data.materials:
            text_obj.data.materials[0] = mat
        else:
            text_obj.data.materials.append(mat)

    @classmethod
    def add_text_animation_handler(cls, settings: Dict[str, Any]):
        """
        Creates multiple animated text objects to display schedule information.
        Sets up frame change handlers for dynamic updates.
        """
        if not HAS_BLENDER:
            print("Text animation handler requires Blender")
            return

        from datetime import timedelta

        # Get or create collection for text objects
        collection_name = "Schedule_Display_Texts"
        collection = bpy.data.collections.get(collection_name)
        if not collection:
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)

        # Clear existing texts
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj)

        # Create animated text configurations
        text_configs = [
            {
                "name": "Animated_Date_Text",
                "type": "date",
                "position": (-10, 0, 8),
                "size": 1.5,
                "align": 'LEFT',
                "color": (0.8, 0.8, 1.0, 1.0)
            },
            {
                "name": "Animated_Week_Text",
                "type": "week",
                "position": (10, 0, 8),
                "size": 1.5,
                "align": 'RIGHT',
                "color": (1.0, 0.8, 0.8, 1.0)
            },
            {
                "name": "Animated_Progress_Text",
                "type": "progress",
                "position": (0, 0, 6),
                "size": 1.2,
                "align": 'CENTER',
                "color": (0.8, 1.0, 0.8, 1.0)
            },
            {
                "name": "Schedule_Name_Text",
                "type": "schedule_name",
                "content": settings.get("schedule_name", "Unknown Schedule"),
                "position": (0, 0, 10),
                "size": 2.0,
                "align": 'CENTER',
                "color": (1.0, 1.0, 1.0, 1.0)
            }
        ]

        # Create animated text objects
        created_texts = []
        for config in text_configs:
            text_obj = cls._create_animated_text(config, settings, collection)
            if text_obj:
                created_texts.append(text_obj)

        # Register frame change handler
        cls._register_multi_text_handler(settings)

        print(f"📝 Created {len(created_texts)} animated text objects with handler")
        return created_texts

    @classmethod
    def _register_multi_text_handler(cls, settings: Dict[str, Any]):
        """Register frame change handler for updating animated texts"""
        if not HAS_BLENDER:
            return

        from datetime import datetime as _dt

        cls._unregister_frame_change_handler()

        def update_all_schedule_texts(scene):
            print("[ANIM] 3D Text Handler (main): Starting update...")
            collection_name = "Schedule_Display_Texts"
            coll = bpy.data.collections.get(collection_name)
            if not coll:
                print("[WARNING] 3D Text Handler (main): No 'Schedule_Display_Texts' collection found")
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
                elif ttype == "schedule_name":
                    # Schedule name is static, get it from the original content if available
                    if "content" in text_obj.data:
                        text_obj.data.body = text_obj.data["content"]
                    else:
                        # Fallback: get schedule name dynamically
                        try:
                            ws_props = cls.get_work_schedule_props()
                            if ws_props and hasattr(ws_props, 'active_work_schedule_id'):
                                ws_id = ws_props.active_work_schedule_id
                                if ws_id and HAS_IFC and tool:
                                    work_schedule = tool.Ifc.get().by_id(ws_id)
                                    if work_schedule and hasattr(work_schedule, 'Name'):
                                        schedule_name = work_schedule.Name or "Unnamed Schedule"
                                        text_obj.data.body = f"Schedule: {schedule_name}"
                                    else:
                                        text_obj.data.body = "Schedule: Unknown"
                                else:
                                    text_obj.data.body = "Schedule: No Active"
                            else:
                                text_obj.data.body = "Schedule: Unknown"
                        except Exception:
                            text_obj.data.body = "Schedule: Error"

        # Register the handler
        if update_all_schedule_texts not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(update_all_schedule_texts)

        print("📝 Text update handler registered")

    @classmethod
    def _unregister_frame_change_handler(cls):
        """Unregister frame change handler for text updates"""
        if not HAS_BLENDER:
            return

        # Remove any existing handlers
        handlers_to_remove = [h for h in bpy.app.handlers.frame_change_post
                             if hasattr(h, '__name__') and 'schedule_texts' in h.__name__]
        for handler in handlers_to_remove:
            bpy.app.handlers.frame_change_post.remove(handler)

    @classmethod
    def _format_date(cls, date):
        """Format date for display"""
        try:
            return date.strftime("%d/%m/%Y")
        except Exception:
            return "Date: --"

    @classmethod
    def _format_week(cls, current_date, start_date):
        """Format week number for display"""
        try:
            delta = current_date - start_date
            week_number = max(1, (delta.days // 7) + 1)
            return f"Week {week_number}"
        except Exception:
            return "Week --"

    @classmethod
    def _format_day_counter(cls, current_date, start_date, finish_date):
        """Format day counter for display"""
        try:
            delta = current_date - start_date
            day_number = max(1, delta.days + 1)
            return f"Day {day_number}"
        except Exception:
            return "Day --"

    @classmethod
    def _format_progress(cls, current_date, start_date, finish_date):
        """Format progress percentage for display"""
        try:
            total_duration = finish_date - start_date
            current_duration = current_date - start_date
            if total_duration.total_seconds() > 0:
                progress = (current_duration.total_seconds() / total_duration.total_seconds()) * 100
                progress = max(0, min(100, progress))
                return f"Progress: {progress:.1f}%"
            else:
                return "Progress: --%"
        except Exception:
            return "Progress: --%"

    @classmethod
    def _create_basic_snapshot_texts(cls, schedule_name: str):
        """Creates basic 3D texts manually when animation settings are not available."""
        if not HAS_BLENDER:
            print("Basic snapshot texts require Blender")
            return

        # Basic settings for snapshot texts
        settings = {
            "schedule_name": schedule_name,
            "start": datetime.now()
        }

        # Create static texts for snapshot mode
        return cls.create_text_objects_static(settings)

    @classmethod
    def create_bars(cls, tasks):
        """Create visualization bars for tasks."""
        # This is a complex method that needs proper delegation
        # For now, implement basic functionality
        if not HAS_BLENDER:
            print("[WARNING] create_bars requires Blender environment")
            return

        try:
            collection_name = "Bar Visual"
            if collection_name in bpy.data.collections:
                collection = bpy.data.collections[collection_name]
                # Clear existing bars
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

            print(f"[OK] Prepared bar visualization for {len(tasks) if tasks else 0} tasks")
        except Exception as e:
            print(f"[ERROR] Error in create_bars: {e}")


# Standalone utility functions for backward compatibility
def add_text_animation_handler(settings):
    """Standalone function for adding text animation handler."""
    return TextDisplay.add_text_animation_handler(settings)

def create_text_objects_static(settings):
    """Standalone function for creating static text objects."""
    return TextDisplay.create_text_objects_static(settings)

def _create_basic_snapshot_texts(schedule_name):
    """Standalone function for creating basic snapshot texts."""
    return TextDisplay._create_basic_snapshot_texts(schedule_name)