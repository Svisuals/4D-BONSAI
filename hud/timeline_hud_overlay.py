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
import gpu
import os
import locale
import blf
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from . import drawing_utils_hud_overlay as draw_utils


class TimelineHUD:

    def __init__(self):
        self.font_id = 0

    def draw(self, data, settings, viewport_width, viewport_height, font_id):
        """Timeline HUD estilo Synchro 4D Pro con una sola barra background"""
        """Synchro 4D Pro style Timeline HUD with a single background bar"""
        print(f"\n🎬 === TIMELINE HUD DRAW START ===")
        print(f"🎬 Viewport: {viewport_width}x{viewport_height}")
        print(f"🎬 Settings enabled: {settings.get('enabled', False)}")
        print(f"🎬 Data received: {list(data.keys()) if data else 'None'}")
        print(f"🎬 Is snapshot: {data.get('is_snapshot', False) if data else 'Unknown'}")
        print(f"🎬 Font ID at start: {font_id}")
        self.font_id = font_id
        
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
            draw_utils.draw_rounded_rect(x_start, y_start, bar_w, int(bar_h), color_background, border_radius)
        else:
            draw_utils.draw_gpu_rect(x_start, y_start, bar_w, int(bar_h), color_background)

        # 1.5. Draw progress bar if enabled
        if settings.get('show_progress_bar', True):
            # FIXED: For snapshots, disable animated progress bar
            if data.get('is_snapshot', False):
                # For snapshots, show static progress bar only if date is within range
                if viz_start <= current_date <= viz_finish:
                    progress_x_end = date_to_x(current_date)
                    progress_width = progress_x_end - x_start
                    if progress_width > 0:
                        draw_utils.draw_gpu_rect(x_start, y_start, int(progress_width), int(bar_h), progress_color)
            else:
                # Normal animated behavior for non-snapshot mode
                if current_date > viz_start:
                    progress_x_end = date_to_x(current_date)
                    progress_width = progress_x_end - x_start
                    
                    if progress_width > 0:
                        draw_utils.draw_gpu_rect(x_start, y_start, int(progress_width), int(bar_h), progress_color)

        # 2. Draw indicator lines and texts
        self.draw_synchro_timeline_marks(x_start, y_start, bar_w, int(bar_h), 
                                       display_start, display_end, zoom_level, color_text, data)

        # 3. Draw current date indicator (vertical line with diamond)
        x_current = date_to_x(current_date)
        draw_utils.draw_current_date_indicator(x_current, y_start, int(bar_h), color_indicator)

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
                            draw_utils.draw_timeline_line(year_x, y_start, bar_h, year_line_color, 2.0)
                            
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
                        draw_utils.draw_timeline_line(month_x, y_start, line_height, month_line_color, 1.5)
                        
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
                            draw_utils.draw_timeline_line(day_x, y_start, line_height, day_line_color, 0.5) # Línea más fina
                            
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

                # Decidimos la altura del texto de la semana según si los días son visibles
                days_are_visible = (zoom_level == 'DETAILED')
                if days_are_visible:
                    y_pos_weeks = y_start + 15  # Posición elevada para no solapar con los días
                else:
                    y_pos_weeks = y_start + 5   # Posición original, más abajo

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
                            draw_utils.draw_timeline_line(week_x, y_start, line_height, week_line_color, 1.0)
                            
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
                                text_y = y_pos_weeks  # Posicionado más abajo para evitar solapamiento con meses
                                
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
                    draw_utils.draw_rounded_rect(x_start, y_start, int(progress_width), bar_h, progress_color, border_radius)
                elif border_radius > 0 and progress_width > border_radius:
                    # If it is partial but wide enough, round only the left side
                    draw_utils.draw_partial_rounded_rect(x_start, y_start, int(progress_width), bar_h, progress_color, border_radius, 'LEFT')
                else:
                    # For small bars or without radius, use a normal rectangle
                    draw_utils.draw_gpu_rect(x_start, y_start, int(progress_width), bar_h, progress_color)
                    
        except Exception as e:
            print(f"Error drawing timeline progress bar: {e}")