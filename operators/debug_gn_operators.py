# Debug operators for Geometry Nodes system
import bpy
import bmesh
from bpy.types import Operator


class DebugGNSystem(Operator):
    bl_idname = "bim.debug_gn_system"
    bl_label = "Debug GN System"
    bl_description = "Diagnose Geometry Nodes animation system issues"

    def execute(self, context):
        print("\n" + "="*60)
        print("🔍 GEOMETRY NODES SYSTEM DIAGNOSIS")
        print("="*60)

        # 1. Check for node tree
        node_tree_name = "Bonsai 4D Node Tree"
        if node_tree_name in bpy.data.node_groups:
            node_tree = bpy.data.node_groups[node_tree_name]
            print(f"✅ Node tree '{node_tree_name}' exists with {len(node_tree.nodes)} nodes")
        else:
            print(f"❌ Node tree '{node_tree_name}' NOT FOUND")
            return {'CANCELLED'}

        # 2. Check for controller
        controllers = [obj for obj in bpy.data.objects if obj.get("is_gn_controller", False)]
        if controllers:
            controller = controllers[0]
            print(f"✅ Controller found: {controller.name}")
        else:
            print("❌ No GN controller found")

        # 3. Check objects with GN modifiers
        objects_with_modifiers = []
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod.name == "Bonsai 4D Animation" and mod.type == 'NODES':
                        objects_with_modifiers.append(obj)
                        break

        print(f"🎯 Found {len(objects_with_modifiers)} objects with GN modifiers")

        # 4. Detailed analysis of each object
        for i, obj in enumerate(objects_with_modifiers[:5]):  # Limit to first 5 for readability
            print(f"\n--- OBJECT {i+1}: {obj.name} ---")

            # Check attributes
            if obj.data and hasattr(obj.data, 'attributes'):
                attrs = obj.data.attributes
                schedule_start = attrs.get("schedule_start")
                schedule_end = attrs.get("schedule_end")
                effect_type = attrs.get("effect_type")

                print(f"  Attributes present: {list(attrs.keys())}")

                if schedule_start:
                    # Get actual values from the attribute
                    values = [schedule_start.data[i].value for i in range(min(3, len(schedule_start.data)))]
                    print(f"  schedule_start sample values: {values}")
                else:
                    print("  ❌ schedule_start attribute MISSING")

                if schedule_end:
                    values = [schedule_end.data[i].value for i in range(min(3, len(schedule_end.data)))]
                    print(f"  schedule_end sample values: {values}")
                else:
                    print("  ❌ schedule_end attribute MISSING")

                if effect_type:
                    values = [effect_type.data[i].value for i in range(min(3, len(effect_type.data)))]
                    print(f"  effect_type sample values: {values}")
                else:
                    print("  ❌ effect_type attribute MISSING")
            else:
                print("  ❌ No attributes found on object")

            # Check modifier setup
            modifier = None
            for mod in obj.modifiers:
                if mod.name == "Bonsai 4D Animation" and mod.type == 'NODES':
                    modifier = mod
                    break

            if modifier:
                print(f"  ✅ Modifier found: {modifier.name}")
                print(f"  Node group: {modifier.node_group.name if modifier.node_group else 'NONE'}")

                # Check inputs
                for input_name in ['Current Frame', 'Schedule Type', 'ColorType Group']:
                    if input_name in modifier:
                        value = modifier[input_name]
                        print(f"  Input '{input_name}': {value}")
                    else:
                        print(f"  ❌ Input '{input_name}' MISSING")

                # Check drivers
                if modifier.animation_data and modifier.animation_data.drivers:
                    print(f"  ✅ Has {len(modifier.animation_data.drivers)} drivers")
                    for driver in modifier.animation_data.drivers:
                        print(f"    Driver: {driver.data_path} = {driver.driver.expression}")
                else:
                    print("  ❌ No drivers found")
            else:
                print("  ❌ No GN modifier found")

        # 5. Check current frame effect
        current_frame = context.scene.frame_current
        print(f"\n📅 Current frame: {current_frame}")
        print("Try changing the frame and see if objects change...")

        # 6. Recommendations
        print("\n🔧 RECOMMENDATIONS:")
        if not objects_with_modifiers:
            print("- No objects found with GN modifiers. Run the GN animation creation first.")

        missing_attrs = False
        for obj in objects_with_modifiers[:3]:
            if obj.data and hasattr(obj.data, 'attributes'):
                if "schedule_start" not in obj.data.attributes:
                    missing_attrs = True
                    break

        if missing_attrs:
            print("- Attributes are missing. The baking process may have failed.")
            print("- Check if the async task completed successfully.")

        print("="*60 + "\n")

        return {'FINISHED'}


