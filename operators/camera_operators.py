# File: camera_operators.py
# Description: All camera-related operators for the add-on.

import bpy
import bonsai.tool as tool

# --- Helpers ---

def _get_4d_cameras(self, context):
    """EnumProperty items callback: returns available 4D cameras.
    Identifies cameras by name pattern or a custom flag 'is_4d_camera'.
    """
    try:
        items = []
        for obj in bpy.data.objects:
            if tool.Sequence.is_bonsai_camera(obj):
                items.append((obj.name, obj.name, '4D/Snapshot camera'))
        if not items:
            items = [('NONE', '<No cameras found>', 'No 4D or Snapshot cameras detected')]
        return items
    except Exception:
        return [('NONE', '<No cameras found>', 'No 4D or Snapshot cameras detected')]

# --- Operators ---

class ResetCameraSettings(bpy.types.Operator):
    bl_idname = "bim.reset_camera_settings"
    bl_label = "Reset Camera Settings"
    bl_description = "Reset camera and orbit settings to their default values (HUD and UI settings are preserved)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            camera_props.camera_focal_mm = 35.0
            camera_props.camera_clip_start = 0.1
            camera_props.camera_clip_end = 10000.0
            
            camera_props.orbit_mode = "CIRCLE_360"
            # ... (rest of the properties)
            
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
            # ... (code of the execute method)
            
            self.report({'INFO'}, "Camera aligned to view and set to static.")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to align camera: {str(e)}")
            return {'CANCELLED'}


class Delete4DCamera(bpy.types.Operator):
    """Deletes a 4D camera and its associated objects (path, target)"""
    bl_idname = "bim.delete_4d_camera"
    bl_label = "Delete a 4D Camera"
    bl_options = {'REGISTER', 'UNDO'}

    camera_to_delete: bpy.props.EnumProperty(
        name="Camera",
        description="Select the 4D camera to delete",
        items=_get_4d_cameras
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

        path_name = f"4D_OrbitPath_for_{cam_name}"
        target_name = f"4D_OrbitTarget_for_{cam_name}"

        path_obj = bpy.data.objects.get(path_name)
        target_obj = bpy.data.objects.get(target_name)

        objects_to_remove = [cam_obj]
        if path_obj:
            objects_to_remove.append(path_obj)
        if target_obj:
            objects_to_remove.append(target_obj)

        try:
            for obj in objects_to_remove:
                bpy.data.objects.remove(obj, do_unlink=True)
            self.report({'INFO'}, f"Successfully deleted '{cam_name}' and its associated objects.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to delete camera objects: {e}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AddSnapshotCamera(bpy.types.Operator):
    """Add a static camera for snapshot viewing"""
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
    """Align snapshot camera to current 3D viewport view"""
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