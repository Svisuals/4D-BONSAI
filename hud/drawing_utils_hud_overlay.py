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
import blf
from gpu_extras.batch import batch_for_shader
from math import cos, sin


def draw_gpu_rect(x, y, w, h, color):
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


def draw_rounded_rect(x, y, w, h, color, radius):
        """Draws a rectangle with rounded corners using approximation with multiple triangles."""
        try:
            # Limit the radius to half the smaller dimension
            max_radius = min(w, h) / 2.0
            radius = min(radius, max_radius)
            
            if radius <= 0:
                # If the radius is 0 or negative, draw a normal rectangle
                draw_gpu_rect(x, y, w, h, color)
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
            draw_gpu_rect(x, y, w, h, color)


def draw_partial_rounded_rect(x, y, w, h, color, radius, rounded_side='LEFT'):
        """Dibuja un rectángulo con esquinas redondeadas solo en un lado"""
        """Draws a rectangle with rounded corners on one side only"""
        try:
            if rounded_side == 'LEFT' and w > radius:
                # Draw left rounded rectangle + right normal rectangle
                left_width = min(radius * 2, w // 2)
                right_width = w - left_width
                
                # Rounded left part (use full rounded rectangle as base)
                draw_rounded_rect(x, y, left_width, h, color, radius)
                
                # Rectangular right part (if there is space)
                if right_width > 0:
                    draw_gpu_rect(x + left_width, y, right_width, h, color)
            else:
                # Fallback to normal rectangle
                draw_gpu_rect(x, y, w, h, color)
                
        except Exception as e:
            print(f"Error drawing partial rounded rectangle: {e}")
            draw_gpu_rect(x, y, w, h, color)

def draw_background_with_effects(x, y, width, height, align_x, align_y, settings):
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
                draw_rounded_rect(bg_x, bg_y, final_width, final_height, avg_color, border_radius)
            else:
                draw_rounded_rect(bg_x, bg_y, final_width, final_height, background_color, border_radius)
        else:
            # Use original method
            if settings.get('background_gradient_enabled', False):
                draw_gradient_background(vertices, indices, settings)
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
            draw_border(
                bg_x, bg_y, final_width, final_height, border_width,
                settings.get('border_color', (1.0, 1.0, 1.0, 0.5)),
            )

        gpu.state.blend_set('NONE')


def draw_gradient_background(vertices, indices, settings):
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

def draw_border(x, y, width, height, border_width, border_color):
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

def draw_text_with_shadow(font_id, text, x, y, settings, align_x='LEFT'):
        """Dibuja texto con sombra y alineación mejorada usando baseline correcto"""
        """Draws text with shadow and improved alignment using the correct baseline"""
        # Configure font
        font_size = int(settings.get('scale', 1.0) * 16)
        blf.size(font_id, font_size)

        # Calculate text width for alignment
        text_width, text_height = blf.dimensions(font_id, text)

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

            blf.position(font_id, text_x + shadow_offset_x, text_y + shadow_offset_y, 0)
            blf.color(font_id, *shadow_color)
            blf.draw(font_id, text)

        # Draw main text
        text_color = settings.get('text_color', (1.0, 1.0, 1.0, 1.0))
        blf.position(font_id, text_x, text_y, 0)
        blf.color(font_id, *text_color)
        blf.draw(font_id, text)

        return text_width, text_height

def draw_timeline_line(x, y, height, color, width=1.0):
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

def draw_current_date_indicator(x, y_start, bar_h, color_indicator):
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

def draw_color_indicator(x: float, y: float, size: float, color: tuple):
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


def draw_legend_background(x: float, y: float, width: float, height: float, settings: dict):
    """Draws the legend background with configurable effects"""
    try:
        background_color = settings.get('background_color', (0.0, 0.0, 0.0, 0.8))
        border_radius = settings.get('border_radius', 5.0)
        
        if border_radius > 0:
            draw_rounded_rect(x, y, width, height, background_color, border_radius)
        else:
            draw_gpu_rect(x, y, width, height, background_color)
            
    except Exception as e:
        print(f"❌ Error drawing legend background: {e}")