class TestDriversDebug(Operator):
    bl_idname = "bim.test_drivers_debug"
    bl_label = "Test Drivers Debug"
    bl_description = "Debug if drivers are updating when frame changes"

    def execute(self, context):
        print("\n" + "="*60)
        print("🔧 TESTING DRIVERS AND GEOMETRY NODES")
        print("="*60)

        # Test at different frames
        test_frames = [1, 50, 100, 150, 200, 250, 300]

        for frame in test_frames:
            print(f"\n📅 FRAME {frame}:")
            context.scene.frame_set(frame)

            # Force update
            bpy.context.view_layer.update()

            # Check objects with GN modifiers
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    modifier = None
                    for mod in obj.modifiers:
                        if mod.name == "Bonsai 4D Animation" and mod.type == 'NODES':
                            modifier = mod
                            break

                    if modifier:
                        # Check driver values
                        current_frame_value = modifier.get("Socket_1", "NOT_FOUND")
                        schedule_type_value = modifier.get("Socket_2", "NOT_FOUND")
                        colortype_value = modifier.get("Socket_3", "NOT_FOUND")

                        print(f"  {obj.name}:")
                        print(f"    Socket_1 (Current Frame): {current_frame_value}")
                        print(f"    Socket_2 (Schedule Type): {schedule_type_value}")
                        print(f"    Socket_3 (ColorType): {colortype_value}")

                        # Check if object is visible
                        visible = obj.visible_get()
                        print(f"    Object visible: {visible}")

                        # Check attributes
                        if obj.data and hasattr(obj.data, 'attributes'):
                            start = obj.data.attributes.get("schedule_start")
                            end = obj.data.attributes.get("schedule_end")
                            if start and end:
                                start_val = start.data[0].value if len(start.data) > 0 else "NO_DATA"
                                end_val = end.data[0].value if len(end.data) > 0 else "NO_DATA"
                                print(f"    Attributes: start={start_val}, end={end_val}")

        self.report({'INFO'}, "Driver debug completed - check console")
        return {'FINISHED'}


class TestGNAnimation(Operator):
    bl_idname = "bim.test_gn_animation"
    bl_label = "Test GN Animation"
    bl_description = "Test if Geometry Nodes animation is working by changing frame"

    def execute(self, context):
        print("\n" + "="*60)
        print("🎬 TESTING GEOMETRY NODES ANIMATION")
        print("="*60)

        # Test frame changes
        original_frame = context.scene.frame_current
        test_frames = [1, 50, 100, 150, 200, 250]

        for frame in test_frames:
            context.scene.frame_set(frame)
            print(f"📅 Frame {frame}: Testing visibility and materials...")

            # Check objects with GN modifiers
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    modifier = None
                    for mod in obj.modifiers:
                        if mod.name == "Bonsai 4D Animation" and mod.type == 'NODES':
                            modifier = mod
                            break

                    if modifier:
                        # Check if object is visible
                        visible = obj.visible_get()
                        print(f"  {obj.name}: visible={visible}")

                        # Check current material
                        if obj.data.materials:
                            material = obj.data.materials[0] if obj.data.materials else None
                            print(f"    Material: {material.name if material else 'None'}")

        # Restore original frame
        context.scene.frame_set(original_frame)

        self.report({'INFO'}, "Animation test completed - check console")
        return {'FINISHED'}


