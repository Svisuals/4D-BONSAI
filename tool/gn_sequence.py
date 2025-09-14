# EN: tool/sequence/gn_sequence.py
import bpy
import time
import bmesh
from typing import Dict, Any, Optional
from bonsai.bim.module.sequence.core import async_manager

# Import bonsai tool safely
try:
    import bonsai.tool as tool
except ImportError:
    try:
        # Try importing from alternative path
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
        import bonsai.tool as tool
    except ImportError:
        tool = None

# --- CONSTANTES ---
GN_MODIFIER_NAME = "Bonsai 4D"
GN_NODETREE_NAME = "Bonsai 4D Node Tree"
GN_CONTROLLER_COLLECTION = "GN_CONTROLLERS"
ATTR_SCHEDULE_START = "schedule_start"
ATTR_SCHEDULE_END = "schedule_end"
ATTR_SCHEDULE_DURATION = "schedule_duration"
ATTR_ACTUAL_START = "actual_start"
ATTR_ACTUAL_END = "actual_end"
ATTR_ACTUAL_DURATION = "actual_duration"
ATTR_EFFECT_TYPE = "effect_type"
ATTR_COLORTYPE_ID = "colortype_id"

def ensure_gn_controller():
    """
    Ensures that a GN controller object exists, creates one if needed
    """
    # Look for existing controller
    controller_objects = [obj for obj in bpy.data.objects if obj.get("is_gn_controller", False)]

    if controller_objects:
        print(f"🎮 Using existing GN controller: {controller_objects[0].name}")
        return controller_objects[0]

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

    # Set default properties if the properties exist
    if hasattr(controller, "BonsaiGNController"):
        ctrl_props = controller.BonsaiGNController
        ctrl_props.schedule_type_to_display = '0'  # Schedule by default

    print(f"✅ Created GN controller: {controller.name}")
    return controller

def bake_all_attributes_worker(product_cache, profiles_data, colortype_mapping):
    """
    OPTIMIZED: Función que procesa atributos en lotes para mejorar rendimiento
    con modelos grandes (8000+ objetos). NO USA BPY NI CONTEXT.
    """
    async_manager.update_progress(0, "Iniciando horneado optimizado de atributos...")

    # ⭐ CRUCIAL: Create ColorType materials FIRST (like keyframes but with materials)
    print("🎨 CREATING COLORTYPE MATERIALS for Geometry Nodes...")
    try:
        create_colortype_materials()
        print("✅ ColorType materials created successfully!")
    except Exception as e:
        print(f"⚠️ Warning: Could not create ColorType materials: {e}")
        # Continue anyway - materials might already exist

    attributes_to_set = {}
    date_mapping = {
        ATTR_SCHEDULE_START: 'schedule_start_day',
        ATTR_SCHEDULE_END: 'schedule_end_day',
        ATTR_SCHEDULE_DURATION: 'schedule_duration',
        ATTR_ACTUAL_START: 'actual_start_day',
        ATTR_ACTUAL_END: 'actual_end_day',
        ATTR_ACTUAL_DURATION: 'actual_duration',
    }

    total_products = len(product_cache)
    processed = 0

    # OPTIMIZATION: Process in batches of 1000 for better performance
    batch_size = 1000
    batch_count = 0

    print(f"🚀 OPTIMIZED BAKING: Processing {total_products} products in batches of {batch_size}")

    for prod_id, prod_data in product_cache.items():
        obj_name = prod_data.get('blender_object_name')
        if not obj_name:
            processed += 1
            continue

        # OPTIMIZATION: Skip attribute creation if minimal data available
        if not prod_data.get('schedule_start_day') and not prod_data.get('schedule_end_day'):
            # Use minimal default attributes for objects without schedule data
            attributes_to_set[obj_name] = {
                ATTR_SCHEDULE_START: {"value": 1.0, "type": 'FLOAT', "domain": 'POINT'},
                ATTR_SCHEDULE_END: {"value": 999999.0, "type": 'FLOAT', "domain": 'POINT'},
                ATTR_EFFECT_TYPE: {"value": 0, "type": 'INT', "domain": 'POINT'}
            }
            processed += 1
            continue

        attributes_to_set[obj_name] = {}

        # 1. Preparar fechas y duraciones (optimizado)
        for attr_name, cache_key in date_mapping.items():
            value = prod_data.get(cache_key, 999999)
            if 'duration' in cache_key and value == 0:
                value = 1
            attributes_to_set[obj_name][attr_name] = {
                "value": value,
                "type": 'FLOAT',
                "domain": 'POINT'
            }

        # 2. Preparar tipo de efecto (optimizado)
        profile_name = get_profile_for_product(prod_data, colortype_mapping)
        profile = profiles_data.get(profile_name)
        effect_value = 1 if profile and hasattr(profile, 'gn_appearance_effect') and profile.gn_appearance_effect == 'GROWTH' else 0
        attributes_to_set[obj_name][ATTR_EFFECT_TYPE] = {
            "value": effect_value,
            "type": 'INT',
            "domain": 'POINT'
        }

        # 3. REAL COLORTYPE: Read from task assignment (like keyframes)
        real_colortype_id = get_real_colortype_for_product(prod_data, colortype_mapping, prod_id)
        attributes_to_set[obj_name]["object_colortype_id"] = {
            "value": real_colortype_id,
            "type": 'INT',  # Store as integer ID for Geometry Nodes compatibility
            "domain": 'POINT'
        }

        # 3. Preparar ID del colortype para asignación de material
        colortype_id = get_colortype_id_for_product(prod_data, colortype_mapping)
        attributes_to_set[obj_name][ATTR_COLORTYPE_ID] = {
            "value": colortype_id,
            "type": 'INT',
            "domain": 'POINT'
        }

        processed += 1

        # OPTIMIZATION: Update progress less frequently for large models
        if processed % batch_size == 0:
            batch_count += 1
            progress = (processed / total_products) * 100
            async_manager.update_progress(progress, f"Batch {batch_count} completado ({processed}/{total_products})")
            print(f"🔄 Batch {batch_count}: {processed}/{total_products} productos procesados ({progress:.1f}%)")

    async_manager.update_progress(100, "Horneado optimizado completado")
    print(f"✅ OPTIMIZED BAKING COMPLETED: {processed} productos procesados en {batch_count + 1} lotes")
    return attributes_to_set

def get_profile_for_product(prod_data, colortype_mapping):
    """
    Obtiene el perfil de ColorType para un producto específico.
    """
    # TODO: Implementar lógica basada en tus datos específicos
    # Por ejemplo, podrías usar el PredefinedType de la tarea asociada
    task_id = prod_data.get('task_id')
    if task_id and task_id in colortype_mapping:
        return colortype_mapping[task_id].get('profile_name', 'NOTDEFINED')
    return 'NOTDEFINED'

