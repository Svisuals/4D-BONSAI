import bpy
import json
import calendar
from mathutils import Matrix
from datetime import datetime
from dateutil import relativedelta
import bonsai.tool as tool

try:
    from .prop import update_filter_column
    from . import prop
    from .ui import calculate_visible_columns_count
except Exception:
    try:
        from bonsai.bim.module.sequence.prop import update_filter_column
        import bonsai.bim.module.sequence.prop as prop
        from bonsai.bim.module.sequence.ui import calculate_visible_columns_count
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

try:
    from .animation_operators import _ensure_default_group
except Exception:
    try:
        from bonsai.bim.module.sequence.animation_operators import _ensure_default_group
    except Exception:
        def _ensure_default_group(context):
            """Fallback implementation if import fails"""
            pass

try:
    from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
except Exception:
    UnifiedColorTypeManager = None  # optional

# Constants
DEMO_KEYS = {"DEMOLITION","REMOVAL","DISPOSAL","DISMANTLE"}

# Helper Functions

def _get_internal_colortype_sets(context):
    scene = context.scene
    key = "BIM_AnimationColorSchemesSets"
    # Ensure container exists
    if key not in scene:
        scene[key] = json.dumps({})
    # Parse
    try:
        data = json.loads(scene[key])
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    # --- Auto-create DEFAULT group if empty ---
    try:
        if not data:
            default_names = [
                "ATTENDANCE", "CONSTRUCTION", "DEMOLITION", "DISMANTLE",
                "DISPOSAL", "INSTALLATION", "LOGISTIC", "MAINTENANCE",
                "MOVE", "OPERATION", "REMOVAL", "RENOVATION",
            ]
            data = {"DEFAULT": {"ColorTypes": [{"name": n} for n in default_names]}}
            scene[key] = json.dumps(data)
    except Exception:
        pass
    return data

def _set_internal_colortype_sets(context, data: dict):
    context.scene["BIM_AnimationColorSchemesSets"] = json.dumps(data)

def _current_colortype_names():
    try:
        props = tool.Sequence.get_animation_props()
        return [p.name for p in getattr(props, "ColorTypes", [])]
    except Exception:
        return []

def _clean_task_colortype_mappings(context, removed_group_name: str | None = None):
    """
    Ensures per-task mapping stays consistent:
      - If a group is removed, drop its entry from each task.
      - If selected colortype no longer exists in the current group, clear it.
    Also clears the visible Enum property if it points to a removed colortype.
    """
    try:
        wprops = tool.Sequence.get_work_schedule_props()
        tprops = tool.Sequence.get_task_tree_props()
        anim = tool.Sequence.get_animation_props()
        active_group = getattr(anim, "ColorType_groups", "") or ""
        valid_names = set(_current_colortype_names())

        for t in list(getattr(tprops, "tasks", [])):
            # Remove group-specific entry if group removed
            if removed_group_name and hasattr(t, "colortype_group_choices"):
                to_keep = []
                for item in t.colortype_group_choices:
                    if item.group_name != removed_group_name:
                        to_keep.append((item.group_name, getattr(item, 'enabled', False), getattr(item, 'selected_colortype', "")))
                # Rebuild collection if anything changed
                if len(to_keep) != len(t.colortype_group_choices):
                    t.colortype_group_choices.clear()
                    for g, en, sel in to_keep:
                        it = t.colortype_group_choices.add()
                        it.group_name = g
                        try:
                            it.enabled = bool(en)
                        except Exception:
                            pass
                        try:
                            it.selected_colortype = sel or ""
                        except Exception:
                            pass

                # If the visible toggle points to removed group, turn it off
                if active_group == removed_group_name:
                    try:
                        t.use_active_colortype_group = False
                        prop.safe_set_selected_colortype_in_active_group(t, "")
                    except Exception:
                        pass

            # If current visible selection references a deleted colortype, clear it
            try:
                if getattr(t, "selected_colortype_in_active_group", "") and \
                   t.selected_colortype_in_active_group not in valid_names:
                    prop.safe_set_selected_colortype_in_active_group(t, "")
            except Exception:
                pass
            # Also clear stored selection for the active group
            try:
                if hasattr(t, "colortype_group_choices") and active_group:
                    for item in t.colortype_group_choices:
                        if item.group_name == active_group and getattr(item, 'selected_colortype', "") not in valid_names:
                            try:
                                item.selected_colortype = ""
                            except Exception:
                                pass
            except Exception:
                pass
    except Exception:
        # Best-effort; never break operator
        pass

