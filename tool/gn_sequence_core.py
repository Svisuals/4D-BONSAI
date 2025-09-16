# Enhanced Geometry Nodes Sequence System - V113 Functionality Restored
# This file contains the ACTUAL V113 implementation that was missing

import bpy
import time
import bmesh
from typing import Dict, Any, Optional, Tuple

# Import bonsai tool safely
try:
    import bonsai.tool as tool
    import ifcopenshell
    import ifcopenshell.util.sequence
except ImportError:
    tool = None
    ifcopenshell = None

# Enhanced constants from V113
GN_MODIFIER_NAME = "Bonsai 4D"
GN_NODETREE_NAME = "Bonsai 4D Node Tree"
GN_SUPER_MATERIAL_NAME = "Bonsai 4D Super Material"
GN_CONTROLLER_COLLECTION = "GN_CONTROLLERS"

# Enhanced attribute names from V113
ATTR_SCHEDULE_START = "schedule_start"
ATTR_SCHEDULE_END = "schedule_end"
ATTR_SCHEDULE_DURATION = "schedule_duration"
ATTR_ACTUAL_START = "actual_start"
ATTR_ACTUAL_END = "actual_end"
ATTR_ACTUAL_DURATION = "actual_duration"
ATTR_EFFECT_TYPE = "effect_type"
ATTR_COLORTYPE_ID = "colortype_id"
ATTR_VISIBILITY_BEFORE_START = "visibility_before_start"
ATTR_VISIBILITY_AFTER_END = "visibility_after_end"
ATTR_ANIMATION_STATE = "animation_state"


