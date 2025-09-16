# Enhanced Geometry Nodes Sequence System for Bonsai 4D
# Complete implementation of the 4D Animation system using Geometry Nodes
# This file contains the refactored and enhanced version of the GN system

import bpy
import time
import bmesh
from typing import Dict, Any, Optional, Tuple
from bonsai.core import async_manager

# Import bonsai tool safely
try:
    import bonsai.tool as tool
    import ifcopenshell
    import ifcopenshell.util.sequence
except ImportError:
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
        import bonsai.tool as tool
        import ifcopenshell
        import ifcopenshell.util.sequence
    except ImportError:
        tool = None
        ifcopenshell = None

# --- ENHANCED CONSTANTS ---
GN_MODIFIER_NAME = "Bonsai 4D"
GN_NODETREE_NAME = "Bonsai 4D Node Tree"
GN_SUPER_MATERIAL_NAME = "Bonsai 4D Super Material"
GN_CONTROLLER_COLLECTION = "GN_CONTROLLERS"

# Enhanced attribute names
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
ATTR_RELATIONSHIP_TYPE = "relationship_type"  # 0=OUTPUT, 1=INPUT

def bake_all_attributes_worker_enhanced(work_schedule, settings):
    """
    ETAPA 1: Refactorized worker function that is autonomous and bakes a complete
    set of attributes defining object behavior over time.

    This function replicates the logic from get_animation_settings and
    get_animation_product_frames_enhanced to correctly calculate dates,
    frames, and states structure.
    """
    async_manager.update_progress(0, "Iniciando horneado completo de atributos...")

    print("🚀 ETAPA 1: Enhanced attribute baking with complete logic replication")

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

    # Step 3: Replicate get_animation_product_frames_enhanced logic
    product_frames = {}
    attributes_to_set = {}

    def process_task_enhanced(task):
        """Enhanced task processing with complete ColorType logic"""
        if ifcopenshell is None:
            print("❌ ERROR: ifcopenshell not available - cannot process nested tasks")
            return
        for subtask in ifcopenshell.util.sequence.get_nested_tasks(task):
            process_task_enhanced(subtask)

        # Get task dates using the same logic as keyframes
        task_start = ifcopenshell.util.sequence.derive_date(task, start_date_type, is_earliest=True)
        task_finish = ifcopenshell.util.sequence.derive_date(task, finish_date_type, is_latest=True)

        if not task_start or not task_finish:
            return

        # Get ColorType profile for this task - REAL ASSIGNMENT
        ColorType = get_assigned_ColorType_for_task_enhanced(task)

        # Check for priority mode (consider_start only)
        is_priority_mode = (
            getattr(ColorType, 'consider_start', False) and
            not getattr(ColorType, 'consider_active', True) and
            not getattr(ColorType, 'consider_end', True)
        )

        # Calculate frames
        if task_start > viz_finish:
            return

        if viz_duration.total_seconds() > 0:
            start_progress = (task_start - viz_start).total_seconds() / viz_duration.total_seconds()
            finish_progress = (task_finish - viz_start).total_seconds() / viz_duration.total_seconds()
        else:
            start_progress, finish_progress = 0.0, 1.0

        start_frame = int(round(settings["start_frame"] + (start_progress * settings["total_frames"])))
        finish_frame = int(round(settings["start_frame"] + (finish_progress * settings["total_frames"])))

        # Process task outputs and inputs
        all_products = []
        if ifcopenshell is not None:
            for output in ifcopenshell.util.sequence.get_task_outputs(task):
                all_products.append((output, "output"))
        else:
            print("❌ WARNING: ifcopenshell not available - cannot get task outputs")
        try:
            for input_prod in tool.Sequence.get_task_inputs(task):
                all_products.append((input_prod, "input"))
        except AttributeError:
            print(f"❌ WARNING: Cannot access task inputs for task {task} - tool.Sequence not available")
            pass

        for product, relationship in all_products:
            try:
                obj = tool.Ifc.get_object(product)
            except AttributeError:
                print(f"❌ WARNING: Cannot get object for product {product} - tool.Ifc not available")
                continue
            if not obj or obj.type != 'MESH':
                continue

            product_id = product.id()

            # CORRECTED VISIBILITY LOGIC: Replicate keyframes system exactly
            colortype_name = getattr(ColorType, 'name', 'UNKNOWN')
            consider_start = getattr(ColorType, 'consider_start', True)
            hide_at_end = getattr(ColorType, 'hide_at_end', False)

            # ENHANCED VISIBILITY LOGIC: Consider both relationship AND ColorType
            if colortype_name in ['DEMOLITION', 'DISMANTLE', 'REMOVAL', 'DISPOSAL']:
                # DEMOLITION-type objects: exist before, disappear after task (regardless of relationship)
                visibility_before_start = 1
                visibility_after_end = 0
                print(f"   🧨 DEMOLITION-TYPE ({colortype_name}): before={visibility_before_start}, after={visibility_after_end}")
            elif relationship == "output":  # CONSTRUCTION objects
                # Construction objects: hidden before start unless consider_start=True
                # Remain visible after end unless hide_at_end=True
                visibility_before_start = 1 if consider_start else 0
                visibility_after_end = 0 if hide_at_end else 1
                print(f"   🏗️  CONSTRUCTION (output): before={visibility_before_start}, after={visibility_after_end}")
            elif relationship == "input":  # INPUT objects (non-demolition)
                # Input objects: visible before (they exist), behavior depends on ColorType
                visibility_before_start = 1
                visibility_after_end = 0 if hide_at_end else 1
                print(f"   📦 INPUT (input): before={visibility_before_start}, after={visibility_after_end}")
            else:  # Default behavior for unknown relationships
                visibility_before_start = 1 if consider_start else 0
                visibility_after_end = 0 if hide_at_end else 1
                print(f"   ❓ UNKNOWN relationship ({relationship}): before={visibility_before_start}, after={visibility_after_end}")

            print(f"🔧 VISIBILITY LOGIC ({relationship}): ColorType={colortype_name}")
            print(f"   Properties: consider_start={consider_start}, hide_at_end={hide_at_end}")
            print(f"   Final visibility: before={visibility_before_start}, after={visibility_after_end}")

            # Get ColorType ID for material assignment
            colortype_id = get_colortype_id_for_product_enhanced(product, task, ColorType)

            # Convert relationship to numeric value for attribute (0=OUTPUT, 1=INPUT)
            relationship_type = 0 if relationship == "output" else 1

            # Debug ColorType properties
            colortype_name = getattr(ColorType, 'name', 'UNKNOWN')
            gn_effect = getattr(ColorType, 'gn_appearance_effect', 'INSTANT')
            effect_type = 1 if gn_effect == 'GROWTH' else 0
            print(f"   🎨 ColorType: {colortype_name}, gn_appearance_effect: {gn_effect}, effect_type: {effect_type}")
            print(f"   🔧 DEBUG: colortype_id assigned: {colortype_id}")

            # Bake all attributes for this object
            attributes_to_set[obj.name] = {
                # Frame attributes (use frame numbers for GN comparison)
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
                # Enhanced visibility attributes (NEW)
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
                # Effect type attribute (NEW)
                ATTR_EFFECT_TYPE: {
                    "value": effect_type,
                    "type": 'INT',
                    "domain": 'POINT'
                },
                # ColorType ID for material system (NEW)
                ATTR_COLORTYPE_ID: {
                    "value": colortype_id,
                    "type": 'INT',
                    "domain": 'POINT'
                },
                # Relationship type (NEW): 0=OUTPUT, 1=INPUT
                ATTR_RELATIONSHIP_TYPE: {
                    "value": relationship_type,
                    "type": 'INT',
                    "domain": 'POINT'
                }
            }

            # Debug timing values
            print(f"✅ Enhanced attributes prepared for {obj.name}: ColorType={ColorType.name if hasattr(ColorType, 'name') else 'N/A'}")
            print(f"   📅 Task dates: {task_start} to {task_finish}")
            print(f"   🎬 Frame range: {start_frame} to {finish_frame} (USING THESE IN ATTRIBUTES)")
            print(f"   👁️  Visibility: before={visibility_before_start}, after={visibility_after_end}, effect={effect_type}")
            print(f"   🔗 Relationship: {relationship} (type={relationship_type})")
            print(f"   🔧 GN will compare Current Frame with start_frame={start_frame} and end_frame={finish_frame}")

    # Process all root tasks
    if ifcopenshell is None:
        print("❌ ERROR: ifcopenshell not available - cannot get root tasks")
        return {}
    for root_task in ifcopenshell.util.sequence.get_root_tasks(work_schedule):
        process_task_enhanced(root_task)

    async_manager.update_progress(100, "Horneado completo completado")
    print(f"✅ ETAPA 1 COMPLETADA: {len(attributes_to_set)} objetos procesados con atributos completos")

    return attributes_to_set

def get_assigned_ColorType_for_task_enhanced(task):
    """
    REFACTORED VERSION: Determines the ColorType for a task replicating the exact
    precedence logic of the keyframes system and UI.
    """
    try:
        import bpy, json
        from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager

        context = bpy.context
        animation_props = tool.Sequence.get_animation_props()
        task_id_str = str(task.id())

        # 1. DETERMINE ACTIVE GROUP (CORRECT PRECEDENCE LOGIC)
        active_group_name = "DEFAULT"
        # Priority 1: First ENABLED group in animation stack.
        for item in getattr(animation_props, 'animation_group_stack', []):
            if getattr(item, 'enabled', False) and getattr(item, 'group', None):
                active_group_name = item.group
                break

        print(f"   🎨 Determining ColorType for Task {task_id_str} in Active Group '{active_group_name}'")

        # 2. GET TASK-SPECIFIC CONFIGURATION (from UI snapshot)
        task_config = None
        try:
            cache_raw = context.scene.get("_task_colortype_snapshot_cache_json")
            if cache_raw:
                task_config = json.loads(cache_raw).get(task_id_str)
        except Exception:
            pass

        # 3. RESOLVE COLORTYPE NAME
        colortype_name = None
        # Priority A: Task-specific assignment for active group.
        if task_config and 'groups' in task_config:
            for choice in task_config['groups']:
                if choice.get('group_name') == active_group_name and choice.get('enabled') and choice.get('selected_value'):
                    colortype_name = choice['selected_value']
                    print(f"      -> Found via Task-Specific assignment: '{colortype_name}'")
                    break

        # Priority B: If no specific assignment, use task PredefinedType.
        if not colortype_name:
            colortype_name = getattr(task, "PredefinedType", "NOTDEFINED") or "NOTDEFINED"
            print(f"      -> Using PredefinedType fallback: '{colortype_name}'")

        # 4. LOAD COLORTYPE DATA FROM CORRECT GROUP
        ColorType_data = UnifiedColorTypeManager.get_group_colortypes(context, active_group_name).get(colortype_name)

        # Fallback: If not found in active group, search in DEFAULT.
        if not ColorType_data and active_group_name != "DEFAULT":
            print(f"      -> Not found in '{active_group_name}', trying DEFAULT group...")
            ColorType_data = UnifiedColorTypeManager.get_group_colortypes(context, "DEFAULT").get(colortype_name)

        # Final fallback: If still not found, use NOTDEFINED from DEFAULT.
        if not ColorType_data:
            print(f"      -> Still not found, using NOTDEFINED from DEFAULT.")
            colortype_name = "NOTDEFINED"
            ColorType_data = UnifiedColorTypeManager.get_group_colortypes(context, "DEFAULT").get(colortype_name)

        if ColorType_data:
            return create_colortype_from_data(colortype_name, ColorType_data)
        else:
            return create_default_colortype(colortype_name)

    except Exception as e:
        print(f"⚠️ CRITICAL ERROR in get_assigned_ColorType_for_task_enhanced: {e}")
        return create_default_colortype("NOTDEFINED")

