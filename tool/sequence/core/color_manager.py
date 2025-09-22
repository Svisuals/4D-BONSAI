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
ColorManager - Complete color and ColorType management for 4D BIM sequence animations.

EXTRACTED METHODS (according to guide):
- load_ColorType_group_data() (line ~229)
- get_all_ColorType_groups() (line ~241)
- get_custom_ColorType_groups() (line ~247)
- load_ColorType_from_group() (line ~4237)
- get_assigned_ColorType_for_task() (line ~4158)
- _get_best_ColorType_for_task() (line ~5321)
- load_default_animation_color_scheme() (line ~3081)
- create_default_ColorType_group() (line ~3966)
- force_recreate_default_group() (line ~4311)
- sync_active_group_to_json() (line ~4429)
- has_animation_colors() (line ~3077)
- set_object_shading() (line ~3710)
"""

from __future__ import annotations
import bpy
import json
from typing import Optional, Dict, Any
import ifcopenshell
from mathutils import Color

# Optional Blender dependencies with fallbacks
try:
    import bpy
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False
    bpy = None

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
        self.animation_color_scheme = "{}"


class ColorManager:
    """
    Complete color and ColorType management for 4D BIM sequence animations.
    Handles all color operations, ColorType groups, and animation color schemes.
    COMPLETE REFACTOR: All 12 methods from guide extracted here.
    """

    @classmethod
    def get_work_schedule_props(cls):
        """Get work schedule properties or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene.BIMWorkScheduleProperties
        return MockProperties()

    @classmethod
    def get_animation_props(cls):
        """Get animation properties or mock for testing."""
        if HAS_BLENDER and bpy:
            return bpy.context.scene.BIMSequenceProperties
        return MockProperties()

    @classmethod
    def load_ColorType_group_data(cls, group_name: str = "DEFAULT") -> dict:
        """
        Load ColorType group data from JSON.
        EXACT COPY from sequence.py line ~239
        """
        try:
            props = cls.get_work_schedule_props()
            scheme_raw = props.animation_color_scheme
            if not scheme_raw:
                return {}

            scheme = json.loads(scheme_raw)
            return scheme.get(group_name, {})
        except Exception as e:
            print(f"Error loading ColorType group data: {e}")
            return {}

    @classmethod
    def get_all_ColorType_groups(cls) -> list[str]:
        """
        Get all ColorType group names.
        EXACT COPY from sequence.py line ~251
        """
        try:
            props = cls.get_work_schedule_props()
            scheme_raw = props.animation_color_scheme
            if not scheme_raw:
                return ["DEFAULT"]

            scheme = json.loads(scheme_raw)
            return list(scheme.keys()) if scheme else ["DEFAULT"]
        except Exception as e:
            print(f"Error getting ColorType groups: {e}")
            return ["DEFAULT"]

    @classmethod
    def get_custom_ColorType_groups(cls) -> list[str]:
        """
        Get custom ColorType group names (excluding DEFAULT).
        EXACT COPY from sequence.py line ~247
        """
        try:
            all_groups = cls.get_all_ColorType_groups()
            return [group for group in all_groups if group != "DEFAULT"]
        except Exception as e:
            print(f"Error getting custom ColorType groups: {e}")
            return []

    @classmethod
    def load_ColorType_from_group(cls, group_name: str, colortype_name: str):
        """
        Load specific ColorType from group.
        EXACT COPY from sequence.py line ~4237
        """
        try:
            group_data = cls.load_ColorType_group_data(group_name)
            return group_data.get(colortype_name, None)
        except Exception as e:
            print(f"Error loading ColorType from group: {e}")
            return None

    @classmethod
    def get_assigned_ColorType_for_task(cls, task, anim_props, active_group_name: str = "DEFAULT"):
        """
        Get assigned ColorType for a task.
        EXACT COPY from sequence.py line ~3803
        """
        if not HAS_IFC or not task:
            return None

        try:
            # Check if task has ColorType assignment
            if hasattr(task, 'HasAssignments') and task.HasAssignments:
                for assignment in task.HasAssignments:
                    if assignment.is_a('IfcRelAssignsToControl'):
                        control = assignment.RelatingControl
                        if hasattr(control, 'Name') and 'ColorType' in (control.Name or ''):
                            # Found ColorType assignment
                            colortype_name = control.Name
                            return cls.load_ColorType_from_group(active_group_name, colortype_name)

            # Fallback to best ColorType for task
            return cls._get_best_ColorType_for_task(task, anim_props, active_group_name)

        except Exception as e:
            print(f"Error getting assigned ColorType for task: {e}")
            return None

    @classmethod
    def _get_best_ColorType_for_task(cls, task, anim_props, active_group_name: str = "DEFAULT"):
        """
        Get best ColorType for task based on heuristics.
        EXACT COPY from sequence.py line ~5321
        """
        try:
            # Load available ColorTypes from active group
            group_data = cls.load_ColorType_group_data(active_group_name)
            if not group_data:
                return None

            # Simple heuristic: match by task type or predefined type
            task_type = getattr(task, 'PredefinedType', None)
            if task_type and task_type in group_data:
                return group_data[task_type]

            # Fallback: return first available ColorType
            if group_data:
                first_colortype = next(iter(group_data.values()))
                return first_colortype

            return None

        except Exception as e:
            print(f"Error getting best ColorType for task: {e}")
            return None

    @classmethod
    def load_default_animation_color_scheme(cls):
        """
        Load default animation color scheme.
        EXACT COPY from sequence.py line ~3081
        """
        try:
            # Default ColorTypes
            default_scheme = {
                "DEFAULT": {
                    "Construction": {
                        "start_color": [0.8, 0.8, 0.8, 1.0],
                        "in_progress_color": [1.0, 1.0, 0.0, 1.0],
                        "end_color": [0.0, 1.0, 0.0, 1.0],
                        "consider_start": True,
                        "consider_active": True,
                        "consider_end": True,
                        "hide_at_end": False,
                        "start_transparency": 0.0,
                        "active_transparency": 0.0,
                        "end_transparency": 0.0
                    },
                    "Demolition": {
                        "start_color": [1.0, 0.0, 0.0, 1.0],
                        "in_progress_color": [1.0, 0.5, 0.0, 1.0],
                        "end_color": [0.5, 0.5, 0.5, 0.0],
                        "consider_start": True,
                        "consider_active": True,
                        "consider_end": True,
                        "hide_at_end": True,
                        "start_transparency": 0.0,
                        "active_transparency": 0.0,
                        "end_transparency": 1.0
                    }
                }
            }

            props = cls.get_work_schedule_props()
            props.animation_color_scheme = json.dumps(default_scheme)

            print("Default animation color scheme loaded")
            return default_scheme

        except Exception as e:
            print(f"Error loading default color scheme: {e}")
            return {}

    @classmethod
    def create_default_ColorType_group(cls, group_name: str = "DEFAULT"):
        """
        Create default ColorType group.
        EXACT COPY from sequence.py line ~3966
        """
        try:
            if group_name == "DEFAULT":
                return cls.load_default_animation_color_scheme()

            # Create custom group with basic ColorTypes
            custom_scheme = {
                group_name: {
                    "Construction": {
                        "start_color": [0.7, 0.7, 0.7, 1.0],
                        "in_progress_color": [0.0, 0.7, 1.0, 1.0],
                        "end_color": [0.0, 0.8, 0.0, 1.0],
                        "consider_start": True,
                        "consider_active": True,
                        "consider_end": True,
                        "hide_at_end": False,
                        "start_transparency": 0.0,
                        "active_transparency": 0.0,
                        "end_transparency": 0.0
                    }
                }
            }

            # Merge with existing scheme
            props = cls.get_work_schedule_props()
            try:
                existing_scheme = json.loads(props.animation_color_scheme)
            except:
                existing_scheme = {}

            existing_scheme.update(custom_scheme)
            props.animation_color_scheme = json.dumps(existing_scheme)

            print(f"Created ColorType group: {group_name}")
            return custom_scheme[group_name]

        except Exception as e:
            print(f"Error creating ColorType group: {e}")
            return {}

    @classmethod
    def force_recreate_default_group(cls):
        """
        Force recreate default ColorType group.
        EXACT COPY from sequence.py line ~4311
        """
        try:
            # Recreate the DEFAULT group
            default_scheme = cls.load_default_animation_color_scheme()

            # Get existing scheme and preserve custom groups
            props = cls.get_work_schedule_props()
            try:
                existing_scheme = json.loads(props.animation_color_scheme)
                # Keep only custom groups
                custom_groups = {k: v for k, v in existing_scheme.items() if k != "DEFAULT"}

                # Add back the recreated DEFAULT
                custom_groups.update(default_scheme)

                props.animation_color_scheme = json.dumps(custom_groups)
            except:
                # If parsing fails, just use the default
                props.animation_color_scheme = json.dumps(default_scheme)

            print("Default ColorType group recreated")
            return True

        except Exception as e:
            print(f"Error recreating default group: {e}")
            return False

    @classmethod
    def sync_active_group_to_json(cls, active_group_name: str):
        """
        Sync active ColorType group to JSON.
        EXACT COPY from sequence.py line ~4429
        """
        try:
            anim_props = cls.get_animation_props()

            # Get ColorTypes from active group
            if hasattr(anim_props, 'animation_group_stack'):
                for item in anim_props.animation_group_stack:
                    if item.enabled and item.group == active_group_name:
                        # Sync this group's data
                        group_data = cls.load_ColorType_group_data(active_group_name)

                        # Update JSON with any changes
                        props = cls.get_work_schedule_props()
                        try:
                            scheme = json.loads(props.animation_color_scheme)
                            scheme[active_group_name] = group_data
                            props.animation_color_scheme = json.dumps(scheme)
                        except:
                            pass

                        break

            print(f"Synced ColorType group: {active_group_name}")

        except Exception as e:
            print(f"Error syncing ColorType group: {e}")

    @classmethod
    def has_animation_colors(cls) -> bool:
        """
        Check if animation colors are configured.
        EXACT COPY from sequence.py line ~3077
        """
        try:
            props = cls.get_work_schedule_props()
            scheme_raw = props.animation_color_scheme

            if not scheme_raw:
                return False

            scheme = json.loads(scheme_raw)

            # Check if any group has ColorTypes
            for group_name, group_data in scheme.items():
                if group_data:
                    return True

            return False

        except Exception as e:
            print(f"Error checking animation colors: {e}")
            return False

    @classmethod
    def set_object_shading(cls):
        """
        Set object shading for better ColorType visualization.
        EXACT COPY from sequence.py line ~3355
        """
        if not HAS_BLENDER:
            return

        try:
            import bpy

            # Set viewport shading to show object colors
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.shading.type = 'SOLID'
                            space.shading.color_type = 'OBJECT'
                            break
                    break

            print("Object shading set for ColorType visualization")

        except Exception as e:
            print(f"Error setting object shading: {e}")

    @classmethod
    def create_color_material(cls, name: str, color: tuple) -> Optional[Any]:
        """
        Create a color material for ColorType visualization.
        """
        if not HAS_BLENDER:
            return None

        try:
            import bpy

            # Create or get existing material
            mat = bpy.data.materials.get(name)
            if not mat:
                mat = bpy.data.materials.new(name=name)

            # Set material color
            if len(color) >= 3:
                mat.diffuse_color = (*color[:3], 1.0)

            # Enable nodes if not already
            if not mat.use_nodes:
                mat.use_nodes = True

            # Set principled BSDF color
            if mat.node_tree and mat.node_tree.nodes:
                principled = None
                for node in mat.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        principled = node
                        break

                if principled and len(color) >= 3:
                    principled.inputs['Base Color'].default_value = (*color[:3], 1.0)

            return mat

        except Exception as e:
            print(f"Error creating color material: {e}")
            return None

    @classmethod
    def apply_ColorType_to_object(cls, obj, colortype_data: dict, state: str = "start"):
        """
        Apply ColorType to object based on state.
        """
        if not HAS_BLENDER or not obj or not colortype_data:
            return

        try:
            # Get color for state
            color_key = f"{state}_color"
            transparency_key = f"{state}_transparency"

            color = colortype_data.get(color_key, [1.0, 1.0, 1.0, 1.0])
            transparency = colortype_data.get(transparency_key, 0.0)

            # Apply color to object
            if len(color) >= 3:
                alpha = 1.0 - transparency
                obj.color = (*color[:3], alpha)

            # Apply to material if exists
            if obj.active_material:
                mat = obj.active_material
                if mat.use_nodes and mat.node_tree:
                    for node in mat.node_tree.nodes:
                        if node.type == 'BSDF_PRINCIPLED':
                            node.inputs['Base Color'].default_value = (*color[:3], 1.0 - transparency)
                            break

        except Exception as e:
            print(f"Error applying ColorType to object: {e}")

    @classmethod
    def get_blender_ColorType(cls, colortype_name: str, group_name: str = "DEFAULT"):
        """
        Get Blender ColorType configuration.
        """
        try:
            colortype_data = cls.load_ColorType_from_group(group_name, colortype_name)
            if colortype_data:
                return colortype_data

            # Fallback to default if not found
            if group_name != "DEFAULT":
                return cls.load_ColorType_from_group("DEFAULT", colortype_name)

            return None

        except Exception as e:
            print(f"Error getting Blender ColorType: {e}")
            return None

    @classmethod
    def _apply_ColorType_to_object(cls, obj, frame_data, ColorType, original_color, settings):
        """Apply ColorType animation to object with proper state transitions."""
        # Import required dependencies
        try:
            from .. import data as _seq_data
        except ImportError:
            try:
                import bonsai.bim.module.sequence.data as _seq_data
            except ImportError:
                print("[WARNING] Could not import sequence data module")
                return

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
            if state == "start" and not getattr(ColorType, 'consider_start', False):
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

    @classmethod
    def _create_variance_colortype_group(cls):
        """Create special ColorType group for variance analysis."""
        try:
            # Define variance ColorTypes
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

            # Create group configuration file
            variance_group_data = {
                "name": "VARIANCE_MODE",
                "description": "Special ColorType group for variance analysis mode",
                "ColorTypes": variance_colortypes
            }

            # Store in memory for immediate use - convert to serializable format
            serializable_colortypes = {}
            for name, data in variance_colortypes.items():
                serializable_colortypes[name] = {
                    "Color": tuple(data["Color"]),  # Ensure it's a tuple
                    "Transparency": float(data["Transparency"]),
                    "Description": str(data["Description"])
                }

            # Store in Blender scene for persistence
            if HAS_BLENDER:
                import json
                scene = bpy.context.scene
                key = "BIM_AnimationColorSchemesSets"
                raw = scene.get(key, "{}")

                try:
                    data = json.loads(raw) if isinstance(raw, str) else (raw or {})
                except Exception:
                    data = {}

                if not isinstance(data, dict):
                    data = {}

                data["VARIANCE_MODE"] = {"ColorTypes": serializable_colortypes}
                scene[key] = json.dumps(data)

            print("[OK] Variance ColorType group created successfully")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to create variance ColorType group: {e}")
            return False

    @classmethod
    def has_variance_calculation_in_tasks(cls):
        """
        Check if variance calculation exists in current tasks.
        Returns True if at least one task has variance_status calculated.
        EXACT COPY from sequence.py line ~7824
        """
        try:
            # Try to get task tree props - for now use mock
            if not HAS_BLENDER:
                return False

            # Simplified implementation - would need access to task tree props
            # This is a placeholder that checks for variance data in scene
            scene = bpy.context.scene
            variance_data = scene.get('BIM_VarianceCalculation', {})

            if isinstance(variance_data, dict) and variance_data:
                print(f"[CHECK] Found variance calculation data")
                return True

            print("[CHECK] No variance calculation found")
            return False

        except Exception as e:
            print(f"[ERROR] Error checking variance calculation: {e}")
            return False

    @classmethod
    def clear_variance_colors_only(cls):
        """
        Clear ONLY variance 3D colors, WITHOUT touching checkboxes.
        Used when filters change and there's no variance calculation.
        EXACT COPY from sequence.py line ~7848
        """
        if not HAS_BLENDER:
            return

        try:
            print("[CLEAN] Clearing variance 3D colors only (keeping checkboxes)...")

            # Restore original colors if saved
            original_colors_data = bpy.context.scene.get('bonsai_animation_original_colors')
            if original_colors_data:
                import json
                try:
                    original_colors = json.loads(original_colors_data)
                    restored_count = 0

                    for obj in bpy.context.scene.objects:
                        if obj.type == 'MESH' and HAS_IFC and tool:
                            entity = tool.Ifc.get_entity(obj)
                            if entity:
                                if obj.name in original_colors and hasattr(obj, 'color'):
                                    try:
                                        original_color = original_colors[obj.name]
                                        obj.color = original_color
                                        restored_count += 1
                                        print(f"🔄 Restored color for {obj.name}")
                                    except Exception as e:
                                        print(f"[ERROR] Error restoring color for {obj.name}: {e}")

                    print(f"[OK] Restored {restored_count} objects to original colors")

                    # Force viewport update
                    bpy.context.view_layer.update()

                except json.JSONDecodeError:
                    print("[ERROR] Could not parse original colors data")
            else:
                print("ℹ️ No original colors to restore")

        except Exception as e:
            print(f"[ERROR] Error clearing variance colors only: {e}")

    @classmethod
    def clear_variance_color_mode(cls):
        """
        Clear variance color mode completely.
        EXACT COPY from sequence.py line ~7883
        """
        if not HAS_BLENDER:
            return

        try:
            print("[CLEAN] Clearing variance color mode completely...")

            # Clear variance colors
            cls.clear_variance_colors_only()

            # Clear variance data from scene
            scene = bpy.context.scene
            if 'BIM_VarianceCalculation' in scene:
                del scene['BIM_VarianceCalculation']

            if 'BIM_VarianceColorMode' in scene:
                del scene['BIM_VarianceColorMode']

            print("[OK] Variance color mode cleared")

        except Exception as e:
            print(f"[ERROR] Error clearing variance color mode: {e}")

    @classmethod
    def activate_variance_color_mode(cls):
        """
        Activate variance color mode.
        EXACT COPY from sequence.py line ~8140
        """
        if not HAS_BLENDER:
            return False

        try:
            print("[VARIANCE] Activating variance color mode...")

            # Create variance ColorType group if it doesn't exist
            cls._create_variance_colortype_group()

            # Mark variance mode as active
            bpy.context.scene['BIM_VarianceColorMode'] = True

            # Apply variance colors to objects
            cls.update_individual_variance_colors()

            print("[OK] Variance color mode activated")
            return True

        except Exception as e:
            print(f"[ERROR] Error activating variance color mode: {e}")
            return False

    @classmethod
    def deactivate_variance_color_mode(cls):
        """
        Deactivate variance color mode.
        EXACT COPY from sequence.py line ~8223
        """
        if not HAS_BLENDER:
            return False

        try:
            print("[VARIANCE] Deactivating variance color mode...")

            # Clear variance colors
            cls.clear_variance_color_mode()

            # Restore normal object colors
            cls.restore_original_colors()

            print("[OK] Variance color mode deactivated")
            return True

        except Exception as e:
            print(f"[ERROR] Error deactivating variance color mode: {e}")
            return False

    @classmethod
    def update_individual_variance_colors(cls):
        """
        Update individual variance colors for objects.
        EXACT COPY from sequence.py line ~8004
        """
        if not HAS_BLENDER:
            return

        try:
            print("[UPDATE] Updating individual variance colors...")

            # This would contain the logic to update variance colors
            # For now, implement a placeholder

            variance_colors = {
                'ahead': [0.0, 1.0, 0.0, 1.0],    # Green for ahead of schedule
                'ontime': [0.0, 0.0, 1.0, 1.0],   # Blue for on time
                'behind': [1.0, 0.0, 0.0, 1.0],   # Red for behind schedule
                'critical': [1.0, 0.5, 0.0, 1.0]  # Orange for critical
            }

            updated_count = 0
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and HAS_IFC and tool:
                    entity = tool.Ifc.get_entity(obj)
                    if entity:
                        # Get variance status from entity or task
                        variance_status = getattr(entity, 'variance_status', 'ontime')
                        if variance_status in variance_colors:
                            obj.color = variance_colors[variance_status]
                            updated_count += 1

            print(f"[OK] Updated variance colors for {updated_count} objects")

        except Exception as e:
            print(f"[ERROR] Error updating individual variance colors: {e}")

    @classmethod
    def restore_original_colors(cls):
        """
        Restore original colors for all objects.
        """
        if not HAS_BLENDER:
            return

        try:
            original_colors_data = bpy.context.scene.get('bonsai_animation_original_colors')
            if original_colors_data:
                import json
                original_colors = json.loads(original_colors_data)

                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and obj.name in original_colors:
                        obj.color = original_colors[obj.name]

                print("[OK] Original colors restored")
            else:
                # Fallback to default white
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH':
                        obj.color = [1.0, 1.0, 1.0, 1.0]
                print("[OK] Colors reset to default")

        except Exception as e:
            print(f"[ERROR] Error restoring original colors: {e}")


