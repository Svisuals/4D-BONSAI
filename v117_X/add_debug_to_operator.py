# Add Debug to Operator - Add debug prints to see execution flow
def add_debug_to_operator():
    """Add debug prints to work_schedule_operators.py to see what's happening"""
    try:
        operator_path = r"C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\.local\lib\python3.11\site-packages\bonsai\bim\module\sequence\operators\work_schedule_operators.py"

        # Read the file
        with open(operator_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Add debug print right before the optimization detection
        debug_line = """
            print("[DEBUG] About to check for optimized methods...")
            print(f"[DEBUG] tool.Sequence has get_animation_product_frames_enhanced_optimized: {hasattr(tool.Sequence, 'get_animation_product_frames_enhanced_optimized')}")
            """

        # Find the line "# FORCE USE OPTIMIZED FRAME COMPUTATION" and add debug before it
        target = "# FORCE USE OPTIMIZED FRAME COMPUTATION"
        if target in content:
            content = content.replace(target, debug_line + target)

            # Write back
            with open(operator_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print("SUCCESS: Added debug prints to operator")
            print("Now create a 4D animation and you should see [DEBUG] messages")
        else:
            print("ERROR: Could not find target line in operator")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    add_debug_to_operator()