def get_colortype_id_for_product(prod_data, colortype_mapping):
    """
    Obtiene un ID numérico único para el colortype del producto.
    """
    profile_name = get_profile_for_product(prod_data, colortype_mapping)
    # Mapear nombres de colortype a IDs numéricos
    colortype_to_id = {
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
        'USERDEFINED': 14
    }
    return colortype_to_id.get(profile_name, 13)

def get_real_colortype_for_product(prod_data, colortype_mapping, prod_id):
    """
    Read real ColorType from task assignment (like keyframes system)
    """
    try:
        # Get task ID from product data
        task_id = prod_data.get('task_id')
        if not task_id:
            print(f"⚠️ No task_id for product {prod_id}, using DEFAULT colortype")
            return 0  # DEFAULT

        # Try to get ColorType from Animation Settings (same as keyframes)
        import bonsai.tool as tool
        if hasattr(tool, 'Sequence'):
            anim_props = tool.Sequence.get_animation_props()

            if hasattr(anim_props, 'ColorTypes'):
                # Find the ColorType group that contains this task
                for i, colortype_group in enumerate(anim_props.ColorTypes):
                    if hasattr(colortype_group, 'tasks'):
                        # Check if this task is in this ColorType group
                        for task in colortype_group.tasks:
                            if hasattr(task, 'id') and task.id == task_id:
                                print(f"✅ Found task {task_id} in ColorType group {i}: {colortype_group.name}")
                                return i  # Return ColorType group index

                # If task not found in any ColorType group
                print(f"⚠️ Task {task_id} not found in any ColorType group, using DEFAULT")
                return 0  # DEFAULT

    except Exception as e:
        print(f"⚠️ Error reading real ColorType for product {prod_id}: {e}")

    # Fallback: use DEFAULT ColorType
    return 0

def create_advanced_nodetree():
    """DEBUGGING VERSION: Create minimal working node tree"""
    print("🔧 CREATING DEBUG VERSION - Minimal working node tree")

    # For debugging, let's create a super simple version first
    return create_minimal_debug_nodetree()

def create_minimal_debug_nodetree():
    """FULL INTEGRATION: Complete node tree with all keyframe features"""

    if GN_NODETREE_NAME in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[GN_NODETREE_NAME])

    # Create complete node tree
    node_tree = bpy.data.node_groups.new(GN_NODETREE_NAME, 'GeometryNodeTree')

    # Input and output nodes
    input_node = node_tree.nodes.new('NodeGroupInput')
    input_node.location = (-1000, 0)
    output_node = node_tree.nodes.new('NodeGroupOutput')
    output_node.location = (1000, 0)

    # COMPLETE INTERFACE: Like keyframes
    node_tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    node_tree.interface.new_socket('Current Frame', in_out='INPUT', socket_type='NodeSocketFloat')
    node_tree.interface.new_socket('Schedule Type', in_out='INPUT', socket_type='NodeSocketInt')
    node_tree.interface.new_socket('ColorType Group', in_out='INPUT', socket_type='NodeSocketInt')
    node_tree.interface.new_socket('Speed Multiplier', in_out='INPUT', socket_type='NodeSocketFloat')  # NEW: Speed settings
    node_tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

    # 1. ATTRIBUTE READERS: Read baked schedule data (like keyframes)
    attr_schedule_start = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_schedule_start.data_type = 'FLOAT'
    attr_schedule_start.inputs['Name'].default_value = ATTR_SCHEDULE_START
    attr_schedule_start.location = (-800, 300)

    attr_schedule_end = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_schedule_end.data_type = 'FLOAT'
    attr_schedule_end.inputs['Name'].default_value = ATTR_SCHEDULE_END
    attr_schedule_end.location = (-800, 200)

    attr_colortype_id = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_colortype_id.data_type = 'INT'
    attr_colortype_id.inputs['Name'].default_value = "object_colortype_id"  # Per-object ColorType
    attr_colortype_id.location = (-800, 100)

    # 2. SPEED INTEGRATION: Apply speed multiplier to current frame AND adjust ranges
    multiply_speed = node_tree.nodes.new('ShaderNodeMath')
    multiply_speed.operation = 'MULTIPLY'
    multiply_speed.location = (-600, 0)

    # SPEED AFFECTS RANGES: Adjust start/end frames by speed (like keyframes)
    adjust_start_speed = node_tree.nodes.new('ShaderNodeMath')
    adjust_start_speed.operation = 'MULTIPLY'
    adjust_start_speed.location = (-600, 200)

    adjust_end_speed = node_tree.nodes.new('ShaderNodeMath')
    adjust_end_speed.operation = 'MULTIPLY'
    adjust_end_speed.location = (-600, 100)

    # 3. SCHEDULE LOGIC: Objects visible between adjusted start and end (like keyframes)
    compare_started = node_tree.nodes.new('FunctionNodeCompare')
    compare_started.operation = 'GREATER_EQUAL'
    compare_started.data_type = 'FLOAT'
    compare_started.location = (-400, 200)

    compare_finished = node_tree.nodes.new('FunctionNodeCompare')
    compare_finished.operation = 'LESS_EQUAL'
    compare_finished.data_type = 'FLOAT'
    compare_finished.location = (-400, 100)

    bool_and = node_tree.nodes.new('FunctionNodeBooleanMath')
    bool_and.operation = 'AND'
    bool_and.location = (-200, 150)

    # 4. DELETE GEOMETRY: Hide objects outside schedule
    delete_geometry = node_tree.nodes.new('GeometryNodeDeleteGeometry')
    delete_geometry.location = (0, 0)

    # REMOVED: invert_selection node - logic was incorrect

    # 5. SOLID SHADING: Object colors (like keyframes)
    store_color = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
    store_color.data_type = 'FLOAT_COLOR'
    store_color.domain = 'POINT'  # Store on point level (OBJECT domain not valid)
    store_color.inputs['Name'].default_value = "Col"  # Object color attribute
    store_color.location = (200, 0)

    # 6. COLORTYPE COLORS: Individual per object colors (like keyframes)
    colortype_colors = create_colortype_color_switches(node_tree, attr_colortype_id, (0, 200))

    # Create default material for compatibility
    default_material = bpy.data.materials.get("4D_DEFAULT")
    if not default_material:
        default_material = bpy.data.materials.new("4D_DEFAULT")
        default_material.diffuse_color = (0.8, 0.8, 0.8, 1.0)

    # CONNECTIONS: Complete integration with Speed Settings affecting ranges
    # Speed integration for current frame
    node_tree.links.new(input_node.outputs['Current Frame'], multiply_speed.inputs[0])
    node_tree.links.new(input_node.outputs['Speed Multiplier'], multiply_speed.inputs[1])

    # CRITICAL: Speed affects START/FINISH ranges (like keyframes)
    node_tree.links.new(attr_schedule_start.outputs['Attribute'], adjust_start_speed.inputs[0])
    node_tree.links.new(input_node.outputs['Speed Multiplier'], adjust_start_speed.inputs[1])

    node_tree.links.new(attr_schedule_end.outputs['Attribute'], adjust_end_speed.inputs[0])
    node_tree.links.new(input_node.outputs['Speed Multiplier'], adjust_end_speed.inputs[1])

    # Schedule logic using speed-adjusted ranges
    node_tree.links.new(multiply_speed.outputs['Value'], compare_started.inputs[0])
    node_tree.links.new(adjust_start_speed.outputs['Value'], compare_started.inputs[1])

    node_tree.links.new(multiply_speed.outputs['Value'], compare_finished.inputs[0])
    node_tree.links.new(adjust_end_speed.outputs['Value'], compare_finished.inputs[1])

    node_tree.links.new(compare_started.outputs['Result'], bool_and.inputs[0])
    node_tree.links.new(compare_finished.outputs['Result'], bool_and.inputs[1])

    # CORRECTED LOGIC: Delete Geometry deletes when TRUE, so invert visibility logic
    invert_selection = node_tree.nodes.new('FunctionNodeBooleanMath')
    invert_selection.operation = 'NOT'
    invert_selection.location = (-100, 0)

    node_tree.links.new(input_node.outputs['Geometry'], delete_geometry.inputs['Geometry'])
    node_tree.links.new(bool_and.outputs['Boolean'], invert_selection.inputs['Boolean'])
    node_tree.links.new(invert_selection.outputs['Boolean'], delete_geometry.inputs['Selection'])

    # LOGIC: bool_and=TRUE (visible) → NOT → FALSE → don't delete (keep visible)
    # LOGIC: bool_and=FALSE (invisible) → NOT → TRUE → delete (make invisible)

    # SOLID SHADING SYSTEM: Store object colors
    node_tree.links.new(delete_geometry.outputs['Geometry'], store_color.inputs['Geometry'])
    node_tree.links.new(colortype_colors.outputs['Output'], store_color.inputs['Value'])

    # Final output
    node_tree.links.new(store_color.outputs['Geometry'], output_node.inputs['Geometry'])

    print("✅ FULL INTEGRATION NODE TREE: Complete keyframe-like functionality")
    return node_tree

