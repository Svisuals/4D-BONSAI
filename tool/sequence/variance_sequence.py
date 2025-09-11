# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>, 2025 Federico Eraso <feraso@svisuals.net>
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

# Importaciones internas
import bonsai.tool as tool
from .props_sequence import PropsSequence

class VarianceSequence(PropsSequence):
    """Maneja el modo de análisis de varianza, incluyendo el cálculo y la coloración."""
    
    _original_colors = {}


    @classmethod
    def has_variance_calculation_in_tasks(cls):
        """
        Verifica si hay cálculo de varianza en las tareas actuales.
        Retorna True si al menos una tarea tiene variance_status calculado.
        """
        try:
            tprops = cls.get_task_tree_props()
            if not tprops or not tprops.tasks:
                return False
            
            variance_count = 0
            for task in tprops.tasks:
                variance_status = getattr(task, 'variance_status', '')
                if variance_status and variance_status.strip():
                    variance_count += 1
            
            print(f"🔍 Found {variance_count} tasks with variance calculation out of {len(tprops.tasks)} total tasks")
            return variance_count > 0
            
        except Exception as e:
            print(f"❌ Error checking variance calculation: {e}")
            return False

    @classmethod
    def clear_variance_colors_only(cls):
        """
        Limpia SOLO los colores 3D de varianza, SIN tocar checkboxes.
        Se usa cuando cambian filtros y no hay cálculo de varianza.
        """
        try:
            print("🧹 Clearing variance 3D colors only (keeping checkboxes)...")
            
            # Restaurar colores originales si están guardados
            if hasattr(cls, '_original_colors') and cls._original_colors:
                restored_count = 0
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                        if obj.name in cls._original_colors and hasattr(obj, 'color'):
                            try:
                                original_color = cls._original_colors[obj.name]
                                obj.color = original_color
                                restored_count += 1
                                print(f"🔄 Restored color for {obj.name}")
                            except Exception as e:
                                print(f"❌ Error restoring color for {obj.name}: {e}")
                
                print(f"✅ Restored {restored_count} objects to original colors")
                
                # Forzar actualización del viewport
                bpy.context.view_layer.update()
            else:
                print("ℹ️ No original colors to restore")
                
        except Exception as e:
            print(f"❌ Error clearing variance colors only: {e}")
            import traceback
            traceback.print_exc()


    @classmethod
    def clear_variance_color_mode(cls):
        """
        Limpia el modo de color de varianza y restaura colores originales.
        Se llama cuando se limpia varianza o cambia tipo de cronograma.
        """
        try:
            print("🧹 CLEAR_VARIANCE_COLOR_MODE: Starting cleanup process...")
            
            # Desactivar todos los checkboxes de varianza
            tprops = cls.get_task_tree_props()
            if tprops:
                cleared_checkboxes = 0
                total_tasks = len(tprops.tasks)
                print(f"🔍 Found {total_tasks} total tasks")
                
                for task in tprops.tasks:
                    if getattr(task, 'is_variance_color_selected', False):
                        task.is_variance_color_selected = False
                        cleared_checkboxes += 1
                        print(f"✅ Cleared checkbox for task {task.ifc_definition_id}")
                        
                print(f"✅ Cleared {cleared_checkboxes} variance checkboxes out of {total_tasks} tasks")
            else:
                print("❌ No task tree properties found")
            
            # COMPREHENSIVE COLOR RESTORATION
            restored_count = 0
            
            # Method 1: Try to restore from cached original colors
            if hasattr(cls, '_original_colors') and cls._original_colors:
                print(f"🔄 Attempting to restore from cached colors ({len(cls._original_colors)} stored)")
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                        if obj.name in cls._original_colors and hasattr(obj, 'color'):
                            try:
                                original_color = cls._original_colors[obj.name]
                                obj.color = original_color
                                restored_count += 1
                                print(f"✅ Restored cached color for {obj.name}")
                            except Exception as e:
                                print(f"❌ Error restoring cached color for {obj.name}: {e}")
                
                # Limpiar cache de colores originales
                cls._original_colors = {}
                print("🧹 Cleared original colors cache")
            
            # Method 2: If no cached colors or insufficient restoration, reset to default colors
            if restored_count == 0:
                print("🔄 No cached colors found, resetting all IFC objects to default gray")
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                        try:
                            # Reset to default gray color
                            obj.color = (0.8, 0.8, 0.8, 1.0)
                            obj.hide_viewport = False
                            obj.hide_render = False
                            restored_count += 1
                        except Exception as e:
                            print(f"❌ Error resetting color for {obj.name}: {e}")
            
            print(f"✅ Total objects reset: {restored_count}")
            
            # Method 3: Force complete viewport refresh
            try:
                # Clear animation data that might be affecting colors
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and obj.animation_data:
                        obj.animation_data_clear()
                
                # Force viewport update
                bpy.context.view_layer.update()
                
                # Force redraw of all 3D viewports
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.shading.color_type = 'OBJECT'  # Ensure object colors are visible
                
                print("🔄 Forced complete viewport refresh")
                
            except Exception as e:
                print(f"⚠️ Error during viewport refresh: {e}")
                
        except Exception as e:
            print(f"❌ Error clearing variance color mode: {e}")
            import traceback
            traceback.print_exc()


    @classmethod 
    def update_individual_variance_colors(cls):
        """
        Actualiza colores basado en checkboxes individuales de cada tarea.
        Cada tarea funciona independientemente.
        """
        try:
            print("🎯 Updating individual variance colors...")
            
            # Asegurar viewport correcto
            cls._ensure_viewport_shading()
            
            # Obtener tareas
            tprops = cls.get_task_tree_props()
            if not tprops:
                print("❌ No task tree properties found")
                return
            
            # Guardar colores originales la primera vez (si no están guardados)
            if not hasattr(cls, '_original_colors'):
                cls._original_colors = {}
                for obj in bpy.context.scene.objects:
                    if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                        if hasattr(obj, 'color'):
                            cls._original_colors[obj.name] = tuple(obj.color)
                print(f"💾 Saved original colors for {len(cls._original_colors)} objects")
            
            # Identificar tareas con checkbox activo
            variance_selected_tasks = [t for t in tprops.tasks if getattr(t, 'is_variance_color_selected', False)]
            
            print(f"🔍 Found {len(variance_selected_tasks)} tasks with active variance checkbox")
            if variance_selected_tasks:
                for task in variance_selected_tasks:
                    print(f"  📋 Task {task.ifc_definition_id}: {task.name} (Status: {getattr(task, 'variance_status', 'No status')})")
            else:
                print("🎯 No active checkboxes → restoring original colors")
                # Restaurar colores originales de todos los objetos IFC
                mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
                restored_count = 0
                
                for obj in mesh_objects:
                    element = tool.Ifc.get_entity(obj)
                    if element and hasattr(obj, 'color'):
                        try:
                            # Usar color guardado o blanco por defecto
                            if hasattr(cls, '_original_colors') and obj.name in cls._original_colors:
                                original_color = cls._original_colors[obj.name]
                                print(f"🔄 Restoring saved color for {obj.name}: {original_color}")
                            else:
                                original_color = (1.0, 1.0, 1.0, 1.0)  # Blanco por defecto
                                print(f"🔄 Using default color for {obj.name}")
                            
                            obj.color = original_color
                            restored_count += 1
                            
                        except Exception as e:
                            print(f"❌ Error restoring color for {obj.name}: {e}")
                
                print(f"✅ Restored {restored_count} objects to original colors")
                
                # No limpiar cache aquí - mantener colores guardados para futuros usos
                
                # Forzar actualización del viewport
                bpy.context.view_layer.update()
                return
            
            # Crear mapeo de objetos a tareas
            object_to_task_map = cls._build_object_task_mapping(tprops.tasks)
            
            # Contar objetos mesh en la escena
            mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
            ifc_objects = []
            
            for obj in mesh_objects:
                element = tool.Ifc.get_entity(obj)
                if element:
                    ifc_objects.append(obj)
            
            print(f"🔍 Scene analysis: {len(mesh_objects)} mesh objects, {len(ifc_objects)} have IFC data, {len(object_to_task_map)} task mappings")
            
            # Procesar cada objeto en la escena
            processed_count = 0
            colored_count = 0
            
            for obj in mesh_objects:
                element = tool.Ifc.get_entity(obj)
                if not element:
                    print(f"⚠️ {obj.name} → No IFC element → SKIP")
                    continue
                
                processed_count += 1
                
                # Usar el nuevo método para determinar color
                color = cls._get_variance_color_for_object_real(obj, element, object_to_task_map, variance_selected_tasks)
                
                if color is None:
                    # No cambiar color (sin checkboxes activos)
                    continue
                
                # Aplicar color al objeto
                cls._apply_color_to_object_simple(obj, color)
                colored_count += 1
            
            print(f"📊 SUMMARY: Processed {processed_count} objects, {colored_count} got variance colors")
            
            # Forzar actualización del viewport
            bpy.context.view_layer.update()
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            
            print("✅ Individual variance colors updated successfully")
            
        except Exception as e:
            print(f"❌ Error updating individual variance colors: {e}")
            import traceback
            traceback.print_exc()


    @classmethod
    def activate_variance_color_mode(cls):
        """
        Activa el modo de color de varianza integrándose con el sistema existente de ColorTypes
        """
        try:
            print("🎨 Activating variance color mode...")
            
            # Guardar colores originales de objetos antes de cambiarlos
            cls._save_original_object_colors()
            
            # Marcar que el modo varianza está activo
            bpy.context.scene['BIM_VarianceColorModeActive'] = True
            
            # Crear un ColorType group especial para varianza
            cls._create_variance_colortype_group()
            
            # Activar el live color update system
            anim_props = cls.get_animation_props()
            anim_props.enable_live_color_updates = True
            
            # Registrar el handler si no está registrado
            cls.register_live_color_update_handler()
            
            # Trigger immediate color update
            cls._trigger_variance_color_update()
            
            print("✅ Variance color mode activated successfully")
            
        except Exception as e:
            print(f"❌ Error activating variance color mode: {e}")
            import traceback
            traceback.print_exc()

    @classmethod
    def _save_original_object_colors(cls):
        """Guardar los colores originales de todos los objetos"""
        try:
            original_colors = {}
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and hasattr(obj, 'color'):
                    original_colors[obj.name] = tuple(obj.color)
            
            bpy.context.scene['BIM_VarianceOriginalObjectColors'] = original_colors
            print(f"🔄 Saved original colors for {len(original_colors)} objects")
            
        except Exception as e:
            print(f"❌ Error saving original object colors: {e}")

    @classmethod
    def _restore_original_object_colors(cls):
        """Restaurar los colores originales de todos los objetos"""
        try:
            original_colors = bpy.context.scene.get('BIM_VarianceOriginalObjectColors', {})
            restored_count = 0
            
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and hasattr(obj, 'color') and obj.name in original_colors:
                    obj.color = original_colors[obj.name]
                    restored_count += 1
            
            # Limpiar los datos guardados
            if 'BIM_VarianceOriginalObjectColors' in bpy.context.scene:
                del bpy.context.scene['BIM_VarianceOriginalObjectColors']
                
            print(f"✅ Restored original colors for {restored_count} objects")
            
        except Exception as e:
            print(f"❌ Error restoring original object colors: {e}")

    @classmethod
    def deactivate_variance_color_mode(cls):
        """
        Desactiva el modo de color de varianza y restaura los colores originales
        """
        try:
            print("🔄 Deactivating variance color mode...")
            
            # Restaurar colores originales de objetos
            cls._restore_original_object_colors()
            
            # Desmarcar que el modo varianza está activo
            if 'BIM_VarianceColorModeActive' in bpy.context.scene:
                del bpy.context.scene['BIM_VarianceColorModeActive']
            
            # Limpiar datos de varianza
            if 'BIM_VarianceColorTypes' in bpy.context.scene:
                del bpy.context.scene['BIM_VarianceColorTypes']
            
            # Forzar actualización del viewport
            bpy.context.view_layer.update()
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            
            print("✅ Variance color mode deactivated successfully")
            
        except Exception as e:
            print(f"❌ Error deactivating variance color mode: {e}")
            import traceback
            traceback.print_exc()

    @classmethod
    def _create_variance_colortype_group(cls):
        """Crea un grupo de ColorTypes especial para varianza"""
        try:
            # Definir los ColorTypes de varianza
            variance_colortypes = {
                "DELAYED": {
                    "Color": (1.0, 0.2, 0.2),
                    "Transparency": 0.0,
                    "Description": "Tasks that are delayed"
                },
                "AHEAD": {
                    "Color": (0.2, 1.0, 0.2), 
                    "Transparency": 0.0,
                    "Description": "Tasks that are ahead of schedule"
                },
                "ONTIME": {
                    "Color": (0.2, 0.2, 1.0),
                    "Transparency": 0.0, 
                    "Description": "Tasks that are on time"
                },
                "UNSELECTED": {
                    "Color": (0.8, 0.8, 0.8),
                    "Transparency": 0.7,
                    "Description": "Tasks not selected for variance view"
                }
            }
            
            # Crear el archivo de configuración del grupo
            variance_group_data = {
                "name": "VARIANCE_MODE",
                "description": "Special ColorType group for variance analysis mode",
                "ColorTypes": variance_colortypes
            }
            
            # Almacenar en memoria para uso inmediato - convertir a formato serializable
            serializable_colortypes = {}
            for name, data in variance_colortypes.items():
                serializable_colortypes[name] = {
                    "Color": tuple(data["Color"]),  # Asegurar que sea tupla
                    "Transparency": float(data["Transparency"]),
                    "Description": str(data["Description"])
                }
            
            bpy.context.scene['BIM_VarianceColorTypes'] = serializable_colortypes
            
            print("✅ Created variance ColorType group")
            
        except Exception as e:
            print(f"❌ Error creating variance ColorType group: {e}")


    @classmethod  
    def _trigger_variance_color_update(cls):
        """Fuerza una actualización de colores usando el sistema existente"""
        try:
            # Usar el live color update handler existente pero con lógica de varianza
            cls._variance_aware_color_update()
            
        except Exception as e:
            print(f"❌ Error triggering variance color update: {e}")


    @classmethod
    def _variance_aware_color_update(cls):
        """Actualización de colores que tiene en cuenta el modo de varianza"""
        try:
            is_variance_mode = bpy.context.scene.get('BIM_VarianceColorModeActive', False)
            
            if not is_variance_mode:
                # Si no está en modo varianza, usar el sistema normal
                return
            
            print("🎯 Applying variance-aware color update...")
            
            # IMPORTANT: Asegurar que el viewport está en modo Material Preview o Rendered
            cls._ensure_viewport_shading()
            
            # Obtener tareas con varianza seleccionadas
            tprops = cls.get_task_tree_props()
            if not tprops:
                return
                
            variance_selected_tasks = [
                task for task in tprops.tasks 
                if getattr(task, 'is_variance_color_selected', False) and task.variance_status
            ]
            
            variance_colortypes = bpy.context.scene.get('BIM_VarianceColorTypes', {})
            
            # Crear mapeo de objetos IFC a tareas reales
            object_to_task_map = cls._build_object_task_mapping(tprops.tasks)
            
            # Iterar sobre todos los objetos y aplicar colores de varianza
            for obj in bpy.context.scene.objects:
                if obj.type != 'MESH':
                    continue
                    
                element = tool.Ifc.get_entity(obj)
                if not element:
                    continue
                
                # Determinar el color basado en la relación real tarea-objeto
                color = cls._get_variance_color_for_object_real(obj, element, object_to_task_map, variance_selected_tasks)
                
                if color:
                    cls._apply_color_to_object_simple(obj, color)
            
            # Forzar actualización del viewport
            bpy.context.view_layer.update()
            
            # También actualizar el depsgraph
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            
        except Exception as e:
            print(f"❌ Error in variance aware color update: {e}")


    @classmethod
    def _ensure_viewport_shading(cls):
        """Asegurar que el viewport esté en modo Solid con colores de objeto"""
        try:
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            current_shading = space.shading.type
                            print(f"🔍 Current viewport shading: {current_shading}")
                            
                            # Asegurar modo Solid con colores de objeto
                            if current_shading != 'SOLID':
                                space.shading.type = 'SOLID'
                                print("🔄 Changed viewport to Solid mode")
                            
                            if hasattr(space.shading, 'color_type'):
                                space.shading.color_type = 'OBJECT'
                                print("🎨 Set solid shading to OBJECT color mode")
                            break
        except Exception as e:
            print(f"⚠️ Could not ensure viewport shading: {e}")


    @classmethod
    def _build_object_task_mapping(cls, all_tasks):
        """Construye mapeo usando el sistema correcto de Bonsai"""
        object_task_map = {}
        
        print(f"🔍 Building object-task mapping for {len(all_tasks)} tasks using Bonsai system...")
        
        # Usar el método correcto de Bonsai para obtener outputs
        ifc_file = tool.Ifc.get()
        if not ifc_file:
            print("❌ No IFC file available")
            return object_task_map
        
        for task_pg in all_tasks:
            try:
                task_ifc = ifc_file.by_id(task_pg.ifc_definition_id)
                if not task_ifc:
                    continue
                    
                # Usar el método correcto de Bonsai para obtener outputs
                outputs = cls.get_task_outputs(task_ifc)
                
                if outputs:
                    print(f"📋 Task {task_pg.ifc_definition_id} ({task_pg.name}) has {len(outputs)} outputs:")
                    for output in outputs:
                        object_task_map[output.id()] = task_pg
                        print(f"  → Output {output.id()} ({output.Name}) assigned to task")
                else:
                    print(f"❌ Task {task_pg.ifc_definition_id} ({task_pg.name}) has no outputs")
                        
            except Exception as e:
                print(f"❌ Error mapping task {task_pg.ifc_definition_id}: {e}")
                continue
        
        print(f"✅ Built mapping: {len(object_task_map)} object-task relationships")
        return object_task_map


    @classmethod
    def _get_variance_color_for_object_real(cls, obj, element, object_task_map, variance_selected_tasks):
        """Determina color simple y directo"""
        try:
            element_id = element.id()
            assigned_task = object_task_map.get(element_id)
            
            # Si este objeto pertenece a una tarea con checkbox activo
            if assigned_task and getattr(assigned_task, 'is_variance_color_selected', False):
                variance_status = getattr(assigned_task, 'variance_status', '')
                
                # Colorear según status de varianza
                if "Delayed" in variance_status:
                    print(f"🔴 {obj.name} → Task {assigned_task.ifc_definition_id} → DELAYED")
                    return (1.0, 0.2, 0.2, 1.0)  # Rojo
                elif "Ahead" in variance_status:
                    print(f"🟢 {obj.name} → Task {assigned_task.ifc_definition_id} → AHEAD") 
                    return (0.2, 1.0, 0.2, 1.0)  # Verde
                elif "On Time" in variance_status:
                    print(f"🔵 {obj.name} → Task {assigned_task.ifc_definition_id} → ONTIME")
                    return (0.2, 0.2, 1.0, 1.0)  # Azul
                else:
                    print(f"❓ {obj.name} → Task {assigned_task.ifc_definition_id} → Unknown status: '{variance_status}'")
                    return (0.8, 0.8, 0.8, 0.3)  # Gris transparente
            else:
                # Objeto sin tarea seleccionada → gris transparente
                return (0.8, 0.8, 0.8, 0.3)
                
        except Exception as e:
            print(f"❌ Error getting color for object {obj.name}: {e}")
            return (0.8, 0.8, 0.8, 0.3)


    @classmethod
    def _apply_color_to_object_simple(cls, obj, color):
        """Aplicar color solo al objeto (para viewport Solid)"""
        try:
            print(f"🎨 Applying variance color {color} to {obj.name}")
            
            # SOLO aplicar color del objeto (para modo Solid > Object)
            if hasattr(obj, 'color'):
                obj.color = color[:4] if len(color) >= 4 else color[:3] + (1.0,)
                print(f"✅ Set object color for {obj.name}: {obj.color}")
            else:
                print(f"⚠️ Object {obj.name} does not have color property")
                        
        except Exception as e:
            print(f"❌ Error applying simple color to {obj.name}: {e}")
            import traceback
            traceback.print_exc()


    @classmethod
    def clear_schedule_variance(cls):
        """
        Clear schedule variance data, colors and reset objects to their original state.
        Called when clearing variance or switching schedule types.
        """
        try:
            print("🧹 CLEAR_SCHEDULE_VARIANCE: Starting comprehensive cleanup process...")
            
            # STEP 1: Clear variance DATA from all tasks (this was missing!)
            tprops = cls.get_task_tree_props()
            if tprops and tprops.tasks:
                cleared_tasks = 0
                print(f"🧹 CLEAR_SCHEDULE_VARIANCE: Found {len(tprops.tasks)} tasks to clean")
                
                for task in tprops.tasks:
                    # CRITICAL: Clear the variance data properties set by CalculateScheduleVariance
                    if hasattr(task, 'variance_days'):
                        task.variance_days = 0
                        cleared_tasks += 1
                        
                    if hasattr(task, 'variance_status'):
                        task.variance_status = ""
                        
                    # Clear variance color selection checkbox
                    if hasattr(task, 'is_variance_color_selected'):
                        task.is_variance_color_selected = False
                        
                print(f"✅ CLEAR_SCHEDULE_VARIANCE: Cleared variance data from {cleared_tasks} tasks")
            else:
                print("⚠️ CLEAR_SCHEDULE_VARIANCE: No task properties found")
            
            # STEP 2: Clear variance color mode and restore original colors
            print("🧹 CLEAR_SCHEDULE_VARIANCE: Clearing variance color mode...")
            cls.clear_variance_color_mode()
            
            # STEP 3: Remove variance mode flags from scene
            scene_flags_cleared = 0
            if hasattr(bpy.context.scene, 'BIM_VarianceColorModeActive'):
                del bpy.context.scene['BIM_VarianceColorModeActive']
                scene_flags_cleared += 1
                print("🧹 Removed BIM_VarianceColorModeActive flag from scene")
                
            # Clear any other variance-related scene properties
            variance_keys = [key for key in bpy.context.scene.keys() if 'variance' in key.lower()]
            for key in variance_keys:
                try:
                    del bpy.context.scene[key]
                    scene_flags_cleared += 1
                    print(f"🧹 Removed scene property: {key}")
                except Exception as e:
                    print(f"⚠️ Could not remove scene property {key}: {e}")
            
            print(f"✅ CLEAR_SCHEDULE_VARIANCE: Cleared {scene_flags_cleared} scene flags")
            
            # STEP 4: Reset ALL IFC objects to default appearance (comprehensive reset)
            print("🧹 CLEAR_SCHEDULE_VARIANCE: Resetting all IFC objects to default state...")
            reset_objects = 0
            
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                    try:
                        # Reset color to default gray
                        obj.color = (0.8, 0.8, 0.8, 1.0)
                        
                        # Reset visibility
                        obj.hide_viewport = False
                        obj.hide_render = False
                        
                        # Clear any animation data that might be affecting appearance
                        if obj.animation_data:
                            obj.animation_data_clear()
                        
                        # Reset material overrides if any
                        if obj.material_slots:
                            for slot in obj.material_slots:
                                if slot.material:
                                    slot.material.diffuse_color = (0.8, 0.8, 0.8, 1.0)
                        
                        reset_objects += 1
                        
                    except Exception as e:
                        print(f"⚠️ Error resetting object {obj.name}: {e}")
            
            print(f"✅ CLEAR_SCHEDULE_VARIANCE: Reset {reset_objects} objects to default state")
            
            # STEP 5: Force complete viewport refresh
            print("🧹 CLEAR_SCHEDULE_VARIANCE: Forcing viewport refresh...")
            try:
                # Update view layer
                bpy.context.view_layer.update()
                
                # Force redraw of all 3D viewports
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                # Ensure object colors are visible
                                if hasattr(space.shading, 'color_type'):
                                    space.shading.color_type = 'OBJECT'
                                    
                print("✅ CLEAR_SCHEDULE_VARIANCE: Viewport refresh completed")
                
            except Exception as e:
                print(f"⚠️ Error during viewport refresh: {e}")
            
            print("✅ CLEAR_SCHEDULE_VARIANCE: Comprehensive cleanup completed successfully")
            
        except Exception as e:
            print(f"❌ Error in clear_schedule_variance: {e}")
            import traceback
            traceback.print_exc()


























