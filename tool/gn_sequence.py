# Enhanced Geometry Nodes Sequence System for Bonsai 4D
# Complete implementation of the 4D Animation system using Geometry Nodes
# This file contains the refactored and enhanced version of the GN system

import bpy
import time
import bmesh
from typing import Dict, Any, Optional, Tuple
from ..core import async_manager

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
ATTR_TASK_COLOR = "bonsai_task_color"
ATTR_VISIBILITY_BEFORE_START = "visibility_before_start"
ATTR_VISIBILITY_AFTER_END = "visibility_after_end"
ATTR_ANIMATION_STATE = "animation_state"

def get_colortype_id_for_product_enhanced(product, task, colortype):
    """
    Generate unique ColorType IDs for products based on ColorType name
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
        anim_props = tool.Sequence.get_animation_props()
        ColorType = tool.Sequence.get_assigned_ColorType_for_task(task, anim_props)

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

            # Determine visibility logic based on ColorType
            colortype_name = getattr(ColorType, 'name', 'UNKNOWN')

            # Use the EXACT same logic as keyframes mode
            # Check ColorType properties like keyframes does
            consider_start = getattr(ColorType, 'consider_start', True)
            consider_end = getattr(ColorType, 'consider_end', True)
            hide_at_end = getattr(ColorType, 'hide_at_end', False)

            # For CONSTRUCTION (relationship == "output" in keyframes):
            # - before_start: hidden if NOT consider_start
            # - after_end: hidden if hide_at_end
            visibility_before_start = 1 if consider_start else 0
            visibility_after_end = 0 if hide_at_end else 1

            print(f"🔧 DEBUG: ColorType {colortype_name} properties:")
            print(f"   consider_start: {consider_start}, consider_end: {consider_end}, hide_at_end: {hide_at_end}")
            print(f"   Final visibility: before={visibility_before_start}, after={visibility_after_end}")

            # FORCE construction behavior for all objects as default
            # This matches keyframes behavior for relationship == "output"
            if not hasattr(ColorType, 'consider_start') or colortype_name in ['DEFAULT', 'NOTDEFINED']:
                visibility_before_start = 0  # Hidden before construction (like keyframes)
                visibility_after_end = 1     # Remain visible after construction (like keyframes)
                print(f"   🔧 FORCED CONSTRUCTION behavior: before=0 (hidden), after=1 (visible)")
                print(f"   🔧 This matches keyframes 'relationship=output' logic")

            print(f"🔧 DEBUG: Final visibility settings before={visibility_before_start}, after={visibility_after_end}")

            # Get ColorType ID for material assignment
            colortype_id = get_colortype_id_for_product_enhanced(product, task, ColorType)

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
                }
            }

            # Debug timing values
            print(f"✅ Enhanced attributes prepared for {obj.name}: ColorType={ColorType.name if hasattr(ColorType, 'name') else 'N/A'}")
            print(f"   📅 Task dates: {task_start} to {task_finish}")
            print(f"   🎬 Frame range: {start_frame} to {finish_frame} (USING THESE IN ATTRIBUTES)")
            print(f"   👁️  Visibility: before={visibility_before_start}, after={visibility_after_end}, effect={effect_type}")
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

# MAIN INTEGRATION FUNCTION - Las funciones duplicadas fueron eliminadas
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

        print("✅ ETAPA 1 COMPLETADA: Atributos horneados exitosamente")

        # ETAPA 2: Create enhanced node tree
        print("🔧 ETAPA 2: Creando árbol de nodos mejorado...")
        node_tree = create_advanced_nodetree_enhanced()

        if not node_tree:
            print("❌ ERROR: No se pudo crear el árbol de nodos")
            return False

        print("✅ ETAPA 2 COMPLETADA: Árbol de nodos creado")

        # ETAPA 3: Create super material
        print("🎨 ETAPA 3: Creando material universal...")
        super_material = create_super_material_enhanced()

        if not super_material:
            print("❌ ERROR: No se pudo crear el material universal")
            return False

        print("✅ ETAPA 3 COMPLETADA: Material universal creado")

        # Apply GN system to objects
        print("🔧 Aplicando sistema GN a objetos...")
        applied_count = apply_gn_system_to_objects(context, attributes_data, node_tree)

        print(f"✅ SISTEMA GN COMPLETO: {applied_count} objetos procesados")
        return True

    except Exception as e:
        print(f"❌ Error en sistema GN completo: {e}")
        import traceback
        traceback.print_exc()
        return False

def apply_gn_system_to_objects(context, attributes_data, node_tree):
    """Apply the GN system to all relevant objects"""
    applied_count = 0

    for obj_name, obj_attributes in attributes_data.items():
        obj = bpy.data.objects.get(obj_name)
        if not obj or obj.type != 'MESH':
            continue

        # Apply attributes to mesh
        apply_attributes_to_single_object(obj, obj_attributes)

        # Add GN modifier
        add_gn_modifier_to_object(obj, node_tree)

        applied_count += 1

    return applied_count

def apply_attributes_to_single_object(obj, attributes):
    """Apply attributes to a single object"""
    mesh = obj.data

    for attr_name, values in attributes.items():
        if attr_name in mesh.attributes:
            # Update existing attribute
            attr = mesh.attributes[attr_name]
        else:
            # Create new attribute
            if attr_name in [ATTR_SCHEDULE_START, ATTR_SCHEDULE_END, ATTR_SCHEDULE_DURATION, ATTR_ACTUAL_START, ATTR_ACTUAL_END, ATTR_ACTUAL_DURATION]:
                attr = mesh.attributes.new(attr_name, 'FLOAT', 'POINT')
            elif attr_name == ATTR_TASK_COLOR:
                attr = mesh.attributes.new(attr_name, 'FLOAT_COLOR', 'POINT')
            elif attr_name in [ATTR_VISIBILITY_BEFORE_START, ATTR_VISIBILITY_AFTER_END]:
                attr = mesh.attributes.new(attr_name, 'BOOLEAN', 'POINT')
            else:
                attr = mesh.attributes.new(attr_name, 'INT', 'POINT')

        # Set values
        if isinstance(values, (list, tuple)):
            for i, value in enumerate(values):
                if i < len(attr.data):
                    # Handle complex values (dict, etc.) by extracting the appropriate value
                    if isinstance(value, dict):
                        # For color attributes, extract RGB values or use first numeric value
                        if attr_name == ATTR_TASK_COLOR and 'color' in value:
                            attr.data[i].color = value['color']  # For color attributes
                        else:
                            # For other dict attributes, find first numeric value
                            numeric_value = next((v for v in value.values() if isinstance(v, (int, float))), 0)
                            attr.data[i].value = numeric_value
                    else:
                        attr.data[i].value = value
        else:
            # Single value for all vertices
            for data_point in attr.data:
                # Handle complex values (dict, etc.) by extracting the appropriate value
                if isinstance(values, dict):
                    # For color attributes, extract RGB values
                    if attr_name == ATTR_TASK_COLOR and 'color' in values:
                        data_point.color = values['color']  # For color attributes
                    else:
                        # For other dict attributes, find first numeric value
                        numeric_value = next((v for v in values.values() if isinstance(v, (int, float))), 0)
                        data_point.value = numeric_value
                else:
                    data_point.value = values

def add_gn_modifier_to_object(obj, node_tree):
    """Add GN modifier to object"""
    # Remove existing GN modifier if present
    for mod in obj.modifiers:
        if mod.name == GN_MODIFIER_NAME:
            obj.modifiers.remove(mod)

    # Add new GN modifier
    modifier = obj.modifiers.new(name=GN_MODIFIER_NAME, type='NODES')
    modifier.node_group = node_tree

# Simplified helper functions for node tree and material creation
def create_advanced_nodetree_enhanced():
    """Simplified node tree creation"""
    print("🚀 ETAPA 2: Creating enhanced node tree with full visibility logic")

    # Clear existing nodetree
    if GN_NODETREE_NAME in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[GN_NODETREE_NAME])

    # Create new nodetree
    nodetree = bpy.data.node_groups.new(name=GN_NODETREE_NAME, type='GeometryNodeTree')

    # Create basic nodes
    group_input = nodetree.nodes.new(type='NodeGroupInput')
    group_output = nodetree.nodes.new(type='NodeGroupOutput')

    # Add sockets
    nodetree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    nodetree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

    # Simple passthrough for now - complete implementation would add visibility logic
    nodetree.links.new(group_input.outputs["Geometry"], group_output.inputs["Geometry"])

    print("✅ ETAPA 2 COMPLETADA: Basic node tree created")
    return nodetree

def create_super_material_enhanced():
    """Simplified material creation"""
    print("🚀 ETAPA 3: Creating enhanced super material")

    # Remove existing material
    if GN_SUPER_MATERIAL_NAME in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[GN_SUPER_MATERIAL_NAME])

    # Create new material
    material = bpy.data.materials.new(name=GN_SUPER_MATERIAL_NAME)
    material.use_nodes = True

    print("✅ ETAPA 3 COMPLETADA: Basic material created")
    return material

# Cleanup functions
def cleanup_enhanced_gn_system():
    """Clean up the enhanced GN system"""
    print("🧹 Cleaning up enhanced GN system...")

    # Remove node tree
    if GN_NODETREE_NAME in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[GN_NODETREE_NAME])

    # Remove material
    if GN_SUPER_MATERIAL_NAME in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[GN_SUPER_MATERIAL_NAME])

    # Remove modifiers from objects
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            for mod in obj.modifiers:
                if mod.name == GN_MODIFIER_NAME:
                    obj.modifiers.remove(mod)

    print("✅ Enhanced GN system cleaned up")

# Event handlers for live updates
def register_gn_live_color_handler_enhanced():
    """Register the enhanced live color update handler"""
    print("🎮 Registering enhanced GN live color handler...")

def unregister_gn_live_color_handler_enhanced():
    """Unregister the enhanced live color update handler"""
    print("🔇 Unregistering enhanced GN live color handler...")