# Debug Optimization Detection - Run in Blender Console
# This will show exactly what's happening with the method detection

def debug_optimization_detection():
    """Debug why optimizations are not being detected"""
    try:
        import bonsai.tool as tool
        print("=== OPTIMIZATION DETECTION DEBUG ===")

        # Check if methods exist
        methods_to_check = [
            'get_animation_product_frames_enhanced_optimized',
            'animate_objects_with_ColorTypes_optimized',
            'clear_objects_animation_optimized'
        ]

        for method_name in methods_to_check:
            has_method = hasattr(tool.Sequence, method_name)
            print(f"  {method_name}: {'[OK]' if has_method else '[MISSING]'}")

            if has_method:
                method = getattr(tool.Sequence, method_name)
                print(f"    Type: {type(method)}")
                print(f"    Callable: {callable(method)}")

        # Check required modules
        print("\n=== REQUIRED MODULES ===")
        try:
            from bonsai.bim.module.sequence import ifc_lookup
            print("  ifc_lookup: [OK]")
        except ImportError as e:
            print(f"  ifc_lookup: [ERROR] {e}")

        try:
            from bonsai.bim.module.sequence import performance_cache
            print("  performance_cache: [OK]")
        except ImportError as e:
            print(f"  performance_cache: [ERROR] {e}")

        try:
            from bonsai.bim.module.sequence import batch_processor
            print("  batch_processor: [OK]")
        except ImportError as e:
            print(f"  batch_processor: [ERROR] {e}")

        # Test manual detection
        print("\n=== MANUAL DETECTION TEST ===")
        if hasattr(tool.Sequence, 'get_animation_product_frames_enhanced_optimized'):
            print("  Manual hasattr check: [OK] - Method should be detected!")
        else:
            print("  Manual hasattr check: [FAIL] - Method not found")

            # List all available methods for debugging
            all_methods = [attr for attr in dir(tool.Sequence) if not attr.startswith('_')]
            optimized_methods = [m for m in all_methods if 'optimized' in m.lower()]
            print(f"  Available optimized methods: {optimized_methods}")

    except Exception as e:
        print(f"DEBUG ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_optimization_detection()