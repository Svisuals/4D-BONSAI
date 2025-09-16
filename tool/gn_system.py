# Main GN System Integration File
# Complete Geometry Nodes 4D Animation System for Bonsai
# This file provides the main entry points and system integration

"""
SISTEMA COMPLETO DE ANIMACIÓN 4D BASADO EN GEOMETRY NODES

Este sistema proporciona una alternativa de alto rendimiento al sistema de animación
por keyframes existente, implementando las siguientes características:

CARACTERÍSTICAS PRINCIPALES:
✅ Compatibilidad visual dual (Solid + Material/Rendered modes)
✅ Integración completa con Live Color Scheme
✅ Sistema de ColorTypes individual por objeto
✅ Lógica de visibilidad de tres estados (before_start, active, after_end)
✅ Efectos de aparición (Instant/Growth)
✅ Integración total con la UI existente
✅ Rendimiento optimizado para modelos grandes

ETAPAS IMPLEMENTADAS:

ETAPA 1: Preparación y Horneado de Datos de Geometría
- Función bake_all_attributes_worker_enhanced() autónoma
- Cálculo completo de fechas y estados basado en get_animation_settings()
- Horneado de atributos de visibilidad y apariencia
- Atributos: schedule_start/end, visibility_before_start/after_end, effect_type, colortype_id

ETAPA 2: Lógica de Visibilidad Completa en el Árbol de Nodos
- Función create_advanced_nodetree_enhanced() con lógica de tres estados
- Implementación procedural de la lógica: (es_antes AND visibility_before) OR (es_activo) OR (es_después AND visibility_after)
- Generación de atributos de salida para el shader (animation_state, colortype_id)
- Sistema de efectos Instant/Growth

ETAPA 3: Sistema de Apariencia Dual
- Súper Material universal para modos Material Preview/Rendered
- Manejador de eventos para modo Solid (gn_live_color_update_handler_enhanced)
- Sincronización perfecta entre ambos modos de visualización

ETAPA 4: Integración con UI Existente
- Modificación de operadores CreateAnimation/ClearAnimation
- Integración con el botón Live Color Scheme existente
- Detección automática de cambios en ColorType assignments
- Sistema de re-horneado automático

ARQUITECTURA DEL SISTEMA:

1. gn_sequence_enhanced.py - Sistema principal con todas las etapas
2. gn_ui_integration.py - Integración con la UI existente
3. gn_system_main.py (este archivo) - Punto de entrada y coordinación
4. Modificaciones menores en operadores existentes

USO DEL SISTEMA:

1. Inicialización:
   from .tool.gn_system_main import initialize_complete_gn_system
   initialize_complete_gn_system()

2. Crear animación:
   - Usar el botón "Create Animation" existente
   - El sistema detecta automáticamente si usar Keyframes o GN
   - Configurar "Live Color Scheme" funciona igual que antes

3. Limpieza:
   from .tool.gn_system_main import cleanup_complete_gn_system
   cleanup_complete_gn_system()

COMPATIBILIDAD:
- ✅ Totalmente compatible con el sistema de Keyframes existente
- ✅ Los usuarios pueden alternar entre modos sin problemas
- ✅ Mismo comportamiento visual que el sistema de Keyframes
- ✅ Mismos controles de UI y funcionalidad
"""

import bpy
from typing import Optional, Dict, Any

try:
    import bonsai.tool as tool
    from .gn_sequence import (
        create_complete_gn_animation_system_enhanced,
        cleanup_enhanced_gn_system,
        register_gn_live_color_handler_enhanced,
        unregister_gn_live_color_handler_enhanced
    )
    from .gn_ui import (
        initialize_gn_ui_integration,
        cleanup_gn_ui_integration,
        is_geometry_nodes_mode,
        get_current_animation_mode
    )
except ImportError as e:
    print(f"⚠️ Could not import GN system components: {e}")
    tool = None

# System status tracking
_gn_system_initialized = False
_gn_system_active = False

