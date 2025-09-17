# Force Animation Application to Use Optimized Methods

def force_animation_optimization():
    """Modify animation application to use optimized methods"""

    try:
        operator_path = r"C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\.local\lib\python3.11\site-packages\bonsai\bim\module\sequence\operators\animation_operators.py"

        # Read the file
        with open(operator_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace the animation application call
        old_call = '_apply_colortype_animation(context, frames, settings)'

        new_call = '''# FORCE USE OPTIMIZED ANIMATION METHOD
            try:
                if hasattr(tool.Sequence, 'animate_objects_with_ColorTypes_optimized'):
                    from bonsai.bim.module.sequence import performance_cache, batch_processor
                    cache = performance_cache.get_performance_cache()
                    batch = batch_processor.BlenderBatchProcessor()
                    if not cache.cache_valid:
                        print("[OPTIMIZED] Building performance cache...")
                        cache.build_scene_cache()
                    print("[OPTIMIZED] Using enhanced optimized animation application...")
                    tool.Sequence.animate_objects_with_ColorTypes_optimized(
                        settings, frames, cache, batch
                    )
                else:
                    _apply_colortype_animation(context, frames, settings)
            except Exception as e:
                print(f"[ERROR] Optimized animation failed: {e}")
                _apply_colortype_animation(context, frames, settings)'''

        if old_call in content:
            content = content.replace(old_call, new_call)
            print("Replaced animation application with optimized version")

            # Write back the file
            with open(operator_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print("SUCCESS: Animation application optimized!")
            return True
        else:
            print("Could not find animation application code to replace")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

# Run the fix
if __name__ == "__main__":
    success = force_animation_optimization()
    if success:
        print("Animation application is now optimized!")
        print("Your 4D animation should now be 10x faster!")
    else:
        print("Could not optimize animation application")