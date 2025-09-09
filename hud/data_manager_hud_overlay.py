# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2021-2022 Yassine Oualid <yassine@sigmadimensions.com>
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


import bpy
from datetime import datetime
import ifcopenshell.util.sequence


class DataManager:
    """Manages HUD data retrieval and settings"""
    
    def __init__(self):
        pass




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

            # --- CHECK FOR SNAPSHOT MODE ---
            # Detect snapshot mode to auto-enable Timeline HUD
            work_props = tool.Sequence.get_work_schedule_props()
            snapshot_date = getattr(work_props, 'visualisation_start', None)
            is_snapshot_ui_active = getattr(work_props, 'should_show_snapshot_ui', False)
            scene_snapshot_mode = hasattr(bpy.context.scene, 'get') and bpy.context.scene.get("is_snapshot_mode", False)
            
            is_snapshot_mode_active = (
                is_snapshot_ui_active and
                snapshot_date and snapshot_date.strip() not in ('', '-')
            ) or scene_snapshot_mode
            
            print(f"🔍 SNAPSHOT DETECTION: is_snapshot_ui_active={is_snapshot_ui_active}, scene_snapshot_mode={scene_snapshot_mode}")
            print(f"🔍 SNAPSHOT DETECTION: snapshot_date='{snapshot_date}', is_snapshot_mode_active={is_snapshot_mode_active}")
            
            # --- TIMELINE HUD SETTINGS (NEW) ---
            # Enable Timeline HUD automatically for snapshots (following v90 behavior)
            timeline_enabled_setting = getattr(camera_props, 'enable_timeline_hud', False)
                
            timeline_hud_settings = {
                'enabled': timeline_enabled_setting,
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


# Global instance for easy access
_data_manager = DataManager()

# Convenience functions for backwards compatibility
def get_schedule_data():
    """Global function to get schedule data"""
    return _data_manager.get_schedule_data()

def get_hud_settings():
    """Global function to get HUD settings"""
    return _data_manager.get_hud_settings()

def get_camera_props():
    """Global function to get camera properties"""
    return _data_manager.get_camera_props()

def get_unified_schedule_range(work_schedule):
    """Global function to get unified schedule range"""
    return _data_manager.get_unified_schedule_range(work_schedule)
