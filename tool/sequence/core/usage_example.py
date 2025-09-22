"""
Usage example showing how to integrate ColorManager with the original sequence.py
"""

def example_integration():
    """Example of how to use ColorManager in place of sequence.py methods"""

    # Method 1: Direct import and usage
    from color_manager import ColorManager

    print("=== Method 1: Direct ColorManager usage ===")

    # Get all ColorType groups
    groups = ColorManager.get_all_ColorType_groups()
    print(f"Available groups: {groups}")

    # Create a fallback ColorType
    construction_type = ColorManager.create_fallback_ColorType("CONSTRUCTION")
    print(f"Fallback ColorType for CONSTRUCTION:")
    print(f"  Name: {construction_type.name}")
    print(f"  Start color: {construction_type.start_color}")
    print(f"  Active color: {construction_type.in_progress_color}")
    print(f"  End color: {construction_type.end_color}")
    print(f"  Hide at end: {construction_type.hide_at_end}")

    # Check animation colors
    has_colors = ColorManager.has_animation_colors()
    print(f"Has animation colors: {has_colors}")

    print("\n=== Method 2: Compatibility aliases ===")

    # Method 2: Using compatibility aliases (drop-in replacement)
    from color_manager import (
        get_all_ColorType_groups,
        create_fallback_ColorType,
        has_animation_colors
    )

    # These work exactly like the original sequence.py methods
    groups_alias = get_all_ColorType_groups()
    demolition_type = create_fallback_ColorType("DEMOLITION")
    has_colors_alias = has_animation_colors()

    print(f"Groups (via alias): {groups_alias}")
    print(f"Demolition ColorType name: {demolition_type.name}")
    print(f"Demolition hides at end: {demolition_type.hide_at_end}")
    print(f"Has colors (via alias): {has_colors_alias}")

def example_colortype_properties():
    """Show all properties available on a ColorType object"""

    from color_manager import ColorManager

    print("=== ColorType Properties Example ===")

    # Create different types to show variety
    predefined_types = ["CONSTRUCTION", "DEMOLITION", "OPERATION", "LOGISTIC", "NOTDEFINED"]

    for ptype in predefined_types:
        colortype = ColorManager.create_fallback_ColorType(ptype)
        print(f"\n{ptype} ColorType:")
        print(f"  consider_start: {colortype.consider_start}")
        print(f"  consider_active: {colortype.consider_active}")
        print(f"  consider_end: {colortype.consider_end}")
        print(f"  start_color: {colortype.start_color}")
        print(f"  in_progress_color: {colortype.in_progress_color}")
        print(f"  end_color: {colortype.end_color}")
        print(f"  use_start_original_color: {colortype.use_start_original_color}")
        print(f"  use_active_original_color: {colortype.use_active_original_color}")
        print(f"  use_end_original_color: {colortype.use_end_original_color}")
        print(f"  hide_at_end: {colortype.hide_at_end}")

def example_error_handling():
    """Show how the module handles errors gracefully"""

    from color_manager import ColorManager

    print("=== Error Handling Example ===")

    # These should work without Blender installed
    try:
        groups = ColorManager.get_all_ColorType_groups()
        print(f"Groups (no Blender): {groups}")
    except Exception as e:
        print(f"Error getting groups: {e}")

    try:
        group_data = ColorManager.load_ColorType_group_data("NONEXISTENT")
        print(f"Nonexistent group data: {group_data}")
    except Exception as e:
        print(f"Error loading group data: {e}")

    try:
        colortype = ColorManager.load_ColorType_from_group("NONEXISTENT", "CONSTRUCTION")
        print(f"ColorType from nonexistent group: {colortype}")
    except Exception as e:
        print(f"Error loading ColorType: {e}")

if __name__ == "__main__":
    print("ColorManager Usage Examples")
    print("=" * 50)

    try:
        example_integration()
        print("\n" + "=" * 50)
        example_colortype_properties()
        print("\n" + "=" * 50)
        example_error_handling()

        print("\n" + "=" * 50)
        print("[SUCCESS] All examples completed successfully!")
        print("The ColorManager module is ready for use.")

    except Exception as e:
        print(f"[ERROR] Example failed: {e}")
        import traceback
        traceback.print_exc()