# Debug operators for Geometry Nodes 4D Animation System
# This file provides debugging tools for the GN system

import bpy
from typing import Optional

try:
    from ..tool import gn_system
except ImportError:
    gn_system = None

class BIM_OT_DebugGNSystem(bpy.types.Operator):
    """Debug operator to print GN system status"""
    bl_idname = "bim.debug_gn_system"
    bl_label = "Debug GN System"
    bl_description = "Print current state of the Geometry Nodes 4D system"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            if gn_system is None:
                self.report({'ERROR'}, "GN system not available")
                return {'CANCELLED'}

            # Get system status
            gn_system.debug_gn_system()

            self.report({'INFO'}, "Debug info printed to console")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Debug failed: {e}")
            return {'CANCELLED'}

class BIM_OT_TestGNSystem(bpy.types.Operator):
    """Test operator to verify GN system functionality"""
    bl_idname = "bim.test_gn_system"
    bl_label = "Test GN System"
    bl_description = "Run tests on the Geometry Nodes 4D system"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            if gn_system is None:
                self.report({'ERROR'}, "GN system not available")
                return {'CANCELLED'}

            success = gn_system.test_gn_system()

            if success:
                self.report({'INFO'}, "GN system test passed")
            else:
                self.report({'WARNING'}, "GN system test failed")

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Test failed: {e}")
            return {'CANCELLED'}

class BIM_OT_PrintObjectAttributes(bpy.types.Operator):
    """Print baked attributes for selected object"""
    bl_idname = "bim.print_object_attributes"
    bl_label = "Print Object GN Attributes"
    bl_description = "Print all baked attributes for the selected object"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            if not context.active_object:
                self.report({'WARNING'}, "No active object selected")
                return {'CANCELLED'}

            obj = context.active_object
            if obj.type != 'MESH':
                self.report({'WARNING'}, "Active object is not a mesh")
                return {'CANCELLED'}

            print("=" * 50)
            print(f"GN ATTRIBUTES FOR OBJECT: {obj.name}")
            print("=" * 50)

            # Check for attributes
            if obj.data.attributes:
                for attr in obj.data.attributes:
                    print(f"Attribute: {attr.name} (Type: {attr.data_type}, Domain: {attr.domain})")

                    # Print some sample values
                    if len(attr.data) > 0:
                        if attr.data_type == 'FLOAT':
                            values = [attr.data[i].value for i in range(min(5, len(attr.data)))]
                            print(f"  Sample values: {values}")
                        elif attr.data_type == 'INT':
                            values = [attr.data[i].value for i in range(min(5, len(attr.data)))]
                            print(f"  Sample values: {values}")
                        elif attr.data_type == 'BOOLEAN':
                            values = [attr.data[i].value for i in range(min(5, len(attr.data)))]
                            print(f"  Sample values: {values}")
            else:
                print("No attributes found on this object")

            print("=" * 50)

            self.report({'INFO'}, f"Attributes printed for {obj.name}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Print attributes failed: {e}")
            return {'CANCELLED'}

class BIM_OT_PrintNodeTree(bpy.types.Operator):
    """Print the structure of the GN node tree"""
    bl_idname = "bim.print_gn_nodetree"
    bl_label = "Print GN Node Tree"
    bl_description = "Print the structure of the Bonsai 4D node tree"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            from ..tool.gn_sequence import GN_NODETREE_NAME

            node_tree = bpy.data.node_groups.get(GN_NODETREE_NAME)
            if not node_tree:
                self.report({'WARNING'}, f"Node tree '{GN_NODETREE_NAME}' not found")
                return {'CANCELLED'}

            print("=" * 60)
            print(f"GN NODE TREE STRUCTURE: {GN_NODETREE_NAME}")
            print("=" * 60)

            print(f"Total nodes: {len(node_tree.nodes)}")
            print("\nNodes:")
            for node in node_tree.nodes:
                print(f"  - {node.name} ({node.type})")
                if hasattr(node, 'node_tree') and node.node_tree:
                    print(f"    Linked to: {node.node_tree.name}")

            print(f"\nTotal links: {len(node_tree.links)}")
            print("\nConnections:")
            for link in node_tree.links:
                from_node = link.from_node.name
                from_socket = link.from_socket.name
                to_node = link.to_node.name
                to_socket = link.to_socket.name
                print(f"  {from_node}.{from_socket} -> {to_node}.{to_socket}")

            print("=" * 60)

            self.report({'INFO'}, f"Node tree structure printed")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Print node tree failed: {e}")
            return {'CANCELLED'}

# Operator registration
classes = (
    BIM_OT_DebugGNSystem,
    BIM_OT_TestGNSystem,
    BIM_OT_PrintObjectAttributes,
    BIM_OT_PrintNodeTree,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)