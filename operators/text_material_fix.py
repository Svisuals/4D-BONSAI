import bpy
import bonsai.tool as tool

class EnsureTextMaterials(bpy.types.Operator):
    bl_idname = "bim.ensure_text_materials"
    bl_label = "Fix 3D Text Colors"
    bl_description = "Ensure all 3D schedule texts have materials for color control"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            print("🎨 Fixing 3D text materials for color control...")

            # Get the Schedule_Display_Texts collection
            collection = bpy.data.collections.get("Schedule_Display_Texts")
            if not collection or not collection.objects:
                self.report({'WARNING'}, "No 3D schedule texts found")
                return {'CANCELLED'}

            fixed_count = 0

            for text_obj in collection.objects:
                if text_obj.type != 'FONT':
                    continue

                text_curve = text_obj.data

                # Check if it already has a material
                if text_curve.materials and len(text_curve.materials) > 0:
                    # Verify the material has nodes properly configured
                    mat = text_curve.materials[0]
                    if mat.use_nodes and mat.node_tree:
                        bsdf = mat.node_tree.nodes.get("Principled BSDF")
                        if bsdf:
                            print(f"✅ Text '{text_obj.name}' already has proper material")
                            continue

                # Create or fix material
                mat_name = f"Material_{text_obj.name}"
                mat = bpy.data.materials.get(mat_name)

                if not mat:
                    mat = bpy.data.materials.new(name=mat_name)

                mat.use_nodes = True

                # Configure material nodes
                if mat.node_tree:
                    # Clear existing nodes
                    mat.node_tree.nodes.clear()

                    # Create Principled BSDF node
                    bsdf = mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
                    bsdf.location = (0, 0)

                    # Create Output node
                    output = mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
                    output.location = (300, 0)

                    # Connect nodes
                    mat.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

                    # Set default color (white)
                    bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
                    bsdf.inputs["Metallic"].default_value = 0.0
                    bsdf.inputs["Roughness"].default_value = 0.5

                # Assign material to text
                if text_curve.materials:
                    text_curve.materials[0] = mat
                else:
                    text_curve.materials.append(mat)

                fixed_count += 1
                print(f"🎨 Fixed material for text: {text_obj.name}")

            if fixed_count > 0:
                self.report({'INFO'}, f"Fixed materials for {fixed_count} 3D texts")
            else:
                self.report({'INFO'}, "All 3D texts already have proper materials")

            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to fix text materials: {e}")
            print(f"❌ Error in EnsureTextMaterials: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(EnsureTextMaterials)

def unregister():
    bpy.utils.unregister_class(EnsureTextMaterials)

if __name__ == "__main__":
    register()