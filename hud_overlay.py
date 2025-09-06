# Bonsai - OpenBIM Blender Add-on
# HUD Overlay System for 4D Animation
# Copyright (C) 2024

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from datetime import datetime, timedelta  # noqa: F401  (used by Bonsai tool down the stack)
from dateutil.relativedelta import relativedelta
import json  # noqa: F401
from mathutils import Vector  # noqa: F401
import locale
from math import cos, sin

import os
# Global handler reference
_hud_draw_handler = None
_hud_enabled = False


class ScheduleHUD:
    """Enhanced HUD system to display schedule information"""

    def __init__(self):
        self.font_id = 0
        self.font_size = 16
        self.margin = 20
        self.line_height = 25
        # Valores por defecto (se sobrescriben con get_hud_settings)
        self.text_color = (1.0, 1.0, 1.0, 1.0)
        self.background_color = (0.0, 0.0, 0.0, 0.5)
        self.text_shadow_enabled = True
        self.text_shadow_offset = (1.0, -1.0)
        self.text_shadow_color = (0.0, 0.0, 0.0, 0.8)
        
        # Cache para legend data con invalidación por cambios de grupo
        self._legend_data_cache = None
        self._cached_animation_groups = None
        self._cache_timestamp = 0
        self._last_active_group = None  # Track the last active group to detect changes
        
        # INIT DEBUG: Verify font system
        print(f"🎬 ScheduleHUD.__init__: font_id inicializado como {self.font_id}")
        
        # Try to load explicit font
        self.ensure_valid_font()

    def ensure_valid_font(self):
        """Ensures we have a valid font_id for text rendering"""
        try:
            print(f"🔤 ensure_valid_font: comenzando con font_id={self.font_id}")
            
            # Intentar múltiples métodos de carga de fuente
            font_attempts = [
                # Método 1: Usar font_id 0 (default)
                {"method": "default", "id": 0},
                # Método 2: Cargar fuente del sistema de Blender
                {"method": "blender_default", "path": None},
                # Método 3: Intentar cargar DroidSans
                {"method": "droidsans", "path": "droidsans.ttf"}
            ]
            
            for attempt in font_attempts:
                try:
                    if attempt["method"] == "default":
                        # Probar si font_id 0 funciona
                        test_font_id = 0
                        blf.size(test_font_id, 12)
                        test_dims = blf.dimensions(test_font_id, "TEST")
                        if test_dims[0] > 0 and test_dims[1] > 0:
                            print(f"🔤 ✅ Font ID 0 funciona: dims={test_dims}")
                            self.font_id = test_font_id
                            return
                        else:
                            print(f"🔤 ❌ Font ID 0 no válido: dims={test_dims}")
                    
                    elif attempt["method"] == "blender_default":
                        # Intentar cargar con bpy.data.fonts
                        if hasattr(bpy.data, 'fonts') and len(bpy.data.fonts) > 0:
                            print(f"🔤 Fonts disponibles en Blender: {[f.name for f in bpy.data.fonts]}")
                        
                    elif attempt["method"] == "droidsans":
                        # Intentar cargar DroidSans específicamente
                        datafiles_dir = bpy.utils.system_resource('DATAFILES')
                        font_path = os.path.join(datafiles_dir, "fonts", attempt["path"])
                        if os.path.exists(font_path):
                            loaded_id = blf.load(font_path)
                            if loaded_id != -1:
                                # Verificar que funciona
                                blf.size(loaded_id, 12)
                                test_dims = blf.dimensions(loaded_id, "TEST")
                                if test_dims[0] > 0 and test_dims[1] > 0:
                                    print(f"🔤 ✅ DroidSans cargada desde {font_path}: id={loaded_id}, dims={test_dims}")
                                    self.font_id = loaded_id
                                    return
                                else:
                                    print(f"🔤 ❌ DroidSans cargada pero no funcional: id={loaded_id}")
                            else:
                                print(f"🔤 ❌ No se pudo cargar DroidSans desde {font_path}")
                        else:
                            print(f"🔤 ❌ No se encontró path para DroidSans en {font_path}")
                            
                except Exception as fe:
                    print(f"🔤 ❌ Error en método {attempt['method']}: {fe}")
            
            # Si llegamos aquí, usar font_id 0 como último recurso
            print(f"🔤 ⚠️ Usando font_id 0 como último recurso")
            self.font_id = 0
            
        except Exception as e:
            print(f"🔤 ❌ Error general en ensure_valid_font: {e}")
            self.font_id = 0

    def get_schedule_data(self):
        """Extracts data from the current schedule"""
        try:
            import bonsai.tool as tool

            # Obtener propiedades
            work_props = tool.Sequence.get_work_schedule_props()
            anim_props = tool.Sequence.get_animation_props()

            # CRITICAL: Check if synchronization mode is enabled
            sync_enabled = getattr(anim_props, "auto_update_on_date_source_change", False)
            print(f"🔗 HUD: Synchronization mode {'ENABLED' if sync_enabled else 'DISABLED'}")
            
            # Fechas de visualización (rango seleccionado)
            if sync_enabled:
                # In synchronized mode, use the same unified range for visualization
                # This will be set after we calculate the unified range
                viz_start = None  # Will be set to unified range
                viz_finish = None  # Will be set to unified range
                print("🔗 HUD: Will use unified range for visualization dates")
            else:
                # In independent mode, use the current schedule type's range
                viz_start = tool.Sequence.get_start_date()
                viz_finish = tool.Sequence.get_finish_date()
                print(f"📅 HUD: Using independent visualization range: {viz_start} to {viz_finish}")
            
            # NEW: Get dates from the full active schedule
            full_schedule_start, full_schedule_end = None, None
            try:
                # Verificar si hay un cronograma activo
                active_schedule = tool.Sequence.get_active_work_schedule()
                print(f"🔍 Cronograma activo: {active_schedule.Name if active_schedule else 'NINGUNO'}")
                
                if active_schedule:
                    print(f"🔍 Intentando obtener fechas del cronograma '{active_schedule.Name}'...")
                    
                    # CRITICAL: Use unified range if synchronization is enabled
                    if sync_enabled:
                        print("🔗 HUD: Getting UNIFIED date range (all 4 schedule types)")
                        full_schedule_start, full_schedule_end = self.get_unified_schedule_range(active_schedule)
                        print(f"🔗 HUD: Unified range: {full_schedule_start} to {full_schedule_end}")
                    else:
                        print("📅 HUD: Getting independent range for current schedule type")
                        full_schedule_start, full_schedule_end = tool.Sequence.get_schedule_date_range()
                    
                    print(f"🔍 Resultado: start={full_schedule_start}, end={full_schedule_end}")
                    
                    # CRITICAL: Set visualization dates to unified range if synchronization is enabled
                    if sync_enabled and full_schedule_start and full_schedule_end:
                        viz_start = full_schedule_start
                        viz_finish = full_schedule_end
                        print(f"🔗 HUD: Set visualization dates to unified range: {viz_start.strftime('%Y-%m-%d')} to {viz_finish.strftime('%Y-%m-%d')}")
                    
                    if full_schedule_start and full_schedule_end:
                        print(f"📊 Cronograma completo: {full_schedule_start.strftime('%Y-%m-%d')} → {full_schedule_end.strftime('%Y-%m-%d')}")
                    else:
                        print(f"⚠️ Cronograma activo encontrado pero sin fechas válidas")
                        print(f"🔍 Intentando método alternativo...")
                        
                        # ALTERNATIVE METHOD: Get dates directly from tasks
                        try:
                            import ifcopenshell.util.sequence
                            tasks = ifcopenshell.util.sequence.get_root_tasks(active_schedule)
                            print(f"🔍 Tareas encontradas: {len(tasks) if tasks else 0}")
                            
                            if tasks:
                                all_dates = []
                                for task in tasks:
                                    task_time = getattr(task, 'TaskTime', None)
                                    if task_time:
                                        start = getattr(task_time, 'ScheduleStart', None)
                                        finish = getattr(task_time, 'ScheduleFinish', None)
                                        print(f"🔍 Tarea '{task.Name}': {start} → {finish}")
                                        if start:
                                            all_dates.append(start)
                                        if finish:
                                            all_dates.append(finish)
                                
                                if all_dates:
                                    # Convert strings to datetime if necessary
                                    from datetime import datetime
                                    datetime_dates = []
                                    for date in all_dates:
                                        if isinstance(date, str):
                                            try:
                                                # Parsear ISO format
                                                dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                                                datetime_dates.append(dt)
                                            except:
                                                print(f"❌ Error parseando fecha: {date}")
                                        else:
                                            datetime_dates.append(date)
                                    
                                    if datetime_dates:
                                        full_schedule_start = min(datetime_dates)
                                        full_schedule_end = max(datetime_dates)
                                        print(f"📊 Fechas obtenidas de tareas: {full_schedule_start.strftime('%Y-%m-%d')} → {full_schedule_end.strftime('%Y-%m-%d')}")
                                else:
                                    print(f"❌ No se encontraron fechas en las tareas")
                        except Exception as e:
                            print(f"❌ Error en método alternativo: {e}")
                            import traceback
                            traceback.print_exc()
                else:
                    print(f"⚠️ No hay cronograma activo seleccionado")
                    
            except Exception as e:
                print(f"⚠️ Error obteniendo fechas del cronograma: {e}")
                import traceback
                traceback.print_exc()

            # --- IMPROVED MODE DETECTION LOGIC ---
            # Usar el estado de la UI (should_show_snapshot_ui) para determinar el modo de forma fiable,
            # en lugar de depender de si las fechas de animación están vacías.
            snapshot_date = getattr(work_props, 'visualisation_start', None)
            is_snapshot_ui_active = getattr(work_props, 'should_show_snapshot_ui', False)
            is_snapshot_mode = (
                is_snapshot_ui_active and
                snapshot_date and snapshot_date.strip() not in ('', '-')
            )
            
            if is_snapshot_mode:
                print(f"🎬 SNAPSHOT MODE: Using date {snapshot_date}")
            else:
                print(f"🎞️ ANIMATION MODE: Range {viz_start} to {viz_finish}")
                
            # NEW: Snapshot support - use specific date
            if is_snapshot_mode:
                # En modo Snapshot, ignorar el rango de animación y usar la fecha de snapshot.
                if snapshot_date and snapshot_date.strip() not in ('', '-'):
                    try:
                        from datetime import datetime
                        current_date = datetime.fromisoformat(snapshot_date.replace('Z', '+00:00'))
                        if full_schedule_start and full_schedule_end:
                            from . import operator
                            metrics = operator.calculate_schedule_metrics(
                                current_date, current_date, current_date,
                                full_schedule_start, full_schedule_end
                            )
                            if metrics:
                                print("🎬 SNAPSHOT MODE: Animation disabled for HUD Schedule and Timeline")
                                return {
                                    'full_schedule_start': full_schedule_start,
                                    'full_schedule_end': full_schedule_end, 
                                    'current_date': current_date,
                                    'start_date': current_date,
                                    'finish_date': current_date,
                                    'current_frame': -1,  # FIXED: Disable frame animation for snapshots
                                    'total_days': (full_schedule_end - full_schedule_start).days + 1,
                                    'elapsed_days': metrics['day'],
                                    'week_number': metrics['week'],
                                    'progress_pct': metrics['progress'],
                                    'day_of_week': current_date.strftime('%A'),
                                    'schedule_name': active_schedule.Name if active_schedule else 'No Schedule',
                                    'is_snapshot': True,
                                }
                        # Fallback si no hay métricas o no hay rango completo
                        print("🎬 SNAPSHOT MODE: Animation disabled for HUD Schedule and Timeline (fallback)")
                        return {
                            'full_schedule_start': full_schedule_start,
                            'full_schedule_end': full_schedule_end,
                            'current_date': current_date,
                            'start_date': current_date,
                            'finish_date': current_date,
                            'current_frame': -1,  # FIXED: Disable frame animation for snapshots
                            'total_days': 1,
                            'elapsed_days': 1,
                            'week_number': 1,
                            'progress_pct': 100,
                            'day_of_week': current_date.strftime('%A'),
                            'schedule_name': active_schedule.Name if active_schedule else 'No Schedule',
                            'is_snapshot': True,
                        }
                    except Exception as e:
                        print(f"❌ Error procesando snapshot: {e}")
    
            # --- NORMAL ANIMATION LOGIC (if not snapshot) ---
            scene = bpy.context.scene
            current_frame = scene.frame_current
            start_frame = scene.frame_start
            end_frame = scene.frame_end

            # Calculate current date based on frame (using selected range)
            if end_frame > start_frame and viz_start and viz_finish:
                progress = (current_frame - start_frame) / (end_frame - start_frame)
                progress = max(0.0, min(1.0, progress))

                duration = viz_finish - viz_start
                current_date = viz_start + (duration * progress)
            elif viz_start:
                current_date = viz_start
            else:
                # Fallback: usar fecha actual si no hay fechas de visualización
                from datetime import datetime
                current_date = datetime.now()
                print("⚠️ Sin fechas de visualización configuradas, usando fecha actual")

            # IMPROVED: Calculate metrics using full schedule with EXACT v7 logic
            if full_schedule_start and full_schedule_end:
                print(f"🎯 Calculando métricas con cronograma completo usando lógica v7")
                
                # Convert to dates only for precise calculations (exact v7 logic)
                cd_d = current_date.date()
                fss_d = full_schedule_start.date()
                fse_d = full_schedule_end.date()
                
                # NEW LOGIC: Handle dates before the schedule with 0 values
                delta_days = (cd_d - fss_d).days
                
                if cd_d < fss_d:
                    # Si current_date es anterior al inicio del cronograma: day=0, week=0, progress=0%
                    # If current_date is before the start of the schedule: day=0, week=0, progress=0%
                    day_from_schedule = 0
                    week_number = 0
                    progress_pct = 0  # 0% real, se mostrará internamente como 0.1
                else:
                    # 1. DAY: from the start of the FULL SCHEDULE (starting at 1)
                    day_from_schedule = max(1, delta_days + 1)
                    
                    # 2. WEEK: desde inicio del CRONOGRAMA COMPLETO (comenzando en W1) 
                    week_number = max(1, (delta_days // 7) + 1)
                    
                    # 3. PROGRESS: relativo al CRONOGRAMA COMPLETO [0..100] comenzando en 0%
                    total_schedule_days = (fse_d - fss_d).days
                    
                    if delta_days <= 0:
                        progress_pct = 0  # 0% real
                    elif cd_d >= fse_d or total_schedule_days <= 0:
                        progress_pct = 100
                    else:
                        progress_pct = (delta_days / total_schedule_days) * 100
                        progress_pct = round(progress_pct)
                
                # CORRECTION: Use the values calculated from the full schedule for the display.
                # 'total_days' and 'elapsed_days' now reflect the full schedule.
                total_days_full_schedule = (fse_d - fss_d).days + 1
                
                return {
                    'full_schedule_start': full_schedule_start,
                    'full_schedule_end': full_schedule_end,
                    'current_date': current_date,
                    'start_date': viz_start,
                    'finish_date': viz_finish,
                    'current_frame': current_frame,
                    'total_days': total_days_full_schedule,
                    'elapsed_days': day_from_schedule,
                    'week_number': int(max(0, week_number)),
                    'progress_pct': progress_pct,
                    'day_of_week': current_date.strftime('%A'),
                    'schedule_name': active_schedule.Name if active_schedule else 'No Schedule',
                    'is_snapshot': False, # No es snapshot si llegamos aquí
                }
            else:
                print(f"⚠️ Sin fechas de cronograma completo, usando fallback")

                # FALLBACK: Use logic based only on selected range
                if viz_start and viz_finish:
                    viz_start_d = viz_start.date()
                    viz_finish_d = viz_finish.date()
                    
                    # Calculate total_days and elapsed_days consistently
                    total_days = (viz_finish_d - viz_start_d).days + 1
                    elapsed_days = (current_date - viz_start).days + 1
                    elapsed_days = max(1, min(total_days, elapsed_days))
                else:
                    # Sin fechas de rango, usar valores por defecto
                    total_days = 1
                    elapsed_days = 1
                    print("⚠️ Sin fechas de rango seleccionado, usando valores por defecto")

                # Calculate week_number and progress_pct
                if end_frame > start_frame:
                    frame_progress = (current_frame - start_frame) / (end_frame - start_frame)
                    frame_progress = max(0.0, min(1.0, frame_progress))
                    
                    # WEEK: from the start of the range (starting at W1)
                    # Use elapsed_days for consistency
                    week_number = max(1, ((elapsed_days - 1) // 7) + 1)
                    
                    # PROGRESS: based on frame progress
                    progress_pct = round(frame_progress * 100)
                    progress_pct = max(0, min(100, progress_pct))
                else:
                    # Si no hay animación, estamos en el día 1, semana 1, 0% progreso
                    week_number = 1
                    progress_pct = 0
                
                return {
                    'full_schedule_start': full_schedule_start,
                    'full_schedule_end': full_schedule_end,
                    'current_date': current_date,
                    'start_date': viz_start,
                    'finish_date': viz_finish,
                    'current_frame': current_frame,
                    'total_days': total_days,
                    'elapsed_days': elapsed_days,
                    'week_number': int(max(0, week_number)),
                    'progress_pct': progress_pct,
                    'day_of_week': current_date.strftime('%A'),
                    'schedule_name': active_schedule.Name if active_schedule else 'No Schedule',
                    'is_snapshot': False, # No es snapshot si llegamos aquí
                }
        except Exception as e:
            print(f"Error getting schedule data: {e}")
            import traceback
            traceback.print_exc()
            return None



    def get_unified_schedule_range(self, work_schedule):
        """
        Calculate the unified date range by analyzing ALL 4 schedule types
        Returns the earliest start and latest finish across all types
        Used for Timeline HUD when synchronization is enabled
        """
        from datetime import datetime
        import ifcopenshell.util.sequence
        
        if not work_schedule:
            return None, None
        
        all_starts = []
        all_finishes = []
        
        # Check all schedule types: SCHEDULE, ACTUAL, EARLY, LATE
        for schedule_type in ["SCHEDULE", "ACTUAL", "EARLY", "LATE"]:
            start_attr = f"{schedule_type.capitalize()}Start"
            finish_attr = f"{schedule_type.capitalize()}Finish"
            
            print(f"🔍 UNIFIED HUD: Analyzing {schedule_type} -> {start_attr}/{finish_attr}")
            
            # Get all tasks from schedule
            root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
            
            def get_all_tasks_recursive(tasks):
                result = []
                for task in tasks:
                    result.append(task)
                    nested = ifcopenshell.util.sequence.get_nested_tasks(task)
                    if nested:
                        result.extend(get_all_tasks_recursive(nested))
                return result
            
            all_tasks = get_all_tasks_recursive(root_tasks)
            
            for task in all_tasks:
                start_date = ifcopenshell.util.sequence.derive_date(task, start_attr, is_earliest=True)
                if start_date:
                    all_starts.append(start_date)
                
                finish_date = ifcopenshell.util.sequence.derive_date(task, finish_attr, is_latest=True)
                if finish_date:
                    all_finishes.append(finish_date)
        
        if not all_starts or not all_finishes:
            print("❌ UNIFIED HUD: No valid dates found across all schedule types")
            return None, None
        
        unified_start = min(all_starts)
        unified_finish = max(all_finishes)
        
        print(f"✅ UNIFIED HUD: Timeline range spans {unified_start.strftime('%Y-%m-%d')} to {unified_finish.strftime('%Y-%m-%d')}")
        return unified_start, unified_finish

    def get_hud_settings(self):
        """Gets complete HUD configuration from properties"""
        try:
            import bonsai.tool as tool
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit

            # --- TEXT HUD SETTINGS (EXISTING) ---
            text_hud_settings = {
                'enabled': getattr(camera_props, 'enable_text_hud', False),
                'position': getattr(camera_props, 'hud_position', 'TOP_RIGHT'),
                'margin_h': getattr(camera_props, 'hud_margin_horizontal', 0.05),
                'margin_v': getattr(camera_props, 'hud_margin_vertical', 0.05),
                'spacing': getattr(camera_props, 'hud_text_spacing', 0.08),
                'scale': getattr(camera_props, 'hud_scale_factor', 1.0),
                'text_color': getattr(camera_props, 'hud_text_color', (1.0, 1.0, 1.0, 1.0)),
                'background_color': getattr(camera_props, 'hud_background_color', (0.0, 0.0, 0.0, 0.8)),
                'text_alignment': getattr(camera_props, 'hud_text_alignment', 'LEFT'),
                'padding_h': getattr(camera_props, 'hud_padding_horizontal', 10.0),
                'padding_v': getattr(camera_props, 'hud_padding_vertical', 8.0),
                'border_radius': getattr(camera_props, 'hud_border_radius', 5.0),
                'border_width': getattr(camera_props, 'hud_border_width', 0.0),
                'border_color': getattr(camera_props, 'hud_border_color', (1.0, 1.0, 1.0, 0.5)),
                'text_shadow_enabled': getattr(camera_props, 'hud_text_shadow_enabled', True),
                'text_shadow_offset_x': getattr(camera_props, 'hud_text_shadow_offset_x', 1.0),
                'text_shadow_offset_y': getattr(camera_props, 'hud_text_shadow_offset_y', -1.0),
                'text_shadow_color': getattr(camera_props, 'hud_text_shadow_color', (0.0, 0.0, 0.0, 0.8)),
                'background_shadow_enabled': getattr(camera_props, 'hud_background_shadow_enabled', False),
                'background_shadow_offset_x': getattr(camera_props, 'hud_background_shadow_offset_x', 3.0),
                'background_shadow_offset_y': getattr(camera_props, 'hud_background_shadow_offset_y', -3.0),
                'background_shadow_blur': getattr(camera_props, 'hud_background_shadow_blur', 5.0),
                'background_shadow_color': getattr(camera_props, 'hud_background_shadow_color', (0.0, 0.0, 0.0, 0.6)),
                'font_weight': getattr(camera_props, 'hud_font_weight', 'NORMAL'),
                'letter_spacing': getattr(camera_props, 'hud_letter_spacing', 0.0),
                'background_gradient_enabled': getattr(camera_props, 'hud_background_gradient_enabled', False),
                'background_gradient_color': getattr(camera_props, 'hud_background_gradient_color', (0.1, 0.1, 0.1, 0.9)),
                'gradient_direction': getattr(camera_props, 'hud_gradient_direction', 'VERTICAL'),
                # Flags de visibilidad
                'hud_show_date': getattr(camera_props, 'hud_show_date', True),
                'hud_show_week': getattr(camera_props, 'hud_show_week', True),
                'hud_show_day': getattr(camera_props, 'hud_show_day', True),
                'hud_show_progress': getattr(camera_props, 'hud_show_progress', True),
            }

            # --- TIMELINE HUD SETTINGS (NEW) ---
            timeline_hud_settings = {
                'enabled': getattr(camera_props, 'enable_timeline_hud', False),
                'locked': getattr(camera_props, 'timeline_hud_locked', True),
                'manual_x': getattr(camera_props, 'timeline_hud_manual_x', 0.0),
                'manual_y': getattr(camera_props, 'timeline_hud_manual_y', 0.0),
                'position': getattr(camera_props, 'timeline_hud_position', 'BOTTOM'),
                'margin_h': getattr(camera_props, 'timeline_hud_margin_horizontal', 0.0),
                'margin_v': getattr(camera_props, 'timeline_hud_margin_vertical', 0.05),
                'zoom_level': getattr(camera_props, 'timeline_hud_zoom_level', 'MONTHS'),
                'height': getattr(camera_props, 'timeline_hud_height', 30.0),
                'width': getattr(camera_props, 'timeline_hud_width', 0.8),
                'border_radius': getattr(camera_props, 'timeline_hud_border_radius', 10.0),
                'show_progress_bar': getattr(camera_props, 'timeline_hud_show_progress_bar', True),
                'color_inactive_range': getattr(camera_props, 'timeline_hud_color_inactive_range', (0.588, 0.953, 0.745, 0.3)),
                'color_active_range': getattr(camera_props, 'timeline_hud_color_active_range', (0.588, 0.953, 0.745, 0.5)),
                'color_progress': getattr(camera_props, 'timeline_hud_color_progress', (0.122, 0.663, 0.976, 0.102)),  # #1FA9F91A
            'color_indicator': getattr(camera_props, 'timeline_hud_color_indicator', (1.0, 0.906, 0.204, 1.0)), # #FFE734FF
                'color_text': getattr(camera_props, 'timeline_hud_color_text', (1.0, 1.0, 1.0, 1.0)),
            }
            
            # --- LEGEND HUD SETTINGS (NEW) ---
            legend_hud_settings = {
                'enabled': getattr(camera_props, 'enable_legend_hud', False),
                'position': getattr(camera_props, 'legend_hud_position', 'TOP_LEFT'),
                'margin_h': getattr(camera_props, 'legend_hud_margin_horizontal', 0.05),
                'margin_v': getattr(camera_props, 'legend_hud_margin_vertical', 0.5),
                'orientation': getattr(camera_props, 'legend_hud_orientation', 'VERTICAL'),
                'scale': getattr(camera_props, 'legend_hud_scale', 1.0),
                'background_color': getattr(camera_props, 'legend_hud_background_color', (0.0, 0.0, 0.0, 0.8)),
                'border_radius': getattr(camera_props, 'legend_hud_border_radius', 5.0),
                'padding_h': getattr(camera_props, 'legend_hud_padding_horizontal', 12.0),
                'padding_v': getattr(camera_props, 'legend_hud_padding_vertical', 8.0),
                'item_spacing': getattr(camera_props, 'legend_hud_item_spacing', 8.0),
                'text_color': getattr(camera_props, 'legend_hud_text_color', (1.0, 1.0, 1.0, 1.0)),
                'show_title': getattr(camera_props, 'legend_hud_show_title', True),
                'title_text': getattr(camera_props, 'legend_hud_title_text', 'Legend'),
                'title_color': getattr(camera_props, 'legend_hud_title_color', (1.0, 1.0, 1.0, 1.0)),
                'color_indicator_size': getattr(camera_props, 'legend_hud_color_indicator_size', 12.0),
                'text_shadow_enabled': getattr(camera_props, 'legend_hud_text_shadow_enabled', True),
                'text_shadow_color': getattr(camera_props, 'legend_hud_text_shadow_color', (0.0, 0.0, 0.0, 0.8)),
                'text_shadow_offset_x': getattr(camera_props, 'legend_hud_text_shadow_offset_x', 1.0),
                'text_shadow_offset_y': getattr(camera_props, 'legend_hud_text_shadow_offset_y', -1.0),
                'selected_colortypes': getattr(camera_props, 'legend_hud_selected_colortypes', set()),
                'auto_scale': getattr(camera_props, 'legend_hud_auto_scale', True),
                'max_width': getattr(camera_props, 'legend_hud_max_width', 0.3),  # 30% of viewport width
            }
            
            return text_hud_settings, timeline_hud_settings, legend_hud_settings

        except Exception as e:
            print(f"Error getting HUD settings: {e}")
            return {}, {}, {}
    def calculate_position(self, viewport_width, viewport_height, settings):
        """Calcula la posición del HUD en píxeles"""
        margin_h = int(viewport_width * settings['margin_h'])
        margin_v = int(viewport_height * settings['margin_v'])

        position = settings['position']

        if position == 'TOP_RIGHT':
            x = viewport_width - margin_h
            y = viewport_height - margin_v
            align_x = 'RIGHT'
            align_y = 'TOP'
        elif position == 'TOP_LEFT':
            x = margin_h
            y = viewport_height - margin_v
            align_x = 'LEFT'
            align_y = 'TOP'
        elif position == 'BOTTOM_RIGHT':
            x = viewport_width - margin_h
            y = margin_v
            align_x = 'RIGHT'
            align_y = 'BOTTOM'
        else:  # BOTTOM_LEFT
            x = margin_h
            y = margin_v
            align_x = 'LEFT'
            align_y = 'BOTTOM'

        return x, y, align_x, align_y

    def format_text_lines(self, data):
        """Formats the HUD text lines"""
        if not data:
            return ["No Schedule Data"]

        lines = [
            f"{data['current_date'].strftime('%d %B %Y')}",
            f"Week {data['week_number']} - {data['day_of_week']}",
            f"Day {data['elapsed_days']} of {data['total_days']}",
            f"Progress: {data['progress_pct']}%",
        ]

        return lines

    def draw_background_with_effects(self, x, y, width, height, align_x, align_y, settings):
        """Dibuja fondo con efectos mejorados y coordenadas corregidas.
        `width` y `height` deben ser SOLO del bloque de texto (sin padding)."""
        """Draws background with enhanced effects and corrected coordinates. `width` and `height` should be ONLY for the text block (without padding)."""
        padding_h = settings.get('padding_h', 10.0)
        padding_v = settings.get('padding_v', 8.0)

        # Final width and height including padding
        final_width = width + (padding_h * 2)
        final_height = height + (padding_v * 2)

        # Calculate background position according to alignment
        if align_x == 'RIGHT':
            bg_x = x - final_width
        elif align_x == 'CENTER':
            bg_x = x - (final_width / 2)
        else:  # LEFT
            bg_x = x

        if align_y == 'TOP':
            bg_y = y - final_height
        else:  # BOTTOM
            bg_y = y

        # Draw background shadow if enabled
        if settings.get('background_shadow_enabled', False):
            shadow_offset_x = settings.get('background_shadow_offset_x', 3.0)
            shadow_offset_y = settings.get('background_shadow_offset_y', -3.0)
            shadow_color = settings.get('background_shadow_color', (0.0, 0.0, 0.0, 0.6))

            shadow_vertices = [
                (bg_x + shadow_offset_x, bg_y + shadow_offset_y),
                (bg_x + final_width + shadow_offset_x, bg_y + shadow_offset_y),
                (bg_x + final_width + shadow_offset_x, bg_y + final_height + shadow_offset_y),
                (bg_x + shadow_offset_x, bg_y + final_height + shadow_offset_y),
            ]

            shadow_indices = [(0, 1, 2), (2, 3, 0)]

            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'TRIS', {"pos": shadow_vertices}, indices=shadow_indices)

            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("color", shadow_color)
            batch.draw(shader)

        # Create main background vertices
        vertices = [
            (bg_x, bg_y),
            (bg_x + final_width, bg_y),
            (bg_x + final_width, bg_y + final_height),
            (bg_x, bg_y + final_height),
        ]

        indices = [(0, 1, 2), (2, 3, 0)]

        # Draw background with rounded corners if enabled
        border_radius = settings.get('border_radius', 0.0)
        background_color = settings.get('background_color', (0.0, 0.0, 0.0, 0.8))
        
        if border_radius > 0:
            # Use rounded rectangle
            if settings.get('background_gradient_enabled', False):
                # Para gradientes, usar color promedio como aproximación
                gradient_color = settings.get('background_gradient_color', (0.1, 0.1, 0.1, 0.9))
                avg_color = tuple((c1 + c2) / 2 for c1, c2 in zip(background_color, gradient_color))
                self.draw_rounded_rect(bg_x, bg_y, final_width, final_height, avg_color, border_radius)
            else:
                self.draw_rounded_rect(bg_x, bg_y, final_width, final_height, background_color, border_radius)
        else:
            # Use original method
            if settings.get('background_gradient_enabled', False):
                self.draw_gradient_background(vertices, indices, settings)
            else:
                shader = gpu.shader.from_builtin('UNIFORM_COLOR')
                batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)

                gpu.state.blend_set('ALPHA')
                shader.bind()
                shader.uniform_float("color", background_color)
                batch.draw(shader)

        # Draw border if enabled
        border_width = settings.get('border_width', 0.0)
        if border_width > 0:
            self.draw_border(
                bg_x, bg_y, final_width, final_height, border_width,
                settings.get('border_color', (1.0, 1.0, 1.0, 0.5)),
            )

        gpu.state.blend_set('NONE')

    def draw_gradient_background(self, vertices, indices, settings):
        """Draws a background with a gradient (simplified)"""
        try:
            color1 = settings.get('background_color', (0.0, 0.0, 0.0, 0.8))
            color2 = settings.get('background_gradient_color', (0.1, 0.1, 0.1, 0.9))

            # To simplify, use average color
            avg_color = tuple((c1 + c2) / 2 for c1, c2 in zip(color1, color2))

            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)

            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("color", avg_color)
            batch.draw(shader)
        except Exception as e:
            print(f"Error drawing gradient: {e}")
            # Fallback to solid color
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("color", settings.get('background_color', (0.0, 0.0, 0.0, 0.8)))
            batch.draw(shader)

    def draw_border(self, x, y, width, height, border_width, border_color):
        """Draws a border around the rectangle"""
        try:
            # Border lines
            border_lines = [
                # Top
                [(x, y + height), (x + width, y + height)],
                # Bottom
                [(x, y), (x + width, y)],
                # Left
                [(x, y), (x, y + height)],
                # Right
                [(x + width, y), (x + width, y + height)],
            ]

            gpu.state.blend_set('ALPHA')
            gpu.state.line_width_set(border_width)

            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            for line in border_lines:
                batch = batch_for_shader(shader, 'LINES', {"pos": line})
                shader.bind()
                shader.uniform_float("color", border_color)
                batch.draw(shader)

            gpu.state.line_width_set(1.0)  # Reset line width
        except Exception as e:
            print(f"Error drawing border: {e}")

    def draw_text_with_shadow(self, text, x, y, settings, align_x='LEFT'):
        """Dibuja texto con sombra y alineación mejorada usando baseline correcto"""
        """Draws text with shadow and improved alignment using the correct baseline"""
        # Configure font
        font_size = int(settings.get('scale', 1.0) * 16)
        blf.size(self.font_id, font_size)

        # Calculate text width for alignment
        text_width, text_height = blf.dimensions(self.font_id, text)

        # Adjust X position according to alignment
        text_alignment = settings.get('text_alignment', 'LEFT')
        if text_alignment == 'RIGHT' or align_x == 'RIGHT':
            text_x = x - text_width
        elif text_alignment == 'CENTER' or align_x == 'CENTER':
            text_x = x - (text_width / 2)
        else:  # LEFT
            text_x = x

        # Y comes as baseline
        text_y = y

        # Draw text shadow if enabled
        if settings.get('text_shadow_enabled', True):
            shadow_offset_x = settings.get('text_shadow_offset_x', 1.0)
            shadow_offset_y = settings.get('text_shadow_offset_y', -1.0)
            shadow_color = settings.get('text_shadow_color', (0.0, 0.0, 0.0, 0.8))

            blf.position(self.font_id, text_x + shadow_offset_x, text_y + shadow_offset_y, 0)
            blf.color(self.font_id, *shadow_color)
            blf.draw(self.font_id, text)

        # Draw main text
        text_color = settings.get('text_color', (1.0, 1.0, 1.0, 1.0))
        blf.position(self.font_id, text_x, text_y, 0)
        blf.color(self.font_id, *text_color)
        blf.draw(self.font_id, text)

        return text_width, text_height

    def draw_timeline_hud(self, data, settings, viewport_width, viewport_height):
        """Timeline HUD estilo Synchro 4D Pro con una sola barra background"""
        """Synchro 4D Pro style Timeline HUD with a single background bar"""
        print(f"\n🎬 === TIMELINE HUD DRAW START ===")
        print(f"🎬 Viewport: {viewport_width}x{viewport_height}")
        print(f"🎬 Settings enabled: {settings.get('enabled', False)}")
        print(f"🎬 Font ID at start: {self.font_id}")
        
        # Verificar datos necesarios - CORREGIDO: usar rangos seleccionados
        full_start = data.get('full_schedule_start')
        full_end = data.get('full_schedule_end')
        viz_start = data.get('viz_start') or data.get('start_date')
        viz_finish = data.get('viz_finish') or data.get('finish_date')
        current_date = data.get('current_date')
        
        print(f"🎬 Data keys: {list(data.keys())}")
        print(f"🎬 Timeline data valid: full_start={full_start is not None}, viz_start={viz_start is not None}, current_date={current_date is not None}")

        # DEBUG: Mostrar rangos
        print(f"📅 Timeline HUD Ranges:")
        if full_start and full_end:
            print(f"   Full Schedule: {full_start.strftime('%Y-%m-%d')} → {full_end.strftime('%Y-%m-%d')}")
        if viz_start and viz_finish:
            print(f"   Selected Range: {viz_start.strftime('%Y-%m-%d')} → {viz_finish.strftime('%Y-%m-%d')}")
        if current_date:
            print(f"   Current Date: {current_date.strftime('%Y-%m-%d')}")

        # FIXED: Handle both animation mode (needs viz range) and snapshot mode (needs current_date)
        if data.get('is_snapshot', False):
            # Snapshot mode: only need current_date and schedule range
            if not (current_date and full_start and full_end):
                print("❌ Timeline HUD (Snapshot): Missing current_date or schedule range")
                return
            # For snapshot, use full schedule range as display range
            viz_start = full_start
            viz_finish = full_end
            print(f"🎬 Timeline HUD: Using full schedule range for snapshot")
        else:
            # Animation mode: need viz range and current_date
            if not (viz_start and viz_finish and current_date):
                print("❌ Timeline HUD (Animation): Missing required viz_start, viz_finish or current_date")
                return
        
        # Configuration
        color_background = settings.get('color_inactive_range', (0.2, 0.2, 0.2, 0.8)) # Renombrar a color_background para claridad
        color_text = settings.get('color_text', (1.0, 1.0, 1.0, 1.0))
        color_indicator = settings.get('color_indicator', (1.0, 1.0, 1.0, 1.0))
        progress_color = settings.get('color_progress')
        bar_h = settings.get('height', 40.0)
        border_radius = settings.get('border_radius', 0.0)

        # Viewport geometry and positioning
        margin_v_px = int(viewport_height * settings.get('margin_v', 0.05))
        bar_h = settings.get('height', 40.0)
        bar_w = int(viewport_width * settings.get('width', 0.8))
        
        h_margin_offset = int(viewport_width * settings.get('margin_h', 0.0))
        x_start = ((viewport_width - bar_w) // 2) + h_margin_offset
        y_start = margin_v_px if settings.get('position') == 'BOTTOM' else viewport_height - margin_v_px - bar_h

        # CORRECTION: The timeline display range is NOW the animation range.
        # This makes the background bar and the progress bar always occupy the widget's space.
        display_start = viz_start
        display_end = viz_finish

        duration = (display_end - display_start).total_seconds()
        if duration <= 0:
            return # No dibujar si el rango es inválido

        def date_to_x(date):
            # Clamp date to the display window to avoid extreme values
            date = max(display_start, min(display_end, date))
            progress = (date - display_start).total_seconds() / duration
            return int(x_start + progress * bar_w)

        # Determine the zoom level for the timestamps
        selected_days = (viz_finish - viz_start).days
        if selected_days <= 14:  # <= 2 semanas
            zoom_level = 'DETAILED'
        elif selected_days <= 180:  # <= 6 meses (aprox)
            zoom_level = 'NORMAL'
        elif selected_days <= 730:  # <= 2 años
            zoom_level = 'WIDE'
        else:  # > 2 años
            zoom_level = 'FULL'

        # ====== DRAW ELEMENTS ======
        try:
            gpu.state.blend_set('ALPHA')
        except Exception:
            pass

        # 1. Draw background bar (now occupies the full width of the widget)
        if border_radius > 0:
            self.draw_rounded_rect(x_start, y_start, bar_w, int(bar_h), color_background, border_radius)
        else:
            self.draw_gpu_rect(x_start, y_start, bar_w, int(bar_h), color_background)

        # 1.5. Draw progress bar if enabled
        if settings.get('show_progress_bar', True):
            # FIXED: For snapshots, disable animated progress bar
            if data.get('is_snapshot', False):
                # For snapshots, show static progress bar only if date is within range
                if viz_start <= current_date <= viz_finish:
                    progress_x_end = date_to_x(current_date)
                    progress_width = progress_x_end - x_start
                    if progress_width > 0:
                        self.draw_gpu_rect(x_start, y_start, int(progress_width), int(bar_h), progress_color)
            else:
                # Normal animated behavior for non-snapshot mode
                if current_date > viz_start:
                    progress_x_end = date_to_x(current_date)
                    progress_width = progress_x_end - x_start
                    
                    if progress_width > 0:
                        self.draw_gpu_rect(x_start, y_start, int(progress_width), int(bar_h), progress_color)

        # 2. Draw indicator lines and texts
        self.draw_synchro_timeline_marks(x_start, y_start, bar_w, int(bar_h), 
                                       display_start, display_end, zoom_level, color_text, data)

        # 3. Draw current date indicator (vertical line with diamond)
        x_current = date_to_x(current_date)
        self.draw_current_date_indicator(x_current, y_start, int(bar_h), color_indicator)

        try:
            gpu.state.blend_set('NONE')
        except Exception:
            pass

    def draw_synchro_timeline_marks(self, x_start, y_start, bar_w, bar_h, start_date, end_date, zoom_level, color_text, data=None):
        """Draws Synchro 4D Pro style timestamps with lines and texts"""
        try:
            duration_seconds = (end_date - start_date).total_seconds()
            if duration_seconds <= 0:
                return

            def date_to_x(date):
                progress = (date - start_date).total_seconds() / duration_seconds
                return int(x_start + progress * bar_w)

            # DEEP DIAGNOSTIC: Verify valid font_id
            print(f"🔍 DEEP DEBUG: font_id={self.font_id}, viewport bounds=({x_start}, {y_start}, {bar_w}, {bar_h})")
            
            # Try to load font explicitly if necessary
            if self.font_id == 0:
                try:
                    # Verificar si hay fuentes disponibles
                    font_dir = bpy.utils.system_resource('DATAFILES', "fonts")
                    available_fonts = blf.load(os.path.join(font_dir, "droidsans.ttf"))
                    if available_fonts != -1:
                        self.font_id = available_fonts
                        print(f"🔍 Fuente cargada explícitamente: font_id={self.font_id}")
                    else:
                        print(f"⚠️ No se pudo cargar fuente personalizada, usando font_id=0")
                except Exception as fe:
                    print(f"⚠️ Error cargando fuente: {fe}")
            
            # Configure font with debugging
            print(f"🔍 Configurando fuente: font_id={self.font_id}, color={color_text}")
            blf.size(self.font_id, 10)
            blf.color(self.font_id, *color_text)
            
            # Basic rendering test (only to verify font_id)
            test_text = "TEST"
            test_dims = blf.dimensions(self.font_id, test_text)
            print(f"🔍 Test text '{test_text}' dimensions: {test_dims}")
            # TEST text removido - los años aparecen en su lugar

            # Force locale to English for consistent month names
            original_locale = locale.getlocale(locale.LC_TIME)
            try:
                try:
                    locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
                except locale.Error:
                    locale.setlocale(locale.LC_TIME, 'C')

                # ====== DRAW YEARS WITH CHANGE INDICATORS ======
                current_year = start_date.year
                end_year = end_date.year
                
                print(f"🗓️ Dibujando años desde {current_year} hasta {end_year}")
                print(f"🗓️ Rango de fechas: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")
                print(f"🗓️ Timeline coordinates: x_start={x_start}, bar_w={bar_w}, y_start={y_start}, bar_h={bar_h}")
                
                years_drawn = 0
                # Extend the loop by one year to draw the final marker
                for year in range(current_year, end_year + 2):
                    # Calculate the effective start date of the year within the timeline
                    if year == current_year:
                        # For the first year, use the timeline start date
                        year_effective_start = start_date
                    else:
                        # For subsequent years, use January 1
                        year_effective_start = datetime(year, 1, 1)
                    
                    # Only process if the year appears in the timeline
                    if year_effective_start <= end_date:
                        year_x = date_to_x(year_effective_start)
                        print(f"🗓️ Año {year}: fecha_efectiva={year_effective_start.strftime('%Y-%m-%d')}, x={year_x}")
                        
                        # Check if it is within the visible area
                        if x_start <= year_x <= x_start + bar_w:
                            print(f"🗓️ ✅ Dibujando año {year} en x={year_x}")
                            
                            # Vertical year line (full height)
                            year_line_color = (color_text[0], color_text[1], color_text[2], 0.8)
                            self.draw_timeline_line(year_x, y_start, bar_h, year_line_color, 2.0)
                            
                            # YEAR TEXT with distinctive yellow color
                            year_text = str(year)
                            
                            # Configure font for years (white color like lines and texts)
                            blf.size(self.font_id, 12)
                            year_color = color_text  # Usar el mismo color que otros textos (blanco)
                            blf.color(self.font_id, *year_color)
                            
                            # Text position (just above the bar)
                            text_x = year_x + 4
                            text_y = y_start + bar_h + 4
                            
                            # Renderizar texto de año
                            blf.position(self.font_id, text_x, text_y, 0)
                            blf.draw(self.font_id, year_text)
                            print(f"🗓️ ✅ Año {year} dibujado en ({text_x}, {text_y})")
                            years_drawn += 1
                            
                            # Restore original configuration
                            blf.size(self.font_id, 10)
                            blf.color(self.font_id, *color_text)
                            
                        else:
                            print(f"🗓️ ❌ Año {year} fuera del área visible (x={year_x})")
                    else:
                        print(f"🗓️ Año {year} fuera del rango temporal")
                
                print(f"🗓️ Total años dibujados: {years_drawn}")

                # ====== DRAW MONTHS ======
                current_month = datetime(start_date.year, start_date.month, 1)
                # Extend the loop by one month to ensure the final marker is drawn
                loop_end_month = end_date + relativedelta(months=1)
                
                # Loop until the marker is past the end date's extended boundary
                while current_month <= loop_end_month:
                    month_x = date_to_x(current_month)
                    
                    if x_start <= month_x <= x_start + bar_w:
                        # Vertical month line (3/4 height)
                        line_height = bar_h * 0.75
                        month_line_color = (color_text[0], color_text[1], color_text[2], 0.6)
                        self.draw_timeline_line(month_x, y_start, line_height, month_line_color, 1.5)
                        
                        # Month text (positioned at the top of the bar)
                        month_text = current_month.strftime('%b')  # Jan, Feb, etc.
                        text_dims = blf.dimensions(self.font_id, month_text)
                        text_x = month_x + 4
                        text_y = y_start + bar_h - 18  # Movido más abajo para evitar solapamiento
                        blf.color(self.font_id, color_text[0], color_text[1], color_text[2], color_text[3])
                        blf.position(self.font_id, text_x, text_y, 0)
                        blf.draw(self.font_id, month_text)
                    
                    # Advance to the next month
                    if current_month.month == 12:
                        current_month = datetime(current_month.year + 1, 1, 1)
                    else:
                        current_month = datetime(current_month.year, current_month.month + 1, 1)

                # ====== DIBUJAR DÍAS ======
                # Solo mostrar días si el zoom es muy detallado (e.g., <= 2 semanas)
                if zoom_level == 'DETAILED':
                    current_day_date = start_date
                    day_counter = 0
                    # Extend the loop by one day to ensure the final marker is drawn
                    loop_end_day = end_date + timedelta(days=1)
                    
                    # Use the START date as a reference point for Day 0/1
                    reference_start = data.get('viz_start') or data.get('start_date') or start_date
                    full_start = data.get('full_schedule_start')
                    
                    # If there is a full schedule, use that as a reference for the day counter
                    if full_start and full_start <= reference_start:
                        actual_day_ref = full_start
                    else:
                        actual_day_ref = reference_start

                    # Loop until the marker is past the end date's extended boundary
                    while current_day_date <= loop_end_day:
                        day_x = date_to_x(current_day_date)
                        
                        if x_start <= day_x <= x_start + bar_w:
                            # Vertical day line (1/4 height)
                            line_height = bar_h * 0.25
                            day_line_color = (color_text[0], color_text[1], color_text[2], 0.2) # Color más claro
                            self.draw_timeline_line(day_x, y_start, line_height, day_line_color, 0.5) # Línea más fina
                            
                            # Day text (D + number)
                            delta_days_from_ref = (current_day_date.date() - actual_day_ref.date()).days
                            day_number_display = max(1, delta_days_from_ref + 1) # Días comienzan en 1
                            day_text = f"D{day_number_display}"
                            
                            text_x = day_x + 1
                            text_y = y_start + 2 # Muy abajo en la barra, debajo de las semanas
                            
                            blf.color(self.font_id, color_text[0], color_text[1], color_text[2], color_text[3])
                            blf.position(self.font_id, text_x, text_y, 0)
                            blf.draw(self.font_id, day_text)
                        
                        current_day_date += timedelta(days=1)
                        day_counter += 1

                # ====== DRAW WEEKS (always visible with adaptive logic) ======
                # CORRECTED: Show weeks at all zoom levels but with different frequencies
                duration_days = (end_date - start_date).days
                if duration_days <= 365:  # <= 1 año: mostrar todas las semanas
                    week_interval = 1
                    show_week_text = True
                elif duration_days <= 730:  # <= 2 años: mostrar cada 2 semanas
                    week_interval = 2 
                    show_week_text = True
                else:  # > 2 años: mostrar cada 4 semanas (solo líneas, sin texto)
                    week_interval = 4
                    show_week_text = False

                # NEW APPROACH: Vertical lines that mark EXACTLY the BEGINNINGS of the week
                # based on the configured START date, ALIGNED WITH THE INDICATOR
                
                # Use the START date as a reference point for Week 0/1
                reference_start = data.get('viz_start') or data.get('start_date') or start_date
                full_start = data.get('full_schedule_start') # Usar el full_schedule_start para la referencia de la semana
                
                # CRITICAL: Use full schedule as reference if it exists
                if full_start:
                    actual_start = full_start
                    print(f"🔄 Usando cronograma completo como referencia: {actual_start.strftime('%Y-%m-%d')}")
                else:
                    actual_start = reference_start
                    print(f"🔄 Usando rango seleccionado como referencia: {actual_start.strftime('%Y-%m-%d')}")
                
                # Empezar desde la fecha de START configurada (no desde lunes ISO)
                week_start_date = actual_start
                week_counter = 0
                
                print(f"🔄 Timeline weeks aligned from START date: {week_start_date.strftime('%Y-%m-%d')}")
                
                # Draw vertical lines every 7 days from the START date
                while week_start_date <= end_date:
                    week_x = date_to_x(week_start_date)
                    
                    # --- START OF CORRECTION ---
                    if x_start <= week_x <= x_start + bar_w and week_counter % week_interval == 0:
                        if show_week_text:
                            # Vertical week line ALIGNED with the indicator
                            line_height = bar_h * 0.5
                            week_line_color = (color_text[0], color_text[1], color_text[2], 0.4)
                            self.draw_timeline_line(week_x, y_start, line_height, week_line_color, 1.0)
                            
                            # Week text PERFECTLY ALIGNED with the vertical line
                            if show_week_text:
                                try:
                                    # LÓGICA IDÉNTICA al Viewport HUD para garantizar sincronización perfecta
                                    if full_start:
                                        # Con cronograma completo: usar la MISMA lógica exacta que get_schedule_data()
                                        week_date = week_start_date.date()
                                        fss_d = full_start.date()
                                        
                                        delta_days = (week_date - fss_d).days
                                        if week_date < fss_d:
                                            week_number_display = 0
                                        else:
                                            week_number_display = max(1, (delta_days // 7) + 1)
                                        
                                        week_text = f"W{week_number_display}"
                                        
                                    else:
                                        # Sin cronograma completo: usar rango seleccionado
                                        ref_start_d = reference_start.date()
                                        week_date = week_start_date.date()
                                        
                                        delta_days = (week_date - ref_start_d).days
                                        if week_date < ref_start_d:
                                            week_number_display = 0
                                        else:
                                            week_number_display = max(1, (delta_days // 7) + 1)
                                        
                                        week_text = f"W{week_number_display}"
                                        
                                except Exception as e:
                                    print(f"❌ Error calculando semana sincronizada: {e}")
                                    week_text = f"W{week_counter}"
                                    
                                # POSITION EXACTLY ALIGNED with the vertical line
                                text_x = week_x + 1  # Muy cerca de la línea para alineación perfecta
                                text_y = y_start + 5  # Posicionado más abajo para evitar solapamiento con meses
                                
                                blf.color(self.font_id, color_text[0], color_text[1], color_text[2], color_text[3])
                                blf.position(self.font_id, text_x, text_y, 0)
                                blf.draw(self.font_id, week_text)
                    # --- END OF CORRECTION ---
                    
                    # Next week start date (every 7 days)
                    week_start_date += timedelta(days=7)
                    week_counter += 1

            finally:
                # Restore original locale
                try:
                    locale.setlocale(locale.LC_TIME, original_locale)
                except Exception:
                    pass

        except Exception as e:
            print(f"❌ Error en draw_synchro_timeline_marks: {e}")
            import traceback
            traceback.print_exc()

    def draw_timeline_line(self, x, y, height, color, width=1.0):
        """Draws a vertical line for timeline marks"""
        try:
            vertices = [(x, y), (x, y + height)]
            
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'LINES', {"pos": vertices})
            
            gpu.state.blend_set('ALPHA')
            gpu.state.line_width_set(width)
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
            gpu.state.line_width_set(1.0)  # Reset
        except Exception as e:
            print(f"❌ Error dibujando línea timeline: {e}")

    def draw_current_date_indicator(self, x, y_start, bar_h, color_indicator):
        """Draws the current date indicator with adaptive styles according to position"""
        try:
            line_width = 2.0
            diamond_size = 5

            # 1. Vertical line (from the base to the top of the bar)
            line_vertices = [(x, y_start), (x, y_start + bar_h + 10)]
            
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'LINES', {"pos": line_vertices})
            
            gpu.state.blend_set('ALPHA')
            gpu.state.line_width_set(line_width)
            shader.bind()
            shader.uniform_float("color", color_indicator)
            batch.draw(shader)
            gpu.state.line_width_set(1.0)
            
            # 2. Diamond/Arrow at the top
            diamond_y = y_start + bar_h + 10
            
            diamond_vertices = [
                (x, diamond_y + diamond_size), (x + diamond_size, diamond_y),
                (x, diamond_y - diamond_size), (x - diamond_size, diamond_y)
            ]
            
            diamond_indices = [(0, 1, 2), (2, 3, 0)]
            
            diamond_batch = batch_for_shader(shader, 'TRIS', {"pos": diamond_vertices}, indices=diamond_indices)
            shader.bind()
            shader.uniform_float("color", color_indicator)
            diamond_batch.draw(shader)
            
        except Exception as e:
            print(f"❌ Error dibujando indicador fecha actual: {e}")

    def draw_gpu_rect(self, x, y, w, h, color):
        """Draws a simple rectangle using the GPU module."""
        vertices = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        indices = [(0, 1, 2), (2, 3, 0)]
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.blend_set('NONE')

    def draw_rounded_rect(self, x, y, w, h, color, radius):
        """Draws a rectangle with rounded corners using approximation with multiple triangles."""
        try:
            # Limit the radius to half the smaller dimension
            max_radius = min(w, h) / 2.0
            radius = min(radius, max_radius)
            
            if radius <= 0:
                # If the radius is 0 or negative, draw a normal rectangle
                self.draw_gpu_rect(x, y, w, h, color)
                return
            
            vertices = []
            indices = []
            
            # Number of segments for the rounded corners (more = smoother)
            segments = max(4, int(radius / 2))  # Ajustar según el tamaño del radio
            
            # Center of the rectangle to facilitate calculations
            center_x = x + w / 2
            center_y = y + h / 2
            
            # Crear vértices para un rectángulo redondeado
            # Esquina inferior izquierda
            for i in range(segments + 1):
                angle = 3.14159 + i * (3.14159 / 2) / segments  # 180° a 270°
                vx = x + radius + radius * cos(angle)
                vy = y + radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Esquina inferior derecha
            for i in range(segments + 1):
                angle = 3.14159 * 1.5 + i * (3.14159 / 2) / segments  # 270° a 360°
                vx = x + w - radius + radius * cos(angle)
                vy = y + radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Esquina superior derecha
            for i in range(segments + 1):
                angle = 0 + i * (3.14159 / 2) / segments  # 0° a 90°
                vx = x + w - radius + radius * cos(angle)
                vy = y + h - radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Esquina superior izquierda
            for i in range(segments + 1):
                angle = 3.14159 / 2 + i * (3.14159 / 2) / segments  # 90° a 180°
                vx = x + radius + radius * cos(angle)
                vy = y + h - radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Create triangles using the center as a common point
            center_vertex_index = len(vertices)
            vertices.append((center_x, center_y))
            
            # Connect all perimeter vertices with the center
            total_perimeter_vertices = len(vertices) - 1
            for i in range(total_perimeter_vertices):
                next_i = (i + 1) % total_perimeter_vertices
                indices.append((center_vertex_index, i, next_i))
            
            # Dibujar el rectángulo redondeado
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
            
        except Exception as e:
            print(f"Error drawing rounded rectangle: {e}")
            # Fallback to normal rectangle
            self.draw_gpu_rect(x, y, w, h, color)

    def draw_timeline_progress_bar(self, x_start, y_start, bar_w, bar_h, timeline_start, timeline_end, current_date, progress_color, date_to_x_func, border_radius=0):
        """Draws a progress bar on the timeline that shows the progress up to the current date"""
        try:
            if not (timeline_start and timeline_end and current_date and progress_color):
                return
                
            # Calculate the width of the progress bar up to the current indicator
            if current_date <= timeline_start:
                # Si estamos antes del inicio del timeline, no hay progreso
                progress_width = 0
            elif current_date >= timeline_end:
                # Si estamos después del final del timeline, progreso completo
                progress_width = bar_w
            else:
                # Progreso proporcional desde el inicio del timeline hasta la fecha actual
                x_current = date_to_x_func(current_date)
                x_timeline_start = date_to_x_func(timeline_start)
                progress_width = max(0, x_current - x_timeline_start)
                
            # Only draw if there is progress
            if progress_width > 0:
                if border_radius > 0 and progress_width == bar_w:
                    # If it is the full bar, use rounded corners
                    self.draw_rounded_rect(x_start, y_start, int(progress_width), bar_h, progress_color, border_radius)
                elif border_radius > 0 and progress_width > border_radius:
                    # If it is partial but wide enough, round only the left side
                    self.draw_partial_rounded_rect(x_start, y_start, int(progress_width), bar_h, progress_color, border_radius, 'LEFT')
                else:
                    # For small bars or without radius, use a normal rectangle
                    self.draw_gpu_rect(x_start, y_start, int(progress_width), bar_h, progress_color)
                    
        except Exception as e:
            print(f"Error drawing timeline progress bar: {e}")

    def draw_partial_rounded_rect(self, x, y, w, h, color, radius, rounded_side='LEFT'):
        """Dibuja un rectángulo con esquinas redondeadas solo en un lado"""
        """Draws a rectangle with rounded corners on one side only"""
        try:
            if rounded_side == 'LEFT' and w > radius:
                # Draw left rounded rectangle + right normal rectangle
                left_width = min(radius * 2, w // 2)
                right_width = w - left_width
                
                # Rounded left part (use full rounded rectangle as base)
                self.draw_rounded_rect(x, y, left_width, h, color, radius)
                
                # Rectangular right part (if there is space)
                if right_width > 0:
                    self.draw_gpu_rect(x + left_width, y, right_width, h, color)
            else:
                # Fallback to normal rectangle
                self.draw_gpu_rect(x, y, w, h, color)
                
        except Exception as e:
            print(f"Error drawing partial rounded rectangle: {e}")
            self.draw_gpu_rect(x, y, w, h, color)

    def draw_legend_hud(self, data, settings, viewport_width, viewport_height):
        """Draws the Legend HUD with active animation profiles and their dynamic colors"""
        print(f"\n🎨 === LEGEND HUD DRAW START ===")
        print(f"🎨 Viewport: {viewport_width}x{viewport_height}")
        print(f"🎨 Settings enabled: {settings.get('enabled', False)}")
        
        try:
            # Obtener perfiles activos del sistema de animación
            legend_data = self.get_active_colortype_legend_data()
            if not legend_data:
                print("❌ Legend HUD: No active colortype data available")
                return
            
            print(f"🎨 Legend data: {len(legend_data)} ColorTypes found")
            
            # Configuration
            position = settings.get('position', 'BOTTOM_LEFT')
            margin_h = settings.get('margin_h', 0.05)
            margin_v = settings.get('margin_v', 0.05)
            
            # Calculate base position
            margin_h_px = int(viewport_width * margin_h)
            margin_v_px = int(viewport_height * margin_v)
            
            # Positioning according to configuration
            if '_' in position:
                align_y_str, align_x_str = position.split('_')
            else:
                align_y_str, align_x_str = ('BOTTOM', 'LEFT')

            if align_x_str == 'LEFT':
                base_x = margin_h_px
                align_x = 'LEFT'
            elif align_x_str == 'RIGHT':
                base_x = viewport_width - margin_h_px
                align_x = 'RIGHT'
            else:  # CENTER
                base_x = viewport_width // 2
                align_x = 'CENTER'

            if align_y_str == 'TOP':
                base_y = viewport_height - margin_v_px
                align_y = 'TOP'
            else:  # BOTTOM
                base_y = margin_v_px
                align_y = 'BOTTOM'
            
            # Draw legend elements
            self.draw_legend_elements(
                legend_data, settings, base_x, base_y, align_x, align_y, viewport_width, viewport_height
            )
            
            print("✅ Legend HUD drawn successfully")
            
        except Exception as e:
            print(f"❌ Error drawing legend HUD: {e}")
            import traceback
            traceback.print_exc()

    def get_active_colortype_legend_data(self, include_hidden=False) -> list:
        """Gets the active profile data for the legend with 3 color columns and cache system"""
        try:
            import bonsai.tool as tool
            import time
            
            # Get animation properties
            anim_props = tool.Sequence.get_animation_props()
            if not hasattr(anim_props, 'animation_group_stack') or not anim_props.animation_group_stack:
                print("🎨 No animation group stack found")
                self._legend_data_cache = []
                return []
            
            # Get the current active group to check if anything has changed
            current_active_group = None
            print("🔍 HUD: Checking animation group stack for active group:")
            for i, item in enumerate(anim_props.animation_group_stack):
                enabled = getattr(item, 'enabled', False)
                print(f"  {i}: Group '{item.group}' enabled={enabled}")
                if enabled and current_active_group is None:
                    current_active_group = item.group
                    print(f"🎯 HUD: Selected active group: {current_active_group}")
                    break

            # FALLBACK: If no group is enabled, default to "DEFAULT"
            if current_active_group is None:
                print("❌ HUD: No active group found (no enabled groups)")
                current_active_group = "DEFAULT"
                print("🔄 HUD: Falling back to 'DEFAULT' group.")
            
            # AUTOMATIC DETECTION: If the active group changed, clear hidden profiles
            if self._last_active_group != current_active_group:
                print(f"🔄 AUTO-DETECTION: Active group changed from '{self._last_active_group}' to '{current_active_group}'")
                self._last_active_group = current_active_group
                
                # Auto-clear hidden profiles to show the new active group
                try:
                    camera_props = self.get_camera_props()
                    if camera_props:
                        camera_props.legend_hud_visible_colortypes = ""
                        print("✅ AUTO-CLEARED: legend_hud_visible_colortypes (showing all colortypes from new active group)")
                except Exception as e:
                    print(f"⚠️ Could not auto-clear visible colortypes: {e}")
            
            current_timestamp = time.time()
            
            # Get visibility settings to include in the cache comparison
            camera_props = self.get_camera_props()
            visible_colortypes_str = getattr(camera_props, 'legend_hud_visible_colortypes', '') if camera_props else ''
            
            # The cache depends on the active group, visible profiles and whether we include hidden ones
            cache_key = (current_active_group, visible_colortypes_str, include_hidden)
            
            if (self._legend_data_cache is not None and 
                self._cached_animation_groups == cache_key and 
                current_timestamp - self._cache_timestamp < 1.0):
                return self._legend_data_cache
            
            print(f"🎨 Refreshing legend data cache for active group: {current_active_group} (include_hidden={include_hidden})")
            
            hidden_colortypes = set()
            if not include_hidden:
                if visible_colortypes_str.strip():
                    hidden_colortypes = {p.strip() for p in visible_colortypes_str.split(',') if p.strip()}
            
            legend_data = []
            
            # Use the active group already found during caching
            if not current_active_group:
                print("🎨 No active group found (no enabled groups)")
                self._legend_data_cache = []
                return []
            
            active_group = current_active_group
            print(f"🎨 Found active group (first enabled): {active_group}")
            
            # Only process the found active group
            print(f"🎨 Processing active group: {active_group}")
            
            # Get profiles from this group using UnifiedColorTypeManager
            from .prop import UnifiedColorTypeManager
            
            # SPECIAL CASE: For DEFAULT group in Legend HUD, always ensure full colortype list
            if active_group == "DEFAULT":
                # Force load of all DEFAULT colortypes for legend display
                UnifiedColorTypeManager.ensure_default_group_has_all_predefined_types(bpy.context)
            
            group_colortypes = UnifiedColorTypeManager.get_group_colortypes(bpy.context, active_group)
            
            if not group_colortypes:
                print(f"🎨 No colortypes found for active group {active_group}")
                self._legend_data_cache = []
                return []
            
            # Process each profile of the active group
            for colortype_name, colortype_data in group_colortypes.items():
                if colortype_name in hidden_colortypes:
                    continue
                
                # Get the 3 colors: start, active, end
                start_color = self.get_colortype_color_for_state(colortype_data, 'start')
                active_color = self.get_colortype_color_for_state(colortype_data, 'in_progress') 
                end_color = self.get_colortype_color_for_state(colortype_data, 'end')
                
                legend_entry = {
                    'name': colortype_name,
                    'start_color': start_color,
                    'active_color': active_color,
                    'end_color': end_color,
                    'group': active_group,  # Usar active_group en lugar de group_name
                    'active': True,  # Está en el stack activo
                }
                
                legend_data.append(legend_entry)
                print(f"🎨 Added legend entry: {colortype_name} - Start:{start_color} Active:{active_color} End:{end_color}")
            
            # Update cache
            self._legend_data_cache = legend_data
            self._cached_animation_groups = cache_key
            self._cache_timestamp = current_timestamp
            
            return legend_data
            
        except Exception as e:
            print(f"❌ Error getting active colortype legend data: {e}")
            import traceback
            traceback.print_exc()
            self._legend_data_cache = []
            return []

    def get_colortype_color_for_state(self, colortype_data: dict, state: str) -> tuple:
        """Gets the color of a profile for a specific state (start/in_progress/end)"""
        try:
            # Mapping of states to color fields
            color_field_mapping = {
                'start': 'start_color',
                'in_progress': 'in_progress_color',
                'active': 'in_progress_color',  # Alias
                'end': 'end_color',
                'finished': 'end_color',  # Alias
            }
            
            color_field = color_field_mapping.get(state, 'in_progress_color')
            
            # Get the profile color
            if color_field in colortype_data:
                color = colortype_data[color_field]
                
                # Ensure valid RGBA format
                if isinstance(color, (list, tuple)) and len(color) >= 3:
                    if len(color) == 3:
                        return (*color, 1.0)  # Agregar alpha
                    else:
                        return tuple(color[:4])  # Limitar a RGBA
                        
            # Fallback colors by state
            fallback_colors = {
                'start': (0.8, 0.8, 0.2, 1.0),      # Amarillo
                'in_progress': (0.2, 0.8, 0.2, 1.0), # Verde
                'end': (0.2, 0.2, 0.8, 1.0),         # Azul
            }
            
            return fallback_colors.get(state, (0.7, 0.7, 0.7, 1.0))  # Gris por defecto
            
        except Exception as e:
            print(f"❌ Error getting colortype color for state {state}: {e}")
            return (0.7, 0.7, 0.7, 1.0)  # Color gris por defecto

    def get_camera_props(self) -> bpy.types.PropertyGroup | None:
        """Helper to get camera properties"""
        try:
            import bonsai.tool as tool
            animation_props = tool.Sequence.get_animation_props()
            if hasattr(animation_props, 'camera_orbit') and animation_props.camera_orbit:
                return animation_props.camera_orbit
            return None
        except Exception as e:
            print(f"❌ Error getting camera props: {e}")
            return None

    def invalidate_legend_cache(self):
        """Invalidates the legend data cache to force an update"""
        print("🔄 Invalidating legend cache")
        self._legend_data_cache = None
        self._cached_animation_groups = None
        self._cache_timestamp = 0
        self._last_active_group = None  # Reset group tracking to force detection

    def draw_legend_elements(self, legend_data: list, settings: dict, base_x: float, base_y: float, align_x: str, align_y: str, viewport_width: int, viewport_height: int):
        """Draws the individual legend elements with support for 3 color columns"""
        try:
            if not legend_data:
                return

            camera_props = self.get_camera_props()
            if not camera_props:
                return

            # --- 2. GET VISIBILITY AND STYLE SETTINGS ---
            show_start = getattr(camera_props, 'legend_hud_show_start_column', False)
            show_active = getattr(camera_props, 'legend_hud_show_active_column', True)
            show_end = getattr(camera_props, 'legend_hud_show_end_column', False)
            
            show_start_title = getattr(camera_props, 'legend_hud_show_start_title', False)
            show_active_title = getattr(camera_props, 'legend_hud_show_active_title', True)
            show_end_title = getattr(camera_props, 'legend_hud_show_end_title', False)
            
            scale = settings.get('scale', 1.0)
            font_size = int(14 * scale)
            color_indicator_size = settings.get('color_indicator_size', 12.0) * scale
            item_spacing = settings.get('item_spacing', 8.0) * scale
            column_spacing = getattr(camera_props, 'legend_hud_column_spacing', 16.0) * scale
            padding_h = settings.get('padding_h', 12.0) * scale
            padding_v = settings.get('padding_v', 8.0) * scale
            text_gap = 8 * scale

            orientation = settings.get('orientation', 'VERTICAL')
            auto_scale = getattr(camera_props, 'legend_hud_auto_scale', True)

            # --- 3. CALCULATE CONTENT DIMENSIONS ---
            blf.size(self.font_id, font_size)
            
            colors_width = 0
            num_visible_cols = sum([show_start, show_active, show_end])
            if num_visible_cols > 0:
                colors_width = (num_visible_cols * color_indicator_size) + max(0, num_visible_cols - 1) * column_spacing

            _, row_height = blf.dimensions(self.font_id, "X")

            item_widths = []
            for item in legend_data:
                text_width, _ = blf.dimensions(self.font_id, item['name'])
                item_width = colors_width + text_gap + text_width
                item_widths.append(item_width)

            rows_of_indices = []
            total_content_width = 0

            if orientation == 'VERTICAL':
                rows_of_indices = [[i] for i in range(len(legend_data))]
                if item_widths:
                    total_content_width = max(item_widths)
            else: # HORIZONTAL
                max_width_prop = getattr(camera_props, 'legend_hud_max_width', 0.3)
                max_width_px = viewport_width * max_width_prop

                if legend_data:
                    if auto_scale:
                        # Con auto_scale, poner todos los elementos en una fila para mejor alineación
                        rows_of_indices.append(list(range(len(legend_data))))
                    else:
                        current_row_indices = []
                        current_row_width = 0
                        for i, item_width in enumerate(item_widths):
                            if not current_row_indices or (current_row_width + item_spacing + item_width <= max_width_px):
                                current_row_indices.append(i)
                                current_row_width += item_width
                                if len(current_row_indices) > 1:
                                    current_row_width += item_spacing
                            else:
                                rows_of_indices.append(current_row_indices)
                                current_row_indices = [i]
                                current_row_width = item_width
                        if current_row_indices:
                            rows_of_indices.append(current_row_indices)

                if auto_scale:
                    total_content_width = sum(item_widths) + max(0, len(item_widths) - 1) * item_spacing
                else:
                    max_row_width = 0
                    for row in rows_of_indices:
                        row_width = sum(item_widths[i] for i in row) + max(0, len(row) - 1) * item_spacing
                        max_row_width = max(max_row_width, row_width)
                    total_content_width = max_row_width

            total_content_height = 0
            if settings.get('show_title', True):
                original_font_size = font_size
                title_font_size = getattr(camera_props, 'legend_hud_title_font_size', 16.0) * scale
                blf.size(self.font_id, int(title_font_size))
                _, title_h = blf.dimensions(self.font_id, settings.get('title_text', 'Legend'))
                blf.size(self.font_id, original_font_size) # Restore
                total_content_height += title_h + item_spacing
            
            if any([show_start_title and show_start, show_active_title and show_active, show_end_title and show_end]):
                total_content_height += row_height + item_spacing
            
            total_content_height += len(rows_of_indices) * (row_height + item_spacing)
            if rows_of_indices:
                total_content_height -= item_spacing

            # --- 4. CALCULATE BACKGROUND GEOMETRY AND DRAW ---
            bg_width = total_content_width + 2 * padding_h
            bg_height = total_content_height + 2 * padding_v

            if align_x == 'RIGHT': bg_x = base_x - bg_width
            elif align_x == 'CENTER': bg_x = base_x - bg_width / 2
            else: bg_x = base_x

            if align_y == 'TOP': bg_y = base_y - bg_height
            else: bg_y = base_y

            self.draw_legend_background(bg_x, bg_y, bg_width, bg_height, settings)

            # --- 5. DRAW CONTENT ---
            content_x = bg_x + padding_h
            current_y = bg_y + bg_height - padding_v

            if settings.get('show_title', True):
                original_font_size = font_size
                title_text = settings.get('title_text', 'Legend')
                title_color = settings.get('title_color', (1.0, 1.0, 1.0, 1.0))
                
                # Get and set title font size from settings
                title_font_size = getattr(camera_props, 'legend_hud_title_font_size', 16.0) * scale
                blf.size(self.font_id, int(title_font_size))
                
                # Get dimensions with the correct font size
                title_w, title_h = blf.dimensions(self.font_id, title_text)
                current_y -= title_h
                
                # Correctly center the title using its width
                title_x = content_x + (total_content_width - title_w) / 2
                self.draw_legend_text(title_text, title_x, current_y, title_color, settings)
                current_y -= item_spacing
                
                # Restore font size for items
                blf.size(self.font_id, original_font_size)

            if any([show_start_title and show_start, show_active_title and show_active, show_end_title and show_end]):
                current_y -= row_height
                self.draw_column_titles(content_x, current_y, color_indicator_size, column_spacing,
                                        show_start, show_active, show_end,
                                        show_start_title, show_active_title, show_end_title,
                                        settings)
                current_y -= item_spacing
            
            # --- 6. DRAW PROFILE ROWS (UNIFIED LOGIC) ---
            if rows_of_indices:
                for row_indices in rows_of_indices:
                    current_y -= row_height
                    current_x = content_x
                    
                    if orientation == 'HORIZONTAL':
                        current_row_width = sum(item_widths[i] for i in row_indices) + max(0, len(row_indices) - 1) * item_spacing
                        # Siempre alinear de izquierda a derecha para mejor legibilidad
                        # Solo ajustar posición si no es alineación LEFT (que ya está en content_x)
                        if align_x == 'CENTER': current_x += (total_content_width - current_row_width) / 2
                        elif align_x == 'RIGHT': current_x += total_content_width - current_row_width

                    for item_index in row_indices:
                        self.draw_colortype_row(legend_data[item_index], current_x, current_y, color_indicator_size, column_spacing, show_start, show_active, show_end, settings)
                        if orientation == 'HORIZONTAL': current_x += item_widths[item_index] + item_spacing
                    current_y -= item_spacing

        except Exception as e:
            print(f"❌ Error drawing legend elements: {e}")
            import traceback
            traceback.print_exc()

    def draw_legend_background(self, x: float, y: float, width: float, height: float, settings: dict):
        """Draws the legend background with configurable effects"""
        try:
            background_color = settings.get('background_color', (0.0, 0.0, 0.0, 0.8))
            border_radius = settings.get('border_radius', 5.0)
            
            if border_radius > 0:
                self.draw_rounded_rect(x, y, width, height, background_color, border_radius)
            else:
                self.draw_gpu_rect(x, y, width, height, background_color)
                
        except Exception as e:
            print(f"❌ Error drawing legend background: {e}")

    def draw_legend_text(self, text: str, x: float, y: float, color: tuple, settings: dict):
        """Draws legend text with configurable shadow"""
        try:
            # Draw shadow if enabled
            if settings.get('text_shadow_enabled', True):
                shadow_offset_x = settings.get('text_shadow_offset_x', 1.0)
                shadow_offset_y = settings.get('text_shadow_offset_y', -1.0)
                shadow_color = settings.get('text_shadow_color', (0.0, 0.0, 0.0, 0.8))
                
                blf.position(self.font_id, x + shadow_offset_x, y + shadow_offset_y, 0)
                blf.color(self.font_id, *shadow_color)
                blf.draw(self.font_id, text)
            
            # Draw main text
            blf.position(self.font_id, x, y, 0)
            blf.color(self.font_id, *color)
            blf.draw(self.font_id, text)
            
        except Exception as e:
            print(f"❌ Error drawing legend text: {e}")

    def draw_color_indicator(self, x: float, y: float, size: float, color: tuple):
        """Draws a color indicator circle"""
        try:
            import math
            radius = size / 2.0
            center_x = x + radius
            center_y = y + radius
            segments = 32

            vertices = [(center_x, center_y)]  # Center vertex
            for i in range(segments + 1):
                angle = 2 * math.pi * i / segments
                vx = center_x + radius * math.cos(angle)
                vy = center_y + radius * math.sin(angle)
                vertices.append((vx, vy))

            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})

            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
            gpu.state.blend_set('NONE')

        except Exception as e:
            print(f"❌ Error drawing color indicator: {e}")

    def draw_column_titles(self, base_x: float, y: float, indicator_size: float, column_spacing: float,
                           show_start: bool, show_active: bool, show_end: bool, 
                           show_start_title: bool, show_active_title: bool, show_end_title: bool, settings: dict):
        """Draws the titles of the Start/Active/End columns"""
        try:
            title_color = settings.get('title_color', (1.0, 1.0, 1.0, 1.0))
            current_x = base_x
            
            if show_start and show_start_title:
                text_width, _ = blf.dimensions(self.font_id, "S")
                title_x = current_x + (indicator_size - text_width) / 2
                self.draw_legend_text("S", title_x, y, title_color, settings)
            if show_start:
                current_x += indicator_size + column_spacing
                
            if show_active and show_active_title:
                text_width, _ = blf.dimensions(self.font_id, "A")
                title_x = current_x + (indicator_size - text_width) / 2
                self.draw_legend_text("A", title_x, y, title_color, settings)
            if show_active:
                current_x += indicator_size + column_spacing
                
            if show_end and show_end_title:
                text_width, _ = blf.dimensions(self.font_id, "E")
                title_x = current_x + (indicator_size - text_width) / 2
                self.draw_legend_text("E", title_x, y, title_color, settings)
                
        except Exception as e:
            print(f"❌ Error drawing column titles: {e}")

    def draw_colortype_row(self, legend_item: dict, base_x: float, y: float, indicator_size: float, column_spacing: float,
                         show_start: bool, show_active: bool, show_end: bool, settings: dict):
        """Draws a profile row with its corresponding colors"""
        try:
            current_x = base_x
            text_color = settings.get('text_color', (1.0, 1.0, 1.0, 1.0))
            _, row_height = blf.dimensions(self.font_id, "X")
            
            # Draw color indicators
            if show_start:
                self.draw_color_indicator(current_x, y, indicator_size, legend_item['start_color'])
                current_x += indicator_size + column_spacing
                
            if show_active:
                self.draw_color_indicator(current_x, y, indicator_size, legend_item['active_color'])
                current_x += indicator_size + column_spacing
                
            if show_end:
                self.draw_color_indicator(current_x, y, indicator_size, legend_item['end_color'])
            
            # Calculate X for the text
            text_gap = 8 * settings.get('scale', 1.0)
            num_visible_cols = sum([show_start, show_active, show_end])
            colors_block_width = (num_visible_cols * indicator_size) + max(0, num_visible_cols - 1) * column_spacing
            text_x = base_x + colors_block_width + text_gap
            
            self.draw_legend_text(legend_item['name'], text_x, y, text_color, settings)
            
        except Exception as e:
            print(f"❌ Error drawing colortype row: {e}")


    def draw(self):
        """Main HUD drawing function with improved diagnostics"""
        try:
            if not hasattr(bpy.context, 'region') or not bpy.context.region: return
            if not hasattr(bpy.context, 'space_data') or not bpy.context.space_data: return
            if bpy.context.space_data.type != 'VIEW_3D': return

            # --- GET ALL SETS OF SETTINGS ---
            text_settings, timeline_settings, legend_settings = self.get_hud_settings()

            # If all are disabled, exit
            if not text_settings.get('enabled', False) and not timeline_settings.get('enabled', False) and not legend_settings.get('enabled', False):
                return

            data = self.get_schedule_data()
            if not data: return

            region = bpy.context.region
            viewport_width, viewport_height = region.width, region.height

            # --- Force locale to English for all drawing ---
            original_locale = locale.getlocale(locale.LC_TIME)
            try:
                try:
                    locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
                except locale.Error:
                    locale.setlocale(locale.LC_TIME, 'C')

                # --- 1. DRAW THE TEXT HUD (EXISTING LOGIC) ---
                if text_settings.get('enabled', False):
                    text_base_x, text_base_y, text_align_x, text_align_y = self.calculate_position(viewport_width, viewport_height, text_settings)
                    
                    lines_to_draw = []
                    lines_to_draw.append(f"Schedule: {data.get('schedule_name', 'Unknown')}")
                    if text_settings.get('hud_show_date', True):
                        lines_to_draw.append(f"{data['current_date'].strftime('%d/%m/%Y')}")
                    if text_settings.get('hud_show_week', True):
                        lines_to_draw.append(f"Week {data['week_number']}")
                    if text_settings.get('hud_show_day', True):
                        lines_to_draw.append(f"Day {data['elapsed_days']}")
                    if text_settings.get('hud_show_progress', True):
                        lines_to_draw.append(f"Progress: {data['progress_pct']}%")

                    if lines_to_draw:
                        font_size = int(text_settings.get('scale', 1.0) * 16)
                        blf.size(self.font_id, font_size)
                        
                        line_dims = [blf.dimensions(self.font_id, line) for line in lines_to_draw]
                        max_width = max(w for w, h in line_dims) if line_dims else 0
                        total_text_height = sum(h for w, h in line_dims) + max(0, len(lines_to_draw) - 1) * (text_settings.get('spacing', 0.02) * viewport_height)
                        
                        self.draw_background_with_effects(text_base_x, text_base_y, max_width, total_text_height, text_align_x, text_align_y, text_settings)
                        
                        padding_v = text_settings.get('padding_v', 8.0)
                        if text_align_y == 'TOP':
                            current_y = text_base_y - padding_v - line_dims[0][1]
                        else:
                            current_y = text_base_y + padding_v + total_text_height - line_dims[0][1]

                        padding_h = text_settings.get('padding_h', 10.0)
                        for i, line in enumerate(lines_to_draw):
                            if text_align_x == 'RIGHT':
                                text_x = text_base_x - padding_h
                                self.draw_text_with_shadow(line, text_x, current_y, text_settings, 'RIGHT')
                            else:
                                text_x = text_base_x + padding_h
                                self.draw_text_with_shadow(line, text_x, current_y, text_settings, 'LEFT')
                            
                            if i < len(lines_to_draw) - 1:
                                current_y -= ((text_settings.get('spacing', 0.02) * viewport_height) + line_dims[i + 1][1])

                # --- 2. DRAW THE NEW TIMELINE HUD ---
                if timeline_settings.get('enabled', False):
                    self.draw_timeline_hud(data, timeline_settings, viewport_width, viewport_height)

                # --- 3. DRAW THE NEW LEGEND HUD ---
                if legend_settings.get('enabled', False):
                    self.draw_legend_hud(data, legend_settings, viewport_width, viewport_height)

            finally:
                # --- Restore the original locale ---
                try:
                    locale.setlocale(locale.LC_TIME, original_locale)
                except Exception:
                    pass

        except Exception as e:
            print(f"HUD draw error: {e}")
            import traceback
            traceback.print_exc()

    def draw_static(self):
        """Static drawing method for snapshot mode - prevents animation"""
        try:
            if not hasattr(bpy.context, 'region') or not bpy.context.region: return
            if not hasattr(bpy.context, 'space_data') or not bpy.context.space_data: return
            if bpy.context.space_data.type != 'VIEW_3D': return

            # Get data once and cache it for static display
            data = self.get_schedule_data()
            if not data:
                return

            # Only redraw if this is genuinely a new snapshot (not just frame change)
            current_snapshot_key = (
                data.get('is_snapshot', False),
                data.get('current_date'),
                data.get('schedule_name'),
            )
            
            if hasattr(self, '_last_snapshot_key') and self._last_snapshot_key == current_snapshot_key:
                # Same snapshot data, skip redraw to prevent animation
                return
                
            self._last_snapshot_key = current_snapshot_key
            print(f"🎬 STATIC DRAW: Snapshot at {data.get('current_date')}")
            
            # Get settings
            text_settings, timeline_settings, legend_settings = self.get_hud_settings()
            
            if not text_settings.get('enabled', False) and not timeline_settings.get('enabled', False) and not legend_settings.get('enabled', False):
                return

            # Set viewport info
            viewport_width = bpy.context.region.width
            viewport_height = bpy.context.region.height

            # Draw static HUD elements
            if text_settings.get('enabled', False):
                self.draw_text_hud(data, text_settings, viewport_width, viewport_height)

            if timeline_settings.get('enabled', False):
                self.draw_timeline_hud(data, timeline_settings, viewport_width, viewport_height)

            if legend_settings.get('enabled', False):
                self.draw_legend_hud(data, legend_settings, viewport_width, viewport_height)

        except Exception as e:
            print(f"HUD static draw error: {e}")
            import traceback
            traceback.print_exc()


def draw_hud_callback():
    """Callback that runs every frame to draw the HUD"""
    try:
        # Always use regular draw - snapshot detection is now handled inside get_schedule_data()
        # This ensures proper data flow while preventing animation for snapshots
        schedule_hud.draw()
    except Exception as e:
        print(f"🔴 HUD callback error: {e}")
        import traceback
        traceback.print_exc()


# Global instance of the HUD
schedule_hud = ScheduleHUD()


def register_hud_handler():
    """Registers the HUD drawing handler"""
    global _hud_draw_handler, _hud_enabled

    if _hud_draw_handler is not None:
        unregister_hud_handler()

    try:
        _hud_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_hud_callback, (), 'WINDOW', 'POST_PIXEL'
        )
        _hud_enabled = True
        print("✅ HUD handler registered successfully")

        # Force immediate redraw
        wm = bpy.context.window_manager
        for window in wm.windows:
            screen = window.screen
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

    except Exception as e:
        print(f"🔴 Error registering HUD handler: {e}")
        _hud_enabled = False


def unregister_hud_handler():
    """Unregisters the HUD drawing handler"""
    global _hud_draw_handler, _hud_enabled

    if _hud_draw_handler is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_hud_draw_handler, 'WINDOW')
            print("✅ HUD handler unregistered successfully")
        except Exception as e:
            print(f"🔴 Error removing HUD handler: {e}")
        _hud_draw_handler = None

    _hud_enabled = False


def is_hud_enabled():
    """Checks if the HUD is active"""
    return _hud_enabled


def ensure_hud_handlers():
    """Ensures that all handlers are registered correctly"""
    global _hud_enabled

def invalidate_legend_hud_cache():
    """Función global para invalidar el caché del Legend HUD cuando cambien los grupos de animación"""
    global schedule_hud
    if 'schedule_hud' in globals() and schedule_hud and hasattr(schedule_hud, 'invalidate_legend_cache'):
        schedule_hud.invalidate_legend_cache()
        print("🔄 Legend HUD cache invalidated globally")
    
    # Also update 3D Legend HUD if it exists and is enabled
    try:
        import bonsai.tool as tool
        anim_props = tool.Sequence.get_animation_props()
        camera_props = anim_props.camera_orbit
        
        if getattr(camera_props, 'enable_3d_legend_hud', False):
            # Check if 3D Legend HUD exists
            hud_exists = False
            for obj in bpy.data.objects:
                if obj.get("is_3d_legend_hud", False):
                    hud_exists = True
                    break
            
            if hud_exists:
                print("🔄 Updating 3D Legend HUD due to ColorType change")
                bpy.ops.bim.update_3d_legend_hud()
    except Exception as e:
        print(f"⚠️ Failed to auto-update 3D Legend HUD: {e}")
    
    print(f"🔍 Estado actual: _hud_enabled={_hud_enabled}")
    if not _hud_enabled:
        print("🔧 Registrando handlers del HUD automáticamente...")
        register_hud_handler()
    else:
        print("✅ Handlers ya están activos")


def refresh_hud():
    """Forces a viewport refresh to update the HUD"""
    try:
        wm = bpy.context.window_manager
        for window in wm.windows:
            screen = window.screen
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        print("🔄 HUD refresh requested")
    except Exception as e:
        print(f"🔴 HUD refresh error: {e}")


# 🔧 ADDITIONAL DIAGNOSTIC FUNCTION
def debug_hud_state():
    """Diagnostic function to debug the HUD state"""
    print("\n🔍 === HUD DEBUG STATE ===")
    print(f"Handler enabled: {_hud_enabled}")
    print(f"Handler object: {_hud_draw_handler}")

    try:
        import bonsai.tool as tool
        anim_props = tool.Sequence.get_animation_props()
        camera_props = anim_props.camera_orbit
        hud_enabled = getattr(camera_props, 'enable_text_hud', False)
        print(f"Property enable_text_hud: {hud_enabled}")

        # Verificar datos de cronograma
        data = schedule_hud.get_schedule_data()
        print(f"Schedule data available: {data is not None}")
        if data:
            print(f"  Current date: {data.get('current_date')}")
            print(f"  Frame: {data.get('current_frame')}")

    except Exception as e:
        print(f"Error in debug: {e}")

    print("=== END DEBUG ===\n")