import bpy
import json
import calendar
from mathutils import Matrix
from datetime import datetime
from dateutil import relativedelta
from typing import get_args, TYPE_CHECKING, assert_never
import bonsai.tool as tool
import bonsai.core.sequence as core

try:
    from .prop import update_filter_column
    from . import prop
    from .ui import calculate_visible_columns_count
    from .schedule_task_operators import snapshot_all_ui_state, restore_all_ui_state
except Exception:
    try:
        from bonsai.bim.module.sequence.prop import update_filter_column
        import bonsai.bim.module.sequence.prop as prop
        from bonsai.bim.module.sequence.ui import calculate_visible_columns_count
        from bonsai.bim.module.sequence.schedule_task_operators import snapshot_all_ui_state, restore_all_ui_state
    except Exception:
        def update_filter_column(*args, **kwargs):
            pass
        def calculate_visible_columns_count(context):
            return 3  # Safe fallback
        # Fallback for safe assignment function
        class PropFallback:
            @staticmethod
            def safe_set_selected_colortype_in_active_group(task_obj, value):
                try:
                    setattr(task_obj, "selected_colortype_in_active_group", value)
                except Exception as e:
                    print(f"❌ Fallback safe_set failed: {e}")
        prop = PropFallback()
        
        def snapshot_all_ui_state(context):
            pass
        def restore_all_ui_state(context):
            pass


def _related_object_type_items(self, context):
    try:
        from typing import get_args
        from bonsai import tool as _tool
        vals = list(get_args(getattr(_tool.Sequence, "RELATED_OBJECT_TYPE", tuple()))) or []
    except Exception:
        vals = []
    if not vals:
        # Safe fallback
        vals = ("PRODUCT", "RESOURCE", "PROCESS")
    return [(str(v), str(v).replace("_", " ").title(), "") for v in vals]


# ============================================================================
# ASSIGNMENT OPERATORS
# ============================================================================

class AssignPredecessor(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_predecessor"
    bl_label = "Assign Predecessor"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.assign_predecessor(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))


class AssignSuccessor(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_successor"
    bl_label = "Assign Successor"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.assign_successor(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))


class UnassignPredecessor(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_predecessor"
    bl_label = "Unassign Predecessor"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.unassign_predecessor(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))


class UnassignSuccessor(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_successor"
    bl_label = "Unassign Successor"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.unassign_successor(tool.Ifc, tool.Sequence, task=tool.Ifc.get().by_id(self.task))


class AssignProduct(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_product"
    bl_label = "Assign Product"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()
    relating_product: bpy.props.IntProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)
        try:
            if self.relating_product:
                core.assign_products(
                    tool.Ifc,
                    tool.Sequence,
                    tool.Spatial,
                    task=tool.Ifc.get().by_id(self.task),
                    products=[tool.Ifc.get().by_id(self.relating_product)],
                )
            else:
                core.assign_products(tool.Ifc, tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task))
            tool.Sequence.load_task_properties()
        finally:
            restore_all_ui_state(context)


class UnassignProduct(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_product"
    bl_label = "Unassign Product"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()
    relating_product: bpy.props.IntProperty()

    def _execute(self, context):
        snapshot_all_ui_state(context)
        try:
            if self.relating_product:
                core.unassign_products(
                    tool.Ifc,
                    tool.Sequence,
                    tool.Spatial,
                    task=tool.Ifc.get().by_id(self.task),
                    products=[tool.Ifc.get().by_id(self.relating_product)],
                )
            else:
                core.unassign_products(tool.Ifc, tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task))
            tool.Sequence.load_task_properties()
            task_ifc = tool.Ifc.get().by_id(self.task)
            tool.Sequence.update_task_ICOM(task_ifc)
        finally:
            restore_all_ui_state(context)


class AssignProcess(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_process"
    bl_label = "Assign Process"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()
    related_object_type: bpy.props.EnumProperty(  # pyright: ignore [reportRedeclaration]
        items=_related_object_type_items,
    )
    related_object: bpy.props.IntProperty()

    if TYPE_CHECKING:
        related_object_type: tool.Sequence.RELATED_OBJECT_TYPE

    @classmethod
    def description(cls, context, properties):
        return f"Assign selected {properties.related_object_type} to the selected task"

    def _execute(self, context):
        snapshot_all_ui_state(context)
        try:
            if self.related_object_type == "RESOURCE":
                core.assign_resource(tool.Ifc, tool.Sequence, tool.Resource, task=tool.Ifc.get().by_id(self.task))
            elif self.related_object_type == "PRODUCT":
                if self.related_object:
                    core.assign_input_products(
                        tool.Ifc,
                        tool.Sequence,
                        tool.Spatial,
                        task=tool.Ifc.get().by_id(self.task),
                        products=[tool.Ifc.get().by_id(self.related_object)],
                    )
                else:
                    core.assign_input_products(tool.Ifc, tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task))
            elif self.related_object_type == "CONTROL":
                self.report({"ERROR"}, "Assigning process control is not yet supported")  # TODO
            else:
                assert_never(self.related_object_type)
            task_ifc = tool.Ifc.get().by_id(self.task)
            tool.Sequence.update_task_ICOM(task_ifc)
        finally:
            restore_all_ui_state(context)


