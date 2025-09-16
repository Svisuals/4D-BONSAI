# Debug and User Operators for Geometry Nodes 4D Animation System
# Provides essential operators for applying, cleaning, and debugging the GN system

import bpy
from typing import Optional

try:
    import bonsai.tool as tool
    from bonsai.tool import gn_system
    from bonsai.tool import gn_integration
except ImportError:
    tool = None
    gn_system = None
    gn_integration = None


class BONSAI_OT_apply_gn_data_to_selection(bpy.types.Operator):
    """Apply Geometry Nodes 4D data to selected objects"""
    bl_idname = "bonsai.apply_gn_data_to_selection"
    bl_label = "Apply GN Data to Selection"
    bl_description = "Apply Geometry Nodes animation data to selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not gn_system:
            self.report({'ERROR'}, "GN system not available")
            return {'CANCELLED'}

        if not tool:
            self.report({'ERROR'}, "Bonsai tool not available")
            return {'CANCELLED'}

        # Get selected objects
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'WARNING'}, "No mesh objects selected")
            return {'CANCELLED'}

        print(f"🎯 Applying GN data to {len(selected_objects)} selected objects...")

        try:
            # Get active work schedule and its tasks
            work_schedule = tool.Sequence.get_active_work_schedule()
            if not work_schedule:
                self.report({'ERROR'}, "No active work schedule found")
                return {'CANCELLED'}

            tasks = tool.Sequence.get_work_schedule_tasks(work_schedule)
            if not tasks:
                self.report({'ERROR'}, "No tasks found in work schedule")
                return {'CANCELLED'}

            # Process each selected object
            objects_processed = 0
            for obj in selected_objects:
                # Add to GN management system
                if gn_system.add_object_to_gn_references(obj):
                    # Find and apply task data
                    task_found = False

                    # Try to find a task for this object
                    try:
                        element = tool.Ifc.get_entity(obj)
                        if element:
                            for task in tasks:
                                task_products = tool.Sequence.get_task_related_products(task)
                                if element in task_products:
                                    if gn_system.update_task_attributes_on_object(obj, task):
                                        objects_processed += 1
                                        task_found = True
                                        break
                    except Exception:
                        pass

                    # If no specific task found, apply to first available task
                    if not task_found and tasks:
                        if gn_system.update_task_attributes_on_object(obj, tasks[0]):
                            objects_processed += 1

                    # Add GN modifier if it doesn't exist
                    has_gn_modifier = any(mod.name == gn_system.GN_MODIFIER_NAME
                                        for mod in obj.modifiers if mod.type == 'NODES')

                    if not has_gn_modifier:
                        # Add GN modifier (would need node group)
                        print(f"⚠️ GN modifier not found on {obj.name} - would need to add node group")

            self.report({'INFO'}, f"Applied GN data to {objects_processed}/{len(selected_objects)} objects")
            print(f"✅ GN data application complete: {objects_processed} objects processed")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to apply GN data: {e}")
            print(f"❌ Error applying GN data: {e}")
            return {'CANCELLED'}


class BONSAI_OT_clean_gn_data_from_selection(bpy.types.Operator):
    """Clean Geometry Nodes 4D data from selected objects"""
    bl_idname = "bonsai.clean_gn_data_from_selection"
    bl_label = "Clean GN Data from Selection"
    bl_description = "Remove Geometry Nodes animation data from selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not gn_system:
            self.report({'ERROR'}, "GN system not available")
            return {'CANCELLED'}

        # Get selected objects
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'WARNING'}, "No mesh objects selected")
            return {'CANCELLED'}

        print(f"🧹 Cleaning GN data from {len(selected_objects)} selected objects...")

        try:
            objects_cleaned = 0
            for obj in selected_objects:
                # Remove GN attributes from mesh
                if gn_system.clean_gn_attributes_from_object(obj):
                    objects_cleaned += 1

                # Remove from GN management
                gn_system.remove_object_from_gn_references(obj)

                # Remove GN modifier
                for mod in obj.modifiers:
                    if mod.name == gn_system.GN_MODIFIER_NAME and mod.type == 'NODES':
                        obj.modifiers.remove(mod)
                        print(f"✅ Removed GN modifier from {obj.name}")
                        break

            self.report({'INFO'}, f"Cleaned GN data from {objects_cleaned} objects")
            print(f"✅ GN data cleaning complete: {objects_cleaned} objects cleaned")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to clean GN data: {e}")
            print(f"❌ Error cleaning GN data: {e}")
            return {'CANCELLED'}


class BONSAI_OT_debug_gn_system(bpy.types.Operator):
    """Debug the Geometry Nodes 4D system"""
    bl_idname = "bonsai.debug_gn_system"
    bl_label = "Debug GN System"
    bl_description = "Print debug information about the Geometry Nodes system"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not gn_system:
            self.report({'ERROR'}, "GN system not available")
            return {'CANCELLED'}

        try:
            print("=" * 60)
            print("GEOMETRY NODES 4D SYSTEM DEBUG")
            print("=" * 60)

            # System availability
            print(f"Tool available: {tool is not None}")
            print(f"GN system available: {gn_system is not None}")
            print(f"GN integration available: {gn_integration is not None}")

            if tool:
                # Work schedule info
                work_schedule = tool.Sequence.get_active_work_schedule()
                print(f"Active work schedule: {work_schedule.Name if work_schedule else 'None'}")

                if work_schedule:
                    tasks = tool.Sequence.get_work_schedule_tasks(work_schedule)
                    print(f"Number of tasks: {len(tasks) if tasks else 0}")

                # Animation properties
                anim_props = tool.Sequence.get_animation_props()
                if anim_props:
                    print(f"Animation engine: {getattr(anim_props, 'animation_engine', 'Not set')}")
                    print(f"Live color updates: {getattr(anim_props, 'enable_live_color_updates', 'Not set')}")

            # Managed objects
            managed_objects = gn_system.get_gn_managed_objects()
            print(f"GN managed objects: {len(managed_objects)}")

            # Objects with GN modifiers in scene
            gn_modifier_count = 0
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    for mod in obj.modifiers:
                        if mod.name == gn_system.GN_MODIFIER_NAME and mod.type == 'NODES':
                            gn_modifier_count += 1
                            break

            print(f"Objects with GN modifiers: {gn_modifier_count}")

            # Selected objects info
            selected_mesh = [obj for obj in context.selected_objects if obj.type == 'MESH']
            print(f"Selected mesh objects: {len(selected_mesh)}")

            print("=" * 60)

            self.report({'INFO'}, "Debug info printed to console")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Debug failed: {e}")
            print(f"❌ Debug error: {e}")
            return {'CANCELLED'}