# Cleaned up - minimal debug version only

def create_dynamic_material_system(node_tree, colortype_attr_node, location):
    """Create a dynamic material/color system that handles multiple ColorTypes like keyframes"""
    attr_actual_end.data_type = 'FLOAT'
    attr_actual_end.inputs['Name'].default_value = ATTR_ACTUAL_END
    attr_actual_end.location = (-1800, -200)

    attr_effect_type = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_effect_type.data_type = 'INT'
    attr_effect_type.inputs['Name'].default_value = ATTR_EFFECT_TYPE
    attr_effect_type.location = (-1800, -400)

    attr_colortype_id = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_colortype_id.data_type = 'INT'
    attr_colortype_id.inputs['Name'].default_value = ATTR_COLORTYPE_ID
    attr_colortype_id.location = (-1800, -600)

    # 2. Switch para seleccionar entre Schedule/Actual
    schedule_switch_start = node_tree.nodes.new('GeometryNodeSwitch')
    schedule_switch_start.input_type = 'FLOAT'
    schedule_switch_start.location = (-1400, 300)

    schedule_switch_end = node_tree.nodes.new('GeometryNodeSwitch')
    schedule_switch_end.input_type = 'FLOAT'
    schedule_switch_end.location = (-1400, 100)

    # 3. FIXED: Lógica de visibilidad correcta (current_frame >= start AND current_frame <= end)
    compare_started = node_tree.nodes.new('FunctionNodeCompare')
    compare_started.data_type = 'FLOAT'
    compare_started.operation = 'GREATER_EQUAL'  # FIXED: current_frame >= start
    compare_started.location = (-1000, 400)

    compare_finished = node_tree.nodes.new('FunctionNodeCompare')
    compare_finished.data_type = 'FLOAT'
    compare_finished.operation = 'LESS_EQUAL'  # FIXED: current_frame <= end
    compare_finished.location = (-1000, 200)
    print("🔧 CRITICAL FIX: Corrected visibility comparison logic")

    # RESTORED: Proper animation logic (objects appear/disappear based on schedule)
    bool_and = node_tree.nodes.new('FunctionNodeBooleanMath')
    bool_and.operation = 'AND'  # Normal visibility logic: started AND not_finished
    bool_and.location = (-800, 300)
    print("🎬 ANIMATION RESTORED: Objects will animate based on schedule")

    # 4. Cálculo de progreso para efecto Growth (0-1)
    subtract_progress = node_tree.nodes.new('ShaderNodeMath')
    subtract_progress.operation = 'SUBTRACT'
    subtract_progress.location = (-600, 0)

    divide_progress = node_tree.nodes.new('ShaderNodeMath')
    divide_progress.operation = 'DIVIDE'
    divide_progress.location = (-400, 0)

    clamp_progress = node_tree.nodes.new('ShaderNodeClamp')
    clamp_progress.inputs['Min'].default_value = 0.0
    clamp_progress.inputs['Max'].default_value = 1.0
    clamp_progress.location = (-200, 0)

    # 5. Geometría para efecto Growth
    position_node = node_tree.nodes.new('GeometryNodeInputPosition')
    position_node.location = (-600, -400)

    separate_xyz = node_tree.nodes.new('ShaderNodeSeparateXYZ')
    separate_xyz.location = (-400, -400)

    map_range_z = node_tree.nodes.new('ShaderNodeMapRange')
    map_range_z.location = (-200, -400)

    compare_z_cut = node_tree.nodes.new('FunctionNodeCompare')
    compare_z_cut.data_type = 'FLOAT'
    compare_z_cut.operation = 'LESS_EQUAL'
    compare_z_cut.location = (0, -300)

    # 6. Switch entre geometría Instant y Growth
    effect_switch = node_tree.nodes.new('GeometryNodeSwitch')
    effect_switch.input_type = 'BOOLEAN'
    effect_switch.location = (400, 0)

    visibility_and_effect = node_tree.nodes.new('FunctionNodeBooleanMath')
    visibility_and_effect.operation = 'AND'
    visibility_and_effect.location = (600, 0)

    # 7. INVERT logic for Delete Geometry (Delete Geometry removes TRUE, but we want to SHOW TRUE)
    invert_selection = node_tree.nodes.new('FunctionNodeBooleanMath')
    invert_selection.operation = 'NOT'  # Invert the visibility logic
    invert_selection.location = (700, 0)
    print("🔧 VISIBILITY FIX: Added NOT node to invert Delete Geometry logic")

    # 8. Delete Geometry node (now deletes where selection is FALSE, shows where TRUE)
    delete_geometry = node_tree.nodes.new('GeometryNodeDeleteGeometry')
    delete_geometry.location = (800, 0)

    # 8. SIMPLE: Basic Set Material node (no complex hybrid system)
    set_material = node_tree.nodes.new('GeometryNodeSetMaterial')
    set_material.location = (1000, 0)

    # Debug: Print available inputs to fix connection error
    print(f"🔍 Set Material node inputs: {[inp.name for inp in set_material.inputs]}")
    print("🔧 SIMPLE SYSTEM: Basic material setup to avoid crashes")

    # === CONEXIONES ===

    # Conectar inputs a switches de schedule
    node_tree.links.new(attr_schedule_start.outputs['Attribute'], schedule_switch_start.inputs['False'])
    node_tree.links.new(attr_actual_start.outputs['Attribute'], schedule_switch_start.inputs['True'])
    node_tree.links.new(input_node.outputs['Schedule Type'], schedule_switch_start.inputs['Switch'])

    node_tree.links.new(attr_schedule_end.outputs['Attribute'], schedule_switch_end.inputs['False'])
    node_tree.links.new(attr_actual_end.outputs['Attribute'], schedule_switch_end.inputs['True'])
    node_tree.links.new(input_node.outputs['Schedule Type'], schedule_switch_end.inputs['Switch'])

    # FIXED: Conectar lógica de visibilidad con inputs correctos
    # compare_started: current_frame >= start_frame
    node_tree.links.new(input_node.outputs['Current Frame'], compare_started.inputs['A'])
    node_tree.links.new(schedule_switch_start.outputs['Output'], compare_started.inputs['B'])

    # compare_finished: current_frame <= end_frame
    node_tree.links.new(input_node.outputs['Current Frame'], compare_finished.inputs['A'])
    node_tree.links.new(schedule_switch_end.outputs['Output'], compare_finished.inputs['B'])
    print("🔧 CRITICAL FIX: Corrected visibility input connections")

    node_tree.links.new(compare_started.outputs['Result'], bool_and.inputs[0])
    node_tree.links.new(compare_finished.outputs['Result'], bool_and.inputs[1])

    # Conectar cálculo de progreso
    node_tree.links.new(input_node.outputs['Current Frame'], subtract_progress.inputs[0])
    node_tree.links.new(schedule_switch_start.outputs['Output'], subtract_progress.inputs[1])

    node_tree.links.new(subtract_progress.outputs['Value'], divide_progress.inputs[0])
    # Conectar duration (end - start) al divisor
    duration_subtract = node_tree.nodes.new('ShaderNodeMath')
    duration_subtract.operation = 'SUBTRACT'
    duration_subtract.location = (-600, -100)
    node_tree.links.new(schedule_switch_end.outputs['Output'], duration_subtract.inputs[0])
    node_tree.links.new(schedule_switch_start.outputs['Output'], duration_subtract.inputs[1])
    node_tree.links.new(duration_subtract.outputs['Value'], divide_progress.inputs[1])

    node_tree.links.new(divide_progress.outputs['Value'], clamp_progress.inputs['Value'])

    # Conectar efecto Growth
    node_tree.links.new(position_node.outputs['Position'], separate_xyz.inputs['Vector'])
    node_tree.links.new(separate_xyz.outputs['Z'], map_range_z.inputs['Value'])
    node_tree.links.new(clamp_progress.outputs['Result'], map_range_z.inputs['To Max'])

    node_tree.links.new(separate_xyz.outputs['Z'], compare_z_cut.inputs['A'])
    node_tree.links.new(map_range_z.outputs['Result'], compare_z_cut.inputs['B'])

    # Conectar switch de efecto
    node_tree.links.new(bool_and.outputs['Boolean'], effect_switch.inputs['False'])  # Instant
    node_tree.links.new(compare_z_cut.outputs['Result'], effect_switch.inputs['True'])  # Growth
    node_tree.links.new(attr_effect_type.outputs['Attribute'], effect_switch.inputs['Switch'])

    # Conectar geometría final CON LÓGICA INVERTIDA
    node_tree.links.new(input_node.outputs['Geometry'], delete_geometry.inputs['Geometry'])
    # CRITICAL FIX: Invert the selection logic (effect_switch -> NOT -> delete_geometry)
    node_tree.links.new(effect_switch.outputs['Output'], invert_selection.inputs['Boolean'])
    node_tree.links.new(invert_selection.outputs['Boolean'], delete_geometry.inputs['Selection'])
    print("🔧 VISIBILITY FIX: Connected inverted selection logic")

    # SIMPLE MATERIAL SYSTEM: Just use a basic default material to avoid crashes

    # Get or create a simple default material
    default_material = bpy.data.materials.get("4D_DEFAULT")
    if not default_material:
        default_material = bpy.data.materials.new("4D_DEFAULT")
        default_material.diffuse_color = (0.8, 0.8, 0.8, 1.0)  # Gray

    # Simple connections - no complex switching to avoid crashes
    node_tree.links.new(delete_geometry.outputs['Geometry'], set_material.inputs['Geometry'])
    set_material.inputs['Material'].default_value = default_material
    node_tree.links.new(set_material.outputs['Geometry'], output_node.inputs['Geometry'])

    print("🔧 SIMPLE SYSTEM: Using basic default material to prevent crashes")

    print(f"Árbol de nodos AVANZADO '{GN_NODETREE_NAME}' creado.")
    return node_tree