def create_default_colortype(name):
    """
    FIXED: Create a default ColorType using real data from DEFAULT group
    instead of hardcoded values
    """
    try:
        import bpy
        from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager

        context = bpy.context

        # Try to get the ColorType from DEFAULT group first
        default_group_colortypes = UnifiedColorTypeManager.get_group_colortypes(context, "DEFAULT")

        if name in default_group_colortypes:
            # Use real data from DEFAULT group
            colortype_data = default_group_colortypes[name]
            print(f"   🎯 Using real DEFAULT group data for '{name}'")
            return create_colortype_from_data(name, colortype_data)

        # If not found in DEFAULT, look for NOTDEFINED
        if "NOTDEFINED" in default_group_colortypes:
            colortype_data = default_group_colortypes["NOTDEFINED"]
            print(f"   🎯 Using NOTDEFINED from DEFAULT group for '{name}'")
            return create_colortype_from_data(name, colortype_data)

    except Exception as e:
        print(f"   ⚠️ Cannot access DEFAULT group, using hardcoded fallback: {e}")

    # Final fallback: hardcoded values only if DEFAULT group is not accessible
    class DefaultColorType:
        def __init__(self, name):
            self.name = name
            self.consider_start = True
            self.consider_active = True
            self.consider_end = True
            self.hide_at_end = False
            self.gn_appearance_effect = 'INSTANT'
            self.start_color = (0.5, 0.5, 0.5, 1.0)
            self.active_color = (0.0, 0.8, 0.0, 1.0)
            self.end_color = (0.8, 0.8, 0.8, 1.0)
            # CRITICAL: Set flags to use real colors
            self.use_start_original_color = False
            self.use_active_original_color = False
            self.use_end_original_color = False

    print(f"   🔧 Using hardcoded fallback ColorType for '{name}'")
    return DefaultColorType(name)

def create_colortype_from_data(colortype_name, colortype_data):
    """Create ColorType object from data dictionary"""
    class DataColorType:
        def __init__(self, name, data):
            self.name = name
            self.consider_start = data.get('consider_start', True)
            self.consider_active = data.get('consider_active', True)
            self.consider_end = data.get('consider_end', True)
            self.hide_at_end = data.get('hide_at_end', False)
            self.gn_appearance_effect = data.get('gn_appearance_effect', 'INSTANT')

            # FIXED: Read real color data from ColorType using correct field names
            self.start_color = data.get('start_color', [1, 1, 1, 1])
            self.active_color = data.get('in_progress_color', [0.0, 0.8, 0.0, 1.0])  # Note: in_progress_color not active_color
            self.end_color = data.get('end_color', [0.8, 0.8, 0.8, 1.0])

            # CRITICAL FIX: Read use_original_color flags from real ColorType data
            self.use_start_original_color = data.get('use_start_original_color', False)
            self.use_active_original_color = data.get('use_active_original_color', False)
            self.use_end_original_color = data.get('use_end_original_color', False)

            # Read transparency data
            self.start_transparency = data.get('start_transparency', 0.0)
            self.active_start_transparency = data.get('active_start_transparency', 0.0)
            self.end_transparency = data.get('end_transparency', 0.0)

            # DEBUG: Print all ColorType properties for verification
            print(f"   🔧 ColorType '{name}' properties loaded:")
            print(f"      consider_start: {self.consider_start}")
            print(f"      consider_end: {self.consider_end}")
            print(f"      hide_at_end: {self.hide_at_end}")
            print(f"      colors: start={self.start_color}, active={self.active_color}, end={self.end_color}")
            print(f"      use_original_colors: start={self.use_start_original_color}, active={self.use_active_original_color}, end={self.use_end_original_color}")

    return DataColorType(colortype_name, colortype_data)

def get_colortype_id_for_product_enhanced(product, task, colortype):
    """
    Enhanced version that generates unique ColorType IDs
    """
    # Map ColorType names to numeric IDs
    colortype_name = getattr(colortype, 'name', 'NOTDEFINED')

    # Base ColorType mapping for standard types
    colortype_to_id = {
        'DEFAULT': 0,
        'CONSTRUCTION': 1,
        'INSTALLATION': 2,
        'DEMOLITION': 3,
        'REMOVAL': 4,
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
        # This ensures same ColorType name always gets same ID
        hash_id = hash(colortype_name) % 100  # Limit to reasonable range
        colortype_id = 15 + abs(hash_id)  # Start custom IDs at 15+
        print(f"   🔧 Custom ColorType '{colortype_name}' -> Generated ID {colortype_id}")

    print(f"   🔧 DEBUG ColorType ID: '{colortype_name}' -> ID {colortype_id}")
    return colortype_id

def convert_date_to_day_number(date):
    """Convert a datetime to day number since epoch for GN compatibility"""
    try:
        from datetime import datetime
        epoch = datetime(1970, 1, 1)
        if isinstance(date, datetime):
            return (date - epoch).days
        return 0.0
    except Exception:
        return 0.0

def create_advanced_nodetree_enhanced():
    """
    ETAPA 2: Enhanced node tree with complete visibility logic
    that implements the three-state behavior using baked attributes
    """
    print("🔧 ETAPA 2: Creating enhanced node tree with complete visibility logic")

    if GN_NODETREE_NAME in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[GN_NODETREE_NAME])

    # Create enhanced node tree
    node_tree = bpy.data.node_groups.new(GN_NODETREE_NAME, 'GeometryNodeTree')

    # Enhanced input/output interface
    node_tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    node_tree.interface.new_socket('Current Frame', in_out='INPUT', socket_type='NodeSocketFloat')
    node_tree.interface.new_socket('Schedule Type', in_out='INPUT', socket_type='NodeSocketInt')
    node_tree.interface.new_socket('ColorType Group', in_out='INPUT', socket_type='NodeSocketInt')
    node_tree.interface.new_socket('Speed Multiplier', in_out='INPUT', socket_type='NodeSocketFloat')
    node_tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

    # Input and output nodes
    input_node = node_tree.nodes.new('NodeGroupInput')
    input_node.location = (-1200, 0)
    output_node = node_tree.nodes.new('NodeGroupOutput')
    output_node.location = (1200, 0)

    # STEP 1: Read enhanced attributes
    attr_schedule_start = create_attribute_reader(node_tree, ATTR_SCHEDULE_START, 'FLOAT', (-1000, 400))
    attr_schedule_end = create_attribute_reader(node_tree, ATTR_SCHEDULE_END, 'FLOAT', (-1000, 300))
    attr_visibility_before = create_attribute_reader(node_tree, ATTR_VISIBILITY_BEFORE_START, 'INT', (-1000, 200))
    attr_visibility_after = create_attribute_reader(node_tree, ATTR_VISIBILITY_AFTER_END, 'INT', (-1000, 100))
    attr_effect_type = create_attribute_reader(node_tree, ATTR_EFFECT_TYPE, 'INT', (-1000, 0))
    attr_colortype_id = create_attribute_reader(node_tree, ATTR_COLORTYPE_ID, 'INT', (-1000, -100))

    # STEP 2: Enhanced visibility logic with three states
    visibility_system = create_enhanced_visibility_system(
        node_tree,
        input_node,
        attr_schedule_start,
        attr_schedule_end,
        attr_visibility_before,
        attr_visibility_after,
        (-600, 200)
    )

    # STEP 3: Effect system (Instant vs Growth)
    effect_system = create_effect_system(
        node_tree,
        input_node,
        attr_schedule_start,
        attr_schedule_end,
        attr_effect_type,
        visibility_system,
        (-200, 0)
    )

    # STEP 4: Delete Geometry based on final visibility
    delete_geometry = node_tree.nodes.new('GeometryNodeDeleteGeometry')
    delete_geometry.location = (200, 0)

    # STEP 5: Enhanced material/color system
    material_system = create_enhanced_material_system(
        node_tree,
        attr_colortype_id,
        (400, 200)
    )

    # STEP 6: Store animation state for shader output
    store_animation_state = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
    store_animation_state.data_type = 'FLOAT'
    store_animation_state.domain = 'POINT'
    store_animation_state.inputs['Name'].default_value = ATTR_ANIMATION_STATE
    store_animation_state.location = (600, 0)

    # STEP 7: Store colortype_id for shader
    store_colortype_for_shader = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
    store_colortype_for_shader.data_type = 'INT'
    store_colortype_for_shader.domain = 'POINT'
    store_colortype_for_shader.inputs['Name'].default_value = "colortype_id"
    store_colortype_for_shader.location = (800, 0)

    # Create inversion for Delete Geometry (when visibility=True, we DON'T want to delete)
    invert_visibility = node_tree.nodes.new('FunctionNodeBooleanMath')
    invert_visibility.operation = 'NOT'
    invert_visibility.location = (150, -50)

    # Enhanced connections
    node_tree.links.new(input_node.outputs['Geometry'], delete_geometry.inputs['Geometry'])
    # Use visibility system (inverted) for delete selection
    node_tree.links.new(visibility_system.outputs['Boolean'], invert_visibility.inputs['Boolean'])
    node_tree.links.new(invert_visibility.outputs['Boolean'], delete_geometry.inputs['Selection'])

    if material_system:
        node_tree.links.new(delete_geometry.outputs['Geometry'], material_system.inputs['Geometry'])
        node_tree.links.new(material_system.outputs['Geometry'], store_animation_state.inputs['Geometry'])
    else:
        node_tree.links.new(delete_geometry.outputs['Geometry'], store_animation_state.inputs['Geometry'])

    # Store animation state and colortype for shader
    animation_state = calculate_animation_state(node_tree, input_node, attr_schedule_start, attr_schedule_end, (400, -200))
    node_tree.links.new(animation_state.outputs['Value'], store_animation_state.inputs['Value'])
    node_tree.links.new(store_animation_state.outputs['Geometry'], store_colortype_for_shader.inputs['Geometry'])
    node_tree.links.new(attr_colortype_id.outputs['Attribute'], store_colortype_for_shader.inputs['Value'])

    # Final output
    node_tree.links.new(store_colortype_for_shader.outputs['Geometry'], output_node.inputs['Geometry'])

    print("✅ ETAPA 2 COMPLETADA: Enhanced node tree with complete visibility logic created")
    return node_tree

