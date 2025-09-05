import bpy
import json
import calendar
from mathutils import Matrix
from datetime import datetime
from dateutil import relativedelta
import bonsai.tool as tool
import bonsai.core.sequence as core
import ifcopenshell.util.sequence
import ifcopenshell.util.selector
from bpy_extras.io_utils import ImportHelper, ExportHelper
from typing import TYPE_CHECKING

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
        def snapshot_all_ui_state(context):
            pass
        def restore_all_ui_state(context):
            pass
        # Fallback for safe assignment function
        class PropFallback:
            @staticmethod
            def safe_set_selected_colortype_in_active_group(task_obj, value):
                try:
                    setattr(task_obj, "selected_colortype_in_active_group", value)
                except Exception as e:
                    print(f"❌ Fallback safe_set failed: {e}")
        prop = PropFallback()


# Status Filter Operators
class EnableStatusFilters(bpy.types.Operator):
    bl_idname = "bim.enable_status_filters"
    bl_label = "Enable Status Filters"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_status_props()
        props.is_enabled = True
        hidden_statuses = {s.name for s in props.statuses if not s.is_visible}

        props.statuses.clear()

        statuses = set()
        for element in tool.Ifc.get().by_type("IfcPropertyEnumeratedValue"):
            if element.Name == "Status":
                if element.PartOfPset and isinstance(element.EnumerationValues, tuple):
                    pset = element.PartOfPset[0]
                    if pset.Name.startswith("Pset_") and pset.Name.endswith("Common"):
                        statuses.update(element.EnumerationValues)
                    elif pset.Name == "EPset_Status":  # Our secret sauce
                        statuses.update(element.EnumerationValues)
            elif element.Name == "UserDefinedStatus":
                statuses.add(element.NominalValue)

        statuses = ["No Status"] + sorted([s.wrappedValue for s in statuses])

        for status in statuses:
            new = props.statuses.add()
            new.name = status
            if new.name in hidden_statuses:
                new.is_visible = False

        visible_statuses = {s.name for s in props.statuses if s.is_visible}
        tool.Sequence.set_visibility_by_status(visible_statuses)
        return {"FINISHED"}


class DisableStatusFilters(bpy.types.Operator):
    bl_idname = "bim.disable_status_filters"
    bl_label = "Disable Status Filters"
    bl_description = "Deactivate status filters panel.\nCan be used to refresh the displayed statuses"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_status_props()

        all_statuses = {s.name for s in props.statuses}
        tool.Sequence.set_visibility_by_status(all_statuses)
        props.is_enabled = False
        return {"FINISHED"}


class ActivateStatusFilters(bpy.types.Operator):
    bl_idname = "bim.activate_status_filters"
    bl_label = "Activate Status Filters"
    bl_description = "Filter and display objects based on currently selected IFC statuses"
    bl_options = {"REGISTER", "UNDO"}

    only_if_enabled: bpy.props.BoolProperty(  # pyright: ignore[reportRedeclaration]
        name="Only If Filters are Enabled",
        description="Activate status filters only in case if they were enabled from the UI before.",
        default=False,
    )

    if TYPE_CHECKING:
        only_if_enabled: bool

    def execute(self, context):
        props = tool.Sequence.get_status_props()

        if not props.is_enabled:
            if not self.only_if_enabled:
                # Allow users to use the same operator to refresh filters,
                # even if they were not enabled before.
                # Typically would occur when operator is added to Quick Favorites.
                bpy.ops.bim.enable_status_filters()
            return {"FINISHED"}

        visible_statuses = {s.name for s in props.statuses if s.is_visible}
        tool.Sequence.set_visibility_by_status(visible_statuses)
        return {"FINISHED"}


class SelectStatusFilter(bpy.types.Operator):
    bl_idname = "bim.select_status_filter"
    bl_label = "Select Status Filter"
    bl_description = "Select elements with currently selected status"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def execute(self, context):
        query = f"IfcProduct, /Pset_.*Common/.Status={self.name} + IfcProduct, EPset_Status.Status={self.name}"
        if self.name == "No Status":
            query = f"IfcProduct, /Pset_.*Common/.Status=NULL, EPset_Status.Status=NULL"
        for element in ifcopenshell.util.selector.filter_elements(tool.Ifc.get(), query):
            obj = tool.Ifc.get_object(element)
            if obj:
                obj.select_set(True)
        return {"FINISHED"}