class BONSAI_OT_update_gn_objects(bpy.types.Operator):
    """Update all Geometry Nodes managed objects"""
    bl_idname = "bonsai.update_gn_objects"
    bl_label = "Update GN Objects"
    bl_description = "Update all objects managed by the Geometry Nodes system"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not gn_system:
            self.report({'ERROR'}, "GN system not available")
            return {'CANCELLED'}

        try:
            updated_count = gn_system.update_all_gn_objects()
            self.report({'INFO'}, f"Updated {updated_count} GN objects")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Update failed: {e}")
            return {'CANCELLED'}


class BONSAI_OT_sync_gn_settings(bpy.types.Operator):
    """Sync GN system with animation settings"""
    bl_idname = "bonsai.sync_gn_settings"
    bl_label = "Sync GN Settings"
    bl_description = "Synchronize GN system with current animation settings"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not gn_integration:
            self.report({'ERROR'}, "GN integration not available")
            return {'CANCELLED'}

        try:
            gn_integration.sync_gn_with_animation_settings_changes(context=context)
            self.report({'INFO'}, "GN system synchronized with animation settings")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Sync failed: {e}")
            return {'CANCELLED'}


class BONSAI_OT_test_node_tree_creation(bpy.types.Operator):
    """Test Node Tree Creation"""
    bl_idname = "bonsai.test_node_tree_creation"
    bl_label = "Test Node Tree Creation"
    bl_description = "Test the complete node tree creation system"
    bl_options = {'REGISTER'}

    def execute(self, context):
        print("=" * 80)
        print("🧪 TESTING NODE TREE CREATION SYSTEM")
        print("=" * 80)

        try:
            # Test imports
            try:
                from bonsai.tool import gn_sequence_core
                print("✅ gn_sequence_core imported successfully")
            except ImportError as e:
                print(f"❌ Failed to import gn_sequence_core: {e}")
                self.report({'ERROR'}, f"Import failed: {e}")
                return {'CANCELLED'}

            # Test node group creation
            print("\n📦 Testing node group creation...")
            try:
                node_group = gn_sequence_core.create_bonsai_4d_node_group()
                if node_group:
                    print(f"✅ Node group created: {node_group.name}")
                    print(f"   Input sockets: {len(node_group.inputs)}")
                    print(f"   Output sockets: {len(node_group.outputs)}")
                    print(f"   Nodes: {len(node_group.nodes)}")
                else:
                    print("❌ Node group creation returned None")
            except Exception as e:
                print(f"❌ Node group creation failed: {e}")
                import traceback
                traceback.print_exc()

            # Test super material creation
            print("\n🎨 Testing super material creation...")
            try:
                super_material = gn_sequence_core.create_super_material_enhanced()
                if super_material:
                    print(f"✅ Super material created: {super_material.name}")
                    print(f"   Nodes: {len(super_material.node_tree.nodes) if super_material.node_tree else 0}")
                else:
                    print("❌ Super material creation returned None")
            except Exception as e:
                print(f"❌ Super material creation failed: {e}")
                import traceback
                traceback.print_exc()

            # List all node groups in scene
            print("\n📋 Current node groups in scene:")
            for i, ng in enumerate(bpy.data.node_groups):
                print(f"   {i+1}. {ng.name} (type: {ng.type})")

            # List all materials in scene
            print("\n🎨 Current materials in scene:")
            for i, mat in enumerate(bpy.data.materials):
                print(f"   {i+1}. {mat.name}")

            # Test complete system
            print("\n🔧 Testing complete system creation...")
            try:
                # Get work schedule and settings
                work_schedule = tool.Sequence.get_active_work_schedule() if tool else None
                settings = tool.Sequence.get_animation_settings() if tool else {}

                if work_schedule and settings:
                    success = gn_sequence_core.create_complete_gn_animation_system_enhanced(context, work_schedule, settings)
                    print(f"✅ Complete system test result: {success}")
                else:
                    print("⚠️ No work schedule or settings - skipping complete system test")
                    print(f"   Work schedule: {work_schedule}")
                    print(f"   Settings: {bool(settings)}")
            except Exception as e:
                print(f"❌ Complete system test failed: {e}")
                import traceback
                traceback.print_exc()

            print("=" * 80)
            self.report({'INFO'}, "Node tree creation test completed - check console")
            return {'FINISHED'}

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Test failed: {e}")
            return {'CANCELLED'}


# Registration
classes = [
    BONSAI_OT_apply_gn_data_to_selection,
    BONSAI_OT_clean_gn_data_from_selection,
    BONSAI_OT_debug_gn_system,
    BONSAI_OT_update_gn_objects,
    BONSAI_OT_sync_gn_settings,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()