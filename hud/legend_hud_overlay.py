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
import blf
from . import drawing_utils_hud_overlay as draw_utils
from . import data_manager_hud_overlay as data_manager

class LegendHUD:
    def __init__(self, font_id):
        self.font_id = font_id
        # Inicializa caches aquí
        self._legend_data_cache = None
        self._cached_animation_groups = None
        self._cache_timestamp = 0
        self._last_active_group = None
        self.font_id = 0 # O la lógica de fuentes que necesites

    def draw(self, data, settings, viewport_width, viewport_height, font_id):
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
                    camera_props = data_manager.get_camera_props()
                    if camera_props:
                        camera_props.legend_hud_visible_colortypes = ""
                        print("✅ AUTO-CLEARED: legend_hud_visible_colortypes (showing all colortypes from new active group)")
                except Exception as e:
                    print(f"⚠️ Could not auto-clear visible colortypes: {e}")
            
            current_timestamp = time.time()
            
            # Get visibility settings to include in the cache comparison
            camera_props = data_manager.get_camera_props()
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
            from ..prop.color_manager_prop import UnifiedColorTypeManager
            
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

            camera_props = data_manager.get_camera_props()
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

            # Dibujar el fondo directamente con las utilidades
            background_color = settings.get('background_color', (0.0, 0.0, 0.0, 0.8))
            border_radius = settings.get('border_radius', 5.0)

            if border_radius > 0:
                draw_utils.draw_rounded_rect(bg_x, bg_y, bg_width, bg_height, background_color, border_radius)
            else:
                draw_utils.draw_gpu_rect(bg_x, bg_y, bg_width, bg_height, background_color)

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
                draw_utils.draw_text_with_shadow(self.font_id, title_text, title_x, current_y, {'text_color': title_color, 'text_shadow_enabled': settings.get('text_shadow_enabled', True), 'text_shadow_offset_x': settings.get('text_shadow_offset_x', 1.0), 'text_shadow_offset_y': settings.get('text_shadow_offset_y', -1.0), 'text_shadow_color': settings.get('text_shadow_color', (0.0, 0.0, 0.0, 0.8))})
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

    def draw_column_titles(self, base_x: float, y: float, indicator_size: float, column_spacing: float,
                       show_start: bool, show_active: bool, show_end: bool,
                       show_start_title: bool, show_active_title: bool, show_end_title: bool, settings: dict):
        """Draws the titles of the Start/Active/End columns using the centralized drawing utility."""
        try:
            # Ya no necesitamos 'title_color' aquí porque la función de utils lo obtiene de 'settings'
            current_x = base_x

            if show_start and show_start_title:
                text_width, _ = blf.dimensions(self.font_id, "S")
                title_x = current_x + (indicator_size - text_width) / 2
                # ANTES: self.draw_legend_text(...)
                # AHORA: Usamos la función de draw_utils, que dibuja el texto Y su sombra.
                draw_utils.draw_text_with_shadow(self.font_id, "S", title_x, y, settings)
            if show_start:
                current_x += indicator_size + column_spacing

            if show_active and show_active_title:
                text_width, _ = blf.dimensions(self.font_id, "A")
                title_x = current_x + (indicator_size - text_width) / 2
                # ANTES: self.draw_legend_text(...)
                # AHORA: Usamos la función de draw_utils
                draw_utils.draw_text_with_shadow(self.font_id, "A", title_x, y, settings)
            if show_active:
                current_x += indicator_size + column_spacing

            if show_end and show_end_title:
                text_width, _ = blf.dimensions(self.font_id, "E")
                title_x = current_x + (indicator_size - text_width) / 2
                # ANTES: self.draw_legend_text(...)
                # AHORA: Usamos la función de draw_utils
                draw_utils.draw_text_with_shadow(self.font_id, "E", title_x, y, settings)

        except Exception as e:
            print(f"❌ Error drawing column titles: {e}")

    def draw_colortype_row(self, legend_item: dict, base_x: float, y: float, indicator_size: float, column_spacing: float,
                     show_start: bool, show_active: bool, show_end: bool, settings: dict):
        """Draws a profile row with its corresponding colors"""
        try:
            current_x = base_x
            # Ya no necesitamos 'text_color' aquí, la función utils lo tomará de 'settings'
            _, row_height = blf.dimensions(self.font_id, "X")

            # Draw color indicators
            if show_start:
                draw_utils.draw_color_indicator(current_x, y, indicator_size, legend_item['start_color'])
                current_x += indicator_size + column_spacing

            if show_active:
                draw_utils.draw_color_indicator(current_x, y, indicator_size, legend_item['active_color'])
                current_x += indicator_size + column_spacing

            if show_end:
                draw_utils.draw_color_indicator(current_x, y, indicator_size, legend_item['end_color'])

            # Calculate X for the text
            text_gap = 8 * settings.get('scale', 1.0)
            num_visible_cols = sum([show_start, show_active, show_end])
            colors_block_width = (num_visible_cols * indicator_size) + max(0, num_visible_cols - 1) * column_spacing
            text_x = base_x + colors_block_width + text_gap

            # ANTES: self.draw_legend_text(...)
            # AHORA: Usamos la función de draw_utils, que dibuja el texto y su sombra.
            draw_utils.draw_text_with_shadow(self.font_id, legend_item['name'], text_x, y, settings)

        except Exception as e:
            print(f"❌ Error drawing colortype row: {e}")