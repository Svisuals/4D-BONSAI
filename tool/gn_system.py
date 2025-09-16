# Geometry Nodes 4D System - Core System Module
# Complete Geometry Nodes 4D Animation System for Bonsai
# This file provides the core low-level functions for the GN system

"""
GEOMETRY NODES 4D SYSTEM - Core System Module

This module provides the core low-level functionality for writing task attributes
to mesh geometry and updating Geometry Nodes modifier inputs.

Based on V113 implementation with improvements:
- Robust attribute writing to object mesh data
- Safe modifier socket updates with fallback methods
- Integration with existing Bonsai task and ColorType systems
"""

import bpy
from typing import Optional, Dict, Any

try:
    import bonsai.tool as tool
    import ifcopenshell
except ImportError:
    # For development context where bonsai.tool might not be available
    tool = None
    ifcopenshell = None

# Constants for Geometry Nodes system
GN_MODIFIER_NAME = "Bonsai 4D"
GN_NODETREE_NAME = "Bonsai 4D Node Tree"

# Attribute names for task data (compatible with gn_sequence_core)
ATTR_TASK_START_FRAME = "schedule_start"
ATTR_TASK_END_FRAME = "schedule_end"
ATTR_TASK_COLOR = "bonsai_task_color"
ATTR_CURRENT_FRAME = "bonsai_current_frame"

# Additional V113 attributes for cleanup
ATTR_SCHEDULE_DURATION = "schedule_duration"
ATTR_ACTUAL_START = "actual_start"
ATTR_ACTUAL_END = "actual_end"
ATTR_ACTUAL_DURATION = "actual_duration"
ATTR_EFFECT_TYPE = "effect_type"
ATTR_COLORTYPE_ID = "colortype_id"
ATTR_VISIBILITY_BEFORE_START = "visibility_before_start"
ATTR_VISIBILITY_AFTER_END = "visibility_after_end"
ATTR_ANIMATION_STATE = "animation_state"


