#!/usr/bin/env python3
"""
Test script to verify imports are working correctly after refactoring.
Run this to check if all critical modules can be imported without errors.
"""

def test_task_sequence_imports():
    """Test that task_sequence.py imports work correctly."""
    print("Testing task_sequence imports...")
    try:
        from tool.sequence.task_sequence import get_task_attributes
        print("✅ get_task_attributes imported successfully")
        
        from tool.sequence.task_sequence import get_task_time_attributes
        print("✅ get_task_time_attributes imported successfully")
        
        from tool.sequence.task_sequence import get_work_time_attributes
        print("✅ get_work_time_attributes imported successfully")
        
        from tool.sequence.task_sequence import get_work_plan_attributes
        print("✅ get_work_plan_attributes imported successfully")
        
    except Exception as e:
        print(f"❌ Error importing task_sequence functions: {e}")
        return False
    return True

def test_main_sequence_imports():
    """Test that main_sequence.py imports work correctly."""
    print("Testing main_sequence imports...")
    try:
        from tool.sequence.main_sequence import Sequence
        print("✅ Sequence class imported successfully")
        
    except Exception as e:
        print(f"❌ Error importing main_sequence: {e}")
        return False
    return True

def test_utils_sequence_imports():
    """Test that utils_sequence.py imports work correctly."""
    print("Testing utils_sequence imports...")
    try:
        from tool.sequence.utils_sequence import get_work_time_attributes
        print("✅ utils_sequence functions imported successfully")
        
    except Exception as e:
        print(f"❌ Error importing utils_sequence: {e}")
        return False
    return True

def test_bonsai_bim_helper():
    """Test that bonsai.bim.helper is accessible."""
    print("Testing bonsai.bim.helper access...")
    try:
        import bonsai.bim.helper
        from bonsai.bim.helper import draw_attributes, parse_datetime
        print("✅ bonsai.bim.helper imported successfully")
        print("✅ draw_attributes function accessible")
        print("✅ parse_datetime function accessible")
        
    except Exception as e:
        print(f"❌ Error importing bonsai.bim.helper: {e}")
        return False
    return True

if __name__ == "__main__":
    print("🔍 Testing imports after refactoring...\n")
    
    tests = [
        test_bonsai_bim_helper,
        test_task_sequence_imports,
        test_main_sequence_imports,
        test_utils_sequence_imports,
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All imports working correctly! Task editing should work now.")
    else:
        print("⚠️ Some imports still have issues. Check the errors above.")