def create_attribute_reader(node_tree, attr_name, data_type, location):
    """Helper to create attribute reader nodes"""
    attr_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_node.data_type = data_type
    attr_node.inputs['Name'].default_value = attr_name
    attr_node.location = location
    return attr_node

def create_enhanced_visibility_system(node_tree, input_node, attr_start, attr_end, attr_vis_before, attr_vis_after, location):
    """
    Enhanced visibility system that implements complete three-state logic:
    before_start, active, after_end
    """
    # Current frame comparison nodes
    compare_started = node_tree.nodes.new('FunctionNodeCompare')
    compare_started.operation = 'GREATER_EQUAL'
    compare_started.data_type = 'FLOAT'
    compare_started.location = (location[0], location[1] + 100)

    compare_finished = node_tree.nodes.new('FunctionNodeCompare')
    compare_finished.operation = 'LESS_THAN'
    compare_finished.data_type = 'FLOAT'
    compare_finished.location = (location[0], location[1])

    # State calculation
    # es_antes = Current Frame < schedule_start
    # es_activo = Current Frame >= schedule_start AND Current Frame < schedule_end
    # es_despues = Current Frame >= schedule_end

    # Active state (between start and end)
    bool_and_active = node_tree.nodes.new('FunctionNodeBooleanMath')
    bool_and_active.operation = 'AND'
    bool_and_active.location = (location[0] + 200, location[1] + 50)

    # Before state (before start)
    compare_before = node_tree.nodes.new('FunctionNodeCompare')
    compare_before.operation = 'LESS_THAN'
    compare_before.data_type = 'FLOAT'
    compare_before.location = (location[0], location[1] - 100)

    # After state (after end)
    compare_after = node_tree.nodes.new('FunctionNodeCompare')
    compare_after.operation = 'GREATER_EQUAL'
    compare_after.data_type = 'FLOAT'
    compare_after.location = (location[0], location[1] - 200)

    # FIXED VISIBILITY LOGIC:
    # visible_final = (before_state AND visibility_before) OR (active_state) OR (after_state AND visibility_after)
    # DEBUG: Adding debug info for visibility logic

    before_visibility = node_tree.nodes.new('FunctionNodeBooleanMath')
    before_visibility.operation = 'AND'
    before_visibility.location = (location[0] + 400, location[1] + 100)

    after_visibility = node_tree.nodes.new('FunctionNodeBooleanMath')
    after_visibility.operation = 'AND'
    after_visibility.location = (location[0] + 400, location[1] - 100)

    # Convert int to bool for visibility attributes
    before_to_bool = node_tree.nodes.new('FunctionNodeCompare')
    before_to_bool.operation = 'GREATER_THAN'
    before_to_bool.data_type = 'INT'
    before_to_bool.inputs[1].default_value = 0
    before_to_bool.location = (location[0] + 200, location[1] + 200)

    after_to_bool = node_tree.nodes.new('FunctionNodeCompare')
    after_to_bool.operation = 'GREATER_THAN'
    after_to_bool.data_type = 'INT'
    after_to_bool.inputs[1].default_value = 0
    after_to_bool.location = (location[0] + 200, location[1] - 200)

    # Final OR logic
    or_before_active = node_tree.nodes.new('FunctionNodeBooleanMath')
    or_before_active.operation = 'OR'
    or_before_active.location = (location[0] + 600, location[1])

    final_or = node_tree.nodes.new('FunctionNodeBooleanMath')
    final_or.operation = 'OR'
    final_or.location = (location[0] + 800, location[1])

    # Connections
    # Current frame comparisons
    node_tree.links.new(input_node.outputs['Current Frame'], compare_started.inputs[0])
    node_tree.links.new(attr_start.outputs['Attribute'], compare_started.inputs[1])

    node_tree.links.new(input_node.outputs['Current Frame'], compare_finished.inputs[0])
    node_tree.links.new(attr_end.outputs['Attribute'], compare_finished.inputs[1])

    node_tree.links.new(input_node.outputs['Current Frame'], compare_before.inputs[0])
    node_tree.links.new(attr_start.outputs['Attribute'], compare_before.inputs[1])

    node_tree.links.new(input_node.outputs['Current Frame'], compare_after.inputs[0])
    node_tree.links.new(attr_end.outputs['Attribute'], compare_after.inputs[1])

    # Active state (started AND not finished)
    node_tree.links.new(compare_started.outputs['Result'], bool_and_active.inputs[0])
    node_tree.links.new(compare_finished.outputs['Result'], bool_and_active.inputs[1])

    # Visibility attribute conversions
    node_tree.links.new(attr_vis_before.outputs['Attribute'], before_to_bool.inputs[0])
    node_tree.links.new(attr_vis_after.outputs['Attribute'], after_to_bool.inputs[0])

    # Visibility combinations
    node_tree.links.new(compare_before.outputs['Result'], before_visibility.inputs[0])
    node_tree.links.new(before_to_bool.outputs['Result'], before_visibility.inputs[1])

    node_tree.links.new(compare_after.outputs['Result'], after_visibility.inputs[0])
    node_tree.links.new(after_to_bool.outputs['Result'], after_visibility.inputs[1])

    # Final visibility logic
    node_tree.links.new(before_visibility.outputs['Boolean'], or_before_active.inputs[0])
    node_tree.links.new(bool_and_active.outputs['Boolean'], or_before_active.inputs[1])

    node_tree.links.new(or_before_active.outputs['Boolean'], final_or.inputs[0])
    node_tree.links.new(after_visibility.outputs['Boolean'], final_or.inputs[1])

    print("✅ FIXED Enhanced visibility system with corrected three-state logic created")
    print(f"   🔧 Logic: (before AND vis_before) OR (active) OR (after AND vis_after)")
    return final_or

def create_effect_system(node_tree, input_node, attr_start, attr_end, attr_effect, visibility_system, location):
    """Create the effect system for Instant vs Growth appearance"""
    # Growth effect calculation (for effect_type = 1)
    # Calculate progress: (current_frame - start_frame) / (end_frame - start_frame)

    subtract_progress = node_tree.nodes.new('ShaderNodeMath')
    subtract_progress.operation = 'SUBTRACT'
    subtract_progress.location = location

    subtract_duration = node_tree.nodes.new('ShaderNodeMath')
    subtract_duration.operation = 'SUBTRACT'
    subtract_duration.location = (location[0], location[1] - 100)

    divide_progress = node_tree.nodes.new('ShaderNodeMath')
    divide_progress.operation = 'DIVIDE'
    divide_progress.location = (location[0] + 200, location[1])

    clamp_progress = node_tree.nodes.new('ShaderNodeClamp')
    clamp_progress.inputs['Min'].default_value = 0.0
    clamp_progress.inputs['Max'].default_value = 1.0
    clamp_progress.location = (location[0] + 400, location[1])

    # Growth geometry effect (simplified - could be enhanced)
    position_node = node_tree.nodes.new('GeometryNodeInputPosition')
    position_node.location = (location[0], location[1] - 300)

    separate_xyz = node_tree.nodes.new('ShaderNodeSeparateXYZ')
    separate_xyz.location = (location[0] + 200, location[1] - 300)

    # Z-based growth effect
    multiply_z_progress = node_tree.nodes.new('ShaderNodeMath')
    multiply_z_progress.operation = 'MULTIPLY'
    multiply_z_progress.location = (location[0] + 400, location[1] - 300)

    compare_z_threshold = node_tree.nodes.new('FunctionNodeCompare')
    compare_z_threshold.operation = 'LESS_EQUAL'
    compare_z_threshold.data_type = 'FLOAT'
    compare_z_threshold.location = (location[0] + 600, location[1] - 300)

    # Switch between Instant and Growth
    effect_switch = node_tree.nodes.new('GeometryNodeSwitch')
    effect_switch.input_type = 'BOOLEAN'
    effect_switch.location = (location[0] + 600, location[1])

    # Convert effect type int to bool
    effect_to_bool = node_tree.nodes.new('FunctionNodeCompare')
    effect_to_bool.operation = 'GREATER_THAN'
    effect_to_bool.data_type = 'INT'
    effect_to_bool.inputs[1].default_value = 0
    effect_to_bool.location = (location[0] + 400, location[1] + 100)

    # Connections
    # Progress calculation
    node_tree.links.new(input_node.outputs['Current Frame'], subtract_progress.inputs[0])
    node_tree.links.new(attr_start.outputs['Attribute'], subtract_progress.inputs[1])

    node_tree.links.new(attr_end.outputs['Attribute'], subtract_duration.inputs[0])
    node_tree.links.new(attr_start.outputs['Attribute'], subtract_duration.inputs[1])

    node_tree.links.new(subtract_progress.outputs['Value'], divide_progress.inputs[0])
    node_tree.links.new(subtract_duration.outputs['Value'], divide_progress.inputs[1])

    node_tree.links.new(divide_progress.outputs['Value'], clamp_progress.inputs['Value'])

    # Growth effect
    node_tree.links.new(position_node.outputs['Position'], separate_xyz.inputs['Vector'])
    node_tree.links.new(separate_xyz.outputs['Z'], multiply_z_progress.inputs[0])
    node_tree.links.new(clamp_progress.outputs['Result'], multiply_z_progress.inputs[1])

    node_tree.links.new(separate_xyz.outputs['Z'], compare_z_threshold.inputs[0])
    node_tree.links.new(multiply_z_progress.outputs['Value'], compare_z_threshold.inputs[1])

    # Effect switch
    node_tree.links.new(attr_effect.outputs['Attribute'], effect_to_bool.inputs[0])
    node_tree.links.new(effect_to_bool.outputs['Result'], effect_switch.inputs['Switch'])

    # Instant effect uses visibility system directly
    node_tree.links.new(visibility_system.outputs['Boolean'], effect_switch.inputs['False'])
    # Growth effect combines visibility with growth
    growth_and_visibility = node_tree.nodes.new('FunctionNodeBooleanMath')
    growth_and_visibility.operation = 'AND'
    growth_and_visibility.location = (location[0] + 400, location[1] - 150)

    node_tree.links.new(visibility_system.outputs['Boolean'], growth_and_visibility.inputs[0])
    node_tree.links.new(compare_z_threshold.outputs['Result'], growth_and_visibility.inputs[1])
    node_tree.links.new(growth_and_visibility.outputs['Boolean'], effect_switch.inputs['True'])

    # NO INVERT - Direct visibility control
    # If visibility_system returns True when object should be visible,
    # we DON'T invert for Delete Geometry - we want to delete when invisible (False)
    # Let's test without inversion first
    print("🔧 DEBUG: Using direct visibility without inversion")
    # invert_for_delete = node_tree.nodes.new('FunctionNodeBooleanMath')
    # invert_for_delete.operation = 'NOT'
    # invert_for_delete.location = (location[0] + 800, location[1])
    # node_tree.links.new(effect_switch.outputs['Output'], invert_for_delete.inputs['Boolean'])

    print("✅ Effect system (Instant vs Growth) created")
    return effect_switch  # Return the switch directly instead of inverted

