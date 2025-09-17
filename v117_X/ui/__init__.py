"""User Interface (UI) Panels for 4D BIM Scheduling - Modular Organization.

This package contains the Panel (bpy.types.Panel) and UIList (bpy.types.UIList) 
classes, thematically organized to build the addon's interface in Blender.

The structure is as follows:
- panels_schedule.py: Panels for managing schedules, tasks, variance analysis, and ICOM.
- panels_animation.py: Panels dedicated to 4D animation configuration, color schemes, camera control, orbit, and HUD settings.
- panels_workplan.py: Panels for managing Work Plans and Calendars.
- elements.py: Contains reusable UI elements, primarily the UIList classes that display data lists.

The __init__.py file acts as an orchestrator, importing all components and managing 
their centralized registration and unregistration in Blender.
"""


import bpy

# 1. Importar todas las clases desde los nuevos módulos de UI
from .animation_ui import (
    BIM_PT_animation_tools,
    BIM_PT_animation_color_schemes,
)
from .lists_ui import (
    BIM_UL_animation_group_stack,
    BIM_UL_task_columns,
    BIM_UL_task_filters,
    BIM_UL_saved_filter_sets,
    BIM_UL_task_inputs,
    BIM_UL_task_resources,
    BIM_UL_animation_colors,
    BIM_UL_task_outputs,
    BIM_UL_product_input_tasks,
    BIM_UL_product_output_tasks,
    BIM_UL_tasks,
)
from .management_ui import (
    BIM_PT_work_plans,
    BIM_PT_work_calendars,
    BIM_PT_4D_Tools,
)
from .schedule_ui import (
    BIM_PT_colortype_maintenance,
    BIM_PT_work_schedules,
    BIM_PT_task_icom,
    BIM_PT_variance_analysis,
)
from .panels_schedule import (
    BIM_PT_status,
)

# 2. Agrupar todas las clases en una sola tupla para facilitar el registro
classes = (
    # Paneles de Animación
    BIM_PT_animation_tools,
    BIM_PT_animation_color_schemes,
    # Clases de Listas (UIList)
    BIM_UL_animation_group_stack,
    BIM_UL_task_columns,
    BIM_UL_task_filters,
    BIM_UL_saved_filter_sets,
    BIM_UL_task_inputs,
    BIM_UL_task_resources,
    BIM_UL_animation_colors,
    BIM_UL_task_outputs,
    BIM_UL_product_input_tasks,
    BIM_UL_product_output_tasks,
    BIM_UL_tasks,
    # Paneles de Gestión
    BIM_PT_work_plans,
    BIM_PT_work_calendars,
    BIM_PT_4D_Tools,
    # Paneles de Cronograma
    BIM_PT_status,
    BIM_PT_colortype_maintenance,
    BIM_PT_work_schedules,
    BIM_PT_task_icom,
    BIM_PT_variance_analysis,
)

# 3. Funciones de registro y des-registro para este paquete de UI
def register():
    """Registra todas las clases de UI de este módulo."""
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    """Des-registra todas las clases de UI en orden inverso."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)