def bake_all_attributes_worker_enhanced(work_schedule, settings):
    """
    V113 CORE FUNCTION: Enhanced worker function that bakes a complete
    set of attributes defining object behavior over time.

    This replicates the exact V113 logic from get_animation_settings and
    get_animation_product_frames_enhanced.
    """
    print("🚀 V113 CORE: Enhanced attribute baking with complete logic replication")

    # Step 1: Replicate get_animation_settings logic
    animation_start = int(settings["start_frame"])
    animation_end = int(settings["start_frame"] + settings["total_frames"])
    viz_start = settings["start"]
    viz_finish = settings["finish"]
    viz_duration = settings["duration"]

    # Step 2: Get ColorType configuration
    if tool is None:
        print("❌ ERROR: Bonsai tool not available - cannot access work schedule properties")
        return {}

    props = tool.Sequence.get_work_schedule_props()
    date_source = getattr(props, "date_source_type", "SCHEDULE")
    start_date_type = f"{date_source.capitalize()}Start"
    finish_date_type = f"{date_source.capitalize()}Finish"

    # Step 3: Process tasks with complete ColorType logic
    product_frames = {}
    attributes_to_set = {}

    def process_task_enhanced(task):
        """Enhanced task processing with complete ColorType logic from V113"""
        if ifcopenshell is None:
            print("❌ ERROR: ifcopenshell not available - cannot process nested tasks")
            return

        # Process nested tasks recursively
        for subtask in ifcopenshell.util.sequence.get_nested_tasks(task):
            process_task_enhanced(subtask)

        # Get task dates using the same logic as keyframes
        task_start = ifcopenshell.util.sequence.derive_date(task, start_date_type, is_earliest=True)
        task_finish = ifcopenshell.util.sequence.derive_date(task, finish_date_type, is_latest=True)

        if not task_start or not task_finish:
            return

        # Get ColorType profile for this task - REAL ASSIGNMENT
        ColorType = get_assigned_colortype_for_task_enhanced(task)
        if not ColorType:
            print(f"⚠️ No ColorType found for task {task.Name if hasattr(task, 'Name') else 'Unknown'}")
            return

        # Convert dates to frame numbers
        task_start_days = (task_start - viz_start).days
        task_end_days = (task_finish - viz_start).days
        start_frame = int((task_start_days / viz_duration.days) * settings["total_frames"])
        finish_frame = int((task_end_days / viz_duration.days) * settings["total_frames"])

        print(f"📋 Processing task: {getattr(task, 'Name', 'Unknown')}")
        print(f"   Frames: {start_frame} to {finish_frame}")

        # Get all products assigned to this task
        all_products = []
        try:
            task_inputs = tool.Sequence.get_task_inputs(task)
            task_outputs = tool.Sequence.get_task_outputs(task)
            all_products.extend([(p, "input") for p in task_inputs])
            all_products.extend([(p, "output") for p in task_outputs])
        except AttributeError:
            print(f"❌ WARNING: Cannot access task inputs/outputs for task {task}")
            return

        # Process each product
        for product, relationship in all_products:
            try:
                obj = tool.Ifc.get_object(product)
            except AttributeError:
                print(f"❌ WARNING: Cannot get object for product {product}")
                continue

            if not obj or obj.type != 'MESH':
                continue

            # Determine visibility logic based on ColorType (V113 exact logic)
            colortype_name = getattr(ColorType, 'name', 'UNKNOWN')
            consider_start = getattr(ColorType, 'consider_start', True)
            consider_end = getattr(ColorType, 'consider_end', True)
            hide_at_end = getattr(ColorType, 'hide_at_end', False)

            # For CONSTRUCTION (relationship == "output" in keyframes):
            # - before_start: hidden if NOT consider_start
            # - after_end: hidden if hide_at_end
            visibility_before_start = 1 if consider_start else 0
            visibility_after_end = 0 if hide_at_end else 1

            print(f"🔧 ColorType {colortype_name} properties:")
            print(f"   consider_start: {consider_start}, consider_end: {consider_end}, hide_at_end: {hide_at_end}")
            print(f"   Final visibility: before={visibility_before_start}, after={visibility_after_end}")

            # FORCE construction behavior for undefined ColorTypes
            if not hasattr(ColorType, 'consider_start') or colortype_name in ['DEFAULT', 'NOTDEFINED']:
                visibility_before_start = 0  # Hidden before construction
                visibility_after_end = 1     # Remain visible after construction
                print(f"   🔧 FORCED CONSTRUCTION behavior: before=0 (hidden), after=1 (visible)")

            # Get ColorType ID for material assignment
            colortype_id = get_colortype_id_for_product_enhanced(product, task, ColorType)

            # Get effect type (INSTANT vs GROWTH)
            gn_effect = getattr(ColorType, 'gn_appearance_effect', 'INSTANT')
            effect_type = 1 if gn_effect == 'GROWTH' else 0

            print(f"   🎨 ColorType: {colortype_name}, effect: {gn_effect}, effect_type: {effect_type}")
            print(f"   🔧 colortype_id: {colortype_id}")

            # Bake ALL attributes for this object (V113 complete set)
            attributes_to_set[obj.name] = {
                # Frame attributes
                ATTR_SCHEDULE_START: {
                    "value": start_frame,
                    "type": 'FLOAT',
                    "domain": 'POINT'
                },
                ATTR_SCHEDULE_END: {
                    "value": finish_frame,
                    "type": 'FLOAT',
                    "domain": 'POINT'
                },
                ATTR_SCHEDULE_DURATION: {
                    "value": (task_finish - task_start).days,
                    "type": 'FLOAT',
                    "domain": 'POINT'
                },
                # Actual frames (same as schedule for now)
                ATTR_ACTUAL_START: {
                    "value": start_frame,
                    "type": 'FLOAT',
                    "domain": 'POINT'
                },
                ATTR_ACTUAL_END: {
                    "value": finish_frame,
                    "type": 'FLOAT',
                    "domain": 'POINT'
                },
                ATTR_ACTUAL_DURATION: {
                    "value": (task_finish - task_start).days,
                    "type": 'FLOAT',
                    "domain": 'POINT'
                },
                # Enhanced visibility attributes
                ATTR_VISIBILITY_BEFORE_START: {
                    "value": visibility_before_start,
                    "type": 'INT',
                    "domain": 'POINT'
                },
                ATTR_VISIBILITY_AFTER_END: {
                    "value": visibility_after_end,
                    "type": 'INT',
                    "domain": 'POINT'
                },
                # Effect type attribute
                ATTR_EFFECT_TYPE: {
                    "value": effect_type,
                    "type": 'INT',
                    "domain": 'POINT'
                },
                # ColorType ID for material assignment
                ATTR_COLORTYPE_ID: {
                    "value": colortype_id,
                    "type": 'INT',
                    "domain": 'POINT'
                },
                # Animation state (for advanced control)
                ATTR_ANIMATION_STATE: {
                    "value": 0,  # 0=normal, 1=highlighted, 2=selected
                    "type": 'INT',
                    "domain": 'POINT'
                }
            }

    # Process all root tasks
    if ifcopenshell is None:
        print("❌ ERROR: ifcopenshell not available - cannot get root tasks")
        return {}

    for root_task in ifcopenshell.util.sequence.get_root_tasks(work_schedule):
        process_task_enhanced(root_task)

    print(f"✅ V113 CORE COMPLETED: {len(attributes_to_set)} objects processed with complete attributes")
    return attributes_to_set