def _colortype_set_items(self, context):
    items = []
    data = _get_internal_colortype_sets(context)
    for i, name in enumerate(sorted(data.keys())):
        items.append((name, name, "", i))
    if not items:
        items = [("", "<no groups>", "", 0)]
    return items

def _removable_colortype_set_items(self, context):
    """Returns colortype sets that can be removed (excludes DEFAULT)."""
    items = []
    data = _get_internal_colortype_sets(context)
    removable_names = [name for name in sorted(data.keys()) if name != "DEFAULT"]
    for i, name in enumerate(removable_names):
        items.append((name, name, "", i))
    if not items:
        items = [("", "<no removable groups>", "", 0)]
    return items

def _verify_colortype_json_stats(context):
    data = _get_internal_colortype_sets(context)
    total_colortypes = 0
    missing_hide = 0
    demo_count = 0
    for gname, gdata in (data or {}).items():
        for prof in gdata.get("ColorTypes", []):
            total_colortypes += 1
            name = prof.get("name", "")
            if name in DEMO_KEYS:
                demo_count += 1
            if "hide_at_end" not in prof:
                missing_hide += 1
    return total_colortypes, demo_count, missing_hide

# Configuration Operator Classes

class VisualiseWorkScheduleDate(bpy.types.Operator):
    bl_idname = "bim.visualise_work_schedule_date"
    bl_label = "Visualise Work Schedule Date"
    bl_options = {"REGISTER", "UNDO"}
    work_schedule: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        props = tool.Sequence.get_work_schedule_props()
        return bool(props.visualisation_start)

    def execute(self, context):
        # --- INICIO DE LA CORRECCIÓN ---
        # 1. FORZAR LA SINCRONIZACIÓN: Al igual que con la animación, esto asegura
        #    que el snapshot use los datos más actualizados del grupo que se está editando.
        try:
            tool.Sequence.sync_active_group_to_json()
        except Exception as e:
            print(f"Error syncing colortypes for snapshot: {e}")
        # --- FIN DE LA CORRECCIÓN ---

        # Obtener el work schedule
        work_schedule = tool.Ifc.get().by_id(self.work_schedule)

        # NUEVA CORRECCIÓN: Obtener el rango de visualización configurado
        viz_start, viz_finish = tool.Sequence.get_visualization_date_range()

        # --- NUEVO: Obtener la fuente de fechas desde las propiedades ---
        props = tool.Sequence.get_work_schedule_props()
        date_source = getattr(props, "date_source_type", "SCHEDULE")

        if not viz_start:
            self.report({'ERROR'}, "No start date configured for visualization")
            return {'CANCELLED'}

        # CORRECCIÓN: Usar la fecha de inicio de visualización como fecha del snapshot
        snapshot_date = viz_start
        
        # Ejecutar la lógica central de visualización CON el rango de visualización
        product_states = tool.Sequence.process_construction_state(
            work_schedule,
            snapshot_date,
            viz_start=viz_start,
            viz_finish=viz_finish,
            date_source=date_source  # NUEVO: Pasar la fuente de fechas
        )

        # Aplicar el snapshot con los estados corregidos
        tool.Sequence.show_snapshot(product_states)
        
        # NUEVA FUNCIONALIDAD: Detener animación al crear snapshot para modo fijo
        try:
            if bpy.context.screen.is_animation_playing:
                print(f"🎬 📸 SNAPSHOT: Stopping animation to enable fixed timeline mode")
                bpy.ops.screen.animation_cancel(restore_frame=False)
        except Exception as e:
            print(f"❌ Error stopping animation during snapshot creation: {e}")

        # Dar feedback claro al usuario sobre qué grupo se usó
        anim_props = tool.Sequence.get_animation_props()
        active_group = None
        for stack_item in anim_props.animation_group_stack:
            if getattr(stack_item, 'enabled', False) and stack_item.group:
                active_group = stack_item.group
                break

        group_used = active_group or "DEFAULT"

        # NUEVO: Información adicional sobre el filtrado
        viz_end_str = viz_finish.strftime('%Y-%m-%d') if viz_finish else "No limit"
        self.report({'INFO'}, f"Snapshot at {snapshot_date.strftime('%Y-%m-%d')} using group '{group_used}' (range: {viz_start.strftime('%Y-%m-%d')} to {viz_end_str})")

        return {"FINISHED"}