class DebugAttributeValues(Operator):
    bl_idname = "bim.debug_attribute_values"
    bl_label = "Debug Attribute Values"
    bl_description = "Debug schedule_start and schedule_end attribute values"

    def execute(self, context):
        print("\n" + "=" * 60)
        print("🔍 DEBUG 1: ATTRIBUTE VALUES")
        print("=" * 60)

        for obj in context.scene.objects:
            if obj.type == 'MESH' and obj.data and hasattr(obj.data, 'attributes'):
                attrs = obj.data.attributes

                # Check if has GN modifier
                has_gn = any(mod.name == "Bonsai 4D Animation" for mod in obj.modifiers)
                if not has_gn:
                    continue

                print(f"\n--- OBJECT: {obj.name} ---")

                # Check schedule_start
                if "schedule_start" in attrs:
                    start_attr = attrs["schedule_start"]
                    values = [start_attr.data[i].value for i in range(min(5, len(start_attr.data)))]
                    print(f"  schedule_start: {values} (domain: {start_attr.domain})")
                else:
                    print("  ❌ schedule_start MISSING")

                # Check schedule_end
                if "schedule_end" in attrs:
                    end_attr = attrs["schedule_end"]
                    values = [end_attr.data[i].value for i in range(min(5, len(end_attr.data)))]
                    print(f"  schedule_end: {values} (domain: {end_attr.domain})")
                else:
                    print("  ❌ schedule_end MISSING")

                # Expected vs actual
                print(f"  Expected range: Objects should be visible between start-end frames")

        self.report({'INFO'}, "Attribute debug completed - check console")
        return {'FINISHED'}


class TestSpeedIntegration(Operator):
    bl_idname = "bim.test_speed_integration"
    bl_label = "Test Speed Integration"
    bl_description = "Test if Speed Settings are properly integrated with Geometry Nodes"

    def execute(self, context):
        print("\n" + "=" * 60)
        print("🔍 DEBUG 2: SPEED INTEGRATION")
        print("=" * 60)

        # Test different speed settings
        speed_values = [0.5, 1.0, 2.0, 4.0]
        original_frame = context.scene.frame_current
        test_frame = 100

        for speed in speed_values:
            print(f"\n🎯 TESTING SPEED: {speed}x")

            # Set speed in animation properties
            try:
                if hasattr(context.scene, 'BIMAnimationProperties'):
                    context.scene.BIMAnimationProperties.playback_speed = speed
                    print(f"✅ Set playback_speed to {speed}")
                else:
                    print("❌ BIMAnimationProperties not found")
                    continue
            except Exception as e:
                print(f"❌ Failed to set speed: {e}")
                continue

            # Set frame and force update
            context.scene.frame_set(test_frame)
            context.view_layer.update()

            # Check GN modifiers for speed multiplier
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    for mod in obj.modifiers:
                        if mod.name == "Bonsai 4D Animation" and mod.type == 'NODES':
                            # Check if Speed Multiplier input exists and has correct value
                            speed_inputs = [key for key in mod.keys()
                                          if any(term in key.lower() for term in ['speed', 'socket_4', 'input_5'])]

                            if speed_inputs:
                                speed_input = speed_inputs[0]
                                current_speed = mod.get(speed_input, "NOT_FOUND")
                                print(f"  {obj.name}: {speed_input} = {current_speed}")

                                # Check if driver is working
                                if hasattr(mod, 'animation_data') and mod.animation_data:
                                    for driver in mod.animation_data.drivers:
                                        if speed_input in driver.data_path:
                                            print(f"    Driver expression: {driver.driver.expression}")
                                            print(f"    Driver variables: {[var.name for var in driver.driver.variables]}")
                            else:
                                print(f"  {obj.name}: No speed input found")
                            break

        # Restore original frame
        context.scene.frame_set(original_frame)

        self.report({'INFO'}, "Speed integration test completed - check console")
        return {'FINISHED'}