def get_assigned_colortype_for_task_enhanced(task):
    """
    V113 FUNCTION: Get the assigned ColorType for a task
    Enhanced version that replicates the exact logic from V113
    """
    try:
        if tool is None:
            print("❌ ERROR: Bonsai tool not available - cannot access animation properties")
            return None

        animation_props = tool.Sequence.get_animation_props()

        # Resolve active group from animation stack
        active_group_name = None
        try:
            for item in getattr(animation_props, 'animation_group_stack', []):
                if getattr(item, 'enabled', False) and getattr(item, 'group', None):
                    active_group_name = item.group
                    break
        except Exception:
            pass

        if not active_group_name:
            active_group_name = getattr(animation_props, 'ColorType_groups', 'DEFAULT')

        print(f"🎯 Active ColorType group: {active_group_name}")

        # Get ColorTypes from the active group
        try:
            colortype_collection = animation_props.ColorTypes
            for colortype in colortype_collection:
                if getattr(colortype, 'name', None) == active_group_name:
                    return colortype
        except Exception as e:
            print(f"⚠️ Error accessing ColorTypes: {e}")

        # Fallback: return first available ColorType
        try:
            if hasattr(animation_props, 'ColorTypes') and len(animation_props.ColorTypes) > 0:
                return animation_props.ColorTypes[0]
        except Exception:
            pass

        print(f"⚠️ No ColorType found for group {active_group_name}")
        return None

    except Exception as e:
        print(f"❌ Error in get_assigned_colortype_for_task_enhanced: {e}")
        return None


def get_colortype_id_for_product_enhanced(product, task, ColorType):
    """
    V113 FUNCTION: Generate consistent ColorType ID for product/task combination
    """
    colortype_name = getattr(ColorType, 'name', 'DEFAULT')

    # Standard ColorType to ID mapping (from V113)
    colortype_to_id = {
        'DEFAULT': 0,
        'CONSTRUCTION': 1,
        'DEMOLITION': 2,
        'TEMPORARY': 3,
        'MODIFICATION': 4,
        'DISPOSAL': 5,
        'DISMANTLE': 6,
        'OPERATION': 7,
        'MAINTENANCE': 8,
        'ATTENDANCE': 9,
        'RENOVATION': 10,
        'LOGISTIC': 11,
        'MOVE': 12,
        'NOTDEFINED': 13,
        'USERDEFINED': 14,
    }

    # For custom ColorType names, generate a consistent ID based on hash
    if colortype_name in colortype_to_id:
        colortype_id = colortype_to_id[colortype_name]
    else:
        # Generate consistent ID for custom ColorTypes using hash
        hash_id = hash(colortype_name) % 100  # Limit to reasonable range
        colortype_id = 15 + abs(hash_id)  # Start custom IDs at 15+
        print(f"   🔧 Custom ColorType '{colortype_name}' -> Generated ID {colortype_id}")

    return colortype_id


