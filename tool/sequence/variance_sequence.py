# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>
#
# This file is part of Bonsai.
#
# Bonsai is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Bonsai is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai.  If not, see <http://www.gnu.org/licenses/>.



import bpy
import traceback
import bonsai.tool as tool
from . import props_sequence
from . import task_sequence

_original_colors = {}


def has_variance_calculation_in_tasks():
    """Verifica si hay cálculo de varianza en las tareas actuales."""
    tprops = props_sequence.get_task_tree_props()
    if not tprops or not tprops.tasks: return False
    return any(getattr(task, 'variance_status', '') for task in tprops.tasks)


def clear_variance_colors_only():
    """Limpia SOLO los colores 3D de varianza, SIN tocar checkboxes."""
    global _original_colors
    if _original_colors:
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and obj.name in _original_colors:
                try:
                    obj.color = _original_colors[obj.name]
                except Exception as e:
                    print(f"❌ Error restoring color for {obj.name}: {e}")
        bpy.context.view_layer.update()


def clear_variance_color_mode():
    """Clear variance color mode and restore original colors"""
    global _original_colors
    
    # Restore original colors
    clear_variance_colors_only()
    
    # Clear the variance color mode flag
    bpy.context.scene['BIM_VarianceColorModeActive'] = False
    
    # Clear stored colors
    _original_colors.clear()

def update_individual_variance_colors():
    """Update variance colors for individual tasks based on their variance status"""
    global _original_colors
    
    # Store original colors if not already stored
    if not _original_colors:
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                _original_colors[obj.name] = tuple(obj.color)
    
    # Get task tree properties
    tprops = props_sequence.get_task_tree_props()
    if not tprops or not tprops.tasks:
        return
    
    # Update colors based on variance status
    import bonsai.tool as tool
    ifc = tool.Ifc.get()
    
    for task_prop in tprops.tasks:
        if not hasattr(task_prop, 'variance_status') or not task_prop.variance_status:
            continue
        
        # Get the IFC task
        task = ifc.by_id(task_prop.ifc_definition_id)
        if not task:
            continue
        
        # Get task outputs (products)
        outputs = task_sequence.get_task_outputs(task)
        
        # Apply variance color to each product's object
        for product in outputs:
            obj = tool.Ifc.get_object(product)
            if not obj:
                continue
            
            # Determine variance color based on status
            variance_status = task_prop.variance_status
            if variance_status == 'AHEAD':
                color = (0.0, 1.0, 0.0, 1.0)  # Green for ahead
            elif variance_status == 'BEHIND':
                color = (1.0, 0.0, 0.0, 1.0)  # Red for behind
            elif variance_status == 'ON_TIME':
                color = (0.0, 0.0, 1.0, 1.0)  # Blue for on time
            else:
                continue  # No variance or unknown status
            
            obj.color = color
    
    # Update viewport
    bpy.context.view_layer.update()

def _variance_aware_color_update():
    """Internal function for variance-aware color updates during animation"""
    if not bpy.context.scene.get('BIM_VarianceColorModeActive', False):
        return
    
    # This function is called during frame changes when variance mode is active
    # It ensures variance colors are maintained during animation playback
    update_individual_variance_colors()

def enable_variance_color_mode():
    """Enable variance color mode"""
    bpy.context.scene['BIM_VarianceColorModeActive'] = True
    update_individual_variance_colors()

def disable_variance_color_mode():
    """Disable variance color mode"""
    clear_variance_color_mode()

def activate_variance_color_mode():
    """Activate variance color mode with full integration"""
    try:
        print("🎨 Activating variance color mode...")
        
        # Save original colors before changing them
        _save_original_object_colors()
        
        # Mark variance mode as active
        bpy.context.scene['BIM_VarianceColorModeActive'] = True
        
        # Create variance ColorType group
        _create_variance_colortype_group()
        
        # Enable live color updates
        from . import props_sequence
        anim_props = props_sequence.get_animation_props()
        anim_props.enable_live_color_updates = True
        
        # Register handler and trigger update
        from . import colortype_sequence
        colortype_sequence.register_live_color_update_handler()
        
        _trigger_variance_color_update()
        
        print("✅ Variance color mode activated successfully")
        
    except Exception as e:
        print(f"❌ Error activating variance color mode: {e}")
        import traceback
        traceback.print_exc()