class DebugVisibilityLogic(Operator):
    bl_idname = "bim.debug_visibility_logic"
    bl_label = "Debug Visibility Logic"
    bl_description = "Debug if visibility logic inversion is working correctly"

    def execute(self, context):
        print("\n" + "=" * 60)
        print("🔍 DEBUG 3: VISIBILITY LOGIC")
        print("=" * 60)

        # Test at problem frame
        test_frame = 150
        context.scene.frame_set(test_frame)

        print(f"Testing at FRAME {test_frame} (where objects disappear):")

        for obj in context.scene.objects:
            if obj.type == 'MESH':
                # Check if has GN modifier
                gn_modifier = None
                for mod in obj.modifiers:
                    if mod.name == "Bonsai 4D Animation" and mod.type == 'NODES':
                        gn_modifier = mod
                        break

                if not gn_modifier:
                    continue

                print(f"\n--- OBJECT: {obj.name} ---")

                # Check inputs to modifier
                current_frame_val = gn_modifier.get("Socket_1", "NOT_FOUND")
                speed_val = gn_modifier.get("Socket_4", "NOT_FOUND")

                print(f"  Current Frame input: {current_frame_val}")
                print(f"  Speed Multiplier input: {speed_val}")

                # Calculate effective frame
                try:
                    effective_frame = float(current_frame_val) * float(speed_val) if current_frame_val != "NOT_FOUND" and speed_val != "NOT_FOUND" else "CALC_ERROR"
                    print(f"  Effective Frame (frame * speed): {effective_frame}")
                except:
                    print(f"  Effective Frame: CALCULATION_ERROR")

                # Check attributes
                if obj.data and hasattr(obj.data, 'attributes'):
                    start_attr = obj.data.attributes.get("schedule_start")
                    end_attr = obj.data.attributes.get("schedule_end")

                    if start_attr and end_attr:
                        start_val = start_attr.data[0].value if len(start_attr.data) > 0 else "NO_DATA"
                        end_val = end_attr.data[0].value if len(end_attr.data) > 0 else "NO_DATA"

                        print(f"  schedule_start: {start_val}")
                        print(f"  schedule_end: {end_val}")

                        # Manual visibility calculation
                        try:
                            if effective_frame != "CALC_ERROR" and start_val != "NO_DATA" and end_val != "NO_DATA":
                                should_be_visible = float(effective_frame) >= float(start_val) and float(effective_frame) <= float(end_val)
                                print(f"  SHOULD BE VISIBLE: {should_be_visible}")
                                print(f"  Logic: {effective_frame} >= {start_val} AND {effective_frame} <= {end_val}")

                                # Check actual visibility
                                actual_visible = obj.visible_get()
                                print(f"  ACTUALLY VISIBLE: {actual_visible}")

                                if should_be_visible != actual_visible:
                                    print(f"  🚨 VISIBILITY MISMATCH!")
                        except Exception as e:
                            print(f"  ❌ Manual calculation failed: {e}")

        self.report({'INFO'}, "Visibility logic debug completed - check console")
        return {'FINISHED'}