def create_dynamic_material_system(node_tree, colortype_attr_node, location):
    """Create a dynamic material/color system that handles multiple ColorTypes like keyframes"""

    # Create materials for all possible ColorTypes
    create_colortype_materials()

    # Create COLOR system for both materials AND solid colors
    color_system = create_colortype_color_system(node_tree, colortype_attr_node, location)

    # Create material switches for different ColorTypes (simplified version)
    # In a full system, this would be a node group with all ColorType combinations

    # Switch for Color Type 1 (ID = 1)
    switch_colortype1 = node_tree.nodes.new('GeometryNodeSwitch')
    switch_colortype1.name = "Color Type 1 Switch"
    switch_colortype1.location = location
    switch_colortype1.input_type = 'MATERIAL'

    # Switch for Color Type 2 (ID = 2)
    switch_colortype2 = node_tree.nodes.new('GeometryNodeSwitch')
    switch_colortype2.name = "Color Type 2 Switch"
    switch_colortype2.location = (location[0], location[1] - 100)
    switch_colortype2.input_type = 'MATERIAL'

    # Set up materials
    default_mat = bpy.data.materials.get("4D_DEFAULT")
    colortype1_mat = bpy.data.materials.get("4D_Color Type 1")
    colortype2_mat = bpy.data.materials.get("4D_Color Type 2")

    # Configure first switch (DEFAULT vs Color Type 1)
    if default_mat:
        switch_colortype1.inputs['False'].default_value = default_mat
    if colortype1_mat:
        switch_colortype1.inputs['True'].default_value = colortype1_mat

    # Configure second switch (previous result vs Color Type 2)
    switch_colortype2.inputs['False'].default_value = None  # Will be connected
    if colortype2_mat:
        switch_colortype2.inputs['True'].default_value = colortype2_mat

    # Comparison nodes for each ColorType
    compare_colortype1 = node_tree.nodes.new('FunctionNodeCompare')
    compare_colortype1.name = "Compare ColorType 1"
    compare_colortype1.location = (location[0] - 150, location[1])
    compare_colortype1.operation = 'EQUAL'
    compare_colortype1.data_type = 'INT'
    compare_colortype1.inputs[1].default_value = 1  # Color Type 1 ID

    compare_colortype2 = node_tree.nodes.new('FunctionNodeCompare')
    compare_colortype2.name = "Compare ColorType 2"
    compare_colortype2.location = (location[0] - 150, location[1] - 100)
    compare_colortype2.operation = 'EQUAL'
    compare_colortype2.data_type = 'INT'
    compare_colortype2.inputs[1].default_value = 2  # Color Type 2 ID

    # Connect comparisons
    node_tree.links.new(colortype_attr_node.outputs['Attribute'], compare_colortype1.inputs[0])
    node_tree.links.new(colortype_attr_node.outputs['Attribute'], compare_colortype2.inputs[0])

    # Connect switches
    node_tree.links.new(compare_colortype1.outputs['Result'], switch_colortype1.inputs['Switch'])
    node_tree.links.new(compare_colortype2.outputs['Result'], switch_colortype2.inputs['Switch'])

    # Chain switches: switch1 → switch2
    node_tree.links.new(switch_colortype1.outputs['Output'], switch_colortype2.inputs['False'])

    # Debug: Print available outputs to fix connection error
    print(f"🔍 Material switch outputs: {[out.name for out in switch_colortype2.outputs]}")

    return {'material_switch': switch_colortype2, 'color_system': color_system}  # Return both systems

