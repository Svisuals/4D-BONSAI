# EN: tool/sequence/gn_sequence.py
import bpy
import time
import bmesh
from typing import Dict, Any, Optional
from bonsai.bim.module.sequence.core import async_manager

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
    Función 'pura' que se ejecuta en el hilo secundario.
    Calcula todos los atributos y devuelve un diccionario de instrucciones.
    NO USA BPY NI CONTEXT.
    """
    async_manager.update_progress(0, "Iniciando horneado de atributos...")

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

    for prod_id, prod_data in product_cache.items():
        obj_name = prod_data.get('blender_object_name')
        if not obj_name:
            processed += 1
            continue

        attributes_to_set[obj_name] = {}

        # 1. Preparar fechas y duraciones
        for attr_name, cache_key in date_mapping.items():
            value = prod_data.get(cache_key, 999999)
            if 'duration' in cache_key and value == 0:
                value = 1
            attributes_to_set[obj_name][attr_name] = {
                "value": value,
                "type": 'FLOAT',
                "domain": 'POINT'
            }

        # 2. Preparar tipo de efecto basado en el profile del producto
        profile_name = get_profile_for_product(prod_data, colortype_mapping)
        profile = profiles_data.get(profile_name)
        effect_value = 1 if profile and hasattr(profile, 'gn_appearance_effect') and profile.gn_appearance_effect == 'GROWTH' else 0
        attributes_to_set[obj_name][ATTR_EFFECT_TYPE] = {
            "value": effect_value,
            "type": 'INT',
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
        progress = (processed / total_products) * 100
        async_manager.update_progress(progress, f"Procesando {obj_name}...")

    async_manager.update_progress(100, "Horneado completado")
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

def create_advanced_nodetree():
    """
    Crea el árbol de nodos completo para la animación 4D con Geometry Nodes.
    """
    if GN_NODETREE_NAME in bpy.data.node_groups:
        return bpy.data.node_groups[GN_NODETREE_NAME]

    # Crear el árbol de nodos
    node_tree = bpy.data.node_groups.new(name=GN_NODETREE_NAME, type='GeometryNodeTree')

    # Crear nodos de entrada y salida
    input_node = node_tree.nodes.new('NodeGroupInput')
    output_node = node_tree.nodes.new('NodeGroupOutput')

    input_node.location = (-2000, 0)
    output_node.location = (2000, 0)

    # Crear inputs y outputs del node group
    node_tree.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    node_tree.interface.new_socket(name='Current Frame', in_out='INPUT', socket_type='NodeSocketFloat')
    node_tree.interface.new_socket(name='Schedule Type', in_out='INPUT', socket_type='NodeSocketInt')
    node_tree.interface.new_socket(name='ColorType Group', in_out='INPUT', socket_type='NodeSocketInt')
    node_tree.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

    # === NODOS PRINCIPALES ===

    # 1. Named Attribute nodes para leer los atributos horneados
    attr_schedule_start = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_schedule_start.data_type = 'FLOAT'
    attr_schedule_start.inputs['Name'].default_value = ATTR_SCHEDULE_START
    attr_schedule_start.location = (-1800, 400)

    attr_schedule_end = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_schedule_end.data_type = 'FLOAT'
    attr_schedule_end.inputs['Name'].default_value = ATTR_SCHEDULE_END
    attr_schedule_end.location = (-1800, 200)

    attr_actual_start = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr_actual_start.data_type = 'FLOAT'
    attr_actual_start.inputs['Name'].default_value = ATTR_ACTUAL_START
    attr_actual_start.location = (-1800, 0)

    attr_actual_end = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
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

    # 3. Lógica de visibilidad (started AND NOT finished)
    compare_started = node_tree.nodes.new('FunctionNodeCompare')
    compare_started.data_type = 'FLOAT'
    compare_started.operation = 'LESS_EQUAL'
    compare_started.location = (-1000, 400)

    compare_finished = node_tree.nodes.new('FunctionNodeCompare')
    compare_finished.data_type = 'FLOAT'
    compare_finished.operation = 'GREATER_THAN'
    compare_finished.location = (-1000, 200)

    bool_and = node_tree.nodes.new('FunctionNodeBooleanMath')
    bool_and.operation = 'AND'
    bool_and.location = (-800, 300)

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

    # 7. Delete Geometry node
    delete_geometry = node_tree.nodes.new('GeometryNodeDeleteGeometry')
    delete_geometry.location = (800, 0)

    # 8. Set Material node para colortype
    set_material = node_tree.nodes.new('GeometryNodeSetMaterial')
    set_material.location = (1000, 0)

    # === CONEXIONES ===

    # Conectar inputs a switches de schedule
    node_tree.links.new(attr_schedule_start.outputs['Attribute'], schedule_switch_start.inputs['False'])
    node_tree.links.new(attr_actual_start.outputs['Attribute'], schedule_switch_start.inputs['True'])
    node_tree.links.new(input_node.outputs['Schedule Type'], schedule_switch_start.inputs['Switch'])

    node_tree.links.new(attr_schedule_end.outputs['Attribute'], schedule_switch_end.inputs['False'])
    node_tree.links.new(attr_actual_end.outputs['Attribute'], schedule_switch_end.inputs['True'])
    node_tree.links.new(input_node.outputs['Schedule Type'], schedule_switch_end.inputs['Switch'])

    # Conectar lógica de visibilidad
    node_tree.links.new(schedule_switch_start.outputs['Output'], compare_started.inputs['A'])
    node_tree.links.new(input_node.outputs['Current Frame'], compare_started.inputs['B'])

    node_tree.links.new(input_node.outputs['Current Frame'], compare_finished.inputs['A'])
    node_tree.links.new(schedule_switch_end.outputs['Output'], compare_finished.inputs['B'])

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

    # Conectar geometría final
    node_tree.links.new(input_node.outputs['Geometry'], delete_geometry.inputs['Geometry'])
    node_tree.links.new(effect_switch.outputs['Output'], delete_geometry.inputs['Selection'])

    node_tree.links.new(delete_geometry.outputs['Geometry'], set_material.inputs['Geometry'])

    # TODO: Conectar lógica de asignación de material basada en colortype_id
    # Esto requiere crear materiales dinámicamente o usar un sistema de materiales

    node_tree.links.new(set_material.outputs['Geometry'], output_node.inputs['Geometry'])

    print(f"Árbol de nodos AVANZADO '{GN_NODETREE_NAME}' creado.")
    return node_tree

def apply_gn_modifiers_and_drivers(context, controller_objects):
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

    print(f"Aplicando modificadores a {len(objects_to_modify)} objetos...")

    # Ensure a controller exists
    controller = ensure_gn_controller()
    controller_objects = [controller] if controller else []

    for obj in objects_to_modify:
        # Buscar modificador existente o crear uno nuevo
        modifier = None
        for mod in obj.modifiers:
            if mod.name == GN_MODIFIER_NAME and mod.type == 'NODES':
                modifier = mod
                break

        if not modifier:
            modifier = obj.modifiers.new(name=GN_MODIFIER_NAME, type='NODES')

        modifier.node_group = node_tree

        # Debug: Check if object has the required attributes
        if obj.data and hasattr(obj.data, 'attributes'):
            attrs_found = [attr_name for attr_name in [ATTR_SCHEDULE_START, ATTR_SCHEDULE_END, ATTR_EFFECT_TYPE]
                          if attr_name in obj.data.attributes]
            print(f"🔍 Object {obj.name} has attributes: {attrs_found}")

        # CRITICAL: Add Current Frame driver first - essential for animation
        if 'Current Frame' in modifier:
            driver = modifier.driver_add('["Current Frame"]').driver
            driver.type = 'SCRIPTED'
            driver.expression = 'frame'  # Blender built-in frame variable
            print(f"✅ Added Current Frame driver to {obj.name}")
        else:
            print(f"⚠️ 'Current Frame' input not found in modifier for {obj.name}")

        # Configurar drivers para leer del controlador más cercano o activo
        if controller_objects:
            controller = controller_objects[0]  # Por simplicidad, usar el primero
            print(f"🎮 Using controller: {controller.name}")

            # Driver para Schedule Type
            if 'Schedule Type' in modifier:
                driver = modifier.driver_add('["Schedule Type"]').driver
                driver.type = 'SCRIPTED'
                var = driver.variables.new()
                var.name = 'schedule_type'
                var.type = 'SINGLE_PROP'
                var.targets[0].id = controller
                var.targets[0].data_path = 'BonsaiGNController.schedule_type_to_display'
                driver.expression = 'int(schedule_type)'
                print(f"✅ Added Schedule Type driver to {obj.name}")

            # Driver para ColorType Group
            if 'ColorType Group' in modifier:
                driver = modifier.driver_add('["ColorType Group"]').driver
                driver.type = 'SCRIPTED'
                var = driver.variables.new()
                var.name = 'colortype_group'
                var.type = 'SINGLE_PROP'
                var.targets[0].id = controller
                var.targets[0].data_path = 'BonsaiGNController.colortype_group_to_display'
                driver.expression = 'int(colortype_group) if colortype_group else 0'
                print(f"✅ Added ColorType Group driver to {obj.name}")
        else:
            # No controller found - create default values
            print("⚠️ No controller found, using default values")
            if 'Schedule Type' in modifier:
                modifier["Schedule Type"] = 0
            if 'ColorType Group' in modifier:
                modifier["ColorType Group"] = 0

    print(f"Modificadores aplicados correctamente a {len(objects_to_modify)} objetos.")

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

    try:
        # 1. Clear any existing GN system
        cleanup_gn_system()

        # 2. Prepare data for geometry nodes
        product_cache = {}
        profiles_data = {}
        colortype_mapping = {}

        # Extract data from product_frames (keyframe format) to GN format
        for product_id, frame_data in product_frames.items():
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
            for frame, state_data in frame_data.items():
                if state_data.get('state') == 'STARTED':
                    if schedule_start is None or frame < schedule_start:
                        schedule_start = frame
                elif state_data.get('state') == 'FINISHED':
                    if schedule_end is None or frame > schedule_end:
                        schedule_end = frame

            if schedule_start is None or schedule_end is None:
                continue

            # Convert to GN format
            product_cache[product_id] = {
                'blender_object_name': obj.name,
                'schedule_start_day': float(schedule_start),
                'schedule_end_day': float(schedule_end),
                'schedule_duration': float(schedule_end - schedule_start),
                'actual_start_day': float(schedule_start),  # For now, same as schedule
                'actual_end_day': float(schedule_end),
                'actual_duration': float(schedule_end - schedule_start),
                'task_id': None  # Would need to be extracted from your data
            }

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
            return True
        else:
            print("❌ Failed to start GN animation creation")
            return False

    except Exception as e:
        print(f"❌ Error creating GN animation system: {e}")
        return False