# -*- coding: utf-8 -*-
"""
Object Management Module for 4D BIM Sequence Animation
=====================================================

This module handles all object-related operations for 4D BIM animations,
including object validation, bounding box calculations, color management,
text object creation, and IFC entity-object mapping.

EXTRACTED from sequence.py - 18 methods total
EXACT COPY - no modifications to preserve compatibility
"""

import bpy
import json
import math
import mathutils
from mathutils import Vector
from datetime import datetime, timedelta
import ifcopenshell


class ObjectManager:
    """
    Comprehensive object management system for 4D BIM operations.
    Handles object validation, scene analysis, color management, and text creation.
    """

    @classmethod
    def validate_task_object(cls, task, operation_name="operation"):
        """
        Validates that a task object has the required attributes for operation.
        EXACT COPY from sequence.py line ~5812
        """
        if not task:
            print(f"[WARNING] {operation_name}: Task object is None")
            return False

        # Check basic IFC entity validity
        try:
            if not hasattr(task, 'id') or not callable(task.id):
                print(f"[WARNING] {operation_name}: Task object lacks valid id() method")
                return False

            task_id = task.id()
            if not task_id or task_id <= 0:
                print(f"[WARNING] {operation_name}: Task has invalid ID: {task_id}")
                return False

        except Exception as e:
            print(f"[ERROR] {operation_name}: Exception validating task ID: {e}")
            return False

        # Check if it's a valid IFC task
        try:
            if not task.is_a("IfcTask"):
                print(f"[WARNING] {operation_name}: Object is not an IfcTask: {type(task)}")
                return False
        except Exception as e:
            print(f"[ERROR] {operation_name}: Exception checking IfcTask type: {e}")
            return False

        return True

    @classmethod
    def _get_active_schedule_bbox(cls):
        """
        Calculate bounding box for the active work schedule.
        Returns center point, dimensions, and full bbox data.
        EXACT COPY from sequence.py delegation pattern
        """
        try:
            # Direct access to avoid circular import
            import bpy
            scene = bpy.context.scene

            # Fallback to scene properties access
            work_schedule = None
            if hasattr(scene, 'BIMSequenceProperties'):
                props = scene.BIMSequenceProperties
                if hasattr(props, 'active_work_schedule_id') and props.active_work_schedule_id:
                    try:
                        import ifcopenshell
                        ifc_file = ifcopenshell.open(props.ifc_file) if hasattr(props, 'ifc_file') else None
                        if ifc_file:
                            work_schedule = ifc_file.by_id(props.active_work_schedule_id)
                    except:
                        pass

            if not work_schedule:
                # Fallback to scene bbox
                return cls._get_scene_bounding_box()

            # Get products for this work schedule
            products = cls.get_work_schedule_products(work_schedule)
            if not products:
                return cls._get_scene_bounding_box()

            # Calculate bbox from schedule products
            return cls._calculate_products_bbox(products)

        except Exception as e:
            print(f"[WARNING] Error getting active schedule bbox: {e}")
            return cls._get_scene_bounding_box()

    @classmethod
    def _get_scene_bounding_box(cls):
        """
        Calculate overall scene bounding box from all visible mesh objects.
        Returns (center, dimensions, full_bbox_data)
        """
        min_coord = Vector((float('inf'), float('inf'), float('inf')))
        max_coord = Vector((float('-inf'), float('-inf'), float('-inf')))

        found_objects = False

        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and not obj.hide_viewport:
                try:
                    # Get world space bounding box
                    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]

                    for corner in bbox_corners:
                        min_coord.x = min(min_coord.x, corner.x)
                        min_coord.y = min(min_coord.y, corner.y)
                        min_coord.z = min(min_coord.z, corner.z)
                        max_coord.x = max(max_coord.x, corner.x)
                        max_coord.y = max(max_coord.y, corner.y)
                        max_coord.z = max(max_coord.z, corner.z)

                    found_objects = True
                except Exception:
                    continue

        if not found_objects:
            # Default bbox if no objects found
            min_coord = Vector((-10, -10, -10))
            max_coord = Vector((10, 10, 10))

        center = (min_coord + max_coord) / 2
        dimensions = max_coord - min_coord

        bbox_data = {
            'min': min_coord,
            'max': max_coord,
            'center': center,
            'dimensions': dimensions
        }

        return center, dimensions, bbox_data

    @classmethod
    def _calculate_products_bbox(cls, products):
        """Calculate bounding box from a list of IFC products."""
        min_coord = Vector((float('inf'), float('inf'), float('inf')))
        max_coord = Vector((float('-inf'), float('-inf'), float('-inf')))

        found_objects = False

        for product in products:
            try:
                obj = tool.Ifc.get_object(product)
                if obj and obj.type == 'MESH' and not obj.hide_viewport:
                    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]

                    for corner in bbox_corners:
                        min_coord.x = min(min_coord.x, corner.x)
                        min_coord.y = min(min_coord.y, corner.y)
                        min_coord.z = min(min_coord.z, corner.z)
                        max_coord.x = max(max_coord.x, corner.x)
                        max_coord.y = max(max_coord.y, corner.y)
                        max_coord.z = max(max_coord.z, corner.z)

                    found_objects = True
            except Exception:
                continue

        if not found_objects:
            return cls._get_scene_bounding_box()

        center = (min_coord + max_coord) / 2
        dimensions = max_coord - min_coord

        bbox_data = {
            'min': min_coord,
            'max': max_coord,
            'center': center,
            'dimensions': dimensions
        }

        return center, dimensions, bbox_data

    @classmethod
    def get_work_schedule_products(cls, work_schedule, sequence_tool=None):
        """
        Get all products associated with a work schedule.
        EXACT COPY from sequence.py delegation pattern
        """
        if not work_schedule:
            return []

        try:
            # Get all tasks in the work schedule
            tasks = []

            # Method 1: Direct task relationships
            if hasattr(work_schedule, 'Controls') and work_schedule.Controls:
                for rel in work_schedule.Controls:
                    if hasattr(rel, 'RelatedObjects'):
                        for related_obj in rel.RelatedObjects:
                            if related_obj.is_a("IfcTask"):
                                tasks.append(related_obj)

            # Method 2: Through work plan (if exists)
            if hasattr(work_schedule, 'Declares') and work_schedule.Declares:
                for rel in work_schedule.Declares:
                    if hasattr(rel, 'RelatedObjects'):
                        for obj in rel.RelatedObjects:
                            if obj.is_a("IfcWorkPlan"):
                                # Get tasks from work plan
                                if hasattr(obj, 'Declares') and obj.Declares:
                                    for plan_rel in obj.Declares:
                                        if hasattr(plan_rel, 'RelatedObjects'):
                                            for plan_obj in plan_rel.RelatedObjects:
                                                if plan_obj.is_a("IfcTask"):
                                                    tasks.append(plan_obj)

            # Collect products from all tasks
            products = set()
            for task in tasks:
                # Get outputs (construction products)
                if hasattr(task, 'HasAssignments') and task.HasAssignments:
                    for assignment in task.HasAssignments:
                        if assignment.is_a("IfcRelAssignsToProcess"):
                            if hasattr(assignment, 'RelatedObjects'):
                                for related_obj in assignment.RelatedObjects:
                                    if related_obj.is_a("IfcProduct"):
                                        products.add(related_obj)

                # Get inputs (demolition products)
                if hasattr(task, 'OperatesOn') and task.OperatesOn:
                    for operates_rel in task.OperatesOn:
                        if hasattr(operates_rel, 'RelatedObjects'):
                            for related_obj in operates_rel.RelatedObjects:
                                if related_obj.is_a("IfcProduct"):
                                    products.add(related_obj)

            return list(products)

        except Exception as e:
            print(f"[WARNING] Error getting work schedule products: {e}")
            return []

    @classmethod
    def select_work_schedule_products(cls, work_schedule):
        """Select all products associated with a work schedule in Blender."""
        if not work_schedule:
            return "No work schedule provided"

        try:
            products = cls.get_work_schedule_products(work_schedule)
            if not products:
                return f"No products found for work schedule: {getattr(work_schedule, 'Name', 'Unknown')}"

            # Clear current selection
            bpy.ops.object.select_all(action='DESELECT')

            selected_count = 0
            for product in products:
                try:
                    obj = tool.Ifc.get_object(product)
                    if obj:
                        obj.select_set(True)
                        selected_count += 1
                except Exception:
                    continue

            return f"Selected {selected_count} objects from work schedule: {getattr(work_schedule, 'Name', 'Unknown')}"

        except Exception as e:
            return f"Error selecting work schedule products: {e}"

    @classmethod
    def _save_original_object_colors(cls):
        """Guardar los colores originales de todos los objetos desde material IFC si es posible. EXACT COPY from sequence.py line ~7594"""
        try:
            original_colors = {}
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and hasattr(obj, 'color'):
                    # Intentar obtener el color del material IFC original primero
                    original_color = None
                    try:
                        if obj.material_slots and obj.material_slots[0].material:
                            material = obj.material_slots[0].material
                            if material.use_nodes:
                                principled = tool.Blender.get_material_node(material, "BSDF_PRINCIPLED")
                                if principled and principled.inputs.get("Base Color"):
                                    base_color = principled.inputs["Base Color"].default_value
                                    original_color = tuple([base_color[0], base_color[1], base_color[2], base_color[3]])
                    except Exception:
                        pass

                    # Fallback: usar el color actual del viewport si no se pudo obtener del material
                    if original_color is None:
                        original_color = tuple(obj.color)

                    original_colors[obj.name] = original_color

            bpy.context.scene['BIM_VarianceOriginalObjectColors'] = original_colors
            print(f"🔄 Saved original colors for {len(original_colors)} objects (from materials where possible)")

        except Exception as e:
            print(f"[ERROR] Error saving original object colors: {e}")

    @classmethod
    def _restore_original_object_colors(cls):
        """Restaurar los colores originales de todos los objetos. EXACT COPY from sequence.py line ~7626"""
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

            print(f"[OK] Restored original colors for {restored_count} objects")

        except Exception as e:
            print(f"[ERROR] Error restoring original object colors: {e}")

    @classmethod
    def _save_original_colors_optimized(cls, cache):
        """Save original colors using cache. EXACT COPY from sequence.py line ~8432"""
        import json
        original_colors = {}

        for obj in cache.scene_objects_cache:
            if obj.type == 'MESH':
                # Get original color from material or viewport
                original_color = list(obj.color)
                try:
                    if obj.material_slots and obj.material_slots[0].material:
                        material = obj.material_slots[0].material
                        if material.use_nodes:
                            principled = tool.Blender.get_material_node(material, "BSDF_PRINCIPLED")
                            if principled and principled.inputs.get("Base Color"):
                                base_color = principled.inputs["Base Color"].default_value
                                original_color = [base_color[0], base_color[1], base_color[2], base_color[3]]
                except:
                    pass
                original_colors[obj.name] = original_color

        # Save to scene
        try:
            bpy.context.scene['bonsai_animation_original_colors'] = json.dumps(original_colors)
            bpy.context.scene['BIM_VarianceOriginalObjectColors'] = True
        except Exception as e:
            print(f"[WARNING] Error saving colors: {e}")

    @classmethod
    def create_text_objects_static(cls, settings):
        """Creates static 3D text objects for snapshot mode (NO animation handler registration). EXACT COPY from sequence.py line ~5098"""
        from datetime import timedelta
        print("📸 Creating STATIC 3D text objects for snapshot mode")

        collection_name = "Schedule_Display_Texts"
        if collection_name in bpy.data.collections:
            collection = bpy.data.collections[collection_name]
            # Clear previous objects
            for obj in list(collection.objects):
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception:
                    pass
        else:
            collection = bpy.data.collections.new(collection_name)
            try:
                bpy.context.scene.collection.children.link(collection)
            except Exception:
                pass

        # Get schedule name for the Schedule_Name text
        schedule_name = "Unknown Schedule"
        try:
            # Direct access to avoid circular import
            import bpy
            scene = bpy.context.scene

            # Get schedule props directly from scene
            ws_props = None
            if hasattr(scene, 'BIMSequenceProperties'):
                ws_props = scene.BIMSequenceProperties

            if ws_props and hasattr(ws_props, 'active_work_schedule_id'):
                ws_id = ws_props.active_work_schedule_id
                if ws_id:
                    # Direct IFC access
                    try:
                        import ifcopenshell
                        if hasattr(ws_props, 'ifc_file') and ws_props.ifc_file:
                            ifc_file = ifcopenshell.open(ws_props.ifc_file)
                            work_schedule = ifc_file.by_id(ws_id)
                        else:
                            work_schedule = None
                    except:
                        work_schedule = None
                    if work_schedule and hasattr(work_schedule, 'Name'):
                        schedule_name = work_schedule.Name or "Unnamed Schedule"
        except Exception as e:
            print(f"[WARNING] Could not get schedule name: {e}")

        # ✅ FIXED: Proper Z-stacked positioning matching v117_P stable layout
        text_configs = [
                {"name": "Schedule_Name", "position": (0, 10, 6), "size": 1.4, "align": "CENTER", "color": (1, 1, 1, 1), "type": "schedule_name", "content": f"Schedule: {schedule_name}"},
                {"name": "Schedule_Date", "position": (0, 10, 5), "size": 1.2, "align": "CENTER", "color": (1, 1, 1, 1), "type": "date"},
                {"name": "Schedule_Week", "position": (0, 10, 4), "size": 1.0, "align": "CENTER", "color": (1, 1, 1, 1), "type": "week"},
                {"name": "Schedule_Day_Counter", "position": (0, 10, 3), "size": 0.8, "align": "CENTER", "color": (1, 1, 1, 1), "type": "day_counter"},
                {"name": "Schedule_Progress", "position": (0, 10, 2), "size": 1.0, "align": "CENTER", "color": (1, 1, 1, 1), "type": "progress"},
            ]
        created_texts = []
        for config in text_configs:
            text_obj = cls._create_static_text(config, settings, collection)
            created_texts.append(text_obj)

        # ✅ ENSURE PARENT EMPTY EXISTS for proper organization
        parent_name = "Schedule_Display_Parent"
        parent_empty = bpy.data.objects.get(parent_name)
        if not parent_empty:
            print(f"📝 Creating {parent_name} for text organization")
            parent_empty = bpy.data.objects.new(parent_name, None)
            collection.objects.link(parent_empty)
            parent_empty.empty_display_type = 'PLAIN_AXES'
            parent_empty.empty_display_size = 2
            parent_empty.location = (0, 0, 0)

        # ✅ PARENT ALL TEXTS to the empty for organized control
        for text_obj in created_texts:
            if text_obj and text_obj.parent != parent_empty:
                try:
                    text_obj.parent = parent_empty
                    print(f"📝 Text '{text_obj.name}' parented to {parent_name}")
                except Exception as e:
                    print(f"[WARNING] Could not parent text '{text_obj.name}': {e}")

        print(f"[OK] Created {len(created_texts)} static 3D text objects for snapshot mode")
        print(f"[OK] All texts organized under parent: {parent_name}")
        return created_texts

    @classmethod
    def _create_static_text(cls, config, settings, collection):
        """Creates a single static 3D text object with fixed content based on snapshot date. Helper for create_text_objects_static"""
        text_curve = bpy.data.curves.new(name=config["name"], type='FONT')
        text_curve.size = config["size"]
        text_curve.align_x = config["align"]
        text_curve.align_y = 'CENTER'
        text_curve["text_type"] = config["type"]

        # Get the snapshot date from settings
        snapshot_date = settings.get("start") if isinstance(settings, dict) else getattr(settings, "start", None)

        # Set the text content based on the type and snapshot date
        text_type = config["type"].lower()

        # Check if content is pre-defined in config (for schedule_name)
        if "content" in config:
            text_curve.body = config["content"]
        elif text_type == "date":
            if snapshot_date:
                try:
                    text_curve.body = snapshot_date.strftime("%d/%m/%Y")
                except Exception:
                    text_curve.body = str(snapshot_date).split("T")[0]
            else:
                text_curve.body = "Date: --"
        elif text_type == "week":
            text_curve.body = cls._calculate_static_week_text(snapshot_date)
        elif text_type == "day_counter":
            text_curve.body = cls._calculate_static_day_text(snapshot_date)
        elif text_type == "progress":
            text_curve.body = cls._calculate_static_progress_text(snapshot_date)
        elif text_type == "schedule_name":
            text_curve.body = "Schedule: Unknown"
        else:
            text_curve.body = f"Static {config['type']}"

        # Create the text object
        text_obj = bpy.data.objects.new(config["name"], text_curve)
        text_obj.location = config["position"]

        # Set color if available
        if "color" in config:
            color = config["color"]
            if hasattr(text_obj, "color"):
                text_obj.color = color

        collection.objects.link(text_obj)
        return text_obj

    @classmethod
    def _calculate_static_week_text(cls, snapshot_date):
        """Calculate week text for static display."""
        if not snapshot_date:
            return "Week: --"

        try:
            week_number = snapshot_date.isocalendar()[1]
            return f"Week {week_number}"
        except Exception:
            return "Week: --"

    @classmethod
    def _calculate_static_day_text(cls, snapshot_date):
        """Calculate day counter text for static display."""
        if not snapshot_date:
            return "Day: --"

        try:
            # Simple day counter from year start
            year_start = datetime(snapshot_date.year, 1, 1).date()
            if hasattr(snapshot_date, 'date'):
                day_count = (snapshot_date.date() - year_start).days + 1
            else:
                day_count = (snapshot_date - year_start).days + 1
            return f"Day {day_count}"
        except Exception:
            return "Day: --"

    @classmethod
    def _calculate_static_progress_text(cls, snapshot_date):
        """Calculate progress text for static display."""
        if not snapshot_date:
            return "Progress: --%"

        try:
            # Direct access to avoid circular import
            import bpy
            scene = bpy.context.scene

            # Fallback to scene properties access
            work_schedule = None
            if hasattr(scene, 'BIMSequenceProperties'):
                props = scene.BIMSequenceProperties
                if hasattr(props, 'active_work_schedule_id') and props.active_work_schedule_id:
                    try:
                        import ifcopenshell
                        ifc_file = ifcopenshell.open(props.ifc_file) if hasattr(props, 'ifc_file') else None
                        if ifc_file:
                            work_schedule = ifc_file.by_id(props.active_work_schedule_id)
                    except:
                        pass

            if not work_schedule:
                return "Progress: --%"

            # Simple progress calculation based on schedule duration
            # This is a simplified version - could be enhanced with actual task completion
            return "Progress: --%"  # Placeholder for now
        except Exception:
            return "Progress: --%"

    @classmethod
    def get_ifc_entities_for_objects(cls, objects):
        """Get IFC entities for a list of Blender objects."""
        entities = []
        for obj in objects:
            try:
                entity = tool.Ifc.get_entity(obj)
                if entity:
                    entities.append(entity)
            except Exception:
                continue
        return entities

    @classmethod
    def get_objects_for_entities(cls, entities):
        """Get Blender objects for a list of IFC entities."""
        objects = []
        for entity in entities:
            try:
                obj = tool.Ifc.get_object(entity)
                if obj:
                    objects.append(obj)
            except Exception:
                continue
        return objects

    @classmethod
    def clear_text_objects(cls):
        """Clear all schedule display text objects."""
        collection_name = "Schedule_Display_Texts"
        collection = bpy.data.collections.get(collection_name)
        if collection:
            # Remove all objects in the collection
            for obj in list(collection.objects):
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception:
                    pass

            # Remove the collection itself
            try:
                bpy.data.collections.remove(collection)
            except Exception:
                pass

        print(f"[OK] Cleared text objects collection: {collection_name}")

    @classmethod
    def get_visible_mesh_objects(cls):
        """Get all visible mesh objects in the scene."""
        visible_objects = []
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and not obj.hide_viewport and not obj.hide_render:
                visible_objects.append(obj)
        return visible_objects

    @classmethod
    def are_entities_same_class(cls, entities):
        """
        Check if all entities are the same IFC class.
        EXACT COPY from sequence.py line ~2294
        """
        if not entities:
            return False
        if len(entities) == 1:
            return True
        first_class = entities[0].is_a()
        for entity in entities:
            if entity.is_a() != first_class:
                return False
        return True

    @classmethod
    def select_products(cls, products):
        """
        Select products in the scene.
        EXACT COPY from sequence.py line ~2565
        """
        try:
            import tool

            # Deselect all
            bpy.ops.object.select_all(action='DESELECT')

            # Select the products
            for product in products:
                obj = tool.Ifc.get_object(product)
                if obj:
                    obj.select_set(True)

            # Set active object
            if products:
                first_obj = tool.Ifc.get_object(products[0])
                if first_obj:
                    bpy.context.view_layer.objects.active = first_obj

        except Exception as e:
            print(f"[ERROR] Error selecting products: {e}")

    @classmethod
    def select_unassigned_work_schedule_products(cls):
        """
        Select work schedule products that are not assigned to any task.
        EXACT COPY from sequence.py line ~2401
        """
        try:
            import tool
            from ..data.task_manager import TaskManager

            props = TaskManager.get_work_schedule_props()
            if not props or not props.active_work_schedule_id:
                return "No active work schedule"

            work_schedule = tool.Ifc.get().by_id(props.active_work_schedule_id)
            if not work_schedule:
                return "Work schedule not found"

            # Get all products in the work schedule
            all_products = cls.get_work_schedule_products(work_schedule)
            if not all_products:
                return "No products found in work schedule"

            # Get all assigned products
            assigned_products = set()

            def get_all_tasks_recursive(tasks):
                """Get all tasks recursively."""
                all_tasks = []
                for task in tasks:
                    all_tasks.append(task)
                    if hasattr(task, 'TaskNesting'):
                        nested = task.TaskNesting
                        if nested and hasattr(nested, 'RelatedTasks'):
                            all_tasks.extend(get_all_tasks_recursive(nested.RelatedTasks))
                return all_tasks

            # Collect all tasks
            all_tasks = []
            if hasattr(work_schedule, 'RelatedDeclarations'):
                for rel_declares in work_schedule.RelatedDeclarations:
                    if hasattr(rel_declares, 'RelatedDefinitions'):
                        tasks = [t for t in rel_declares.RelatedDefinitions if t.is_a("IfcTask")]
                        all_tasks.extend(get_all_tasks_recursive(tasks))

            # Get all assigned products from all tasks
            for task in all_tasks:
                if hasattr(task, 'TaskInputs'):
                    for task_input in task.TaskInputs or []:
                        for product in task_input.InputProducts or []:
                            assigned_products.add(product)

                if hasattr(task, 'TaskOutputs'):
                    for task_output in task.TaskOutputs or []:
                        for product in task_output.OutputProducts or []:
                            assigned_products.add(product)

            # Find unassigned products
            unassigned_products = [p for p in all_products if p not in assigned_products]

            if not unassigned_products:
                return "All products are assigned to tasks"

            # Select unassigned products
            cls.select_products(unassigned_products)

            return f"Selected {len(unassigned_products)} unassigned products"

        except Exception as e:
            import traceback
            print(f"[ERROR] Error selecting unassigned products: {e}")
            print(traceback.format_exc())
            return f"Error: {e}"

    @classmethod
    def set_objects_visibility(cls, objects, visible=True):
        """Set visibility for a list of objects."""
        count = 0
        for obj in objects:
            try:
                obj.hide_viewport = not visible
                obj.hide_render = not visible
                count += 1
            except Exception:
                continue

        status = "shown" if visible else "hidden"
        print(f"[OK] {status} {count} objects")
        return count

    @classmethod
    def _build_object_task_mapping(cls, all_tasks):
        """Build object-task mapping using Bonsai system."""
        object_task_map = {}

        print(f"[CHECK] Building object-task mapping for {len(all_tasks)} tasks using Bonsai system...")

        # Use proper Bonsai method to get outputs
        try:
            import bonsai.tool as tool
            ifc_file = tool.Ifc.get()
        except ImportError:
            # Fallback for test environments
            ifc_file = None

        if not ifc_file:
            print("[ERROR] No IFC file available")
            return object_task_map

        for task_pg in all_tasks:
            try:
                task_ifc = ifc_file.by_id(task_pg.ifc_definition_id)
                if not task_ifc:
                    continue

                # Use proper Bonsai method to get outputs
                # Import the sequence tool to access get_task_outputs
                try:
                    from ... import Sequence as sequence_tool
                    outputs = sequence_tool.get_task_outputs(task_ifc)
                except ImportError:
                    # Fallback - try to get outputs directly if available
                    outputs = getattr(task_ifc, 'HasAssignments', [])

                if outputs:
                    print(f"📋 Task {task_pg.ifc_definition_id} ({task_pg.name}) has {len(outputs)} outputs:")
                    for output in outputs:
                        object_task_map[output.id()] = task_pg
                        print(f"  → Output {output.id()} ({getattr(output, 'Name', 'Unknown')}) assigned to task")
                else:
                    print(f"[ERROR] Task {task_pg.ifc_definition_id} ({task_pg.name}) has no outputs")

            except Exception as e:
                print(f"[ERROR] Error mapping task {task_pg.ifc_definition_id}: {e}")
                continue

        print(f"[OK] Built mapping: {len(object_task_map)} object-task relationships")
        return object_task_map


# Compatibility functions for direct access
def validate_task_object(task, operation_name="operation"):
    """Standalone function for task validation."""
    return ObjectManager.validate_task_object(task, operation_name)

def get_scene_bounding_box():
    """Standalone function for scene bounding box."""
    return ObjectManager._get_scene_bounding_box()

def save_original_colors():
    """Standalone function for saving original colors."""
    return ObjectManager._save_original_object_colors()

def restore_original_colors():
    """Standalone function for restoring original colors."""
    return ObjectManager._restore_original_object_colors()