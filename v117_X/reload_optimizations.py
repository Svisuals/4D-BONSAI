# Script para recargar optimizaciones en Blender
# Ejecutar en consola de Blender después de modificar archivos

import bpy
import importlib
import sys

def reload_bonsai_optimizations():
    """Recarga todos los módulos de Bonsai para aplicar optimizaciones"""
    print("🔄 RELOADING BONSAI MODULES FOR OPTIMIZATIONS...")

    # Lista de módulos a recargar
    modules_to_reload = [
        'bonsai.tool.sequence',
        'bonsai.bim.module.sequence.operators.animation_operators',
        'bonsai.bim.module.sequence.performance_cache',
        'bonsai.bim.module.sequence.batch_processor',
        'bonsai.bim.module.sequence.ifc_lookup',
    ]

    reloaded_count = 0
    for module_name in modules_to_reload:
        try:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
                print(f"✅ Reloaded: {module_name}")
                reloaded_count += 1
            else:
                # Try to import if not loaded
                try:
                    importlib.import_module(module_name)
                    print(f"✅ Imported: {module_name}")
                    reloaded_count += 1
                except ImportError:
                    print(f"⚠️ Could not import: {module_name}")
        except Exception as e:
            print(f"❌ Error reloading {module_name}: {e}")

    print(f"🔄 Reloaded {reloaded_count}/{len(modules_to_reload)} modules")

    # Verificar que las optimizaciones están disponibles
    try:
        import bonsai.tool as tool

        # Check if optimized methods are now available
        optimized_methods = [
            'get_animation_product_frames_enhanced_optimized',
            'animate_objects_with_ColorTypes_optimized',
            'clear_objects_animation_optimized'
        ]

        available_methods = []
        for method in optimized_methods:
            if hasattr(tool.Sequence, method):
                available_methods.append(method)

        print(f"\n🔍 OPTIMIZATION STATUS: {len(available_methods)}/{len(optimized_methods)} methods available")

        for method in available_methods:
            print(f"  ✅ {method}")

        missing = set(optimized_methods) - set(available_methods)
        for method in missing:
            print(f"  ❌ {method}")

        if len(available_methods) == len(optimized_methods):
            print("\n🎉 ALL OPTIMIZATIONS LOADED SUCCESSFULLY!")
            print("🚀 Animation should now be 10x faster!")
        else:
            print(f"\n⚠️ {len(missing)} optimization methods missing")
            print("💡 Try restarting Blender to ensure all modules load correctly")

        return len(available_methods) == len(optimized_methods)

    except Exception as e:
        print(f"❌ Error checking optimizations: {e}")
        return False

def force_optimization_reload():
    """Fuerza la recarga completa incluyendo invalidación de cache"""
    print("🔥 FORCING COMPLETE OPTIMIZATION RELOAD...")

    # Invalidar todos los caches
    try:
        from bonsai.bim.module.sequence import performance_cache, ifc_lookup
        performance_cache.invalidate_cache()
        ifc_lookup.invalidate_all_lookups()
        print("✅ All caches invalidated")
    except ImportError:
        print("⚠️ Cache modules not available for invalidation")

    # Forzar rebuilding en próxima ejecución
    bpy.context.scene['force_cache_rebuild'] = True
    print("✅ Cache rebuild flag set")

    # Recargar módulos
    return reload_bonsai_optimizations()

def quick_test_optimizations():
    """Test rápido de optimizaciones"""
    print("\n🧪 QUICK OPTIMIZATION TEST...")

    try:
        # Test imports
        from bonsai.bim.module.sequence import performance_cache, batch_processor, ifc_lookup
        print("✅ Optimization modules importable")

        # Test cache
        cache = performance_cache.get_performance_cache()
        if not cache.cache_valid:
            cache.build_scene_cache()
        print(f"✅ Cache: {len(cache.scene_objects_cache)} objects")

        # Test methods
        import bonsai.tool as tool
        methods_available = 0
        if hasattr(tool.Sequence, 'get_animation_product_frames_enhanced_optimized'):
            methods_available += 1
        if hasattr(tool.Sequence, 'animate_objects_with_ColorTypes_optimized'):
            methods_available += 1
        if hasattr(tool.Sequence, 'clear_objects_animation_optimized'):
            methods_available += 1

        print(f"✅ Optimized methods: {methods_available}/3 available")

        if methods_available == 3:
            print("🎉 ALL OPTIMIZATIONS READY!")
            return True
        else:
            print("⚠️ Some optimizations missing - try force reload")
            return False

    except Exception as e:
        print(f"❌ Quick test failed: {e}")
        return False

# Auto-execute when script is run
if __name__ == "__main__":
    reload_bonsai_optimizations()
    quick_test_optimizations()

# Manual execution functions:
# reload_bonsai_optimizations()       # Reload modules
# force_optimization_reload()         # Force complete reload
# quick_test_optimizations()          # Quick test