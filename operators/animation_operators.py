# File: animation_operators.py
# Description: Animation-related operators for the 4D add-on.

import bpy
import bonsai.tool as tool
import ifcopenshell.util.sequence
from .. import hud_overlay
from datetime import datetime, timedelta
from .schedule_task_operators import snapshot_all_ui_state, restore_all_ui_state

# === Animation operators ===

class CreateAnimation(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.create_animation"
    bl_label = "Create 4D Animation"
    bl_options = {"REGISTER", "UNDO"}

    preserve_current_frame: bpy.props.BoolProperty(default=False)

    def _execute(self, context):
        stored_frame = context.scene.frame_current
        frames = {}
        props = tool.Sequence.get_work_schedule_props()
        anim_props = tool.Sequence.get_animation_props()
        
        # CRITICAL: Check if synchronization mode is enabled
        sync_enabled = getattr(anim_props, "auto_update_on_date_source_change", False)
        print(f"🎬 CREATE_ANIMATION: Synchronization mode {'ENABLED' if sync_enabled else 'DISABLED'}")
        
        ws_id = getattr(props, "active_work_schedule_id", None)
        if not ws_id:
            self.report({'ERROR'}, "No active Work Schedule selected.")
            return {'CANCELLED'}
        work_schedule = tool.Ifc.get().by_id(ws_id)
        if not work_schedule:
            self.report({'ERROR'}, "Active Work Schedule not found in IFC.")
            return {'CANCELLED'}
        
        # CRITICAL FIX: If synchronization is enabled, set unified date range BEFORE creating animation
        if sync_enabled:
            print("🔗 CREATE_ANIMATION: Setting unified date range for synchronized mode")
            try:
                # Calculate unified range from all 4 schedule types
                unified_start, unified_finish = self._get_unified_date_range(work_schedule)
                
                if unified_start and unified_finish:
                    # Store original ranges for reference
                    original_start = getattr(props, "visualisation_start", None)
                    original_finish = getattr(props, "visualisation_finish", None)
                    
                    # Set visualization properties to unified range
                    props.visualisation_start = unified_start.isoformat()
                    props.visualisation_finish = unified_finish.isoformat()
                    
                    print(f"🔗 CREATE_ANIMATION: Set unified range:")
                    print(f"   ORIGINAL: {original_start} to {original_finish}")
                    print(f"   UNIFIED:  {props.visualisation_start} to {props.visualisation_finish}")
                else:
                    print("⚠️ CREATE_ANIMATION: Could not calculate unified range, using current range")
            except Exception as e:
                print(f"⚠️ CREATE_ANIMATION: Error setting unified range: {e}")
                # Continue with current range as fallback
        
        # Get the final date range (unified if sync enabled, or original if not)
        start = getattr(props, "visualisation_start", None)
        finish = getattr(props, "visualisation_finish", None)
        if not start or not finish or "-" in (start, finish):
            self.report({'ERROR'}, "Invalid date range.")
            return {'CANCELLED'}
            
        _ensure_default_group(context)
        _clear_previous_animation(context)
        settings = _get_animation_settings(context)
        try:
            frames = _compute_product_frames(context, work_schedule, settings)
            _apply_colortype_animation(context, frames, settings)
        except Exception as e:
            self.report({'ERROR'}, f"Animation process failed: {e}")
            return {'CANCELLED'}

        # --- Lógica de preservación del fotograma ---
        if self.preserve_current_frame:
            context.scene.frame_set(stored_frame)
            
        self.report({'INFO'}, f"Animation created for {len(frames)} elements.")

        # Levantar la bandera para indicar que la animación ya existe.
        anim_props = tool.Sequence.get_animation_props()
        anim_props.is_animation_created = True

        return {'FINISHED'}

    def execute(self, context):
        try:
            return self._execute(context)
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}
    
    def _get_unified_date_range(self, work_schedule):
        """
        Calculate the unified date range by analyzing ALL 4 schedule types
        Returns the earliest start and latest finish across all types
        Used when synchronization is enabled during animation creation
        """
        from datetime import datetime
        
        if not work_schedule:
            return None, None
        
        all_starts = []
        all_finishes = []
        
        # Check all schedule types: SCHEDULE, ACTUAL, EARLY, LATE
        for schedule_type in ["SCHEDULE", "ACTUAL", "EARLY", "LATE"]:
            start_attr = f"{schedule_type.capitalize()}Start"
            finish_attr = f"{schedule_type.capitalize()}Finish"
            
            print(f"🔍 CREATE_ANIMATION: Analyzing {schedule_type} -> {start_attr}/{finish_attr}")
            
            # Get all tasks from schedule
            root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
            
            def get_all_tasks_recursive(tasks):
                result = []
                for task in tasks:
                    result.append(task)
                    nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested:
                        result.extend(get_all_tasks_recursive(nested))
                return result
            
            all_tasks = get_all_tasks_recursive(root_tasks)
            
            for task in all_tasks:
                start_date = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
                if start_date:
                    all_starts.append(start_date)
                
                finish_date = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
                if finish_date:
                    all_finishes.append(finish_date)
        
        if not all_starts or not all_finishes:
            print("❌ CREATE_ANIMATION: No valid dates found across all schedule types")
            return None, None
        
        unified_start = min(all_starts)
        unified_finish = max(all_finishes)
        
        print(f"✅ CREATE_ANIMATION: Unified range spans {unified_start.strftime('%Y-%m-%d')} to {unified_finish.strftime('%Y-%m-%d')}")
        return unified_start, unified_finish