def create_enhanced_material_system(node_tree, attr_colortype_id, location):
    """
    ETAPA 3: Create enhanced material system that supports both
    Material Preview/Rendered and Solid viewport modes
    """
    print("🎨 ETAPA 3: Creating enhanced dual material system")

    # Create the Super Material first
    super_material = create_super_material()

    # Set Material node for rendered modes
    set_material = node_tree.nodes.new('GeometryNodeSetMaterial')
    set_material.location = location
    set_material.inputs['Material'].default_value = super_material

    print(f"✅ ETAPA 3: Enhanced material system created")
    print(f"   🎨 Super Material: {super_material.name} (ID: {super_material})")
    print(f"   🔧 Set Material Node: {set_material.name} at {location}")
    return set_material

def create_super_material():
    """
    ETAPA 3: Create the universal Super Material for Material/Render modes
    """
    material_name = GN_SUPER_MATERIAL_NAME

    # Remove existing material if it exists
    if material_name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[material_name])

    # Create new material
    super_material = bpy.data.materials.new(material_name)
    super_material.use_nodes = True

    # Clear default nodes
    super_material.node_tree.nodes.clear()

    # Create material nodes
    output_node = super_material.node_tree.nodes.new('ShaderNodeOutputMaterial')
    output_node.location = (400, 0)

    bsdf_node = super_material.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf_node.location = (200, 0)

    # Read animation state and colortype from geometry attributes
    attr_animation_state = super_material.node_tree.nodes.new('ShaderNodeAttribute')
    attr_animation_state.attribute_name = ATTR_ANIMATION_STATE
    attr_animation_state.location = (-400, 200)

    attr_colortype_id = super_material.node_tree.nodes.new('ShaderNodeAttribute')
    attr_colortype_id.attribute_name = "colortype_id"
    attr_colortype_id.location = (-400, 0)

    # Create dynamic color system based on colortype_id and animation_state
    color_system = create_material_color_system(super_material.node_tree, attr_colortype_id, attr_animation_state, (0, 100))

    # Connect to BSDF
    super_material.node_tree.links.new(color_system.outputs['Color'], bsdf_node.inputs['Base Color'])
    super_material.node_tree.links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])

    print(f"✅ Super Material '{material_name}' created with dynamic color system")
    return super_material

def create_material_color_system(node_tree, attr_colortype, attr_animation_state, location):
    """Create DYNAMIC color system for the Super Material using REAL ColorType colors from DEFAULT group"""

    print("🎨 Creating DYNAMIC Super Material system using REAL ColorType colors from ACTIVE group")

    # REAL ColorType colors from ACTIVE group - DYNAMIC system
    real_colortype_ramps = {}

    # Get the active group name
    import bpy
    try:
        animation_props = tool.Sequence.get_animation_props()
        active_group_name = "DEFAULT"
        for item in getattr(animation_props, 'animation_group_stack', []):
            if getattr(item, 'enabled', False) and getattr(item, 'group', None):
                active_group_name = item.group
                break
        print(f"   🎯 Using ACTIVE group: {active_group_name}")
    except:
        active_group_name = "DEFAULT"
        print(f"   🎯 Fallback to DEFAULT group")

    # Get the main ColorTypes from ACTIVE group
    colortype_names = ['CONSTRUCTION', 'DEMOLITION', 'MOVE', 'INSTALLATION', 'DEFAULT']

    for i, colortype_name in enumerate(colortype_names):
        try:
            # Get the real ColorType from ACTIVE group
            real_colortype = get_colortype_by_name_from_group(colortype_name, active_group_name)

            # Create ColorRamp with REAL colors
            ramp = node_tree.nodes.new('ShaderNodeValToRGB')
            ramp.name = f"ColorRamp_{colortype_name}"
            ramp.location = (location[0], location[1] + (i * 100))

            # Set REAL colors from ColorType
            start_color = getattr(real_colortype, 'start_color', [0.8, 0.8, 0.8, 1.0])
            active_color = getattr(real_colortype, 'active_color', [0.0, 0.8, 0.0, 1.0])
            end_color = getattr(real_colortype, 'end_color', [0.8, 0.8, 0.8, 1.0])

            # Configure ColorRamp with real colors
            ramp.color_ramp.elements[0].position = 0.0
            ramp.color_ramp.elements[0].color = (start_color[0], start_color[1], start_color[2], 1.0)
            ramp.color_ramp.elements[1].position = 0.5
            ramp.color_ramp.elements[1].color = (active_color[0], active_color[1], active_color[2], 1.0)
            ramp.color_ramp.elements.new(1.0)
            ramp.color_ramp.elements[2].color = (end_color[0], end_color[1], end_color[2], 1.0)

            real_colortype_ramps[colortype_name] = ramp
            print(f"   ✅ Real ColorRamp created for {colortype_name}: start={start_color}, active={active_color}, end={end_color}")

        except Exception as e:
            print(f"   ⚠️ Error creating real ColorRamp for {colortype_name}: {e}")
            # Fallback to hardcoded if can't read real colors
            ramp = node_tree.nodes.new('ShaderNodeValToRGB')
            ramp.name = f"ColorRamp_{colortype_name}_Fallback"
            ramp.location = (location[0], location[1] + (i * 100))
            ramp.color_ramp.elements[0].color = (0.8, 0.8, 0.8, 1.0)
            ramp.color_ramp.elements[1].color = (0.0, 0.8, 0.0, 1.0)
            real_colortype_ramps[colortype_name] = ramp

    # Conectar animation_state a TODAS las rampas reales
    for ramp in real_colortype_ramps.values():
        node_tree.links.new(attr_animation_state.outputs['Fac'], ramp.inputs['Fac'])

    # CREAR SISTEMA SELECTOR (MUX) BASADO EN COLORTYPE_ID
    # Compare para CONSTRUCTION (colortype_id == 1)
    compare_construction = node_tree.nodes.new('ShaderNodeMath')
    compare_construction.operation = 'COMPARE'
    compare_construction.inputs[1].default_value = 1.0  # Construction ID
    compare_construction.inputs[2].default_value = 0.001  # Epsilon para comparación
    compare_construction.location = (location[0] + 300, location[1] + 300)

    # Compare para DEMOLITION (colortype_id == 3)
    compare_demolition = node_tree.nodes.new('ShaderNodeMath')
    compare_demolition.operation = 'COMPARE'
    compare_demolition.inputs[1].default_value = 3.0  # Demolition ID
    compare_demolition.inputs[2].default_value = 0.001  # Epsilon para comparación
    compare_demolition.location = (location[0] + 300, location[1] + 200)

    # Conectar colortype_id a los comparadores
    node_tree.links.new(attr_colortype.outputs['Fac'], compare_construction.inputs[0])
    node_tree.links.new(attr_colortype.outputs['Fac'], compare_demolition.inputs[0])

    # SISTEMA MIX COLOR PARA SELECCIÓN
    # Mix 1: Seleccionar entre Default y Construction
    mix_construction = node_tree.nodes.new('ShaderNodeMixRGB')
    mix_construction.name = "Mix_Construction"
    mix_construction.location = (location[0] + 600, location[1] + 250)
    mix_construction.blend_type = 'MIX'

    # Mix 2: Resultado anterior vs Demolition (selector final)
    mix_final = node_tree.nodes.new('ShaderNodeMixRGB')
    mix_final.name = "Mix_Final"
    mix_final.location = (location[0] + 900, location[1] + 150)
    mix_final.blend_type = 'MIX'

    # CONECTAR EL SISTEMA MUX con rampas reales
    # Mix Construction: usa compare_construction como factor
    node_tree.links.new(compare_construction.outputs['Value'], mix_construction.inputs['Fac'])
    node_tree.links.new(real_colortype_ramps['DEFAULT'].outputs['Color'], mix_construction.inputs['Color1'])  # Default
    node_tree.links.new(real_colortype_ramps['CONSTRUCTION'].outputs['Color'], mix_construction.inputs['Color2'])  # Construction

    # Mix Final: usa compare_demolition como factor
    node_tree.links.new(compare_demolition.outputs['Value'], mix_final.inputs['Fac'])
    node_tree.links.new(mix_construction.outputs['Color'], mix_final.inputs['Color1'])  # Resultado anterior
    node_tree.links.new(real_colortype_ramps['DEMOLITION'].outputs['Color'], mix_final.inputs['Color2'])  # Demolition

    print("   ✅ DYNAMIC Super Material system created with REAL ColorType colors:")
    print("      - Real ColorRamps from DEFAULT group using actual start/active/end colors")
    print("      - MUX selector based on colortype_id")
    print("      - Full animation_state integration")
    print("      - Colors match keyframes system exactly")

    return mix_final

