#!/usr/bin/env python3
"""
Script to automatically apply critical fixes to the installed Bonsai version.
This fixes the import errors and missing properties that break 4D scheduling.
"""

import os
import shutil
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

def backup_original_files(bonsai_path, files_to_fix):
    """Create backups of original files before modifying."""
    backup_dir = bonsai_path.parent / "bonsai_backup"
    backup_dir.mkdir(exist_ok=True)
    
    for file_path in files_to_fix:
        full_path = bonsai_path / file_path
        if full_path.exists():
            backup_path = backup_dir / file_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(full_path, backup_path)
            print(f"✅ Backed up: {file_path}")

def apply_filter_fixes(bonsai_path):
    """Apply fixes to filter.py for missing properties and enum values."""
    filter_file = bonsai_path / "bim/module/sequence/prop/filter.py"
    
    if not filter_file.exists():
        print(f"❌ Filter file not found: {filter_file}")
        return False
    
    # Read the current content
    content = filter_file.read_text(encoding='utf-8')
    
    # Fix 1: Add show_saved_filters property
    if 'show_saved_filters' not in content:
        # Find the BIMTaskFilterProperties class and add the property
        old_pattern = '''show_filters: BoolProperty(
        name="Show Filters",
        description="Toggle the visibility of the filter panel",
        default=False
    )'''
        
        new_pattern = '''show_filters: BoolProperty(
        name="Show Filters", 
        description="Toggle the visibility of the filter panel",
        default=False
    )
    
    show_saved_filters: BoolProperty(
        name="Show Saved Filters",
        description="Toggle the visibility of the saved filter sets panel", 
        default=False
    )'''
        
        if old_pattern in content:
            content = content.replace(old_pattern, new_pattern)
            print("✅ Added show_saved_filters property")
    
    # Fix 2: Add fallback for IfcTaskTime enum values
    enum_fallback = '''    # 3. IfcTaskTime columns  
    task_time_columns = SequenceData.data.get("task_time_columns_enum", [])
    
    # If no task time columns are loaded, add common ones manually
    if not task_time_columns:
        task_time_columns = [
            ("ScheduleStart/string", "Schedule Start", "Scheduled start date"),
            ("ScheduleFinish/string", "Schedule Finish", "Scheduled finish date"),
            ("ActualStart/string", "Actual Start", "Actual start date"),
            ("ActualFinish/string", "Actual Finish", "Actual finish date"),
            ("EarlyStart/string", "Early Start", "Early start date"),
            ("EarlyFinish/string", "Early Finish", "Early finish date"),
            ("LateStart/string", "Late Start", "Late start date"),
            ("LateFinish/string", "Late Finish", "Late finish date"),
            ("FreeFloat/string", "Free Float", "Free float duration"),
            ("TotalFloat/string", "Total Float", "Total float duration"),
            ("Duration/string", "Duration", "Task duration"),
            ("RemainingTime/string", "Remaining Time", "Remaining duration"),
            ("Completion/float", "Completion", "Task completion percentage"),
        ]
    
    for name_type, label, desc in task_time_columns:'''
    
    if 'task_time_columns = SequenceData.data.get("task_time_columns_enum", [])' not in content:
        # Find the existing IfcTaskTime section and replace it
        old_tasktime_pattern = '''    # 3. IfcTaskTime columns  
    for name_type, label, desc in SequenceData.data.get("task_time_columns_enum", []):'''
        
        if old_tasktime_pattern in content:
            content = content.replace(old_tasktime_pattern, enum_fallback)
            print("✅ Added IfcTaskTime enum fallback")
    
    # Write the updated content
    filter_file.write_text(content, encoding='utf-8')
    print(f"✅ Updated: {filter_file}")
    return True

def apply_import_fixes(bonsai_path):
    """Apply import fixes to sequence tool files."""
    files_to_fix = [
        "tool/sequence/task_sequence.py",
        "tool/sequence/main_sequence.py", 
        "tool/sequence/utils_sequence.py"
    ]
    
    for file_path in files_to_fix:
        full_path = bonsai_path / file_path
        if not full_path.exists():
            print(f"❌ File not found: {full_path}")
            continue
            
        content = full_path.read_text(encoding='utf-8')
        
        # Fix import statements - handle all variations
        content = content.replace('from ...helper import', 'from bonsai.bim.helper import')
        content = content.replace('from .. import helper', 'import bonsai.bim.helper')
        content = content.replace('helper.parse_datetime', 'bonsai.bim.helper.parse_datetime')
        content = content.replace('helper.parse_duration', 'bonsai.bim.helper.parse_duration')  
        content = content.replace('helper.isodate_duration', 'bonsai.bim.helper.isodate_duration')
        content = content.replace('helper.export_attributes', 'bonsai.bim.helper.export_attributes')
        content = content.replace('helper.import_attributes', 'bonsai.bim.helper.import_attributes')
        
        # Fix property references in task_sequence.py - all instances
        if 'task_sequence.py' in file_path:
            content = content.replace(
                'props = props_sequence.get_task_tree_props()',
                'props = props_sequence.get_work_schedule_props()'
            )
            # Also fix any remaining instances  
            content = content.replace(
                'get_task_tree_props().task_attributes',
                'get_work_schedule_props().task_attributes'
            )
        
        full_path.write_text(content, encoding='utf-8')
        print(f"✅ Updated: {file_path}")
    
    return True