# Task Filter Operators
class AddTaskFilter(bpy.types.Operator):
    """Adds a new filter rule to the list."""
    bl_idname = "bim.add_task_filter"
    bl_label = "Add Task Filter"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Removed last_lookahead_window clearing to preserve active filters
        new_rule = props.filters.rules.add()
        
        # Set default to TASK.NAME, especially important for the first filter
        new_rule.column = "IfcTask.Name||string"
        
        # Inicializa data_type/operadores de la nueva regla
        update_filter_column(new_rule, context)
        
        props.filters.active_rule_index = len(props.filters.rules) - 1
        return {'FINISHED'}


class RemoveTaskFilter(bpy.types.Operator):
    """Deletes the selected filter rule."""
    bl_idname = "bim.remove_task_filter"
    bl_label = "Remove Task Filter"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Removed last_lookahead_window clearing to preserve active filters
        index = props.filters.active_rule_index
        
        if 0 <= index < len(props.filters.rules):
            props.filters.rules.remove(index)
            props.filters.active_rule_index = min(max(0, index - 1), len(props.filters.rules) - 1)
            
            # Ahora, refresca la lista de tareas aplicando el nuevo conjunto de filtros.
            # Esta lógica es la misma que en ApplyTaskFilters.
            try:
                snapshot_all_ui_state(context)
            except Exception as e:
                print(f"Bonsai WARNING: snapshot_all_ui_state failed in RemoveTaskFilter: {e}")

            try:
                ws = tool.Sequence.get_active_work_schedule()
                if ws:
                    tool.Sequence.load_task_tree(ws)
                    tool.Sequence.load_task_properties()
            except Exception as e:
                print(f"Bonsai WARNING: task tree reload failed in RemoveTaskFilter: {e}")

            try:
                restore_all_ui_state(context)
            except Exception as e:
                print(f"Bonsai WARNING: restore_all_ui_state failed in RemoveTaskFilter: {e}")

        return {'FINISHED'}


class ClearAllTaskFilters(bpy.types.Operator):
    """Clears all task filters at once."""
    bl_idname = "bim.clear_all_task_filters"
    bl_label = "Clear All Filters"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        
        # Clear all filter rules
        props.filters.rules.clear()
        props.filters.active_rule_index = 0
        
        # Apply the changes (reload task tree with no filters)
        try:
            snapshot_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: snapshot_all_ui_state failed in ClearAllTaskFilters: {e}")

        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties()
        except Exception as e:
            print(f"Bonsai WARNING: task tree reload failed in ClearAllTaskFilters: {e}")

        try:
            restore_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: restore_all_ui_state failed in ClearAllTaskFilters: {e}")

        self.report({'INFO'}, "All filters cleared")
        return {'FINISHED'}


class ApplyTaskFilters(bpy.types.Operator):
    """Triggers the recalculation and update of the task list."""
    bl_idname = "bim.apply_task_filters"
    bl_label = "Apply Task Filters"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Removed problematic last_lookahead_window clearing - following v50 approach
        # 1) Guardar snapshot del estado UI
        try:
            snapshot_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: snapshot_all_ui_state falló: {e}")

        # 2) Recalcular lista aplicando filtros activos
        try:
            ws = tool.Sequence.get_active_work_schedule()
            if ws:
                tool.Sequence.load_task_tree(ws)
                tool.Sequence.load_task_properties()
        except Exception as e:
            print(f"Bonsai WARNING: recarga de tareas falló: {e}")

        # 2.5) Lógica inteligente: Si las nuevas tareas NO tienen varianza calculada, limpiar colores 3D
        try:
            if not tool.Sequence.has_variance_calculation_in_tasks():
                print("🧠 New tasks have no variance calculation → clearing 3D colors only")
                tool.Sequence.clear_variance_colors_only()
            else:
                print("ℹ️ New tasks have variance calculation → keeping colors active")
        except Exception as e:
            print(f"⚠️ Error in intelligent variance color check: {e}")

        # 3) Restaurar estado UI
        try:
            restore_all_ui_state(context)
        except Exception as e:
            print(f"Bonsai WARNING: restore_all_ui_state falló: {e}")

        return {'FINISHED'}