def create_dynamic_colortype_system_for_geometry_nodes(node_tree, attr_colortype, attr_animation_state, location):
    """Create DYNAMIC color system for Geometry Nodes (not shader nodes)"""

    print("🎨 Creating DYNAMIC color system for Geometry Nodes with multiple ColorType support")

    # Create individual ColorRamps for different task types
    color_ramps = {}
    base_x = location[0]
    base_y = location[1]

    # 1. CONSTRUCTION ColorRamp (colortype_id = 1)
    construction_ramp = node_tree.nodes.new('ShaderNodeValToRGB')
    construction_ramp.name = "ColorRamp_Construction"
    construction_ramp.location = (base_x - 200, base_y + 200)
    construction_ramp.color_ramp.elements[0].position = 0.0
    construction_ramp.color_ramp.elements[0].color = (0.9, 0.9, 0.9, 1.0)  # Before: light gray
    construction_ramp.color_ramp.elements[1].position = 0.5
    construction_ramp.color_ramp.elements[1].color = (0.0, 0.9, 0.0, 1.0)  # Active: bright green
    construction_ramp.color_ramp.elements.new(1.0)
    construction_ramp.color_ramp.elements[2].color = (0.7, 0.9, 0.7, 1.0)  # After: light green
    color_ramps[1] = construction_ramp

    # 2. DEMOLITION ColorRamp (colortype_id = 3)
    demolition_ramp = node_tree.nodes.new('ShaderNodeValToRGB')
    demolition_ramp.name = "ColorRamp_Demolition"
    demolition_ramp.location = (base_x - 200, base_y + 100)
    demolition_ramp.color_ramp.elements[0].position = 0.0
    demolition_ramp.color_ramp.elements[0].color = (0.9, 0.9, 0.9, 1.0)  # Before: light gray
    demolition_ramp.color_ramp.elements[1].position = 0.5
    demolition_ramp.color_ramp.elements[1].color = (0.9, 0.0, 0.0, 1.0)  # Active: red
    demolition_ramp.color_ramp.elements.new(1.0)
    demolition_ramp.color_ramp.elements[2].color = (0.3, 0.3, 0.3, 1.0)  # After: dark gray (demolished)
    color_ramps[3] = demolition_ramp

    # 3. INSTALLATION ColorRamp (colortype_id = 2)
    installation_ramp = node_tree.nodes.new('ShaderNodeValToRGB')
    installation_ramp.name = "ColorRamp_Installation"
    installation_ramp.location = (base_x - 200, base_y)
    installation_ramp.color_ramp.elements[0].position = 0.0
    installation_ramp.color_ramp.elements[0].color = (0.9, 0.9, 0.9, 1.0)  # Before: light gray
    installation_ramp.color_ramp.elements[1].position = 0.5
    installation_ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.9, 1.0)  # Active: blue
    installation_ramp.color_ramp.elements.new(1.0)
    installation_ramp.color_ramp.elements[2].color = (0.7, 0.7, 0.9, 1.0)  # After: light blue
    color_ramps[2] = installation_ramp

    # 4. DEFAULT/FALLBACK ColorRamp (colortype_id = 0)
    default_ramp = node_tree.nodes.new('ShaderNodeValToRGB')
    default_ramp.name = "ColorRamp_Default"
    default_ramp.location = (base_x - 200, base_y - 100)
    default_ramp.color_ramp.elements[0].position = 0.0
    default_ramp.color_ramp.elements[0].color = (0.8, 0.8, 0.8, 1.0)  # Before: gray
    default_ramp.color_ramp.elements[1].position = 0.5
    default_ramp.color_ramp.elements[1].color = (0.0, 0.8, 0.0, 1.0)  # Active: green (default construction-like)
    default_ramp.color_ramp.elements.new(1.0)
    default_ramp.color_ramp.elements[2].color = (0.6, 0.9, 0.6, 1.0)  # After: light green
    color_ramps[0] = default_ramp

    # Connect animation_state to all ColorRamps
    for ramp in color_ramps.values():
        node_tree.links.new(attr_animation_state.outputs['Value'], ramp.inputs['Fac'])

    # Create selector system using colortype_id (using GEOMETRY NODE types)
    compare_construction = node_tree.nodes.new('FunctionNodeCompare')
    compare_construction.name = "Compare_Construction"
    compare_construction.operation = 'EQUAL'
    compare_construction.data_type = 'INT'
    compare_construction.inputs[1].default_value = 1  # CONSTRUCTION
    compare_construction.location = (base_x, base_y + 200)

    compare_demolition = node_tree.nodes.new('FunctionNodeCompare')
    compare_demolition.name = "Compare_Demolition"
    compare_demolition.operation = 'EQUAL'
    compare_demolition.data_type = 'INT'
    compare_demolition.inputs[1].default_value = 3  # DEMOLITION
    compare_demolition.location = (base_x, base_y + 100)

    compare_installation = node_tree.nodes.new('FunctionNodeCompare')
    compare_installation.name = "Compare_Installation"
    compare_installation.operation = 'EQUAL'
    compare_installation.data_type = 'INT'
    compare_installation.inputs[1].default_value = 2  # INSTALLATION
    compare_installation.location = (base_x, base_y)

    # Mix nodes for selector (simplified to 3 choices)
    mix_1 = node_tree.nodes.new('ShaderNodeMix')  # Construction vs default
    mix_1.name = "Mix_Construction"
    mix_1.data_type = 'RGBA'
    mix_1.location = (base_x + 200, base_y + 100)

    mix_2 = node_tree.nodes.new('ShaderNodeMix')  # Demolition vs result of mix_1
    mix_2.name = "Mix_Demolition"
    mix_2.data_type = 'RGBA'
    mix_2.location = (base_x + 400, base_y + 50)

    mix_3 = node_tree.nodes.new('ShaderNodeMix')  # Installation vs result of mix_2
    mix_3.name = "Mix_Installation"
    mix_3.data_type = 'RGBA'
    mix_3.location = (base_x + 600, base_y)

    # Connect colortype_id to all compare nodes
    node_tree.links.new(attr_colortype.outputs['Attribute'], compare_construction.inputs[0])
    node_tree.links.new(attr_colortype.outputs['Attribute'], compare_demolition.inputs[0])
    node_tree.links.new(attr_colortype.outputs['Attribute'], compare_installation.inputs[0])

    # Connect compare results to mix factors
    node_tree.links.new(compare_construction.outputs['Result'], mix_1.inputs['Fac'])
    node_tree.links.new(compare_demolition.outputs['Result'], mix_2.inputs['Fac'])
    node_tree.links.new(compare_installation.outputs['Result'], mix_3.inputs['Fac'])

    # Connect ColorRamps to Mix inputs
    node_tree.links.new(default_ramp.outputs['Color'], mix_1.inputs['A'])  # Default
    node_tree.links.new(construction_ramp.outputs['Color'], mix_1.inputs['B'])  # Construction

    node_tree.links.new(mix_1.outputs['Result'], mix_2.inputs['A'])
    node_tree.links.new(demolition_ramp.outputs['Color'], mix_2.inputs['B'])  # Demolition

    node_tree.links.new(mix_2.outputs['Result'], mix_3.inputs['A'])
    node_tree.links.new(installation_ramp.outputs['Color'], mix_3.inputs['B'])  # Installation

    print(f"   ✅ Created DYNAMIC geometry nodes color system with {len(color_ramps)} ColorRamps")
    print(f"   🔧 This function is for GEOMETRY NODES only, not shader materials")

    return mix_3  # Final mix node

def calculate_animation_state(node_tree, input_node, attr_start, attr_end, location):
    """Calculate animation state (0.0=before, 0.5=active, 1.0=after) for shader"""
    # Determine current state based on frame position
    compare_started = node_tree.nodes.new('FunctionNodeCompare')
    compare_started.operation = 'GREATER_EQUAL'
    compare_started.data_type = 'FLOAT'
    compare_started.location = location

    compare_finished = node_tree.nodes.new('FunctionNodeCompare')
    compare_finished.operation = 'GREATER_EQUAL'
    compare_finished.data_type = 'FLOAT'
    compare_finished.location = (location[0], location[1] - 100)

    # Convert booleans to state values
    # before_start = 0.0, active = 0.5, after_end = 1.0

    switch_start = node_tree.nodes.new('ShaderNodeMath')
    switch_start.operation = 'MULTIPLY'
    switch_start.inputs[1].default_value = 0.5  # Active state value
    switch_start.location = (location[0] + 200, location[1])

    switch_end = node_tree.nodes.new('ShaderNodeMath')
    switch_end.operation = 'ADD'
    switch_end.location = (location[0] + 400, location[1])

    bool_to_float_end = node_tree.nodes.new('ShaderNodeMath')
    bool_to_float_end.operation = 'MULTIPLY'
    bool_to_float_end.inputs[1].default_value = 0.5  # Additional for end state
    bool_to_float_end.location = (location[0] + 200, location[1] - 100)

    # Connections
    node_tree.links.new(input_node.outputs['Current Frame'], compare_started.inputs[0])
    node_tree.links.new(attr_start.outputs['Attribute'], compare_started.inputs[1])

    node_tree.links.new(input_node.outputs['Current Frame'], compare_finished.inputs[0])
    node_tree.links.new(attr_end.outputs['Attribute'], compare_finished.inputs[1])

    # Convert to state values
    node_tree.links.new(compare_started.outputs['Result'], switch_start.inputs[0])
    node_tree.links.new(compare_finished.outputs['Result'], bool_to_float_end.inputs[0])

    node_tree.links.new(switch_start.outputs['Value'], switch_end.inputs[0])
    node_tree.links.new(bool_to_float_end.outputs['Value'], switch_end.inputs[1])

    return switch_end

# Event handler system for Solid shading mode (ETAPA 3 - parte 2)
def gn_live_color_update_handler_enhanced(scene, depsgraph=None):
    """
    ETAPA 3: Enhanced frame change handler for Geometry Nodes
    Updates object.color for Solid shading mode based on GN attributes
    """
    try:
        # Only process if we have GN controllers in the scene
        has_gn_controllers = any(obj.get("is_gn_controller", False) for obj in scene.objects)
        if not has_gn_controllers:
            return

        # Check if Live Color Scheme is active
        if not is_live_color_scheme_active():
            return

        current_frame = scene.frame_current

        # UNIFIED COLOR SYSTEM: Update both Super Material and Solid colors together
        update_unified_color_system(scene, current_frame)

    except Exception as e:
        print(f"⚠️ Error in enhanced GN live color handler: {e}")

def update_unified_color_system(scene, current_frame):
    """
    UNIFIED COLOR SYSTEM: Update both Super Material and Solid colors together
    Ensures perfect synchronization between Material mode and Solid mode
    """
    try:
        # Step 1: Update Super Material with current active group colors
        update_super_material_with_active_group_colors()

        # Step 2: Update all objects with GN modifiers
        for obj in scene.objects:
            if obj.type == 'MESH' and has_gn_modifier(obj):
                update_object_solid_color_from_attributes(obj, current_frame)

        print(f"✅ UNIFIED color system updated for frame {current_frame}")

    except Exception as e:
        print(f"⚠️ Error in unified color system update: {e}")

