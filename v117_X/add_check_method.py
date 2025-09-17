# Add the missing check_optimizations_available method

def add_check_method():
    """Add the missing check_optimizations_available method to the Sequence class"""

    try:
        installer_path = r"C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\.local\lib\python3.11\site-packages\bonsai\tool\sequence.py"

        # Read the file
        with open(installer_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if method already exists
        if 'def check_optimizations_available(' in content:
            print("Method check_optimizations_available already exists")
            return True

        # Find where to insert the method (before the first optimized method)
        first_optimized_method = 'def get_animation_product_frames_enhanced_optimized('

        if first_optimized_method in content:
            # Create the check method
            check_method = '''    @classmethod
    def check_optimizations_available(cls):
        """Check if performance optimizations are available"""
        optimized_methods = [
            'get_animation_product_frames_enhanced_optimized',
            'animate_objects_with_ColorTypes_optimized',
            'clear_objects_animation_optimized'
        ]

        available = []
        for method in optimized_methods:
            if hasattr(cls, method):
                available.append(method)

        print(f"[CHECK] OPTIMIZATION CHECK: {len(available)}/{len(optimized_methods)} methods available")
        for method in available:
            print(f"  [OK] {method}")

        missing = set(optimized_methods) - set(available)
        for method in missing:
            print(f"  [ERROR] {method}")

        return len(available) == len(optimized_methods)

    @classmethod
    '''

            # Insert the method before the first optimized method
            content = content.replace(f'    @classmethod\n    {first_optimized_method}', check_method + first_optimized_method)

            # Write back the file
            with open(installer_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print("SUCCESS: Added check_optimizations_available method")
            return True
        else:
            print("ERROR: Could not find insertion point")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

# Run the fix
if __name__ == "__main__":
    success = add_check_method()
    if success:
        print("\nSUCCESS! Now restart Blender and test with:")
        print("exec(open(r'C:\\Users\\fede_\\Desktop\\SVisuals\\Codigos\\Bonsai Bim\\4D\\Refactorizado\\bck\\v117_estable sin GN -MODIFICADO\\final_test.py').read())")
    else:
        print("\nFAILED: Could not add check method")