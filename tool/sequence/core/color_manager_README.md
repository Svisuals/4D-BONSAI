# ColorManager Module

A standalone color management module for Bonsai BIM sequence animations, extracted from the main sequence.py file for better modularity and reusability.

## Features

- **Standalone Design**: Works independently with optional Blender dependencies
- **ColorType Management**: Handle DEFAULT and custom ColorType groups
- **Color Scheme Operations**: Create, load, and manage animation color schemes
- **Animation Application**: Apply colors to objects during 4D animations
- **Graceful Degradation**: Functions correctly even without Blender installed

## Quick Start

```python
from bonsai.tool.sequence.core import ColorManager

# Basic usage
groups = ColorManager.get_all_ColorType_groups()
fallback = ColorManager.create_fallback_ColorType("CONSTRUCTION")
```

## Core Methods

### ColorType Group Management
- `load_ColorType_group_data(group_name)` - Load data from specific group
- `get_all_ColorType_groups()` - Get all available groups
- `get_custom_ColorType_groups()` - Get custom groups (excluding DEFAULT)
- `load_ColorType_from_group(group_name, colortype_name)` - Load specific ColorType

### Task ColorType Assignment
- `get_assigned_ColorType_for_task(task, animation_props, active_group_name)` - Get ColorType for task
- `_get_best_ColorType_for_task(task, anim_props)` - Find best matching ColorType

### Color Scheme Operations
- `has_animation_colors()` - Check if animation colors are enabled
- `load_default_animation_color_scheme()` - Reset to original ColorTypes
- `create_default_ColorType_group()` - Create DEFAULT group with standard profiles
- `force_recreate_default_group()` - Force recreation of DEFAULT group
- `sync_active_group_to_json()` - Sync UI group to scene JSON

### Color Application
- `apply_ColorType_animation(obj, frame_data, ColorType, original_color, settings)` - Apply animation
- `apply_state_appearance(obj, ColorType, state, start_frame, end_frame, original_color)` - Apply state
- `_apply_ColorType_to_object(obj, frame_data, ColorType, original_color, settings)` - Apply with transparency
- `set_object_shading()` - Set viewport shading mode
- `create_fallback_ColorType(predefined_type)` - Create fallback ColorType

## Dependencies

### Required
- `json` (standard library)
- `typing` (standard library)

### Optional (with fallbacks)
- `bpy` (Blender Python API) - For Blender integration
- `ifcopenshell` - For IFC entity handling
- `bonsai.tool` - For Bonsai BIM integration

## Usage Patterns

### Basic ColorType Creation
```python
# Create a fallback ColorType for any PredefinedType
colortype = ColorManager.create_fallback_ColorType("CONSTRUCTION")
print(f"ColorType: {colortype.name}")
print(f"Active color: {colortype.in_progress_color}")
```

### Group Management
```python
# Get all available groups
all_groups = ColorManager.get_all_ColorType_groups()

# Get only custom groups
custom_groups = ColorManager.get_custom_ColorType_groups()

# Load specific ColorType from a group
colortype = ColorManager.load_ColorType_from_group("DEFAULT", "CONSTRUCTION")
```

### Animation Application (Blender required)
```python
# Apply ColorType animation to an object
ColorManager.apply_ColorType_animation(
    obj=blender_object,
    frame_data=frame_data_dict,
    ColorType=colortype,
    original_color=(1.0, 1.0, 1.0, 1.0),
    settings=animation_settings
)
```

## Error Handling

The module is designed to handle missing dependencies gracefully:

- **No Blender**: Methods return empty lists/dicts or False
- **No IFC**: Task-related methods return None
- **Missing Bonsai Tools**: Fallback implementations are used

## Testing

Run the test suite to verify functionality:

```bash
cd tool/sequence/core
python test_color_manager.py
```

## File Structure

```
tool/sequence/core/
├── __init__.py              # Module exports
├── color_manager.py         # Main ColorManager class
├── test_color_manager.py    # Test suite
└── color_manager_README.md  # This documentation
```

## Integration with Original sequence.py

The ColorManager can be used as a drop-in replacement for the color management methods in sequence.py:

```python
# Replace sequence.py calls like this:
# sequence.load_ColorType_from_group(group, name)

# With ColorManager calls:
from bonsai.tool.sequence.core import ColorManager
ColorManager.load_ColorType_from_group(group, name)
```

## Backward Compatibility

Compatibility aliases are provided at the module level:
```python
from bonsai.tool.sequence.core.color_manager import load_ColorType_from_group
# This works exactly like the original sequence.py method
```