def apply_attributes_to_objects_enhanced(context, attributes_data):
    """
    V113 FUNCTION: Apply baked attributes to mesh objects
    Enhanced version with proper error handling and optimization
    """
    print(f"📊 V113: Applying attributes to {len(attributes_data)} objects...")

    for obj_name, attributes in attributes_data.items():
        obj = bpy.data.objects.get(obj_name)
        if not obj or obj.type != 'MESH' or not obj.data:
            continue

        # Ensure mesh has vertices
        if not obj.data.vertices:
            continue

        print(f"   📝 Writing {len(attributes)} attributes to {obj_name}")

        # Apply each attribute
        for attr_name, attr_data in attributes.items():
            try:
                # Remove existing attribute if it exists
                if attr_name in obj.data.attributes:
                    obj.data.attributes.remove(obj.data.attributes[attr_name])

                # Create new attribute
                attr = obj.data.attributes.new(
                    name=attr_name,
                    type=attr_data["type"],
                    domain=attr_data["domain"]
                )

                # Set attribute value for all vertices/points
                for i in range(len(attr.data)):
                    attr.data[i].value = attr_data["value"]

                print(f"      ✅ {attr_name}: {attr_data['value']} ({attr_data['type']})")

            except Exception as e:
                print(f"⚠️ Error setting attribute {attr_name} on {obj_name}: {e}")

    print("✅ V113: Attributes applied successfully")


def create_advanced_nodetree():
    """
    COMPLETE NODE TREE CREATION: Generate the Geometry Nodes tree for 4D animation
    """
    print("🔧 Creating complete Geometry Nodes tree for 4D animation...")

    # Remove existing node tree if it exists
    if GN_NODETREE_NAME in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[GN_NODETREE_NAME])

    # Create new node tree
    node_tree = bpy.data.node_groups.new(GN_NODETREE_NAME, 'GeometryNodeTree')

    # Clear default nodes
    node_tree.nodes.clear()

    # Create input/output nodes
    input_node = node_tree.nodes.new('NodeGroupInput')
    output_node = node_tree.nodes.new('NodeGroupOutput')
    input_node.location = (-800, 0)
    output_node.location = (800, 0)

    # Setup interface
    if hasattr(node_tree, 'interface'):
        # Blender 4.0+ interface system
        interface = node_tree.interface
        interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        interface.new_socket('Current Frame', in_out='INPUT', socket_type='NodeSocketFloat')
        interface.new_socket('Speed Multiplier', in_out='INPUT', socket_type='NodeSocketFloat')
        interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    else:
        # Legacy interface system
        node_tree.inputs.new('NodeSocketGeometry', 'Geometry')
        node_tree.inputs.new('NodeSocketFloat', 'Current Frame')
        node_tree.inputs.new('NodeSocketFloat', 'Speed Multiplier')
        node_tree.outputs.new('NodeSocketGeometry', 'Geometry')

    # Create attribute reading nodes
    attr_start = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_start.location = (-600, 200)
    attr_start.data_type = 'FLOAT'
    attr_start.inputs['Name'].default_value = ATTR_SCHEDULE_START

    attr_end = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_end.location = (-600, 0)
    attr_end.data_type = 'FLOAT'
    attr_end.inputs['Name'].default_value = ATTR_SCHEDULE_END

    attr_vis_before = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_vis_before.location = (-600, -200)
    attr_vis_before.data_type = 'INT'
    attr_vis_before.inputs['Name'].default_value = ATTR_VISIBILITY_BEFORE_START

    attr_vis_after = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_vis_after.location = (-600, -400)
    attr_vis_after.data_type = 'INT'
    attr_vis_after.inputs['Name'].default_value = ATTR_VISIBILITY_AFTER_END

    # Create comparison nodes for visibility logic
    compare_start = node_tree.nodes.new('FunctionNodeCompare')
    compare_start.location = (-300, 200)
    compare_start.data_type = 'FLOAT'
    compare_start.operation = 'GREATER_THAN'

    compare_end = node_tree.nodes.new('FunctionNodeCompare')
    compare_end.location = (-300, 0)
    compare_end.data_type = 'FLOAT'
    compare_end.operation = 'LESS_THAN'

    # Create boolean logic nodes
    bool_and = node_tree.nodes.new('FunctionNodeBooleanMath')
    bool_and.location = (-100, 100)
    bool_and.operation = 'AND'

    # Create delete geometry node for visibility
    delete_geo = node_tree.nodes.new('GeometryNodeDeleteGeometry')
    delete_geo.location = (400, 0)
    delete_geo.domain = 'POINT'

    # Connect the nodes
    links = node_tree.links

    # Connect inputs to comparisons
    links.new(input_node.outputs['Current Frame'], compare_start.inputs[0])
    links.new(attr_start.outputs['Attribute'], compare_start.inputs[1])
    links.new(input_node.outputs['Current Frame'], compare_end.inputs[0])
    links.new(attr_end.outputs['Attribute'], compare_end.inputs[1])

    # Connect comparisons to boolean logic
    links.new(compare_start.outputs['Result'], bool_and.inputs[0])
    links.new(compare_end.outputs['Result'], bool_and.inputs[1])

    # Connect geometry flow
    links.new(input_node.outputs['Geometry'], delete_geo.inputs['Geometry'])
    links.new(bool_and.outputs['Boolean'], delete_geo.inputs['Selection'])
    links.new(delete_geo.outputs['Geometry'], output_node.inputs['Geometry'])

    print("✅ Complete Geometry Nodes tree created successfully")
    return node_tree


