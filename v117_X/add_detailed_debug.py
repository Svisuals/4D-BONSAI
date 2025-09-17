# Add Detailed Exception Debug to Operator
def add_detailed_debug():
    """Add detailed exception debugging to see what's failing"""
    try:
        operator_path = r"C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\.local\lib\python3.11\site-packages\bonsai\bim\module\sequence\operators\work_schedule_operators.py"

        # Read the file
        with open(operator_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace the simple exception handling with detailed debugging
        old_except = """            except Exception as e:
                print(f"[ERROR] Optimized frame computation failed: {e}")
                product_frames = tool.Sequence.get_animation_product_frames_enhanced(work_schedule, settings)"""

        new_except = """            except Exception as e:
                print(f"[ERROR] Optimized frame computation failed: {e}")
                import traceback
                print(f"[ERROR] Full traceback:")
                traceback.print_exc()
                print(f"[ERROR] Exception type: {type(e)}")
                print(f"[ERROR] Exception args: {e.args}")
                product_frames = tool.Sequence.get_animation_product_frames_enhanced(work_schedule, settings)"""

        if old_except in content:
            content = content.replace(old_except, new_except)

            # Also add detailed debugging for the second try-except block
            old_except2 = """            except Exception as e:
                print(f"[ERROR] Optimized animation application failed: {e}")
                tool.Sequence.animate_objects_with_ColorTypes_new(settings, product_frames)"""

            new_except2 = """            except Exception as e:
                print(f"[ERROR] Optimized animation application failed: {e}")
                import traceback
                print(f"[ERROR] Full traceback:")
                traceback.print_exc()
                print(f"[ERROR] Exception type: {type(e)}")
                print(f"[ERROR] Exception args: {e.args}")
                tool.Sequence.animate_objects_with_ColorTypes_new(settings, product_frames)"""

            content = content.replace(old_except2, new_except2)

            # Write back
            with open(operator_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print("SUCCESS: Added detailed exception debugging")
            print("Now create a 4D animation and you should see detailed error information")
        else:
            print("ERROR: Could not find target exception handling in operator")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    add_detailed_debug()