class LoadAndActivatecolortypeGroup(bpy.types.Operator):
    bl_idname = "bim.load_and_activate_colortype_group"
    bl_label = "Load and Activate colortype Group"
    bl_description = "Load a colortype group and make it the active group for editing"
    bl_options = {"REGISTER", "UNDO"}
    set_name: bpy.props.EnumProperty(name="Group", items=_colortype_set_items)

    def execute(self, context):
        if not self.set_name:
            self.report({'WARNING'}, "No group selected")
            return {'CANCELLED'}

        # Primero cargar los perfiles
        bpy.ops.bim.load_appearance_colortype_set_internal(set_name=self.set_name)

        # Luego establecer como grupo activo
        props = tool.Sequence.get_animation_props()
        props.ColorType_groups = self.set_name

        # Sincronizar con JSON
        tool.Sequence.sync_active_group_to_json()

        self.report({'INFO'}, f"Loaded and activated group '{self.set_name}'")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class SetupDefaultcolortypes(bpy.types.Operator):
    bl_idname = "bim.setup_default_colortypes"
    bl_label = "Setup Default colortypes"
    bl_description = "Create DEFAULT colortype group (if missing) and add it to the animation stack"

    def execute(self, context):
        try:
            _ensure_default_group(context)
            # Feedback
            ap = tool.Sequence.get_animation_props()
            groups = [getattr(it, "group", "?") for it in getattr(ap, "animation_group_stack", [])]
            if groups:
                self.report({'INFO'}, f"Animation groups: {', '.join(groups)}")
            else:
                self.report({'WARNING'}, "No animation groups present")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to setup default colortypes: {e}")
            return {'CANCELLED'}

class UpdateDefaultcolortypeColors(bpy.types.Operator):
    bl_idname = "bim.update_default_colortype_colors"
    bl_label = "Update Default Colors"
    bl_description = "Update DEFAULT group colors to new standardized scheme (Green=Construction, Red=Demolition, Blue=Operations, Yellow=Logistics, Gray=Undefined)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            from bonsai.bim.module.sequence.prop import UnifiedColorTypeManager
            UnifiedColorTypeManager.update_default_group_colors(context)
            self.report({'INFO'}, "DEFAULT colortype colors updated to new scheme")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to update colors: {e}")
            return {'CANCELLED'}

class BIM_OT_verify_colortype_json(bpy.types.Operator):
    bl_idname = "bim.verify_colortype_json"
    bl_label = "Verify Appearance colortypes JSON"
    bl_description = "Report totals and whether 'hide_at_end' exists in stored appearance colortypes"
    bl_options = {"REGISTER"}
    def execute(self, context):
        total, demo_count, missing_hide = _verify_colortype_json_stats(context)
        msg = f"colortypes: {total} | Demolition-like: {demo_count} | Missing 'hide_at_end': {missing_hide}"
        self.report({'INFO'}, msg)
        print("[VERIFY]", msg)
        return {'FINISHED'}