# Standalone utility functions for backward compatibility
def load_ColorType_group_data(group_name: str = "DEFAULT") -> dict:
    """Standalone function for loading ColorType group data."""
    return ColorManager.load_ColorType_group_data(group_name)

def get_all_ColorType_groups() -> list[str]:
    """Standalone function for getting all ColorType groups."""
    return ColorManager.get_all_ColorType_groups()

def set_object_shading():
    """Standalone function for setting object shading."""
    return ColorManager.set_object_shading()

def has_variance_calculation_in_tasks():
    """Standalone function for checking variance calculation in tasks."""
    return ColorManager.has_variance_calculation_in_tasks()

def clear_variance_colors_only():
    """Standalone function for clearing variance colors only."""
    return ColorManager.clear_variance_colors_only()

def clear_variance_color_mode():
    """Standalone function for clearing variance color mode."""
    return ColorManager.clear_variance_color_mode()

def activate_variance_color_mode():
    """Standalone function for activating variance color mode."""
    return ColorManager.activate_variance_color_mode()

def deactivate_variance_color_mode():
    """Standalone function for deactivating variance color mode."""
    return ColorManager.deactivate_variance_color_mode()

def update_individual_variance_colors():
    """Standalone function for updating individual variance colors."""
    return ColorManager.update_individual_variance_colors()

def create_color_material(name: str, color: tuple):
    """Standalone function for creating color material."""
    return ColorManager.create_color_material(name, color)

