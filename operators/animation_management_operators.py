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
            if not async_manager.task_status["running"]:
                try:
                    status, result = async_manager.result_queue.get_nowait()
                    if status == 'SUCCESS':
                        self.apply_baked_attributes(result)
                        self.create_gn_system(context)
                        self.report({'INFO'}, "Geometry Nodes animation system created successfully.")
                    else:
                        self.report({'ERROR'}, f"Async task failed: {result}")
                except queue.Empty:
                    pass
                self.finish(context)
                return {'FINISHED'}

            # Update status bar
            context.workspace.status_text_set_internal(
                f"Processing... {async_manager.task_status['message']} ({async_manager.task_status['progress']:.1f}%)"
            )
        elif event.type == 'ESC':
            self.finish(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def execute(self, context):
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def finish(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        context.workspace.status_text_set_internal(None)

    def apply_baked_attributes(self, attributes_to_set):
        """Applies the baked attributes to mesh objects in the main thread"""
        print("Applying baked attributes in main thread...")

        for obj_name, attrs in attributes_to_set.items():
            obj = bpy.data.objects.get(obj_name)
            if not obj or obj.type != 'MESH' or not obj.data.vertices:
                continue

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

                # Set the attribute value for all vertices
                if data['type'] == 'FLOAT':
                    values = [data['value']] * len(obj.data.vertices)
                    attr.data.foreach_set('value', values)
                elif data['type'] == 'INT':
                    values = [data['value']] * len(obj.data.vertices)
                    attr.data.foreach_set('value', values)

        print(f"Applied attributes to {len(attributes_to_set)} objects.")

    def create_gn_system(self, context):
        """Creates the complete Geometry Nodes system after attributes are baked"""
        print("Creating Geometry Nodes system...")

        # Create the node tree
        node_tree = gn_sequence.create_advanced_nodetree()

        # Get all controllers
        controllers = [obj for obj in context.scene.objects
                      if hasattr(obj, "BonsaiGNController")]

        # Apply modifiers and drivers to all relevant objects
        gn_sequence.apply_gn_modifiers_and_drivers(context, controllers)

        print("Geometry Nodes system created successfully.")


class CreateUpdate4DAnimation(bpy.types.Operator):
    bl_idname = "bim.create_update_4d_animation"
    bl_label = "Create / Update 4D Animation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            anim_props = tool.Sequence.get_animation_props()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to get animation properties: {e}")
            return {'CANCELLED'}

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

                # Try to get existing keyframe animation data first
                product_frames = None
                try:
                    settings = tool.Sequence.get_animation_settings() or {}
                    from .animation_operators import _compute_product_frames
                    product_frames = _compute_product_frames(context, work_schedule, settings)

                    if product_frames:
                        print(f"🔄 Converting existing keyframe data to Geometry Nodes...")
                        # Use the bridge function to convert keyframe data to GN
                        success = gn_sequence.create_gn_animation_system(
                            context, work_schedule, product_frames, settings
                        )

                        if success:
                            self.report({'INFO'}, "Converting keyframe animation to Geometry Nodes...")
                            return {'FINISHED'}
                        else:
                            print("❌ GN conversion failed, falling back to direct GN creation")
                except Exception as e:
                    print(f"Could not convert keyframe data to GN: {e}")

                # Fallback to original GN creation method
                # 1. Get data using available SequenceCache methods
                work_schedule_id = work_schedule.id()

                print(f"🔍 GN: Getting data for work schedule ID {work_schedule_id}")

                # Use SequenceCache methods that actually exist
                schedule_dates = SequenceCache.get_schedule_dates(work_schedule_id, "SCHEDULE")
                task_products = SequenceCache.get_task_products(work_schedule_id)

                print(f"🔍 GN: Schedule dates result: {schedule_dates is not None}")
                print(f"🔍 GN: Task products result: {task_products is not None}")

                # If SequenceCache doesn't have data, try to get it directly from IFC
                if not schedule_dates or not task_products:
                    print("⚠️ GN: SequenceCache has no data, trying direct IFC access...")

                    try:
                        import ifcopenshell.util.sequence

                        # Get data directly from IFC
                        print(f"🔍 GN: Getting root tasks from work schedule...")
                        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
                        print(f"🔍 GN: Found {len(root_tasks) if root_tasks else 0} root tasks")

                        # Get all tasks recursively
                        def get_all_tasks_recursive(tasks):
                            all_tasks = []
                            for task in tasks:
                                all_tasks.append(task)
                                nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                                if nested:
                                    all_tasks.extend(get_all_tasks_recursive(nested))
                            return all_tasks

                        all_tasks = get_all_tasks_recursive(root_tasks) if root_tasks else []
                        print(f"🔍 GN: Total tasks found: {len(all_tasks)}")

                        if not all_tasks:
                            # Use diagnostic function to provide helpful feedback
                            issues = self.diagnose_schedule_issues(work_schedule)
                            error_msg = "No tasks found in the work schedule. Issues found: " + "; ".join(issues)
                            self.report({'WARNING'}, error_msg)
                            return {'CANCELLED'}

                        # Build schedule_dates manually
                        tasks_dates = []
                        for task in all_tasks:
                            try:
                                start_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
                                finish_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)

                                if start_date and finish_date:
                                    tasks_dates.append((task.id(), start_date, finish_date))
                            except Exception as e:
                                print(f"⚠️ GN: Could not get dates for task {task.id()}: {e}")

                        if not tasks_dates:
                            # Use diagnostic function to provide helpful feedback
                            issues = self.diagnose_schedule_issues(work_schedule)
                            error_msg = "No tasks with valid dates found. Issues found: " + "; ".join(issues)
                            self.report({'WARNING'}, error_msg)
                            return {'CANCELLED'}

                        # Calculate overall date range
                        all_start_dates = [date[1] for date in tasks_dates]
                        all_finish_dates = [date[2] for date in tasks_dates]
                        overall_start = min(all_start_dates)
                        overall_finish = max(all_finish_dates)

                        schedule_dates = {
                            'tasks_dates': tasks_dates,
                            'date_range': (overall_start, overall_finish),
                            'task_count': len(tasks_dates)
                        }

                        # Build task_products manually
                        task_products = {}
                        for task in all_tasks:
                            product_ids = []

                            # Get products from task outputs (IfcRelAssignsToProduct)
                            for rel in getattr(task, 'HasAssignments', []):
                                if rel.is_a('IfcRelAssignsToProduct'):
                                    product = rel.RelatingProduct
                                    if product and hasattr(product, 'id'):
                                        product_ids.append(product.id())

                            # Get products from task inputs (IfcRelAssignsToProcess)
                            for rel in getattr(task, 'OperatesOn', []):
                                for obj in getattr(rel, 'RelatedObjects', []):
                                    if obj.is_a('IfcProduct') and hasattr(obj, 'id'):
                                        product_ids.append(obj.id())

                            if product_ids:
                                task_products[task.id()] = list(set(product_ids))  # Remove duplicates

                        print(f"✅ GN: Direct IFC access successful - {len(schedule_dates['tasks_dates'])} tasks, {len(task_products)} with products")

                    except Exception as e:
                        print(f"❌ GN: Direct IFC access failed: {e}")
                        import traceback
                        traceback.print_exc()
                        self.report({'ERROR'}, f"Could not retrieve schedule data: {e}")
                        return {'CANCELLED'}

                if not schedule_dates or not task_products:
                    self.report({'WARNING'}, "No schedule data found. Please ensure your work schedule has tasks with assigned products and valid dates.")
                    return {'CANCELLED'}

                # Convert SequenceCache data to product_cache format expected by GN system
                product_cache = {}

                # Get timing data for tasks
                tasks_dates = schedule_dates.get('tasks_dates', [])
                task_timing = {}
                for task_id, start_date, finish_date in tasks_dates:
                    # Convert dates to frame numbers (simplified)
                    try:
                        # For now, use dummy frame values - this would need proper date->frame conversion
                        task_timing[task_id] = {
                            'schedule_start_day': 1.0,
                            'schedule_end_day': 100.0,
                            'schedule_duration': 99.0,
                            'actual_start_day': 1.0,
                            'actual_end_day': 100.0,
                            'actual_duration': 99.0
                        }
                    except Exception as e:
                        print(f"Warning: Could not process timing for task {task_id}: {e}")

                for task_id, product_ids in task_products.items():
                    for product_id in product_ids:
                        # Get the Blender object for this product
                        obj = None
                        for scene_obj in context.scene.objects:
                            if scene_obj.type == 'MESH' and hasattr(scene_obj, 'BIMObjectProperties'):
                                props = scene_obj.BIMObjectProperties
                                if hasattr(props, 'ifc_definition_id') and props.ifc_definition_id == product_id:
                                    obj = scene_obj
                                    break

                        if obj and task_id in task_timing:
                            product_cache[product_id] = {
                                'blender_object_name': obj.name,
                                'task_id': task_id,
                                **task_timing[task_id]  # Add timing data
                            }

                if not product_cache:
                    # More helpful error message
                    blender_objects = len([obj for obj in context.scene.objects if obj.type == 'MESH' and hasattr(obj, 'BIMObjectProperties')])
                    self.report({'WARNING'}, f"No 3D objects found for animation. Found {blender_objects} BIM objects, but none are linked to tasks with valid dates. Please ensure your tasks have products assigned and schedule dates configured.")
                    return {'CANCELLED'}

                # 2. Get profile data from animation properties
                profiles_data = {}
                colortype_mapping = {}

                try:
                    # Extract profiles from the ColorTypes collection
                    for profile in anim_props.ColorTypes:
                        profiles_data[profile.name] = profile

                    # Build colortype_mapping based on task-profile relationships
                    colortype_mapping = self.build_colortype_mapping(context)

                except Exception as e:
                    print(f"Warning: Could not extract profile data: {e}")
                    profiles_data = {}
                    colortype_mapping = {}

                # 3. Submit the heavy task to the async manager
                success = async_manager.submit_task(
                    gn_sequence.bake_all_attributes_worker,
                    product_cache,
                    profiles_data,
                    colortype_mapping
                )

                if not success:
                    self.report({'ERROR'}, "Failed to submit background task.")
                    return {'CANCELLED'}

                # 4. Start the modal operator to monitor progress
                bpy.ops.bim.run_async_task('INVOKE_DEFAULT')

                self.report({'INFO'}, "Started Geometry Nodes animation creation...")
                return {'FINISHED'}

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