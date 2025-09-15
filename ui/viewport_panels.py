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
from bpy.types import Panel
import bonsai.tool as tool


class BIM_PT_4D_Animation_Viewport(Panel):
    bl_label = "4D Animation"
    bl_idname = "BIM_PT_4D_Animation_Viewport"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "4D BIM"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        try:
            layout = self.layout
            anim_props = tool.Sequence.get_animation_props()

            # === ANIMATION ENGINE SELECTOR ===
            engine_box = layout.box()
            engine_box.label(text="Animation Engine:", icon="SETTINGS")
            engine_row = engine_box.row(align=True)
            engine_row.prop(anim_props, "animation_engine", expand=True)

            # === GEOMETRY NODES ENGINE SPECIFIC CONTROLS ===
            if anim_props.animation_engine == 'GEOMETRY_NODES':
                gn_box = layout.box()
                gn_box.label(text="GN Controls:", icon="GEOMETRY_NODES")

                # Controller management
                controller_row = gn_box.row(align=True)
                controller_row.operator("bim.add_gn_view_controller", text="Add Controller", icon="ADD")

                # Show active controllers info
                try:
                    controllers = [obj for obj in context.scene.objects if hasattr(obj, "BonsaiGNController")]
                    if controllers:
                        info_row = gn_box.row()
                        info_row.label(text=f"Controllers: {len(controllers)}", icon="EMPTY_AXIS")

                        # Show controller-specific settings for the active object
                        active_obj = context.active_object
                        if active_obj and hasattr(active_obj, "BonsaiGNController"):
                            ctrl_props = active_obj.BonsaiGNController
                            ctrl_box = gn_box.box()
                            ctrl_box.label(text=f"Active: {active_obj.name}", icon="EMPTY_AXIS")

                            # All settings managed from Animation Settings (like keyframes mode)
                            ctrl_row = ctrl_box.row(align=True)
                            ctrl_row.label(text="Settings from Animation Settings", icon='INFO')
                    else:
                        info_row = gn_box.row()
                        info_row.label(text="Add Controller", icon="INFO")
                except Exception as e:
                    error_row = gn_box.row()
                    error_row.label(text=f"Error: {e}", icon="ERROR")

            # === MAIN ANIMATION ACTIONS ===
            main_box = layout.box()
            main_box.label(text="Actions:", icon="OUTLINER_OB_CAMERA")

            # Main animation button
            main_row = main_box.row()
            main_row.scale_y = 1.5
            op = main_row.operator(
                "bim.create_update_4d_animation",
                text="Create/Update Animation",
                icon="OUTLINER_OB_CAMERA")

            # Reset button
            reset_row = main_box.row()
            reset_row.operator("bim.clear_previous_animation", text="Reset Animation", icon="TRASH")

            # === QUICK SETTINGS ===
            if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                quick_box = layout.box()
                quick_box.label(text="Quick Settings:", icon="SETTINGS")

                # Show active group
                active_group = None
                for group_item in anim_props.animation_group_stack:
                    if getattr(group_item, "enabled", False):
                        active_group = group_item.group
                        break

                group_row = quick_box.row()
                group_row.label(text="Active Group:")
                group_row.label(text=active_group if active_group else "None")

        except Exception as e:
            layout.label(text=f"Error loading 4D Animation: {e}", icon="ERROR")


class BIM_PT_4D_Controllers_Viewport(Panel):
    bl_label = "GN Controllers"
    bl_idname = "BIM_PT_4D_Controllers_Viewport"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "4D BIM"
    bl_parent_id = "BIM_PT_4D_Animation_Viewport"
    bl_order = 2

    @classmethod
    def poll(cls, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            return anim_props.animation_engine == 'GEOMETRY_NODES'
        except:
            return False

    def draw(self, context):
        try:
            layout = self.layout

            # List all controllers
            controllers = [obj for obj in context.scene.objects if hasattr(obj, "BonsaiGNController")]

            if controllers:
                for controller in controllers:
                    ctrl_box = layout.box()
                    header = ctrl_box.row(align=True)

                    # Controller name as a label (clicking won't do anything, but shows the name)
                    header.label(text=controller.name, icon="EMPTY_AXIS")

                    # Visibility toggle
                    visibility_icon = "HIDE_OFF" if not controller.hide_viewport else "HIDE_ON"
                    header.prop(controller, "hide_viewport", text="", icon=visibility_icon, emboss=False)

                    # Show settings if this is the active object
                    if context.active_object == controller:
                        ctrl_props = controller.BonsaiGNController

                        # All settings managed from Animation Settings (like keyframes mode)
                        settings_row = ctrl_box.row()
                        settings_row.label(text="Settings from Animation Settings", icon='INFO')
            else:
                layout.label(text="No Controllers", icon="INFO")
                layout.operator("bim.add_gn_view_controller", text="Add First Controller", icon="ADD")

        except Exception as e:
            layout.label(text=f"Error: {e}", icon="ERROR")