class ClearAnimation(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.clear_animation"
    bl_label = "Clear 4D Animation"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        _clear_previous_animation(context)
        self.report({'INFO'}, "Previous animation cleared")
        return {'FINISHED'}

    def execute(self, context):
        try:
            return self._execute(context)
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}


class AddAnimationTaskType(bpy.types.Operator):
    bl_idname = "bim.add_animation_task_type"
    bl_label = "Add Task Type"
    bl_options = {"REGISTER", "UNDO"}
    group: bpy.props.EnumProperty(items=[('INPUT','INPUT',''),('OUTPUT','OUTPUT','')], name="Group", default='INPUT')
    name: bpy.props.StringProperty(name="Name", default="New Type")
    animation_type: bpy.props.StringProperty(name="Type", default="")

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        coll = props.task_input_colors if self.group == 'INPUT' else props.task_output_colors
        item = coll.add()
        item.name = self.name or "New Type"
        item.animation_type = self.animation_type or item.name
        try:
            item.color = (1.0, 0.0, 0.0, 1.0)
        except Exception:
            pass
        if self.group == 'INPUT':
            props.active_color_component_inputs_index = len(coll)-1
        else:
            props.active_color_component_outputs_index = len(coll)-1
        try:
            from bonsai.bim.module.sequence.prop import cleanup_all_tasks_colortype_mappings
            cleanup_all_tasks_colortype_mappings(context)
        except Exception:
            pass
        return {'FINISHED'}


class RemoveAnimationTaskType(bpy.types.Operator):
    bl_idname = "bim.remove_animation_task_type"
    bl_label = "Remove Task Type"
    bl_options = {"REGISTER", "UNDO"}
    group: bpy.props.EnumProperty(items=[('INPUT','INPUT',''),('OUTPUT','OUTPUT','')], name="Group", default='INPUT')

    def execute(self, context):
        props = tool.Sequence.get_animation_props()
        if self.group == 'INPUT':
            idx = getattr(props, "active_color_component_inputs_index", 0)
            coll = getattr(props, "task_input_colors", None)
        else:
            idx = getattr(props, "active_color_component_outputs_index", 0)
            coll = getattr(props, "task_output_colors", None)
        if coll is not None and 0 <= idx < len(coll):
            coll.remove(idx)
            if self.group == 'INPUT':
                props.active_color_component_inputs_index = max(0, idx-1)
            else:
                props.active_color_component_outputs_index = max(0, idx-1)
        return {'FINISHED'}


class AddAnimationCamera(bpy.types.Operator):
    """Add a camera specifically for Animation Settings"""
    bl_idname = "bim.add_animation_camera"
    bl_label = "Add Animation Camera"
    bl_description = "Create a new camera for Animation Settings with orbital animation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # For animation cameras, we should try to call the full method if possible
            # but have a fallback to simple creation
            try:
                from . import tool
                cam_obj = tool.Sequence.add_animation_camera()
            except:
                # Fallback to simple camera creation
                cam_data = bpy.data.cameras.new(name="4D_Animation_Camera")
                cam_obj = bpy.data.objects.new(name="4D_Animation_Camera", object_data=cam_data)
                
                # Mark as animation camera
                cam_obj['is_4d_camera'] = True
                cam_obj['is_animation_camera'] = True
                cam_obj['camera_context'] = 'animation'
                
                # Link to scene
                context.collection.objects.link(cam_obj)
                
                # Configure camera settings
                cam_data.lens = 50
                cam_data.clip_start = 0.1
                cam_data.clip_end = 1000
                
                # Position camera with a good default view
                cam_obj.location = (15, -15, 10)
                cam_obj.rotation_euler = (1.1, 0.0, 0.785)
                
                # Set as active camera
                context.scene.camera = cam_obj
            
            # Select the camera
            bpy.ops.object.select_all(action='DESELECT')
            cam_obj.select_set(True)
            context.view_layer.objects.active = cam_obj
            
            self.report({'INFO'}, f"Animation camera '{cam_obj.name}' created and set as active")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create animation camera: {str(e)}")
            return {'CANCELLED'}


# === Helper functions ===

def _sequence_has(attr: str) -> bool:
    try:
        return hasattr(tool.Sequence, attr)
    except Exception:
        return False

