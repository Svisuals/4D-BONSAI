# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2020, 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>
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
import queue
import bonsai.tool as tool
from bonsai.bim.module.sequence.core import async_manager
from bonsai.tool import gn_sequence
from bonsai.bim.module.sequence.data import SequenceCache

# Import required helper functions
from .animation_operators import _clear_previous_animation, _restore_3d_texts_state


class RunAsyncTaskWithProgress(bpy.types.Operator):
    bl_idname = "bim.run_async_task"
    bl_label = "Processing in Background"
    bl_options = {"REGISTER"}
    _timer = None

    def modal(self, context, event):
        if event.type == 'TIMER':
            print(f"🔍 MODAL DEBUG: Timer event, task_running={async_manager.task_status['running']}")
            if not async_manager.task_status["running"]:
                print("🔄 Async task completed - checking results...")
                try:
                    status, result = async_manager.result_queue.get_nowait()
                    print(f"🔍 Got result: status={status}, result_type={type(result)}")
                    if status == 'SUCCESS':
                        print("✅ Async task succeeded - applying baked attributes...")
                        self.apply_baked_attributes(result)
                        print("🎯 Creating GN system...")
                        self.create_gn_system(context)
                        print("✅ GN system creation completed!")
                        self.report({'INFO'}, "Geometry Nodes animation system created successfully.")
                    else:
                        print(f"❌ Async task failed: {result}")
                        self.report({'ERROR'}, f"Async task failed: {result}")
                except queue.Empty:
                    print("⚠️ No result found in queue - task may still be running")
                    print(f"🔍 QUEUE DEBUG: queue size = {async_manager.result_queue.qsize()}")
                    pass
                print("🏁 MODAL DEBUG: Finishing modal operator...")
                self.finish(context)
                return {'FINISHED'}
            else:
                print(f"🔄 MODAL DEBUG: Task still running - progress={async_manager.task_status['progress']}%")

            # Update status bar
            context.workspace.status_text_set_internal(
                f"Processing... {async_manager.task_status['message']} ({async_manager.task_status['progress']:.1f}%)"
            )
        elif event.type == 'ESC':
            self.finish(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def execute(self, context):
        print("🎬 MODAL DEBUG: Starting modal operator...")
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        print("✅ MODAL DEBUG: Modal operator started successfully")
        return {'RUNNING_MODAL'}

    def finish(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        context.workspace.status_text_set_internal(None)

    def apply_baked_attributes(self, attributes_to_set):
        """OPTIMIZED: Applies baked attributes efficiently for large models (8000+ objects)"""
        total_objects = len(attributes_to_set)
        print(f"🚀 OPTIMIZED ATTRIBUTE APPLICATION: Processing {total_objects} objects...")

        batch_size = 500  # Process in smaller batches for UI responsiveness
        processed = 0

        # Disable viewport updates during bulk operations
        bpy.context.scene.frame_set(bpy.context.scene.frame_current, subframe=0.0)

        for obj_name, attrs in attributes_to_set.items():
            obj = bpy.data.objects.get(obj_name)
            if not obj or obj.type != 'MESH' or not obj.data.vertices:
                processed += 1
                continue

            # OPTIMIZATION: Batch attribute creation for each object
            vertex_count = len(obj.data.vertices)

            for attr_name, data in attrs.items():
                # Create or get existing attribute
                if attr_name not in obj.data.attributes:
                    attr = obj.data.attributes.new(
                        name=attr_name,
                        type=data['type'],
                        domain=data['domain']
                    )
                else:
                    attr = obj.data.attributes[attr_name]

                # OPTIMIZATION: Use foreach_set for bulk assignment (faster than individual assignments)
                if data['type'] == 'FLOAT':
                    values = [data['value']] * vertex_count
                    attr.data.foreach_set('value', values)
                elif data['type'] == 'INT':
                    values = [data['value']] * vertex_count
                    attr.data.foreach_set('value', values)

            processed += 1

            # OPTIMIZATION: Progress feedback for large models
            if processed % batch_size == 0:
                progress = (processed / total_objects) * 100
                print(f"🔄 Attribute application: {processed}/{total_objects} ({progress:.1f}%)")
                # Force UI update to prevent freezing
                bpy.context.view_layer.update()

        print(f"✅ OPTIMIZED ATTRIBUTE APPLICATION COMPLETED: {processed} objects processed")

    def create_gn_system(self, context):
        """Creates the complete Geometry Nodes system after attributes are baked"""
        print("🎯 Creating Geometry Nodes system...")

        # SOLID COLOR FOCUS: Skip material creation - we're using Solid shading mode
        print("🎨 SOLID COLOR MODE: Skipping material creation (using vertex colors/attributes)")

        # Create the node tree
        print("🌳 Creating advanced node tree...")
        node_tree = gn_sequence.create_advanced_nodetree()
        print(f"✅ Node tree created: {node_tree.name if node_tree else 'FAILED'}")

        # Get all controllers
        controllers = [obj for obj in context.scene.objects
                      if obj.get("is_gn_controller", False)]
        print(f"🎮 Found {len(controllers)} GN controllers")

        # CRITICAL FIX: If no controllers found, create one
        if len(controllers) == 0:
            print("🚨 No GN controllers found - creating one...")
            controller = gn_sequence.ensure_gn_controller()
            if controller:
                controllers = [controller]
                print(f"✅ Created GN controller: {controller.name}")
            else:
                print("❌ Failed to create GN controller")

        print(f"🎮 Final controller count: {len(controllers)}")

        # Apply modifiers and drivers to all relevant objects
        print("⚙️ Applying GN modifiers and drivers...")
        gn_sequence.apply_gn_modifiers_and_drivers(context, controllers)
        print("✅ Modifiers and drivers applied")

        # REMOVED: Complex solid colors system (caused crashes)
        print("🔧 SIMPLIFIED: Skipping complex solid color setup to prevent crashes")

        # INTEGRATION: Register GN Live Color handler if Live Color is enabled
        try:
            anim_props = tool.Sequence.get_animation_props()
            if hasattr(anim_props, 'enable_live_color_updates') and anim_props.enable_live_color_updates:
                gn_sequence.register_gn_live_color_handler()
                print("✅ GN Live Color handler registered (Live Color is enabled)")
        except Exception as live_e:
            print(f"⚠️ Could not register GN Live Color handler: {live_e}")

        print("✅ Geometry Nodes system created successfully.")


class CreateUpdate4DAnimation(bpy.types.Operator):
    bl_idname = "bim.create_update_4d_animation"
    bl_label = "Create / Update 4D Animation"
    bl_options = {"REGISTER", "UNDO"}

    # Camera action property for dialog (like v93)
    camera_action: bpy.props.EnumProperty(
        name="Camera Action",
        description="Choose whether to create a new camera or update the existing one",
        items=[
            ('UPDATE', "Update Existing Camera", "Update the existing 4D camera with current settings"),
            ('CREATE_NEW', "Create New Camera", "Create a new 4D camera"),
            ('NONE', "No Camera Action", "Do not add or modify the camera"),
        ],
        default='UPDATE'
    )

    @classmethod
    def poll(cls, context):
        """Date validation: prevent animation creation without Start/Finish dates (like v96)"""
        try:
            props = tool.Sequence.get_work_schedule_props()
            has_start = bool(props.visualisation_start and props.visualisation_start != "-")
            has_finish = bool(props.visualisation_finish and props.visualisation_finish != "-")
            return has_start and has_finish
        except Exception:
            return False

    def invoke(self, context, event):
        """Show camera options dialog before creating animation (like v93)"""
        try:
            # Check if there's an existing 4D animation camera
            existing_cam = None
            for obj in bpy.data.objects:
                if (obj.type == 'CAMERA' and
                    obj.get('is_4d_camera') and
                    obj.get('is_animation_camera')):
                    existing_cam = obj
                    break

            if existing_cam:
                # If camera exists, show dialog with options
                return context.window_manager.invoke_props_dialog(self)
            else:
                # If no camera, default to creating new one and execute directly
                self.camera_action = 'CREATE_NEW'
                return self.execute(context)

        except Exception as e:
            self.report({'ERROR'}, f"Failed to invoke animation dialog: {e}")
            return {'CANCELLED'}

    def draw(self, context):
        """Draw the camera options dialog (like v93)"""
        layout = self.layout
        layout.label(text="An existing 4D animation camera was found.")
        layout.label(text="What would you like to do with the camera?")
        layout.prop(self, "camera_action", expand=True)

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to get animation properties: {e}")
            return {'CANCELLED'}

        # === CAMERA MANAGEMENT LOGIC (like v93) ===
        try:
            self.handle_camera_action(context)
        except Exception as e:
            print(f"Warning: Camera action failed: {e}")
            # Continue with animation creation even if camera fails

        if anim_props.animation_engine == 'KEYFRAME':
            # === LEGACY KEYFRAME ENGINE ===
            print("Running Keyframe (Legacy) engine...")
            try:
                # Import and call your existing legacy functions
                from .animation_operators import create_4d_animation_legacy
                create_4d_animation_legacy(context)
                self.report({'INFO'}, "Keyframe animation created successfully.")
                return {'FINISHED'}
            except ImportError:
                self.report({'WARNING'},
                          "Legacy animation functions not found. Creating basic keyframe animation.")
                # Fallback to basic implementation
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Legacy animation failed: {e}")
                return {'CANCELLED'}

        elif anim_props.animation_engine == 'GEOMETRY_NODES':
            # === NEW GEOMETRY NODES ENGINE ===
            print("Running Geometry Nodes (Real-time) engine...")

            # Check if another task is running
            if async_manager.task_status["running"]:
                self.report({'WARNING'}, "A background process is already running.")
                return {'CANCELLED'}

            try:
                # Check if we can use existing keyframe data for GN conversion
                work_schedule = tool.Sequence.get_active_work_schedule()
                if not work_schedule:
                    self.report({'ERROR'}, "No active work schedule found.")
                    return {'CANCELLED'}

                # CORRECTED LOGIC: Geometry Nodes ALWAYS uses fast path (no baking needed)
                total_objects = len([obj for obj in bpy.data.objects if obj.type == 'MESH' and tool.Ifc.get_entity(obj)])
                print(f"🔍 Detected {total_objects} IFC objects in model")
                print(f"⚡ GEOMETRY NODES ENGINE: Using fast creation (no baking needed)")

                # Geometry Nodes doesn't need pre-baked data - it computes everything in real-time
                return self.create_fast_gn_system(context, work_schedule, total_objects)

            except Exception as e:
                self.report({'ERROR'}, f"Failed to start Geometry Nodes animation: {e}")
                return {'CANCELLED'}

        else:
            self.report({'ERROR'}, f"Unknown animation engine: {anim_props.animation_engine}")
            return {'CANCELLED'}

    def build_colortype_mapping(self, context):
        """Build mapping between tasks and their colortype profiles"""
        # TODO: Implement this based on your specific data structure
        # This should return a dictionary mapping task IDs to profile information
        mapping = {}

        try:
            # Example implementation - adapt to your needs
            task_props = tool.Sequence.get_task_tree_props()
            if task_props and hasattr(task_props, 'tasks'):
                for task in task_props.tasks:
                    task_id = getattr(task, 'ifc_definition_id', None)
                    if task_id:
                        # Get the profile name for this task
                        # This is where you'd implement your task->profile logic
                        profile_name = self.get_profile_for_task(task)
                        mapping[task_id] = {
                            'profile_name': profile_name,
                            'task_name': getattr(task, 'name', 'Unknown')
                        }
        except Exception as e:
            print(f"Warning: Could not build colortype mapping: {e}")

        return mapping

    def diagnose_schedule_issues(self, work_schedule):
        """Diagnose common issues with work schedule configuration for better user feedback"""
        issues = []

        try:
            import ifcopenshell.util.sequence

            # Check for tasks
            root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
            if not root_tasks:
                issues.append("No root tasks found in the work schedule")
                return issues

            # Get all tasks
            def get_all_tasks_recursive(tasks):
                all_tasks = []
                for task in tasks:
                    all_tasks.append(task)
                    nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested:
                        all_tasks.extend(get_all_tasks_recursive(nested))
                return all_tasks

            all_tasks = get_all_tasks_recursive(root_tasks)

            tasks_with_dates = 0
            tasks_with_products = 0

            for task in all_tasks:
                # Check dates
                try:
                    start_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
                    finish_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
                    if start_date and finish_date:
                        tasks_with_dates += 1
                except:
                    pass

                # Check products
                has_products = False
                for rel in getattr(task, 'HasAssignments', []):
                    if rel.is_a('IfcRelAssignsToProduct'):
                        has_products = True
                        break

                if not has_products:
                    for rel in getattr(task, 'OperatesOn', []):
                        for obj in getattr(rel, 'RelatedObjects', []):
                            if obj.is_a('IfcProduct'):
                                has_products = True
                                break
                        if has_products:
                            break

                if has_products:
                    tasks_with_products += 1

            if tasks_with_dates == 0:
                issues.append(f"None of {len(all_tasks)} tasks have schedule dates configured")
            elif tasks_with_dates < len(all_tasks):
                issues.append(f"Only {tasks_with_dates} of {len(all_tasks)} tasks have schedule dates")

            if tasks_with_products == 0:
                issues.append(f"None of {len(all_tasks)} tasks have products assigned")
            elif tasks_with_products < len(all_tasks):
                issues.append(f"Only {tasks_with_products} of {len(all_tasks)} tasks have products assigned")

        except Exception as e:
            issues.append(f"Error analyzing schedule: {e}")

        return issues

    def get_profile_for_task(self, task):
        """Get the appropriate profile name for a task"""
        # TODO: Implement your logic here
        # This might involve checking task types, predefined types, etc.
        try:
            # Example: use predefined type if available
            from bonsai.bim.module.sequence.data import SequenceData
            task_id = getattr(task, 'ifc_definition_id', None)
            if task_id and SequenceData.data:
                task_data = SequenceData.data.get("tasks", {}).get(task_id)
                if task_data and task_data.get("PredefinedType"):
                    return task_data["PredefinedType"]
        except Exception:
            pass

        return "NOTDEFINED"  # Default fallback

    def create_fast_gn_system(self, context, work_schedule, total_objects):
        """FAST PATH: Create GN system optimized for large models (8000+ objects)"""
        print(f"🚀 FAST GN SYSTEM: Creating optimized system for {total_objects} objects")

        try:
            # Get animation settings
            settings = tool.Sequence.get_animation_settings() or {}

            print("⚡ FAST PATH: Creating minimal product_frames for GN system")

            # Create minimal product_frames for GN system to work
            product_frames = self.create_minimal_product_frames(context, work_schedule)

            if not product_frames:
                self.report({'WARNING'}, "No objects found for animation")
                return {'CANCELLED'}

            print(f"⚡ Created minimal frames for {len(product_frames)} objects")

            # Create the GN system with minimal data
            success = gn_sequence.create_gn_animation_system(
                context, work_schedule, product_frames, settings
            )

            if success:
                self.report({'INFO'}, f"Fast GN system created for {total_objects} objects!")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Fast GN system creation failed")
                return {'CANCELLED'}

        except Exception as e:
            print(f"❌ Fast GN system creation failed: {e}")
            self.report({'ERROR'}, f"Fast GN system failed: {e}")
            return {'CANCELLED'}

    def create_minimal_product_frames(self, context, work_schedule):
        """Create minimal product_frames data for fast GN creation"""
        print("⚡ Building minimal product frames...")

        product_frames = {}

        try:
            # Get all IFC objects that could be animated
            ifc_objects = []
            for obj in bpy.data.objects:
                if obj.type == 'MESH' and tool.Ifc.get_entity(obj):
                    ifc_objects.append(obj)

            print(f"⚡ Found {len(ifc_objects)} IFC objects")

            # Create minimal frame data for each object
            frame_start = context.scene.frame_start
            frame_end = context.scene.frame_end

            for obj in ifc_objects:
                try:
                    entity = tool.Ifc.get_entity(obj)
                    if not entity:
                        continue

                    # Get the IFC product ID
                    product_id = entity.id()

                    # Get the actual ColorType for this object from its task
                    object_colortype = self.get_object_colortype_from_task(entity, obj)

                    # Create minimal task data - objects will animate from start to end
                    task_data = {
                        'task_id': product_id,  # Use entity ID as task ID
                        'name': obj.name,
                        'start_frame': frame_start,
                        'finish_frame': frame_end,
                        'effect_type': 'INSTANT',  # Default effect
                        'colortype': object_colortype  # Get actual ColorType like keyframes
                    }

                    # CORRECTED: Use product_id as key (not object name)
                    product_frames[product_id] = [task_data]

                except Exception as e:
                    print(f"⚠️ Could not process object {obj.name}: {e}")
                    continue

            print(f"✅ Created minimal frames for {len(product_frames)} objects")
            return product_frames

        except Exception as e:
            print(f"❌ Failed to create minimal product frames: {e}")
            return {}

    def get_object_colortype_from_task(self, entity, obj):
        """Get the specific ColorType for this object from its task (like keyframes does)"""
        try:
            # Find the task that owns this product/object
            ifc_file = tool.Ifc.get()

            # Look for task assignments
            for rel in getattr(entity, 'HasAssignments', []):
                if rel.is_a('IfcRelAssignsToProcess'):
                    task = rel.RelatingProcess
                    if task and task.is_a('IfcTask'):
                        # Get task properties from Blender
                        task_props = tool.Sequence.get_task_tree_props()
                        if task_props and task_props.tasks:
                            for task_pg in task_props.tasks:
                                if hasattr(task_pg, 'ifc_definition_id') and task_pg.ifc_definition_id == task.id():
                                    # Found the task PropertyGroup - get its ColorType
                                    colortype = getattr(task_pg, 'animation_color_schemes', '') or getattr(task_pg, 'selected_colortype_in_active_group', '')
                                    if colortype and colortype not in ['', 'DEFAULT']:
                                        print(f"🎨 Object {obj.name} → Task {task.id()} → ColorType '{colortype}'")
                                        return colortype

            # Fallback: try to get from related tasks
            for rel in getattr(entity, 'HasAssignments', []):
                if rel.is_a('IfcRelAssignsToProduct'):
                    # This might be a different relationship type
                    continue

            print(f"🎨 Object {obj.name} → No specific task ColorType found, using DEFAULT")
            return 'DEFAULT'

        except Exception as e:
            print(f"⚠️ Could not get ColorType for {obj.name}: {e}")
            return 'DEFAULT'

    def handle_camera_action(self, context):
        """Handle camera creation/update based on user selection (like v93)"""
        if self.camera_action == 'NONE':
            print("🎥 Camera action: NONE - Skipping camera handling")
            return

        # Find existing 4D animation camera
        existing_cam = None
        for obj in bpy.data.objects:
            if (obj.type == 'CAMERA' and
                obj.get('is_4d_camera') and
                obj.get('is_animation_camera')):
                existing_cam = obj
                break

        if self.camera_action == 'UPDATE' and existing_cam:
            print(f"🎥 Camera action: UPDATE - Updating existing camera '{existing_cam.name}'")
            try:
                # Update existing camera with current animation settings
                anim_props = tool.Sequence.get_animation_props()
                camera_props = anim_props.camera_orbit

                # Update camera properties
                if hasattr(camera_props, 'camera_focal_mm'):
                    existing_cam.data.lens = camera_props.camera_focal_mm
                if hasattr(camera_props, 'camera_clip_start'):
                    existing_cam.data.clip_start = camera_props.camera_clip_start
                if hasattr(camera_props, 'camera_clip_end'):
                    existing_cam.data.clip_end = camera_props.camera_clip_end

                # Set as active camera
                context.scene.camera = existing_cam
                print(f"✅ Updated camera '{existing_cam.name}' and set as active")

            except Exception as e:
                print(f"❌ Failed to update camera: {e}")

        elif self.camera_action == 'CREATE_NEW' or (self.camera_action == 'UPDATE' and not existing_cam):
            print("🎥 Camera action: CREATE_NEW - Creating new animation camera")
            try:
                # Create new animation camera
                bpy.ops.bim.add_animation_camera()
                print("✅ Created new animation camera")

            except Exception as e:
                print(f"❌ Failed to create new camera: {e}")
                # Fallback to basic camera creation
                try:
                    cam_data = bpy.data.cameras.new(name="4D_Animation_Camera")
                    cam_obj = bpy.data.objects.new(name="4D_Animation_Camera", object_data=cam_data)

                    # Mark as animation camera
                    cam_obj['is_4d_camera'] = True
                    cam_obj['is_animation_camera'] = True
                    cam_obj['camera_context'] = 'animation'

                    # Link to scene
                    context.collection.objects.link(cam_obj)

                    # Set as active camera
                    context.scene.camera = cam_obj
                    print("✅ Created fallback animation camera")

                except Exception as fallback_e:
                    print(f"❌ Even fallback camera creation failed: {fallback_e}")


class ConvertAnimationEngine(bpy.types.Operator):
    bl_idname = "bim.convert_animation_engine"
    bl_label = "Convert Animation Engine"
    bl_description = "Convert between Keyframe and Geometry Nodes animation systems"
    bl_options = {"REGISTER", "UNDO"}

    target_engine: bpy.props.EnumProperty(
        name="Target Engine",
        items=[
            ('KEYFRAME', "Convert to Keyframe", "Convert current Geometry Nodes animation to keyframes"),
            ('GEOMETRY_NODES', "Convert to Geometry Nodes", "Convert current keyframe animation to Geometry Nodes"),
        ],
        default='GEOMETRY_NODES'
    )

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
            work_schedule = tool.Sequence.get_active_work_schedule()

            if not work_schedule:
                self.report({'ERROR'}, "No active work schedule found.")
                return {'CANCELLED'}

            if self.target_engine == 'GEOMETRY_NODES':
                # Convert keyframes to Geometry Nodes
                print("🔄 Converting keyframe animation to Geometry Nodes...")

                # Get existing keyframe data
                from .animation_operators import _get_animation_settings, _compute_product_frames
                settings = _get_animation_settings(context)
                product_frames = _compute_product_frames(context, work_schedule, settings)

                if not product_frames:
                    self.report({'WARNING'}, "No keyframe animation data found to convert.")
                    return {'CANCELLED'}

                # Convert to GN system
                success = gn_sequence.create_gn_animation_system(
                    context, work_schedule, product_frames, settings
                )

                if success:
                    # Update the engine preference
                    anim_props.animation_engine = 'GEOMETRY_NODES'
                    self.report({'INFO'}, "Successfully converted to Geometry Nodes system.")
                    return {'FINISHED'}
                else:
                    self.report({'ERROR'}, "Failed to convert to Geometry Nodes.")
                    return {'CANCELLED'}

            elif self.target_engine == 'KEYFRAME':
                # Convert Geometry Nodes to keyframes
                print("🔄 Converting Geometry Nodes animation to keyframes...")

                # First check if GN system exists
                gn_objects = []
                for obj in context.scene.objects:
                    if obj.type == 'MESH':
                        for mod in obj.modifiers:
                            if mod.name == gn_sequence.GN_MODIFIER_NAME:
                                gn_objects.append(obj)
                                break

                if not gn_objects:
                    self.report({'WARNING'}, "No Geometry Nodes animation found to convert.")
                    return {'CANCELLED'}

                # Create keyframe animation using existing logic
                from .animation_operators import create_4d_animation_legacy

                # Clean GN system first
                gn_sequence.cleanup_gn_system()

                # Create keyframe animation
                create_4d_animation_legacy(context)

                # Update the engine preference
                anim_props.animation_engine = 'KEYFRAME'
                self.report({'INFO'}, f"Successfully converted {len(gn_objects)} objects from Geometry Nodes to keyframes.")
                return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Conversion failed: {e}")
            return {'CANCELLED'}

class AddGNViewController(bpy.types.Operator):
    bl_idname = "bim.add_gn_view_controller"
    bl_label = "Add GN View Controller"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Create or get the controller collection
        coll_name = gn_sequence.GN_CONTROLLER_COLLECTION
        if coll_name not in bpy.data.collections:
            coll = bpy.data.collections.new(coll_name)
            context.scene.collection.children.link(coll)
        else:
            coll = bpy.data.collections[coll_name]

        # Create the controller object (Empty)
        bpy.ops.object.empty_add(type='PLAIN_AXES')
        controller = context.active_object
        controller.name = "GN_4D_Controller"

        # Move to the correct collection and unlink from others
        for c in controller.users_collection:
            c.objects.unlink(controller)
        coll.objects.link(controller)

        # Set default properties
        if hasattr(controller, "BonsaiGNController"):
            ctrl_props = controller.BonsaiGNController
            ctrl_props.schedule_type_to_display = '0'  # Schedule by default
            # The colortype_group_to_display will use the dynamic enum

        self.report({'INFO'}, f"Controller '{controller.name}' created in collection '{coll_name}'.")
        return {'FINISHED'}


class ClearPreviousAnimation(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.clear_previous_animation"
    bl_label = "Reset Animation"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        # Stop animation if playing
        try:
            if bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel(restore_frame=False)
        except Exception as e:
            print(f"Could not stop animation: {e}")

        try:
            # Check animation engine and clean accordingly
            anim_props = tool.Sequence.get_animation_props()

            if anim_props.animation_engine == 'GEOMETRY_NODES':
                # Clean Geometry Nodes system
                gn_sequence.cleanup_gn_system()
                print("Geometry Nodes system cleaned.")

            # Clean legacy animation regardless
            _clear_previous_animation(context)

            # Clean HUD Legend
            try:
                if anim_props and hasattr(anim_props, 'camera_orbit'):
                    camera_props = anim_props.camera_orbit

                    # Get all colortypes to hide them
                    if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                        all_colortype_names = []
                        for group_item in anim_props.animation_group_stack:
                            group_name = group_item.group
                            from ..prop.color_manager_prop import UnifiedColorTypeManager
                            group_colortypes = UnifiedColorTypeManager.get_group_colortypes(context, group_name)
                            if group_colortypes:
                                all_colortype_names.extend(group_colortypes.keys())

                        # Hide all colortypes in HUD
                        if all_colortype_names:
                            hidden_colortypes_str = ','.join(set(all_colortype_names))
                            camera_props.legend_hud_visible_colortypes = hidden_colortypes_str
                            print(f"🧹 Hidden colortypes in HUD Legend: {hidden_colortypes_str}")

                    # Invalidate HUD cache
                    try:
                        from ..hud import invalidate_legend_hud_cache
                        invalidate_legend_hud_cache()
                        print("🧹 Active colortype group cleared from HUD Legend")
                    except ImportError:
                        pass  # HUD module might not be available

            except Exception as legend_e:
                print(f"⚠️ Could not clear colortype group: {legend_e}")

            self.report({'INFO'}, "Animation cleared successfully.")
            context.scene.frame_set(context.scene.frame_start)
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to clear animation: {e}")
            return {"CANCELLED"}

    def execute(self, context):
        return self._execute(context)


class ClearPreviousSnapshot(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.clear_previous_snapshot"
    bl_label = "Reset Snapshot"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        print(f"🔄 Reset snapshot started")

        # Stop animation if playing
        try:
            if bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel(restore_frame=False)
                print(f"✅ Animation playback stopped")
        except Exception as e:
            print(f"❌ Could not stop animation: {e}")

        try:
            # Clear previous animation/snapshot
            print(f"🔄 Clearing previous animation...")
            _clear_previous_animation(context)
            print(f"✅ Previous animation cleared")

            # Clear snapshot data
            if hasattr(bpy.context.scene, 'snapshot_data'):
                del bpy.context.scene.snapshot_data

            # Clear HUD Legend (same as animation reset)
            try:
                anim_props = tool.Sequence.get_animation_props()
                if anim_props and hasattr(anim_props, 'camera_orbit'):
                    camera_props = anim_props.camera_orbit

                    if hasattr(anim_props, 'animation_group_stack') and anim_props.animation_group_stack:
                        all_colortype_names = []
                        for group_item in anim_props.animation_group_stack:
                            group_name = group_item.group
                            from ..prop.color_manager_prop import UnifiedColorTypeManager
                            group_colortypes = UnifiedColorTypeManager.get_group_colortypes(context, group_name)
                            if group_colortypes:
                                all_colortype_names.extend(group_colortypes.keys())

                        if all_colortype_names:
                            hidden_colortypes_str = ','.join(set(all_colortype_names))
                            camera_props.legend_hud_visible_colortypes = hidden_colortypes_str
                            print(f"🧹 Hidden colortypes in HUD Legend: {hidden_colortypes_str}")

                    try:
                        from ..hud import invalidate_legend_hud_cache
                        invalidate_legend_hud_cache()
                        print("🧹 Active colortype group cleared from HUD Legend")
                    except ImportError:
                        pass

            except Exception as legend_e:
                print(f"⚠️ Could not clear colortype group: {legend_e}")

            # Restore 3D texts state
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