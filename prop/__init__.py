"""Property Groups for 4D BIM scheduling - Modular Organization.

This package contains PropertyGroup classes organized thematically:
- animation.py: Animation, colors and colortype management
- camera_hud.py: Camera, orbit and HUD properties  
- task.py: Core Task properties, resources and products
- schedule.py: WorkSchedules and WorkPlans
- filter.py: Task filtering logic
- calendar.py: Calendar properties and date picker
- misc.py: Miscellaneous properties

All PropertyGroups maintain full compatibility with the original prop.py implementation.
"""

# Import all PropertyGroups to make them available when importing from prop
from .animation import (
    UnifiedColorTypeManager,
    AnimationColorSchemes,
    AnimationColorTypeGroupItem,
    BIMAnimationProperties
)

from .camera_hud import (
    BIMCameraOrbitProperties
)

from .task import (
    TaskcolortypeGroupChoice,
    Task,
    TaskResource,
    TaskProduct,
    BIMTaskTreeProperties
)

from .schedule import (
    WorkPlan,
    BIMWorkPlanProperties,
    BIMWorkScheduleProperties
)

from .filter import (
    TaskFilterRule,
    BIMTaskFilterProperties,
    SavedFilterSet
)

from .calendar import (
    WorkCalendar,
    RecurrenceComponent,
    BIMWorkCalendarProperties,
    DatePickerProperties,
    BIMDateTextProperties
)

from .misc import (
    BIMTaskTypeColor,
    IFCStatus,
    BIMStatusProperties
)

# Export all classes for easy importing
__all__ = [
    # Animation
    'UnifiedColorTypeManager',
    'AnimationColorSchemes',
    'AnimationColorTypeGroupItem',
    'BIMAnimationProperties',
    
    # Camera & HUD
    'BIMCameraOrbitProperties',
    
    # Tasks
    'TaskcolortypeGroupChoice',
    'Task',
    'TaskResource',
    'TaskProduct',
    'BIMTaskTreeProperties',
    
    # Schedules
    'WorkPlan',
    'BIMWorkPlanProperties',
    'BIMWorkScheduleProperties',
    
    # Filters
    'TaskFilterRule',
    'BIMTaskFilterProperties',
    'SavedFilterSet',
    
    # Calendar
    'WorkCalendar',
    'RecurrenceComponent',
    'BIMWorkCalendarProperties',
    'DatePickerProperties',
    'BIMDateTextProperties',
    
    # Miscellaneous
    'BIMTaskTypeColor',
    'IFCStatus',
    'BIMStatusProperties'
]