class ApplyLookaheadFilter(bpy.types.Operator):
    """Applies a 'Lookahead' filter to see upcoming tasks."""

    bl_idname = "bim.apply_lookahead_filter"
    bl_label = "Apply Lookahead Filter"
    bl_options = {"REGISTER", "UNDO"}

    time_window: bpy.props.EnumProperty(
        name="Time Window",
        items=[
            ('THIS_WEEK', "This Week", "Show tasks scheduled for the current week"),
            ('LAST_WEEK', "Last Week", "Show tasks scheduled for the previous week"),
            ("1_WEEK", "Next 1 Week", ""),
            ("2_WEEKS", "Next 2 Weeks", ""),
            ("4_WEEKS", "Next 4 Weeks", ""),
            ("6_WEEKS", "Next 6 Weeks", ""),
            ("12_WEEKS", "Next 12 Weeks", ""),
        ],
    )

    def execute(self, context):
        from datetime import datetime, timedelta
        import ifcopenshell.util.sequence

        # 1. Verificar que hay un cronograma activo
        active_schedule = tool.Sequence.get_active_work_schedule()
        if not active_schedule:
            self.report({'ERROR'}, "No active work schedule. Please select one first.")
            return {'CANCELLED'}

        # 2. Verificar que el cronograma no esté vacío
        if not ifcopenshell.util.sequence.get_root_tasks(active_schedule):
            self.report({'WARNING'}, "The active schedule has no tasks. Filter not applied.")
            return {'CANCELLED'}

        props = tool.Sequence.get_work_schedule_props()

        # Store the selected time window so we can re-apply it automatically
        props.last_lookahead_window = self.time_window

        props.filters.rules.clear()  # Limpiar filtros existentes

        # --- INICIO DE LA MODIFICACIÓN ---
        # Obtener el tipo de fecha seleccionado en la UI (Schedule, Actual, etc.)
        date_source = getattr(props, "date_source_type", "SCHEDULE")
        date_prefix = date_source.capitalize()
        start_column = f"IfcTaskTime.{date_prefix}Start||date"
        finish_column = f"IfcTaskTime.{date_prefix}Finish||date"
        # --- END OF MODIFICATION ---

        today = datetime.now()
        filter_start = None
        filter_end = None

        if self.time_window == 'THIS_WEEK':
            filter_start = today - timedelta(days=today.weekday())
            filter_end = filter_start + timedelta(days=6)
        elif self.time_window == 'LAST_WEEK':
            filter_start = today - timedelta(days=today.weekday(), weeks=1)
            filter_end = filter_start + timedelta(days=6)
        elif self.time_window == "1_WEEK":
            filter_start = today
            filter_end = today + timedelta(weeks=1)
        elif self.time_window == "2_WEEKS":
            filter_start = today
            filter_end = today + timedelta(weeks=2)
        elif self.time_window == "4_WEEKS":
            filter_start = today
            filter_end = today + timedelta(weeks=4)
        elif self.time_window == "6_WEEKS":
            filter_start = today
            filter_end = today + timedelta(weeks=6)
        else:  # 12_WEEKS
            filter_start = today
            filter_end = today + timedelta(weeks=12)

        # --- INICIO DE LA MODIFICACIÓN ---
        # Regla 1: La tarea debe empezar ANTES (o en) la fecha de fin del rango, usando la columna dinámica.
        rule1 = props.filters.rules.add()
        rule1.is_active = True
        rule1.column = start_column
        rule1.operator = "LTE"  # Menor o igual que
        rule1.value_string = filter_end.strftime("%Y-%m-%d")

        # Regla 2: La tarea debe terminar DESPUÉS (o en) la fecha de inicio del rango, usando la columna dinámica.
        rule2 = props.filters.rules.add()
        rule2.is_active = True
        rule2.column = finish_column
        rule2.operator = "GTE"  # Mayor o igual que
        rule2.value_string = filter_start.strftime("%Y-%m-%d")
        # --- END OF MODIFICATION ---

        props.filters.active_rule_index = 0 # Asegura que una regla esté seleccionada para las operaciones de UI
        props.filters.logic = "AND"

        # --- INICIO DE LA CORRECCIÓN ---
        # Actualizar las fechas de Animation Settings para que coincidan con el filtro
        if filter_start and filter_end:
            tool.Sequence.update_visualisation_date(filter_start, filter_end)
        # --- FIN DE LA CORRECCIÓN ---
        bpy.ops.bim.apply_task_filters()
        self.report({"INFO"}, f"Filter applied: {self.time_window.replace('_', ' ').title()} (using {date_prefix} dates)"
        )
        return {"FINISHED"}