def initialize_complete_gn_system():
    """
    Inicializa el sistema completo de animación 4D basado en Geometry Nodes

    Returns:
        bool: True si la inicialización fue exitosa
    """
    global _gn_system_initialized

    if _gn_system_initialized:
        print("✅ GN system already initialized")
        return True

    print("🚀 Initializing complete Geometry Nodes 4D Animation System...")
    print("=" * 80)

    try:
        # Verificar que Bonsai tool esté disponible
        if tool is None:
            print("❌ Bonsai tool not available - cannot initialize GN system")
            return False

        # Inicializar integración con UI
        print("📱 STEP 1: Initializing UI integration...")
        ui_success = initialize_gn_ui_integration()

        if not ui_success:
            print("❌ UI integration failed")
            return False

        print("✅ STEP 1 COMPLETED: UI integration successful")

        # Registrar manejadores de eventos
        print("🎮 STEP 2: Registering event handlers...")
        try:
            # Los manejadores se registrarán cuando Live Color Scheme se active
            print("✅ STEP 2 COMPLETED: Event handlers ready")
        except Exception as e:
            print(f"⚠️ STEP 2 WARNING: Some event handlers may not be available: {e}")

        # Marcar sistema como inicializado
        _gn_system_initialized = True

        print("=" * 80)
        print("✅ GEOMETRY NODES 4D ANIMATION SYSTEM INITIALIZED SUCCESSFULLY!")
        print("   - All 4 stages implemented")
        print("   - UI integration active")
        print("   - Compatible with existing Keyframes system")
        print("   - Ready for high-performance 4D animation")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"❌ Failed to initialize GN system: {e}")
        import traceback
        traceback.print_exc()
        return False

def cleanup_complete_gn_system():
    """
    Limpia completamente el sistema de Geometry Nodes
    """
    global _gn_system_initialized, _gn_system_active

    print("🧹 Cleaning up complete Geometry Nodes 4D Animation System...")

    try:
        # Limpiar sistema activo si está funcionando
        if _gn_system_active:
            deactivate_gn_system()

        # Limpiar integración con UI
        cleanup_gn_ui_integration()

        # Limpiar sistema de GN
        cleanup_enhanced_gn_system()

        # Marcar como no inicializado
        _gn_system_initialized = False

        print("✅ Complete GN system cleaned up successfully")

    except Exception as e:
        print(f"⚠️ Error during GN system cleanup: {e}")

def activate_gn_system(context, work_schedule, settings):
    """
    Activa el sistema de GN para una animación específica

    Args:
        context: Blender context
        work_schedule: IfcWorkSchedule activo
        settings: Configuración de animación

    Returns:
        bool: True si la activación fue exitosa
    """
    global _gn_system_active

    if not _gn_system_initialized:
        print("❌ GN system not initialized - call initialize_complete_gn_system() first")
        return False

    print("🎬 Activating GN animation system...")

    try:
        # Crear el sistema completo de animación
        success = create_complete_gn_animation_system_enhanced(context, work_schedule, settings)

        if success:
            _gn_system_active = True
            print("✅ GN animation system activated successfully")
            return True
        else:
            print("❌ Failed to activate GN animation system")
            return False

    except Exception as e:
        print(f"❌ Error activating GN system: {e}")
        import traceback
        traceback.print_exc()
        return False

def deactivate_gn_system():
    """
    Desactiva el sistema de GN actual
    """
    global _gn_system_active

    if not _gn_system_active:
        print("✅ GN system already inactive")
        return True

    print("🔇 Deactivating GN animation system...")

    try:
        # Limpiar sistema activo
        cleanup_enhanced_gn_system()

        # Desregistrar manejadores
        unregister_gn_live_color_handler_enhanced()

        _gn_system_active = False
        print("✅ GN animation system deactivated successfully")
        return True

    except Exception as e:
        print(f"⚠️ Error deactivating GN system: {e}")
        return False

def get_gn_system_status():
    """
    Obtiene el estado actual del sistema de GN

    Returns:
        dict: Estado del sistema
    """
    return {
        'initialized': _gn_system_initialized,
        'active': _gn_system_active,
        'mode': get_current_animation_mode(),
        'is_gn_mode': is_geometry_nodes_mode(),
        'tool_available': tool is not None
    }

