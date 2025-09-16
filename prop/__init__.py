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
    GNObjectReference, BIMTaskTypeColor, AnimationColorSchemes, AnimationColorTypeGroupItem,
    BIMAnimationProperties, BIM_GN_Controller_Properties,
    
    # De camera_prop.py
    BIMCameraOrbitProperties,
    
    # De ui_helpers_prop.py
    IFCStatus, BIMStatusProperties, DatePickerProperties, BIMDateTextProperties,
)

# --- 3. Funciones de registro y desregistro para todo el paquete ---
def register():
    """Registra todas las clases de propiedades de este paquete."""
    for cls in classes:
        bpy.utils.register_class(cls)

    BIMWorkScheduleProperties.filters = PointerProperty(type=BIMTaskFilterProperties)
    BIMAnimationProperties.camera_orbit = PointerProperty(type=BIMCameraOrbitProperties)
    bpy.types.Object.BonsaiGNController = PointerProperty(type=BIM_GN_Controller_Properties)

def unregister():
    """Desregistra todas las clases en orden inverso."""
    if hasattr(BIMWorkScheduleProperties, 'filters'):
        del BIMWorkScheduleProperties.filters
    if hasattr(BIMAnimationProperties, 'camera_orbit'):
        del BIMAnimationProperties.camera_orbit
    if hasattr(bpy.types.Object, 'BonsaiGNController'):
        del bpy.types.Object.BonsaiGNController

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