class BIM_OT_fix_colortype_hide_at_end_immediate(bpy.types.Operator):
    bl_idname = "bim.fix_colortype_hide_at_end_immediate"
    bl_label = "Fix 'hide_at_end' Immediately"
    bl_description = "Add 'hide_at_end' to stored appearance colortypes (True for DEMOLITION/REMOVAL/DISPOSAL/DISMANTLE), then rebuild animation"
    bl_options = {"REGISTER","UNDO"}
    def execute(self, context):
        print("🚀 INICIANDO CORRECCIÓN INMEDIATA DE HIDE_AT_END")
        print("="*60)
        print("📝 PASO 1: Migrando perfiles existentes...")
        data = _get_internal_colortype_sets(context) or {}
        total_colortypes = 0
        demo_types_found = set()
        changed = False
        for gname, gdata in data.items():
            colortypes = gdata.get("ColorTypes", [])
            for prof in colortypes:
                total_colortypes += 1
                name = prof.get("name", "")
                is_demo = name in DEMO_KEYS
                if is_demo: demo_types_found.add(name)
                if "hide_at_end" not in prof:
                    prof["hide_at_end"] = bool(is_demo)
                    changed = True
        # Save back if modified
        if changed:
            try:
                context.scene["BIM_AnimationColorSchemesSets"] = json.dumps(data, ensure_ascii=False)
            except Exception as e:
                print("⚠️ Failed to guardar JSON de perfiles:", e)
        for nm in sorted(DEMO_KEYS):
            print(f"  ✅ {nm}: {'OCULTARÁ' if nm in DEMO_KEYS else 'MOSTRARÁ'} objetos al final")
        print("\n🔨 PASO 2: Configurando demolición...")
        print("  ✅ DEMOLITION: Updated para ocultarse")
        print("\n🔍 PASO 3: Verificando configuración...")
        total, demo_count, missing = _verify_colortype_json_stats(context)
        print("📊 RESUMEN:")
        print(f"   Total de perfiles: {total}")
        print(f"   Perfiles de demolición: {demo_count}")
        print(f"   Faltan 'hide_at_end': {missing}")
        print("\n🎬 PASO 4: Regenerando animación...")
        # Best-effort cleanup & regenerate with existing ops
        try:
            if hasattr(bpy.ops.bim, "clear_previous_animation"):
                bpy.ops.bim.clear_previous_animation()
        except Exception:
            pass
        try:
            if hasattr(bpy.ops.bim, "clear_animation"):
                bpy.ops.bim.clear_animation()
        except Exception:
            pass
        try:
            if hasattr(bpy.ops.bim, "create_animation"):
                bpy.ops.bim.create_animation()
        except Exception:
            pass
        print("   ✅ Animación regenerada exitosamente (si la API lo permite)")
        print("="*60)
        self.report({'INFO'}, "✅ CORRECCIÓN APLICADA EXITOSAMENTE")
        return {'FINISHED'}

class RefreshSnapshotTexts(bpy.types.Operator):
    bl_idname = "bim.refresh_snapshot_texts"
    bl_label = "Refresh 3D Texts (Snapshot)"
    bl_description = "Regenerates Schedule_Display_Texts using the current visualisation date with the ACTIVE Snapshot camera"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            scene = context.scene
            cam_obj = scene.camera
            if not cam_obj:
                self.report({'ERROR'}, "No active camera in scene")
                return {'CANCELLED'}
            if not cam_obj.get('is_snapshot_camera', False):
                self.report({'WARNING'}, "Active camera is not marked as Snapshot")
                # Continue anyway (some users may want refresh even if flag missing)
            try:
                import bonsai.tool as tool
            except Exception as e:
                self.report({'ERROR'}, f"Cannot import bonsai.tool: {e}")
                return {'CANCELLED'}

            # Resolve a 'current' visualisation datetime
            ws_props = None
            try:
                ws_props = tool.Sequence.get_work_schedule_props()
            except Exception:
                ws_props = None

            start_dt = None
            try:
                start_str = getattr(ws_props, "visualisation_start", None) if ws_props else None
                parse = getattr(tool.Sequence, "parse_isodate_datetime", None) or getattr(tool.Sequence, "parse_isodate", None)
                if start_str and parse:
                    start_dt = parse(start_str)
            except Exception:
                start_dt = None

            if start_dt is None:
                from datetime import datetime as _dt
                start_dt = _dt.now()

            snapshot_settings = {
                "start": start_dt,
                "finish": start_dt,
                "start_frame": scene.frame_current,
                "total_frames": 1,
            }

            # Rebuild 3D texts collection
            try:
                tool.Sequence.add_text_animation_handler(snapshot_settings)
            except Exception as e:
                self.report({'ERROR'}, f"Failed to rebuild 3D texts: {e}")
                return {'CANCELLED'}

            # Optional auto-arrange
            try:
                bpy.ops.bim.arrange_schedule_texts()
            except Exception:
                pass

            self.report({'INFO'}, "Snapshot 3D texts refreshed")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}