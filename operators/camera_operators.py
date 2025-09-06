# File: camera_operators.py
# Description: All camera-related operators for the add-on.

import bpy
import bonsai.tool as tool

# --- Helpers ---

import bpy
import bonsai.tool as tool

# --- HELPER FUNCTIONS ---

def _get_animation_cameras(self, context):
    """Callback que retorna SOLO las cámaras de Animación."""
    items = []
    for obj in bpy.data.objects:
        if tool.Sequence.is_bonsai_animation_camera(obj):
            items.append((obj.name, obj.name, 'Cámara de Animación 4D'))
    if not items:
        items = [('NONE', '<No hay cámaras de animación>', 'No se detectaron cámaras de Animación 4D')]
    return items

def _get_snapshot_cameras(self, context):
    """Callback que retorna SOLO las cámaras de Snapshot."""
    items = []
    for obj in bpy.data.objects:
        if tool.Sequence.is_bonsai_snapshot_camera(obj):
            items.append((obj.name, obj.name, 'Cámara de Snapshot 4D'))
    if not items:
        items = [('NONE', '<No hay cámaras de snapshot>', 'No se detectaron cámaras de Snapshot')]
    return items


# --- OPERATORS ---

class ResetCameraSettings(bpy.types.Operator):
    bl_idname = "bim.reset_camera_settings"
    bl_label = "Reset Camera Settings"
    bl_description = "Reset camera and orbit settings to their default values (HUD and UI settings are preserved)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            # --- Resetear todas las propiedades a sus valores por defecto ---

            # Propiedades de la Cámara
            camera_props.camera_focal_mm = 35.0
            camera_props.camera_clip_start = 0.1
            camera_props.camera_clip_end = 10000.0

            # Propiedades de la Órbita
            camera_props.orbit_mode = "CIRCLE_360"
            camera_props.orbit_radius_mode = "AUTO"
            camera_props.orbit_radius = 10.0
            camera_props.orbit_height = 8.0
            camera_props.orbit_start_angle_deg = 0.0
            camera_props.orbit_direction = "CCW"

            # Propiedades del Objetivo (Look At)
            camera_props.look_at_mode = "AUTO"
            camera_props.look_at_object = None # Limpiar cualquier objeto seleccionado

            # Propiedades de la Trayectoria y la Animación
            camera_props.orbit_path_shape = "CIRCLE"
            camera_props.custom_orbit_path = None # Limpiar cualquier trayectoria personalizada
            camera_props.orbit_path_method = "FOLLOW_PATH"
            camera_props.interpolation_mode = "LINEAR"
            camera_props.bezier_smoothness_factor = 0.35
            camera_props.orbit_use_4d_duration = True
            camera_props.orbit_duration_frames = 250.0
            camera_props.hide_orbit_path = False

            self.report({'INFO'}, "Camera and orbit settings have been reset")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Reset failed: {str(e)}")
            return {'CANCELLED'}


class Align4DCameraToView(bpy.types.Operator):
    bl_idname = "bim.align_4d_camera_to_view"
    bl_label = "Align Active Camera to View"
    bl_description = "Aligns the active 4D camera to the current 3D view and sets it to static"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.scene or not context.scene.camera:
            return False
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                return True
        return False

    def execute(self, context):
        try:
            cam_obj = context.scene.camera
            if not cam_obj:
                self.report({'ERROR'}, "No active camera in scene.")
                return {'CANCELLED'}

            rv3d = None
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    rv3d = area.spaces.active.region_3d
                    break
            
            if not rv3d:
                self.report({'ERROR'}, "No active 3D viewport found.")
                return {'CANCELLED'}

            cam_obj.matrix_world = rv3d.view_matrix.inverted()

            tool.Sequence.clear_camera_animation(cam_obj)
            
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            camera_props.orbit_mode = 'NONE'

            if getattr(camera_props, 'enable_text_hud', False):
                try:
                    bpy.ops.bim.refresh_schedule_hud()
                except Exception as e:
                    print(f"HUD refresh after align failed: {e}")
            
            self.report({'INFO'}, "Camera aligned to view and set to static.")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to align camera: {str(e)}")
            return {'CANCELLED'}

