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
import os
import blf

from .text_hud_overlay import TextHUD
from .timeline_hud_overlay import TimelineHUD
from .legend_hud_overlay import LegendHUD
from . import data_manager_hud_overlay as data_manager

_hud_draw_handler = None
_hud_enabled = False


class ScheduleHUD:
    """Enhanced HUD system to display schedule information"""
    def __init__(self):
        """
        El constructor del "Jefe". Prepara la fuente y crea las
        instancias de cada especialista.
        """
        self.font_id = 0
        self.ensure_valid_font()
        
        self.text_hud = TextHUD()
        self.timeline_hud = TimelineHUD()
        self.legend_hud = LegendHUD()

    def ensure_valid_font(self):
        """
        Busca y carga la mejor fuente disponible.
        (Esta es tu lógica original completa).
        """
        try:
            font_path = os.path.join(bpy.utils.system_resource('DATAFILES'), "fonts", "droidsans.ttf")
            if os.path.exists(font_path):
                font_id = blf.load(font_path)
                if font_id != -1:
                    self.font_id = font_id
                    return
        except Exception as e:
            print(f"Bonsai HUD: No se pudo cargar la fuente DroidSans, usando default. Error: {e}")
        self.font_id = 0

    def draw(self):
        """
        El método de dibujo principal del "Jefe". Llama a los especialistas
        para que hagan su trabajo.
        """
        try:
            if not hasattr(bpy.context, 'region') or not bpy.context.region: return
            if bpy.context.space_data.type != 'VIEW_3D': return

            text_settings, timeline_settings, legend_settings = data_manager.get_hud_settings()
            
            if not text_settings.get('enabled', False) and not timeline_settings.get('enabled', False) and not legend_settings.get('enabled', False):
                return

            data = data_manager.get_schedule_data()
            if not data: return

            viewport_width = bpy.context.region.width
            viewport_height = bpy.context.region.height

            # --- Delegar el trabajo a los especialistas ---
            if text_settings.get('enabled', False):
                self.text_hud.draw(data, text_settings, viewport_width, viewport_height, self.font_id)

            if timeline_settings.get('enabled', False):
                self.timeline_hud.draw(data, timeline_settings, viewport_width, viewport_height, self.font_id)

            if legend_settings.get('enabled', False):
                self.legend_hud.draw(data, legend_settings, viewport_width, viewport_height, self.font_id)

        except Exception as e:
            print(f"Bonsai HUD draw error: {e}")
            import traceback
            traceback.print_exc()

    def draw_static(self):
        """Static drawing method for snapshot mode - prevents animation"""
        try:
            if not hasattr(bpy.context, 'region') or not bpy.context.region: return
            if not hasattr(bpy.context, 'space_data') or not bpy.context.space_data: return
            if bpy.context.space_data.type != 'VIEW_3D': return

            # Get data once and cache it for static display
            data = data_manager.get_schedule_data()
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
            text_settings, timeline_settings, legend_settings = data_manager.get_hud_settings()
            
            if not text_settings.get('enabled', False) and not timeline_settings.get('enabled', False) and not legend_settings.get('enabled', False):
                return

            # Set viewport info
            viewport_width = bpy.context.region.width
            viewport_height = bpy.context.region.height

            # Draw static HUD elements
            if text_settings.get('enabled', False):
                self.text_hud.draw(data, text_settings, viewport_width, viewport_height, self.font_id)

            if timeline_settings.get('enabled', False):
                self.timeline_hud.draw(data, timeline_settings, viewport_width, viewport_height, self.font_id)

            if legend_settings.get('enabled', False):
                self.legend_hud.draw(data, legend_settings, viewport_width, viewport_height, self.font_id)

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
    print(f"🔍 Estado actual: _hud_enabled={_hud_enabled}")
    if not _hud_enabled:
        print("🔧 Registrando handlers del HUD automáticamente...")
        register_hud_handler()
    else:
        print("✅ Handlers ya están activos")

def invalidate_legend_hud_cache():
    """Función global para invalidar el caché del Legend HUD cuando cambien los grupos de animación"""
    global schedule_hud
    if 'schedule_hud' in globals() and schedule_hud and hasattr(schedule_hud.legend_hud, 'invalidate_legend_cache'):
        schedule_hud.legend_hud.invalidate_legend_cache()
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
        data = data_manager.get_schedule_data()
        print(f"Schedule data available: {data is not None}")
        if data:
            print(f"  Current date: {data.get('current_date')}")
            print(f"  Frame: {data.get('current_frame')}")

    except Exception as e:
        print(f"Error in debug: {e}")

    print("=== END DEBUG ===\n")


# Add missing functions for backward compatibility that might be needed by other modules
def draw_current_date_indicator(x, y, height, color):
    """Draws a current date indicator line"""
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        
        vertices = [
            (x, y),
            (x, y + height)
        ]
        
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": vertices})
        
        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.blend_set('NONE')
        
    except Exception as e:
        print(f"❌ Error drawing current date indicator: {e}")


def draw_color_indicator(x, y, size, color):
    """Draws a color indicator square"""
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        
        vertices = [
            (x, y),
            (x + size, y),
            (x + size, y + size),
            (x, y + size)
        ]
        
        indices = [(0, 1, 2), (2, 3, 0)]
        
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
        
        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.blend_set('NONE')
        
    except Exception as e:
        print(f"❌ Error drawing color indicator: {e}")