def create_colortype_materials():
    """Create materials for all possible ColorTypes from Animation Settings"""
    # Get actual ColorTypes from Animation Settings
    colortype_materials = get_animation_colortypes_for_materials()

    # Basic fallback materials
    basic_materials = [
        ("4D_DEFAULT", (0.8, 0.8, 0.8, 1.0)),      # Gray default
        ("4D_Color Type 1", (0.2, 0.8, 0.2, 1.0)), # Green
        ("4D_Color Type 2", (0.2, 0.2, 0.8, 1.0)), # Blue
        ("4D_Color Type 3", (0.8, 0.8, 0.2, 1.0)), # Yellow
    ]

    materials_to_create = colortype_materials + basic_materials

    for mat_name, color in materials_to_create:
        if mat_name not in bpy.data.materials:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True

            # Get principled BSDF node
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value = color
                bsdf.inputs["Roughness"].default_value = 0.5

            print(f"✅ Created ColorType material: {mat_name}")

def get_animation_colortypes_for_materials():
    """Get ColorTypes from Animation Settings and convert to material specs"""
    materials = []

    try:
        # Get animation properties to read actual ColorTypes
        if tool is None:
            raise ImportError("bonsai.tool not available")
        anim_props = tool.Sequence.get_animation_props()

        if hasattr(anim_props, 'ColorTypes'):
            for colortype in anim_props.ColorTypes:
                if hasattr(colortype, 'name') and hasattr(colortype, 'completed_color'):
                    mat_name = f"4D_{colortype.name}"
                    # Use completed_color as the primary color
                    color = tuple(colortype.completed_color) + (1.0,)  # Add alpha
                    materials.append((mat_name, color))

    except Exception as e:
        print(f"⚠️ Could not read ColorTypes from Animation Settings: {e}")

    return materials

def create_colortype_color_system(node_tree, colortype_attr_node, location):
    """Create color system that works for both Material and Solid shading modes"""

    # Color values for each ColorType (RGB + Alpha)
    colortype_colors = {
        0: (0.8, 0.8, 0.8, 1.0),    # DEFAULT - Gray
        1: (0.2, 0.8, 0.2, 1.0),    # Color Type 1 - Green
        2: (0.2, 0.2, 0.8, 1.0),    # Color Type 2 - Blue
        3: (0.8, 0.8, 0.2, 1.0),    # Color Type 3 - Yellow
    }

    # Create color switches for each ColorType
    color_switch1 = node_tree.nodes.new('GeometryNodeSwitch')
    color_switch1.name = "Color Switch 1"
    color_switch1.location = (location[0], location[1] + 200)
    color_switch1.input_type = 'RGBA'

    color_switch2 = node_tree.nodes.new('GeometryNodeSwitch')
    color_switch2.name = "Color Switch 2"
    color_switch2.location = (location[0] + 150, location[1] + 200)
    color_switch2.input_type = 'RGBA'

    # Set default colors
    color_switch1.inputs['False'].default_value = colortype_colors[0]  # DEFAULT
    color_switch1.inputs['True'].default_value = colortype_colors[1]   # Color Type 1

    # Don't set default_value for connected inputs, just set a placeholder
    color_switch2.inputs['True'].default_value = colortype_colors[2]   # Color Type 2
    # Note: False input will be connected from color_switch1

    # Comparison nodes
    compare_color1 = node_tree.nodes.new('FunctionNodeCompare')
    compare_color1.name = "Compare Color 1"
    compare_color1.location = (location[0] - 150, location[1] + 200)
    compare_color1.operation = 'EQUAL'
    compare_color1.data_type = 'INT'
    compare_color1.inputs[1].default_value = 1

    compare_color2 = node_tree.nodes.new('FunctionNodeCompare')
    compare_color2.name = "Compare Color 2"
    compare_color2.location = (location[0] - 150, location[1] + 100)
    compare_color2.operation = 'EQUAL'
    compare_color2.data_type = 'INT'
    compare_color2.inputs[1].default_value = 2

    # Connect comparisons
    node_tree.links.new(colortype_attr_node.outputs['Attribute'], compare_color1.inputs[0])
    node_tree.links.new(colortype_attr_node.outputs['Attribute'], compare_color2.inputs[0])

    # Connect color switches
    node_tree.links.new(compare_color1.outputs['Result'], color_switch1.inputs['Switch'])
    node_tree.links.new(compare_color2.outputs['Result'], color_switch2.inputs['Switch'])

    # Chain color switches
    node_tree.links.new(color_switch1.outputs['Output'], color_switch2.inputs['False'])

    print("🎨 Color system created for both Material and Solid shading modes")

    return color_switch2  # Return final color output

