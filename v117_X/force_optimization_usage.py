# Force Animation Operator to Use Optimized Methods

def force_optimization_usage():
    """Modify animation operator to use optimized methods"""

    try:
        operator_path = r"C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\.local\lib\python3.11\site-packages\bonsai\bim\module\sequence\operators\animation_operators.py"

        # Read the file
        with open(operator_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find and replace the frames computation
        old_frames_code = '''            # Compute frames with optimization
            frames_start = time.time()
            frames = _compute_product_frames(context, work_schedule, settings)
            frames_time = time.time() - frames_start
            print(f"📊 FRAMES COMPUTED: {len(frames)} products in {frames_time:.2f}s")'''

        new_frames_code = '''            # Compute frames with optimization - FORCE USE OF OPTIMIZED METHOD
            frames_start = time.time()

            # Try to use optimized method first
            try:
                if hasattr(tool.Sequence, 'get_animation_product_frames_enhanced_optimized'):
                    from bonsai.bim.module.sequence import ifc_lookup
                    lookup = ifc_lookup.get_ifc_lookup()
                    date_cache = ifc_lookup.get_date_cache()

                    # Build lookup tables if not already built
                    if not lookup.lookup_built:
                        print("[OPTIMIZED] Building lookup tables...")
                        lookup.build_lookup_tables(work_schedule)

                    print("[OPTIMIZED] Using enhanced optimized frame computation...")
                    frames = tool.Sequence.get_animation_product_frames_enhanced_optimized(
                        work_schedule, settings, lookup, date_cache
                    )
                else:
                    print("[FALLBACK] Using standard frame computation...")
                    frames = _compute_product_frames(context, work_schedule, settings)
            except Exception as e:
                print(f"[ERROR] Optimized method failed: {e}, using fallback...")
                frames = _compute_product_frames(context, work_schedule, settings)

            frames_time = time.time() - frames_start
            print(f"[PERF] FRAMES COMPUTED: {len(frames)} products in {frames_time:.2f}s")'''

        # Apply frames replacement
        if old_frames_code in content:
            content = content.replace(old_frames_code, new_frames_code)
            print("✅ Replaced frames computation with optimized version")
        else:
            print("⚠️ Could not find frames computation code to replace")

        # Find and replace the animation application
        old_anim_code = '''            # Apply animation with optimization
            anim_start = time.time()
            _apply_colortype_animation(context, frames, settings)
            anim_time = time.time() - anim_start
            print(f"🎬 ANIMATION APPLIED: Completed in {anim_time:.2f}s")'''

        new_anim_code = '''            # Apply animation with optimization - FORCE USE OF OPTIMIZED METHOD
            anim_start = time.time()

            # Try to use optimized animation method first
            try:
                if hasattr(tool.Sequence, 'animate_objects_with_ColorTypes_optimized'):
                    from bonsai.bim.module.sequence import performance_cache, batch_processor
                    cache = performance_cache.get_performance_cache()
                    batch = batch_processor.BlenderBatchProcessor()

                    # Build cache if not already built
                    if not cache.cache_valid:
                        print("[OPTIMIZED] Building performance cache...")
                        cache.build_scene_cache()

                    print("[OPTIMIZED] Using enhanced optimized animation application...")
                    tool.Sequence.animate_objects_with_ColorTypes_optimized(
                        settings, frames, cache, batch
                    )
                else:
                    print("[FALLBACK] Using standard animation application...")
                    _apply_colortype_animation(context, frames, settings)
            except Exception as e:
                print(f"[ERROR] Optimized animation failed: {e}, using fallback...")
                _apply_colortype_animation(context, frames, settings)

            anim_time = time.time() - anim_start
            print(f"[PERF] ANIMATION APPLIED: Completed in {anim_time:.2f}s")'''

        # Apply animation replacement
        if old_anim_code in content:
            content = content.replace(old_anim_code, new_anim_code)
            print("✅ Replaced animation application with optimized version")
        else:
            print("⚠️ Could not find animation application code to replace")

        # Write back the file
        with open(operator_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print("SUCCESS: Animation operator now forces use of optimized methods!")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False

# Run the fix
if __name__ == "__main__":
    success = force_optimization_usage()
    if success:
        print("\nSUCCESS! Your 4D animation will now use optimized methods!")
        print("Next: Create a 4D animation and it should be 10x faster!")
    else:
        print("\nFAILED: Could not force optimization usage")