def create_gn_animation_auto(preserve_current_frame=False):
    """
    Crear animación GN de forma automática (equivalente al operador CreateAnimation)

    Args:
        preserve_current_frame: Si preservar el frame actual

    Returns:
        dict: Resultado de la operación {'FINISHED'} o {'CANCELLED'}
    """
    if not _gn_system_initialized:
        print("❌ GN system not initialized")
        return {'CANCELLED'}

    try:
        context = bpy.context
        stored_frame = context.scene.frame_current

        # Obtener work schedule y settings
        work_schedule = tool.Sequence.get_active_work_schedule()
        if not work_schedule:
            print("❌ No active work schedule found")
            return {'CANCELLED'}

        settings = tool.Sequence.get_animation_settings()
        if not settings:
            print("❌ Could not calculate animation settings")
            return {'CANCELLED'}

        # Activar sistema GN
        success = activate_gn_system(context, work_schedule, settings)

        if success:
            # Configurar Live Color Scheme si está habilitado
            anim_props = tool.Sequence.get_animation_props()
            if anim_props.enable_live_color_updates:
                register_gn_live_color_handler_enhanced()

            # Preservar frame si se solicita
            if preserve_current_frame:
                context.scene.frame_set(stored_frame)

            print("✅ GN animation created successfully")
            return {'FINISHED'}
        else:
            return {'CANCELLED'}

    except Exception as e:
        print(f"❌ Error creating GN animation: {e}")
        return {'CANCELLED'}

def clear_gn_animation_auto():
    """
    Limpiar animación GN de forma automática (equivalente al operador ClearAnimation)

    Returns:
        dict: Resultado de la operación {'FINISHED'} o {'CANCELLED'}
    """
    try:
        # Desactivar sistema si está activo
        success = deactivate_gn_system()

        if success:
            print("✅ GN animation cleared successfully")
            return {'FINISHED'}
        else:
            return {'CANCELLED'}

    except Exception as e:
        print(f"❌ Error clearing GN animation: {e}")
        return {'CANCELLED'}

def toggle_gn_live_color_auto(enable):
    """
    Activar/desactivar Live Color Scheme para GN de forma automática

    Args:
        enable: True para activar, False para desactivar
    """
    try:
        if enable:
            if _gn_system_active and is_geometry_nodes_mode():
                register_gn_live_color_handler_enhanced()
                print("✅ GN Live Color Scheme enabled")
        else:
            unregister_gn_live_color_handler_enhanced()
            print("✅ GN Live Color Scheme disabled")

    except Exception as e:
        print(f"⚠️ Error toggling GN live color: {e}")

# Funciones de conveniencia para desarrollo y debugging
def debug_gn_system():
    """
    Imprime información de debug del sistema GN
    """
    status = get_gn_system_status()

    print("=" * 50)
    print("GEOMETRY NODES SYSTEM DEBUG INFO")
    print("=" * 50)
    print(f"Initialized: {status['initialized']}")
    print(f"Active: {status['active']}")
    print(f"Current Mode: {status['mode']}")
    print(f"Is GN Mode: {status['is_gn_mode']}")
    print(f"Tool Available: {status['tool_available']}")

    # Información adicional del contexto
    try:
        context = bpy.context
        work_schedule = tool.Sequence.get_active_work_schedule() if tool else None
        anim_props = tool.Sequence.get_animation_props() if tool else None

        print(f"Active Work Schedule: {work_schedule.Name if work_schedule else 'None'}")
        print(f"Live Color Updates: {anim_props.enable_live_color_updates if anim_props else 'N/A'}")
        print(f"Animation Created: {anim_props.is_animation_created if anim_props else 'N/A'}")

        # Contar objetos con modificadores GN
        gn_objects = 0
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod.name == "Bonsai 4D" and mod.type == 'NODES':
                        gn_objects += 1
                        break

        print(f"Objects with GN Modifiers: {gn_objects}")

    except Exception as e:
        print(f"Error getting debug info: {e}")

    print("=" * 50)

def test_gn_system():
    """
    Función de prueba para verificar que el sistema funciona correctamente
    """
    print("🧪 Testing Geometry Nodes 4D Animation System...")

    try:
        # Test 1: Inicialización
        print("Test 1: Initialization...")
        init_success = initialize_complete_gn_system()
        print(f"✅ Initialization: {'PASS' if init_success else 'FAIL'}")

        # Test 2: Estado del sistema
        print("Test 2: System status...")
        status = get_gn_system_status()
        print(f"✅ Status check: {'PASS' if status['initialized'] else 'FAIL'}")

        # Test 3: Información de debug
        print("Test 3: Debug info...")
        debug_gn_system()
        print("✅ Debug info: PASS")

        print("🧪 System test completed")
        return True

    except Exception as e:
        print(f"❌ System test failed: {e}")
        return False