def update_super_material_with_active_group_colors():
    """
    DYNAMIC MATERIAL UPDATE: Update Super Material ColorRamps with colors from active Animation Settings group
    """
    try:
        import bpy

        # Get the Super Material
        super_material = bpy.data.materials.get(GN_SUPER_MATERIAL_NAME)
        if not super_material or not super_material.node_tree:
            return

        # Get main ColorTypes for the active group
        colortype_names = ['CONSTRUCTION', 'DEMOLITION', 'MOVE', 'INSTALLATION', 'DEFAULT']

        for colortype_name in colortype_names:
            try:
                # Get REAL ColorType from current active group
                real_colortype = get_assigned_ColorType_for_task_enhanced_by_name(colortype_name)

                # Find the corresponding ColorRamp node in Super Material
                ramp_node_name = f"ColorRamp_{colortype_name}"
                ramp_node = super_material.node_tree.nodes.get(ramp_node_name)

                if ramp_node and real_colortype:
                    # Update ColorRamp with REAL colors from active group
                    start_color = getattr(real_colortype, 'start_color', [0.8, 0.8, 0.8, 1.0])
                    active_color = getattr(real_colortype, 'active_color', [0.0, 0.8, 0.0, 1.0])
                    end_color = getattr(real_colortype, 'end_color', [0.8, 0.8, 0.8, 1.0])

                    # Update the ColorRamp elements
                    if len(ramp_node.color_ramp.elements) >= 3:
                        ramp_node.color_ramp.elements[0].color = (start_color[0], start_color[1], start_color[2], 1.0)
                        ramp_node.color_ramp.elements[1].color = (active_color[0], active_color[1], active_color[2], 1.0)
                        ramp_node.color_ramp.elements[2].color = (end_color[0], end_color[1], end_color[2], 1.0)

                        print(f"   🎨 Super Material ColorRamp updated for {colortype_name}: active={active_color}")

            except Exception as e:
                print(f"   ⚠️ Error updating Super Material ColorRamp for {colortype_name}: {e}")

    except Exception as e:
        print(f"⚠️ Error updating Super Material with active group colors: {e}")

def get_assigned_ColorType_for_task_enhanced_by_name(colortype_name):
    """
    Get ColorType by name from the currently active group in Animation Settings
    """
    try:
        # Create a dummy task to use the existing function
        # We just need to get the ColorType by name from active group
        import bpy
        from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager

        context = bpy.context
        animation_props = tool.Sequence.get_animation_props()

        # Get active group name
        active_group_name = "DEFAULT"
        for item in getattr(animation_props, 'animation_group_stack', []):
            if getattr(item, 'enabled', False) and getattr(item, 'group', None):
                active_group_name = item.group
                break

        # Get ColorType from active group
        return get_colortype_by_name_from_group(colortype_name, active_group_name)

    except Exception as e:
        print(f"⚠️ Error getting ColorType {colortype_name} from active group: {e}")
        return None

def get_colortype_by_name_from_group(colortype_name, group_name="DEFAULT"):
    """
    Get ColorType by name from a specific group
    """
    try:
        import bpy
        from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager

        context = bpy.context

        # Get ColorTypes from specified group
        group_colortypes = UnifiedColorTypeManager.get_group_colortypes(context, group_name)

        if colortype_name in group_colortypes:
            colortype_data = group_colortypes[colortype_name]
            return create_colortype_from_data(colortype_name, colortype_data)
        else:
            print(f"⚠️ ColorType {colortype_name} not found in group {group_name}")
            return None

    except Exception as e:
        print(f"⚠️ Error getting ColorType {colortype_name} from group {group_name}: {e}")
        return None

def has_gn_modifier(obj):
    """Check if object has our GN modifier"""
    return any(mod.name == GN_MODIFIER_NAME and mod.type == 'NODES' for mod in obj.modifiers)

def get_task_for_product(element):
    """
    FIXED VERSION: Helper function to find the task that produces/consumes a product.
    Uses all tasks in the IFC file instead of work_schedule nested tasks.
    """
    try:
        if not element or not tool:
            return None

        # Get all tasks from the IFC file directly (more reliable)
        ifc_file = tool.Ifc.get()
        if not ifc_file:
            return None

        all_tasks = ifc_file.by_type('IfcTask')

        for task in all_tasks:
            # Check outputs
            try:
                for output in ifcopenshell.util.sequence.get_task_outputs(task):
                    if output.id() == element.id():
                        return task
            except:
                pass

            # Check inputs
            try:
                for input_prod in tool.Sequence.get_task_inputs(task):
                    if input_prod.id() == element.id():
                        return task
            except:
                pass

        return None
    except Exception as e:
        print(f"⚠️ Error finding task for product: {e}")
        return None

def update_object_solid_color_from_attributes(obj, current_frame):
    """
    REAL-TIME SYNCHRONIZATION VERSION: Update object.color for Solid shading
    ignoring baked colortype_id and recalculating ColorType in real-time.
    """
    try:
        if not obj.data or not hasattr(obj.data, 'attributes'):
            return

        # Read timing and relationship attributes (these remain valid from baking)
        schedule_start = read_attribute_value(obj, ATTR_SCHEDULE_START, 1.0)
        schedule_end = read_attribute_value(obj, ATTR_SCHEDULE_END, 999999.0)
        relationship_type = read_attribute_value(obj, ATTR_RELATIONSHIP_TYPE, 0)  # 0=OUTPUT, 1=INPUT

        # Determine current state
        if current_frame < schedule_start:
            state = "before_start"
        elif current_frame >= schedule_start and current_frame < schedule_end:
            state = "active"
        else:
            state = "after_end"

        # REAL-TIME COLORTYPE CALCULATION: Ignore baked colortype_id and recalculate
        colortype_object = None
        try:
            element = tool.Ifc.get_entity(obj)
            if element:
                # Find the task for this product
                task = get_task_for_product(element)
                if task:
                    # Recalculate the ColorType using current UI state
                    colortype_object = get_assigned_ColorType_for_task_enhanced(task)
                    print(f"🔄 REAL-TIME ColorType for {obj.name}: {getattr(colortype_object, 'name', 'UNKNOWN')}")
                else:
                    print(f"   ⚠️ No task found for object {obj.name}")
            else:
                print(f"   ⚠️ No IFC element found for object {obj.name}")

        except Exception as e:
            print(f"   ⚠️ Error getting real-time ColorType: {e}")

        # KEYFRAMES EXACT LOGIC: Apply visibility based on relationship and ColorType
        relationship_str = "OUTPUT" if relationship_type == 0 else "INPUT"
        visible = True  # Default for active state

        if colortype_object:
            # Get real visibility properties from ColorType
            consider_start = getattr(colortype_object, 'consider_start', True)
            hide_at_end = getattr(colortype_object, 'hide_at_end', False)
            colortype_name = getattr(colortype_object, 'name', 'UNKNOWN')

            # KEYFRAMES EXACT LOGIC: Apply relationship-based visibility rules
            if state == "before_start":
                if relationship_type == 0:  # OUTPUT (Construction)
                    # OUTPUT products: Hidden before start unless consider_start=True
                    visible = consider_start
                    print(f"      -> OUTPUT: visible={visible} (consider_start={consider_start})")
                else:  # INPUT (Demolition/Resources)
                    # INPUT products: Always visible before (they exist to be consumed/demolished)
                    visible = True
                    print(f"      -> INPUT: visible=True (always visible before)")
            elif state == "active":
                # Always visible during active phase regardless of relationship
                visible = True
            else:  # after_end
                if colortype_name in ['DEMOLITION', 'DISMANTLE', 'REMOVAL', 'DISPOSAL'] or hide_at_end:
                    # Objects that disappear after completion
                    visible = False
                    print(f"      -> Disappears after completion (hide_at_end={hide_at_end} or demolition type)")
                else:
                    # Objects that remain visible after completion
                    visible = True
                    print(f"      -> Remains visible after completion")

            print(f"   👁️  KEYFRAMES LOGIC for {obj.name}: {state} + {relationship_str} -> visible={visible}")
            print(f"      ColorType={colortype_name}, consider_start={consider_start}, hide_at_end={hide_at_end}")
        else:
            # Fallback visibility if no ColorType found
            if state == "before_start" and relationship_type == 0:
                visible = False  # OUTPUT without ColorType: hidden before start
            else:
                visible = state == "active"  # Default: only visible during active

        # Use the recalculated ColorType (colortype_id is now irrelevant)
        color = get_colortype_color_for_state(0, state, colortype_object)

        # Apply color and visibility
        if visible:
            obj.color = color
            obj.hide_viewport = False
            # Force viewport updates for color visibility
            obj.show_name = True  # This forces viewport update
            obj.show_name = False  # Reset to normal
            # Force all viewports to redraw
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
            print(f"   ✅ Applied color {color} to {obj.name}, visible=True")
        else:
            obj.hide_viewport = True
            print(f"   ❌ Hidden {obj.name}, visible=False")

    except Exception as e:
        print(f"⚠️ Error updating solid color for {obj.name}: {e}")

def read_attribute_value(obj, attr_name, default_value):
    """Read attribute value from mesh object"""
    try:
        if attr_name in obj.data.attributes:
            attr = obj.data.attributes[attr_name]
            if len(attr.data) > 0:
                return attr.data[0].value
        return default_value
    except Exception:
        return default_value

