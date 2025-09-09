# Bonsai - OpenBIM Blender Add-on
# HUD Manager - High-level HUD lifecycle management
# Copyright (C) 2024

import bpy

# Global handler reference
_hud_draw_handler = None
_hud_enabled = False


def draw_hud_callback():
    """Callback that runs every frame to draw the HUD"""
    try:
        # Import here to avoid circular imports
        from . import schedule_hud
        
        # Always use regular draw - snapshot detection is now handled inside get_schedule_data()
        # This ensures proper data flow while preventing animation for snapshots
        schedule_hud.draw()
    except Exception as e:
        print(f"🔴 HUD callback error: {e}")
        import traceback
        traceback.print_exc()


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
    """Global function to invalidate Legend HUD cache when animation groups change"""
    # Import here to avoid circular imports
    from . import schedule_hud
    
    if hasattr(schedule_hud, 'invalidate_legend_cache'):
        schedule_hud.invalidate_legend_cache()
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
    
    # Ensure handlers are active
    ensure_hud_handlers()


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


def debug_hud_state():
    """Diagnostic function to debug the HUD state"""
    from . import schedule_hud
    
    print("\n🔍 === HUD DEBUG STATE ===")
    print(f"Handler enabled: {_hud_enabled}")
    print(f"Handler object: {_hud_draw_handler}")

    try:
        import bonsai.tool as tool
        anim_props = tool.Sequence.get_animation_props()
        camera_props = anim_props.camera_orbit
        hud_enabled = getattr(camera_props, 'enable_text_hud', False)
        print(f"Property enable_text_hud: {hud_enabled}")

        # Verify schedule data
        data = schedule_hud.get_schedule_data()
        print(f"Schedule data available: {data is not None}")
        if data:
            print(f"  Current date: {data.get('current_date')}")
            print(f"  Frame: {data.get('current_frame')}")

    except Exception as e:
        print(f"Error in debug: {e}")

    print("=== END DEBUG ===\n")