def _save_original_object_colors():
    """Save original colors of all objects"""
    try:
        original_colors = {}
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and hasattr(obj, 'color'):
                original_colors[obj.name] = tuple(obj.color)
        
        bpy.context.scene['BIM_VarianceOriginalObjectColors'] = original_colors
        print(f"🔄 Saved original colors for {len(original_colors)} objects")
        
    except Exception as e:
        print(f"❌ Error saving original object colors: {e}")

def _restore_original_object_colors():
    """Restore original colors of all objects"""
    try:
        original_colors = bpy.context.scene.get('BIM_VarianceOriginalObjectColors', {})
        
        for obj_name, color in original_colors.items():
            obj = bpy.data.objects.get(obj_name)
            if obj and hasattr(obj, 'color'):
                obj.color = color
        
        print(f"🔄 Restored original colors for {len(original_colors)} objects")
        
    except Exception as e:
        print(f"❌ Error restoring original object colors: {e}")

def deactivate_variance_color_mode():
    """Deactivate variance color mode completely"""
    try:
        print("🎨 Deactivating variance color mode...")
        
        # Restore original colors
        _restore_original_object_colors()
        
        # Clear variance mode flag
        bpy.context.scene['BIM_VarianceColorModeActive'] = False
        
        # Disable live color updates
        from . import props_sequence
        anim_props = props_sequence.get_animation_props()
        anim_props.enable_live_color_updates = False
        
        # Unregister handler
        from . import colortype_sequence
        colortype_sequence.unregister_live_color_update_handler()
        
        # Clear stored data
        if 'BIM_VarianceOriginalObjectColors' in bpy.context.scene:
            del bpy.context.scene['BIM_VarianceOriginalObjectColors']
        
        print("✅ Variance color mode deactivated successfully")
        
    except Exception as e:
        print(f"❌ Error deactivating variance color mode: {e}")

def _create_variance_colortype_group():
    """Create a special ColorType group for variance visualization"""
    import json
    
    scene = bpy.context.scene
    raw_data = scene.get("BIM_AnimationColorSchemesSets", "{}")
    data = json.loads(raw_data) if isinstance(raw_data, str) else (raw_data or {})
    
    # Create variance group
    variance_group = {
        "ColorTypes": [
            {
                "name": "AHEAD",
                "start_color": [0.0, 1.0, 0.0, 1.0],
                "in_progress_color": [0.0, 1.0, 0.0, 1.0],
                "end_color": [0.0, 1.0, 0.0, 1.0],
                "consider_start": True,
                "consider_active": True,
                "consider_end": True
            },
            {
                "name": "BEHIND",
                "start_color": [1.0, 0.0, 0.0, 1.0],
                "in_progress_color": [1.0, 0.0, 0.0, 1.0],
                "end_color": [1.0, 0.0, 0.0, 1.0],
                "consider_start": True,
                "consider_active": True,
                "consider_end": True
            },
            {
                "name": "ON_TIME",
                "start_color": [0.0, 0.0, 1.0, 1.0],
                "in_progress_color": [0.0, 0.0, 1.0, 1.0],
                "end_color": [0.0, 0.0, 1.0, 1.0],
                "consider_start": True,
                "consider_active": True,
                "consider_end": True
            }
        ]
    }
    
    data["VARIANCE"] = variance_group
    scene["BIM_AnimationColorSchemesSets"] = json.dumps(data)

def _trigger_variance_color_update():
    """Trigger immediate variance color update"""
    update_individual_variance_colors()