def update_task_attributes_on_object(obj, task):
    """
    Core function: Write task data as attributes to object's mesh data

    This is the heart of the system - it writes task timing and color information
    directly to the mesh geometry so that Geometry Nodes can read it.

    Args:
        obj: Blender object (must be MESH type)
        task: Bonsai task object with scheduling data

    Returns:
        bool: True if attributes were successfully written
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        print(f"⚠️ Invalid object for GN attributes: {obj.name if obj else 'None'}")
        return False

    if not task or not hasattr(task, 'ScheduleStart') or not hasattr(task, 'ScheduleFinish'):
        print(f"⚠️ Invalid task for GN attributes")
        return False

    print(f"📝 Writing GN attributes for object: {obj.name}")

    try:
        mesh = obj.data

        # Get or create attribute for start frame
        start_attr = mesh.attributes.get(ATTR_TASK_START_FRAME)
        if not start_attr:
            start_attr = mesh.attributes.new(ATTR_TASK_START_FRAME, 'FLOAT', 'POINT')

        # Get or create attribute for end frame
        end_attr = mesh.attributes.get(ATTR_TASK_END_FRAME)
        if not end_attr:
            end_attr = mesh.attributes.new(ATTR_TASK_END_FRAME, 'FLOAT', 'POINT')

        # Get or create attribute for task color
        color_attr = mesh.attributes.get(ATTR_TASK_COLOR)
        if not color_attr:
            color_attr = mesh.attributes.new(ATTR_TASK_COLOR, 'FLOAT_COLOR', 'POINT')

        # Convert task dates to frames (using same logic as keyframe system)
        if tool:
            settings = tool.Sequence.get_animation_settings()
            if settings:
                # Calculate frame numbers from task dates
                viz_start = settings['start']
                viz_duration = settings['duration']
                total_frames = settings['total_frames']

                # Convert task start/finish to frame numbers
                task_start_days = (task.ScheduleStart - viz_start).days
                task_end_days = (task.ScheduleFinish - viz_start).days

                start_frame = int((task_start_days / viz_duration.days) * total_frames)
                end_frame = int((task_end_days / viz_duration.days) * total_frames)

                print(f"   Task frames: {start_frame} to {end_frame}")

                # Write start frame to all points
                for i in range(len(start_attr.data)):
                    start_attr.data[i].value = float(start_frame)

                # Write end frame to all points
                for i in range(len(end_attr.data)):
                    end_attr.data[i].value = float(end_frame)

                # Get task color (simplified - use default construction color)
                task_color = (0.8, 0.6, 0.2, 1.0)  # Orange construction color

                # Write color to all points
                for i in range(len(color_attr.data)):
                    color_attr.data[i].color = task_color

                print(f"✅ Successfully wrote GN attributes for {obj.name}")
                return True

        print(f"⚠️ Could not get animation settings for {obj.name}")
        return False

    except Exception as e:
        print(f"❌ Error writing GN attributes for {obj.name}: {e}")
        return False


def update_modifier_sockets_for_object(obj):
    """
    Update GN modifier inputs (sockets) with global animation data

    This function updates "global" parameters that are the same for all objects,
    like current frame, speed multiplier, etc.

    Args:
        obj: Blender object with GN modifier

    Returns:
        bool: True if modifier was successfully updated
    """
    if not obj or obj.type != 'MESH':
        return False

    # Find the GN modifier
    gn_modifier = None
    for mod in obj.modifiers:
        if mod.name == GN_MODIFIER_NAME and mod.type == 'NODES':
            gn_modifier = mod
            break

    if not gn_modifier:
        print(f"⚠️ No GN modifier found on {obj.name}")
        return False

    try:
        # Update current frame (this drives the animation)
        current_frame = float(bpy.context.scene.frame_current)

        # Try multiple socket access methods for robustness
        frame_updated = False

        # Method 1: Try by identifier (most robust)
        if hasattr(gn_modifier, 'node_group') and gn_modifier.node_group:
            for input_socket in gn_modifier.node_group.inputs:
                if input_socket.name in ['Current Frame', 'Frame', 'bonsai_current_frame']:
                    try:
                        gn_modifier[input_socket.identifier] = current_frame
                        frame_updated = True
                        print(f"✅ Updated frame via identifier for {obj.name}: {current_frame}")
                        break
                    except Exception:
                        continue

        # Method 2: Try by index (V113 method)
        if not frame_updated:
            try:
                # Try common socket indices for frame input
                for socket_index in [0, 1, 2, 3, 4]:
                    try:
                        gn_modifier.inputs[socket_index].default_value = current_frame
                        frame_updated = True
                        print(f"✅ Updated frame via index {socket_index} for {obj.name}: {current_frame}")
                        break
                    except (IndexError, AttributeError):
                        continue
            except Exception:
                pass

        # Method 3: Try by hardcoded names (fallback)
        if not frame_updated:
            for socket_name in ['Socket_0', 'Input_4', 'Current Frame']:
                try:
                    if hasattr(gn_modifier, socket_name):
                        setattr(gn_modifier, socket_name, current_frame)
                        frame_updated = True
                        print(f"✅ Updated frame via name {socket_name} for {obj.name}: {current_frame}")
                        break
                except Exception:
                    continue

        if not frame_updated:
            print(f"⚠️ Could not update frame for {obj.name} - no accessible sockets found")
            return False

        return True

    except Exception as e:
        print(f"❌ Error updating GN modifier for {obj.name}: {e}")
        return False


def add_object_to_gn_references(obj):
    """
    Add an object to the centralized GN references collection

    Args:
        obj: Blender object to add to GN management

    Returns:
        bool: True if object was added successfully
    """
    if not tool:
        print("⚠️ Bonsai tool not available - cannot add to GN references")
        return False

    try:
        anim_props = tool.Sequence.get_animation_props()
        if not anim_props:
            print("⚠️ Could not get animation properties")
            return False

        # Check if object is already in references
        for ref in anim_props.gn_object_references:
            if ref.obj == obj:
                print(f"✅ Object {obj.name} already in GN references")
                return True

        # Add new reference
        new_ref = anim_props.gn_object_references.add()
        new_ref.obj = obj

        print(f"✅ Added {obj.name} to GN references")
        return True

    except Exception as e:
        print(f"❌ Error adding {obj.name} to GN references: {e}")
        return False


def remove_object_from_gn_references(obj):
    """
    Remove an object from the GN references collection

    Args:
        obj: Blender object to remove from GN management

    Returns:
        bool: True if object was removed successfully
    """
    if not tool:
        return False

    try:
        anim_props = tool.Sequence.get_animation_props()
        if not anim_props:
            return False

        # Find and remove the reference
        for i, ref in enumerate(anim_props.gn_object_references):
            if ref.obj == obj:
                anim_props.gn_object_references.remove(i)
                print(f"✅ Removed {obj.name} from GN references")
                return True

        print(f"⚠️ Object {obj.name} not found in GN references")
        return False

    except Exception as e:
        print(f"❌ Error removing {obj.name} from GN references: {e}")
        return False


def get_gn_managed_objects():
    """
    Get all objects currently managed by the GN system

    Returns:
        list: List of Blender objects managed by GN system
    """
    if not tool:
        return []

    try:
        anim_props = tool.Sequence.get_animation_props()
        if not anim_props:
            return []

        managed_objects = []
        for ref in anim_props.gn_object_references:
            if ref.obj and ref.obj.name in bpy.data.objects:
                managed_objects.append(ref.obj)

        return managed_objects

    except Exception as e:
        print(f"❌ Error getting GN managed objects: {e}")
        return []


def update_all_gn_objects():
    """
    Update all GN-managed objects with current frame and settings

    This function is called when the frame changes or settings update
    to keep all GN objects synchronized.

    Returns:
        int: Number of objects successfully updated
    """
    managed_objects = get_gn_managed_objects()
    if not managed_objects:
        print("⚠️ No GN managed objects found")
        return 0

    updated_count = 0
    for obj in managed_objects:
        if update_modifier_sockets_for_object(obj):
            updated_count += 1

    print(f"✅ Updated {updated_count}/{len(managed_objects)} GN objects")
    return updated_count


def clean_gn_attributes_from_object(obj):
    """
    Remove all GN attributes from an object's mesh

    Args:
        obj: Blender object to clean

    Returns:
        bool: True if attributes were cleaned successfully
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return False

    try:
        mesh = obj.data
        attrs_to_remove = [
            ATTR_TASK_START_FRAME,
            ATTR_TASK_END_FRAME,
            ATTR_TASK_COLOR,
            ATTR_CURRENT_FRAME,
            ATTR_SCHEDULE_DURATION,
            ATTR_ACTUAL_START,
            ATTR_ACTUAL_END,
            ATTR_ACTUAL_DURATION,
            ATTR_EFFECT_TYPE,
            ATTR_COLORTYPE_ID,
            ATTR_VISIBILITY_BEFORE_START,
            ATTR_VISIBILITY_AFTER_END,
            ATTR_ANIMATION_STATE
        ]

        removed_count = 0
        for attr_name in attrs_to_remove:
            if mesh.attributes.get(attr_name):
                mesh.attributes.remove(mesh.attributes[attr_name])
                removed_count += 1

        if removed_count > 0:
            print(f"✅ Cleaned {removed_count} GN attributes from {obj.name}")
        return True

    except Exception as e:
        print(f"❌ Error cleaning GN attributes from {obj.name}: {e}")
        return False


# Export main functions for use by integration layer
__all__ = [
    'update_task_attributes_on_object',
    'update_modifier_sockets_for_object',
    'add_object_to_gn_references',
    'remove_object_from_gn_references',
    'get_gn_managed_objects',
    'update_all_gn_objects',
    'clean_gn_attributes_from_object',
    'GN_MODIFIER_NAME',
    'GN_NODETREE_NAME'
]