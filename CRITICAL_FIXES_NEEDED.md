# 🚨 CRITICAL FIXES NEEDED FOR BONSAI 4D SYSTEM

## Problem Description
The errors show that Blender is using the **installed version** of Bonsai (in `AppData\Roaming\Blender Foundation\Blender\4.5\extensions`) rather than the local refactored version. These fixes need to be applied to the installed version for the system to work.

## Error 1: Missing IfcTaskTime Enum Values
**Error:** `enum "IfcTaskTime.ScheduleStart" not found`
**File:** `bonsai\bim\module\sequence\prop\filter.py`

### Fix Required:
In the function `get_all_task_columns_enum`, add fallback values for IfcTaskTime columns:

```python
# 3. IfcTaskTime columns  
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
```

## Error 2: Missing show_saved_filters Property
**File:** `bonsai\bim\module\sequence\prop\filter.py`

### Fix Required:
Add this property to `BIMTaskFilterProperties` class:

```python
show_saved_filters: BoolProperty(
    name="Show Saved Filters",
    description="Toggle the visibility of the saved filter sets panel",
    default=False
)
```

## Error 3: Import Errors in Helper Functions
**Files:** Multiple tool/sequence files

### Fix Required:
Replace all instances of:
- `from ...helper import` → `from bonsai.bim.helper import`
- `helper.parse_datetime` → `bonsai.bim.helper.parse_datetime`

Specific files that need this fix:
- `tool\sequence\task_sequence.py`
- `tool\sequence\main_sequence.py` 
- `tool\sequence\utils_sequence.py`

## Error 4: Incorrect Property Reference
**File:** `tool\sequence\task_sequence.py`

### Fix Required:
In functions `get_task_attributes()`, `load_task_attributes()`, and `get_task_attribute_value()`:

Replace:
```python
props = props_sequence.get_task_tree_props()
```

With:
```python
props = props_sequence.get_work_schedule_props()
```

## Error 5: Import Error in Core Module  
**File:** `core\sequence\task_management_sequence.py`

### Fix Required:
Replace:
```python
from ...data.sequence_data import SequenceData
```

With:
```python
try:
    from ...data.sequence_data import SequenceData
except ImportError:
    # Fallback for different import structures
    try:
        from ....data.sequence_data import SequenceData
    except ImportError:
        # If data module is not available, skip the reload step
        print("⚠️ SequenceData module not available, skipping data reload")
        return
```

## How to Apply These Fixes

### Option 1: Manual Edit (Recommended)
1. Navigate to: `C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\local\lib\python3.11\site-packages\bonsai\bim\module\sequence\`
2. Edit each file mentioned above with the corresponding fixes
3. Restart Blender to reload the changes

### Option 2: Replace Installation
1. Copy the corrected files from this refactored version
2. Replace the corresponding files in the installed Bonsai location
3. Restart Blender

### Option 3: Development Mode
1. Modify Blender to use this local refactored version instead of the installed one
2. Update Python path to point to the local version

## Verification
After applying fixes, these operations should work without errors:
- ✅ Opening schedule UI panels
- ✅ Editing task properties  
- ✅ Using filters with IfcTaskTime properties
- ✅ Saving and loading filter sets

## Files Affected
- `prop/filter.py` (2 fixes)
- `tool/sequence/task_sequence.py` (3 fixes)
- `tool/sequence/main_sequence.py` (1 fix)
- `tool/sequence/utils_sequence.py` (1 fix)  
- `core/sequence/task_management_sequence.py` (1 fix)

## Status: URGENT - SYSTEM NON-FUNCTIONAL WITHOUT THESE FIXES
The 4D scheduling system is currently broken due to these import and property issues introduced during refactoring.