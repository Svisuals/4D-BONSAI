# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021, 2022 Dion Moult <dion@thinkmoult.com>, Yassine Oualid <yassine@sigmadimensions.com>, Federico Eraso <feraso@svisuals.net
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

# Import required helper functions
from .animation_operators import _clear_previous_animation, _restore_3d_texts_state


class ClearPreviousAnimation(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.clear_previous_animation"
    bl_label = "Reset Animation"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        # VALIDATION: Only execute if there is an active animation
        try:
            anim_props = tool.Sequence.get_animation_props()
            is_animation_active = getattr(anim_props, 'is_animation_created', False)
            if not is_animation_active:
                self.report({'WARNING'}, "No active animation to reset")
                return {'CANCELLED'}
        except Exception as e:
            print(f"Could not check animation status: {e}")
            self.report({'ERROR'}, "Could not check animation status")
            return {'CANCELLED'}

        # Stop the animation if it is playing
        try:
            if bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel(restore_frame=False)
        except Exception as e:
            print(f"Could not stop animation: {e}")

        # Complete cleanup of the previous animation
        try:
            _clear_previous_animation(context)
            
            # Clear the active profile group in HUD Legend
            try:
                anim_props = tool.Sequence.get_animation_props()
                if anim_props and hasattr(anim_props, 'camera_orbit'):
                    camera_props = anim_props.camera_orbit

                    # Get all active profiles to hide them
                    if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                        all_colortype_names = []
                        for group_item in anim_props.animation_group_stack:
                            group_name = group_item.group
                            from .prop import UnifiedColorTypeManager
                            group_colortypes = UnifiedColorTypeManager.get_group_colortypes(bpy.context, group_name)
                            if group_colortypes:
                                all_colortype_names.extend(group_colortypes.keys())
                        
                        # Hide all profiles by putting their names in legend_hud_visible_colortypes
                        if all_colortype_names:
                            hidden_colortypes_str = ','.join(set(all_colortype_names))  # use set() to remove duplicates
                            camera_props.legend_hud_visible_colortypes = hidden_colortypes_str
                            print(f"🧹 Hidden colortypes in HUD Legend: {hidden_colortypes_str}")
                    
                    # Clear selected_colortypes just in case
                    if hasattr(camera_props, 'legend_hud_selected_colortypes'):
                        camera_props.legend_hud_selected_colortypes = set()
                    
                    # Invalidate legend HUD cache
                    from ..hud import invalidate_legend_hud_cache
                    invalidate_legend_hud_cache()
                    print("🧹 Active colortype group cleared from HUD Legend.")
            except Exception as legend_e:
                print(f"⚠️ Could not clear colortype group: {legend_e}")
            
            self.report({'INFO'}, "Previous animation cleared.")
            context.scene.frame_set(context.scene.frame_start)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to clear previous animation: {e}")
            return {"CANCELLED"}

    # This 'execute' method IS NOW INSIDE the class.
    def execute(self, context):
        # Calls its own cleanup logic (_execute).
        return self._execute(context)


class ClearPreviousSnapshot(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.clear_previous_snapshot"
    bl_label = "Reset Snapshot"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        # VALIDATION: Only execute if there is an active snapshot
        try:
            is_snapshot_active = bpy.context.scene.get("is_snapshot_mode", False)
            if not is_snapshot_active:
                self.report({'WARNING'}, "No active snapshot to reset")
                return {'CANCELLED'}
        except Exception as e:
            print(f"Could not check snapshot status: {e}")
            self.report({'ERROR'}, "Could not check snapshot status")
            return {'CANCELLED'}

        print(f"🔄 Reset snapshot started")

        # Stop the animation if it is playing
        try:
            if bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel(restore_frame=False)
                print(f"✅ Animation playback stopped")
        except Exception as e:
            print(f"❌ Could not stop animation: {e}")

        # Complete cleanup of snapshot AND animation
        try:
            # CRITICAL: Reset ALL objects to their original state
            print(f"🔄 Clearing previous animation and snapshot...")
            _clear_previous_animation(context)
            print(f"✅ Previous animation and snapshot cleared")
            
            # Clear temporary snapshot data
            if hasattr(bpy.context.scene, 'snapshot_data'):
                del bpy.context.scene.snapshot_data
            
            # Clear the active profile group in HUD Legend
            try:
                anim_props = tool.Sequence.get_animation_props()
                if anim_props and hasattr(anim_props, 'camera_orbit'):
                    camera_props = anim_props.camera_orbit
                    
                    # Get all active profiles to hide them
                    if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                        all_colortype_names = []
                        for group_item in anim_props.animation_group_stack:
                            group_name = group_item.group
                            from .prop import UnifiedColorTypeManager
                            group_colortypes = UnifiedColorTypeManager.get_group_colortypes(bpy.context, group_name)
                            if group_colortypes:
                                all_colortype_names.extend(group_colortypes.keys())
                        
                        # Hide all profiles by putting their names in legend_hud_visible_colortypes
                        if all_colortype_names:
                            hidden_colortypes_str = ','.join(set(all_colortype_names))  # use set() to remove duplicates
                            camera_props.legend_hud_visible_colortypes = hidden_colortypes_str
                            print(f"🧹 Hidden colortypes in HUD Legend: {hidden_colortypes_str}")
                    
                    # Clear selected_colortypes just in case
                    if hasattr(camera_props, 'legend_hud_selected_colortypes'):
                        camera_props.legend_hud_selected_colortypes = set()
                    
                    # Invalidate legend HUD cache
                    from ..hud import invalidate_legend_hud_cache
                    invalidate_legend_hud_cache()
                    print("🧹 Active colortype group cleared from HUD Legend")
            except Exception as legend_e:
                print(f"⚠️ Could not clear colortype group: {legend_e}")
            
            # --- SNAPSHOT 3D TEXTS RESTORATION ---
            # Clear snapshot mode and restore previous state
            if "is_snapshot_mode" in context.scene:
                del context.scene["is_snapshot_mode"]
                print("📸 Snapshot mode deactivated for 3D texts")
            _restore_3d_texts_state()
            
            self.report({'INFO'}, "Snapshot reset completed")
        except Exception as e:
            print(f"Error during snapshot reset: {e}")
            self.report({'WARNING'}, f"Snapshot reset completed with warnings: {e}")
        
        return {'FINISHED'}
    
    # This 'execute' method IS NOW INSIDE the class.
    def execute(self, context):
        # Calls its own cleanup logic (_execute).
        return self._execute(context)