def has_variance_calculation_in_tasks():
    """Check if variance calculation exists in tasks"""
    tprops = props_sequence.get_task_tree_props()
    if not tprops or not tprops.tasks:
        return False
    return any(getattr(task, 'variance_status', '') for task in tprops.tasks)
    """Limpia el modo de color de varianza y restaura colores originales."""
    global _original_colors
    tprops = props_sequence.get_task_tree_props()
    if tprops:
        for task in tprops.tasks:
            if getattr(task, 'is_variance_color_selected', False):
                task.is_variance_color_selected = False
    
    if _original_colors:
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and tool.Ifc.get_entity(obj) and obj.name in _original_colors:
                obj.color = _original_colors[obj.name]
        _original_colors = {}
    else:
         for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                obj.color = (0.8, 0.8, 0.8, 1.0)
    
    try:
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and obj.animation_data:
                obj.animation_data_clear()
        bpy.context.view_layer.update()
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D': area.tag_redraw()
    except Exception as e:
        print(f"⚠️ Error during viewport refresh: {e}")


def update_individual_variance_colors():
    """Actualiza colores basado en checkboxes individuales de cada tarea."""
    global _original_colors
    _ensure_viewport_shading()
    tprops = props_sequence.get_task_tree_props()
    if not tprops: return
    
    if not _original_colors:
        _original_colors = {obj.name: tuple(obj.color) for obj in bpy.context.scene.objects if obj.type == 'MESH' and hasattr(obj, 'color')}

    variance_selected_tasks = [t for t in tprops.tasks if getattr(t, 'is_variance_color_selected', False)]
    
    if not variance_selected_tasks:
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and tool.Ifc.get_entity(obj) and obj.name in _original_colors:
                obj.color = _original_colors[obj.name]
        bpy.context.view_layer.update()
        return

    object_to_task_map = _build_object_task_mapping(tprops.tasks)
    
    for obj in bpy.context.scene.objects:
        element = tool.Ifc.get_entity(obj)
        if not element or obj.type != 'MESH': continue
        color = _get_variance_color_for_object_real(obj, element, object_to_task_map, variance_selected_tasks)
        if color:
            _apply_color_to_object_simple(obj, color)
    
    bpy.context.view_layer.update()
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D': area.tag_redraw()


def activate_variance_color_mode():
    """Activa el modo de color de varianza."""
    _save_original_object_colors()
    bpy.context.scene['BIM_VarianceColorModeActive'] = True
    _create_variance_colortype_group()
    props_sequence.get_animation_props().enable_live_color_updates = True
    from . import animation_sequence
    animation_sequence.register_live_color_update_handler()
    _trigger_variance_color_update()


def _save_original_object_colors():
    """Guardar los colores originales de todos los objetos"""
    original_colors = {obj.name: tuple(obj.color) for obj in bpy.context.scene.objects if obj.type == 'MESH' and hasattr(obj, 'color')}
    bpy.context.scene['BIM_VarianceOriginalObjectColors'] = original_colors


def _restore_original_object_colors():
    """Restaurar los colores originales de todos los objetos"""
    original_colors = bpy.context.scene.get('BIM_VarianceOriginalObjectColors', {})
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and hasattr(obj, 'color') and obj.name in original_colors:
            obj.color = original_colors[obj.name]
    if 'BIM_VarianceOriginalObjectColors' in bpy.context.scene:
        del bpy.context.scene['BIM_VarianceOriginalObjectColors']


def deactivate_variance_color_mode():
    """Desactiva el modo de color de varianza."""
    _restore_original_object_colors()
    if 'BIM_VarianceColorModeActive' in bpy.context.scene:
        del bpy.context.scene['BIM_VarianceColorModeActive']
    if 'BIM_VarianceColorTypes' in bpy.context.scene:
        del bpy.context.scene['BIM_VarianceColorTypes']
    bpy.context.view_layer.update()
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D': area.tag_redraw()


