# Bonsai - OpenBIM Blender Add-on
# HUD Elements - High-level HUD component drawing
# Copyright (C) 2024

import bpy
import blf
import locale
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .drawing import HUDDrawing


class TextHUD:
    """Text-based HUD element for displaying schedule information"""
    
    def __init__(self, drawing_system):
        self.drawing = drawing_system
    
    def draw(self, data, settings, viewport_width, viewport_height):
        """Draw text-based HUD element"""
        if not settings.get('enabled', False):
            return
        
        base_x, base_y, align_x, align_y = self.calculate_position(
            viewport_width, viewport_height, settings)
        
        # Prepare text lines
        lines_to_draw = []
        lines_to_draw.append(f"Schedule: {data.get('schedule_name', 'Unknown')}")
        
        if settings.get('hud_show_date', True):
            lines_to_draw.append(f"{data['current_date'].strftime('%d/%m/%Y')}")
        if settings.get('hud_show_week', True):
            lines_to_draw.append(f"Week {data['week_number']}")
        if settings.get('hud_show_day', True):
            lines_to_draw.append(f"Day {data['elapsed_days']}")
        if settings.get('hud_show_progress', True):
            lines_to_draw.append(f"Progress: {data['progress_pct']}%")
        
        if not lines_to_draw:
            return
        
        # Calculate text dimensions
        font_size = int(settings.get('scale', 1.0) * 16)
        blf.size(self.drawing.font_id, font_size)
        
        max_text_width = 0
        total_text_height = 0
        line_dimensions = []
        
        for line in lines_to_draw:
            width, height = blf.dimensions(self.drawing.font_id, line)
            line_dimensions.append((width, height))
            max_text_width = max(max_text_width, width)
            total_text_height += height
        
        # Add margin between lines
        line_spacing = settings.get('line_spacing', 5)
        total_text_height += line_spacing * (len(lines_to_draw) - 1)
        
        # Calculate background dimensions
        bg_padding = settings.get('background_padding', 10)
        bg_width = max_text_width + 2 * bg_padding
        bg_height = total_text_height + 2 * bg_padding
        
        # Calculate final position with alignment
        final_x, final_y = self.apply_alignment(
            base_x, base_y, bg_width, bg_height, align_x, align_y, settings)
        
        # Draw background
        self.draw_background_with_effects(
            final_x, final_y, bg_width, bg_height, align_x, align_y, settings)
        
        # Draw text lines
        current_y = final_y + bg_height - bg_padding
        for i, line in enumerate(lines_to_draw):
            width, height = line_dimensions[i]
            current_y -= height
            
            text_x = final_x + bg_padding
            if align_x == 'RIGHT':
                text_x = final_x + bg_width - bg_padding
            elif align_x == 'CENTER':
                text_x = final_x + bg_width / 2
            
            self.drawing.draw_text_with_shadow(line, text_x, current_y, settings, align_x)
            current_y -= line_spacing
    
    def calculate_position(self, viewport_width, viewport_height, settings):
        """Calculate HUD position based on settings"""
        margin = settings.get('margin', 20)
        position = settings.get('position', 'TOP_LEFT')
        
        if position == 'TOP_LEFT':
            return margin, viewport_height - margin, 'LEFT', 'TOP'
        elif position == 'TOP_RIGHT':
            return viewport_width - margin, viewport_height - margin, 'RIGHT', 'TOP'
        elif position == 'BOTTOM_LEFT':
            return margin, margin, 'LEFT', 'BOTTOM'
        elif position == 'BOTTOM_RIGHT':
            return viewport_width - margin, margin, 'RIGHT', 'BOTTOM'
        elif position == 'CENTER':
            return viewport_width / 2, viewport_height / 2, 'CENTER', 'CENTER'
        else:
            # Default to TOP_LEFT
            return margin, viewport_height - margin, 'LEFT', 'TOP'
    
    def apply_alignment(self, base_x, base_y, width, height, align_x, align_y, settings):
        """Apply alignment to position"""
        final_x = base_x
        final_y = base_y
        
        if align_x == 'RIGHT':
            final_x = base_x - width
        elif align_x == 'CENTER':
            final_x = base_x - width / 2
        
        if align_y == 'TOP':
            final_y = base_y - height
        elif align_y == 'CENTER':
            final_y = base_y - height / 2
        
        return final_x, final_y
    
    def draw_background_with_effects(self, x, y, width, height, align_x, align_y, settings):
        """Draw background with effects"""
        # Get background settings
        bg_color = settings.get('background_color', (0.0, 0.0, 0.0, 0.5))
        border_color = settings.get('border_color')
        border_width = settings.get('border_width', 0)
        corner_radius = settings.get('corner_radius', 5)
        
        # Draw background
        if corner_radius > 0:
            self.drawing.draw_rounded_rect(x, y, width, height, bg_color, corner_radius)
        else:
            self.drawing.draw_gpu_rect(x, y, width, height, bg_color)
        
        # Draw border if enabled
        if border_width > 0 and border_color:
            self.drawing.draw_border(x, y, width, height, border_width, border_color)