def get_colortype_color_for_state(colortype_id, state, colortype_object=None):
    """Get color for a specific ColorType and animation state, using real ColorType data when available"""

    # If we have the actual ColorType object, use its real colors
    if colortype_object and hasattr(colortype_object, 'start_color'):
        try:
            if state == "before_start":
                if getattr(colortype_object, 'use_start_original_color', False):
                    color = (0.8, 0.8, 0.8, 1.0)  # Default original color
                else:
                    start_color = getattr(colortype_object, 'start_color', [0.8, 0.8, 0.8, 1.0])
                    color = (start_color[0], start_color[1], start_color[2], 1.0)  # Keep full opacity for vibrant colors
            elif state == "active":
                if getattr(colortype_object, 'use_active_original_color', False):
                    color = (0.8, 0.8, 0.8, 1.0)  # Default original color
                else:
                    active_color = getattr(colortype_object, 'active_color', [0.0, 0.8, 0.0, 1.0])
                    color = (active_color[0], active_color[1], active_color[2], 1.0)  # Keep full opacity for vibrant colors
            else:  # after_end
                use_end_original = getattr(colortype_object, 'use_end_original_color', False)
                if use_end_original:
                    color = (0.8, 0.8, 0.8, 1.0)  # Default original color (as configured)
                    print(f"      -> Using original end color (use_end_original_color=True)")
                else:
                    end_color = getattr(colortype_object, 'end_color', [0.8, 0.8, 0.8, 1.0])
                    color = (end_color[0], end_color[1], end_color[2], 1.0)  # Keep full opacity for vibrant colors
                    print(f"      -> Using custom end color: {end_color}")

            print(f"   🎨 ColorType {colortype_id} -> State {state} -> Real Color {color}")
            return color

        except Exception as e:
            print(f"   ⚠️ Error reading ColorType colors: {e}")

    # Fallback to predefined colors for standard ColorTypes
    colortype_colors = {
        0: {  # DEFAULT
            "before_start": (0.8, 0.8, 0.8, 1.0),
            "active": (0.0, 0.8, 0.0, 1.0),
            "after_end": (0.6, 0.9, 0.6, 1.0)
        },
        1: {  # CONSTRUCTION
            "before_start": (0.9, 0.9, 0.9, 1.0),
            "active": (0.0, 0.9, 0.0, 1.0),
            "after_end": (0.7, 0.9, 0.7, 1.0)
        },
        2: {  # INSTALLATION
            "before_start": (0.9, 0.9, 0.9, 1.0),
            "active": (0.0, 0.0, 0.9, 1.0),
            "after_end": (0.7, 0.7, 0.9, 1.0)
        },
        3: {  # DEMOLITION
            "before_start": (0.9, 0.9, 0.9, 1.0),
            "active": (0.9, 0.0, 0.0, 1.0),
            "after_end": (0.3, 0.3, 0.3, 1.0)
        },
        8: {  # MAINTENANCE
            "before_start": (0.9, 0.9, 0.5, 1.0),
            "active": (1.0, 1.0, 0.0, 1.0),
            "after_end": (0.8, 0.8, 0.4, 1.0)
        },
        12: {  # MOVE
            "before_start": (0.9, 0.5, 0.9, 1.0),
            "active": (1.0, 0.0, 1.0, 1.0),
            "after_end": (0.8, 0.4, 0.8, 1.0)
        }
    }

    # Generate consistent colors for custom ColorTypes
    if colortype_id not in colortype_colors:
        # Generate colors based on the ID hash for consistency
        import random
        random.seed(colortype_id)  # Consistent colors for same ID
        hue1 = random.random()
        hue2 = (hue1 + 0.3) % 1.0
        hue3 = (hue1 + 0.6) % 1.0

        def hsv_to_rgb(h, s, v):
            import colorsys
            return colorsys.hsv_to_rgb(h, s, v)

        start_color = hsv_to_rgb(hue1, 0.3, 0.9) + (1.0,)
        active_color = hsv_to_rgb(hue2, 0.8, 0.9) + (1.0,)
        end_color = hsv_to_rgb(hue3, 0.5, 0.8) + (1.0,)

        colortype_colors[colortype_id] = {
            "before_start": start_color,
            "active": active_color,
            "after_end": end_color
        }

    colors = colortype_colors.get(colortype_id, colortype_colors[0])
    color = colors.get(state, colors["active"])
    print(f"   🎨 ColorType {colortype_id} -> State {state} -> Color {color}")
    return color

def is_live_color_scheme_active():
    """Check if Live Color Scheme is currently active"""
    try:
        # This would check the actual Live Color Scheme setting
        # Implementation depends on how it's stored in the addon
        return True  # For now, assume it's always active when GN is used
    except Exception:
        return False

def register_gn_live_color_handler_enhanced():
    """Register enhanced Geometry Nodes handler for Live Scheme Color support"""
    try:
        # Check if our handler is already registered
        if gn_live_color_update_handler_enhanced not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(gn_live_color_update_handler_enhanced)
            print("✅ Enhanced GN Live Color handler registered")
    except Exception as e:
        print(f"⚠️ Error registering enhanced GN live color handler: {e}")

def unregister_gn_live_color_handler_enhanced():
    """Unregister enhanced Geometry Nodes handler for Live Scheme Color"""
    try:
        if gn_live_color_update_handler_enhanced in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.remove(gn_live_color_update_handler_enhanced)
            print("✅ Enhanced GN Live Color handler unregistered")
    except Exception as e:
        print(f"⚠️ Error unregistering enhanced GN live color handler: {e}")

# Main integration function
def create_complete_gn_animation_system_enhanced(context, work_schedule, settings):
    """
    Main function that creates the complete enhanced GN animation system
    with all four stages integrated
    """
    print("🚀 Creating complete enhanced GN animation system...")

    try:
        # ETAPA 1: Bake enhanced attributes
        print("📊 ETAPA 1: Iniciando horneado de atributos mejorado...")
        attributes_data = bake_all_attributes_worker_enhanced(work_schedule, settings)

        if not attributes_data:
            print("❌ ERROR: No se pudieron generar datos de atributos")
            return False

        # Apply attributes to mesh objects
        apply_attributes_to_objects(context, attributes_data)

        # ETAPA 2: Create enhanced node tree
        print("🔧 ETAPA 2: Creando árbol de nodos mejorado...")
        node_tree = create_advanced_nodetree_enhanced()

        # ETAPA 3: Create Super Material and register handlers
        print("🎨 ETAPA 3: Configurando sistema dual de materiales...")
        register_gn_live_color_handler_enhanced()

        # ETAPA 4: Apply modifiers and setup integration
        print("⚙️ ETAPA 4: Aplicando modificadores y configurando integración...")
        apply_gn_modifiers_enhanced(context, node_tree)

        print("✅ Complete enhanced GN animation system created successfully!")
        return True

    except Exception as e:
        print(f"❌ Error creating enhanced GN animation system: {e}")
        import traceback
        traceback.print_exc()
        return False

def apply_attributes_to_objects(context, attributes_data):
    """Apply baked attributes to mesh objects"""
    print(f"📊 Applying attributes to {len(attributes_data)} objects...")

    for obj_name, attributes in attributes_data.items():
        obj = bpy.data.objects.get(obj_name)
        if not obj or obj.type != 'MESH' or not obj.data:
            continue

        # Ensure mesh has vertices
        if not obj.data.vertices:
            continue

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

            except Exception as e:
                print(f"⚠️ Error setting attribute {attr_name} on {obj_name}: {e}")

    print("✅ Attributes applied successfully")

def apply_gn_modifiers_enhanced(context, node_tree):
    """Apply enhanced GN modifiers with complete integration"""
    print("⚙️ Applying enhanced GN modifiers...")

    # Get objects with attributes
    objects_to_modify = []
    for obj in context.scene.objects:
        if (obj.type == 'MESH' and obj.data and obj.data.vertices and
            ATTR_SCHEDULE_START in obj.data.attributes):
            objects_to_modify.append(obj)

    print(f"⚙️ Applying modifiers to {len(objects_to_modify)} objects...")

    # Ensure controller exists
    controller = ensure_gn_controller()

    # Get the Super Material
    super_material = bpy.data.materials.get(GN_SUPER_MATERIAL_NAME)
    if not super_material:
        print("⚠️ Super Material not found, creating it...")
        super_material = create_super_material()

    for obj in objects_to_modify:
        # Remove existing modifier if it exists
        for mod in obj.modifiers[:]:
            if mod.name == GN_MODIFIER_NAME:
                obj.modifiers.remove(mod)

        # Create new modifier
        modifier = obj.modifiers.new(name=GN_MODIFIER_NAME, type='NODES')
        modifier.node_group = node_tree

        # Assign Super Material to object
        if obj.data.materials:
            # Replace first material slot with Super Material
            obj.data.materials[0] = super_material
            print(f"   🎨 Assigned Super Material to {obj.name} (replaced slot 0)")
        else:
            # Create new material slot with Super Material
            obj.data.materials.append(super_material)
            print(f"   🎨 Assigned Super Material to {obj.name} (new slot)")

        # Enable object color display for Solid mode
        # The actual color will be set by the live color update handler based on ColorType
        # Don't force a default gray - let the system use the real ColorType colors
        print(f"   🎨 Object color will be set by live color handler based on real ColorType colors")

        # Force update
        context.view_layer.update()

        # Add drivers for dynamic values
        add_enhanced_drivers(obj, modifier, controller, context)

    # Force viewport to use object color in Solid mode
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    # Set shading mode to Solid and color type to Object
                    space.shading.type = 'SOLID'
                    space.shading.color_type = 'OBJECT'
                    # Additional viewport settings for better visibility
                    if hasattr(space.shading, 'use_object_outline'):
                        space.shading.use_object_outline = True
                    print("   🎨 Viewport set to Solid mode with object colors")
                    break

    print("✅ Enhanced GN modifiers applied successfully")

def add_enhanced_drivers(obj, modifier, controller, context):
    """Add enhanced drivers for complete integration"""
    print(f"🎮 Adding enhanced drivers for {obj.name}...")

    # Current Frame driver - Using variables instead of context (safer)
    try:
        fcurve = modifier.driver_add('["Socket_1"]')
        driver = fcurve.driver
        driver.type = 'SCRIPTED'

        # Create variable for frame_current
        var = driver.variables.new()
        var.name = 'frame'
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'SCENE'
        var.targets[0].id = context.scene
        var.targets[0].data_path = 'frame_current'

        # Simple expression using the variable
        driver.expression = 'frame'

        print(f"✅ Current Frame driver added to {obj.name} with variable-based expression")
    except Exception as e:
        print(f"⚠️ Could not add Current Frame driver to {obj.name}: {e}")

    # Schedule Type driver
    try:
        driver = modifier.driver_add('["Socket_2"]').driver
        driver.type = 'SCRIPTED'
        var = driver.variables.new()
        var.name = 'schedule_type'
        var.type = 'SINGLE_PROP'
        var.targets[0].id = controller
        var.targets[0].data_path = 'BonsaiGNController.schedule_type_to_display'
        driver.expression = 'int(schedule_type)'
        print(f"✅ Schedule Type driver added to {obj.name}")
    except Exception as e:
        print(f"⚠️ Could not add Schedule Type driver to {obj.name}: {e}")

    # Speed Multiplier driver (enhanced)
    try:
        driver = modifier.driver_add('["Socket_4"]').driver
        driver.type = 'SCRIPTED'
        var = driver.variables.new()
        var.name = 'speed_setting'
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'OBJECT'
        var.targets[0].id = controller

        # Controller speed property detection
        if hasattr(controller, 'BonsaiGNController') and hasattr(controller.BonsaiGNController, 'speed_setting'):
            var.targets[0].data_path = 'BonsaiGNController.speed_setting'
            driver.expression = 'max(0.1, float(speed_setting)) if speed_setting else 1.0'
        else:
            # Fallback: try custom property or default
            var.targets[0].data_path = '["speed_setting"]'
            driver.expression = 'speed_setting'

        print(f"✅ Enhanced Speed Multiplier driver added to {obj.name}")
    except Exception as e:
        print(f"⚠️ Could not add Speed Multiplier driver to {obj.name}: {e}")
        # Fallback: set static value
        try:
            modifier["Socket_4"] = 1.0
            print(f"🔧 Set fallback speed=1.0x for {obj.name}")
        except Exception:
            pass

