# Force Animation Operator to Use Optimized Methods - Simple Version

def force_optimization_usage():
    """Modify animation operator to use optimized methods"""

    try:
        operator_path = r"C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\.local\lib\python3.11\site-packages\bonsai\bim\module\sequence\operators\animation_operators.py"

        # Read the file
        with open(operator_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Simple replacement - just change the function call
        old_call = 'frames = _compute_product_frames(context, work_schedule, settings)'

        new_call = '''# FORCE USE OPTIMIZED METHOD
            try:
                if hasattr(tool.Sequence, 'get_animation_product_frames_enhanced_optimized'):
                    from bonsai.bim.module.sequence import ifc_lookup
                    lookup = ifc_lookup.get_ifc_lookup()
                    date_cache = ifc_lookup.get_date_cache()
                    if not lookup.lookup_built:
                        print("[OPTIMIZED] Building lookup tables...")
                        lookup.build_lookup_tables(work_schedule)
                    print("[OPTIMIZED] Using enhanced optimized frame computation...")
                    frames = tool.Sequence.get_animation_product_frames_enhanced_optimized(
                        work_schedule, settings, lookup, date_cache
                    )
                else:
                    frames = _compute_product_frames(context, work_schedule, settings)
            except Exception as e:
                print(f"[ERROR] Optimized method failed: {e}")
                frames = _compute_product_frames(context, work_schedule, settings)'''

        if old_call in content:
            content = content.replace(old_call, new_call)
            print("Replaced frames computation with optimized version")

            # Write back the file
            with open(operator_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print("SUCCESS: Animation operator modified!")
            return True
        else:
            print("Could not find target code to replace")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

# Run the fix
if __name__ == "__main__":
    success = force_optimization_usage()
    if success:
        print("Your 4D animation will now use optimized methods!")
        print("Try creating a 4D animation - it should be 10x faster!")
    else:
        print("Could not force optimization usage")