class TimelineHUD:
    """Timeline-based HUD element for displaying schedule progress"""
    
    def __init__(self, drawing_system):
        self.drawing = drawing_system
    
    def draw(self, data, settings, viewport_width, viewport_height):
        """Timeline HUD estilo Synchro 4D Pro con una sola barra background"""
        """Synchro 4D Pro style Timeline HUD with a single background bar"""
        print(f"\n🎬 === TIMELINE HUD DRAW START ===")
        print(f"🎬 Viewport: {viewport_width}x{viewport_height}")
        print(f"🎬 Settings enabled: {settings.get('enabled', False)}")
        print(f"🎬 Data received: {list(data.keys()) if data else 'None'}")
        print(f"🎬 Is snapshot: {data.get('is_snapshot', False) if data else 'Unknown'}")
        print(f"🎬 Font ID at start: {self.drawing.font_id}")
        
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
            import gpu
            gpu.state.blend_set('ALPHA')
        except Exception:
            pass

        # 1. Draw background bar (now occupies the full width of the widget)
        if border_radius > 0:
            self.drawing.draw_rounded_rect(x_start, y_start, bar_w, int(bar_h), color_background, border_radius)
        else:
            self.drawing.draw_gpu_rect(x_start, y_start, bar_w, int(bar_h), color_background)

        # 1.5. Draw progress bar if enabled
        if settings.get('show_progress_bar', True):
            # FIXED: For snapshots, disable animated progress bar
            if data.get('is_snapshot', False):
                # For snapshots, show static progress bar only if date is within range
                if viz_start <= current_date <= viz_finish:
                    progress_x_end = date_to_x(current_date)
                    progress_width = progress_x_end - x_start
                    if progress_width > 0:
                        self.drawing.draw_gpu_rect(x_start, y_start, int(progress_width), int(bar_h), progress_color)
            else:
                # Normal animated behavior for non-snapshot mode
                if current_date > viz_start:
                    progress_x_end = date_to_x(current_date)
                    progress_width = progress_x_end - x_start
                    
                    if progress_width > 0:
                        self.drawing.draw_gpu_rect(x_start, y_start, int(progress_width), int(bar_h), progress_color)

        # 2. Draw indicator lines and texts
        self.draw_synchro_timeline_marks(x_start, y_start, bar_w, int(bar_h), 
                                       display_start, display_end, zoom_level, color_text, data)

        # 3. Draw current date indicator (vertical line with diamond)
        x_current = date_to_x(current_date)
        self.drawing.draw_current_date_indicator(x_current, y_start, int(bar_h), color_indicator)

        try:
            gpu.state.blend_set('NONE')
        except Exception:
            pass

    def draw_synchro_timeline_marks(self, x_start, y_start, bar_w, bar_h, start_date, end_date, zoom_level, color_text, data=None):
        """Draws Synchro 4D Pro style timestamps with lines and texts"""
        try:
            import os
            duration_seconds = (end_date - start_date).total_seconds()
            if duration_seconds <= 0:
                return

            def date_to_x(date):
                progress = (date - start_date).total_seconds() / duration_seconds
                return int(x_start + progress * bar_w)

            # DEEP DIAGNOSTIC: Verify valid font_id
            print(f"🔍 DEEP DEBUG: font_id={self.drawing.font_id}, viewport bounds=({x_start}, {y_start}, {bar_w}, {bar_h})")
            
            # Try to load font explicitly if necessary
            if self.drawing.font_id == 0:
                try:
                    # Verificar si hay fuentes disponibles
                    font_dir = bpy.utils.system_resource('DATAFILES', "fonts")
                    available_fonts = blf.load(os.path.join(font_dir, "droidsans.ttf"))
                    if available_fonts != -1:
                        self.drawing.font_id = available_fonts
                        print(f"🔍 Fuente cargada explícitamente: font_id={self.drawing.font_id}")
                    else:
                        print(f"⚠️ No se pudo cargar fuente personalizada, usando font_id=0")
                except Exception as fe:
                    print(f"⚠️ Error cargando fuente: {fe}")
            
            # Configure font with debugging
            print(f"🔍 Configurando fuente: font_id={self.drawing.font_id}, color={color_text}")
            blf.size(self.drawing.font_id, 10)
            blf.color(self.drawing.font_id, *color_text)
            
            # Basic rendering test (only to verify font_id)
            test_text = "TEST"
            test_dims = blf.dimensions(self.drawing.font_id, test_text)
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
                            self.drawing.draw_timeline_line(year_x, y_start, bar_h, year_line_color, 2.0)
                            
                            # YEAR TEXT with distinctive yellow color
                            year_text = str(year)
                            
                            # Configure font for years (white color like lines and texts)
                            blf.size(self.drawing.font_id, 12)
                            year_color = color_text  # Usar el mismo color que otros textos (blanco)
                            blf.color(self.drawing.font_id, *year_color)
                            
                            # Text position (just above the bar)
                            text_x = year_x + 4
                            text_y = y_start + bar_h + 4
                            
                            # Renderizar texto de año
                            blf.position(self.drawing.font_id, text_x, text_y, 0)
                            blf.draw(self.drawing.font_id, year_text)
                            print(f"🗓️ ✅ Año {year} dibujado en ({text_x}, {text_y})")
                            years_drawn += 1
                            
                            # Restore original configuration
                            blf.size(self.drawing.font_id, 10)
                            blf.color(self.drawing.font_id, *color_text)
                            
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
                        self.drawing.draw_timeline_line(month_x, y_start, line_height, month_line_color, 1.5)
                        
                        # Month text (positioned at the top of the bar)
                        month_text = current_month.strftime('%b')  # Jan, Feb, etc.
                        text_dims = blf.dimensions(self.drawing.font_id, month_text)
                        text_x = month_x + 4
                        text_y = y_start + bar_h - 18  # Movido más abajo para evitar solapamiento
                        blf.color(self.drawing.font_id, color_text[0], color_text[1], color_text[2], color_text[3])
                        blf.position(self.drawing.font_id, text_x, text_y, 0)
                        blf.draw(self.drawing.font_id, month_text)
                    
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
                            self.drawing.draw_timeline_line(day_x, y_start, line_height, day_line_color, 0.5) # Línea más fina
                            
                            # Day text (D + number)
                            delta_days_from_ref = (current_day_date.date() - actual_day_ref.date()).days
                            day_number_display = max(1, delta_days_from_ref + 1) # Días comienzan en 1
                            day_text = f"D{day_number_display}"
                            
                            text_x = day_x + 1
                            text_y = y_start + 2 # Muy abajo en la barra, debajo de las semanas
                            
                            blf.color(self.drawing.font_id, color_text[0], color_text[1], color_text[2], color_text[3])
                            blf.position(self.drawing.font_id, text_x, text_y, 0)
                            blf.draw(self.drawing.font_id, day_text)
                        
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
                            self.drawing.draw_timeline_line(week_x, y_start, line_height, week_line_color, 1.0)
                            
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
                                
                                blf.color(self.drawing.font_id, color_text[0], color_text[1], color_text[2], color_text[3])
                                blf.position(self.drawing.font_id, text_x, text_y, 0)
                                blf.draw(self.drawing.font_id, week_text)
                    # --- END OF CORRECTION ---
                    
                    # Next week start date (every 7 days)
                    week_start_date += timedelta(days=7)
                    week_counter += 1

            finally:
                # Restore original locale
                try:
                    if original_locale[0]:
                        locale.setlocale(locale.LC_TIME, original_locale)
                except:
                    pass

        except Exception as e:
            print(f"❌ Error en draw_synchro_timeline_marks: {e}")
            import traceback
            traceback.print_exc()