# Filter Set Operators
class UpdateSavedFilterSet(bpy.types.Operator):
    """Overwrites a saved filter set with the current active filter rules."""
    bl_idname = "bim.update_saved_filter_set"
    bl_label = "Update Saved Filter Set"
    bl_options = {"REGISTER", "UNDO"}

    set_index: bpy.props.IntProperty()

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Removed last_lookahead_window clearing to preserve active filters
        saved_set = props.saved_filter_sets[self.set_index]

        # Clear old rules from the saved filter
        saved_set.rules.clear()

        # Copy current active rules to the saved filter
        for active_rule in props.filters.rules:
            saved_rule = saved_set.rules.add()
            saved_rule.is_active = active_rule.is_active
            saved_rule.column = active_rule.column
            saved_rule.operator = active_rule.operator
            try:
                saved_rule.value_string = active_rule.value_string
            except Exception:
                pass
            try:
                saved_rule.data_type = active_rule.data_type
            except Exception:
                pass

        self.report({'INFO'}, f"Filter '{saved_set.name}' updated successfully.")
        return {'FINISHED'}


class SaveFilterSet(bpy.types.Operator):
    """Saves the current filter set as a named preset."""
    bl_idname = "bim.save_filter_set"
    bl_label = "Save Filter Set"
    bl_options = {"REGISTER", "UNDO"}

    set_name: bpy.props.StringProperty(name="Name", description="Name to save this filter set as")

    def execute(self, context):
        if not self.set_name.strip():
            self.report({'ERROR'}, "Name cannot be empty.")
            return {'CANCELLED'}

        props = tool.Sequence.get_work_schedule_props()

        # Crear un nuevo conjunto guardado
        # Create a new saved set
        new_set = props.saved_filter_sets.add()
        new_set.name = self.set_name

        # Copy the rules from the active filter to the new set
        for active_rule in props.filters.rules:
            saved_rule = new_set.rules.add()
            saved_rule.is_active = active_rule.is_active
            saved_rule.column = active_rule.column
            saved_rule.operator = active_rule.operator
            try:
                saved_rule.value_string = active_rule.value_string
            except Exception:
                pass
            try:
                saved_rule.data_type = active_rule.data_type
            except Exception:
                pass

        self.report({'INFO'}, f"Filter '{self.set_name}' saved.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class LoadFilterSet(bpy.types.Operator):
    """Loads a saved filter set and applies it."""
    bl_idname = "bim.load_filter_set"
    bl_label = "Load Filter Set"
    bl_options = {"REGISTER", "UNDO"}

    set_index: bpy.props.IntProperty()

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        if not (0 <= self.set_index < len(props.saved_filter_sets)):
            self.report({'ERROR'}, "Invalid filter index.")
            return {'CANCELLED'}

        saved_set = props.saved_filter_sets[self.set_index]

        # Limpiar filtros activos y cargar los guardados
        props.filters.rules.clear()
        for saved_rule in saved_set.rules:
            active_rule = props.filters.rules.add()
            active_rule.is_active = saved_rule.is_active
            active_rule.column = saved_rule.column
            active_rule.operator = saved_rule.operator
            try:
                active_rule.value_string = saved_rule.value_string
            except Exception:
                pass
            try:
                active_rule.data_type = saved_rule.data_type
            except Exception:
                pass

        # Aplicar filtros recargando la lista
        ws = tool.Sequence.get_active_work_schedule()
        if ws:
            tool.Sequence.load_task_tree(ws)
            tool.Sequence.load_task_properties()

        # Lógica inteligente: Si las nuevas tareas NO tienen varianza calculada, limpiar colores 3D
        try:
            if not tool.Sequence.has_variance_calculation_in_tasks():
                print("🧠 Loaded tasks have no variance calculation → clearing 3D colors only")
                tool.Sequence.clear_variance_colors_only()
            else:
                print("ℹ️ Loaded tasks have variance calculation → keeping colors active")
        except Exception as e:
            print(f"⚠️ Error in intelligent variance color check: {e}")

        return {'FINISHED'}


class RemoveFilterSet(bpy.types.Operator):
    """Deletes a saved filter set."""
    bl_idname = "bim.remove_filter_set"
    bl_label = "Remove Filter Set"
    bl_options = {"REGISTER", "UNDO"}

    set_index: bpy.props.IntProperty()

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        # Removed last_lookahead_window clearing to preserve active filters
        if not (0 <= self.set_index < len(props.saved_filter_sets)):
            self.report({'ERROR'}, "Invalid filter index.")
            return {'CANCELLED'}

        set_name = props.saved_filter_sets[self.set_index].name
        props.saved_filter_sets.remove(self.set_index)
        props.active_saved_filter_set_index = min(max(0, self.set_index - 1), len(props.saved_filter_sets) - 1)
        self.report({'INFO'}, f"Filter '{set_name}' removed.")
        return {'FINISHED'}


class ExportFilterSet(bpy.types.Operator, ExportHelper):
    """Exports the ENTIRE library of saved filter sets to a JSON file."""
    bl_idname = "bim.export_filter_set"
    bl_label = "Export Filter Library"  # Updated label
    bl_description = "Export all saved filters to a single JSON file"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()

        # 1. Prepare a dictionary to store the entire library
        library_data = {}

        # 2. Iterate through each saved filter in the library
        for saved_set in props.saved_filter_sets:
            rules_data = []
            # 3. Iterate through rules of each saved filter
            for rule in saved_set.rules:
                rules_data.append({
                    "is_active": rule.is_active,
                    "column": rule.column,
                    "operator": rule.operator,
                    "value": rule.value,
                })
            # 4. Add the filter and its rules to the library
            library_data[saved_set.name] = {"rules": rules_data}

        # 5. Write the entire library to the JSON file
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(library_data, f, ensure_ascii=False, indent=4)

        self.report({'INFO'}, f"Filter library exported to {self.filepath}")
        return {'FINISHED'}


class ImportFilterSet(bpy.types.Operator, ImportHelper):
    """Imports a library of filter sets from a JSON file, replacing the current library."""
    bl_idname = "bim.import_filter_set"
    bl_label = "Import Filter Library"  # Updated label
    bl_description = "Import a filter library from a JSON file, replacing all current saved filters"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    # 'set_name' property is no longer needed; names come from the JSON file
    def execute(self, context):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                library_data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Could not read or parse JSON file: {e}")
            return {'CANCELLED'}

        props = tool.Sequence.get_work_schedule_props()
        
        # 1. ELIMINADO: La línea `props.saved_filter_sets.clear()` ha sido removida.
        # Ya no se borra la biblioteca existente.
        
        # 2. AÑADIDO: Comprobación para evitar duplicados
        # Obtenemos los nombres de los filtros que ya existen.
        existing_names = {fs.name for fs in props.saved_filter_sets}
        imported_count = 0
        
        for set_name, set_data in library_data.items():
            # Si el nombre del filtro a importar ya existe, lo saltamos.
            if set_name in existing_names:
                continue

            # Si no existe, lo añadimos.
            new_set = props.saved_filter_sets.add()
            new_set.name = set_name
            
            for rule_data in set_data.get("rules", []):
                new_rule = new_set.rules.add()
                new_rule.is_active = rule_data.get("is_active", True)
                new_rule.column = rule_data.get("column", "")
                new_rule.operator = rule_data.get("operator", "CONTAINS")
                new_rule.value = rule_data.get("value", "")
            
            imported_count += 1
        
        self.report({'INFO'}, f"{imported_count} new filter sets imported and combined.")
        return {'FINISHED'}


# Date Picker Operators
class Bonsai_DatePicker(bpy.types.Operator):
    bl_label = "Date Picker"
    bl_idname = "bim.datepicker"
    bl_options = {"REGISTER", "UNDO"}
    target_prop: bpy.props.StringProperty(name="Target date prop to set")
    # TODO: base it on property type.
    include_time: bpy.props.BoolProperty(name="Include Time", default=True)

    if TYPE_CHECKING:
        target_prop: str
        include_time: bool

    def execute(self, context):
        selected_date = context.scene.DatePickerProperties.selected_date
        try:
            # Just to make sure the date is valid.
            tool.Sequence.parse_isodate_datetime(selected_date, self.include_time)
            self.set_scene_prop(self.target_prop, selected_date)
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Provided date is invalid: '{selected_date}'. Exception: {str(e)}.")
            return {"CANCELLED"}

    def draw(self, context):
        props = context.scene.DatePickerProperties
        display_date = tool.Sequence.parse_isodate_datetime(props.display_date, False)
        current_month = (display_date.year, display_date.month)
        lines = calendar.monthcalendar(*current_month)
        month_title, week_titles = calendar.month(*current_month).splitlines()[:2]

        layout = self.layout
        row = layout.row()
        row.prop(props, "selected_date", text="Date")

        # Time.
        if self.include_time:
            row = layout.row()
            row.label(text="Time:")
            row.prop(props, "selected_hour", text="H")
            row.prop(props, "selected_min", text="M")
            row.prop(props, "selected_sec", text="S")

        # Month.
        month_delta = relativedelta.relativedelta(months=1)
        split = layout.split()
        col = split.row()
        op = col.operator("wm.context_set_string", icon="TRIA_LEFT", text="")
        op.data_path = "scene.DatePickerProperties.display_date"
        op.value = tool.Sequence.isodate_datetime(display_date - month_delta, False)

        col = split.row()
        col.label(text=month_title.strip())

        col = split.row()
        col.alignment = "RIGHT"
        op = col.operator("wm.context_set_string", icon="TRIA_RIGHT", text="")
        op.data_path = "scene.DatePickerProperties.display_date"
        op.value = tool.Sequence.isodate_datetime(display_date + month_delta, False)

        # Day of week.
        row = layout.row(align=True)
        for title in week_titles.split():
            col = row.column(align=True)
            col.alignment = "CENTER"
            col.label(text=title.strip())

        # Days calendar.
        current_selected_date = tool.Sequence.parse_isodate_datetime(props.selected_date, self.include_time)
        current_selected_date = current_selected_date.replace(hour=0, minute=0, second=0)

        for line in lines:
            row = layout.row(align=True)
            for i in line:
                col = row.column(align=True)
                if i == 0:
                    col.label(text="  ")
                else:
                    selected_date = datetime(year=display_date.year, month=display_date.month, day=i)
                    is_current_date = current_selected_date == selected_date
                    op = col.operator("wm.context_set_string", text="{:2d}".format(i), depress=is_current_date)
                    if self.include_time:
                        selected_date = selected_date.replace(
                            hour=props.selected_hour, minute=props.selected_min, second=props.selected_sec
                        )
                    op.data_path = "scene.DatePickerProperties.selected_date"
                    op.value = tool.Sequence.isodate_datetime(selected_date, self.include_time)

    def invoke(self, context, event):
        props = context.scene.DatePickerProperties
        current_date_str = self.get_scene_prop(self.target_prop)
        
        current_date = None # Initialize to None
        if current_date_str: # Attempt to parse the existing date string
            current_date = tool.Sequence.parse_isodate_datetime(current_date_str, self.include_time) 
        
        # Fallback to current datetime if parsing failed or no string was provided
        if current_date is None:
            current_date = datetime.now() 
            current_date = current_date.replace(second=0) # Remove seconds for cleaner UI

        if self.include_time:
            props["selected_hour"] = current_date.hour
            props["selected_min"] = current_date.minute
            props["selected_sec"] = current_date.second

        props.display_date = tool.Sequence.isodate_datetime(current_date.replace(day=1), False)
        props.selected_date = tool.Sequence.isodate_datetime(current_date, self.include_time)
        return context.window_manager.invoke_props_dialog(self)

    def get_scene_prop(self, prop_path: str) -> str:
        scene = bpy.context.scene
        return scene.path_resolve(prop_path)

    def set_scene_prop(self, prop_path: str, value: str) -> None:
        scene = bpy.context.scene
        tool.Blender.set_prop_from_path(scene, prop_path, value)


class FilterDatePicker(bpy.types.Operator):
    """A specialized Date Picker that updates the value of a filter rule."""
    bl_idname = "bim.filter_datepicker"
    bl_label = "Select Filter Date"
    bl_options = {"REGISTER", "UNDO"}

    # Propiedad para saber qué regla de la lista modificar
    rule_index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        props = tool.Sequence.get_work_schedule_props()
        if self.rule_index < 0 or self.rule_index >= len(props.filters.rules):
            self.report({'ERROR'}, "Invalid filter rule index.")
            return {'CANCELLED'}
        
        # Obtener la fecha seleccionada del DatePickerProperties
        selected_date_str = context.scene.DatePickerProperties.selected_date
        if not selected_date_str:
            self.report({'ERROR'}, "No date selected.")
            return {'CANCELLED'}
            
        # Actualizar el valor de la regla de filtro
        target_rule = props.filters.rules[self.rule_index]
        target_rule.value_string = selected_date_str
        
        # Aplicar los filtros automáticamente
        try:
            bpy.ops.bim.apply_task_filters()
        except Exception as e:
            print(f"Error applying filters: {e}")
        
        self.report({'INFO'}, f"Date set to: {selected_date_str}")
        return {"FINISHED"}

    def invoke(self, context, event):
        if self.rule_index < 0:
            self.report({'ERROR'}, "No rule index specified.")
            return {'CANCELLED'}
            
        props = tool.Sequence.get_work_schedule_props()
        if self.rule_index >= len(props.filters.rules):
            self.report({'ERROR'}, "Invalid filter rule index.")
            return {'CANCELLED'}
        
        # Obtener la fecha actual de la regla
        current_date_str = props.filters.rules[self.rule_index].value_string
        
        # Configurar el DatePickerProperties
        date_picker_props = context.scene.DatePickerProperties
        
        if current_date_str and current_date_str.strip():
            try:
                # Intentar parsear la fecha existente
                current_date = datetime.fromisoformat(current_date_str.split('T')[0])
            except Exception:
                try:
                    from dateutil import parser as date_parser
                    current_date = date_parser.parse(current_date_str)
                except Exception:
                    current_date = datetime.now()
        else:
            current_date = datetime.now()
        
        # Configurar las propiedades del DatePicker
        date_picker_props.selected_date = current_date.strftime("%Y-%m-%d")
        date_picker_props.display_date = current_date.replace(day=1).strftime("%Y-%m-%d")
        
        # Show the dialog
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        """Calendar interface for selecting dates"""
        import calendar
        from dateutil import relativedelta
        
        layout = self.layout
        props = context.scene.DatePickerProperties
        
        # Parsear la fecha de display actual
        try:
            display_date = datetime.fromisoformat(props.display_date)
        except Exception:
            display_date = datetime.now()
            props.display_date = display_date.strftime("%Y-%m-%d")
        
        # Manual date entry field
        row = layout.row()
        row.prop(props, "selected_date", text="Date")
        
        # Month navigation
        current_month = (display_date.year, display_date.month)
        lines = calendar.monthcalendar(*current_month)
        month_title = calendar.month_name[display_date.month] + f" {display_date.year}"
        
        # Month header with navigation
        row = layout.row(align=True)
        
        # Botón mes anterior
        prev_month = display_date - relativedelta.relativedelta(months=1)
        op = row.operator("wm.context_set_string", icon="TRIA_LEFT", text="")
        op.data_path = "scene.DatePickerProperties.display_date"
        op.value = prev_month.strftime("%Y-%m-%d")
        
        # Month title
        row.label(text=month_title)
        
        # Botón mes siguiente  
        next_month = display_date + relativedelta.relativedelta(months=1)
        op = row.operator("wm.context_set_string", icon="TRIA_RIGHT", text="")
        op.data_path = "scene.DatePickerProperties.display_date"
        op.value = next_month.strftime("%Y-%m-%d")
        
        # Days of the week
        row = layout.row(align=True)
        for day_name in ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']:
            col = row.column(align=True)
            col.alignment = "CENTER"
            col.label(text=day_name)
        
        # Parse the selected date to highlight it
        try:
            selected_date = datetime.fromisoformat(props.selected_date)
        except Exception:
            selected_date = None
        
        # Días del calendario
        for week in lines:
            row = layout.row(align=True)
            for day in week:
                col = row.column(align=True)
                if day == 0:
                    col.label(text="")
                else:
                    day_date = datetime(display_date.year, display_date.month, day)
                    day_str = day_date.strftime("%Y-%m-%d")
                    
                    # Check if it is the selected day
                    is_selected = (selected_date and day_date.date() == selected_date.date())
                    
                    # Button to select the day
                    op = col.operator("wm.context_set_string", 
                                    text=str(day), 
                                    depress=is_selected)
                    op.data_path = "scene.DatePickerProperties.selected_date"
                    op.value = day_str