def _clear_previous_animation(context) -> None:
    """Función de limpieza unificada y robusta para toda la animación 4D."""
    print("🧹 Iniciando limpieza completa de la animación...")

    try:
        # --- 1. DETENER LA ANIMACIÓN Y DESREGISTRAR TODOS LOS HANDLERS ---
        # Es crucial hacer esto primero para detener cualquier proceso en segundo plano.

        # Detener la reproducción si está activa
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
            print("  - Animación detenida.")

        # Desregistrar el handler del HUD 2D (GPU Overlay)
        if hud_overlay.is_hud_enabled():
            hud_overlay.unregister_hud_handler()
            print("  - Handler del HUD 2D desregistrado.")

        # Desregistrar el handler de Live Color Updates (la causa más probable del problema)
        if hasattr(tool.Sequence, 'unregister_live_color_update_handler'):
            tool.Sequence.unregister_live_color_update_handler()
            print("  - Handler de Live Color Updates desregistrado.")

        # Desregistrar el handler de textos 3D
        if hasattr(tool.Sequence, '_unregister_frame_change_handler'):
            tool.Sequence._unregister_frame_change_handler()
            print("  - Handler de textos 3D desregistrado.")

        # --- 2. LIMPIAR OBJETOS DE LA ESCENA ---
        # Eliminar objetos generados por la animación (textos, barras, etc.)
        for coll_name in ["Schedule_Display_Texts", "Bar Visual", "Schedule_Display_3D_Legend"]:
            if coll_name in bpy.data.collections:
                collection = bpy.data.collections[coll_name]
                for obj in list(collection.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(collection)
                print(f"  - Colección '{coll_name}' y sus objetos eliminados.")

        # Eliminar el objeto 'empty' padre
        parent_empty = bpy.data.objects.get("Schedule_Display_Parent")
        if parent_empty:
            bpy.data.objects.remove(parent_empty, do_unlink=True)
            print("  - Objeto 'Schedule_Display_Parent' eliminado.")

        # --- 3. LIMPIAR DATOS DE ANIMACIÓN DE OBJETOS 3D (PRODUCTOS IFC) ---
        print("  - Limpiando keyframes y restaurando visibilidad de objetos 3D...")
        cleaned_count = 0
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                if obj.animation_data:
                    obj.animation_data_clear()
                    cleaned_count += 1

                # Restaurar estado por defecto
                obj.hide_viewport = False
                obj.hide_render = False
                obj.color = (0.8, 0.8, 0.8, 1.0)
        print(f"  - Keyframes eliminados de {cleaned_count} objetos.")

        # --- 4. RESTAURAR LA LÍNEA DE TIEMPO Y LA UI ---
        if "is_snapshot_mode" in context.scene:
            del context.scene["is_snapshot_mode"]

        restore_all_ui_state(context)
        print("  - Estado de la UI restaurado.")

        context.scene.frame_set(context.scene.frame_start)
        print(f"  - Línea de tiempo reseteada al fotograma {context.scene.frame_start}.")

        print("✅ Limpieza de animación completada.")

    except Exception as e:
        print(f"Bonsai WARNING: Ocurrió un error durante la limpieza de la animación: {e}")
        import traceback
        traceback.print_exc()

def _get_animation_settings(context):
    """Get animation settings with fallback for snapshot independence"""
    try:
        if _sequence_has("get_animation_settings"):
            result = tool.Sequence.get_animation_settings()
            if result is not None:
                return result
    except Exception:
        pass
    
    # Fallback to basic settings independent of Animation Settings
    ws = tool.Sequence.get_work_schedule_props()
    ap = tool.Sequence.get_animation_props()
    
    fallback_settings = {
        "start": getattr(ws, "visualisation_start", None),
        "finish": getattr(ws, "visualisation_finish", None),
        "speed": getattr(ws, "visualisation_speed", 1.0),
        "ColorType_system": getattr(ap, "active_ColorType_system", "ColorTypeS"),
        "ColorType_stack": getattr(ap, "ColorType_stack", None),
        "start_frame": getattr(context.scene, "frame_start", 1),
        "total_frames": max(1, getattr(context.scene, "frame_end", 250) - getattr(context.scene, "frame_start", 1)),
    }
    
    return fallback_settings

def _compute_product_frames(context, work_schedule, settings):
    """Compute product frames with enhanced error handling for snapshots"""
    try:
        # Ensure settings has minimum required values for snapshot
        if not isinstance(settings, dict):
            settings = {"start_frame": 1, "total_frames": 250}
        
        # Add fallback values if dates are None (snapshot independence)
        if settings.get("start") is None and settings.get("finish") is None:
            # For snapshots without Animation Settings, use current scene frame
            current_frame = getattr(context.scene, "frame_current", 1)
            settings = dict(settings)  # Copy to avoid modifying original
            settings.update({
                "start_frame": current_frame,
                "total_frames": 1,  # Single frame for snapshot
                "speed": 1.0
            })
        
        if _sequence_has("get_product_frames_with_colortypes"):
            return tool.Sequence.get_product_frames_with_colortypes(work_schedule, settings)
        if _sequence_has("get_animation_product_frames_enhanced"):
            return tool.Sequence.get_animation_product_frames_enhanced(work_schedule, settings)
        if _sequence_has("get_animation_product_frames"):
            return tool.Sequence.get_animation_product_frames(work_schedule, settings)
        # As last resort, call core directly
        import bonsai.core.sequence as _core
        return _core.get_animation_product_frames(tool.Sequence, work_schedule, settings)
    except Exception as e:
        print(f"Warning: Product frames computation failed, using empty result: {e}")
        return {}

def _apply_colortype_animation(context, product_frames, settings):
    if _sequence_has("apply_colortype_animation"):
        tool.Sequence.apply_colortype_animation(product_frames, settings); return
    if _sequence_has("animate_objects_with_ColorTypes"):
        tool.Sequence.animate_objects_with_ColorTypes(settings, product_frames); return
    if _sequence_has("animate_objects"):
        tool.Sequence.animate_objects(product_frames, settings); return
    import bonsai.core.sequence as _core
    _core.animate_objects(tool.Sequence, product_frames, settings)

def _safe_set(obj, name, value):
    try:
        setattr(obj, name, value)
    except Exception:
        # Silently ignore when the target property doesn't exist
        pass

def _ensure_default_group(context):
    # Ensure internal DEFAULT exists
    try:
        # Note: UnifiedColorTypeManager would need to be imported if available
        # For now, we'll skip this part
        pass
    except Exception:
        pass
    # Ensure UI stack has at least one item (animation_group_stack or colortype_stack)
    try:
        ap = tool.Sequence.get_animation_props()
        # Newer stack
        if hasattr(ap, "animation_group_stack") and len(ap.animation_group_stack) == 0:
            it = ap.animation_group_stack.add()
            it.group = getattr(ap, "ColorType_groups", "") or "DEFAULT"
            _safe_set(it, 'enabled', True)
        # Older stack
        if hasattr(ap, "colortype_stack") and len(ap.colortype_stack) == 0:
            it = ap.colortype_stack.add()
            it.group = getattr(ap, "ColorType_groups", "") or "DEFAULT"
            _safe_set(it, 'enabled', True)
    except Exception:
        pass


# ============================================================================
# ANIMATION CLEANUP OPERATORS (moved from operator.py)
# ============================================================================

class ClearPreviousAnimation(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.clear_previous_animation"
    bl_label = "Reset Animation"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        # CORRECCIÓN: Detener la animación si se está reproduciendo

        # Bajar la bandera, ya que la animación se está limpiando.
        anim_props = tool.Sequence.get_animation_props()
        anim_props.is_animation_created = False
        
        try:
            if bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel(restore_frame=False)
        except Exception as e:
            print(f"Could not stop animation: {e}")

        # Clear snapshot mode flag
        if "is_snapshot_mode" in context.scene:
            del context.scene["is_snapshot_mode"]
            print("✅ Cleared is_snapshot_mode flag")

        # Restore UI state (3D texts, Timeline HUD, etc.)
        try:
            restore_all_ui_state(context)
            print(f"✅ UI state restored")
        except Exception as e:
            print(f"❌ Could not restore UI state: {e}")

        # CORRECCIÓN: Limpieza completa de la animación previa
        try:
            _clear_previous_animation(context)
            
            # Limpiar el grupo de perfil activo en HUD Legend
            try:
                anim_props = tool.Sequence.get_animation_props()
                if anim_props and hasattr(anim_props, 'camera_orbit'):
                    camera_props = anim_props.camera_orbit
                    
                    # Obtener todos los perfiles activos para ocultarlos
                    if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                        all_colortype_names = []
                        for group_item in anim_props.animation_group_stack:
                            group_name = group_item.group
                            from ..prop import UnifiedColorTypeManager
                            group_colortypes = UnifiedColorTypeManager.get_group_colortypes(bpy.context, group_name)
                            if group_colortypes:
                                all_colortype_names.extend(group_colortypes.keys())
                        
                        # Ocultar todos los perfiles poniendo sus nombres en legend_hud_visible_colortypes
                        if all_colortype_names:
                            hidden_colortypes_str = ','.join(set(all_colortype_names))  # usar set() para eliminar duplicados
                            camera_props.legend_hud_visible_colortypes = hidden_colortypes_str
                            print(f"🧹 Hidden colortypes in HUD Legend: {hidden_colortypes_str}")
                    
                    # Limpiar selected_colortypes por si acaso
                    if hasattr(camera_props, 'legend_hud_selected_colortypes'):
                        camera_props.legend_hud_selected_colortypes = set()
                    
                    # Invalidar caché del legend HUD
                    from bonsai.bim.module.sequence.hud_overlay import invalidate_legend_hud_cache
                    invalidate_legend_hud_cache()
                    print("🧹 Active colortype group cleared from HUD Legend")
            except Exception as legend_e:
                print(f"⚠️ Could not clear colortype group: {legend_e}")
            
            self.report({'INFO'}, "Previous animation cleared.")
            context.scene.frame_set(context.scene.frame_start)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to clear previous animation: {e}")
            return {"CANCELLED"}

    def execute(self, context):
        return self._execute(context)


class ClearPreviousSnapshot(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.clear_previous_snapshot"
    bl_label = "Reset Snapshot"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        print(f"🔄 Reset snapshot started")
        
        # CORRECCIÓN: Detener la animación si se está reproduciendo
        try:
            if bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel(restore_frame=False)
                print(f"✅ Animation playback stopped")
        except Exception as e:
            print(f"❌ Could not stop animation: {e}")

        # Clear snapshot mode flag
        if "is_snapshot_mode" in context.scene:
            del context.scene["is_snapshot_mode"]
            print("✅ Cleared is_snapshot_mode flag")

        # Restore UI state (3D texts, Timeline HUD, etc.)
        try:
            restore_all_ui_state(context)
            print(f"✅ UI state restored")
        except Exception as e:
            print(f"❌ Could not restore UI state: {e}")

        # CORRECCIÓN: Limpieza completa de snapshot previo
        try:
            # CRITICAL: Resetear todos los objetos a estado original (usar función existente)
            print(f"🔄 Clearing previous animation...")
            _clear_previous_animation(context)
            print(f"✅ Previous animation cleared")
            
            # Limpiar datos temporales de snapshot
            if hasattr(bpy.context.scene, 'snapshot_data'):
                del bpy.context.scene.snapshot_data
            
            # Limpiar el grupo de perfil activo en HUD Legend
            try:
                anim_props = tool.Sequence.get_animation_props()
                if anim_props and hasattr(anim_props, 'camera_orbit'):
                    camera_props = anim_props.camera_orbit
                    
                    # Obtener todos los perfiles activos para ocultarlos
                    if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                        all_colortype_names = []
                        for group_item in anim_props.animation_group_stack:
                            group_name = group_item.group
                            from ..prop import UnifiedColorTypeManager
                            group_colortypes = UnifiedColorTypeManager.get_group_colortypes(bpy.context, group_name)
                            if group_colortypes:
                                all_colortype_names.extend(group_colortypes.keys())
                        
                        # Ocultar todos los perfiles poniendo sus nombres en legend_hud_visible_colortypes
                        if all_colortype_names:
                            hidden_colortypes_str = ','.join(set(all_colortype_names))  # usar set() para eliminar duplicados
                            camera_props.legend_hud_visible_colortypes = hidden_colortypes_str
                            print(f"🧹 Hidden colortypes in HUD Legend: {hidden_colortypes_str}")
                    
                    # Limpiar selected_colortypes por si acaso
                    if hasattr(camera_props, 'legend_hud_selected_colortypes'):
                        camera_props.legend_hud_selected_colortypes = set()
                    
                    # Invalidar caché del legend HUD
                    from bonsai.bim.module.sequence.hud_overlay import invalidate_legend_hud_cache
                    invalidate_legend_hud_cache()
                    print("🧹 Active colortype group cleared from HUD Legend")
            except Exception as legend_e:
                print(f"⚠️ Could not clear colortype group: {legend_e}")
            
            # --- SNAPSHOT 3D TEXTS RESTORATION ---
            # Clear snapshot mode and restore previous state
            if "is_snapshot_mode" in context.scene:
                del context.scene["is_snapshot_mode"]
                print("📸 Snapshot mode deactivated for 3D texts")
            _restore_3d_texts_state()
            
            self.report({'INFO'}, "Snapshot reset completed")
        except Exception as e:
            print(f"Error during snapshot reset: {e}")
            self.report({'WARNING'}, f"Snapshot reset completed with warnings: {e}")
        
        return {'FINISHED'}
    
    def execute(self, context):
        return self._execute(context)

class SyncAnimationByDate(bpy.types.Operator):
    bl_idname = "bim.sync_animation_by_date"
    bl_label = "Sync Animation by Date"
    bl_options = {"INTERNAL"}
    previous_start_date: bpy.props.StringProperty()
    previous_finish_date: bpy.props.StringProperty()

    def execute(self, context):
        anim_props = tool.Sequence.get_animation_props()
        if not getattr(anim_props, "auto_update_on_date_source_change", False):
            return {'CANCELLED'}
        was_playing = bpy.context.screen.is_animation_playing
        if was_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        try:
            start_date = datetime.fromisoformat(self.previous_start_date)
            finish_date = datetime.fromisoformat(self.previous_finish_date)
            current_frame = context.scene.frame_current
            start_frame = context.scene.frame_start
            end_frame = context.scene.frame_end
            progress = (current_frame - start_frame) / (end_frame - start_frame) if (end_frame - start_frame) > 0 else 0
            current_date = start_date + (finish_date - start_date) * progress
            props = tool.Sequence.get_work_schedule_props()
            new_start_date = datetime.fromisoformat(props.visualisation_start)
            new_finish_date = datetime.fromisoformat(props.visualisation_finish)
            new_duration = (new_finish_date - new_start_date).total_seconds()
            new_progress = (current_date - new_start_date).total_seconds() / new_duration if new_duration > 0 else 0
            new_progress = max(0.0, min(1.0, new_progress))
            new_frame = start_frame + (end_frame - start_frame) * new_progress
            context.scene.frame_set(int(round(new_frame)))
        except (ValueError, TypeError) as e:
            print(f"Sync failed: {e}")
        if was_playing:
            bpy.ops.screen.animation_play()
        return {'FINISHED'}


class SyncAnimationDateSource(bpy.types.Operator):
    """Synchronize date source type during animation playback"""
    bl_idname = "bim.sync_animation_date_source"
    bl_label = "Sync Animation Date Source"
    bl_description = "Switch between schedule types (SCHEDULE, ACTUAL, EARLY, LATE) while maintaining temporal position"
    bl_options = {"REGISTER", "UNDO"}

    new_date_source: bpy.props.StringProperty(
        name="New Date Source",
        description="The schedule type to switch to (e.g. SCHEDULE, ACTUAL, EARLY, LATE)"
    )

    def execute(self, context):
        try:
            # Set flag to prevent interference from update_date_source_type
            context.scene['_synch_in_progress'] = True
            
            props = tool.Sequence.get_work_schedule_props()
            anim_props = tool.Sequence.get_animation_props()
            
            # Validate current state
            current_date_source = getattr(props, "date_source_type", "SCHEDULE")
            if self.new_date_source == current_date_source:
                context.scene['_synch_in_progress'] = False
                return {'CANCELLED'}  # Already using this date source
            
            # CRITICAL: Check if synchronization mode is enabled
            sync_enabled = getattr(anim_props, "auto_update_on_date_source_change", False)
            print(f"🔄 SYNCH: Synchronization mode {'ENABLED' if sync_enabled else 'DISABLED'}")
            
            if not sync_enabled:
                # MODE 1: BEFORE synchronization is activated
                # Each schedule type maintains its independent date ranges
                print("📅 SYNCH: Independent mode - restoring original date ranges")
                return self._execute_independent_mode(context, props, current_date_source)
            else:
                # MODE 2: AFTER synchronization is activated  
                # All schedule types use the same unified temporal range during animation
                print("🔗 SYNCH: Synchronized mode - maintaining unified temporal position")
                return self._execute_synchronized_mode(context, props, anim_props, current_date_source)
            
        except Exception as e:
            print(f"❌ SYNCH: Critical error: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Sync operation failed: {e}")
            return {'CANCELLED'}
        finally:
            # Always clear the flag
            if '_synch_in_progress' in context.scene:
                del context.scene['_synch_in_progress']

    def _execute_independent_mode(self, context, props, current_date_source):
        """
        MODE 1: BEFORE synchronization is activated
        Each schedule type maintains its independent original date ranges
        SCHEDULE: 10/06/2025 - 20/06/2025
        ACTUAL:   18/06/2025 - 28/06/2025  
        When switching SCHEDULE->ACTUAL->SCHEDULE, returns to original 10/06/2025
        """
        try:
            # Store original date ranges for each schedule type
            work_schedule_id = props.active_work_schedule_id
            date_ranges_key = f"original_date_ranges_{work_schedule_id}"
            
            # Use Blender's custom properties for reliable storage
            if date_ranges_key not in context.scene:
                context.scene[date_ranges_key] = {}
            
            # Get the stored ranges as a dictionary
            original_ranges = dict(context.scene[date_ranges_key])
            
            # Store the current range for the current date source (if not already stored)
            current_start = getattr(props, "visualisation_start", None)
            current_finish = getattr(props, "visualisation_finish", None)
            
            if current_start and current_finish and current_date_source not in original_ranges:
                original_ranges[current_date_source] = {
                    'start': current_start,
                    'finish': current_finish
                }
                context.scene[date_ranges_key] = original_ranges
                print(f"💾 SYNCH: Stored original {current_date_source} range: {current_start} to {current_finish}")
            
            print(f"🔄 SYNCH: Switching from {current_date_source} to {self.new_date_source}")
            
            # Check if we have stored ranges for the target date source
            if self.new_date_source in original_ranges:
                # Restore the original range for this date source
                stored_range = original_ranges[self.new_date_source]
                props.date_source_type = self.new_date_source
                props.visualisation_start = stored_range['start']
                props.visualisation_finish = stored_range['finish']
                print(f"🔄 SYNCH: Restored original {self.new_date_source} range: {stored_range['start']} to {stored_range['finish']}")
            else:
                # First time switching to this source, calculate new range
                props.date_source_type = self.new_date_source
                
                work_schedule = tool.Sequence.get_active_work_schedule()
                if work_schedule:
                    new_start, new_finish = tool.Sequence.guess_date_range(work_schedule)
                    if new_start and new_finish:
                        props.visualisation_start = new_start.isoformat()
                        props.visualisation_finish = new_finish.isoformat()
                        
                        # Store this new range for future use
                        original_ranges[self.new_date_source] = {
                            'start': props.visualisation_start,
                            'finish': props.visualisation_finish
                        }
                        context.scene[date_ranges_key] = original_ranges
                        print(f"💾 SYNCH: Calculated and stored new {self.new_date_source} range: {props.visualisation_start} to {props.visualisation_finish}")
                    else:
                        props.date_source_type = current_date_source
                        self.report({'ERROR'}, f"No {self.new_date_source} dates available")
                        return {'CANCELLED'}
                else:
                    props.date_source_type = current_date_source
                    self.report({'ERROR'}, "No active work schedule")
                    return {'CANCELLED'}
            
            self.report({'INFO'}, f"Switched to {self.new_date_source} - Independent mode")
            return {'FINISHED'}
            
        except Exception as e:
            print(f"❌ SYNCH: Error in independent mode: {e}")
            props.date_source_type = current_date_source
            self.report({'ERROR'}, f"Independent mode failed: {e}")
            return {'CANCELLED'}

    def _execute_synchronized_mode(self, context, props, anim_props, current_date_source):
        """
        MODE 2: AFTER synchronization is activated
        All schedule types use the same unified temporal range during animation
        Timeline HUD shows the unified range (earliest start, latest finish of all 4 types)
        If Look Ahead filter is active, it overrides the range
        """
        try:
            # Calculate current animation progress to maintain temporal position
            current_frame = context.scene.frame_current
            start_frame = context.scene.frame_start
            end_frame = context.scene.frame_end
            total_frames = end_frame - start_frame
            
            if total_frames <= 0:
                self.report({'ERROR'}, "Invalid animation frame range")
                return {'CANCELLED'}
            
            progress = (current_frame - start_frame) / total_frames
            progress = max(0.0, min(1.0, progress))  # Clamp between 0 and 1
            
            print(f"🎬 SYNCH: Current frame {current_frame}, progress {progress:.3f}")
            
            # Calculate target date based on current position
            from datetime import datetime
            current_start = getattr(props, "visualisation_start", None)
            current_finish = getattr(props, "visualisation_finish", None)
            
            if current_start and current_finish:
                try:
                    current_start_date = datetime.fromisoformat(current_start.replace('Z', '+00:00')).replace(tzinfo=None)
                    current_finish_date = datetime.fromisoformat(current_finish.replace('Z', '+00:00')).replace(tzinfo=None)
                    current_duration = current_finish_date - current_start_date
                    target_date = current_start_date + current_duration * progress
                    print(f"🎯 SYNCH: Target date to maintain: {target_date.strftime('%Y-%m-%d %H:%M:%S')}")
                except Exception as e:
                    print(f"⚠️ SYNCH: Error calculating target date: {e}")
                    target_date = None
            else:
                target_date = None
            
            print(f"🔄 SYNCH: Switching from {current_date_source} to {self.new_date_source}")
            
            # CRITICAL FIX: In synchronized mode, we need to ensure ALL schedule types use the SAME temporal range
            # Get the work schedule to calculate unified range
            work_schedule = tool.Sequence.get_active_work_schedule()
            if work_schedule:
                # Calculate the unified range that encompasses ALL 4 schedule types
                unified_start, unified_finish = self.get_unified_date_range(work_schedule)
                
                if unified_start and unified_finish:
                    # CRITICAL: Set the visualization properties to the unified range
                    # This ensures the animation timeline spans the complete range
                    old_viz_start = props.visualisation_start
                    old_viz_finish = props.visualisation_finish
                    
                    props.visualisation_start = unified_start.isoformat()
                    props.visualisation_finish = unified_finish.isoformat()
                    
                    print(f"🔗 SYNCH: Updated visualization range to unified:")
                    print(f"   OLD: {old_viz_start} to {old_viz_finish}")
                    print(f"   NEW: {props.visualisation_start} to {props.visualisation_finish}")
                    
                    # Now switch the date source type
                    props.date_source_type = self.new_date_source
                    
                    # Calculate the equivalent frame in the unified timeline
                    if target_date:
                        try:
                            # Calculate progress in the unified timeline
                            unified_duration = unified_finish - unified_start
                            if unified_duration.total_seconds() > 0:
                                if target_date < unified_start:
                                    new_frame = start_frame
                                    print("🔗 SYNCH: Target date before unified range, setting to start frame")
                                elif target_date > unified_finish:
                                    new_frame = end_frame
                                    print("🔗 SYNCH: Target date after unified range, setting to end frame")
                                else:
                                    # Calculate equivalent position in unified timeline
                                    unified_progress = (target_date - unified_start) / unified_duration
                                    new_frame = start_frame + total_frames * unified_progress
                                    print(f"🔗 SYNCH: Target date in unified range, progress: {unified_progress:.3f}")
                                
                                # Set the new frame to maintain temporal position
                                new_frame_int = max(start_frame, min(end_frame, int(round(new_frame))))
                                if new_frame_int != current_frame:
                                    context.scene.frame_set(new_frame_int)
                                    print(f"📍 SYNCH: Frame adjusted from {current_frame} to {new_frame_int}")
                                else:
                                    print(f"📍 SYNCH: Frame remains at {current_frame}")
                                
                                # Calculate final date for verification
                                final_progress = (new_frame_int - start_frame) / total_frames
                                final_date = unified_start + unified_duration * final_progress
                                
                                print(f"✅ SYNCH: Final synchronized date: {final_date.strftime('%Y-%m-%d %H:%M:%S')}")
                                self.report({'INFO'}, f"Synced to {self.new_date_source}: {final_date.strftime('%Y-%m-%d')} (Frame {new_frame_int})")
                                return {'FINISHED'}
                            else:
                                print("⚠️ SYNCH: Invalid unified duration")
                        except Exception as e:
                            print(f"⚠️ SYNCH: Error calculating unified frame position: {e}")
                    
                    # Fallback: just switch type and keep current frame
                    props.date_source_type = self.new_date_source
                    print(f"🔗 SYNCH: Synchronized to {self.new_date_source} with unified range (Frame {current_frame})")
                    self.report({'INFO'}, f"Synced to {self.new_date_source} with unified timeline (Frame {current_frame})")
                    return {'FINISHED'}
                else:
                    print("❌ SYNCH: Could not calculate unified date range")
                    self.report({'ERROR'}, "Could not calculate unified date range")
                    return {'CANCELLED'}
            else:
                print("❌ SYNCH: No active work schedule found")
                self.report({'ERROR'}, "No active work schedule found")
                return {'CANCELLED'}
            
        except Exception as e:
            print(f"❌ SYNCH: Error in synchronized mode: {e}")
            props.date_source_type = current_date_source
            self.report({'ERROR'}, f"Synchronized mode failed: {e}")
            return {'CANCELLED'}
    
    def get_unified_date_range(self, work_schedule):
        """
        Calculate the unified date range by analyzing ALL 4 schedule types
        Returns the earliest start and latest finish across all types
        Used for Timeline HUD when synchronization is enabled
        """
        from datetime import datetime
        
        if not work_schedule:
            return None, None
        
        all_starts = []
        all_finishes = []
        
        # Check all schedule types: SCHEDULE, ACTUAL, EARLY, LATE
        for schedule_type in ["SCHEDULE", "ACTUAL", "EARLY", "LATE"]:
            start_attr = f"{schedule_type.capitalize()}Start"
            finish_attr = f"{schedule_type.capitalize()}Finish"
            
            print(f"🔍 UNIFIED: Analyzing {schedule_type} -> {start_attr}/{finish_attr}")
            
            # Get all tasks from schedule
            root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
            
            def get_all_tasks_recursive(tasks):
                result = []
                for task in tasks:
                    result.append(task)
                    nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested:
                        result.extend(get_all_tasks_recursive(nested))
                return result
            
            all_tasks = get_all_tasks_recursive(root_tasks)
            
            for task in all_tasks:
                start_date = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
                if start_date:
                    all_starts.append(start_date)
                
                finish_date = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
                if finish_date:
                    all_finishes.append(finish_date)
        
        if not all_starts or not all_finishes:
            print("❌ UNIFIED: No valid dates found across all schedule types")
            return None, None
        
        unified_start = min(all_starts)
        unified_finish = max(all_finishes)
        
        print(f"✅ UNIFIED: Range spans {unified_start.strftime('%Y-%m-%d')} to {unified_finish.strftime('%Y-%m-%d')}")
        return unified_start, unified_finish


# ... (El resto de tu archivo, desde aquí hacia abajo, debe ser tu CÓDIGO ORIGINAL) ...
# ... He incluido la versión ORIGINAL y CORRECTA de _clear_previous_animation para asegurarme de que el botón Reset funcione ...
def _clear_previous_animation(context) -> None:
    print("🧹 Iniciando limpieza completa de la animación...")
    try:
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        if hud_overlay.is_hud_enabled():
            hud_overlay.unregister_hud_handler()
        if hasattr(tool.Sequence, 'unregister_live_color_update_handler'):
            tool.Sequence.unregister_live_color_update_handler()
        if hasattr(tool.Sequence, '_unregister_frame_change_handler'):
            tool.Sequence._unregister_frame_change_handler()
        for coll_name in ["Schedule_Display_Texts", "Bar Visual", "Schedule_Display_3D_Legend"]:
            if coll_name in bpy.data.collections:
                collection = bpy.data.collections[coll_name]
                for obj in list(collection.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(collection)
        parent_empty = bpy.data.objects.get("Schedule_Display_Parent")
        if parent_empty:
            bpy.data.objects.remove(parent_empty, do_unlink=True)
        cleaned_count = 0
        reset_count = 0
        
        # CRITICAL FIX 2: More aggressive cleanup of ALL IFC objects
        print("🧹 CLEARING: Resetting all IFC object states...")
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                # Clear animation data
                if obj.animation_data:
                    obj.animation_data_clear()
                    cleaned_count += 1
                
                # FORCE reset visibility and colors - this is critical
                obj.hide_viewport = False
                obj.hide_render = False
                obj.color = (0.8, 0.8, 0.8, 1.0)  # Default gray color
                
                # CRITICAL FIX: Also reset any material overrides that might exist
                if obj.material_slots:
                    for slot in obj.material_slots:
                        if slot.material and hasattr(slot.material, 'node_tree'):
                            # Reset any viewport display overrides
                            slot.material.diffuse_color = (0.8, 0.8, 0.8, 1.0)
                
                # Force update the object to ensure changes are applied
                obj.update_tag()
                reset_count += 1
        
        # Force a viewport update to ensure all changes are visible
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        
        print(f"🧹 CLEARED: {cleaned_count} animations, {reset_count} objects reset to default state")
        if "is_snapshot_mode" in context.scene:
            del context.scene["is_snapshot_mode"]
        restore_all_ui_state(context)
        context.scene.frame_set(context.scene.frame_start)
    except Exception as e:
        print(f"Bonsai WARNING: Ocurrió un error durante la limpieza de la animación: {e}")
        import traceback
        traceback.print_exc()
