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

import blf
from datetime import datetime
from . import drawing_utils_hud_overlay as draw_utils
from . import data_manager_hud_overlay as data_manager


class TextHUD:
    def __init__(self, font_id):
        self.font_id = font_id
        pass

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
    
    def draw(self, data, text_settings, viewport_width, viewport_height):
        """
        Dibuja el HUD de texto con toda su lógica.
        """
        # --- COMIENZO DEL BLOQUE DE TEXTO ---
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
            
            # NOTA: Llamamos a las funciones desde 'draw_utils'
            draw_utils.draw_background_with_effects(text_base_x, text_base_y, max_width, total_text_height, text_align_x, text_align_y, text_settings)
            
            padding_v = text_settings.get('padding_v', 8.0)
            if text_align_y == 'TOP':
                current_y = text_base_y - padding_v
                if line_dims: current_y -= line_dims[0][1]
            else:
                current_y = text_base_y + padding_v + total_text_height
                if line_dims: current_y -= line_dims[0][1]

            padding_h = text_settings.get('padding_h', 10.0)
            for i, line in enumerate(lines_to_draw):
                if text_align_x == 'RIGHT':
                    text_x = text_base_x - padding_h
                    # NOTA: Llamamos a las funciones desde 'draw_utils'
                    draw_utils.draw_text_with_shadow(self.font_id, line, text_x, current_y, text_settings, 'RIGHT')
                else:
                    text_x = text_base_x + padding_h
                    # NOTA: Llamamos a las funciones desde 'draw_utils'
                    draw_utils.draw_text_with_shadow(self.font_id, line, text_x, current_y, text_settings, 'LEFT')
                
                if i < len(lines_to_draw) - 1:
                    current_y -= ((text_settings.get('spacing', 0.02) * viewport_height) + line_dims[i + 1][1])


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





