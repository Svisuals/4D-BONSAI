# Bonsai Sequence Module
# Refactored from monolithic sequence.py for better maintainability

"""
Refactored Sequence module with improved organization.

This module provides a compatibility layer that delegates to specialized
sub-modules while maintaining backward compatibility with existing code.
"""

from .core.date_utils import DateUtils
from .core.color_manager import ColorManager
from .core.camera_manager import CameraManager
from .core.animation_engine import AnimationEngine
from .animation.keyframe_manager import KeyframeManager
from .data.task_manager import TaskManager
from .ui.task_properties import TaskProperties
from .ui.text_display import TextDisplay
from .utils.object_manager import ObjectManager
from .operators.task_operators import TaskOperators

# All functionality is now implemented in specialized modules
# No need to import original sequence.py anymore


class Sequence:
    """
    Compatibility layer for the refactored sequence modules.

    This class delegates method calls to the appropriate specialized modules
    while maintaining full backward compatibility with existing code.
    """

    # Date utilities delegation - handled by DateUtils
    @classmethod
    def parse_isodate_datetime(cls, *args, **kwargs):
        """Parse ISO date/time strings. Delegated to DateUtils."""
        return DateUtils.parse_isodate_datetime(*args, **kwargs)

    @classmethod
    def isodate_datetime(cls, *args, **kwargs):
        """Convert to ISO date/time string. Delegated to DateUtils."""
        return DateUtils.isodate_datetime(*args, **kwargs)

    @classmethod
    def get_start_date(cls, *args, **kwargs):
        """Get visualization start date. Delegated to DateUtils."""
        return DateUtils.get_start_date(*args, **kwargs)

    @classmethod
    def get_finish_date(cls, *args, **kwargs):
        """Get visualization finish date. Delegated to DateUtils."""
        return DateUtils.get_finish_date(*args, **kwargs)

    @classmethod
    def get_visualization_date_range(cls, *args, **kwargs):
        """Get visualization date range. Delegated to DateUtils."""
        return DateUtils.get_visualization_date_range(*args, **kwargs)

    @classmethod
    def update_visualisation_date(cls, *args, **kwargs):
        """Update visualization date. Delegated to DateUtils."""
        return DateUtils.update_visualisation_date(*args, **kwargs)

    @classmethod
    def guess_date_range(cls, *args, **kwargs):
        """Guess date range. Delegated to DateUtils."""
        return DateUtils.guess_date_range(*args, **kwargs)

    @classmethod
    def get_schedule_date_range(cls, *args, **kwargs):
        """Get schedule date range. Delegated to DateUtils."""
        return DateUtils.get_schedule_date_range(*args, **kwargs)

    # Color management delegation - handled by ColorManager
    @classmethod
    def load_ColorType_group_data(cls, *args, **kwargs):
        """Load ColorType group data. Delegated to ColorManager."""
        return ColorManager.load_ColorType_group_data(*args, **kwargs)

    @classmethod
    def get_all_ColorType_groups(cls, *args, **kwargs):
        """Get all ColorType groups. Delegated to ColorManager."""
        return ColorManager.get_all_ColorType_groups(*args, **kwargs)

    @classmethod
    def get_custom_ColorType_groups(cls, *args, **kwargs):
        """Get custom ColorType groups. Delegated to ColorManager."""
        return ColorManager.get_custom_ColorType_groups(*args, **kwargs)

    @classmethod
    def load_ColorType_from_group(cls, *args, **kwargs):
        """Load ColorType from group. Delegated to ColorManager."""
        return ColorManager.load_ColorType_from_group(*args, **kwargs)

    @classmethod
    def get_assigned_ColorType_for_task(cls, *args, **kwargs):
        """Get assigned ColorType for task. Delegated to ColorManager."""
        return ColorManager.get_assigned_ColorType_for_task(*args, **kwargs)

    @classmethod
    def has_animation_colors(cls, *args, **kwargs):
        """Check if has animation colors. Delegated to ColorManager."""
        return ColorManager.has_animation_colors(*args, **kwargs)

    @classmethod
    def load_default_animation_color_scheme(cls, *args, **kwargs):
        """Load default animation color scheme. Delegated to ColorManager."""
        return ColorManager.load_default_animation_color_scheme(*args, **kwargs)

    @classmethod
    def create_default_ColorType_group(cls, *args, **kwargs):
        """Create default ColorType group. Delegated to ColorManager."""
        return ColorManager.create_default_ColorType_group(*args, **kwargs)

    @classmethod
    def force_recreate_default_group(cls, *args, **kwargs):
        """Force recreate default group. Delegated to ColorManager."""
        return ColorManager.force_recreate_default_group(*args, **kwargs)

    @classmethod
    def sync_active_group_to_json(cls, *args, **kwargs):
        """Sync active group to JSON. Delegated to ColorManager."""
        return ColorManager.sync_active_group_to_json(*args, **kwargs)

    @classmethod
    def create_fallback_ColorType(cls, *args, **kwargs):
        """Create fallback ColorType. Delegated to ColorManager."""
        return ColorManager.create_fallback_ColorType(*args, **kwargs)

    @classmethod
    def set_object_shading(cls, *args, **kwargs):
        """Set object shading. Delegated to ColorManager."""
        return ColorManager.set_object_shading(*args, **kwargs)

    @classmethod
    def apply_ColorType_animation(cls, *args, **kwargs):
        """Apply ColorType animation. Delegated to ColorManager."""
        return ColorManager.apply_ColorType_animation(*args, **kwargs)

    @classmethod
    def apply_state_appearance(cls, *args, **kwargs):
        """Apply state appearance. Delegated to ColorManager."""
        return ColorManager.apply_state_appearance(*args, **kwargs)

    @classmethod
    def _apply_ColorType_to_object(cls, obj, frame_data, ColorType, original_color, settings):
        """Apply ColorType animation to object. Delegated to ColorManager."""
        return ColorManager._apply_ColorType_to_object(obj, frame_data, ColorType, original_color, settings)

    @classmethod
    def _create_variance_colortype_group(cls):
        """Create variance ColorType group. Delegated to ColorManager."""
        return ColorManager._create_variance_colortype_group()

    # Task management delegation - handled by TaskManager
    @classmethod
    def get_task_bar_list(cls, *args, **kwargs):
        """Get task bar list. Delegated to TaskManager."""
        return TaskManager.get_task_bar_list(*args, **kwargs)

    @classmethod
    def add_task_bar(cls, *args, **kwargs):
        """Add task bar. Delegated to TaskManager."""
        return TaskManager.add_task_bar(*args, **kwargs)

    @classmethod
    def remove_task_bar(cls, *args, **kwargs):
        """Remove task bar. Delegated to TaskManager."""
        return TaskManager.remove_task_bar(*args, **kwargs)

    @classmethod
    def get_animation_bar_tasks(cls, *args, **kwargs):
        """Get animation bar tasks. Delegated to TaskManager."""
        return TaskManager.get_animation_bar_tasks(*args, **kwargs)

    @classmethod
    def refresh_task_bars(cls, *args, **kwargs):
        """Refresh task bars. Delegated to TaskManager."""
        return TaskManager.refresh_task_bars(*args, **kwargs)

    @classmethod
    def clear_task_bars(cls, *args, **kwargs):
        """Clear task bars. Delegated to TaskManager."""
        return TaskManager.clear_task_bars(*args, **kwargs)

    @classmethod
    def load_task_tree(cls, *args, **kwargs):
        """Load task tree. Delegated to TaskProperties."""
        return TaskProperties.load_task_tree(*args, **kwargs)

    @classmethod
    def get_sorted_tasks_ids(cls, *args, **kwargs):
        """Get sorted task IDs. Delegated to TaskManager."""
        return TaskManager.get_sorted_tasks_ids(*args, **kwargs)

    @classmethod
    def get_filtered_tasks(cls, *args, **kwargs):
        """Get filtered tasks. Delegated to TaskManager."""
        return TaskManager.get_filtered_tasks(*args, **kwargs)

    @classmethod
    def create_new_task_li(cls, *args, **kwargs):
        """Create new task. Delegated to TaskManager."""
        return TaskManager.create_new_task_li(*args, **kwargs)

    @classmethod
    def load_task_properties(cls, *args, **kwargs):
        """Load task properties. Delegated to TaskManager."""
        return TaskManager.load_task_properties(*args, **kwargs)

    @classmethod
    def refresh_task_3d_counts(cls, *args, **kwargs):
        """Refresh task 3D counts. Delegated to TaskManager."""
        return TaskManager.refresh_task_3d_counts(*args, **kwargs)

    @classmethod
    def get_active_work_schedule(cls, *args, **kwargs):
        """Get active work schedule. Delegated to TaskManager."""
        return TaskManager.get_active_work_schedule(*args, **kwargs)

    @classmethod
    def get_checked_tasks(cls, *args, **kwargs):
        """Get checked tasks. Delegated to TaskManager."""
        return TaskManager.get_checked_tasks(*args, **kwargs)

    @classmethod
    def get_active_task(cls, *args, **kwargs):
        """Get active task. Delegated to TaskManager."""
        return TaskManager.get_active_task(*args, **kwargs)

    @classmethod
    def get_highlighted_task(cls, *args, **kwargs):
        """Get highlighted task. Delegated to TaskManager."""
        return TaskManager.get_highlighted_task(*args, **kwargs)

    @classmethod
    def get_task_for_product(cls, *args, **kwargs):
        """Get task for product. Delegated to TaskManager."""
        return TaskManager.get_task_for_product(*args, **kwargs)

    @classmethod
    def get_task_tree_props(cls, *args, **kwargs):
        """Get task tree props. Delegated to TaskManager."""
        return TaskManager.get_task_tree_props(*args, **kwargs)

    @classmethod
    def get_task_attribute_value(cls, *args, **kwargs):
        """Get task attribute value. Delegated to TaskManager."""
        return TaskManager.get_task_attribute_value(*args, **kwargs)

    @classmethod
    def get_task_attributes(cls, *args, **kwargs):
        """Get task attributes. Delegated to TaskManager."""
        return TaskManager.get_task_attributes(*args, **kwargs)

    @classmethod
    def load_task_attributes(cls, *args, **kwargs):
        """Load task attributes. Delegated to TaskManager."""
        return TaskManager.load_task_attributes(*args, **kwargs)

    @classmethod
    def enable_editing_task_attributes(cls, *args, **kwargs):
        """Enable editing task attributes. Delegated to TaskManager."""
        return TaskManager.enable_editing_task_attributes(*args, **kwargs)

    @classmethod
    def disable_editing_task(cls, *args, **kwargs):
        """Disable editing task. Delegated to TaskManager."""
        return TaskManager.disable_editing_task(*args, **kwargs)

    @classmethod
    def get_task_inputs(cls, *args, **kwargs):
        """Get task inputs. Delegated to TaskManager."""
        return TaskManager.get_task_inputs(*args, **kwargs)

    @classmethod
    def get_task_outputs(cls, *args, **kwargs):
        """Get task outputs. Delegated to TaskManager."""
        return TaskManager.get_task_outputs(*args, **kwargs)

    @classmethod
    def get_direct_nested_tasks(cls, *args, **kwargs):
        """Get direct nested tasks. Delegated to TaskManager."""
        return TaskManager.get_direct_nested_tasks(*args, **kwargs)

    @classmethod
    def get_direct_task_outputs(cls, *args, **kwargs):
        """Get direct task outputs. Delegated to TaskManager."""
        return TaskManager.get_direct_task_outputs(*args, **kwargs)

    @classmethod
    def get_work_schedule(cls, *args, **kwargs):
        """Get work schedule. Delegated to TaskManager."""
        return TaskManager.get_work_schedule(*args, **kwargs)

    @classmethod
    def get_work_schedule_props(cls, *args, **kwargs):
        """Get work schedule props. Delegated to TaskManager."""
        return TaskManager.get_work_schedule_props(*args, **kwargs)

    @classmethod
    def get_animation_props(cls, *args, **kwargs):
        """Get animation props. Delegated to TaskManager."""
        return TaskManager.get_animation_props(*args, **kwargs)

    @classmethod
    def get_status_props(cls, *args, **kwargs):
        """Get status props. Delegated to TaskManager."""
        return TaskManager.get_status_props(*args, **kwargs)

    @classmethod
    def get_work_plan_props(cls, *args, **kwargs):
        """Get work plan props. Delegated to TaskManager."""
        return TaskManager.get_work_plan_props(*args, **kwargs)

    @classmethod
    def get_work_calendar_props(cls, *args, **kwargs):
        """Get work calendar props. Delegated to TaskManager."""
        return TaskManager.get_work_calendar_props(*args, **kwargs)

    @classmethod
    def enable_editing_work_schedule_tasks(cls, *args, **kwargs):
        """Enable editing work schedule tasks. Delegated to TaskManager."""
        return TaskManager.enable_editing_work_schedule_tasks(*args, **kwargs)

    # Object management delegation - handled by ObjectManager
    @classmethod
    def validate_task_object(cls, task, operation_name="operation"):
        """Validate task object. Delegated to ObjectManager."""
        return ObjectManager.validate_task_object(task, operation_name)

    @classmethod
    def get_work_schedule_products(cls, work_schedule):
        """Get work schedule products. Delegated to ObjectManager."""
        return ObjectManager.get_work_schedule_products(work_schedule)

    @classmethod
    def select_work_schedule_products(cls, work_schedule):
        """Select work schedule products. Delegated to ObjectManager."""
        return ObjectManager.select_work_schedule_products(work_schedule)

    @classmethod
    def _build_object_task_mapping(cls, all_tasks):
        """Build object-task mapping. Delegated to ObjectManager."""
        return ObjectManager._build_object_task_mapping(all_tasks)

    @classmethod
    def _get_active_schedule_bbox(cls):
        """Get active schedule bounding box. Delegated to ObjectManager."""
        return ObjectManager._get_active_schedule_bbox()

    @classmethod
    def select_products(cls, products):
        """Select products. Delegated to ObjectManager."""
        return ObjectManager.select_products(products)

    # Animation delegation - handled by AnimationEngine
    @classmethod
    def get_animation_product_frames(cls, work_schedule, settings):
        """Get animation product frames. Delegated to AnimationEngine."""
        return AnimationEngine.get_animation_product_frames(work_schedule, settings)

    @classmethod
    def get_animation_product_frames_enhanced(cls, work_schedule, settings):
        """Get enhanced animation product frames. Delegated to AnimationEngine."""
        return AnimationEngine.get_animation_product_frames_enhanced(work_schedule, settings)

    @classmethod
    def animate_objects_with_ColorTypes(cls, settings, product_frames):
        """Animate objects with ColorTypes. Delegated to AnimationEngine."""
        return AnimationEngine.animate_objects_with_ColorTypes(settings, product_frames)

    @classmethod
    def show_snapshot(cls, product_states):
        """Show visual snapshot. Delegated to AnimationEngine."""
        return AnimationEngine.show_snapshot(product_states)

    @classmethod
    def process_construction_state(cls, work_schedule, date, viz_start=None, viz_finish=None, date_source="SCHEDULE"):
        """Process construction state. Delegated to AnimationEngine."""
        return AnimationEngine.process_construction_state(work_schedule, date, viz_start, viz_finish, date_source)

    @classmethod
    def _plan_complete_system_animation(cls, obj, states, ColorType, original_color, frame_data, visibility_ops, color_ops):
        """Plan complete system animation. Delegated to AnimationEngine."""
        return AnimationEngine._plan_complete_system_animation(obj, states, ColorType, original_color, frame_data, visibility_ops, color_ops)

    # UI/Display delegation - handled by TextDisplay
    @classmethod
    def create_bars(cls, tasks):
        """Create visualization bars for tasks. Delegated to TextDisplay."""
        return TextDisplay.create_bars(tasks)

    @classmethod
    def _format_date(cls, *args, **kwargs):
        """Format date for display. Delegated to TextDisplay."""
        return TextDisplay._format_date(*args, **kwargs)

    @classmethod
    def _format_week(cls, *args, **kwargs):
        """Format week number for display. Delegated to TextDisplay."""
        return TextDisplay._format_week(*args, **kwargs)

    @classmethod
    def _format_day_counter(cls, *args, **kwargs):
        """Format day counter for display. Delegated to TextDisplay."""
        return TextDisplay._format_day_counter(*args, **kwargs)

    @classmethod
    def _format_progress(cls, *args, **kwargs):
        """Format progress for display. Delegated to TextDisplay."""
        return TextDisplay._format_progress(*args, **kwargs)

    # Camera management delegation - handled by CameraManager
    @classmethod
    def is_bonsai_camera(cls, *args, **kwargs):
        """Check if Bonsai camera. Delegated to CameraManager."""
        return CameraManager.is_bonsai_camera(*args, **kwargs)

    @classmethod
    def is_bonsai_animation_camera(cls, *args, **kwargs):
        """Check if Bonsai animation camera. Delegated to CameraManager."""
        return CameraManager.is_bonsai_animation_camera(*args, **kwargs)

    @classmethod
    def is_bonsai_snapshot_camera(cls, *args, **kwargs):
        """Check if Bonsai snapshot camera. Delegated to CameraManager."""
        return CameraManager.is_bonsai_snapshot_camera(*args, **kwargs)

    @classmethod
    def add_animation_camera(cls, *args, **kwargs):
        """Add animation camera. Delegated to CameraManager."""
        return CameraManager.add_animation_camera(*args, **kwargs)

    @classmethod
    def add_snapshot_camera(cls, *args, **kwargs):
        """Add snapshot camera. Delegated to CameraManager."""
        return CameraManager.add_snapshot_camera(*args, **kwargs)

    # Additional essential delegations for complete compatibility
    @classmethod
    def apply_selection_from_checkboxes(cls, *args, **kwargs):
        """Apply selection from checkboxes. Delegated to TaskOperators."""
        return TaskOperators.apply_selection_from_checkboxes(*args, **kwargs)

    @classmethod
    def expand_task(cls, *args, **kwargs):
        """Expand task. Delegated to TaskManager."""
        return TaskManager.expand_task(*args, **kwargs)

    @classmethod
    def expand_all_tasks(cls, *args, **kwargs):
        """Expand all tasks. Delegated to TaskManager."""
        return TaskManager.expand_all_tasks(*args, **kwargs)

    @classmethod
    def contract_all_tasks(cls, *args, **kwargs):
        """Contract all tasks. Delegated to TaskManager."""
        return TaskManager.contract_all_tasks(*args, **kwargs)

    @classmethod
    def contract_task(cls, *args, **kwargs):
        """Contract task. Delegated to TaskManager."""
        return TaskManager.contract_task(*args, **kwargs)

    @classmethod
    def go_to_task(cls, task):
        """Go to task. Delegated to TaskManager."""
        return TaskManager.go_to_task(task)

    @classmethod
    def get_task_time(cls, task):
        """Get task time. Delegated to TaskManager."""
        return TaskManager.get_task_time(task)

    @classmethod
    def save_original_colors(cls, *args, **kwargs):
        """Save original colors. Delegated to ObjectManager."""
        return ObjectManager.save_original_colors(*args, **kwargs)

    @classmethod
    def clear_variance_colors_only(cls, *args, **kwargs):
        """Clear variance colors only. Delegated to ColorManager."""
        return ColorManager.clear_variance_colors_only(*args, **kwargs)

    @classmethod
    def activate_variance_color_mode(cls, *args, **kwargs):
        """Activate variance color mode. Delegated to ColorManager."""
        return ColorManager.activate_variance_color_mode(*args, **kwargs)

    @classmethod
    def deactivate_variance_color_mode(cls, *args, **kwargs):
        """Deactivate variance color mode. Delegated to ColorManager."""
        return ColorManager.deactivate_variance_color_mode(*args, **kwargs)

    @classmethod
    def create_tasks_json(cls, work_schedule):
        """Create tasks JSON. Delegated to TaskManager."""
        return TaskManager.create_tasks_json(work_schedule)

    @classmethod
    def create_new_task_json(cls, task, json, type_map=None, baseline_schedule=None):
        """Create new task JSON. Delegated to TaskManager."""
        return TaskManager.create_new_task_json(task, json, type_map, baseline_schedule)

    @classmethod
    def get_tasks_for_product(cls, product, work_schedule=None):
        """Get tasks for product. Delegated to TaskManager."""
        return TaskManager.get_tasks_for_product(product, work_schedule)

    @classmethod
    def are_entities_same_class(cls, entities):
        """Check if entities are same class. Delegated to ObjectManager."""
        return ObjectManager.are_entities_same_class(entities)

    @classmethod
    def copy_work_schedule(cls, work_schedule):
        """Copy work schedule. Delegated to TaskManager."""
        return TaskManager.copy_work_schedule(work_schedule)

    @classmethod
    def export_schedule_configuration(cls, work_schedule):
        """Export schedule configuration. Delegated to TaskManager."""
        return TaskManager.export_schedule_configuration(work_schedule)

    @classmethod
    def import_schedule_configuration(cls, *args, **kwargs):
        """Import schedule configuration. Delegated to TaskManager."""
        return TaskManager.import_schedule_configuration(*args, **kwargs)

    # Additional AnimationEngine delegations
    @classmethod
    def build_animation_plan(cls, *args, **kwargs):
        """Build animation plan. Delegated to AnimationEngine."""
        return AnimationEngine.build_animation_plan(*args, **kwargs)

    @classmethod
    def execute_animation_plan(cls, *args, **kwargs):
        """Execute animation plan. Delegated to AnimationEngine."""
        return AnimationEngine.execute_animation_plan(*args, **kwargs)

    @classmethod
    def calculate_frame_for_date(cls, *args, **kwargs):
        """Calculate frame for date. Delegated to AnimationEngine."""
        return AnimationEngine.calculate_frame_for_date(*args, **kwargs)

    @classmethod
    def get_animation_settings(cls, *args, **kwargs):
        """Get animation settings. Delegated to AnimationEngine."""
        return AnimationEngine.get_animation_settings(*args, **kwargs)

    @classmethod
    def enable_animation_mode(cls, *args, **kwargs):
        """Enable animation mode. Delegated to AnimationEngine."""
        return AnimationEngine.enable_animation_mode(*args, **kwargs)

    @classmethod
    def disable_animation_mode(cls, *args, **kwargs):
        """Disable animation mode. Delegated to AnimationEngine."""
        return AnimationEngine.disable_animation_mode(*args, **kwargs)

    @classmethod
    def get_animation_frame_range(cls, *args, **kwargs):
        """Get animation frame range. Delegated to AnimationEngine."""
        return AnimationEngine.get_animation_frame_range(*args, **kwargs)

    @classmethod
    def set_animation_frame(cls, *args, **kwargs):
        """Set animation frame. Delegated to AnimationEngine."""
        return AnimationEngine.set_animation_frame(*args, **kwargs)

    @classmethod
    def clear_animation_data(cls, *args, **kwargs):
        """Clear animation data. Delegated to AnimationEngine."""
        return AnimationEngine.clear_animation_data(*args, **kwargs)

    @classmethod
    def save_animation_state(cls, *args, **kwargs):
        """Save animation state. Delegated to AnimationEngine."""
        return AnimationEngine.save_animation_state(*args, **kwargs)

    @classmethod
    def restore_animation_state(cls, *args, **kwargs):
        """Restore animation state. Delegated to AnimationEngine."""
        return AnimationEngine.restore_animation_state(*args, **kwargs)

    @classmethod
    def export_animation_data(cls, *args, **kwargs):
        """Export animation data. Delegated to AnimationEngine."""
        return AnimationEngine.export_animation_data(*args, **kwargs)

    @classmethod
    def import_animation_data(cls, *args, **kwargs):
        """Import animation data. Delegated to AnimationEngine."""
        return AnimationEngine.import_animation_data(*args, **kwargs)

    @classmethod
    def validate_animation_setup(cls, *args, **kwargs):
        """Validate animation setup. Delegated to AnimationEngine."""
        return AnimationEngine.validate_animation_setup(*args, **kwargs)

    @classmethod
    def optimize_animation_performance(cls, *args, **kwargs):
        """Optimize animation performance. Delegated to AnimationEngine."""
        return AnimationEngine.optimize_animation_performance(*args, **kwargs)

    @classmethod
    def create_animation_preview(cls, *args, **kwargs):
        """Create animation preview. Delegated to AnimationEngine."""
        return AnimationEngine.create_animation_preview(*args, **kwargs)

    @classmethod
    def render_animation_sequence(cls, *args, **kwargs):
        """Render animation sequence. Delegated to AnimationEngine."""
        return AnimationEngine.render_animation_sequence(*args, **kwargs)

    @classmethod
    def setup_frame_change_handler(cls, *args, **kwargs):
        """Setup frame change handler. Delegated to AnimationEngine."""
        return AnimationEngine.setup_frame_change_handler(*args, **kwargs)

    @classmethod
    def remove_frame_change_handler(cls, *args, **kwargs):
        """Remove frame change handler. Delegated to AnimationEngine."""
        return AnimationEngine.remove_frame_change_handler(*args, **kwargs)

    @classmethod
    def clear_objects_animation(cls, *args, **kwargs):
        """Clear objects animation. Delegated to AnimationEngine."""
        return AnimationEngine.clear_objects_animation(*args, **kwargs)

    @classmethod
    def find_object_by_id(cls, *args, **kwargs):
        """Find object by ID. Delegated to AnimationEngine."""
        return AnimationEngine.find_object_by_id(*args, **kwargs)

    @classmethod
    def count_visible_objects(cls, *args, **kwargs):
        """Count visible objects. Delegated to AnimationEngine."""
        return AnimationEngine.count_visible_objects(*args, **kwargs)

    @classmethod
    def get_sequence_props(cls, *args, **kwargs):
        """Get sequence props. Delegated to AnimationEngine."""
        return AnimationEngine.get_sequence_props(*args, **kwargs)

    # Additional CameraManager delegations
    @classmethod
    def align_animation_camera_to_view(cls, *args, **kwargs):
        """Align animation camera to view. Delegated to CameraManager."""
        return CameraManager.align_animation_camera_to_view(*args, **kwargs)

    @classmethod
    def align_snapshot_camera_to_view(cls, *args, **kwargs):
        """Align snapshot camera to view. Delegated to CameraManager."""
        return CameraManager.align_snapshot_camera_to_view(*args, **kwargs)

    @classmethod
    def animate_camera_movement(cls, *args, **kwargs):
        """Animate camera movement. Delegated to CameraManager."""
        return CameraManager.animate_camera_movement(*args, **kwargs)

    @classmethod
    def create_camera_path(cls, *args, **kwargs):
        """Create camera path. Delegated to CameraManager."""
        return CameraManager.create_camera_path(*args, **kwargs)

    @classmethod
    def create_orbit_animation(cls, *args, **kwargs):
        """Create orbit animation. Delegated to CameraManager."""
        return CameraManager.create_orbit_animation(*args, **kwargs)

    @classmethod
    def get_animation_camera(cls, *args, **kwargs):
        """Get animation camera. Delegated to CameraManager."""
        return CameraManager.get_animation_camera(*args, **kwargs)

    @classmethod
    def get_camera_settings(cls, *args, **kwargs):
        """Get camera settings. Delegated to CameraManager."""
        return CameraManager.get_camera_settings(*args, **kwargs)

    @classmethod
    def set_active_camera(cls, *args, **kwargs):
        """Set active camera. Delegated to CameraManager."""
        return CameraManager.set_active_camera(*args, **kwargs)

    @classmethod
    def remove_animation_camera(cls, *args, **kwargs):
        """Remove animation camera. Delegated to CameraManager."""
        return CameraManager.remove_animation_camera(*args, **kwargs)

    @classmethod
    def save_camera_preset(cls, *args, **kwargs):
        """Save camera preset. Delegated to CameraManager."""
        return CameraManager.save_camera_preset(*args, **kwargs)

    @classmethod
    def load_camera_preset(cls, *args, **kwargs):
        """Load camera preset. Delegated to CameraManager."""
        return CameraManager.load_camera_preset(*args, **kwargs)

    @classmethod
    def validate_camera_settings(cls, *args, **kwargs):
        """Validate camera settings. Delegated to CameraManager."""
        return CameraManager.validate_camera_settings(*args, **kwargs)

    # Additional ColorManager delegations
    @classmethod
    def create_color_material(cls, *args, **kwargs):
        """Create color material. Delegated to ColorManager."""
        return ColorManager.create_color_material(*args, **kwargs)

    @classmethod
    def get_blender_ColorType(cls, *args, **kwargs):
        """Get blender ColorType. Delegated to ColorManager."""
        return ColorManager.get_blender_ColorType(*args, **kwargs)

    @classmethod
    def restore_original_colors(cls, *args, **kwargs):
        """Restore original colors. Delegated to ColorManager."""
        return ColorManager.restore_original_colors(*args, **kwargs)

    @classmethod
    def has_variance_calculation_in_tasks(cls, *args, **kwargs):
        """Check if has variance calculation in tasks. Delegated to ColorManager."""
        return ColorManager.has_variance_calculation_in_tasks(*args, **kwargs)

    # Additional ObjectManager delegations
    @classmethod
    def get_visible_mesh_objects(cls, *args, **kwargs):
        """Get visible mesh objects. Delegated to ObjectManager."""
        return ObjectManager.get_visible_mesh_objects(*args, **kwargs)

    @classmethod
    def get_objects_for_entities(cls, *args, **kwargs):
        """Get objects for entities. Delegated to ObjectManager."""
        return ObjectManager.get_objects_for_entities(*args, **kwargs)

    @classmethod
    def get_ifc_entities_for_objects(cls, *args, **kwargs):
        """Get IFC entities for objects. Delegated to ObjectManager."""
        return ObjectManager.get_ifc_entities_for_objects(*args, **kwargs)

    @classmethod
    def set_objects_visibility(cls, *args, **kwargs):
        """Set objects visibility. Delegated to ObjectManager."""
        return ObjectManager.set_objects_visibility(*args, **kwargs)

    @classmethod
    def clear_text_objects(cls, *args, **kwargs):
        """Clear text objects. Delegated to ObjectManager."""
        return ObjectManager.clear_text_objects(*args, **kwargs)

    # Additional TextDisplay delegations
    @classmethod
    def create_text_objects(cls, *args, **kwargs):
        """Create text objects. Delegated to TextDisplay."""
        return TextDisplay.create_text_objects(*args, **kwargs)

    @classmethod
    def create_animated_text_hud(cls, *args, **kwargs):
        """Create animated text HUD. Delegated to TextDisplay."""
        return TextDisplay.create_animated_text_hud(*args, **kwargs)

    @classmethod
    def animate_text_properties(cls, *args, **kwargs):
        """Animate text properties. Delegated to TextDisplay."""
        return TextDisplay.animate_text_properties(*args, **kwargs)

    @classmethod
    def position_text_objects(cls, *args, **kwargs):
        """Position text objects. Delegated to TextDisplay."""
        return TextDisplay.position_text_objects(*args, **kwargs)

    @classmethod
    def remove_text_objects(cls, *args, **kwargs):
        """Remove text objects. Delegated to TextDisplay."""
        return TextDisplay.remove_text_objects(*args, **kwargs)

    @classmethod
    def update_text_content(cls, *args, **kwargs):
        """Update text content. Delegated to TextDisplay."""
        return TextDisplay.update_text_content(*args, **kwargs)

    # Additional TaskOperators delegations
    @classmethod
    def create_task(cls, *args, **kwargs):
        """Create task. Delegated to TaskOperators."""
        return TaskOperators.create_task(*args, **kwargs)

    @classmethod
    def delete_task(cls, *args, **kwargs):
        """Delete task. Delegated to TaskOperators."""
        return TaskOperators.delete_task(*args, **kwargs)

    @classmethod
    def edit_task(cls, *args, **kwargs):
        """Edit task. Delegated to TaskOperators."""
        return TaskOperators.edit_task(*args, **kwargs)

    @classmethod
    def add_task_column(cls, *args, **kwargs):
        """Add task column. Delegated to TaskOperators."""
        return TaskOperators.add_task_column(*args, **kwargs)

    @classmethod
    def remove_task_column(cls, *args, **kwargs):
        """Remove task column. Delegated to TaskOperators."""
        return TaskOperators.remove_task_column(*args, **kwargs)

    @classmethod
    def set_task_sort_column(cls, *args, **kwargs):
        """Set task sort column. Delegated to TaskOperators."""
        return TaskOperators.set_task_sort_column(*args, **kwargs)

    @classmethod
    def find_related_input_tasks(cls, *args, **kwargs):
        """Find related input tasks. Delegated to TaskOperators."""
        return TaskOperators.find_related_input_tasks(*args, **kwargs)

    @classmethod
    def find_related_output_tasks(cls, *args, **kwargs):
        """Find related output tasks. Delegated to TaskOperators."""
        return TaskOperators.find_related_output_tasks(*args, **kwargs)

    # Additional KeyframeManager delegations
    @classmethod
    def apply_visibility_animation(cls, *args, **kwargs):
        """Apply visibility animation. Delegated to KeyframeManager."""
        return KeyframeManager.apply_visibility_animation(*args, **kwargs)

    @classmethod
    def debug_ColorType_application(cls, *args, **kwargs):
        """Debug ColorType application. Delegated to KeyframeManager."""
        return KeyframeManager.debug_ColorType_application(*args, **kwargs)

    # Additional missing method delegations
    @classmethod
    def snapshot_all_ui_state(cls, *args, **kwargs):
        """Snapshot all UI state. Delegated to ObjectManager."""
        return ObjectManager.snapshot_all_ui_state(*args, **kwargs)

    @classmethod
    def restore_all_ui_state(cls, *args, **kwargs):
        """Restore all UI state. Delegated to ObjectManager."""
        return ObjectManager.restore_all_ui_state(*args, **kwargs)

    @classmethod
    def are_entities_same_class(cls, *args, **kwargs):
        """Check if entities are same class. Delegated to ObjectManager."""
        return ObjectManager.are_entities_same_class(*args, **kwargs)

    @classmethod
    def select_products(cls, *args, **kwargs):
        """Select products. Delegated to ObjectManager."""
        return ObjectManager.select_products(*args, **kwargs)

    @classmethod
    def select_unassigned_work_schedule_products(cls, *args, **kwargs):
        """Select unassigned work schedule products. Delegated to ObjectManager."""
        return ObjectManager.select_unassigned_work_schedule_products(*args, **kwargs)

    @classmethod
    def setup_default_task_columns(cls, *args, **kwargs):
        """Setup default task columns. Delegated to TaskOperators."""
        return TaskOperators.setup_default_task_columns(*args, **kwargs)

    @classmethod
    def add_task_column(cls, *args, **kwargs):
        """Add task column. Delegated to TaskOperators."""
        return TaskOperators.add_task_column(*args, **kwargs)

    @classmethod
    def remove_task_column(cls, *args, **kwargs):
        """Remove task column. Delegated to TaskOperators."""
        return TaskOperators.remove_task_column(*args, **kwargs)

    @classmethod
    def set_task_sort_column(cls, *args, **kwargs):
        """Set task sort column. Delegated to TaskOperators."""
        return TaskOperators.set_task_sort_column(*args, **kwargs)

    @classmethod
    def find_related_input_tasks(cls, *args, **kwargs):
        """Find related input tasks. Delegated to TaskOperators."""
        return TaskOperators.find_related_input_tasks(*args, **kwargs)

    @classmethod
    def find_related_output_tasks(cls, *args, **kwargs):
        """Find related output tasks. Delegated to TaskOperators."""
        return TaskOperators.find_related_output_tasks(*args, **kwargs)

    # Additional text/animation methods
    @classmethod
    def add_text_animation_handler(cls, *args, **kwargs):
        """Add text animation handler. Delegated to TextDisplay."""
        return TextDisplay.add_text_animation_handler(*args, **kwargs)

    @classmethod
    def create_text_objects_static(cls, *args, **kwargs):
        """Create text objects static. Delegated to TextDisplay."""
        return TextDisplay.create_text_objects_static(*args, **kwargs)

    # Animation engine methods
    @classmethod
    def animate_objects_with_ColorTypes_new(cls, *args, **kwargs):
        """Animate objects with ColorTypes (new). Delegated to AnimationEngine."""
        return AnimationEngine.animate_objects_with_ColorTypes_new(*args, **kwargs)

    @classmethod
    def get_animation_product_frames_enhanced(cls, *args, **kwargs):
        """Get animation product frames enhanced. Delegated to AnimationEngine."""
        return AnimationEngine.get_animation_product_frames_enhanced(*args, **kwargs)

    @classmethod
    def clear_objects_animation(cls, *args, **kwargs):
        """Clear objects animation. Delegated to AnimationEngine."""
        return AnimationEngine.clear_objects_animation(*args, **kwargs)

    @classmethod
    def has_variance_calculation_in_tasks(cls, *args, **kwargs):
        """Check if has variance calculation in tasks. Delegated to ColorManager."""
        return ColorManager.has_variance_calculation_in_tasks(*args, **kwargs)

    @classmethod
    def update_individual_variance_colors(cls, *args, **kwargs):
        """Update individual variance colors. Delegated to ColorManager."""
        return ColorManager.update_individual_variance_colors(*args, **kwargs)

    @classmethod
    def clear_variance_color_mode(cls, *args, **kwargs):
        """Clear variance color mode. Delegated to ColorManager."""
        return ColorManager.clear_variance_color_mode(*args, **kwargs)

    # Essential methods that need to exist for compatibility but can be minimal
    def __getattr__(self, name):
        """Handle missing methods - all should be delegated to specialized modules."""
        raise AttributeError(f"Method '{name}' not found. All methods should be delegated to specialized modules (DateUtils, ColorManager, etc.). Check if this method needs to be added to the appropriate module.")