def apply_core_fixes(bonsai_path):
    """Apply fixes to core sequence files."""
    core_file = bonsai_path / "core/sequence/task_management_sequence.py"
    
    if not core_file.exists():
        print(f"❌ Core file not found: {core_file}")
        return False
    
    content = core_file.read_text(encoding='utf-8')
    
    # Fix import with fallback
    old_import = 'from ...data.sequence_data import SequenceData'
    new_import = '''try:
        from ...data.sequence_data import SequenceData
    except ImportError:
        # Fallback for different import structures
        try:
            from ....data.sequence_data import SequenceData
        except ImportError:
            # If data module is not available, skip the reload step
            print("⚠️ SequenceData module not available, skipping data reload")
            return'''
    
    if old_import in content and 'try:' not in content:
        content = content.replace(old_import, new_import)
        core_file.write_text(content, encoding='utf-8')
        print(f"✅ Updated: {core_file}")
    
    return True

def apply_additional_sequence_fixes(bonsai_path):
    """Apply fixes to additional sequence-related files that might have issues."""
    additional_files = [
        "tool/sequence/data_sequence.py",
        "tool/sequence/animation_sequence.py", 
        "tool/sequence/camera_sequence.py",
        "data/sequence_data.py"
    ]
    
    fixes_applied = False
    
    for file_path in additional_files:
        full_path = bonsai_path / file_path
        if not full_path.exists():
            continue
            
        content = full_path.read_text(encoding='utf-8')
        original_content = content
        
        # Fix common import issues
        content = content.replace('from ...helper import', 'from bonsai.bim.helper import')
        content = content.replace('from .. import helper', 'import bonsai.bim.helper')  
        content = content.replace('helper.', 'bonsai.bim.helper.')
        
        # Fix property getter issues
        content = content.replace(
            'props_sequence.get_task_tree_props()',
            'props_sequence.get_work_schedule_props()'
        )
        
        # If file was modified, save it
        if content != original_content:
            full_path.write_text(content, encoding='utf-8')
            print(f"✅ Updated additional file: {file_path}")
            fixes_applied = True
    
    return fixes_applied

def main():
    """Main function to apply all critical fixes."""
    print("🔧 Applying critical fixes to installed Bonsai version...")
    
    # Find Bonsai installation
    bonsai_path = find_bonsai_installation()
    if not bonsai_path:
        print("❌ Could not find Bonsai installation directory")
        print("Please manually apply fixes using CRITICAL_FIXES_NEEDED.md")
        return False
    
    print(f"📂 Found Bonsai at: {bonsai_path}")
    
    # Files that will be modified
    files_to_fix = [
        "bim/module/sequence/prop/filter.py",
        "tool/sequence/task_sequence.py", 
        "tool/sequence/main_sequence.py",
        "tool/sequence/utils_sequence.py",
        "core/sequence/task_management_sequence.py"
    ]
    
    # Create backups
    print("\n📋 Creating backups...")
    backup_original_files(bonsai_path, files_to_fix)
    
    # Apply fixes
    print("\n🔨 Applying fixes...")
    success = True
    
    try:
        success &= apply_filter_fixes(bonsai_path)
        success &= apply_import_fixes(bonsai_path)
        success &= apply_core_fixes(bonsai_path)
        
        # Apply additional fixes to other sequence files
        print("\n🔧 Checking additional sequence files...")
        additional_fixes = apply_additional_sequence_fixes(bonsai_path)
        if additional_fixes:
            print("✅ Additional fixes applied")
        else:
            print("ℹ️ No additional fixes needed")
            
    except Exception as e:
        print(f"❌ Error applying fixes: {e}")
        success = False
    
    if success:
        print("\n🎉 All critical fixes applied successfully!")
        print("📝 Please restart Blender to reload the changes")
        print("✅ The 4D scheduling system should now work correctly")
    else:
        print("\n⚠️ Some fixes could not be applied automatically")
        print("📖 Please refer to CRITICAL_FIXES_NEEDED.md for manual instructions")
    
    return success

if __name__ == "__main__":
    main()