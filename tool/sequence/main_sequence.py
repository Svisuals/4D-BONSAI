# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>
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



from __future__ import annotations
import bpy
import ifcopenshell
import ifcopenshell.api
import bonsai.core.tool
import bonsai.bim.helper
from typing import Any, Union, Literal, TYPE_CHECKING

# Imports de los nuevos módulos refactorizados
from . import props_sequence
from . import task_sequence
from . import utils_sequence
from . import camera_sequence
from . import visuals_sequence
from . import colortype_sequence
from . import animation_sequence
from . import variance_sequence
from . import config_sequence

if TYPE_CHECKING:
    from bonsai.bim.prop import Attribute

class Sequence(bonsai.core.tool.Sequence):

    # ==================================================================
    # MÉTODOS QUE PERMANECEN EN LA CLASE PRINCIPAL
    # (Principalmente lógica de atributos de IFC)
    # ==================================================================

    @classmethod
    def get_work_plan_attributes(cls) -> dict[str, Any]:
        import bonsai.bim.module.sequence.helper as helper
        def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
            if "Date" in prop.name or "Time" in prop.name:
                attributes[prop.name] = None if prop.is_null else helper.parse_datetime(prop.string_value)
                return True
            elif prop.name == "Duration" or prop.name == "TotalFloat":
                attributes[prop.name] = None if prop.is_null else helper.parse_duration(prop.string_value)
                return True
            return False
        props = props_sequence.get_work_plan_props()
        return bonsai.bim.helper.export_attributes(props.work_plan_attributes, callback)

    @classmethod
    def load_work_plan_attributes(cls, work_plan: ifcopenshell.entity_instance) -> None:
        def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
            if name in ["CreationDate", "StartTime", "FinishTime"]:
                assert prop
                prop.string_value = "" if prop.is_null else data[name]
                return True
        props = props_sequence.get_work_plan_props()
        props.work_plan_attributes.clear()
        bonsai.bim.helper.import_attributes(work_plan, props.work_plan_attributes, callback)

    @classmethod
    def get_work_schedule_attributes(cls) -> dict[str, Any]:
        import bonsai.bim.module.sequence.helper as helper
        def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
            if "Date" in prop.name or "Time" in prop.name:
                attributes[prop.name] = None if prop.is_null else helper.parse_datetime(prop.string_value)
                return True
            elif prop.name == "Duration" or prop.name == "TotalFloat":
                attributes[prop.name] = None if prop.is_null else helper.parse_duration(prop.string_value)
                return True
            return False
        props = props_sequence.get_work_schedule_props()
        return bonsai.bim.helper.export_attributes(props.work_schedule_attributes, callback)

    @classmethod
    def load_work_schedule_attributes(cls, work_schedule: ifcopenshell.entity_instance) -> None:
        def callback(name: str, prop: Union[Attribute, None], data: dict[str, Any]) -> None | Literal[True]:
            if name in ["CreationDate", "StartTime", "FinishTime"]:
                assert prop
                prop.string_value = "" if prop.is_null else data[name]
                return True
        props = props_sequence.get_work_schedule_props()
        props.work_schedule_attributes.clear()
        bonsai.bim.helper.import_attributes(work_schedule, props.work_schedule_attributes, callback)
    
    # ... (Aquí irían otros métodos de atributos como get_work_schedule_attributes, load_task_attributes, etc.
    # que son pequeños y muy ligados a la manipulación directa de props de Blender. Para mantener la brevedad,
    # los omito, pero seguirían el mismo patrón que los de arriba)

    # ==================================================================
    # ENVOLTORIOS (WRAPPERS) PARA LAS FUNCIONES REFACTORIZADAS
    # ==================================================================

    # --- Propiedades ---
    @classmethod
    def get_work_schedule_props(cls):
        return props_sequence.get_work_schedule_props()
    
    @classmethod
    def get_work_plan_props(cls):
        return props_sequence.get_work_plan_props()
    
    @classmethod
    def get_animation_props(cls):
        return props_sequence.get_animation_props()
    
    @classmethod
    def get_task_tree_props(cls):
        return props_sequence.get_task_tree_props()
    
    @classmethod
    def get_status_props(cls):
        return props_sequence.get_status_props()
    
    @classmethod
    def get_work_calendar_props(cls):
        return props_sequence.get_work_calendar_props()

    # --- Cámaras ---
    @classmethod
    def add_animation_camera(cls):
        return camera_sequence.add_animation_camera()

    @classmethod
    def add_snapshot_camera(cls):
        return camera_sequence.add_snapshot_camera()

    @classmethod
    def align_animation_camera_to_view(cls):
        return camera_sequence.align_animation_camera_to_view()
    
    @classmethod
    def align_snapshot_camera_to_view(cls):
        return camera_sequence.align_snapshot_camera_to_view()
    
    @classmethod
    def update_animation_camera(cls, cam_obj):
        return camera_sequence.update_animation_camera(cam_obj)

    # --- Tareas ---
        
    @classmethod
    def load_task_properties(cls):
        task_sequence.load_task_properties()

    @classmethod
    def update_task_ICOM(cls, task: ifcopenshell.entity_instance):
        task_sequence.update_task_ICOM(task)

    # --- Animación ---
    @classmethod
    def get_animation_settings(cls):
        return animation_sequence.get_animation_settings()
    
    @classmethod
    def get_animation_product_frames_enhanced(cls, work_schedule, settings):
        return animation_sequence.get_animation_product_frames_enhanced(work_schedule, settings)

    @classmethod
    def animate_objects_with_ColorTypes(cls, settings, product_frames):
        animation_sequence.animate_objects_with_ColorTypes(settings, product_frames)
    
    @classmethod
    def get_animation_bar_tasks(cls):
        return visuals_sequence.get_animation_bar_tasks()

    # --- Visuals ---
    @classmethod
    def create_bars(cls, tasks):
        visuals_sequence.create_bars(tasks)

    @classmethod
    def add_text_animation_handler(cls, settings):
        return visuals_sequence.add_text_animation_handler(settings)

    # --- Varianza ---

    # --- Utils ---
    @classmethod
    def get_work_schedule_products(cls, work_schedule):
        return utils_sequence.get_work_schedule_products(work_schedule)
    
    @classmethod
    def select_work_schedule_products(cls, work_schedule):
        return utils_sequence.select_work_schedule_products(work_schedule)
    
    @classmethod
    def select_unassigned_work_schedule_products(cls):
        return utils_sequence.select_unassigned_work_schedule_products()
    
    @classmethod
    def parse_isodate_datetime(cls, value, include_time: bool = True):
        return utils_sequence.parse_isodate_datetime(value, include_time)
    
    @classmethod
    def isodate_datetime(cls, value, include_time: bool = True):
        return utils_sequence.isodate_datetime(value, include_time)
    
    @classmethod
    def guess_date_range(cls, work_schedule):
        return animation_sequence.guess_date_range(work_schedule)

    # --- Configuración ---
    @classmethod
    def copy_3d_configuration(cls, source_schedule):
        return config_sequence.copy_3d_configuration(source_schedule)

    @classmethod
    def sync_3d_elements(cls, work_schedule, property_set_name):
        return config_sequence.sync_3d_elements(work_schedule, property_set_name)

    # --- Methods that need to be implemented ---
    @classmethod
    def get_start_date(cls):
        return animation_sequence.get_start_date()
    
    @classmethod
    def get_finish_date(cls):
        return animation_sequence.get_finish_date()
    
    @classmethod
    def get_active_work_schedule(cls):
        return task_sequence.get_active_work_schedule()
    
    @classmethod
    def get_schedule_date_range(cls, work_schedule=None):
        return utils_sequence.get_schedule_date_range(work_schedule)
    
    @classmethod
    def get_highlighted_task(cls):
        return task_sequence.get_highlighted_task()
    
    @classmethod
    def create_tasks_json(cls, work_schedule=None):
        return utils_sequence.create_tasks_json(work_schedule)
    
    @classmethod
    def get_tasks_for_product(cls, product, work_schedule=None):
        return utils_sequence.get_tasks_for_product(product, work_schedule)
    
    # --- More critical methods ---
    @classmethod
    def get_task_bar_list(cls):
        return visuals_sequence.get_task_bar_list()
    
    @classmethod
    def has_duration(cls, task):
        return task_sequence.has_duration(task)
    
    @classmethod
    def get_task_time(cls, task):
        return task_sequence.get_task_time(task)
    
    @classmethod
    def get_task_time_attributes(cls):
        return task_sequence.get_task_time_attributes()
    
    @classmethod
    def load_task_time_attributes(cls, task_time):
        return task_sequence.load_task_time_attributes(task_time)
    
    @classmethod
    def refresh_task_resources(cls):
        task_sequence.refresh_task_resources()
    
    @classmethod
    def apply_selection_from_checkboxes(cls):
        task_sequence.apply_selection_from_checkboxes()
    
    
    @classmethod
    def get_task_outputs(cls, task):
        return task_sequence.get_task_outputs(task)
    
    @classmethod
    def get_task_attributes(cls):
        return task_sequence.get_task_attributes()
    
    @classmethod
    def load_task_attributes(cls, task):
        return task_sequence.load_task_attributes(task)
    
    @classmethod
    def get_active_task(cls):
        return task_sequence.get_active_task()
    
    @classmethod
    def get_task_attribute_value(cls, attribute_name):
        return task_sequence.get_task_attribute_value(attribute_name)
    
    @classmethod
    def get_work_calendar_attributes(cls):
        return utils_sequence.get_work_calendar_attributes()
    
    @classmethod
    def load_work_calendar_attributes(cls, work_calendar):
        return utils_sequence.load_work_calendar_attributes(work_calendar)
    
    @classmethod
    def get_active_work_time(cls):
        return utils_sequence.get_active_work_time()
    
    @classmethod
    def get_work_time_attributes(cls):
        return utils_sequence.get_work_time_attributes()
    
    @classmethod
    def load_work_time_attributes(cls, work_time):
        return utils_sequence.load_work_time_attributes(work_time)
    
    @classmethod
    def sync_active_group_to_json(cls):
        colortype_sequence.sync_active_group_to_json()
    
    @classmethod
    def register_live_color_update_handler(cls):
        colortype_sequence.register_live_color_update_handler()
    
    @classmethod
    def unregister_live_color_update_handler(cls):
        colortype_sequence.unregister_live_color_update_handler()
    
    @classmethod
    def get_recurrence_pattern_attributes(cls, recurrence_pattern):
        return utils_sequence.get_recurrence_pattern_attributes(recurrence_pattern)
    
    @classmethod
    def load_recurrence_pattern_attributes(cls, recurrence_pattern):
        return utils_sequence.load_recurrence_pattern_attributes(recurrence_pattern)
    
    @classmethod
    def get_recurrence_pattern_times(cls):
        return utils_sequence.get_recurrence_pattern_times()
    
    @classmethod
    def get_rel_sequence_attributes(cls):
        return utils_sequence.get_rel_sequence_attributes()
    
    @classmethod
    def load_rel_sequence_attributes(cls, rel_sequence):
        return utils_sequence.load_rel_sequence_attributes(rel_sequence)
    
    @classmethod
    def get_lag_time_attributes(cls):
        return utils_sequence.get_lag_time_attributes()
    
    @classmethod
    def load_lag_time_attributes(cls, lag_time):
        return utils_sequence.load_lag_time_attributes(lag_time)
    
    @classmethod 
    def get_work_schedule(cls, task):
        return task_sequence.get_work_schedule(task)
    
    @classmethod
    def get_checked_tasks(cls):
        return task_sequence.get_checked_tasks()
    
    @classmethod
    def load_task_resources(cls, task):
        return task_sequence.load_task_resources(task)
    
    @classmethod
    def get_sorted_tasks_ids(cls, tasks):
        return task_sequence.get_sorted_tasks_ids(tasks)
    
    @classmethod
    def get_filtered_tasks(cls, tasks):
        return task_sequence.get_filtered_tasks(tasks)
    
    @classmethod
    def get_selected_task_ids(cls):
        return task_sequence.get_selected_task_ids()
    
    @classmethod
    def get_animation_product_frames(cls, work_schedule, settings):
        return animation_sequence.get_animation_product_frames(work_schedule, settings)
    
    @classmethod
    def get_task_for_product(cls, product):
        return animation_sequence.get_task_for_product(product)
    
    @classmethod
    def get_product_frames_with_ColorTypes(cls, work_schedule, settings):
        return colortype_sequence.get_product_frames_with_ColorTypes(work_schedule, settings)
    
    # --- Additional Input/Output Methods ---
    @classmethod
    def load_task_inputs(cls, inputs):
        return task_sequence.load_task_inputs(inputs)
    
    @classmethod
    def load_task_outputs(cls, outputs):
        return task_sequence.load_task_outputs(outputs)
    
    @classmethod
    def get_task_inputs(cls, task):
        return task_sequence.get_task_inputs(task)
    
    @classmethod
    def get_direct_nested_tasks(cls, task):
        return task_sequence.get_direct_nested_tasks(task)
    
    @classmethod
    def get_direct_task_outputs(cls, task):
        return task_sequence.get_direct_task_outputs(task)
    
    # --- Variance Methods ---
    @classmethod
    def update_individual_variance_colors(cls):
        variance_sequence.update_individual_variance_colors()
    
    @classmethod
    def clear_schedule_variance(cls):
        variance_sequence.clear_variance_color_mode()
    
    @classmethod
    def enable_variance_color_mode(cls):
        return variance_sequence.enable_variance_color_mode()
    
    @classmethod
    def disable_variance_color_mode(cls):
        return variance_sequence.disable_variance_color_mode()
    
    # --- Load/Tree Methods ---
    @classmethod
    def load_task_tree(cls, work_schedule):
        return utils_sequence.load_task_tree(work_schedule)
    
    @classmethod
    def select_unassigned_work_schedule_products(cls):
        return utils_sequence.select_unassigned_work_schedule_products()
    
    @classmethod
    def get_unified_date_range(cls, work_schedule):
        return utils_sequence.get_unified_date_range(work_schedule)
    
    # --- Additional UI and Visibility Methods ---
    @classmethod
    def set_visibility_by_status(cls, visible_statuses):
        return utils_sequence.set_visibility_by_status(visible_statuses)
    
    @classmethod
    def enable_editing_work_plan(cls, work_plan):
        return utils_sequence.enable_editing_work_plan(work_plan)
    
    @classmethod
    def disable_editing_work_plan(cls):
        return utils_sequence.disable_editing_work_plan()
    
    @classmethod
    def enable_editing_work_plan_schedules(cls, work_plan):
        return utils_sequence.enable_editing_work_plan_schedules(work_plan)
    
    @classmethod
    def export_duration_prop(cls, prop, attributes):
        return utils_sequence.export_duration_prop(prop, attributes)
    
    @classmethod
    def add_duration_prop(cls, prop, value):
        return utils_sequence.add_duration_prop(prop, value)
    
    # --- Task Bar Visual Methods ---
    @classmethod
    def add_task_bar(cls, task_id):
        return visuals_sequence.add_task_bar(task_id)
    
    @classmethod
    def remove_task_bar(cls, task_id):
        return visuals_sequence.remove_task_bar(task_id)
    
    @classmethod
    def refresh_task_bars(cls):
        return visuals_sequence.refresh_task_bars()
    
    @classmethod
    def clear_task_bars(cls):
        return visuals_sequence.clear_task_bars()
    
    # --- Camera Detection Methods ---
    @classmethod
    def is_bonsai_camera(cls, obj):
        return visuals_sequence.is_bonsai_camera(obj)
    
    @classmethod
    def is_bonsai_animation_camera(cls, obj):
        return visuals_sequence.is_bonsai_animation_camera(obj)
    
    @classmethod
    def is_bonsai_snapshot_camera(cls, obj):
        return visuals_sequence.is_bonsai_snapshot_camera(obj)
    
    @classmethod
    def clear_camera_animation(cls, cam_obj):
        return camera_sequence.clear_camera_animation(cam_obj)
    
    # --- Additional ColorType Methods ---
    @classmethod
    def get_all_ColorType_groups(cls):
        return colortype_sequence.get_all_ColorType_groups()
    
    @classmethod
    def get_custom_ColorType_groups(cls):
        return colortype_sequence.get_custom_ColorType_groups()
    
    @classmethod
    def load_ColorType_group_data(cls, group_name):
        return colortype_sequence.load_ColorType_group_data(group_name)
    
    # --- Selected Task Methods ---
    @classmethod
    def get_selected_task_ids(cls):
        return task_sequence.get_selected_task_ids()
    
    # --- Work Calendar Methods ---
    @classmethod
    def enable_editing_work_calendar_times(cls, work_calendar):
        return task_sequence.enable_editing_work_calendar_times(work_calendar)
    
    @classmethod
    def load_work_calendar_attributes(cls, work_calendar):
        return task_sequence.load_work_calendar_attributes(work_calendar)
    
    @classmethod
    def enable_editing_work_calendar(cls, work_calendar):
        return task_sequence.enable_editing_work_calendar(work_calendar)
    
    @classmethod
    def disable_editing_work_calendar(cls):
        return task_sequence.disable_editing_work_calendar()
    
    @classmethod
    def get_work_calendar_attributes(cls):
        return task_sequence.get_work_calendar_attributes()
    
    @classmethod
    def load_work_time_attributes(cls, work_time):
        return task_sequence.load_work_time_attributes(work_time)
    
    @classmethod
    def enable_editing_work_time(cls, work_time):
        return task_sequence.enable_editing_work_time(work_time)
    
    @classmethod
    def get_work_time_attributes(cls):
        return task_sequence.get_work_time_attributes()
    
    @classmethod
    def get_recurrence_pattern_attributes(cls, recurrence_pattern):
        return task_sequence.get_recurrence_pattern_attributes(recurrence_pattern)
    
    @classmethod
    def disable_editing_work_time(cls):
        return task_sequence.disable_editing_work_time()
    
    @classmethod
    def get_recurrence_pattern_times(cls):
        return task_sequence.get_recurrence_pattern_times()
    
    @classmethod
    def reset_time_period(cls):
        return task_sequence.reset_time_period()
    
    @classmethod
    def get_active_work_time(cls):
        return task_sequence.get_active_work_time()
    
    # --- Task Management Methods ---
    @classmethod
    def enable_editing_task_calendar(cls, task):
        return task_sequence.enable_editing_task_calendar(task)
    
    @classmethod
    def enable_editing_task_sequence(cls):
        return task_sequence.enable_editing_task_sequence()
    
    @classmethod
    def refresh_task_output_counts(cls):
        return task_sequence.refresh_task_output_counts()
    
    @classmethod
    def disable_selecting_deleted_task(cls):
        return task_sequence.disable_selecting_deleted_task()
    
    @classmethod
    def enable_editing_task_attributes(cls, task):
        return task_sequence.enable_editing_task_attributes(task)
    
    @classmethod
    def disable_editing_task(cls):
        return task_sequence.disable_editing_task()
    
    @classmethod
    def enable_editing_task_time(cls, task):
        return task_sequence.enable_editing_task_time(task)
    
    # --- Sequence Relationship Methods ---
    @classmethod
    def load_rel_sequence_attributes(cls, rel_sequence):
        return task_sequence.load_rel_sequence_attributes(rel_sequence)
    
    @classmethod
    def enable_editing_rel_sequence_attributes(cls, rel_sequence):
        return task_sequence.enable_editing_rel_sequence_attributes(rel_sequence)
    
    @classmethod
    def load_lag_time_attributes(cls, lag_time):
        return task_sequence.load_lag_time_attributes(lag_time)
    
    @classmethod
    def enable_editing_sequence_lag_time(cls, rel_sequence):
        return task_sequence.enable_editing_sequence_lag_time(rel_sequence)
    
    @classmethod
    def get_rel_sequence_attributes(cls):
        return task_sequence.get_rel_sequence_attributes()
    
    @classmethod
    def disable_editing_rel_sequence(cls):
        return task_sequence.disable_editing_rel_sequence()
    
    @classmethod
    def get_lag_time_attributes(cls):
        return task_sequence.get_lag_time_attributes()
    
    # --- Column Management Methods ---
    @classmethod
    def add_task_column(cls, column_type, name, data_type):
        return utils_sequence.add_task_column(column_type, name, data_type)
    
    @classmethod
    def setup_default_task_columns(cls):
        return utils_sequence.setup_default_task_columns()
    
    @classmethod
    def remove_task_column(cls, name):
        return utils_sequence.remove_task_column(name)
    
    @classmethod
    def set_task_sort_column(cls, column):
        return utils_sequence.set_task_sort_column(column)
    
    # --- Validation and Helper Methods ---
    @classmethod
    def validate_task_object(cls, task, context="general"):
        return utils_sequence.validate_task_object(task, context)
    
    @classmethod
    def is_work_schedule_active(cls, work_schedule):
        return utils_sequence.is_work_schedule_active(work_schedule)
    
    @classmethod
    def disable_work_schedule(cls):
        return utils_sequence.disable_work_schedule()
    
    # --- Advanced Animation Methods ---
    @classmethod
    def get_animation_bar_types(cls):
        return animation_sequence.get_animation_bar_types()
    
    @classmethod
    def refresh_animation_color_scheme(cls):
        return animation_sequence.refresh_animation_color_scheme()
    
    @classmethod
    def get_animation_color_scheme(cls):
        return animation_sequence.get_animation_color_scheme()
    
    # --- Bar Creation Methods ---
    @classmethod
    def create_bars(cls, tasks):
        return visuals_sequence.create_bars(tasks)
    
    # --- Task Navigation Methods ---
    @classmethod
    def find_related_input_tasks(cls, product):
        return task_sequence.find_related_input_tasks(product)
    
    @classmethod
    def find_related_output_tasks(cls, product):
        return task_sequence.find_related_output_tasks(product)
    
    @classmethod
    def go_to_task(cls, task):
        return task_sequence.go_to_task(task)
    
    @classmethod
    def expand_task(cls, task):
        return task_sequence.expand_task(task)
    
    @classmethod
    def expand_all_tasks(cls):
        return task_sequence.expand_all_tasks()
    
    @classmethod
    def contract_all_tasks(cls):
        return task_sequence.contract_all_tasks()
    
    @classmethod
    def contract_task(cls, task):
        return task_sequence.contract_task(task)
    
    @classmethod
    def select_products(cls, products):
        return task_sequence.select_products(products)
    
    @classmethod
    def get_checked_tasks(cls):
        return task_sequence.get_checked_tasks()
    
    # --- Work Plan Methods ---
    @classmethod
    def enable_editing_work_plan_schedules(cls, work_plan):
        return task_sequence.enable_editing_work_plan_schedules(work_plan)
    
    @classmethod
    def load_work_plan_attributes(cls, work_plan):
        return task_sequence.load_work_plan_attributes(work_plan)
    
    @classmethod
    def enable_editing_work_plan(cls, work_plan):
        return task_sequence.enable_editing_work_plan(work_plan)
    
    @classmethod
    def disable_editing_work_plan(cls):
        return task_sequence.disable_editing_work_plan()
    
    @classmethod
    def get_work_plan_attributes(cls):
        return task_sequence.get_work_plan_attributes()
    
    @classmethod
    def copy_work_schedule(cls, work_schedule):
        return task_sequence.copy_work_schedule(work_schedule)
    
    @classmethod
    def load_work_schedule_attributes(cls, work_schedule):
        return task_sequence.load_work_schedule_attributes(work_schedule)
    
    # --- Advanced Camera Methods ---
    @classmethod
    def add_animation_camera(cls):
        return camera_sequence.add_animation_camera()
    
    @classmethod
    def add_snapshot_camera(cls):
        return camera_sequence.add_snapshot_camera()
    
    @classmethod
    def align_snapshot_camera_to_view(cls):
        return camera_sequence.align_snapshot_camera_to_view()
    
    @classmethod
    def align_animation_camera_to_view(cls):
        return camera_sequence.align_animation_camera_to_view()
    
    @classmethod
    def update_animation_camera(cls, cam_obj):
        return camera_sequence.update_animation_camera(cam_obj)
    
    # --- Date and Time Utilities ---
    @classmethod
    def parse_isodate_datetime(cls, value, include_time=True):
        return utils_sequence.parse_isodate_datetime(value, include_time)
    
    @classmethod
    def isodate_datetime(cls, value, include_time=True):
        return utils_sequence.isodate_datetime(value, include_time)
    
    # --- Selection and Visibility Methods ---
    @classmethod
    def apply_selection_from_checkboxes(cls):
        return utils_sequence.apply_selection_from_checkboxes()
    
    @classmethod
    def set_visibility_by_status(cls, visible_statuses):
        return utils_sequence.set_visibility_by_status(visible_statuses)
    
    @classmethod
    def select_unassigned_work_schedule_products(cls):
        return utils_sequence.select_unassigned_work_schedule_products()
    
    # --- Export and Import Methods ---
    @classmethod
    def create_tasks_json(cls, work_schedule):
        return utils_sequence.create_tasks_json(work_schedule)
    
    @classmethod
    def sync_3d_elements(cls, work_schedule, property_set_name):
        return utils_sequence.sync_3d_elements(work_schedule, property_set_name)
    
    # --- Get Work Schedule Attributes ---
    @classmethod
    def get_work_schedule_attributes(cls) -> dict[str, Any]:
        import bonsai.bim.module.sequence.helper as helper
        def callback(attributes: dict[str, Any], prop: Attribute) -> bool:
            if "Date" in prop.name or "Time" in prop.name:
                attributes[prop.name] = None if prop.is_null else helper.parse_datetime(prop.string_value)
                return True
            elif prop.name == "Duration" or prop.name == "TotalFloat":
                attributes[prop.name] = None if prop.is_null else helper.parse_duration(prop.string_value)
                return True
            return False
        props = props_sequence.get_work_schedule_props()
        return bonsai.bim.helper.export_attributes(props.work_schedule_attributes, callback)
    
    # --- Missing Methods Implementation ---
    
    @classmethod
    def _add(cls, total, new_value):
        return task_sequence._add(total, new_value)
    
    @classmethod
    def get_all_tasks_recursive_target(cls, work_schedule=None, flatten=True):
        return task_sequence.get_all_tasks_recursive_target(work_schedule, flatten)
    
    @classmethod
    def add_product_frame_full_range(cls, product, start_frame, finish_frame):
        return animation_sequence.add_product_frame_full_range(product, start_frame, finish_frame)
    
    @classmethod
    def calculate_using_frames(cls, task, frames_per_day=30):
        return animation_sequence.calculate_using_frames(task, frames_per_day)
    
    @classmethod
    def calculate_using_multiplier(cls, task, multiplier=1.0):
        return animation_sequence.calculate_using_multiplier(task, multiplier)
    
    # --- Additional Missing Methods Implementation ---
    
    @classmethod
    def _apply_color_to_object_simple(cls, obj, color):
        return colortype_sequence._apply_color_to_object_simple(obj, color)
    
    @classmethod
    def _apply_ColorType_to_object(cls, obj, colortype_data):
        return colortype_sequence._apply_ColorType_to_object(obj, colortype_data)
    
    @classmethod
    def activate_variance_color_mode(cls):
        return colortype_sequence.activate_variance_color_mode()
    
    @classmethod
    def deactivate_variance_color_mode(cls):
        return colortype_sequence.deactivate_variance_color_mode()
    
    @classmethod
    def clear_variance_color_mode(cls):
        return colortype_sequence.clear_variance_color_mode()
    
    @classmethod
    def clear_variance_colors_only(cls):
        return colortype_sequence.clear_variance_colors_only()
    
    @classmethod
    def _save_original_object_colors(cls):
        return colortype_sequence._save_original_object_colors()
    
    @classmethod
    def _restore_original_object_colors(cls):
        return colortype_sequence._restore_original_object_colors()
    
    @classmethod
    def _get_variance_color_for_object_real(cls, obj, task):
        return colortype_sequence._get_variance_color_for_object_real(obj, task)
    
    @classmethod
    def _create_variance_colortype_group(cls):
        return colortype_sequence._create_variance_colortype_group()
    
    @classmethod
    def add_bar(cls, task, start_frame, finish_frame):
        return animation_sequence.add_bar(task, start_frame, finish_frame)
    
    @classmethod
    def add_text(cls, text_content, location=(0, 0, 0)):
        return animation_sequence.add_text(text_content, location)
    
    @classmethod
    def animate_color(cls, obj, start_color, end_color, start_frame, end_frame):
        return animation_sequence.animate_color(obj, start_color, end_color, start_frame, end_frame)
    
    @classmethod
    def animate_scale(cls, obj, start_scale, end_scale, start_frame, end_frame):
        return animation_sequence.animate_scale(obj, start_scale, end_scale, start_frame, end_frame)
    
    @classmethod
    def create_plane(cls, location=(0, 0, 0), size=2.0):
        return animation_sequence.create_plane(location, size)
    
    @classmethod
    def create_task_bar_data(cls, task):
        return animation_sequence.create_task_bar_data(task)
    
    @classmethod
    def place_bar(cls, bar_data, y_position=0):
        return animation_sequence.place_bar(bar_data, y_position)
    
    @classmethod
    def set_material(cls, obj, material_name):
        return animation_sequence.set_material(obj, material_name)
    
    @classmethod
    def shift_object(cls, obj, offset):
        return animation_sequence.shift_object(obj, offset)
    
    @classmethod
    def get_animation_materials(cls):
        return animation_sequence.get_animation_materials()
    
    @classmethod
    def export_schedule_configuration(cls):
        return utils_sequence.export_schedule_configuration()
    
    @classmethod
    def import_schedule_configuration(cls, config_data):
        return utils_sequence.import_schedule_configuration(config_data)
    
    @classmethod
    def generate_gantt_browser_chart(cls):
        return utils_sequence.generate_gantt_browser_chart()
    
    @classmethod
    def has_variance_calculation_in_tasks(cls):
        return utils_sequence.has_variance_calculation_in_tasks()
    
    @classmethod
    def link_collection(cls, collection_name):
        return utils_sequence.link_collection(collection_name)
    
    @classmethod
    def restore_all_ui_state(cls):
        return utils_sequence.restore_all_ui_state()
    
    @classmethod
    def snapshot_all_ui_state(cls):
        return utils_sequence.snapshot_all_ui_state()