class DebugTaskObjectMapping(Operator):
    bl_idname = "bim.debug_task_object_mapping"
    bl_label = "Debug Task-Object Mapping"
    bl_description = "Debug if objects are correctly mapped to tasks with product_id"

    def execute(self, context):
        print("\n" + "=" * 60)
        print("🔍 DEBUG 4: TASK-OBJECT MAPPING")
        print("=" * 60)

        # Count objects with BIMObjectProperties
        objects_with_props = []
        objects_with_ifc_id = []

        for obj in context.scene.objects:
            if obj.type == 'MESH':
                if hasattr(obj, 'BIMObjectProperties'):
                    objects_with_props.append(obj)
                    props = obj.BIMObjectProperties
                    if hasattr(props, 'ifc_definition_id') and props.ifc_definition_id:
                        objects_with_ifc_id.append({
                            'object': obj,
                            'product_id': props.ifc_definition_id
                        })

        print(f"📊 OBJECTS WITH BIMObjectProperties: {len(objects_with_props)}")
        print(f"📊 OBJECTS WITH ifc_definition_id: {len(objects_with_ifc_id)}")

        # Show first 5 mappings
        print(f"\n--- FIRST 5 OBJECT → PRODUCT_ID MAPPINGS ---")
        for i, item in enumerate(objects_with_ifc_id[:5]):
            obj = item['object']
            product_id = item['product_id']
            print(f"  {i+1}. {obj.name} → product_id: {product_id}")

            # Check if object has GN modifier
            has_gn = any(mod.name == "Bonsai 4D Animation" for mod in obj.modifiers)
            print(f"     Has GN modifier: {has_gn}")

            # Check if object has schedule attributes
            if obj.data and hasattr(obj.data, 'attributes'):
                has_start = "schedule_start" in obj.data.attributes
                has_end = "schedule_end" in obj.data.attributes
                print(f"     Has schedule attributes: start={has_start}, end={has_end}")
            else:
                print(f"     Has schedule attributes: NO")

        print(f"\n🎯 RECOMMENDATION:")
        if len(objects_with_ifc_id) == 0:
            print("❌ NO objects found with ifc_definition_id!")
            print("   This means task-object mapping will FAIL completely.")
            print("   GN system cannot find objects to animate.")
        elif len(objects_with_ifc_id) < 10:
            print("⚠️  Very few objects have ifc_definition_id.")
            print("   Check if BIM properties are correctly set.")

        self.report({'INFO'}, "Task-object mapping debug completed - check console")
        return {'FINISHED'}


class DebugColortypeMapping(Operator):
    bl_idname = "bim.debug_colortype_mapping"
    bl_label = "Debug ColorType Mapping"
    bl_description = "Debug if tasks have correct ColorType assignments"

    def execute(self, context):
        print("\n" + "=" * 60)
        print("🔍 DEBUG 5: COLORTYPE MAPPING")
        print("=" * 60)

        try:
            # Try to get work schedule data
            import bonsai.tool as tool
            if hasattr(tool, 'Sequence'):
                schedule_props = tool.Sequence.get_work_schedule_props()
                print(f"✅ Work schedule props accessible")

                # Try to get animation props
                anim_props = tool.Sequence.get_animation_props()
                print(f"✅ Animation props accessible")

                # Check ColorTypes
                if hasattr(anim_props, 'ColorTypes'):
                    colortypes = list(anim_props.ColorTypes)
                    print(f"📊 AVAILABLE COLORTYPES: {len(colortypes)}")

                    for i, colortype in enumerate(colortypes[:5]):  # First 5
                        print(f"  {i+1}. {colortype.name}")
                        if hasattr(colortype, 'completed_color'):
                            print(f"      Color: {colortype.completed_color}")
                        if hasattr(colortype, 'tasks'):
                            tasks_count = len(list(colortype.tasks)) if colortype.tasks else 0
                            print(f"      Tasks assigned: {tasks_count}")
                else:
                    print("❌ No ColorTypes found in animation properties")

        except Exception as e:
            print(f"❌ Failed to access schedule/animation data: {e}")

        # Check objects for colortype attributes
        objects_with_colortype = 0
        for obj in context.scene.objects:
            if obj.type == 'MESH' and obj.data and hasattr(obj.data, 'attributes'):
                if "object_colortype_id" in obj.data.attributes:
                    objects_with_colortype += 1
                    if objects_with_colortype <= 3:  # Show first 3
                        colortype_attr = obj.data.attributes["object_colortype_id"]
                        colortype_val = colortype_attr.data[0].value if len(colortype_attr.data) > 0 else "NO_DATA"
                        print(f"  Object {obj.name}: colortype_id = {colortype_val}")

        print(f"📊 OBJECTS WITH COLORTYPE ATTRIBUTES: {objects_with_colortype}")

        # Check the empty mappings issue
        print(f"\n🚨 CHECKING GN SYSTEM COLORTYPE MAPPING...")
        print("In create_gn_animation_system():")
        print("  profiles_data = {}  ← EMPTY")
        print("  colortype_mapping = {}  ← EMPTY")
        print("This means ALL objects get colortype_id = 13 (NOTDEFINED)")

        self.report({'INFO'}, "ColorType mapping debug completed - check console")
        return {'FINISHED'}


