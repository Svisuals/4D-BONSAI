# Bonsai - OpenBIM Blender Add-on
# Legend HUD Component for 4D Animation
# Copyright (C) 2024

import bpy
import blf
import gpu
import json
import time
from gpu_extras.batch import batch_for_shader


class LegendHUD:
    """Specialized component for displaying colortype legend and task status"""
    
    def __init__(self, font_id):
        """Initialize LegendHUD with shared font"""
        self.font_id = font_id
        
        # Cache for legend data with invalidation
        self._legend_data_cache = None
        self._cached_animation_groups = None
        self._cache_timestamp = 0
        self._last_active_group = None
        
        print(f"🎨 LegendHUD initialized with font_id={font_id}")
    
    def invalidate_legend_cache(self):
        """Invalidates the legend data cache to force an update"""
        print("🔄 Invalidating legend cache")
        self._legend_data_cache = None
        self._cached_animation_groups = None
        self._cache_timestamp = 0
        self._last_active_group = None  # Reset group tracking to force detection
    
    def draw(self, data, settings, viewport_width, viewport_height):
        """Draw legend HUD elements"""
        try:
            # Get legend data
            legend_data = self.get_active_colortype_legend_data()
            if not legend_data:
                return
            
            # Calculate legend positioning
            legend_x, legend_y = self.calculate_legend_position(
                viewport_width, viewport_height, settings
            )
            
            # Draw legend background
            legend_width, legend_height = self.calculate_legend_size(legend_data, settings)
            self.draw_legend_background(legend_x, legend_y, legend_width, legend_height, settings)
            
            # Draw legend items
            self.draw_legend_items(legend_data, legend_x, legend_y, legend_width, legend_height, settings)
            
        except Exception as e:
            print(f"❌ Error in LegendHUD.draw: {e}")
            import traceback
            traceback.print_exc()
    
    def get_active_colortype_legend_data(self, include_hidden=False):
        """Get colortype legend data with caching and visibility filtering"""
        try:
            import bonsai.tool as tool
            
            # Get animation properties
            anim_props = tool.Sequence.get_animation_props()
            if not hasattr(anim_props, 'animation_group_stack') or not anim_props.animation_group_stack:
                print("🎨 No animation group stack found")
                self._legend_data_cache = []
                return []
            
            # Find the first enabled group (active group)
            current_active_group = None
            for group_item in anim_props.animation_group_stack:
                if getattr(group_item, 'enabled', False):
                    current_active_group = getattr(group_item, 'group', '')
                    break
            
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
            
            # Get colortype data with visibility filtering
            legend_data = self._extract_colortype_data(active_group, include_hidden, hidden_colortypes)
            
            # Update cache
            self._legend_data_cache = legend_data
            self._cached_animation_groups = cache_key
            self._cache_timestamp = current_timestamp
            
            print(f"✅ Legend cache updated for group '{active_group}': {len(legend_data)} items")
            return legend_data
            
        except Exception as e:
            print(f"❌ Error getting legend data: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_current_animation_groups(self):
        """Get current state of animation groups for cache comparison"""
        try:
            import bonsai.tool as tool
            anim_props = tool.Sequence.get_animation_props()
            
            # Create a snapshot of current group states
            group_states = []
            for group_item in getattr(anim_props, 'animation_group_stack', []):
                group_states.append({
                    'group': getattr(group_item, 'group', ''),
                    'enabled': getattr(group_item, 'enabled', False)
                })
            
            return tuple(str(sorted(group_states)))
            
        except Exception:
            return None
    
    def _extract_colortype_data(self, active_group, include_hidden=False, hidden_colortypes=None):
        """Extract colortype data from the active group with visibility filtering"""
        try:
            import bonsai.tool as tool
            
            if hidden_colortypes is None:
                hidden_colortypes = set()
            
            # CRITICAL: Import UnifiedColorTypeManager from the correct location
            try:
                from ..prop.color_manager_prop import UnifiedColorTypeManager
            except ImportError:
                from ..prop import UnifiedColorTypeManager
            
            context = bpy.context
            
            # SPECIAL CASE: For DEFAULT group, ensure ALL colortypes are loaded
            if active_group == "DEFAULT":
                print(f"🎨 Processing DEFAULT group - ensuring all colortypes loaded")
                try:
                    UnifiedColorTypeManager.ensure_default_colortypes(context)
                    # Force reload to get complete list
                    UnifiedColorTypeManager._invalidate_cache(context)
                except Exception as e:
                    print(f"⚠️ Could not ensure DEFAULT colortypes: {e}")
            
            # Get colortypes for the active group
            group_colortypes = UnifiedColorTypeManager.get_group_colortypes(context, active_group)
            
            if not group_colortypes:
                print(f"❌ No colortypes found for group '{active_group}'")
                self._legend_data_cache = []
                return []
            
            legend_data = []
            
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
            
            # Sort alphabetically for consistent display
            legend_data.sort(key=lambda x: x['name'])
            
            print(f"🎨 Processed {len(legend_data)} colortypes from active group '{active_group}'")
            if hidden_colortypes:
                print(f"🙈 Hidden colortypes: {list(hidden_colortypes)}")
            
            return legend_data
            
        except Exception as e:
            print(f"❌ Error extracting colortype data: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def calculate_legend_position(self, viewport_width, viewport_height, settings):
        """Calculate the position of the legend"""
        position = settings.get('position', 'TOP_LEFT')
        margin_h = int(viewport_width * settings.get('margin_h', 0.02))
        margin_v = int(viewport_height * settings.get('margin_v', 0.02))
        
        if position == 'TOP_LEFT':
            return margin_h, viewport_height - margin_v
        elif position == 'TOP_RIGHT':
            return viewport_width - margin_h, viewport_height - margin_v
        elif position == 'BOTTOM_LEFT':
            return margin_h, margin_v
        elif position == 'BOTTOM_RIGHT':
            return viewport_width - margin_h, margin_v
        else:  # CENTER or custom
            return viewport_width // 2, viewport_height // 2
    
    def calculate_legend_size(self, legend_data, settings):
        """Calculate the size needed for the legend"""
        if not legend_data:
            return 100, 50  # Minimum size
        
        # Calculate based on number of items and text size
        item_height = settings.get('item_height', 20)
        item_width = settings.get('item_width', 150)
        padding = settings.get('padding', 10)
        
        # Account for title if shown
        title_height = settings.get('title_height', 25) if settings.get('show_title', True) else 0
        
        # Calculate dimensions
        legend_height = title_height + len(legend_data) * item_height + padding * 2
        legend_width = item_width + padding * 2
        
        return legend_width, legend_height
    
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

    def draw_gpu_rect(self, x, y, w, h, color):
        """Draws a simple rectangle"""
        try:
            vertices = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            indices = [(0, 1, 2), (2, 3, 0)]
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
            gpu.state.blend_set('NONE')
        except Exception as e:
            print(f"Error drawing GPU rect: {e}")

    def draw_rounded_rect(self, x, y, w, h, color, radius):
        """Draws a rectangle with rounded corners using approximation with multiple triangles."""
        try:
            from math import cos, sin
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
            segments = max(4, int(radius / 2))  # Adjust according to radius size
            
            # Center of the rectangle to facilitate calculations
            center_x = x + w / 2
            center_y = y + h / 2
            
            # Create vertices for a rounded rectangle
            # Lower left corner
            for i in range(segments + 1):
                angle = 3.14159 + i * (3.14159 / 2) / segments  # 180° to 270°
                vx = x + radius + radius * cos(angle)
                vy = y + radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Lower right corner
            for i in range(segments + 1):
                angle = 3.14159 * 1.5 + i * (3.14159 / 2) / segments  # 270° to 360°
                vx = x + w - radius + radius * cos(angle)
                vy = y + radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Upper right corner
            for i in range(segments + 1):
                angle = 0 + i * (3.14159 / 2) / segments  # 0° to 90°
                vx = x + w - radius + radius * cos(angle)
                vy = y + h - radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Upper left corner
            for i in range(segments + 1):
                angle = 3.14159 / 2 + i * (3.14159 / 2) / segments  # 90° to 180°
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
            
            # Draw the rounded rectangle
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
    
    def draw_legend_border(self, x, y, width, height, border_color):
        """Draw border around legend"""
        try:
            vertices = [
                (x, y), (x + width, y),
                (x + width, y), (x + width, y + height),
                (x + width, y + height), (x, y + height),
                (x, y + height), (x, y)
            ]
            
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'LINES', {"pos": vertices})
            
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("color", border_color)
            batch.draw(shader)
            gpu.state.blend_set('NONE')
            
        except Exception as e:
            print(f"❌ Error drawing legend border: {e}")
    
    def get_camera_props(self):
        """Get camera properties for Legend HUD settings"""
        try:
            import bonsai.tool as tool
            return tool.Sequence.get_animation_camera_props()
        except Exception as e:
            print(f"❌ Error getting camera props: {e}")
            return None
    
    def draw_legend_items(self, legend_data, base_x, base_y, legend_width, legend_height, settings):
        """Draw the individual legend items"""
        try:
            position = settings.get('position', 'TOP_LEFT')
            padding = settings.get('padding', 10)
            item_height = settings.get('item_height', 20)
            
            # Adjust position based on alignment
            if 'RIGHT' in position:
                x = base_x - legend_width
            else:
                x = base_x
                
            if 'BOTTOM' in position:
                y = base_y - legend_height
            else:
                y = base_y
            
            # Draw title if enabled
            current_y = y + legend_height - padding
            if settings.get('show_title', True):
                title_height = settings.get('title_height', 25)
                current_y -= title_height
                
                title_text = settings.get('title_text', 'ColorTypes')
                title_color = settings.get('title_color', (1.0, 1.0, 1.0, 1.0))
                
                blf.size(self.font_id, 14)
                blf.color(self.font_id, *title_color)
                blf.position(self.font_id, x + padding, current_y, 0)
                blf.draw(self.font_id, title_text)
                
                current_y -= 5  # Small gap after title
            
            # Draw legend items
            color_size = settings.get('color_indicator_size', 12)
            text_offset = color_size + 8
            
            blf.size(self.font_id, 11)
            
            for item in legend_data:
                try:
                    current_y -= item_height
                    
                    # Draw the 3 color indicators: start, active, end
                    indicator_x = x + padding
                    
                    # Always draw 3 colors in the correct order
                    colors_to_draw = [
                        ('start', item.get('start_color', [1.0, 1.0, 1.0, 1.0])),
                        ('active', item.get('active_color', [0.0, 1.0, 0.0, 1.0])),
                        ('end', item.get('end_color', [0.0, 0.8, 0.0, 1.0]))
                    ]
                    
                    for i, (state_name, color) in enumerate(colors_to_draw):
                        color_x = indicator_x + i * (color_size + 2)
                        color_y = current_y + (item_height - color_size) // 2
                        
                        self.draw_color_indicator(color_x, color_y, color_size, color)
                    
                    # Draw text label
                    text_color = settings.get('text_color', (1.0, 1.0, 1.0, 1.0))
                    text_x = indicator_x + text_offset + 3 * (color_size + 2)  # Always 3 colors
                    text_y = current_y + (item_height - 12) // 2
                    
                    blf.color(self.font_id, *text_color)
                    blf.position(self.font_id, text_x, text_y, 0)
                    
                    # Truncate long names to fit
                    name = item['name']
                    max_width = legend_width - text_offset - padding * 2 - 3 * (color_size + 2)
                    
                    # Simple truncation - could be improved with proper text measurement
                    if len(name) > 20:
                        name = name[:17] + "..."
                    
                    blf.draw(self.font_id, name)
                    
                except Exception as e:
                    print(f"❌ Error drawing legend item '{item.get('name', 'unknown')}': {e}")
                    continue
                    
        except Exception as e:
            print(f"❌ Error drawing legend items: {e}")
    
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

    def draw_legend_text(self, text: str, x: float, y: float, color: tuple, settings: dict):
        """Draws legend text with proper styling"""
        try:
            scale = settings.get('scale', 1.0)
            font_size = int(12 * scale)
            blf.size(self.font_id, font_size)
            
            # Text shadow if enabled
            if settings.get('text_shadow_enabled', True):
                shadow_offset_x = settings.get('text_shadow_offset_x', 1.0)
                shadow_offset_y = settings.get('text_shadow_offset_y', -1.0)
                shadow_color = settings.get('text_shadow_color', (0.0, 0.0, 0.0, 0.8))
                
                blf.position(self.font_id, x + shadow_offset_x, y + shadow_offset_y, 0)
                blf.color(self.font_id, *shadow_color)
                blf.draw(self.font_id, text)
            
            # Main text
            blf.position(self.font_id, x, y, 0)
            blf.color(self.font_id, *color)
            blf.draw(self.font_id, text)
            
        except Exception as e:
            print(f"❌ Error drawing legend text: {e}")
    
    def get_camera_props(self):
        """Helper to get camera properties"""
        try:
            import bonsai.tool as tool
            anim_props = tool.Sequence.get_animation_props()
            return anim_props.camera_orbit
        except Exception:
            return None

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

            # --- 4. DRAW BACKGROUND ---
            bg_width = total_content_width + padding_h * 2
            bg_height = total_content_height + padding_v * 2
            
            if align_x == 'RIGHT':
                bg_x = base_x - bg_width
            elif align_x == 'CENTER':
                bg_x = base_x - bg_width / 2
            else:
                bg_x = base_x
                
            if align_y == 'TOP':
                bg_y = base_y - bg_height
            else:
                bg_y = base_y

            self.draw_legend_background(bg_x, bg_y, bg_width, bg_height, settings)

            # --- 5. DRAW TITLE ---
            content_start_x = bg_x + padding_h
            current_y = bg_y + bg_height - padding_v
            
            if settings.get('show_title', True):
                title_font_size = getattr(camera_props, 'legend_hud_title_font_size', 16.0) * scale
                blf.size(self.font_id, int(title_font_size))
                title_color = settings.get('title_color', (1.0, 1.0, 1.0, 1.0))
                title_text = settings.get('title_text', 'Legend')
                _, title_h = blf.dimensions(self.font_id, title_text)
                
                current_y -= title_h
                self.draw_legend_text(title_text, content_start_x, current_y, title_color, settings)
                current_y -= item_spacing
                
                # Restore original font size
                blf.size(self.font_id, font_size)

            # --- 6. DRAW LEGEND ITEMS ---
            for row_indices in rows_of_indices:
                current_row_x = content_start_x
                current_y -= row_height
                
                for item_index in row_indices:
                    if item_index < len(legend_data):
                        self.draw_colortype_row(legend_data[item_index], current_row_x, current_y, 
                                             color_indicator_size, column_spacing, 
                                             show_start, show_active, show_end, settings)
                        current_row_x += item_widths[item_index] + item_spacing
                
                current_y -= item_spacing
                
        except Exception as e:
            print(f"❌ Error drawing legend elements: {e}")

    def invalidate_cache(self):
        """Invalidate the legend cache to force refresh"""
        self._legend_data_cache = None
        self._cached_animation_groups = None
        self._cache_timestamp = 0
        print("🔄 Legend HUD cache invalidated manually")
    
    def scroll_up(self):
        """Handle scroll up action (future feature)"""
        print("📜 Legend HUD scroll up (not implemented)")
    
    def scroll_down(self):
        """Handle scroll down action (future feature)"""  
        print("📜 Legend HUD scroll down (not implemented)")
    
    def toggle_item_visibility(self, item_name):
        """Toggle visibility of a legend item (future feature)"""
        print(f"👁️ Toggle visibility for '{item_name}' (not implemented)")