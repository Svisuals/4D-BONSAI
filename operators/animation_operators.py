# File: animation_operators.py
# Description: Animation-related operators for the 4D add-on.

import bpy
import bonsai.tool as tool
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
        # ... (resto de la función _execute de tu archivo original) ...
        # Asegúrate de que al final de la función _execute tienes esta lógica:
        if self.preserve_current_frame:
            context.scene.frame_set(stored_frame)
        self.report({'INFO'}, f"Animation created for {len(frames)} elements.")
        return {'FINISHED'}

    def execute(self, context):
        try:
            return self._execute(context)
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}


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
        # ... (resto de la lógica de SyncAnimationByDate) ...
        return {'FINISHED'}

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
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                if obj.animation_data:
                    obj.animation_data_clear()
                    cleaned_count += 1
                obj.hide_viewport = False
                obj.hide_render = False
                obj.color = (0.8, 0.8, 0.8, 1.0)
        if "is_snapshot_mode" in context.scene:
            del context.scene["is_snapshot_mode"]
        restore_all_ui_state(context)
        context.scene.frame_set(context.scene.frame_start)
    except Exception as e:
        print(f"Bonsai WARNING: Ocurrió un error durante la limpieza de la animación: {e}")
        import traceback
        traceback.print_exc()