class DebugAttributeBaking(Operator):
    bl_idname = "bim.debug_attribute_baking"
    bl_label = "Debug Attribute Baking"
    bl_description = "Debug if attributes are being baked correctly during GN creation"

    def execute(self, context):
        print("\n" + "=" * 60)
        print("🔍 DEBUG 6: ATTRIBUTE BAKING PROCESS")
        print("=" * 60)

        # Simulate the product_frames processing
        print("🔄 SIMULATING GN CREATION PROCESS...")

        # Check objects that would be processed
        processable_objects = []
        for obj in context.scene.objects:
            if obj.type == 'MESH' and hasattr(obj, 'BIMObjectProperties'):
                props = obj.BIMObjectProperties
                if hasattr(props, 'ifc_definition_id') and props.ifc_definition_id:
                    processable_objects.append({
                        'object': obj,
                        'product_id': props.ifc_definition_id
                    })

        print(f"📊 OBJECTS READY FOR PROCESSING: {len(processable_objects)}")

        if len(processable_objects) == 0:
            print("❌ NO objects can be processed!")
            print("   - Objects need BIMObjectProperties")
            print("   - Objects need ifc_definition_id set")
            print("   - This explains why GN system has no schedule data")
            return {'FINISHED'}

        # Show what SHOULD happen vs what IS happening
        print(f"\n--- EXPECTED PROCESS ---")
        for i, item in enumerate(processable_objects[:3]):  # First 3
            obj = item['object']
            product_id = item['product_id']

            print(f"{i+1}. Object: {obj.name}")
            print(f"   product_id: {product_id}")
            print(f"   Expected: Find this product_id in product_frames")
            print(f"   Expected: Extract start/end frames from frame_data")
            print(f"   Expected: Bake schedule_start/end attributes")

            # Check current state
            if obj.data and hasattr(obj.data, 'attributes'):
                has_start = "schedule_start" in obj.data.attributes
                has_end = "schedule_end" in obj.data.attributes
                print(f"   CURRENT: schedule attributes exist: start={has_start}, end={has_end}")

                if has_start:
                    start_attr = obj.data.attributes["schedule_start"]
                    start_val = start_attr.data[0].value if len(start_attr.data) > 0 else "NO_DATA"
                    print(f"   CURRENT: schedule_start = {start_val}")
            else:
                print(f"   CURRENT: No attributes at all")

        # Check the data flow issue
        print(f"\n🚨 POTENTIAL DATA FLOW ISSUES:")
        print("1. product_frames format might be wrong")
        print("2. ifc_definition_id might not match product_id keys")
        print("3. Frame data extraction might be failing")
        print("4. Attribute baking process might have errors")

        self.report({'INFO'}, "Attribute baking debug completed - check console")
        return {'FINISHED'}


