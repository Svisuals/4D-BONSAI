# EN: ui/panels_animation_new.py
import bpy
from bpy.types import Panel
import bonsai.tool as tool

class BIM_PT_sequence_animation(Panel):
    bl_idname = "BIM_PT_sequence_animation"
    bl_label = "4D Animation"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_tab_sequence"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 3

    @classmethod
    def poll(cls, context):
        file = tool.Ifc.get()
        return file and hasattr(file, "schema") and file.schema != "IFC2X3"

    def draw(self, context):
        layout = self.layout
        props = tool.Sequence.get_animation_props()

        # Engine Selector
        engine_box = layout.box()
        engine_box.label(text="Animation Engine", icon='SETTINGS')
        engine_box.prop(props, "animation_engine", expand=True)

        # Geometry Nodes specific controls
        if props.animation_engine == 'GEOMETRY_NODES':
            gn_box = layout.box()
            gn_box.label(text="Real-time View Controllers", icon='GP_SELECT_POINTS')
            gn_box.operator("bim.add_gn_view_controller", icon='ADD', text="Add View Controller")

            # Show controller count if any exist
            try:
                controllers = [obj for obj in context.scene.objects
                             if hasattr(obj, "BonsaiGNController")]
                if controllers:
                    gn_box.label(text=f"{len(controllers)} controller(s) active")
                else:
                    gn_box.label(text="No controllers yet", icon='INFO')
            except:
                pass

        # Main Animation Button (works for both engines)
        main_box = layout.box()
        main_box.label(text="Animation Control", icon="OUTLINER_OB_CAMERA")

        if props.animation_engine == 'KEYFRAME':
            main_box.operator("bim.create_update_4d_animation",
                            text="Create / Update Animation (Legacy)",
                            icon="OUTLINER_OB_CAMERA")
        else:
            main_box.operator("bim.create_update_4d_animation",
                            text="Create / Update Animation (Real-time)",
                            icon="GEOMETRY_NODES")

        # Reset button
        main_box.operator("bim.clear_previous_animation", text="Reset Animation", icon="TRASH")

        # Live Color Updates toggle (for both engines)
        layout.separator()
        layout.prop(props, "enable_live_color_updates",
                   text="Live Color Updates",
                   icon="MODIFIER_ON" if props.enable_live_color_updates else "MODIFIER_OFF")


class BIM_PT_gn_controller_settings(Panel):
    bl_label = "Controller Settings"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_sequence_animation"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        try:
            props = tool.Sequence.get_animation_props()
            return (props.animation_engine == 'GEOMETRY_NODES' and
                    context.active_object and
                    hasattr(context.active_object, "BonsaiGNController"))
        except:
            return False

    def draw(self, context):
        layout = self.layout
        controller_props = context.active_object.BonsaiGNController

        box = layout.box()
        row = box.row()
        row.label(text=f"Active Controller: {context.active_object.name}", icon='OBJECT_DATA')

        # Controller properties
        box.prop(controller_props, "schedule_type_to_display")
        box.prop(controller_props, "colortype_group_to_display")

        # Info about controller
        info_box = layout.box()
        info_box.label(text="Controller Info", icon='INFO')
        info_box.label(text="• This controller defines what is visible in its viewport")
        info_box.label(text="• Multiple controllers allow different views simultaneously")


