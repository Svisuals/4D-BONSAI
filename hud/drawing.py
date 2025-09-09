# Bonsai - OpenBIM Blender Add-on
# HUD Drawing Functions - Low-level GPU drawing utilities
# Copyright (C) 2024

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from math import cos, sin


class HUDDrawing:
    """Low-level drawing functions that interact directly with Blender's GPU module"""
    
    def __init__(self, font_id=0):
        """Initialize drawing system with font configuration"""
        self.font_id = font_id
        self.ensure_valid_font()
    
    def ensure_valid_font(self):
        """Ensures we have a valid font_id for text rendering"""
        try:
            # Test if the current font is valid
            test_dimensions = blf.dimensions(self.font_id, "Test")
            if test_dimensions[0] == 0 and test_dimensions[1] == 0:
                print(f"⚠️ Font ID {self.font_id} seems invalid, resetting to default")
                self.font_id = 0
        except:
            print(f"⚠️ Font ID {self.font_id} caused error, resetting to default")
            self.font_id = 0
    
    def draw_gpu_rect(self, x, y, w, h, color):
        """Draws a simple rectangle using the GPU module"""
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
        """Draws a rectangle with rounded corners using triangles approximation"""
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
            segments = max(4, int(radius / 2))
            
            # Create vertices for rounded rectangle
            # Bottom left corner
            for i in range(segments + 1):
                angle = 3.14159 + i * (3.14159 / 2) / segments  # 180° to 270°
                vx = x + radius + radius * cos(angle)
                vy = y + radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Bottom right corner
            for i in range(segments + 1):
                angle = 3.14159 * 1.5 + i * (3.14159 / 2) / segments  # 270° to 360°
                vx = x + w - radius + radius * cos(angle)
                vy = y + radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Top right corner
            for i in range(segments + 1):
                angle = 0 + i * (3.14159 / 2) / segments  # 0° to 90°
                vx = x + w - radius + radius * cos(angle)
                vy = y + h - radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Top left corner
            for i in range(segments + 1):
                angle = 3.14159 / 2 + i * (3.14159 / 2) / segments  # 90° to 180°
                vx = x + radius + radius * cos(angle)
                vy = y + h - radius + radius * sin(angle)
                vertices.append((vx, vy))
            
            # Create triangles connecting all vertices to the center
            center_x = x + w / 2
            center_y = y + h / 2
            center_index = len(vertices)
            vertices.append((center_x, center_y))
            
            # Create triangle fan from center
            for i in range(len(vertices) - 1):
                indices.append((center_index, i, (i + 1) % (len(vertices) - 1)))
            
            # Draw the rounded rectangle
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
            gpu.state.blend_set('NONE')
            
        except Exception as e:
            print(f"Error drawing rounded rectangle: {e}")
            # Fallback to regular rectangle
            self.draw_gpu_rect(x, y, w, h, color)
    
    def draw_partial_rounded_rect(self, x, y, w, h, color, radius, rounded_side='LEFT'):
        """Draws a rectangle with rounded corners only on one side"""
        try:
            max_radius = min(w, h) / 2.0
            radius = min(radius, max_radius)
            
            if radius <= 0:
                self.draw_gpu_rect(x, y, w, h, color)
                return
            
            vertices = []
            segments = max(4, int(radius / 2))
            
            if rounded_side == 'LEFT':
                # Left side rounded, right side square
                
                # Bottom left corner (rounded)
                for i in range(segments + 1):
                    angle = 3.14159 + i * (3.14159 / 2) / segments  # 180° to 270°
                    vx = x + radius + radius * cos(angle)
                    vy = y + radius + radius * sin(angle)
                    vertices.append((vx, vy))
                
                # Bottom right corner (square)
                vertices.append((x + w, y))
                
                # Top right corner (square)
                vertices.append((x + w, y + h))
                
                # Top left corner (rounded)
                for i in range(segments + 1):
                    angle = 3.14159 / 2 + i * (3.14159 / 2) / segments  # 90° to 180°
                    vx = x + radius + radius * cos(angle)
                    vy = y + h - radius + radius * sin(angle)
                    vertices.append((vx, vy))
            
            elif rounded_side == 'RIGHT':
                # Right side rounded, left side square
                
                # Bottom left corner (square)
                vertices.append((x, y))
                
                # Bottom right corner (rounded)
                for i in range(segments + 1):
                    angle = 3.14159 * 1.5 + i * (3.14159 / 2) / segments  # 270° to 360°
                    vx = x + w - radius + radius * cos(angle)
                    vy = y + radius + radius * sin(angle)
                    vertices.append((vx, vy))
                
                # Top right corner (rounded)
                for i in range(segments + 1):
                    angle = 0 + i * (3.14159 / 2) / segments  # 0° to 90°
                    vx = x + w - radius + radius * cos(angle)
                    vy = y + h - radius + radius * sin(angle)
                    vertices.append((vx, vy))
                
                # Top left corner (square)
                vertices.append((x, y + h))
            
            # Create triangles connecting all vertices to the center
            center_x = x + w / 2
            center_y = y + h / 2
            center_index = len(vertices)
            vertices.append((center_x, center_y))
            
            indices = []
            # Create triangle fan from center
            for i in range(len(vertices) - 1):
                indices.append((center_index, i, (i + 1) % (len(vertices) - 1)))
            
            # Draw the partial rounded rectangle
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
            gpu.state.blend_set('NONE')
            
        except Exception as e:
            print(f"Error drawing partial rounded rectangle: {e}")
            # Fallback to regular rectangle
            self.draw_gpu_rect(x, y, w, h, color)
    
    def draw_border(self, x, y, width, height, border_width, border_color):
        """Draws a border around a rectangle"""
        try:
            if border_width <= 0:
                return
            
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
        """Draws text with shadow and improved alignment"""
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
    
    def draw_gradient_background(self, vertices, indices, settings):
        """Draws a gradient background (simplified implementation)"""
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
            gpu.state.blend_set('NONE')
        except Exception as e:
            print(f"Error drawing gradient background: {e}")

    def draw_background_with_effects(self, x, y, width, height, align_x, align_y, settings):
        """Draws background with enhanced effects and corrected coordinates"""
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
                # For gradients, use average color as approximation
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
    
    def draw_timeline_line(self, x, y, height, color, width=1.0):
        """Draws a vertical timeline line"""
        try:
            line_vertices = [(x, y), (x, y + height)]
            
            gpu.state.blend_set('ALPHA')
            gpu.state.line_width_set(width)
            
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'LINES', {"pos": line_vertices})
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
            
            gpu.state.line_width_set(1.0)  # Reset line width
            gpu.state.blend_set('NONE')
        except Exception as e:
            print(f"Error drawing timeline line: {e}")
    
    def draw_color_indicator(self, x, y, size, color):
        """Draws a small colored square indicator"""
        self.draw_gpu_rect(x, y, size, size, color)

    def draw_current_date_indicator(self, x, y_start, bar_h, color_indicator):
        """Draws current date indicator line on timeline"""
        self.draw_timeline_line(x, y_start, bar_h, color_indicator, 2.0)

    def draw_timeline_progress_bar(self, x_start, y_start, bar_w, bar_h, timeline_start, timeline_end, current_date, progress_color, date_to_x_func, border_radius=0):
        """Draws a progress bar showing timeline completion"""
        try:
            # Calculate progress position
            current_x = date_to_x_func(current_date)
            progress_width = current_x - x_start
            
            if progress_width > 0:
                if border_radius > 0:
                    self.draw_partial_rounded_rect(
                        x_start, y_start, progress_width, bar_h, 
                        progress_color, border_radius, 'LEFT')
                else:
                    self.draw_gpu_rect(x_start, y_start, progress_width, bar_h, progress_color)
        except Exception as e:
            print(f"Error drawing timeline progress bar: {e}")