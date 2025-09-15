# Simple ColorType Persistence - Like v60 but SIMPLE
# Only saves/restores animation_color_schemes - nothing else

import bpy
import bonsai.tool as tool

# Simple dictionary to store colortype values
_simple_colortype_backup = {}

def save_colortypes_simple():
    """Save ONLY animation_color_schemes - SIMPLE like v60"""
    global _simple_colortype_backup
    _simple_colortype_backup.clear()
    
    try:
        context = bpy.context
        tprops = getattr(context.scene, 'BIMTaskTreeProperties', None)
        if not tprops:
            return
        
        # Save ONLY animation_color_schemes for each visible task
        for task in tprops.tasks:
            task_id = str(task.ifc_definition_id)
            if task_id != "0":
                colortype_value = getattr(task, 'animation_color_schemes', '')
                if colortype_value:  # Only save if not empty
                    _simple_colortype_backup[task_id] = colortype_value
        
        print(f"✅ Simple: Saved {len(_simple_colortype_backup)} ColorTypes")
        
    except Exception as e:
        print(f"❌ Simple save failed: {e}")

def restore_colortypes_simple():
    """Restore ONLY animation_color_schemes - SIMPLE like v60"""
    global _simple_colortype_backup
    
    try:
        context = bpy.context
        tprops = getattr(context.scene, 'BIMTaskTreeProperties', None)
        if not tprops or not _simple_colortype_backup:
            return
        
        restored_count = 0
        # Restore ONLY animation_color_schemes for each visible task
        for task in tprops.tasks:
            task_id = str(task.ifc_definition_id)
            if task_id in _simple_colortype_backup:
                try:
                    task.animation_color_schemes = _simple_colortype_backup[task_id]
                    restored_count += 1
                except Exception as e:
                    print(f"❌ Failed to restore task {task_id}: {e}")
        
        print(f"✅ Simple: Restored {restored_count} ColorTypes")
        
    except Exception as e:
        print(f"❌ Simple restore failed: {e}")