class DebugModifierApplication(Operator):
    bl_idname = "bim.debug_modifier_application"
    bl_label = "Debug GN Modifier Application"
    bl_description = "Debug why GN modifiers are not being applied to objects"

    def execute(self, context):
        print("\n" + "=" * 60)
        print("🔍 DEBUG 7: GN MODIFIER APPLICATION")
        print("=" * 60)

        # Check if node tree exists
        node_tree_name = "Bonsai 4D Node Tree"
        if node_tree_name in bpy.data.node_groups:
            node_tree = bpy.data.node_groups[node_tree_name]
            print(f"✅ Node tree exists: {node_tree_name}")
            print(f"   Nodes: {len(node_tree.nodes)}")
            print(f"   Interface inputs: {len([s for s in node_tree.interface.items_tree if s.in_out == 'INPUT'])}")
        else:
            print(f"❌ Node tree missing: {node_tree_name}")
            print("   Cannot apply modifiers without node tree!")
            return {'FINISHED'}

        # Check controller
        controllers = [obj for obj in bpy.data.objects if obj.get("is_gn_controller", False)]
        print(f"🎮 Controllers found: {len(controllers)}")
        if controllers:
            controller = controllers[0]
            print(f"   Controller: {controller.name}")
        else:
            print("❌ No GN controller found")

        # Get objects that SHOULD have modifiers (have schedule attributes)
        objects_with_attributes = []
        objects_with_modifiers = []

        for obj in context.scene.objects:
            if obj.type == 'MESH' and obj.data and hasattr(obj.data, 'attributes'):
                if "schedule_start" in obj.data.attributes:
                    objects_with_attributes.append(obj)

                    # Check if has GN modifier
                    for mod in obj.modifiers:
                        if mod.name == "Bonsai 4D Animation" and mod.type == 'NODES':
                            objects_with_modifiers.append(obj)
                            break

        print(f"📊 Objects WITH schedule attributes: {len(objects_with_attributes)}")
        print(f"📊 Objects WITH GN modifiers: {len(objects_with_modifiers)}")
        print(f"🚨 MISSING modifiers: {len(objects_with_attributes) - len(objects_with_modifiers)}")

        if len(objects_with_attributes) == 0:
            print("❌ No objects with attributes found - baking failed")
            return {'FINISHED'}

        # Test applying modifier to one object manually
        test_obj = objects_with_attributes[0]
        print(f"\n🧪 TESTING MANUAL MODIFIER APPLICATION ON: {test_obj.name}")

        try:
            # Check if already has modifier
            existing_mod = None
            for mod in test_obj.modifiers:
                if mod.name == "Bonsai 4D Animation":
                    existing_mod = mod
                    break

            if existing_mod:
                print(f"   Object already has GN modifier")
                print(f"   Modifier type: {existing_mod.type}")
                print(f"   Node group: {existing_mod.node_group.name if existing_mod.node_group else 'NONE'}")
            else:
                print(f"   Creating new GN modifier...")

                # Create modifier
                modifier = test_obj.modifiers.new(name="Bonsai 4D Animation", type='NODES')
                modifier.node_group = node_tree

                # Force update
                bpy.context.view_layer.update()

                print(f"✅ Modifier created successfully!")
                print(f"   Modifier keys: {list(modifier.keys())}")

                # Try to add Current Frame driver
                try:
                    driver = modifier.driver_add('["Socket_1"]').driver
                    driver.type = 'SCRIPTED'
                    driver.expression = 'frame'
                    print(f"✅ Current Frame driver added")
                except Exception as driver_e:
                    print(f"❌ Driver failed: {driver_e}")
                    # Try alternative socket names
                    for socket_name in ['["Input_2"]', '["Current Frame"]']:
                        try:
                            driver = modifier.driver_add(socket_name).driver
                            driver.type = 'SCRIPTED'
                            driver.expression = 'frame'
                            print(f"✅ Current Frame driver added via {socket_name}")
                            break
                        except:
                            continue

        except Exception as e:
            print(f"❌ Manual modifier application failed: {e}")

        # Check why apply_gn_modifiers_and_drivers() might be failing
        print(f"\n🔍 CHECKING apply_gn_modifiers_and_drivers() CONDITIONS:")

        # Check the filtering condition in line 710
        objects_to_modify = []
        for obj in context.scene.objects:
            if (obj.type == 'MESH' and
                obj.data and
                obj.data.vertices and
                "schedule_start" in obj.data.attributes):
                objects_to_modify.append(obj)

        print(f"📊 Objects that SHOULD be modified: {len(objects_to_modify)}")

        if len(objects_to_modify) == 0:
            print("❌ Filter condition in apply_gn_modifiers_and_drivers() excludes all objects!")
            print("   Checking each condition:")

            for obj in objects_with_attributes[:3]:  # Check first 3
                print(f"   {obj.name}:")
                print(f"     obj.type == 'MESH': {obj.type == 'MESH'}")
                print(f"     obj.data: {obj.data is not None}")
                print(f"     obj.data.vertices: {obj.data.vertices is not None if obj.data else False}")
                print(f"     schedule_start in attributes: {'schedule_start' in obj.data.attributes if obj.data and hasattr(obj.data, 'attributes') else False}")

        self.report({'INFO'}, "Modifier application debug completed - check console")
        return {'FINISHED'}


