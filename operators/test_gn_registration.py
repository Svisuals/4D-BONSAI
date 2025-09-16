# Test GN System Registration
# Simple test operator to verify GN system is registering correctly

import bpy

class BONSAI_OT_test_gn_registration(bpy.types.Operator):
    """Test GN System Registration"""
    bl_idname = "bonsai.test_gn_registration"
    bl_label = "Test GN Registration"
    bl_description = "Simple test to verify GN system is loaded"
    bl_options = {'REGISTER'}

    def execute(self, context):
        print("🎯 GN REGISTRATION TEST SUCCESSFUL!")

        # Test basic imports
        try:
            from bonsai.bim.module.sequence.tool import gn_system
            print("✅ gn_system import: OK")
        except Exception as e:
            print(f"❌ gn_system import: {e}")

        try:
            from bonsai.bim.module.sequence.tool import gn_integration
            print("✅ gn_integration import: OK")
        except Exception as e:
            print(f"❌ gn_integration import: {e}")

        try:
            from bonsai.bim.module.sequence.tool import gn_sequence_core
            print("✅ gn_sequence_core import: OK")
        except Exception as e:
            print(f"❌ gn_sequence_core import: {e}")

        # Test tool availability
        try:
            import bonsai.tool as tool
            print("✅ bonsai.tool import: OK")

            anim_props = tool.Sequence.get_animation_props()
            print(f"✅ Animation properties: {type(anim_props)}")

            if hasattr(anim_props, 'gn_object_references'):
                print(f"✅ gn_object_references: {len(anim_props.gn_object_references)} objects")
            else:
                print("❌ gn_object_references: NOT FOUND")

        except Exception as e:
            print(f"❌ bonsai.tool test: {e}")

        self.report({'INFO'}, "GN Registration test completed - check console")
        return {'FINISHED'}


# Simple registration for this test operator
def register():
    bpy.utils.register_class(BONSAI_OT_test_gn_registration)

def unregister():
    bpy.utils.unregister_class(BONSAI_OT_test_gn_registration)

if __name__ == "__main__":
    register()