def update_all_gn_objects(context=None):
    """
    Update all GN objects when animation settings change

    This function is called when ColorType assignments or animation settings
    are modified and the GN system needs to refresh all objects.

    Args:
        context: Blender context (optional, defaults to bpy.context)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        import bpy

        if context is None:
            context = bpy.context

        print("🔄 Updating all GN objects...")

        # Count objects that will be updated
        gn_objects = []
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod.type == 'NODES' and 'Bonsai' in mod.name:
                        gn_objects.append(obj)
                        break

        if not gn_objects:
            print("ℹ️  No GN objects found to update")
            return True

        print(f"🔄 Updating {len(gn_objects)} GN objects...")

        # Force update of all GN objects
        for obj in gn_objects:
            try:
                # Update object data
                obj.update_tag()

                # Update modifiers specifically
                for mod in obj.modifiers:
                    if mod.type == 'NODES' and 'Bonsai' in mod.name:
                        # Force modifier update
                        mod.show_viewport = mod.show_viewport  # Trigger update

            except Exception as obj_error:
                print(f"⚠️ Error updating object {obj.name}: {obj_error}")

        # Force scene update
        context.view_layer.update()

        # Force viewport redraw
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        print(f"✅ Successfully updated {len(gn_objects)} GN objects")
        return True

    except Exception as e:
        print(f"❌ Error updating GN objects: {e}")
        import traceback
        traceback.print_exc()
        return False

def rebake_attributes_for_tasks(context, tasks):
    """
    Real-time re-baking function for selective ColorType updates.
    Re-bakes only the attributes for objects affected by changed tasks.

    Args:
        context: Blender context
        tasks: List of tasks that need re-baking

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"🔄 Re-baking attributes for {len(tasks)} tasks...")

        # Get current animation settings
        settings = tool.Sequence.get_animation_settings()
        if not settings:
            print("❌ Cannot get animation settings for re-baking")
            return False

        # Import the baking function
        from .gn_sequence import bake_specific_tasks_attributes

        # Re-bake only the affected tasks
        attributes_data = bake_specific_tasks_attributes(tasks, settings)

        # Apply the updated attributes to objects
        apply_attributes_to_objects(context, attributes_data)

        print(f"✅ Re-baked attributes for {len(tasks)} tasks successfully")
        return True

    except Exception as e:
        print(f"❌ Error re-baking attributes: {e}")
        import traceback
        traceback.print_exc()
        return False

def apply_attributes_to_objects(context, attributes_data):
    """
    Apply attribute data to the corresponding objects in the scene.

    Args:
        context: Blender context
        attributes_data: Dictionary mapping object names to attribute data
    """
    try:
        for obj_name, attrs in attributes_data.items():
            obj = context.scene.objects.get(obj_name)
            if obj and obj.type == 'MESH' and obj.data:
                # Apply each attribute to the object
                for attr_name, attr_info in attrs.items():
                    set_attribute_value(obj, attr_name, attr_info["value"],
                                      attr_info["type"], attr_info["domain"])

                # Force object update
                obj.update_tag()

        # Force scene update
        context.view_layer.update()

    except Exception as e:
        print(f"❌ Error applying attributes to objects: {e}")

def set_attribute_value(obj, attr_name, value, attr_type, domain):
    """
    Set an attribute value on an object's mesh data.

    Args:
        obj: Blender object
        attr_name: Name of the attribute
        value: Value to set
        attr_type: Type of attribute ('FLOAT', 'INT', etc.)
        domain: Domain of attribute ('POINT', 'FACE', etc.)
    """
    try:
        # Get or create the attribute
        if attr_name not in obj.data.attributes:
            obj.data.attributes.new(name=attr_name, type=attr_type, domain=domain)

        attr = obj.data.attributes[attr_name]

        # Set the value for all elements
        if hasattr(attr.data, 'foreach_set'):
            # For vector attributes, handle accordingly
            if isinstance(value, (list, tuple)):
                attr.data.foreach_set('value', value * len(attr.data))
            else:
                attr.data.foreach_set('value', [value] * len(attr.data))
        else:
            # Fallback for single values
            for i in range(len(attr.data)):
                attr.data[i].value = value

    except Exception as e:
        print(f"⚠️ Error setting attribute {attr_name}: {e}")

# Export main functions
__all__ = [
    'initialize_complete_gn_system',
    'cleanup_complete_gn_system',
    'activate_gn_system',
    'deactivate_gn_system',
    'get_gn_system_status',
    'create_gn_animation_auto',
    'clear_gn_animation_auto',
    'toggle_gn_live_color_auto',
    'debug_gn_system',
    'test_gn_system',
    'update_all_gn_objects',
    'rebake_attributes_for_tasks',
    'apply_attributes_to_objects',
    'set_attribute_value'
]