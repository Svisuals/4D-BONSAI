"""
Test script for ColorManager module to verify it can be imported and used
without Blender dependencies.
"""


def test_color_manager_import():
    """Test that ColorManager can be imported successfully"""
    try:
        from color_manager import ColorManager
        print("[OK] ColorManager imported successfully")
        return True
    except ImportError as e:
        print(f"[ERROR] Failed to import ColorManager: {e}")
        return False

def test_color_manager_methods():
    """Test that ColorManager methods are accessible"""
    try:
        from color_manager import ColorManager

        # Test method existence
        methods_to_test = [
            'load_ColorType_group_data',
            'get_all_ColorType_groups',
            'get_custom_ColorType_groups',
            'load_ColorType_from_group',
            'get_assigned_ColorType_for_task',
            '_get_best_ColorType_for_task',
            'has_animation_colors',
            'load_default_animation_color_scheme',
            'create_default_ColorType_group',
            'force_recreate_default_group',
            'sync_active_group_to_json',
            'apply_ColorType_animation',
            'apply_state_appearance',
            '_apply_ColorType_to_object',
            'set_object_shading',
            'create_fallback_ColorType'
        ]

        missing_methods = []
        for method_name in methods_to_test:
            if not hasattr(ColorManager, method_name):
                missing_methods.append(method_name)

        if missing_methods:
            print(f"[ERROR] Missing methods: {missing_methods}")
            return False
        else:
            print(f"[OK] All {len(methods_to_test)} expected methods are present")
            return True

    except Exception as e:
        print(f"[ERROR] Error testing methods: {e}")
        return False

def test_fallback_colortype():
    """Test creating a fallback ColorType without Blender"""
    try:
        from color_manager import ColorManager

        # This should work even without Blender
        fallback = ColorManager.create_fallback_ColorType("CONSTRUCTION")

        if fallback and hasattr(fallback, 'name') and fallback.name == "CONSTRUCTION":
            print("[OK] Fallback ColorType creation works")
            return True
        else:
            print("[ERROR] Fallback ColorType creation failed")
            return False

    except Exception as e:
        print(f"[ERROR] Error creating fallback ColorType: {e}")
        return False

def test_graceful_degradation():
    """Test that methods handle missing Blender gracefully"""
    try:
        from color_manager import ColorManager

        # These should return empty/None values without Blender but not crash
        groups = ColorManager.get_all_ColorType_groups()
        custom_groups = ColorManager.get_custom_ColorType_groups()
        has_colors = ColorManager.has_animation_colors()
        group_data = ColorManager.load_ColorType_group_data("DEFAULT")

        print("[OK] Methods handle missing Blender dependencies gracefully")
        print(f"  - get_all_ColorType_groups: {groups}")
        print(f"  - get_custom_ColorType_groups: {custom_groups}")
        print(f"  - has_animation_colors: {has_colors}")
        print(f"  - load_ColorType_group_data: {group_data}")
        return True

    except Exception as e:
        print(f"[ERROR] Error in graceful degradation test: {e}")
        return False

if __name__ == "__main__":
    print("Testing ColorManager module...")
    print("=" * 50)

    tests = [
        test_color_manager_import,
        test_color_manager_methods,
        test_fallback_colortype,
        test_graceful_degradation
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        print(f"\nRunning {test.__name__}...")
        if test():
            passed += 1

    print("\n" + "=" * 50)
    print(f"Tests completed: {passed}/{total} passed")

    if passed == total:
        print("[SUCCESS] All tests passed! ColorManager module is working correctly.")
    else:
        print("[WARNING]  Some tests failed. Check the output above for details.")