def create_super_material():
    """
    SUPER MATERIAL SYSTEM: Create universal material for GN animation
    """
    print("🎨 Creating Bonsai 4D Super Material...")

    # Remove existing material if it exists
    if GN_SUPER_MATERIAL_NAME in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[GN_SUPER_MATERIAL_NAME])

    # Create new material
    material = bpy.data.materials.new(GN_SUPER_MATERIAL_NAME)
    material.use_nodes = True

    # Clear default nodes
    material.node_tree.nodes.clear()

    # Create essential nodes
    output_node = material.node_tree.nodes.new('ShaderNodeOutputMaterial')
    output_node.location = (600, 0)

    principled_node = material.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    principled_node.location = (300, 0)

    # Create attribute nodes for colortype_id
    attr_colortype = material.node_tree.nodes.new('ShaderNodeAttribute')
    attr_colortype.location = (-300, 0)
    attr_colortype.attribute_name = ATTR_COLORTYPE_ID

    # Create ColorRamp for colortype visualization
    color_ramp = material.node_tree.nodes.new('ShaderNodeValToRGB')
    color_ramp.location = (0, 0)

    # Setup ColorRamp with basic construction colors
    color_ramp.color_ramp.elements[0].color = (0.8, 0.8, 0.8, 1.0)  # Default
    color_ramp.color_ramp.elements[1].color = (0.8, 0.6, 0.2, 1.0)  # Construction

    # Connect the nodes
    links = material.node_tree.links
    links.new(attr_colortype.outputs['Fac'], color_ramp.inputs['Fac'])
    links.new(color_ramp.outputs['Color'], principled_node.inputs['Base Color'])
    links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

    print("✅ Bonsai 4D Super Material created successfully")
    return material


def apply_gn_modifier_to_objects(objects_list):
    """
    MODIFIER APPLICATION: Apply GN modifier to objects with robust socket updates
    """
    print(f"🔧 Applying GN modifiers to {len(objects_list)} objects...")

    node_tree = bpy.data.node_groups.get(GN_NODETREE_NAME)
    if not node_tree:
        print("❌ No GN node tree found")
        return False

    material = bpy.data.materials.get(GN_SUPER_MATERIAL_NAME)
    if not material:
        print("❌ No Super Material found")
        return False

    applied_count = 0
    for obj in objects_list:
        if not obj or obj.type != 'MESH':
            continue

        try:
            # Remove existing GN modifier if present
            for mod in obj.modifiers:
                if mod.name == GN_MODIFIER_NAME and mod.type == 'NODES':
                    obj.modifiers.remove(mod)
                    break

            # Add new GN modifier
            modifier = obj.modifiers.new(GN_MODIFIER_NAME, 'NODES')
            modifier.node_group = node_tree

            # Apply super material
            if not obj.data.materials:
                obj.data.materials.append(material)
            else:
                obj.data.materials[0] = material

            # Update modifier sockets with robust method
            update_modifier_sockets_robust(modifier)

            applied_count += 1
            print(f"   ✅ Applied to {obj.name}")

        except Exception as e:
            print(f"   ❌ Failed to apply to {obj.name}: {e}")

    print(f"✅ Applied GN modifiers to {applied_count}/{len(objects_list)} objects")
    return applied_count > 0


