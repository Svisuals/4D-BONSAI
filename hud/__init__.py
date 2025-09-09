# Bonsai - OpenBIM Blender Add-on
# HUD System - Unified HUD interface
# Copyright (C) 2024

import bpy
import locale
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json

from .drawing import HUDDrawing
from .elements import TextHUD, TimelineHUD, LegendHUD


class ScheduleHUD:
    """Enhanced HUD system to display schedule information"""

    def __init__(self):
        # Initialize drawing system
        self.drawing = HUDDrawing()
        
        # Initialize HUD elements
        self.text_hud = TextHUD(self.drawing)
        self.timeline_hud = TimelineHUD(self.drawing)
        self.legend_hud = LegendHUD(self.drawing)
        
        # HUD configuration
        self.font_size = 16
        self.margin = 20
        self.line_height = 25
        
        # Default values (overridden by get_hud_settings)
        self.text_color = (1.0, 1.0, 1.0, 1.0)
        self.background_color = (0.0, 0.0, 0.0, 0.5)
        self.text_shadow_enabled = True
        self.text_shadow_offset = (1.0, -1.0)
        self.text_shadow_color = (0.0, 0.0, 0.0, 0.8)
        
        print(f"🎬 ScheduleHUD.__init__: font_id inicializado como {self.drawing.font_id}")

    @property
    def font_id(self):
        """Access to drawing system font_id for backward compatibility"""
        return self.drawing.font_id

    def ensure_valid_font(self):
        """Delegate to drawing system"""
        self.drawing.ensure_valid_font()
    
    def invalidate_legend_cache(self):
        """Invalidate legend cache"""
        self.legend_hud.invalidate_legend_cache()

    def get_unified_schedule_range(self, work_schedule):
        """
        Calculate the unified date range by analyzing ALL 4 schedule types
        Returns the earliest start and latest finish across all types
        Used for Timeline HUD snapshots and unified timeline display
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
    
    def _is_unified_range(self, work_schedule, viz_start, viz_finish):
        """
        Check if the current visualization range spans multiple schedule types,
        which indicates it's a unified range set by Guess button.
        """
        try:
            # Get the unified range
            unified_start, unified_end = self.get_unified_schedule_range(work_schedule)
            
            if not unified_start or not unified_end:
                return False
            
            # Check if viz range is approximately the same as unified range
            # (allowing for small differences due to time formatting)
            start_match = abs((viz_start - unified_start).total_seconds()) < 86400  # 1 day tolerance
            end_match = abs((viz_finish - unified_end).total_seconds()) < 86400
            
            return start_match and end_match
            
        except Exception as e:
            print(f"⚠️ Error checking unified range: {e}")
            return False
    
    def calculate_position(self, viewport_width, viewport_height, settings):
        """Calculate HUD position in pixels"""
        margin_h = int(viewport_width * settings.get('margin_h', 0.05))
        margin_v = int(viewport_height * settings.get('margin_v', 0.05))

        position = settings.get('position', 'TOP_LEFT')

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
        """Format HUD text lines"""
        if not data:
            return ["No Schedule Data"]

        lines = [
            f"{data['current_date'].strftime('%d %B %Y')}",
            f"Week {data['week_number']}",
            f"Day {data['elapsed_days']}",
            f"Progress: {data['progress_pct']}%",
        ]

        return lines

    def get_camera_props(self):
        """Get camera properties for HUD configuration"""
        try:
            import bonsai.tool as tool
            anim_props = tool.Sequence.get_animation_props()
            return anim_props.camera_orbit
        except Exception as e:
            print(f"⚠️ Error getting camera props: {e}")
            return None

    def get_schedule_data(self):
        """Extracts data from the current schedule"""
        try:
            import bonsai.tool as tool

            # Obtener propiedades
            work_props = tool.Sequence.get_work_schedule_props()
            anim_props = tool.Sequence.get_animation_props()

            # CRITICAL: Check if synchronization mode is enabled
            # Fechas de visualización (rango seleccionado por usuario)
            viz_start = tool.Sequence.get_start_date()
            viz_finish = tool.Sequence.get_finish_date()
            print(f"📅 HUD: Using visualization range: {viz_start} to {viz_finish}")
            
            # Check if we should use unified timeline
            # This happens when user has used Guess to set a unified date range
            full_schedule_start, full_schedule_end = None, None
            try:
                active_schedule = tool.Sequence.get_active_work_schedule()
                print(f"🔍 Active schedule: {active_schedule.Name if active_schedule else 'NONE'}")
                
                if active_schedule:
                    # Check if current viz range spans multiple schedule types (indicates unified range)
                    if viz_start and viz_finish and self._is_unified_range(active_schedule, viz_start, viz_finish):
                        print("🔗 HUD: Detected unified range - using for timeline display")
                        full_schedule_start, full_schedule_end = viz_start, viz_finish
                    else:
                        print("📅 HUD: Using specific schedule type range")
                        full_schedule_start, full_schedule_end = tool.Sequence.get_schedule_date_range()
                    
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
            # Usar múltiples fuentes para determinar el modo snapshot de forma fiable
            snapshot_date = getattr(work_props, 'visualisation_start', None)
            is_snapshot_ui_active = getattr(work_props, 'should_show_snapshot_ui', False)
            is_snapshot_flag_active = bpy.context.scene.get("is_snapshot_mode", False)
            
            is_snapshot_mode = (
                (is_snapshot_ui_active and snapshot_date and snapshot_date.strip() not in ('', '-')) or
                is_snapshot_flag_active
            )
            
            if is_snapshot_mode:
                print(f"🎬 SNAPSHOT MODE: Using date {snapshot_date}")
            else:
                print(f"🎞️ ANIMATION MODE: Range {viz_start} to {viz_finish}")
                
            # NEW: Snapshot support - use specific date
            if is_snapshot_mode:
                # En modo Snapshot, usar SIEMPRE el rango unificado para Timeline HUD
                if snapshot_date and snapshot_date.strip() not in ('', '-'):
                    try:
                        from datetime import datetime
                        current_date = datetime.fromisoformat(snapshot_date.replace('Z', '+00:00'))
                        
                        # CRITICAL: For snapshots, ALWAYS use unified range for Timeline HUD
                        if active_schedule:
                            unified_start, unified_end = self.get_unified_schedule_range(active_schedule)
                            if unified_start and unified_end:
                                print(f"📊 SNAPSHOT: Using unified range {unified_start.strftime('%Y-%m-%d')} → {unified_end.strftime('%Y-%m-%d')}")
                                full_schedule_start, full_schedule_end = unified_start, unified_end
                            else:
                                print("⚠️ SNAPSHOT: No unified range found, using fallback")
                        
                        if full_schedule_start and full_schedule_end:
                
                            # Convertir a fechas para cálculos precisos
                            cd_d = current_date.date()
                            fss_d = full_schedule_start.date()
                            fse_d = full_schedule_end.date()

                            delta_days = (cd_d - fss_d).days
                            
                            if cd_d < fss_d:
                                day_from_schedule = 0
                                week_number = 0
                                progress_pct = 0
                            else:
                                day_from_schedule = max(1, delta_days + 1)
                                week_number = max(1, (delta_days // 7) + 1)
                                total_schedule_days = (fse_d - fss_d).days
                                
                                if delta_days <= 0:
                                    progress_pct = 0
                                elif cd_d >= fse_d or total_schedule_days <= 0:
                                    progress_pct = 100
                                else:
                                    progress_pct = (delta_days / total_schedule_days) * 100
                                    progress_pct = round(progress_pct)

                            total_days_full_schedule = (fse_d - fss_d).days + 1

                            print("🎬 SNAPSHOT MODE: Metrics calculated directly.")
                            return {
                                'full_schedule_start': full_schedule_start,
                                'full_schedule_end': full_schedule_end,
                                'current_date': current_date,
                                'start_date': current_date,
                                'finish_date': current_date,
                                'current_frame': -1,
                                'total_days': total_days_full_schedule,
                                'elapsed_days': day_from_schedule,
                                'week_number': int(max(0, week_number)),
                                'progress_pct': progress_pct,
                                'day_of_week': current_date.strftime('%A'),
                                'schedule_name': active_schedule.Name if active_schedule else 'No Schedule',
                                'is_snapshot': True,
                            }
                        # Fallback: ensure unified range is always available for snapshots
                        if not full_schedule_start or not full_schedule_end:
                            print("⚠️ SNAPSHOT: No unified range found, calculating fallback range")
                            # Use current snapshot date as both start and end if no range is available
                            full_schedule_start = current_date
                            full_schedule_end = current_date
                            
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

            # Get visualization range (user-selected range)
            work_schedule_props = tool.Sequence.get_work_schedule_props()
            viz_start_str = getattr(work_schedule_props, 'visualisation_start', '')
            viz_finish_str = getattr(work_schedule_props, 'visualisation_finish', '')

            viz_start = None
            viz_finish = None
            
            if viz_start_str and viz_finish_str:
                try:
                    from dateutil import parser
                    viz_start = parser.isoparse(viz_start_str)
                    viz_finish = parser.isoparse(viz_finish_str)
                except Exception as e:
                    print(f"⚠️ Error parsing visualization dates: {e}")

            # Get current date
            current_date = None
            
            if is_snapshot:
                # For snapshots, use the snapshot date
                snapshot_date_str = getattr(camera_props, 'snapshot_date', '')
                if snapshot_date_str:
                    try:
                        from dateutil import parser
                        current_date = parser.isoparse(snapshot_date_str)
                    except:
                        current_date = datetime.now().date()
                        current_date = datetime.combine(current_date, datetime.min.time())
                else:
                    current_date = datetime.now().date()
                    current_date = datetime.combine(current_date, datetime.min.time())
            else:
                # For animations, calculate from frame
                current_frame = bpy.context.scene.frame_current
                try:
                    current_date = tool.Sequence.get_frame_date(current_frame)
                except Exception as e:
                    print(f"⚠️ Error getting frame date: {e}")
                    current_date = full_schedule_start

            if not current_date:
                print("❌ Could not determine current date")
                return None

            # Ensure current_date is datetime, not date
            if hasattr(current_date, 'date'):
                pass  # Already datetime
            else:
                current_date = datetime.combine(current_date, datetime.min.time())

            # Calculate progress and time information
            if viz_start and viz_finish:
                # Use visualization range for calculations
                start_for_calc = viz_start
                end_for_calc = viz_finish
            else:
                # Use full schedule range
                start_for_calc = full_schedule_start
                end_for_calc = full_schedule_end

            # Progress calculation
            total_duration = (end_for_calc - start_for_calc).days
            elapsed_duration = max(0, (current_date - start_for_calc).days)
            
            if total_duration > 0:
                progress_pct = min(100, int((elapsed_duration / total_duration) * 100))
            else:
                progress_pct = 0

            # Week calculation
            week_number = current_date.isocalendar()[1]
            elapsed_days = max(1, elapsed_duration + 1)  # +1 because we count from day 1

            # Prepare final data
            data = {
                'schedule_name': getattr(work_schedule, 'Name', 'Unknown Schedule'),
                'current_date': current_date,
                'current_frame': bpy.context.scene.frame_current,
                'week_number': week_number,
                'elapsed_days': elapsed_days,
                'progress_pct': progress_pct,
                'is_snapshot': is_snapshot,
                
                # Date ranges
                'full_schedule_start': full_schedule_start,
                'full_schedule_end': full_schedule_end,
                'viz_start': viz_start,
                'viz_finish': viz_finish,
                'start_date': viz_start or full_schedule_start,  # Fallback compatibility
                'finish_date': viz_finish or full_schedule_end,   # Fallback compatibility
            }

            return data

        except Exception as e:
            print(f"🔴 Error getting schedule data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_hud_settings(self):
        """Get HUD settings from animation properties"""
        try:
            import bonsai.tool as tool
            
            anim_props = tool.Sequence.get_animation_props()
            camera_props = anim_props.camera_orbit
            
            # Text HUD settings
            text_settings = {
                'enabled': getattr(camera_props, 'enable_text_hud', False),
                'position': getattr(camera_props, 'text_hud_position', 'TOP_LEFT'),
                'scale': getattr(camera_props, 'text_hud_scale', 1.0),
                'margin': getattr(camera_props, 'text_hud_margin', 20),
                'background_padding': getattr(camera_props, 'text_hud_background_padding', 10),
                'line_spacing': getattr(camera_props, 'text_hud_line_spacing', 5),
                'corner_radius': getattr(camera_props, 'text_hud_corner_radius', 5),
                
                # Text content options
                'hud_show_date': getattr(camera_props, 'hud_show_date', True),
                'hud_show_week': getattr(camera_props, 'hud_show_week', True),
                'hud_show_day': getattr(camera_props, 'hud_show_day', True),
                'hud_show_progress': getattr(camera_props, 'hud_show_progress', True),
                
                # Colors
                'text_color': tuple(getattr(camera_props, 'text_hud_color', (1.0, 1.0, 1.0, 1.0))),
                'background_color': tuple(getattr(camera_props, 'text_hud_background_color', (0.0, 0.0, 0.0, 0.5))),
                'border_color': tuple(getattr(camera_props, 'text_hud_border_color', (1.0, 1.0, 1.0, 0.3))),
                'border_width': getattr(camera_props, 'text_hud_border_width', 0),
                
                # Text shadow
                'text_shadow_enabled': getattr(camera_props, 'text_shadow_enabled', True),
                'text_shadow_offset_x': getattr(camera_props, 'text_shadow_offset_x', 1.0),
                'text_shadow_offset_y': getattr(camera_props, 'text_shadow_offset_y', -1.0),
                'text_shadow_color': tuple(getattr(camera_props, 'text_shadow_color', (0.0, 0.0, 0.0, 0.8))),
                
                'text_alignment': 'LEFT',
            }
            
            # Timeline HUD settings
            timeline_settings = {
                'enabled': getattr(camera_props, 'enable_timeline_hud', False),
                'timeline_height': getattr(camera_props, 'timeline_height', 30),
                'timeline_margin': getattr(camera_props, 'timeline_margin', 50),
                'timeline_bottom_offset': getattr(camera_props, 'timeline_bottom_offset', 50),
                'show_timeline_labels': getattr(camera_props, 'show_timeline_labels', True),
                
                # Colors
                'timeline_bg_color': tuple(getattr(camera_props, 'timeline_bg_color', (0.2, 0.2, 0.2, 0.8))),
                'timeline_progress_color': tuple(getattr(camera_props, 'timeline_progress_color', (0.3, 0.7, 0.3, 0.9))),
                'timeline_indicator_color': tuple(getattr(camera_props, 'timeline_indicator_color', (1.0, 1.0, 1.0, 1.0))),
                
                # Text properties
                'scale': getattr(camera_props, 'timeline_text_scale', 1.0),
                'text_color': tuple(getattr(camera_props, 'timeline_text_color', (1.0, 1.0, 1.0, 1.0))),
                'text_shadow_enabled': True,
                'text_shadow_color': (0.0, 0.0, 0.0, 0.8),
                'text_shadow_offset_x': 1.0,
                'text_shadow_offset_y': -1.0,
            }
            
            # Legend HUD settings
            legend_settings = {
                'enabled': getattr(camera_props, 'enable_legend_hud', False),
                'legend_position': getattr(camera_props, 'legend_hud_position', 'TOP_RIGHT'),
                'legend_margin': getattr(camera_props, 'legend_hud_margin', 20),
                'legend_padding': getattr(camera_props, 'legend_hud_padding', 10),
                'legend_indicator_size': getattr(camera_props, 'legend_indicator_size', 12),
                'legend_column_spacing': getattr(camera_props, 'legend_column_spacing', 100),
                'legend_row_spacing': getattr(camera_props, 'legend_row_spacing', 20),
                'legend_corner_radius': getattr(camera_props, 'legend_corner_radius', 5),
                
                # Colors
                'legend_bg_color': tuple(getattr(camera_props, 'legend_bg_color', (0.0, 0.0, 0.0, 0.7))),
                
                # Text properties
                'scale': getattr(camera_props, 'legend_text_scale', 1.0),
                'text_color': tuple(getattr(camera_props, 'legend_text_color', (1.0, 1.0, 1.0, 1.0))),
            }
            
            return text_settings, timeline_settings, legend_settings
            
        except Exception as e:
            print(f"🔴 Error getting HUD settings: {e}")
            # Return default settings
            default_text = {
                'enabled': False,
                'position': 'TOP_LEFT',
                'scale': 1.0,
                'margin': 20,
                'text_color': (1.0, 1.0, 1.0, 1.0),
                'background_color': (0.0, 0.0, 0.0, 0.5),
                'text_shadow_enabled': True,
                'text_shadow_color': (0.0, 0.0, 0.0, 0.8),
                'text_shadow_offset_x': 1.0,
                'text_shadow_offset_y': -1.0,
            }
            default_timeline = {'enabled': False}
            default_legend = {'enabled': False}
            
            return default_text, default_timeline, default_legend

    def draw(self):
        """Main HUD drawing function with improved diagnostics"""
        try:
            if not hasattr(bpy.context, 'region') or not bpy.context.region: 
                return
            if not hasattr(bpy.context, 'space_data') or not bpy.context.space_data: 
                return
            if bpy.context.space_data.type != 'VIEW_3D': 
                return

            # Get all HUD settings
            text_settings, timeline_settings, legend_settings = self.get_hud_settings()
            
            print(f"🎯 HUD DRAW: timeline_enabled={timeline_settings.get('enabled', False)}, text_enabled={text_settings.get('enabled', False)}, legend_enabled={legend_settings.get('enabled', False)}")

            # If all are disabled, exit
            if not (text_settings.get('enabled', False) or 
                   timeline_settings.get('enabled', False) or 
                   legend_settings.get('enabled', False)):
                print("❌ HUD DRAW: All HUD elements disabled, exiting")
                return

            data = self.get_schedule_data()
            if not data: 
                return

            region = bpy.context.region
            viewport_width, viewport_height = region.width, region.height

            # Force locale to English for all drawing
            original_locale = locale.getlocale(locale.LC_TIME)
            try:
                try:
                    locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
                except locale.Error:
                    locale.setlocale(locale.LC_TIME, 'C')

                # Draw HUD elements
                if text_settings.get('enabled', False):
                    self.text_hud.draw(data, text_settings, viewport_width, viewport_height)
                
                if timeline_settings.get('enabled', False):
                    self.timeline_hud.draw(data, timeline_settings, viewport_width, viewport_height)
                
                if legend_settings.get('enabled', False):
                    self.legend_hud.draw(data, legend_settings, viewport_width, viewport_height)

            finally:
                # Restore original locale
                try:
                    if original_locale[0]:
                        locale.setlocale(locale.LC_TIME, original_locale)
                except:
                    pass

        except Exception as e:
            print(f"🔴 HUD draw error: {e}")
            import traceback
            traceback.print_exc()

    def draw_static(self):
        """Legacy method - delegates to main draw"""
        self.draw()


# Global instance of the HUD
schedule_hud = ScheduleHUD()

# Export manager functions for backward compatibility
from .manager import (
    register_hud_handler,
    unregister_hud_handler,
    is_hud_enabled,
    ensure_hud_handlers,
    invalidate_legend_hud_cache,
    refresh_hud,
    debug_hud_state
)