class BIM_PT_appearance_profiles(Panel):
    bl_label = "Animation Color Profiles"
    bl_idname = "BIM_PT_appearance_profiles"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_parent_id = "BIM_PT_tab_sequence"
    bl_order = 4

    @classmethod
    def poll(cls, context):
        file = tool.Ifc.get()
        return file and hasattr(file, "schema") and file.schema != "IFC2X3"

    def draw(self, context):
        layout = self.layout
        props = tool.Sequence.get_animation_props()

        # Show current engine for context
        engine_info = layout.row()
        engine_info.label(text=f"Engine: {props.animation_engine}", icon='INFO')

        row = layout.row()
        row.template_list(
            "UI_UL_list", "animation_color_schemes_list",
            props, "ColorTypes",
            props, "active_ColorType_index"
        )

        col = row.column(align=True)
        col.operator("bim.add_animation_color_schemes", icon='ADD', text="")
        col.operator("bim.remove_animation_color_schemes", icon='REMOVE', text="")
        col.separator()
        col.operator("bim.load_animation_color_schemes_set_internal", icon='FILE_TICK', text="")

        if props.ColorTypes and props.active_ColorType_index < len(props.ColorTypes):
            p = props.ColorTypes[props.active_ColorType_index]

            # Profile management box
            box = layout.box()
            row = box.row(align=True)
            row.operator("bim.save_animation_color_schemes_set_internal", icon='ADD', text="Save Set")
            row.operator("bim.update_active_colortype_group", icon='FILE_REFRESH', text="Update")
            row.operator("bim.cleanup_task_colortype_mappings", icon='BRUSH_DATA', text="Clean")
            row.operator("bim.remove_animation_color_schemes_set_internal", icon='TRASH', text="Remove")

            # Profile name
            box = layout.box()
            box.prop(p, "name")

            # NEW: GN Appearance Effect (only show for Geometry Nodes engine)
            if props.animation_engine == 'GEOMETRY_NODES':
                gn_box = layout.box()
                gn_box.label(text="Geometry Nodes Effect", icon='GEOMETRY_NODES')
                gn_box.prop(p, "gn_appearance_effect", expand=True)

                if p.gn_appearance_effect == 'GROWTH':
                    info_row = gn_box.row()
                    info_row.label(text="Objects will 'grow' during task execution", icon='INFO')
                else:
                    info_row = gn_box.row()
                    info_row.label(text="Objects appear instantly at task start", icon='INFO')

            # States to consider
            row = layout.row(align=True)
            row.label(text="States to consider:")
            row.prop(p, "consider_start", text="Start", toggle=True)
            row.prop(p, "consider_active", text="Active", toggle=True)
            row.prop(p, "consider_end", text="End", toggle=True)

            if p.consider_start:
                info_box = layout.box()
                info_box.label(text="ℹ️ Start Mode: Elements maintain start appearance", icon='INFO')
                info_box.label(text="throughout entire animation, ignoring task dates.")

            # Start Appearance
            start_box = layout.box()
            header = start_box.row(align=True)
            header.label(text="Start Appearance", icon='PLAY')
            col = start_box.column()
            col.enabled = bool(getattr(p, "consider_start", True))

            row = col.row(align=True)
            row.prop(p, "use_start_original_color")

            if not p.use_start_original_color:
                color_row = col.row(align=True)
                color_row.label(text="Start Color:")
                color_row.prop(p, "start_color", text="")

            col.prop(p, "start_transparency")

            # Active Appearance
            active_box = layout.box()
            header = active_box.row(align=True)
            header.label(text="Active Appearance", icon='SEQUENCE')
            col = active_box.column()
            col.enabled = bool(getattr(p, "consider_active", True))

            row = col.row(align=True)
            row.prop(p, "use_active_original_color")

            if not p.use_active_original_color:
                color_row = col.row(align=True)
                if hasattr(p, "in_progress_color"):
                    color_row.label(text="In Progress Color:")
                    color_row.prop(p, "in_progress_color", text="")
                elif hasattr(p, "active_color"):
                    color_row.label(text="Active Color:")
                    color_row.prop(p, "active_color", text="")

            col.prop(p, "active_start_transparency")
            col.prop(p, "active_finish_transparency")
            col.prop(p, "active_transparency_interpol")

            # End Appearance
            end_box = layout.box()
            header = end_box.row(align=True)
            header.label(text="End Appearance", icon='FF')
            col = end_box.column()
            col.enabled = bool(getattr(p, "consider_end", True))

            col.prop(p, "hide_at_end")

            row_original = col.row(align=True)
            row_original.enabled = not p.hide_at_end
            row_original.prop(p, "use_end_original_color")

            if not p.use_end_original_color:
                row_color = col.row(align=True)
                row_color.enabled = not p.hide_at_end
                row_color.prop(p, "end_color")

            row_transparency = col.row(align=True)
            row_transparency.enabled = not p.hide_at_end
            row_transparency.prop(p, "end_transparency")