def get_colortype_name_to_id(colortype_name):
    """Convert ColorType name to numeric ID for Geometry Nodes"""
    colortype_map = {
        'DEFAULT': 0,
        'Color Type 1': 1,
        'Color Type 2': 2,
        'Color Type 3': 3,
        'Color Type 4': 4,
        'Color Type 5': 5,
        # Add more as needed
    }

    return colortype_map.get(colortype_name, 0)  # Default to 0 if not found

def create_colortype_color_switches(node_tree, colortype_attr_node, location):
    """Create color switch system for Solid shading (like keyframes)"""

    # ColorType to color mapping (same as keyframes)
    colortype_colors = {
        0: (0.8, 0.8, 0.8, 1.0),    # DEFAULT - Gray
        1: (0.2, 0.8, 0.2, 1.0),    # Color Type 1 - Green
        2: (0.2, 0.2, 0.8, 1.0),    # Color Type 2 - Blue
        3: (0.8, 0.8, 0.2, 1.0),    # Color Type 3 - Yellow
        4: (0.8, 0.2, 0.2, 1.0),    # Color Type 4 - Red
        5: (0.8, 0.2, 0.8, 1.0),    # Color Type 5 - Magenta
    }

    # Create switch chain for ColorTypes (simplified - first 3 types)
    color_switch1 = node_tree.nodes.new('GeometryNodeSwitch')
    color_switch1.input_type = 'RGBA'
    color_switch1.location = location
    color_switch1.inputs['False'].default_value = colortype_colors[0]  # DEFAULT
    color_switch1.inputs['True'].default_value = colortype_colors[1]   # Color Type 1

    color_switch2 = node_tree.nodes.new('GeometryNodeSwitch')
    color_switch2.input_type = 'RGBA'
    color_switch2.location = (location[0] + 200, location[1])
    color_switch2.inputs['True'].default_value = colortype_colors[2]   # Color Type 2

    # Comparison nodes
    compare_colortype1 = node_tree.nodes.new('FunctionNodeCompare')
    compare_colortype1.operation = 'EQUAL'
    compare_colortype1.data_type = 'INT'
    compare_colortype1.inputs[1].default_value = 1  # Color Type 1
    compare_colortype1.location = (location[0] - 200, location[1])

    compare_colortype2 = node_tree.nodes.new('FunctionNodeCompare')
    compare_colortype2.operation = 'EQUAL'
    compare_colortype2.data_type = 'INT'
    compare_colortype2.inputs[1].default_value = 2  # Color Type 2
    compare_colortype2.location = (location[0] - 200, location[1] - 100)

    # Connect comparisons
    node_tree.links.new(colortype_attr_node.outputs['Attribute'], compare_colortype1.inputs[0])
    node_tree.links.new(colortype_attr_node.outputs['Attribute'], compare_colortype2.inputs[0])

    # Connect switches
    node_tree.links.new(compare_colortype1.outputs['Result'], color_switch1.inputs['Switch'])
    node_tree.links.new(compare_colortype2.outputs['Result'], color_switch2.inputs['Switch'])

    # Chain switches: switch1 → switch2
    node_tree.links.new(color_switch1.outputs['Output'], color_switch2.inputs['False'])

    print("🎨 SOLID SHADING: ColorType color switches created (like keyframes)")
    return color_switch2  # Return final color output

