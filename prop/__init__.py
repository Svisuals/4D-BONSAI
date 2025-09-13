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


<<<<<<< HEAD

import bpy
from bpy.props import PointerProperty

# --- 1. Importar todo de cada módulo para que sea accesible desde 'prop' ---
# Usamos 'import *' para poner todas las clases y funciones directamente
# en el espacio de nombres de 'prop', lo que resuelve la importación circular.

from .color_manager_prop import *
from .callbacks_prop import *
from .enums_prop import *
from .task_prop import *
from .schedule_prop import *
from .animation_prop import *
from .camera_prop import *
from .ui_helpers_prop import *


# --- 2. Crear una tupla con todas las clases a registrar ---
classes = (
    # De task_prop.py
    TaskFilterRule, BIMTaskFilterProperties, SavedFilterSet,
    TaskcolortypeGroupChoice, Task, TaskResource, TaskProduct,
    BIMTaskTreeProperties,
    
    # De schedule_prop.py
    WorkPlan, BIMWorkPlanProperties, BIMWorkScheduleProperties,
    WorkCalendar, RecurrenceComponent, BIMWorkCalendarProperties,
    
    # De animation_prop.py
    BIMTaskTypeColor, AnimationColorSchemes, AnimationColorTypeGroupItem,
    BIMAnimationProperties,
    
    # De camera_prop.py
    BIMCameraOrbitProperties,
    
    # De ui_helpers_prop.py
    IFCStatus, BIMStatusProperties, DatePickerProperties, BIMDateTextProperties,
=======
import bpy
from bpy.props import PointerProperty

# Import classes from specific modules to avoid duplicates
from .misc import BIMTaskTypeColor, IFCStatus, BIMStatusProperties
from .calendar import WorkCalendar, RecurrenceComponent, BIMWorkCalendarProperties, DatePickerProperties, BIMDateTextProperties
from .filter import TaskFilterRule, BIMTaskFilterProperties, SavedFilterSet
from .task import TaskcolortypeGroupChoice, Task, TaskResource, TaskProduct, BIMTaskTreeProperties
from .schedule import WorkPlan, BIMWorkPlanProperties, BIMWorkScheduleProperties
from .animation import AnimationColorSchemes, AnimationColorTypeGroupItem, BIMAnimationProperties
from .camera_hud import BIMCameraOrbitProperties

# Import manager and callback functions
from .color_manager_prop import UnifiedColorTypeManager
from .filter import update_filter_column
from .camera_hud import update_schedule_display_parent_constraint

# --- 2. Crear una tupla con todas las clases a registrar ---
classes = (
    # Miscellaneous
    BIMTaskTypeColor, IFCStatus, BIMStatusProperties,
    
    # Calendar
    WorkCalendar, RecurrenceComponent, BIMWorkCalendarProperties,
    DatePickerProperties, BIMDateTextProperties,
    
    # Task filtering
    TaskFilterRule, BIMTaskFilterProperties, SavedFilterSet,
    
    # Tasks
    TaskcolortypeGroupChoice, Task, TaskResource, TaskProduct,
    BIMTaskTreeProperties,
    
    # Schedules
    WorkPlan, BIMWorkPlanProperties, BIMWorkScheduleProperties,
    
    # Animation
    AnimationColorSchemes, AnimationColorTypeGroupItem,
    BIMAnimationProperties,
    
    # Camera
    BIMCameraOrbitProperties,
>>>>>>> 7c0c987dee437856081a6ffee6f0b5d6d9efa138
)

# --- 3. Funciones de registro y desregistro para todo el paquete ---
def register():
    """Registra todas las clases de propiedades de este paquete."""
    for cls in classes:
        bpy.utils.register_class(cls)

    BIMWorkScheduleProperties.filters = PointerProperty(type=BIMTaskFilterProperties)
    BIMAnimationProperties.camera_orbit = PointerProperty(type=BIMCameraOrbitProperties)

def unregister():
    """Desregistra todas las clases en orden inverso."""
    if hasattr(BIMWorkScheduleProperties, 'filters'):
        del BIMWorkScheduleProperties.filters
    if hasattr(BIMAnimationProperties, 'camera_orbit'):
        del BIMAnimationProperties.camera_orbit

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
<<<<<<< HEAD
=======

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

>>>>>>> 7c0c987dee437856081a6ffee6f0b5d6d9efa138