class ForceRebakeAttributes(Operator):
    bl_idname = "bim.force_rebake_attributes"
    bl_label = "Force Rebake Attributes"
    bl_description = "Force rebaking of 4D attributes on selected objects"

    def execute(self, context):
        if not context.selected_objects:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        print("🔄 Force rebaking attributes...")

        # Simple test values for debugging
        test_schedule_start = 1.0
        test_schedule_end = 100.0
        test_effect_type = 1  # INSTANT

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            print(f"Processing {obj.name}...")

            # Ensure we're in Edit mode to modify attributes
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')

            # Get bmesh representation
            bm = bmesh.from_mesh(obj.data)

            # Create or get attributes
            if "schedule_start" not in bm.faces.layers.float:
                bm.faces.layers.float.new("schedule_start")
            if "schedule_end" not in bm.faces.layers.float:
                bm.faces.layers.float.new("schedule_end")
            if "effect_type" not in bm.faces.layers.int:
                bm.faces.layers.int.new("effect_type")

            schedule_start_layer = bm.faces.layers.float["schedule_start"]
            schedule_end_layer = bm.faces.layers.float["schedule_end"]
            effect_type_layer = bm.faces.layers.int["effect_type"]

            # Assign test values to all faces
            for face in bm.faces:
                face[schedule_start_layer] = test_schedule_start
                face[schedule_end_layer] = test_schedule_end
                face[effect_type_layer] = test_effect_type

            # Update mesh
            bmesh.update_edit_mesh(obj.data)
            bpy.ops.object.mode_set(mode='OBJECT')

            print(f"✅ Test attributes baked to {obj.name}")

        self.report({'INFO'}, f"Rebaked attributes on {len(context.selected_objects)} objects")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(DebugGNSystem)
    bpy.utils.register_class(TestDriversDebug)
    bpy.utils.register_class(TestGNAnimation)
    bpy.utils.register_class(DebugAttributeValues)
    bpy.utils.register_class(TestSpeedIntegration)
    bpy.utils.register_class(DebugVisibilityLogic)
    bpy.utils.register_class(DebugTaskObjectMapping)
    bpy.utils.register_class(DebugColortypeMapping)
    bpy.utils.register_class(DebugAttributeBaking)
    bpy.utils.register_class(DebugModifierApplication)
    bpy.utils.register_class(ForceRebakeAttributes)


def unregister():
    bpy.utils.unregister_class(DebugGNSystem)
    bpy.utils.unregister_class(TestDriversDebug)
    bpy.utils.unregister_class(TestGNAnimation)
    bpy.utils.unregister_class(DebugAttributeValues)
    bpy.utils.unregister_class(TestSpeedIntegration)
    bpy.utils.unregister_class(DebugVisibilityLogic)
    bpy.utils.unregister_class(DebugTaskObjectMapping)
    bpy.utils.unregister_class(DebugColortypeMapping)
    bpy.utils.unregister_class(DebugAttributeBaking)
    bpy.utils.unregister_class(DebugModifierApplication)
    bpy.utils.unregister_class(ForceRebakeAttributes)


if __name__ == "__main__":
    register()