def apply_gn_modifiers_and_drivers(context, controller_objects):
    """
    Apply GN modifiers with COMPLETE INTEGRATION to existing systems
    """
    try:
        from .gn_integration import update_gn_modifier_with_integration_data
    except ImportError:
        print("⚠️ Integration module not available, using basic functionality")
        update_gn_modifier_with_integration_data = None
    """
    Aplica modificadores de Geometry Nodes a todos los objetos relevantes
    y configura drivers para leer datos de los controladores.
    """
    node_tree = create_advanced_nodetree()

    # Obtener todos los objetos que tienen atributos de animación
    objects_to_modify = []
    for obj in context.scene.objects:
        if (obj.type == 'MESH' and
            obj.data and
            obj.data.vertices and
            ATTR_SCHEDULE_START in obj.data.attributes):
            objects_to_modify.append(obj)

    print(f"⚙️ Aplicando modificadores a {len(objects_to_modify)} objetos...")
    if len(objects_to_modify) == 0:
        print("❌ WARNING: No objects found with baked attributes for GN modifiers!")

    # Ensure a controller exists
    controller = ensure_gn_controller()
    controller_objects = [controller] if controller else []

    for i, obj in enumerate(objects_to_modify):
        print(f"⚙️ Processing object {i+1}/{len(objects_to_modify)}: {obj.name}")
        # Buscar modificador existente o crear uno nuevo
        modifier = None
        for mod in obj.modifiers:
            if mod.name == GN_MODIFIER_NAME and mod.type == 'NODES':
                modifier = mod
                break

        if not modifier:
            modifier = obj.modifiers.new(name=GN_MODIFIER_NAME, type='NODES')

        modifier.node_group = node_tree

        # Force Blender to update the modifier to create input properties
        bpy.context.view_layer.update()

        # Debug: Check modifier properties after assignment
        print(f"🔍 Modifier properties: {list(modifier.keys())}")
        if hasattr(modifier, 'node_group') and modifier.node_group:
            print(f"🔍 Node group assigned: {modifier.node_group.name}")
            if hasattr(modifier.node_group, 'interface'):
                inputs = [socket.name for socket in modifier.node_group.interface.items_tree if socket.in_out == 'INPUT']
                print(f"🔍 Node group inputs: {inputs}")

        # Debug: Check if object has the required attributes
        if obj.data and hasattr(obj.data, 'attributes'):
            attrs_found = [attr_name for attr_name in [ATTR_SCHEDULE_START, ATTR_SCHEDULE_END, ATTR_EFFECT_TYPE]
                          if attr_name in obj.data.attributes]
            print(f"🔍 Object {obj.name} has attributes: {attrs_found}")

        # CRITICAL: Add Current Frame driver first - essential for animation
        current_frame_added = False
        for input_name in ['["Input_2"]', '["Socket_1"]', '["Current Frame"]']:
            try:
                driver = modifier.driver_add(input_name).driver
                driver.type = 'SCRIPTED'
                driver.expression = 'frame'  # Blender built-in frame variable
                print(f"✅ Added Current Frame driver ({input_name}) to {obj.name}")
                current_frame_added = True
                break
            except Exception as e:
                continue

        if not current_frame_added:
            print(f"⚠️ Could not add Current Frame driver to {obj.name}")
            # Debug: Print available modifier keys
            try:
                available_keys = [key for key in modifier.keys() if 'Input' in key or 'Socket' in key]
                print(f"🔍 Available modifier inputs: {available_keys}")
                # Also try to show all keys
                all_keys = list(modifier.keys())
                print(f"🔍 All modifier keys: {all_keys}")
            except Exception as debug_e:
                print(f"🔍 Debug failed: {debug_e}")

        # Configurar drivers para leer del controlador más cercano o activo
        if controller_objects:
            controller = controller_objects[0]  # Por simplicidad, usar el primero
            print(f"🎮 Using controller: {controller.name}")

            # Driver para Schedule Type
            schedule_type_added = False
            for input_name in ['["Input_3"]', '["Socket_2"]', '["Schedule Type"]']:
                try:
                    driver = modifier.driver_add(input_name).driver
                    driver.type = 'SCRIPTED'
                    var = driver.variables.new()
                    var.name = 'schedule_type'
                    var.type = 'SINGLE_PROP'
                    var.targets[0].id = controller
                    var.targets[0].data_path = 'BonsaiGNController.schedule_type_to_display'
                    driver.expression = 'int(schedule_type)'
                    print(f"✅ Added Schedule Type driver ({input_name}) to {obj.name}")
                    schedule_type_added = True
                    break
                except Exception:
                    continue

            if not schedule_type_added:
                print(f"⚠️ Could not add Schedule Type driver to {obj.name}")

            # Driver para ColorType Group
            colortype_group_added = False
            for input_name in ['["Input_4"]', '["Socket_3"]', '["ColorType Group"]']:
                try:
                    driver = modifier.driver_add(input_name).driver
                    driver.type = 'SCRIPTED'
                    var = driver.variables.new()
                    var.name = 'colortype_group'
                    var.type = 'SINGLE_PROP'
                    var.targets[0].id = controller
                    var.targets[0].data_path = 'BonsaiGNController.colortype_group_to_display'
                    driver.expression = 'int(colortype_group) if colortype_group else 0'
                    print(f"✅ Added ColorType Group driver ({input_name}) to {obj.name}")
                    colortype_group_added = True
                    break
                except Exception:
                    continue

            if not colortype_group_added:
                print(f"⚠️ Could not add ColorType Group driver to {obj.name}")

            # SPEED SETTINGS INTEGRATION: Add Speed Multiplier driver (CRITICAL)
            speed_multiplier_added = False
            for input_name in ['["Input_5"]', '["Socket_4"]', '["Speed Multiplier"]']:
                try:
                    driver = modifier.driver_add(input_name).driver
                    driver.type = 'SCRIPTED'

                    # FIXED: Read speed from animation properties with fallback
                    var = driver.variables.new()
                    var.name = 'speed_setting'
                    var.type = 'SINGLE_PROP'
                    var.targets[0].id = context.scene

                    # Try different possible paths for speed setting
                    try:
                        # Test if the property path exists
                        if hasattr(context.scene, 'BIMAnimationProperties') and hasattr(context.scene.BIMAnimationProperties, 'playback_speed'):
                            var.targets[0].data_path = 'BIMAnimationProperties.playback_speed'
                        else:
                            # Fallback: set to direct value
                            var.targets[0].data_path = 'frame_current'  # Dummy path
                            driver.expression = '1.0'  # Always 1.0x speed
                            print(f"⚠️ BIMAnimationProperties.playback_speed not found, using 1.0x speed")
                    except Exception as path_e:
                        var.targets[0].data_path = 'frame_current'  # Dummy path
                        driver.expression = '1.0'  # Always 1.0x speed
                        print(f"⚠️ Speed path error: {path_e}, using 1.0x speed")

                    # Convert speed setting to multiplier with fallback
                    if 'playback_speed' in var.targets[0].data_path:
                        driver.expression = 'max(0.1, float(speed_setting)) if speed_setting else 1.0'  # Prevent 0.0
                    print(f"✅ Added Speed Multiplier driver ({input_name}) to {obj.name}")
                    speed_multiplier_added = True
                    break
                except Exception:
                    continue

            if not speed_multiplier_added:
                print(f"⚠️ Could not add Speed Multiplier driver to {obj.name}")
                # CRITICAL FIX: Always set default speed to 1.0 to prevent Speed=0.0 bug
                try:
                    # Force set speed to 1.0 via Socket_4
                    modifier["Socket_4"] = 1.0
                    print(f"🔧 FORCED speed=1.0x for {obj.name} via Socket_4 (prevents Speed=0.0 bug)")
                except Exception as fallback_e:
                    print(f"⚠️ Critical fallback speed setting failed: {fallback_e}")
                    # Try alternative socket names
                    for socket_name in ['Socket_4', 'Input_5']:
                        try:
                            modifier[socket_name] = 1.0
                            print(f"🔧 FORCED speed=1.0x for {obj.name} via {socket_name}")
                            break
                        except:
                            continue

        else:
            # No controller found - create default values
            print("⚠️ No controller found, using default values")
            if 'Schedule Type' in modifier:
                modifier["Schedule Type"] = 0
            if 'ColorType Group' in modifier:
                modifier["ColorType Group"] = 0
            # Set default speed
            if 'Speed Multiplier' in modifier:
                modifier["Speed Multiplier"] = 1.0

    print(f"✅ Modificadores aplicados correctamente a {len(objects_to_modify)} objetos.")

    # Force UI update and make node tree visible
    try:
        # Update viewlayer to ensure all changes are visible
        bpy.context.view_layer.update()

        # If there's a Geometry Nodes editor, set it to show our node tree
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'GEOMETRY_NODE_EDITOR':
                    for space in area.spaces:
                        if hasattr(space, 'node_tree'):
                            space.node_tree = node_tree
                            print(f"✅ Set Geometry Nodes editor to show {node_tree.name}")

        # Force redraw of all areas
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

    except Exception as e:
        print(f"⚠️ Could not update UI: {e}")

    # COMPLETE INTEGRATION: Update with all system data
    if update_gn_modifier_with_integration_data:
        integration_result = update_gn_modifier_with_integration_data(context)
        print(f"🚀 INTEGRATION: {integration_result} modifiers updated with speed/date/colortype data")
    else:
        print("🔧 BASIC MODE: Integration features not loaded")

    print("✅ apply_gn_modifiers_and_drivers COMPLETED successfully!")

def setup_object_solid_colors(context):
    """Setup object solid colors for Solid shading mode compatibility"""

    # ColorType to color mapping (matches node system)
    colortype_colors = {
        'DEFAULT': (0.8, 0.8, 0.8),      # Gray
        'Color Type 1': (0.2, 0.8, 0.2), # Green
        'Color Type 2': (0.2, 0.2, 0.8), # Blue
        'Color Type 3': (0.8, 0.8, 0.2), # Yellow
    }

    objects_processed = 0
    for obj in context.scene.objects:
        if obj.type == 'MESH':
            # Check if object has GN modifier
            has_gn_modifier = any(mod.name == GN_MODIFIER_NAME and mod.type == 'NODES'
                                for mod in obj.modifiers)

            if has_gn_modifier:
                # Set default solid color (can be overridden by ColorType selection)
                default_color = colortype_colors['DEFAULT']
                obj.color = (*default_color, 1.0)  # Add alpha

                # Enable object color display
                obj.use_color = True

                objects_processed += 1
                print(f"🎨 Set solid color for {obj.name}: {default_color}")

    print(f"✅ Solid colors configured for {objects_processed} objects")