def _create_variance_colortype_group():
    """Crea un grupo de ColorTypes especial para varianza"""
    variance_colortypes = {
        "DELAYED": {"Color": (1.0, 0.2, 0.2), "Transparency": 0.0},
        "AHEAD": {"Color": (0.2, 1.0, 0.2), "Transparency": 0.0},
        "ONTIME": {"Color": (0.2, 0.2, 1.0), "Transparency": 0.0},
        "UNSELECTED": {"Color": (0.8, 0.8, 0.8), "Transparency": 0.7}
    }
    bpy.context.scene['BIM_VarianceColorTypes'] = variance_colortypes


def _trigger_variance_color_update():
    """Fuerza una actualización de colores."""
    _variance_aware_color_update()


def _variance_aware_color_update():
    """Actualización de colores que tiene en cuenta el modo de varianza"""
    if not bpy.context.scene.get('BIM_VarianceColorModeActive', False): return
    _ensure_viewport_shading()
    tprops = props_sequence.get_task_tree_props()
    if not tprops: return
    variance_selected_tasks = [task for task in tprops.tasks if getattr(task, 'is_variance_color_selected', False) and task.variance_status]
    object_to_task_map = _build_object_task_mapping(tprops.tasks)
    
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH': continue
        element = tool.Ifc.get_entity(obj)
        if not element: continue
        color = _get_variance_color_for_object_real(obj, element, object_to_task_map, variance_selected_tasks)
        if color: _apply_color_to_object_simple(obj, color)

    bpy.context.view_layer.update()
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D': area.tag_redraw()


def _ensure_viewport_shading():
    """Asegurar que el viewport esté en modo Solid con colores de objeto"""
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    if hasattr(space.shading, 'color_type'):
                        space.shading.color_type = 'OBJECT'
                    break


def _build_object_task_mapping(all_tasks):
    """Construye mapeo de objetos a tareas."""
    object_task_map = {}
    ifc_file = tool.Ifc.get()
    if not ifc_file: return object_task_map
    
    for task_pg in all_tasks:
        try:
            task_ifc = ifc_file.by_id(task_pg.ifc_definition_id)
            if not task_ifc: continue
            for output in task_sequence.get_task_outputs(task_ifc):
                object_task_map[output.id()] = task_pg
        except Exception: continue
    return object_task_map


def _get_variance_color_for_object_real(obj, element, object_task_map, variance_selected_tasks):
    """Determina color basado en la relación real tarea-objeto."""
    assigned_task = object_task_map.get(element.id())
    if assigned_task and getattr(assigned_task, 'is_variance_color_selected', False):
        variance_status = getattr(assigned_task, 'variance_status', '')
        if "Delayed" in variance_status: return (1.0, 0.2, 0.2, 1.0)
        elif "Ahead" in variance_status: return (0.2, 1.0, 0.2, 1.0)
        elif "On Time" in variance_status: return (0.2, 0.2, 1.0, 1.0)
    return (0.8, 0.8, 0.8, 0.3)


def _apply_color_to_object_simple(obj, color):
    """Aplicar color solo al objeto para viewport Solid."""
    if hasattr(obj, 'color'):
        obj.color = color[:4] if len(color) >= 4 else tuple(color[:3]) + (1.0,)


def clear_schedule_variance():
    """Limpia datos de varianza, colores y resetea objetos."""
    tprops = props_sequence.get_task_tree_props()
    if tprops and tprops.tasks:
        for task in tprops.tasks:
            if hasattr(task, 'variance_days'): task.variance_days = 0
            if hasattr(task, 'variance_status'): task.variance_status = ""
            if hasattr(task, 'is_variance_color_selected'): task.is_variance_color_selected = False

    clear_variance_color_mode()
    
    for key in [k for k in bpy.context.scene.keys() if 'variance' in k.lower() or k == 'BIM_VarianceColorModeActive']:
        try:
            del bpy.context.scene[key]
        except Exception: pass

    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
            try:
                obj.color = (0.8, 0.8, 0.8, 1.0)
                obj.hide_viewport = False
                obj.hide_render = False
                if obj.animation_data: obj.animation_data_clear()
            except Exception: pass
    
    bpy.context.view_layer.update()
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()
            if area.spaces.active:
                area.spaces.active.shading.color_type = 'OBJECT'