class UnassignProcess(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_process"
    bl_label = "Unassign Process"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()
    related_object_type: bpy.props.EnumProperty(  # pyright: ignore [reportRedeclaration]
        items=_related_object_type_items,
    )
    related_object: bpy.props.IntProperty()
    resource: bpy.props.IntProperty()

    if TYPE_CHECKING:
        related_object_type: tool.Sequence.RELATED_OBJECT_TYPE

    @classmethod
    def description(cls, context, properties):
        return f"Unassign selected {properties.related_object_type} from the selected task"

    def _execute(self, context):
        snapshot_all_ui_state(context)
        try:
            if self.related_object_type == "RESOURCE":
                core.unassign_resource(
                    tool.Ifc,
                    tool.Sequence,
                    tool.Resource,
                    task=tool.Ifc.get().by_id(self.task),
                    resource=tool.Ifc.get().by_id(self.resource),
                )

            elif self.related_object_type == "PRODUCT":
                if self.related_object:
                    core.unassign_input_products(
                        tool.Ifc,
                        tool.Sequence,
                        tool.Spatial,
                        task=tool.Ifc.get().by_id(self.task),
                        products=[tool.Ifc.get().by_id(self.related_object)],
                    )
                else:
                    core.unassign_input_products(
                        tool.Ifc, tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task)
                    )
            elif self.related_object_type == "CONTROL":
                pass  # TODO
                self.report({"INFO"}, "Unassigning process control is not yet supported.")
            else:
                assert_never(self.related_object_type)
            task_ifc = tool.Ifc.get().by_id(self.task)
            tool.Sequence.update_task_ICOM(task_ifc)
        finally:
            restore_all_ui_state(context)
        return {"FINISHED"}


class AssignRecurrencePattern(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_recurrence_pattern"
    bl_label = "Assign Recurrence Pattern"
    bl_options = {"REGISTER", "UNDO"}
    work_time: bpy.props.IntProperty()
    recurrence_type: bpy.props.StringProperty()

    def _execute(self, context):
        core.assign_recurrence_pattern(
            tool.Ifc, work_time=tool.Ifc.get().by_id(self.work_time), recurrence_type=self.recurrence_type
        )
        return {"FINISHED"}


class UnassignRecurrencePattern(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_recurrence_pattern"
    bl_label = "Unassign Recurrence Pattern"
    bl_options = {"REGISTER", "UNDO"}
    recurrence_pattern: bpy.props.IntProperty()

    def _execute(self, context):
        core.unassign_recurrence_pattern(tool.Ifc, recurrence_pattern=tool.Ifc.get().by_id(self.recurrence_pattern))
        return {"FINISHED"}


class AssignLagTime(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.assign_lag_time"
    bl_label = "Assign Time Lag"
    bl_options = {"REGISTER", "UNDO"}
    sequence: bpy.props.IntProperty()

    def _execute(self, context):
        core.assign_lag_time(tool.Ifc, rel_sequence=tool.Ifc.get().by_id(self.sequence))


class UnassignLagTime(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.unassign_lag_time"
    bl_label = "Unassign Time Lag"
    bl_options = {"REGISTER", "UNDO"}
    sequence: bpy.props.IntProperty()

    def _execute(self, context):
        core.unassign_lag_time(tool.Ifc, tool.Sequence, rel_sequence=tool.Ifc.get().by_id(self.sequence))


# ============================================================================
# SELECTION OPERATORS
# ============================================================================

class SelectTaskRelatedProducts(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.select_task_related_products"
    bl_label = "Select All Output Products"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.select_task_outputs(tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task))


class SelectTaskRelatedInputs(bpy.types.Operator, tool.Ifc.Operator):
    bl_idname = "bim.select_task_related_inputs"
    bl_label = "Select All Input Products"
    bl_options = {"REGISTER", "UNDO"}
    task: bpy.props.IntProperty()

    def _execute(self, context):
        core.select_task_inputs(tool.Sequence, tool.Spatial, task=tool.Ifc.get().by_id(self.task))


class LoadProductTasks(bpy.types.Operator):
    bl_idname = "bim.load_product_related_tasks"
    bl_label = "Load Product Tasks"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not tool.Ifc.get() or not (obj := context.active_object) or not (tool.Blender.get_ifc_definition_id(obj)):
            cls.poll_message_set("No IFC object is active.")
            return False
        return True

    def execute(self, context):
        try:
            obj = context.active_object
            if not obj:
                self.report({"ERROR"}, "No active object selected")
                return {"CANCELLED"}

            product = tool.Ifc.get_entity(obj)
            if not product:
                self.report({"ERROR"}, "Active object is not an IFC entity")
                return {"CANCELLED"}

            # Llamar al método corregido
            result = tool.Sequence.load_product_related_tasks(product)

            if isinstance(result, str):
                if "Error" in result:
                    self.report({"ERROR"}, result)
                    return {"CANCELLED"}
                else:
                    self.report({"INFO"}, result)
            else:
                self.report({"INFO"}, f"{len(result)} product tasks loaded.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Failed to load product tasks: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"CANCELLED"}