def cleanup_gn_system():
    """
    Limpia el sistema de Geometry Nodes removiendo modificadores y nodos.
    """
    removed_modifiers = 0

    # Remover modificadores de todos los objetos
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            for modifier in obj.modifiers[:]:
                if modifier.name == GN_MODIFIER_NAME:
                    obj.modifiers.remove(modifier)
                    removed_modifiers += 1

    # Remover el node tree
    if GN_NODETREE_NAME in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[GN_NODETREE_NAME])

    # Limpiar colección de controladores
    if GN_CONTROLLER_COLLECTION in bpy.data.collections:
        coll = bpy.data.collections[GN_CONTROLLER_COLLECTION]
        for obj in list(coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(coll)

    print(f"Sistema de Geometry Nodes limpiado: {removed_modifiers} modificadores removidos.")

def create_gn_animation_system(context, work_schedule, product_frames, settings):
    """
    Creates a complete Geometry Nodes animation system as an alternative to keyframes.
    This function bridges the gap between the keyframe and GN systems.
    """
    print("🎬 Creating Geometry Nodes animation system...")
    print(f"🔍 ENTRY DEBUG: product_frames type={type(product_frames)}, length={len(product_frames) if product_frames else 0}")
    print(f"🔍 ENTRY DEBUG: work_schedule={work_schedule}, settings type={type(settings)}")

    try:
        # 1. Clear any existing GN system
        cleanup_gn_system()

        # 2. Prepare data for geometry nodes
        product_cache = {}
        profiles_data = {}
        colortype_mapping = {}

        # Extract data from product_frames (keyframe format) to GN format
        # Validate that product_frames is a dictionary, not a list
        print(f"🔍 Processing {len(product_frames)} products for GN conversion")

        if not isinstance(product_frames, dict):
            print(f"❌ Error: product_frames is {type(product_frames)}, expected dict")
            print(f"🔍 DEBUG: product_frames content: {str(product_frames)[:200]}...")
            print("🔍 RETURN DEBUG: Returning False - invalid product_frames type")
            return False

        try:
            product_items = product_frames.items()
        except AttributeError as e:
            print(f"❌ Error accessing product_frames.items(): {e}")
            print(f"🔍 product_frames type: {type(product_frames)}")
            print(f"🔍 product_frames: {product_frames}")
            print("🔍 RETURN DEBUG: Returning False - AttributeError on .items()")
            return False

        try:
            for product_id, frame_data in product_items:
                # Get the Blender object
                obj = None
                for scene_obj in context.scene.objects:
                    if scene_obj.type == 'MESH' and hasattr(scene_obj, 'BIMObjectProperties'):
                        props = scene_obj.BIMObjectProperties
                        if hasattr(props, 'ifc_definition_id') and props.ifc_definition_id == product_id:
                            obj = scene_obj
                            break

                if not obj:
                    continue

                # Extract timing data from frame_data
                schedule_start = None
                schedule_end = None

                # Process frame_data to extract timing information

                # Handle the actual data structure: frame_data is a list containing task dictionaries
                if isinstance(frame_data, list):
                    if len(frame_data) > 0:
                        # Get the first (and typically only) task data
                        task_data = frame_data[0]
                        if isinstance(task_data, dict):
                            # Extract start and end frames directly from the task data
                            schedule_start = task_data.get('start_frame')
                            schedule_end = task_data.get('finish_frame')
                            task_id = task_data.get('task_id')  # CRITICAL: Extract task_id

                            # Also try alternative field names
                            if schedule_start is None:
                                schedule_start = task_data.get('STARTED')
                            if schedule_end is None:
                                schedule_end = task_data.get('COMPLETED')

                            print(f"✅ Product {product_id}: start={schedule_start}, end={schedule_end} (task {task_id})")
                        else:
                            print(f"❌ ERROR: task_data is {type(task_data)}, expected dict")
                            continue
                    else:
                        print(f"❌ ERROR: frame_data list is empty")
                        continue
                elif isinstance(frame_data, dict):
                    # Handle the original expected format (frame-by-frame states)
                    for frame, state_data in frame_data.items():
                        if not isinstance(state_data, dict):
                            continue
                        if state_data.get('state') == 'STARTED':
                            if schedule_start is None or frame < schedule_start:
                                schedule_start = frame
                        elif state_data.get('state') == 'FINISHED':
                            if schedule_end is None or frame > schedule_end:
                                schedule_end = frame
                else:
                    print(f"❌ ERROR: frame_data is {type(frame_data)}, expected list or dict")
                    continue

                if schedule_start is None or schedule_end is None:
                    print(f"⚠️ WARNING: Could not extract valid timing for product {product_id}: start={schedule_start}, end={schedule_end}")
                    continue

                # Convert to GN format with REAL task_id
                product_cache[product_id] = {
                    'blender_object_name': obj.name,
                    'schedule_start_day': float(schedule_start),
                    'schedule_end_day': float(schedule_end),
                    'schedule_duration': float(schedule_end - schedule_start),
                    'actual_start_day': float(schedule_start),  # For now, same as schedule
                    'actual_end_day': float(schedule_end),
                    'actual_duration': float(schedule_end - schedule_start),
                    'task_id': task_id  # REAL task_id for ColorType lookup
                }
        except Exception as loop_e:
            print(f"❌ Error in product processing loop: {loop_e}")
            import traceback
            print(f"🔍 Loop traceback: {traceback.format_exc()}")
            print("🔍 RETURN DEBUG: Returning False - Exception in processing loop")
            return False

        # 3. Submit the task to async manager for attribute baking
        success = async_manager.submit_task(
            bake_all_attributes_worker,
            product_cache,
            profiles_data,
            colortype_mapping
        )

        if success:
            # 4. Start modal operator to monitor progress
            bpy.ops.bim.run_async_task('INVOKE_DEFAULT')
            print("✅ Geometry Nodes animation system creation started")
            print("🔍 RETURN DEBUG: Returning True - success!")
            return True
        else:
            print("❌ Failed to start GN animation creation")
            print("🔍 RETURN DEBUG: Returning False - async task failed")
            return False

    except Exception as e:
        print(f"❌ Error creating GN animation system: {e}")
        import traceback
        print(f"🔍 Full traceback: {traceback.format_exc()}")
        print("🔍 RETURN DEBUG: Returning False - Exception in main try block")
        return False