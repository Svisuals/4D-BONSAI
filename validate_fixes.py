#!/usr/bin/env python3
"""
Script to validate that all critical fixes have been properly applied to the Bonsai installation.
Run this after applying fixes to verify everything is working correctly.
"""

import os
import re
from pathlib import Path

def find_bonsai_installation():
    """Find the installed Bonsai directory in Blender extensions."""
    possible_paths = [
        Path.home() / "AppData/Roaming/Blender Foundation/Blender/4.5/extensions/local/lib/python3.11/site-packages/bonsai",
        Path.home() / "AppData/Roaming/Blender Foundation/Blender/4.5/extensions/.local/lib/python3.11/site-packages/bonsai",
        Path.home() / "AppData/Roaming/Blender Foundation/Blender/4.4/extensions/local/lib/python3.11/site-packages/bonsai",
        Path.home() / "AppData/Roaming/Blender Foundation/Blender/4.4/extensions/.local/lib/python3.11/site-packages/bonsai",
    ]
    
    for path in possible_paths:
        if path.exists() and (path / "bim/module/sequence").exists():
            return path
    
    return None

def validate_filter_fixes(bonsai_path):
    """Validate that filter.py fixes have been applied."""
    filter_file = bonsai_path / "bim/module/sequence/prop/filter.py"
    
    if not filter_file.exists():
        return False, "Filter file not found"
    
    content = filter_file.read_text(encoding='utf-8')
    
    # Check 1: show_saved_filters property exists
    if 'show_saved_filters' not in content:
        return False, "Missing show_saved_filters property"
    
    # Check 2: IfcTaskTime enum fallback exists  
    if 'task_time_columns = SequenceData.data.get("task_time_columns_enum", [])' not in content:
        return False, "Missing IfcTaskTime enum fallback"
    
    # Check 3: Fallback enum values exist
    if '"ScheduleStart/string"' not in content:
        return False, "Missing ScheduleStart fallback enum"
    
    return True, "Filter fixes validated"

def validate_import_fixes(bonsai_path):
    """Validate that import fixes have been applied."""
    files_to_check = [
        "tool/sequence/task_sequence.py",
        "tool/sequence/main_sequence.py", 
        "tool/sequence/utils_sequence.py"
    ]
    
    for file_path in files_to_check:
        full_path = bonsai_path / file_path
        if not full_path.exists():
            continue
            
        content = full_path.read_text(encoding='utf-8')
        
        # Check for problematic import patterns
        if 'from ...helper import' in content:
            return False, f"Unfixed relative import in {file_path}"
        
        # Check for correct bonsai.bim.helper usage
        if 'helper.parse_datetime' in content and 'bonsai.bim.helper.parse_datetime' not in content:
            return False, f"Unfixed helper reference in {file_path}"
        
        # Check for property reference fixes in task_sequence.py
        if 'task_sequence.py' in file_path:
            if 'get_task_tree_props().task_attributes' in content:
                return False, "Unfixed task_tree_props reference in task_sequence.py"
    
    return True, "Import fixes validated"

def validate_core_fixes(bonsai_path):
    """Validate that core sequence fixes have been applied."""
    core_file = bonsai_path / "core/sequence/task_management_sequence.py"
    
    if not core_file.exists():
        return True, "Core file not found (optional)"
    
    content = core_file.read_text(encoding='utf-8')
    
    # Check for try/except import handling
    if 'from ...data.sequence_data import SequenceData' in content and 'try:' not in content:
        return False, "Missing import fallback in core file"
    
    return True, "Core fixes validated"

def validate_property_references(bonsai_path):
    """Validate that all property references are correct."""
    sequence_files = list((bonsai_path / "tool/sequence").glob("*.py")) if (bonsai_path / "tool/sequence").exists() else []
    
    for file_path in sequence_files:
        content = file_path.read_text(encoding='utf-8')
        
        # Look for any remaining get_task_tree_props() calls that should be get_work_schedule_props()
        if 'get_task_tree_props()' in content and 'task_attributes' in content:
            return False, f"Potentially incorrect property reference in {file_path.name}"
    
    return True, "Property references validated"

def validate_enum_handling(bonsai_path):
    """Validate that enum handling is robust."""
    filter_file = bonsai_path / "bim/module/sequence/prop/filter.py"
    
    if not filter_file.exists():
        return False, "Filter file missing for enum validation"
    
    content = filter_file.read_text(encoding='utf-8')
    
    # Check that enum functions have proper fallbacks
    if 'SequenceData.data.get(' in content and 'if not' in content:
        return True, "Enum handling validated"
    
    return False, "Missing enum fallback handling"

def main():
    """Main validation function."""
    print("🔍 Validating applied fixes...")
    
    # Find Bonsai installation
    bonsai_path = find_bonsai_installation()
    if not bonsai_path:
        print("❌ Could not find Bonsai installation directory")
        return False
    
    print(f"📂 Validating Bonsai at: {bonsai_path}")
    
    # Run all validations
    validations = [
        ("Filter Fixes", validate_filter_fixes),
        ("Import Fixes", validate_import_fixes),
        ("Core Fixes", validate_core_fixes), 
        ("Property References", validate_property_references),
        ("Enum Handling", validate_enum_handling)
    ]
    
    all_passed = True
    
    for name, validator in validations:
        try:
            passed, message = validator(bonsai_path)
            status = "✅" if passed else "❌"
            print(f"{status} {name}: {message}")
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"❌ {name}: Error during validation - {e}")
            all_passed = False
    
    print(f"\n{'🎉' if all_passed else '⚠️'} Validation {'completed successfully' if all_passed else 'found issues'}")
    
    if all_passed:
        print("✅ All critical fixes have been properly applied")
        print("🚀 The 4D scheduling system should now work correctly")
        print("📝 Restart Blender to ensure all changes are loaded")
    else:
        print("❌ Some fixes are missing or incomplete")
        print("🔧 Please re-run the apply_critical_fixes.py script")
        print("📖 Or manually apply fixes using CRITICAL_FIXES_NEEDED.md")
    
    return all_passed

if __name__ == "__main__":
    main()