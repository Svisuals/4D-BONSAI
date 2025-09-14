# Debug operators for Geometry Nodes system
import bpy
import bmesh
from bpy.types import Operator


class DebugGNSystem(Operator):
    bl_idname = "bim.debug_gn_system"
    bl_label = "Debug GN System"
    bl_description = "Diagnose Geometry Nodes animation system issues"

    def execute(self, context):
        print("\n" + "="*60)
        print("🔍 GEOMETRY NODES SYSTEM DIAGNOSIS")
        print("="*60)

        # 1. Check for node tree
        node_tree_name = "Bonsai 4D Node Tree"
        if node_tree_name in bpy.data.node_groups:
            node_tree = bpy.data.node_groups[node_tree_name]
            print(f"✅ Node tree '{node_tree_name}' exists with {len(node_tree.nodes)} nodes")
        else:
            print(f"❌ Node tree '{node_tree_name}' NOT FOUND")
            return {'CANCELLED'}

        # 2. Check for controller
        controllers = [obj for obj in bpy.data.objects if obj.get("is_gn_controller", False)]
        if controllers:
            controller = controllers[0]
            print(f"✅ Controller found: {controller.name}")
        else:
            print("❌ No GN controller found")

        # 3. Check objects with GN modifiers
        objects_with_modifiers = []
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod.name == "Bonsai 4D Animation" and mod.type == 'NODES':
                        objects_with_modifiers.append(obj)
                        break

        print(f"🎯 Found {len(objects_with_modifiers)} objects with GN modifiers")

        # 4. Detailed analysis of each object
        for i, obj in enumerate(objects_with_modifiers[:5]):  # Limit to first 5 for readability
            print(f"\n--- OBJECT {i+1}: {obj.name} ---")

            # Check attributes
            if obj.data and hasattr(obj.data, 'attributes'):
                attrs = obj.data.attributes
                schedule_start = attrs.get("schedule_start")
                schedule_end = attrs.get("schedule_end")
                effect_type = attrs.get("effect_type")

                print(f"  Attributes present: {list(attrs.keys())}")

                if schedule_start:
                    # Get actual values from the attribute
                    values = [schedule_start.data[i].value for i in range(min(3, len(schedule_start.data)))]
                    print(f"  schedule_start sample values: {values}")
                else:
                    print("  ❌ schedule_start attribute MISSING")

                if schedule_end:
                    values = [schedule_end.data[i].value for i in range(min(3, len(schedule_end.data)))]
                    print(f"  schedule_end sample values: {values}")
                else:
                    print("  ❌ schedule_end attribute MISSING")

                if effect_type:
                    values = [effect_type.data[i].value for i in range(min(3, len(effect_type.data)))]
                    print(f"  effect_type sample values: {values}")
                else:
                    print("  ❌ effect_type attribute MISSING")
            else:
                print("  ❌ No attributes found on object")

            # Check modifier setup
            modifier = None
            for mod in obj.modifiers:
                if mod.name == "Bonsai 4D Animation" and mod.type == 'NODES':
                    modifier = mod
                    break

            if modifier:
                print(f"  ✅ Modifier found: {modifier.name}")
                print(f"  Node group: {modifier.node_group.name if modifier.node_group else 'NONE'}")

                # Check inputs
                for input_name in ['Current Frame', 'Schedule Type', 'ColorType Group']:
                    if input_name in modifier:
                        value = modifier[input_name]
                        print(f"  Input '{input_name}': {value}")
                    else:
                        print(f"  ❌ Input '{input_name}' MISSING")

                # Check drivers
                if modifier.animation_data and modifier.animation_data.drivers:
                    print(f"  ✅ Has {len(modifier.animation_data.drivers)} drivers")
                    for driver in modifier.animation_data.drivers:
                        print(f"    Driver: {driver.data_path} = {driver.driver.expression}")
                else:
                    print("  ❌ No drivers found")
            else:
                print("  ❌ No GN modifier found")

        # 5. Check current frame effect
        current_frame = context.scene.frame_current
        print(f"\n📅 Current frame: {current_frame}")
        print("Try changing the frame and see if objects change...")

        # 6. Recommendations
        print("\n🔧 RECOMMENDATIONS:")
        if not objects_with_modifiers:
            print("- No objects found with GN modifiers. Run the GN animation creation first.")

        missing_attrs = False
        for obj in objects_with_modifiers[:3]:
            if obj.data and hasattr(obj.data, 'attributes'):
                if "schedule_start" not in obj.data.attributes:
                    missing_attrs = True
                    break

        if missing_attrs:
            print("- Attributes are missing. The baking process may have failed.")
            print("- Check if the async task completed successfully.")

        print("="*60 + "\n")

        return {'FINISHED'}


class ForceRebakeAttributes(Operator):
    bl_idname = "bim.force_rebake_attributes"
    bl_label = "Force Rebake Attributes"
    bl_description = "Force rebaking of 4D attributes on selected objects"

    def execute(self, context):
        if not context.selected_objects:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        print("🔄 Force rebaking attributes...")

        # Simple test values for debugging
        test_schedule_start = 1.0
        test_schedule_end = 100.0
        test_effect_type = 1  # INSTANT

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            print(f"Processing {obj.name}...")

            # Ensure we're in Edit mode to modify attributes
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')

            # Get bmesh representation
            bm = bmesh.from_mesh(obj.data)

            # Create or get attributes
            if "schedule_start" not in bm.faces.layers.float:
                bm.faces.layers.float.new("schedule_start")
            if "schedule_end" not in bm.faces.layers.float:
                bm.faces.layers.float.new("schedule_end")
            if "effect_type" not in bm.faces.layers.int:
                bm.faces.layers.int.new("effect_type")

            schedule_start_layer = bm.faces.layers.float["schedule_start"]
            schedule_end_layer = bm.faces.layers.float["schedule_end"]
            effect_type_layer = bm.faces.layers.int["effect_type"]

            # Assign test values to all faces
            for face in bm.faces:
                face[schedule_start_layer] = test_schedule_start
                face[schedule_end_layer] = test_schedule_end
                face[effect_type_layer] = test_effect_type

            # Update mesh
            bmesh.update_edit_mesh(obj.data)
            bpy.ops.object.mode_set(mode='OBJECT')

            print(f"✅ Test attributes baked to {obj.name}")

        self.report({'INFO'}, f"Rebaked attributes on {len(context.selected_objects)} objects")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(DebugGNSystem)
    bpy.utils.register_class(ForceRebakeAttributes)


def unregister():
    bpy.utils.unregister_class(DebugGNSystem)
    bpy.utils.unregister_class(ForceRebakeAttributes)


if __name__ == "__main__":
    register()