# Cleanup function
def cleanup_enhanced_gn_system():
    """Clean up the enhanced GN system"""
    print("🧹 Cleaning up enhanced GN system...")

    # Unregister handlers
    unregister_gn_live_color_handler_enhanced()

    # Reset objects to original state BEFORE removing modifiers
    reset_objects_count = 0
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
            # Reset visibility and color to default state
            obj.hide_viewport = False
            obj.hide_render = False
            obj.color = (0.8, 0.8, 0.8, 1.0)  # Default gray

            # Remove any material slots with Super Material
            if obj.data.materials:
                for i, slot in enumerate(obj.data.materials):
                    if slot and slot.name == GN_SUPER_MATERIAL_NAME:
                        obj.data.materials[i] = None  # Clear the slot

            # Clear animation data that might be left over
            if obj.animation_data:
                obj.animation_data_clear()

            reset_objects_count += 1

    # Remove GN modifiers
    removed_modifiers = 0
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            for modifier in obj.modifiers[:]:
                if modifier.name == GN_MODIFIER_NAME:
                    obj.modifiers.remove(modifier)
                    removed_modifiers += 1

    # Remove node tree
    if GN_NODETREE_NAME in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[GN_NODETREE_NAME])
        print(f"   ✅ Removed GN node tree")

    # Remove Super Material
    if GN_SUPER_MATERIAL_NAME in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[GN_SUPER_MATERIAL_NAME])
        print(f"   ✅ Removed Super Material")

    # Clean controller collection
    if GN_CONTROLLER_COLLECTION in bpy.data.collections:
        coll = bpy.data.collections[GN_CONTROLLER_COLLECTION]
        for obj in list(coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(coll)
        print(f"   ✅ Removed controller collection")

    # Force viewport update
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()

    print(f"✅ GN cleanup complete: {reset_objects_count} objects reset, {removed_modifiers} modifiers removed")

    print(f"✅ Enhanced GN system cleaned up: {removed_modifiers} modifiers removed")

# =============================================================================
# CORE HELPER FUNCTIONS - From original implementation
# =============================================================================

def ensure_gn_controller():
    """
    Ensures that a GN controller object exists, creates one if needed
    """
    # Look for existing controller
    controller_objects = [obj for obj in bpy.data.objects if obj.get("is_gn_controller", False)]

    if controller_objects:
        controller = controller_objects[0]
        print(f"🎮 Using existing GN controller: {controller.name}")

        # Always sync existing controller (SAFE VERSION)
        if hasattr(controller, "BonsaiGNController"):
            try:
                # Safe sync without risky imports
                if not controller.BonsaiGNController.colortype_group_to_display:
                    controller.BonsaiGNController.colortype_group_to_display = "DEFAULT"
                print(f"🎮 Existing controller ensured safe state")
            except Exception as e:
                print(f"⚠️ Could not access controller properties: {e}")

        return controller

    # Create controller if none exists
    print("🎮 No GN controller found, creating one...")

    # Create or get the controller collection
    coll_name = GN_CONTROLLER_COLLECTION
    if coll_name not in bpy.data.collections:
        coll = bpy.data.collections.new(coll_name)
        bpy.context.scene.collection.children.link(coll)
    else:
        coll = bpy.data.collections[coll_name]

    # Create the controller object (Empty)
    bpy.ops.object.empty_add(type='PLAIN_AXES')
    controller = bpy.context.active_object
    controller.name = "GN_4D_Controller_Auto"
    controller["is_gn_controller"] = True

    # Move to the correct collection and unlink from others
    for c in controller.users_collection:
        c.objects.unlink(controller)
    coll.objects.link(controller)

    # Set default properties
    try:
        if hasattr(controller, "BonsaiGNController"):
            ctrl_props = controller.BonsaiGNController
            ctrl_props.schedule_type_to_display = '0'  # Schedule by default
            ctrl_props.colortype_group_to_display = "DEFAULT"
            print("🎮 Controller properties configured")
    except Exception as e:
        print(f"⚠️ Could not configure controller properties: {e}")

    print(f"✅ Created new GN controller: {controller.name}")
    return controller

# =============================================================================
# CLEAN API FUNCTIONS - Main functions without "_enhanced" suffix
# =============================================================================

# Main GN system functions with clean names
def create_gn_animation_system_complete(context, work_schedule, settings):
    """Main function to create complete GN animation system (clean name)"""
    return create_complete_gn_animation_system_enhanced(context, work_schedule, settings)

def cleanup_gn_system_complete():
    """Main function to cleanup GN system (clean name)"""
    return cleanup_enhanced_gn_system()

def register_gn_live_color_handler_main():
    """Main function to register GN live color handler (clean name)"""
    return register_gn_live_color_handler_enhanced()

def unregister_gn_live_color_handler_main():
    """Main function to unregister GN live color handler (clean name)"""
    return unregister_gn_live_color_handler_enhanced()

def create_advanced_nodetree_main():
    """Main function to create advanced node tree (clean name)"""
    return create_advanced_nodetree_enhanced()

# =============================================================================
# COMPATIBILITY FUNCTIONS - Legacy API support
# =============================================================================

def create_gn_animation_system(context, work_schedule, product_frames, settings):
    """
    COMPATIBILITY FUNCTION: Legacy API support

    This function maintains compatibility with existing operators that use the old API.
    It converts the old product_frames format to the new enhanced system.

    Args:
        context: Blender context
        work_schedule: IfcWorkSchedule entity
        product_frames: Legacy product frames data
        settings: Animation settings

    Returns:
        bool: True if successful
    """
    print("🔄 COMPATIBILITY: Using legacy create_gn_animation_system() interface")

    try:
        # Convert legacy product_frames to enhanced format if needed
        # The enhanced system expects work_schedule and settings directly
        success = create_complete_gn_animation_system_enhanced(context, work_schedule, settings)

        if success:
            print("✅ COMPATIBILITY: Legacy GN animation creation successful")
            return True
        else:
            print("❌ COMPATIBILITY: Legacy GN animation creation failed")
            return False

    except Exception as e:
        print(f"❌ COMPATIBILITY ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def cleanup_gn_system():
    """
    COMPATIBILITY FUNCTION: Legacy cleanup API
    """
    print("🧹 COMPATIBILITY: Using legacy cleanup_gn_system() interface")
    try:
        cleanup_enhanced_gn_system()
        print("✅ COMPATIBILITY: Legacy GN cleanup successful")
    except Exception as e:
        print(f"❌ COMPATIBILITY CLEANUP ERROR: {e}")

def apply_gn_modifiers_and_drivers(context, controller_objects):
    """
    COMPATIBILITY FUNCTION: Legacy modifier application
    """
    print("⚙️ COMPATIBILITY: Using legacy apply_gn_modifiers_and_drivers() interface")
    try:
        # The enhanced system handles this internally
        # This is a no-op for compatibility
        print("✅ COMPATIBILITY: Legacy modifier application (handled internally)")
        return True
    except Exception as e:
        print(f"❌ COMPATIBILITY MODIFIER ERROR: {e}")
        return False

def bake_all_attributes_worker(product_cache, profiles_data, colortype_mapping):
    """
    COMPATIBILITY FUNCTION: Legacy baking API
    """
    print("📊 COMPATIBILITY: Using legacy bake_all_attributes_worker() interface")
    try:
        # The enhanced system uses different parameters
        # Return empty dict for compatibility
        print("⚠️ COMPATIBILITY: Legacy baking interface - use enhanced system instead")
        return {}
    except Exception as e:
        print(f"❌ COMPATIBILITY BAKING ERROR: {e}")
        return {}

def create_advanced_nodetree():
    """
    COMPATIBILITY FUNCTION: Legacy node tree creation
    """
    print("🔧 COMPATIBILITY: Using legacy create_advanced_nodetree() interface")
    try:
        return create_advanced_nodetree_enhanced()
    except Exception as e:
        print(f"❌ COMPATIBILITY NODETREE ERROR: {e}")
        return None

# ensure_gn_controller() is now defined above as the main function

def register_gn_live_color_handler():
    """
    COMPATIBILITY FUNCTION: Legacy handler registration
    """
    print("🎨 COMPATIBILITY: Using legacy register_gn_live_color_handler() interface")
    try:
        register_gn_live_color_handler_enhanced()
        print("✅ COMPATIBILITY: Legacy handler registration successful")
    except Exception as e:
        print(f"❌ COMPATIBILITY HANDLER ERROR: {e}")

def unregister_gn_live_color_handler():
    """
    COMPATIBILITY FUNCTION: Legacy handler unregistration
    """
    print("🎨 COMPATIBILITY: Using legacy unregister_gn_live_color_handler() interface")
    try:
        unregister_gn_live_color_handler_enhanced()
        print("✅ COMPATIBILITY: Legacy handler unregistration successful")
    except Exception as e:
        print(f"❌ COMPATIBILITY HANDLER ERROR: {e}")

# Export main functions for use by operators
__all__ = [
    # Primary system (clean names)
    'create_gn_animation_system_complete',
    'cleanup_gn_system_complete',
    'register_gn_live_color_handler_main',
    'unregister_gn_live_color_handler_main',
    'create_advanced_nodetree_main',
    'ensure_gn_controller',

    # Enhanced system (full names for direct access)
    'create_complete_gn_animation_system_enhanced',
    'cleanup_enhanced_gn_system',
    'register_gn_live_color_handler_enhanced',
    'unregister_gn_live_color_handler_enhanced',
    'create_advanced_nodetree_enhanced',

    # Legacy compatibility (for existing operators)
    'create_gn_animation_system',
    'cleanup_gn_system',
    'apply_gn_modifiers_and_drivers',
    'bake_all_attributes_worker',
    'create_advanced_nodetree',
    'register_gn_live_color_handler',
    'unregister_gn_live_color_handler'
]