class LegendHUD:
    """Legend-based HUD element for displaying color coding information"""
    
    def __init__(self, drawing_system):
        self.drawing = drawing_system
        # Cache for legend data
        self._legend_data_cache = None
        self._cache_timestamp = 0
        self._last_active_group = None
    
    def draw(self, data, settings, viewport_width, viewport_height):
        """Draw legend HUD element"""
        if not settings.get('enabled', False):
            return
        
        legend_data = self.get_active_colortype_legend_data()
        if not legend_data:
            return
        
        # Calculate position and dimensions
        base_x, base_y, align_x, align_y = self.calculate_legend_position(
            viewport_width, viewport_height, settings)
        
        # Draw legend elements
        self.draw_legend_elements(
            legend_data, settings, base_x, base_y, align_x, align_y, 
            viewport_width, viewport_height)
    
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
            
            # Enhanced cache key that includes visibility settings
            cache_key = f"{current_active_group}_{visible_colortypes_str}"
            
            # Check if cache is still valid (includes group AND visibility changes)
            if (hasattr(self, '_legend_data_cache') and 
                self._legend_data_cache is not None and 
                hasattr(self, '_cache_timestamp') and 
                current_timestamp - self._cache_timestamp < 2.0 and  # 2-second cache
                hasattr(self, '_cache_key') and 
                self._cache_key == cache_key):
                print("✅ HUD: Using cached legend data")
                return self._legend_data_cache
            
            print(f"🔄 HUD: Rebuilding legend cache for group '{current_active_group}'")
            
            # Get data from the UnifiedColorTypeManager
            from .animation import UnifiedColorTypeManager
            
            all_colortypes = UnifiedColorTypeManager.get_colortype_data_for_group(
                bpy.context, current_active_group
            )
            
            if not all_colortypes:
                print(f"⚠️ No colortypes found for group '{current_active_group}'")
                self._legend_data_cache = []
                self._cache_timestamp = current_timestamp
                self._cache_key = cache_key
                return []
            
            # Filter visible colortypes based on settings
            visible_colortypes_list = []
            if visible_colortypes_str.strip():
                # User has specified which colortypes to show
                visible_colortypes_list = [ct.strip() for ct in visible_colortypes_str.split(',') if ct.strip()]
                print(f"🎯 HUD: Showing only specified colortypes: {visible_colortypes_list}")
            
            legend_items = []
            for colortype_name, colortype_data in all_colortypes.items():
                # Skip if user has specified visible types and this isn't one of them
                if visible_colortypes_list and colortype_name not in visible_colortypes_list:
                    continue
                
                # Skip hidden unless specifically requested
                if not include_hidden and colortype_data.get('is_hidden', False):
                    continue
                
                legend_item = {
                    'name': colortype_name,
                    'color_start': colortype_data.get('color_start', (0.5, 0.5, 0.5, 1.0)),
                    'color_active': colortype_data.get('color_active', (0.7, 0.7, 0.7, 1.0)), 
                    'color_end': colortype_data.get('color_end', (0.9, 0.9, 0.9, 1.0)),
                    'task_count': colortype_data.get('task_count', 0),
                }
                legend_items.append(legend_item)
            
            # Update cache with enhanced key
            self._legend_data_cache = legend_items
            self._cache_timestamp = current_timestamp
            self._cache_key = cache_key
            self._last_active_group = current_active_group
            
            print(f"✅ HUD: Cached {len(legend_items)} legend items for group '{current_active_group}'")
            return legend_items
            
        except Exception as e:
            print(f"❌ Error getting legend data: {e}")
            return []
    
    def get_camera_props(self):
        """Get camera properties for HUD configuration"""
        try:
            import bonsai.tool as tool
            anim_props = tool.Sequence.get_animation_props()
            return anim_props.camera_orbit
        except Exception as e:
            print(f"⚠️ Error getting camera props: {e}")
            return None
    
    def invalidate_legend_cache(self):
        """Invalidate the legend cache"""
        self._legend_data_cache = None
        self._cache_timestamp = 0
        self._last_active_group = None
    
    def calculate_legend_position(self, viewport_width, viewport_height, settings):
        """Calculate legend position based on settings"""
        margin = settings.get('legend_margin', 20)
        position = settings.get('legend_position', 'TOP_RIGHT')
        
        if position == 'TOP_LEFT':
            return margin, viewport_height - margin, 'LEFT', 'TOP'
        elif position == 'TOP_RIGHT':
            return viewport_width - margin, viewport_height - margin, 'RIGHT', 'TOP'
        elif position == 'BOTTOM_LEFT':
            return margin, margin, 'LEFT', 'BOTTOM'
        elif position == 'BOTTOM_RIGHT':
            return viewport_width - margin, margin, 'RIGHT', 'BOTTOM'
        else:
            # Default to TOP_RIGHT
            return viewport_width - margin, viewport_height - margin, 'RIGHT', 'TOP'
    
    def validate_hud_state(self):
        """Comprehensive HUD state validation with detailed diagnostics"""
        validation_results = {
            'status': 'OK',
            'errors': [],
            'warnings': [],
            'info': []
        }
        
        try:
            # Check Blender context
            if not hasattr(bpy.context, 'region') or not bpy.context.region:
                validation_results['errors'].append("No valid Blender region context")
                validation_results['status'] = 'ERROR'
            
            if not hasattr(bpy.context, 'space_data') or not bpy.context.space_data:
                validation_results['errors'].append("No valid space_data context")
                validation_results['status'] = 'ERROR'
            
            if bpy.context.space_data and bpy.context.space_data.type != 'VIEW_3D':
                validation_results['warnings'].append(f"Not in 3D View (current: {bpy.context.space_data.type})")
            
            # Check font system
            if not hasattr(self.drawing, 'font_id') or self.drawing.font_id == -1:
                validation_results['errors'].append("Invalid font_id in drawing system")
                validation_results['status'] = 'ERROR'
            else:
                validation_results['info'].append(f"Font ID: {self.drawing.font_id}")
            
            # Check animation system
            try:
                import bonsai.tool as tool
                anim_props = tool.Sequence.get_animation_props()
                if not anim_props:
                    validation_results['warnings'].append("No animation properties found")
                else:
                    # Check animation groups
                    if hasattr(anim_props, 'animation_group_stack'):
                        group_count = len(anim_props.animation_group_stack)
                        validation_results['info'].append(f"Animation groups: {group_count}")
                        
                        active_groups = [g.group for g in anim_props.animation_group_stack if getattr(g, 'enabled', False)]
                        validation_results['info'].append(f"Active groups: {active_groups}")
                        
                        if not active_groups:
                            validation_results['warnings'].append("No active animation groups")
                    
                    # Check camera properties
                    if hasattr(anim_props, 'camera_orbit'):
                        camera_props = anim_props.camera_orbit
                        hud_states = {
                            'text_hud': getattr(camera_props, 'enable_text_hud', False),
                            'timeline_hud': getattr(camera_props, 'enable_timeline_hud', False),
                            'legend_hud': getattr(camera_props, 'enable_legend_hud', False)
                        }
                        validation_results['info'].append(f"HUD states: {hud_states}")
                        
                        enabled_huds = [k for k, v in hud_states.items() if v]
                        if not enabled_huds:
                            validation_results['warnings'].append("No HUD elements enabled")
            
            except ImportError:
                validation_results['errors'].append("Cannot import bonsai.tool module")
                validation_results['status'] = 'ERROR'
            except Exception as e:
                validation_results['errors'].append(f"Animation system check failed: {e}")
                validation_results['status'] = 'ERROR'
            
            # Check cache system
            if hasattr(self, '_legend_data_cache'):
                cache_age = 0
                if hasattr(self, '_cache_timestamp'):
                    import time
                    cache_age = time.time() - self._cache_timestamp
                validation_results['info'].append(f"Legend cache age: {cache_age:.2f}s")
                
                if self._legend_data_cache is not None:
                    validation_results['info'].append(f"Cached legend items: {len(self._legend_data_cache)}")
            
            # Check viewport
            if bpy.context.region:
                width = bpy.context.region.width
                height = bpy.context.region.height
                validation_results['info'].append(f"Viewport: {width}x{height}")
                
                if width <= 0 or height <= 0:
                    validation_results['warnings'].append("Invalid viewport dimensions")
        
        except Exception as e:
            validation_results['errors'].append(f"Validation failed: {e}")
            validation_results['status'] = 'ERROR'
            import traceback
            validation_results['errors'].append(f"Traceback: {traceback.format_exc()}")
        
        return validation_results
    
    def debug_legend_state(self):
        """Debug legend-specific state and data"""
        print("\n🎨 === LEGEND HUD DEBUG ===")
        
        try:
            # Check animation groups
            import bonsai.tool as tool
            anim_props = tool.Sequence.get_animation_props()
            if anim_props and hasattr(anim_props, 'animation_group_stack'):
                print(f"Animation groups ({len(anim_props.animation_group_stack)}):")
                for i, item in enumerate(anim_props.animation_group_stack):
                    enabled = getattr(item, 'enabled', False)
                    print(f"  {i}: '{item.group}' enabled={enabled}")
            
            # Check cache state
            cache_info = "No cache"
            if hasattr(self, '_legend_data_cache') and self._legend_data_cache is not None:
                cache_info = f"{len(self._legend_data_cache)} items"
                if hasattr(self, '_cache_timestamp'):
                    import time
                    age = time.time() - self._cache_timestamp
                    cache_info += f" (age: {age:.2f}s)"
            print(f"Legend cache: {cache_info}")
            
            # Check camera properties
            camera_props = self.get_camera_props()
            if camera_props:
                visible_types = getattr(camera_props, 'legend_hud_visible_colortypes', '')
                print(f"Visible colortypes: '{visible_types}'")
                print(f"Legend HUD enabled: {getattr(camera_props, 'enable_legend_hud', False)}")
            
            # Test UnifiedColorTypeManager
            try:
                from .animation import UnifiedColorTypeManager
                active_group = getattr(self, '_last_active_group', 'DEFAULT')
                colortype_data = UnifiedColorTypeManager.get_colortype_data_for_group(
                    bpy.context, active_group
                )
                print(f"UnifiedColorTypeManager data for '{active_group}': {len(colortype_data) if colortype_data else 0} colortypes")
            except Exception as e:
                print(f"UnifiedColorTypeManager error: {e}")
        
        except Exception as e:
            print(f"Debug error: {e}")
            import traceback
            traceback.print_exc()
        
        print("=== END LEGEND DEBUG ===\n")
    
    def perform_comprehensive_diagnostic(self):
        """Perform comprehensive HUD diagnostic and return detailed report"""
        print("\n🔍 === COMPREHENSIVE HUD DIAGNOSTIC ===")
        
        # Get validation results
        validation = self.validate_hud_state()
        
        # Print results
        print(f"Overall Status: {validation['status']}")
        
        if validation['errors']:
            print("❌ ERRORS:")
            for error in validation['errors']:
                print(f"  - {error}")
        
        if validation['warnings']:
            print("⚠️  WARNINGS:")
            for warning in validation['warnings']:
                print(f"  - {warning}")
        
        if validation['info']:
            print("ℹ️  INFO:")
            for info in validation['info']:
                print(f"  - {info}")
        
        # Additional specific diagnostics
        self.debug_legend_state()
        
        # Test drawing capabilities
        try:
            print("🎨 Testing drawing system...")
            test_text = "DIAGNOSTIC_TEST"
            blf.size(self.drawing.font_id, 12)
            dims = blf.dimensions(self.drawing.font_id, test_text)
            print(f"✅ Text rendering test passed: '{test_text}' -> {dims}")
        except Exception as e:
            print(f"❌ Text rendering test failed: {e}")
        
        # Performance metrics
        try:
            import time
            start_time = time.time()
            legend_data = self.get_active_colortype_legend_data()
            end_time = time.time()
            print(f"📊 Legend data retrieval: {len(legend_data) if legend_data else 0} items in {(end_time - start_time)*1000:.2f}ms")
        except Exception as e:
            print(f"📊 Performance test failed: {e}")
        
        print("=== END COMPREHENSIVE DIAGNOSTIC ===\n")
        return validation
    
    def draw_legend_elements(self, legend_data, settings, base_x, base_y, align_x, align_y, viewport_width, viewport_height):
        """Draw legend elements with proper layout"""
        if not legend_data:
            return
        
        # Configuration
        indicator_size = settings.get('legend_indicator_size', 12)
        column_spacing = settings.get('legend_column_spacing', 100)
        row_spacing = settings.get('legend_row_spacing', 20)
        padding = settings.get('legend_padding', 10)
        
        # Column titles
        state_columns = ['PLANNED', 'INPROGRESS', 'COMPLETED']
        
        # Calculate dimensions
        font_size = int(settings.get('scale', 1.0) * 12)
        blf.size(self.drawing.font_id, font_size)
        
        max_name_width = 0
        for item in legend_data:
            name_width, _ = blf.dimensions(self.drawing.font_id, item['name'])
            max_name_width = max(max_name_width, name_width)
        
        # Calculate total dimensions
        total_width = max_name_width + len(state_columns) * column_spacing + 2 * padding
        total_height = (len(legend_data) + 1) * row_spacing + 2 * padding  # +1 for header
        
        # Calculate final position
        final_x = base_x
        final_y = base_y
        
        if align_x == 'RIGHT':
            final_x = base_x - total_width
        elif align_x == 'CENTER':
            final_x = base_x - total_width / 2
        
        if align_y == 'TOP':
            final_y = base_y - total_height
        elif align_y == 'CENTER':
            final_y = base_y - total_height / 2
        
        # Draw background
        self.draw_legend_background(final_x, final_y, total_width, total_height, settings)
        
        # Draw content
        current_y = final_y + total_height - padding - row_spacing
        
        # Draw column headers
        header_x = final_x + padding + max_name_width + indicator_size + 10
        for i, state in enumerate(state_columns):
            col_x = header_x + i * column_spacing
            self.draw_legend_text(state, col_x, current_y, (1.0, 1.0, 1.0, 1.0), settings)
        
        current_y -= row_spacing
        
        # Draw legend items
        for item in legend_data:
            name_x = final_x + padding
            self.draw_legend_text(item['name'], name_x, current_y, (1.0, 1.0, 1.0, 1.0), settings)
            
            # Draw color indicators
            for i, state in enumerate(state_columns):
                indicator_x = header_x + i * column_spacing
                color = item['colors'].get(state, (0.5, 0.5, 0.5, 1.0))
                self.drawing.draw_color_indicator(indicator_x, current_y, indicator_size, color)
            
            current_y -= row_spacing
    
    def draw_legend_background(self, x, y, width, height, settings):
        """Draw legend background"""
        bg_color = settings.get('legend_bg_color', (0.0, 0.0, 0.0, 0.7))
        corner_radius = settings.get('legend_corner_radius', 5)
        
        if corner_radius > 0:
            self.drawing.draw_rounded_rect(x, y, width, height, bg_color, corner_radius)
        else:
            self.drawing.draw_gpu_rect(x, y, width, height, bg_color)
    
    def draw_legend_text(self, text, x, y, color, settings):
        """Draw legend text"""
        font_size = int(settings.get('scale', 1.0) * 12)
        blf.size(self.drawing.font_id, font_size)
        blf.position(self.drawing.font_id, x, y, 0)
        blf.color(self.drawing.font_id, *color)
        blf.draw(self.drawing.font_id, text)

    def get_colortype_color_for_state(self, colortype_data: dict, state: str) -> tuple:
        """Get color for a specific colortype and state"""
        try:
            colors = colortype_data.get('colors', {})
            
            # Default colors if not found
            default_colors = {
                'PLANNED': (0.5, 0.5, 0.5, 1.0),
                'INPROGRESS': (1.0, 1.0, 0.0, 1.0),
                'COMPLETED': (0.0, 1.0, 0.0, 1.0),
            }
            
            return colors.get(state, default_colors.get(state, (0.5, 0.5, 0.5, 1.0)))
            
        except Exception as e:
            print(f"⚠️ Error getting colortype color: {e}")
            return (0.5, 0.5, 0.5, 1.0)  # Gray fallback

    def draw_column_titles(self, base_x: float, y: float, indicator_size: float, column_spacing: float,
                          state_columns: list, settings: dict):
        """Draw column titles for legend states"""
        try:
            font_size = int(settings.get('scale', 1.0) * 12)
            blf.size(self.drawing.font_id, font_size)
            
            for i, state in enumerate(state_columns):
                col_x = base_x + i * column_spacing
                
                # Draw state title
                blf.position(self.drawing.font_id, col_x, y, 0)
                blf.color(self.drawing.font_id, 1.0, 1.0, 1.0, 1.0)  # White
                blf.draw(self.drawing.font_id, state)
                
        except Exception as e:
            print(f"⚠️ Error drawing column titles: {e}")

    def draw_colortype_row(self, legend_item: dict, base_x: float, y: float, indicator_size: float, 
                          column_spacing: float, state_columns: list, settings: dict):
        """Draw a single colortype row with name and color indicators"""
        try:
            # Draw colortype name
            name = legend_item.get('name', 'Unknown')
            font_size = int(settings.get('scale', 1.0) * 12)
            blf.size(self.drawing.font_id, font_size)
            blf.position(self.drawing.font_id, base_x, y, 0)
            blf.color(self.drawing.font_id, 1.0, 1.0, 1.0, 1.0)  # White
            blf.draw(self.drawing.font_id, name)
            
            # Calculate name width to position indicators
            name_width, _ = blf.dimensions(self.drawing.font_id, name)
            indicators_start_x = base_x + name_width + 20
            
            # Draw color indicators for each state
            for i, state in enumerate(state_columns):
                indicator_x = indicators_start_x + i * column_spacing
                color = self.get_colortype_color_for_state(legend_item, state)
                self.drawing.draw_color_indicator(indicator_x, y, indicator_size, color)
                
        except Exception as e:
            print(f"⚠️ Error drawing colortype row: {e}")

    def draw_legend_hud(self, data, settings, viewport_width, viewport_height):
        """Complete legend HUD drawing with advanced layout"""
        if not settings.get('enabled', False):
            return
        
        print(f"\n🎨 === LEGEND HUD DRAW START ===")
        print(f"🎨 Viewport: {viewport_width}x{viewport_height}")
        print(f"🎨 Settings enabled: {settings.get('enabled', False)}")
        
        legend_data = self.get_active_colortype_legend_data()
        if not legend_data:
            print("❌ LEGEND HUD: No legend data available")
            return
        
        print(f"🎨 Found {len(legend_data)} legend items")
        
        # Calculate position and dimensions
        base_x, base_y, align_x, align_y = self.calculate_legend_position(
            viewport_width, viewport_height, settings)
        
        # Configuration
        indicator_size = settings.get('legend_indicator_size', 12)
        column_spacing = settings.get('legend_column_spacing', 100)
        row_spacing = settings.get('legend_row_spacing', 20)
        padding = settings.get('legend_padding', 10)
        
        # State columns
        state_columns = ['PLANNED', 'INPROGRESS', 'COMPLETED']
        
        # Calculate dimensions for background
        font_size = int(settings.get('scale', 1.0) * 12)
        blf.size(self.drawing.font_id, font_size)
        
        max_name_width = 0
        for item in legend_data:
            name_width, _ = blf.dimensions(self.drawing.font_id, item.get('name', ''))
            max_name_width = max(max_name_width, name_width)
        
        # Calculate total dimensions
        content_width = max_name_width + 20 + len(state_columns) * column_spacing
        content_height = (len(legend_data) + 1) * row_spacing  # +1 for header
        
        total_width = content_width + 2 * padding
        total_height = content_height + 2 * padding
        
        # Calculate final position with alignment
        final_x = base_x
        final_y = base_y
        
        if align_x == 'RIGHT':
            final_x = base_x - total_width
        elif align_x == 'CENTER':
            final_x = base_x - total_width / 2
        
        if align_y == 'TOP':
            final_y = base_y - total_height
        elif align_y == 'CENTER':
            final_y = base_y - total_height / 2
        
        # Draw background
        self.draw_legend_background(final_x, final_y, total_width, total_height, settings)
        
        # Draw content starting from top
        current_y = final_y + total_height - padding - row_spacing
        content_x = final_x + padding
        
        # Draw column titles
        title_x = content_x + max_name_width + 20
        self.draw_column_titles(title_x, current_y, indicator_size, column_spacing, state_columns, settings)
        current_y -= row_spacing
        
        # Draw legend items
        for item in legend_data:
            self.draw_colortype_row(item, content_x, current_y, indicator_size, column_spacing, state_columns, settings)
            current_y -= row_spacing
        
        print("✅ Legend HUD drawn successfully")