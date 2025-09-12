import bpy
import json
import calendar
from mathutils import Matrix
from datetime import datetime
from dateutil import relativedelta
import bonsai.tool as tool
import bonsai.core.sequence as core

try:
    from ..prop.task import safe_set_selected_colortype_in_active_group
    # ... otras importaciones de ..prop
except (ImportError, ValueError):
    # Fallback si la estructura cambia
    try:
        from ..prop.animation import safe_set_selected_colortype_in_active_group
    except ImportError:
        # Ultimate fallback
        def safe_set_selected_colortype_in_active_group(task_obj, value, skip_validation=False):
            try:
                setattr(task_obj, "selected_colortype_in_active_group", value)
            except Exception:
                pass

try:
    from ..prop import update_filter_column
    from .. import prop
    from .ui import calculate_visible_columns_count
except Exception:
    try:
        from ..prop.filter import update_filter_column
        from .. import prop as prop
        from ..ui import calculate_visible_columns_count
    except Exception:
        def update_filter_column(*args, **kwargs):
            pass
        def calculate_visible_columns_count(context):
            return 3  # Safe fallback
        # Fallback for safe assignment function
        class PropFallback:
            @staticmethod
            def safe_set_selected_colortype_in_active_group(task_obj, value, skip_validation=False):
                try:
                    setattr(task_obj, "selected_colortype_in_active_group", value)
                except Exception as e:
                    print(f"❌ Fallback safe_set failed: {e}")
        prop = PropFallback()


def snapshot_all_ui_state(context):
    """Simple v60-style snapshot - just save ColorTypes"""
    from .simple_colortype_persistence import save_colortypes_simple
    save_colortypes_simple()


def restore_all_ui_state(context):
    """Simple v60-style restore - just restore ColorTypes"""
    from .simple_colortype_persistence import restore_colortypes_simple
    restore_colortypes_simple()


def _save_3d_texts_state():
    """Save current state of all 3D text objects before snapshot"""
    try:
        coll = bpy.data.collections.get("Schedule_Display_Texts")
        if not coll:
            return
        
        state_data = {}
        for obj in coll.objects:
            if hasattr(obj, "data") and obj.data:
                state_data[obj.name] = obj.data.body
        
        # Store in scene for restoration
        bpy.context.scene["3d_texts_previous_state"] = json.dumps(state_data)
        print(f"💾 Saved state for {len(state_data)} 3D text objects")
        
    except Exception as e:
        print(f"❌ Error saving 3D texts state: {e}")

def _restore_3d_texts_state():
    """Restore previous state of all 3D text objects after snapshot reset"""
    try:
        if "3d_texts_previous_state" not in bpy.context.scene:
            print("⚠️ No previous 3D texts state found to restore")
            return
        
        coll = bpy.data.collections.get("Schedule_Display_Texts")
        if not coll:
            print("⚠️ No 'Schedule_Display_Texts' collection found for restoration")
            return
        
        state_data = json.loads(bpy.context.scene["3d_texts_previous_state"])
        restored_count = 0
        
        for obj in coll.objects:
            if hasattr(obj, "data") and obj.data and obj.name in state_data:
                obj.data.body = state_data[obj.name]
                restored_count += 1
        
        # Clean up saved state
        del bpy.context.scene["3d_texts_previous_state"]
        print(f"🔄 Restored state for {restored_count} 3D text objects")
        
    except Exception as e:
        print(f"❌ Error restoring 3D texts state: {e}")


class LoadTaskProperties(bpy.types.Operator):
    bl_idname = "bim.load_task_properties"
    bl_label = "Load Task Properties"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.load_task_properties(tool.Sequence)
        return {"FINISHED"}


class AddTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_task"
    bl_label = "Add Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)

        core.add_task(tool.Ifc, tool.Sequence, parent_task=tool.Ifc.get().by_id(self.task))

        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties(task=None)
        except Exception:
            pass

        restore_all_ui_state(context)


class AddSummaryTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.add_summary_task"
    bl_label = "Add Task"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)

        core.add_summary_task(tool.Ifc, tool.Sequence, work_schedule=tool.Ifc.get().by_id(self.work_schedule))

        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties(task=None)
        except Exception:
            pass

        restore_all_ui_state(context)


class ExpandTask(bpy.types.Operator):
    bl_idname = "bim.expand_task"
    bl_label = "Expand Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        snapshot_all_ui_state(context)

        core.expand_task(tool.Sequence, task=tool.Ifc.get().by_id(self.task))

        return {'FINISHED'}


class ContractTask(bpy.types.Operator):
    bl_idname = "bim.contract_task"
    bl_label = "Contract Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        snapshot_all_ui_state(context)

        core.contract_task(tool.Sequence, task=tool.Ifc.get().by_id(self.task))

        return {'FINISHED'}


class RemoveTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.remove_task"
    bl_label = "Remove Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)

        core.remove_task(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))

        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties(task=None)
        except Exception:
            pass

        restore_all_ui_state(context)


class EnableEditingTask(bpy.types.Operator):
    bl_idname = "bim.enable_editing_task_attributes"
    bl_label = "Enable Editing Task Attributes"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        core.enable_editing_task_attributes(tool.Sequence, task=tool.Ifc.get().by_id(self.task))
        return {"FINISHED"}


class DisableEditingTask(bpy.types.Operator):
    bl_idname = "bim.disable_editing_task"
    bl_label = "Disable Editing Task"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        snapshot_all_ui_state(context)
        core.disable_editing_task(tool.Sequence)
        return {"FINISHED"}


class EditTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.edit_task"
    bl_label = "Edit Task"
    bl_options = {"REGISTER", "UNDO"}

    def _execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        core.edit_task(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(props.active_task_id))


class CopyTaskAttribute(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.copy_task_attribute"
    bl_label = "Copy Task Attribute"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def _execute(self, context):
        core.copy_task_attribute(tool.Ifc, tool.Sequence, attribute_name=self.name)


class CalculateTaskDuration(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.calculate_task_duration"
    bl_label = "Calculate Task Duration"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)
        core.calculate_task_duration(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))
        restore_all_ui_state(context)


class ExpandAllTasks(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.expand_all_tasks"
    bl_label = "Expands All Tasks"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Finds the related Task"
    product_type: bpy.props.StringProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)
        core.expand_all_tasks(tool.Sequence)
        restore_all_ui_state(context)


class ContractAllTasks(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.contract_all_tasks"
    bl_label = "Expands All Tasks"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Finds the related Task"
    product_type: bpy.props.StringProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)
        core.contract_all_tasks(tool.Sequence)
        restore_all_ui_state(context)


class CopyTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.duplicate_task"
    bl_label = "Copy Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)

        core.duplicate_task(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))

        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties(task=None)
        except Exception:
            pass

        restore_all_ui_state(context)


class GoToTask(bpy.types.Operator):
    bl_idname = "bim.go_to_task"
    bl_label = "Highlight Task"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def execute(self, context):
        try:
            task_entity = tool.Ifc.get().by_id(self.task)
            r = core.go_to_task(tool.Sequence, task=task_entity)
            if isinstance(r, str):
                self.report({"WARNING"}, r)
        except Exception as e:
            self.report({"ERROR"}, f"Error: {e}")
        return {"FINISHED"}


class ReorderTask(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.reorder_task_nesting"
    bl_label = "Reorder Nesting"
    bl_options = {"REGISTER", "UNDO"}
    new_index: bpy.props.IntProperty()
    task: bpy.props.IntProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)

        r = core.reorder_task_nesting(
            tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task), new_index=self.new_index
        )

        if isinstance(r, str):
            self.report({"WARNING"}, r)

        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties(task=None)
        except Exception:
            pass

        restore_all_ui_state(context)