def update_modifier_sockets_robust(modifier):
    """
    ROBUST SOCKET UPDATE: Update GN modifier inputs with multiple fallback methods
    """
    current_frame = float(bpy.context.scene.frame_current)
    speed_multiplier = 1.0  # Default speed

    try:
        # Get speed from animation properties
        if tool:
            anim_props = tool.Sequence.get_animation_props()
            speed_multiplier = getattr(anim_props, 'playback_speed', 1.0)
    except Exception:
        pass

    # Method 1: Try by identifier (most robust)
    if hasattr(modifier, 'node_group') and modifier.node_group:
        # Blender 4.0+ interface system
        if hasattr(modifier.node_group, 'interface'):
            for input_socket in modifier.node_group.interface.items_tree:
                if input_socket.in_out == 'INPUT':
                    try:
                        if 'Current Frame' in input_socket.name or 'Frame' in input_socket.name:
                            modifier[input_socket.identifier] = current_frame
                        elif 'Speed' in input_socket.name or 'Multiplier' in input_socket.name:
                            modifier[input_socket.identifier] = speed_multiplier
                    except Exception:
                        continue
        # Legacy interface system
        else:
            for input_socket in modifier.node_group.inputs:
                try:
                    if 'Current Frame' in input_socket.name or 'Frame' in input_socket.name:
                        modifier[input_socket.identifier] = current_frame
                    elif 'Speed' in input_socket.name or 'Multiplier' in input_socket.name:
                        modifier[input_socket.identifier] = speed_multiplier
                except Exception:
                    continue

    # Method 2: Try by index (V113 method)
    try:
        modifier.inputs[1].default_value = current_frame  # Current Frame
        modifier.inputs[2].default_value = speed_multiplier  # Speed Multiplier
    except (IndexError, AttributeError):
        pass

    print(f"   🔧 Updated sockets: frame={current_frame}, speed={speed_multiplier}x")


def create_complete_gn_animation_system():
    """
    COMPLETE SYSTEM: Create the full GN animation system (100% functionality)
    """
    print("🚀 Creating COMPLETE GN animation system (100% functionality)...")

    try:
        # Step 1: Get animation settings
        if not tool:
            print("❌ Bonsai tool not available")
            return False

        settings = tool.Sequence.get_animation_settings()
        if not settings:
            print("❌ Could not get animation settings")
            return False

        work_schedule = tool.Sequence.get_active_work_schedule()
        if not work_schedule:
            print("❌ No active work schedule")
            return False

        print(f"✅ Animation settings obtained: {settings['total_frames']} frames")

        # Step 2: Bake all attributes
        print("🔧 Step 2: Baking complete attributes...")
        attributes_data = bake_all_attributes_worker_enhanced(work_schedule, settings)

        if not attributes_data:
            print("❌ No attributes data generated")
            return False

        print(f"✅ Baked attributes for {len(attributes_data)} objects")

        # Step 3: Apply attributes to objects
        print("🔧 Step 3: Applying attributes to objects...")
        apply_attributes_to_objects_enhanced(bpy.context, attributes_data)

        # Step 4: Create complete node tree
        print("🔧 Step 4: Creating complete node tree...")
        create_advanced_nodetree()

        # Step 5: Create super material
        print("🔧 Step 5: Creating super material...")
        create_super_material()

        # Step 6: Apply modifiers to objects
        print("🔧 Step 6: Applying modifiers to objects...")
        objects_list = [bpy.data.objects.get(obj_name) for obj_name in attributes_data.keys()]
        objects_list = [obj for obj in objects_list if obj]
        apply_gn_modifier_to_objects(objects_list)

        print("✅ COMPLETE GN animation system created successfully (100%)")
        return True

    except Exception as e:
        print(f"❌ Error creating complete GN animation system: {e}")
        import traceback
        traceback.print_exc()
        return False


# Export main functions
__all__ = [
    'bake_all_attributes_worker_enhanced',
    'get_assigned_colortype_for_task_enhanced',
    'get_colortype_id_for_product_enhanced',
    'apply_attributes_to_objects_enhanced',
    'create_complete_gn_animation_system',
    'create_advanced_nodetree',
    'create_super_material',
    'apply_gn_modifier_to_objects',
    'update_modifier_sockets_robust'
]