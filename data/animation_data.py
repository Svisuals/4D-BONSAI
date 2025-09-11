# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>, 2025 Federico Eraso <feraso@svisuals.net>
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
import json
import ifcopenshell.util.sequence
import bonsai.tool as tool


class AnimationColorSchemeData:
    data = {}
    is_loaded = False

    @classmethod
    def load(cls):
        cls.is_loaded = True
        cls.data = {}
        # Be defensive: some older builds may miss methods or JSON structures
        try:
            cls.data["saved_color_schemes"] = cls.saved_color_schemes()
        except Exception:
            cls.data["saved_color_schemes"] = []
        try:
            cls.data["saved_animation_color_schemes"] = cls.saved_animation_color_schemes()
        except Exception:
            cls.data["saved_animation_color_schemes"] = []

    @classmethod
    def saved_color_schemes(cls):
        import json
        results = []
        try:
            groups = tool.Ifc.get().by_type("IfcGroup")
        except Exception:
            groups = []
        for group in groups:
            try:
                data = json.loads(group.Description) if getattr(group, "Description", None) else None
                if (
                    isinstance(data, dict)
                    and data.get("type") == "BBIM_AnimationColorScheme"
                    and data.get("colourscheme")
                ):
                    results.append(group)
            except Exception:
                # Ignore malformed JSON or missing fields
                pass
        results_sorted = sorted(results, key=lambda x: x.Name or "Unnamed")
        return [(str(g.id()), g.Name or "Unnamed", "") for g in results_sorted]

    @classmethod
    def saved_animation_color_schemes(cls):
        results = []
        try:
            for txt in bpy.data.texts:
                if txt.name.startswith("BIM_AcolortypeS_"):
                    name = txt.name.replace("BIM_AcolortypeS_", "", 1)
                    results.append((name, name, "Saved Animation Color Schemes"))
        except Exception:
            pass
        results.sort(key=lambda x: x[0].lower())
        return results

# --- State and ColorType helpers (compatible with UnifiedColorTypeManager) ---
def interpolate_ColorType_values(ColorType, state, progress=0.0):
    """Interpolates ColorType values based on progress (0.0..1.0). Returns dict with 'alpha' if applicable."""
    try:
        # IMPORTANT: Only process active transparency if the state is active AND considered
        if state in ("active", "in_progress") and getattr(ColorType, "consider_active", True):
            start_alpha = float(getattr(ColorType, "active_start_transparency", 0.0) or 0.0)
            end_alpha = float(getattr(ColorType, "active_finish_transparency", start_alpha) or start_alpha)
            interp_type = float(getattr(ColorType, "active_transparency_interpol", 1.0) or 1.0)
            
            if interp_type < 0.5:  # Step
                alpha = start_alpha
            else:  # Linear
                progress = max(0.0, min(1.0, float(progress)))
                alpha = start_alpha + (end_alpha - start_alpha) * progress
            return {"alpha": alpha}
        
        # For start state, verify if it should be considered
        elif state == "start" and getattr(ColorType, "consider_start", False):
            start_alpha = float(getattr(ColorType, "start_transparency", 0.0) or 0.0)
            return {"alpha": start_alpha}
            
    except Exception:
        pass
    return {}

def validate_ColorType_consistency(ColorType_data):
    """Validates consistency of a ColorType dict. Returns list of errors (strings)."""
    errors = []
    # Colors
    for color_field in ("start_color", "in_progress_color", "end_color"):
        if color_field in ColorType_data:
            color = ColorType_data[color_field]
            if not isinstance(color, (list, tuple)) or len(color) not in (3, 4):
                errors.append(f"Invalid {color_field}: {color}")
            else:
                try:
                    vals = [float(v) for v in color]
                    if any(v < 0.0 or v > 1.0 for v in vals):
                        errors.append(f"Out-of-range {color_field}: {color}")
                except Exception:
                    errors.append(f"Non-numeric {color_field}: {color}")
    # Transparencies
    for alpha_field in ("start_transparency", "end_transparency", "active_start_transparency", "active_finish_transparency"):
        if alpha_field in ColorType_data:
            try:
                alpha = float(ColorType_data[alpha_field])
                if not 0.0 <= alpha <= 1.0:
                    errors.append(f"Invalid {alpha_field}: {alpha}")
            except Exception:
                errors.append(f"Non-numeric {alpha_field}: {ColorType_data[alpha_field]}")
    return errors


def validate_and_adjust_frame(frame, settings):
    """
    Validates and adjusts a frame to ensure it's within valid range.
    Prevents negative frames and out-of-range frames.
    """
    start_frame = int(settings.get("start_frame", 1))
    total_frames = int(settings.get("total_frames", 250))
    end_frame = start_frame + total_frames
    
    # Ensure frame is not negative
    if frame < start_frame:
        return start_frame
    
    # Ensure it doesn't exceed the end
    if frame > end_frame:
        return end_frame
    
    return int(frame)

def compute_task_frames(task, settings):
    """Improved version with frame validation"""
    start_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleStart", is_earliest=True)
    finish_date = ifcopenshell.util.sequence.derive_date(task, "ScheduleFinish", is_latest=True)
    
    if not start_date or not finish_date:
        return None, None
    
    # Validate against visualization range
    viz_start = settings["start"]
    viz_finish = settings["finish"]
    
    # If completely outside the range
    if finish_date < viz_start:
        # Task finished before the period
        return settings["start_frame"], settings["start_frame"]
    
    if start_date > viz_finish:
        # Task starts after the period
        return None, None
    
    # Adjust dates to range
    adjusted_start = max(start_date, viz_start)
    adjusted_finish = min(finish_date, viz_finish)
    
    # Calculate frames
    total_frames = int(settings["total_frames"])
    duration = settings["duration"]
    
    if duration.total_seconds() > 0:
        start_progress = (adjusted_start - viz_start) / duration
        finish_progress = (adjusted_finish - viz_start) / duration
    else:
        start_progress = 0
        finish_progress = 1
    
    start_frame = settings["start_frame"] + (start_progress * total_frames)
    finish_frame = settings["start_frame"] + (finish_progress * total_frames)
    
    # Validate and adjust frames
    start_frame = validate_and_adjust_frame(start_frame, settings)
    finish_frame = validate_and_adjust_frame(finish_frame, settings)
    
    # Ensure start <= finish
    if start_frame > finish_frame:
        start_frame = finish_frame
    
    return int(start_frame), int(finish_frame)

def compute_progress_at_frame(task, frame, settings):
    """Returns task progress 0..1 at a frame, or None if not applicable."""
    sf, ff = compute_task_frames(task, settings)
    if sf is None or ff is None or ff <= sf:
        return None
    if frame <= sf:
        return 0.0
    if frame >= ff:
        return 1.0
    return (float(frame) - float(sf)) / float(max(1, ff - sf))


def refresh():
    """Refresh the animation color scheme data by reloading all cached information."""
    AnimationColorSchemeData.load()


