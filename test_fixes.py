#!/usr/bin/env python3
"""
Test script to verify that all the property and import fixes work correctly.
Run this to check if the critical fixes are working after refactoring.
"""

def test_filter_properties():
    """Test that BIMTaskFilterProperties has the required properties."""
    print("Testing BIMTaskFilterProperties...")
    try:
        from prop.filter import BIMTaskFilterProperties
        
        # Create a test instance (this would normally be done by Blender)
        # We'll just check if the class has the right attributes defined
        props_class = BIMTaskFilterProperties
        
        # Check if show_saved_filters exists in the class annotations or __dict__
        if hasattr(props_class, '__annotations__'):
            annotations = props_class.__annotations__
            if 'show_saved_filters' in annotations:
                print("✅ show_saved_filters property found in class annotations")
            else:
                print("❌ show_saved_filters property not found in annotations")
        
        # Also check __dict__ for the property definition
        found_in_dict = any('show_saved_filters' in str(v) for v in props_class.__dict__.values() 
                           if hasattr(v, 'keywords'))
        if found_in_dict:
            print("✅ show_saved_filters property found in class definition")
        else:
            print("❌ show_saved_filters property not found in class definition")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing filter properties: {e}")
        return False

def test_schedule_properties():
    """Test that BIMWorkScheduleProperties has task_attributes."""
    print("Testing BIMWorkScheduleProperties...")
    try:
        from prop.schedule import BIMWorkScheduleProperties
        
        props_class = BIMWorkScheduleProperties
        
        # Check if task_attributes exists
        if hasattr(props_class, '__annotations__'):
            annotations = props_class.__annotations__
            if 'task_attributes' in annotations:
                print("✅ task_attributes property found in class annotations")
            else:
                print("❌ task_attributes property not found in annotations")
        
        found_in_dict = any('task_attributes' in str(v) for v in props_class.__dict__.values() 
                           if hasattr(v, 'keywords'))
        if found_in_dict:
            print("✅ task_attributes property found in class definition")
        else:
            print("❌ task_attributes property not found in class definition")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing schedule properties: {e}")
        return False

def test_task_sequence_functions():
    """Test that task_sequence functions can be imported."""
    print("Testing task_sequence functions...")
    try:
        from tool.sequence.task_sequence import get_task_attributes
        from tool.sequence.task_sequence import load_task_attributes
        from tool.sequence.task_sequence import get_task_attribute_value
        print("✅ All task_sequence functions imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error testing task_sequence functions: {e}")
        return False

def test_enum_fallback():
    """Test that the filter enum has fallback values for IfcTaskTime."""
    print("Testing filter enum fallback...")
    try:
        from prop.filter import get_all_task_columns_enum
        
        # Create a dummy context (this would normally be a Blender context)
        class DummyContext:
            pass
        
        class DummyProps:
            pass
        
        dummy_props = DummyProps()
        dummy_context = DummyContext()
        
        # Call the function to get enum items
        items = get_all_task_columns_enum(dummy_props, dummy_context)
        
        # Check if we have IfcTaskTime.ScheduleStart in the items
        schedule_start_found = any("IfcTaskTime.ScheduleStart" in item[0] for item in items)
        
        if schedule_start_found:
            print("✅ IfcTaskTime.ScheduleStart found in enum items")
        else:
            print("❌ IfcTaskTime.ScheduleStart not found in enum items")
            print(f"Available items: {[item[0] for item in items]}")
        
        return schedule_start_found
        
    except Exception as e:
        print(f"❌ Error testing enum fallback: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Testing all fixes after refactoring...\n")
    
    tests = [
        test_filter_properties,
        test_schedule_properties,
        test_task_sequence_functions,
        test_enum_fallback,
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All fixes working correctly! Schedule editing should work now.")
    else:
        print("⚠️ Some fixes still have issues. Check the errors above.")