# --- OPERADOR DE BORRADO DE CÁMARA DE ANIMACIÓN (NUEVO) ---
class DeleteAnimationCamera(bpy.types.Operator):
    """Elimina una cámara de Animación 4D y sus objetos asociados."""
    bl_idname = "bim.delete_animation_camera"
    bl_label = "Delete an Animation Camera"
    bl_options = {'REGISTER', 'UNDO'}

    camera_to_delete: bpy.props.EnumProperty(
        name="Animation Camera",
        description="Select the Animation camera to delete",
        items=_get_animation_cameras
    )

    def execute(self, context):
        cam_name = self.camera_to_delete
        if cam_name == "NONE" or not cam_name:
            self.report({'INFO'}, "No camera selected to delete.")
            return {'CANCELLED'}

        cam_obj = bpy.data.objects.get(cam_name)
        if not cam_obj:
            self.report({'ERROR'}, f"Camera '{cam_name}' not found.")
            return {'CANCELLED'}

        # Objetos asociados a la cámara de animación
        path_name = f"4D_OrbitPath_for_{cam_name}"
        target_name = f"4D_OrbitTarget_for_{cam_name}"
        objects_to_remove = [cam_obj]
        if bpy.data.objects.get(path_name): objects_to_remove.append(bpy.data.objects[path_name])
        if bpy.data.objects.get(target_name): objects_to_remove.append(bpy.data.objects[target_name])

        for obj in objects_to_remove:
            bpy.data.objects.remove(obj, do_unlink=True)
        self.report({'INFO'}, f"Successfully deleted '{cam_name}' and associated objects.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


# --- OPERADOR DE BORRADO DE CÁMARA DE SNAPSHOT (NUEVO) ---
class DeleteSnapshotCamera(bpy.types.Operator):
    """Elimina una cámara de Snapshot y sus objetos asociados."""
    bl_idname = "bim.delete_snapshot_camera"
    bl_label = "Delete a Snapshot Camera"
    bl_options = {'REGISTER', 'UNDO'}

    camera_to_delete: bpy.props.EnumProperty(
        name="Snapshot Camera",
        description="Select the Snapshot camera to delete",
        items=_get_snapshot_cameras
    )

    def execute(self, context):
        cam_name = self.camera_to_delete
        if cam_name == "NONE" or not cam_name:
            self.report({'INFO'}, "No camera selected to delete.")
            return {'CANCELLED'}

        cam_obj = bpy.data.objects.get(cam_name)
        if not cam_obj:
            self.report({'ERROR'}, f"Camera '{cam_name}' not found.")
            return {'CANCELLED'}

        # Objetos asociados a la cámara de snapshot
        target_name = "Snapshot_Target"
        objects_to_remove = [cam_obj]
        if bpy.data.objects.get(target_name): objects_to_remove.append(bpy.data.objects[target_name])

        for obj in objects_to_remove:
            bpy.data.objects.remove(obj, do_unlink=True)
        self.report({'INFO'}, f"Successfully deleted '{cam_name}' and associated objects.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


# ... (el resto de los operadores de cámara como AddSnapshotCamera y AddAnimationCamera no cambian) ...
class AddSnapshotCamera(bpy.types.Operator):
    bl_idname = "bim.add_snapshot_camera"
    bl_label = "Add Snapshot Camera"
    bl_description = "Create a new static camera positioned for snapshot viewing"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        try:
            cam_obj = tool.Sequence.add_snapshot_camera()
            self.report({'INFO'}, f"Snapshot camera '{cam_obj.name}' created and set as active")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create snapshot camera: {str(e)}")
            return {'CANCELLED'}

class AlignSnapshotCameraToView(bpy.types.Operator):
    bl_idname = "bim.align_snapshot_camera_to_view"
    bl_label = "Align Snapshot Camera to View"
    bl_description = "Align the snapshot camera to match the current 3D viewport view"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        if not getattr(context.scene, "camera", None): return False
        for area in context.screen.areas:
            if area.type == 'VIEW_3D': return True
        return False
    def execute(self, context):
        try:
            tool.Sequence.align_snapshot_camera_to_view()
            self.report({'INFO'}, f"Snapshot camera aligned to current view")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to align snapshot camera: {str(e)}")
            return {'CANCELLED'}

class AddAnimationCamera(bpy.types.Operator):
    bl_idname = "bim.add_animation_camera"
    bl_label = "Add Animation Camera"
    bl_description = "Create a new camera for Animation Settings with orbital animation"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        try:
            cam_obj = tool.Sequence.add_animation_camera()
            bpy.ops.object.select_all(action='DESELECT')
            cam_obj.select_set(True)
            context.view_layer.objects.active = cam_obj
            self.report({'INFO'}, f"Animation camera '{cam_obj.name}' created and set as active")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create animation camera: {str(e)}")
            return {'CANCELLED'}