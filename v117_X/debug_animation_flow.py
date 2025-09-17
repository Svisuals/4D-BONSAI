# Debug Animation Flow - Run in Blender Console BEFORE creating animation
# This will show exactly what operators and methods are being called

import bpy
import bonsai.tool as tool

def patch_animation_methods():
    """Patch animation methods to show when they're called"""

    # Store original methods
    original_methods = {}

    # List of methods that might be involved in animation
    methods_to_patch = [
        'get_animation_product_frames',
        'get_animation_product_frames_enhanced',
        'get_product_frames_with_colortypes',
        'animate_objects',
        'animate_objects_with_ColorTypes',
        'apply_colortype_animation',
        'get_animation_product_frames_enhanced_optimized',
        'animate_objects_with_ColorTypes_optimized',
        'clear_objects_animation_optimized'
    ]

    def make_wrapper(method_name, original_method):
        def wrapper(*args, **kwargs):
            print(f"🔍 CALLED: tool.Sequence.{method_name}")
            print(f"   Args: {len(args)} arguments")
            print(f"   Kwargs: {list(kwargs.keys())}")
            result = original_method(*args, **kwargs)
            print(f"   Result: {type(result)} with {len(result) if hasattr(result, '__len__') else '?'} items")
            return result
        return wrapper

    print("🔧 PATCHING ANIMATION METHODS FOR DEBUGGING...")

    for method_name in methods_to_patch:
        if hasattr(tool.Sequence, method_name):
            original_method = getattr(tool.Sequence, method_name)
            original_methods[method_name] = original_method

            # Create wrapper and patch
            wrapper = make_wrapper(method_name, original_method)
            setattr(tool.Sequence, method_name, wrapper)

            print(f"  ✅ Patched: {method_name}")
        else:
            print(f"  ❌ Not found: {method_name}")

    print(f"\n🔧 Patched {len(original_methods)} methods")
    print("Now create your 4D animation and watch the debug output!")

    return original_methods

def restore_original_methods(original_methods):
    """Restore original methods after debugging"""
    for method_name, original_method in original_methods.items():
        setattr(tool.Sequence, method_name, original_method)
    print(f"🔧 Restored {len(original_methods)} original methods")

# Auto-patch when script runs
if __name__ == "__main__":
    original_methods = patch_animation_methods()
    print("\n" + "="*60)
    print("DEBUG PATCHING COMPLETE!")
    print("Now create your 4D animation and watch for [CALLED] messages")
    print("="*60)

# For manual use:
# original_methods = patch_animation_methods()
#
# # ... create your animation ...
#
# restore_original_methods(original_methods)