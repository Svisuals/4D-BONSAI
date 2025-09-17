# Fix Class Structure - Move optimized methods inside Sequence class

def fix_sequence_class_structure():
    """Move optimized methods from outside the class to inside the class"""

    try:
        installer_path = r"C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\.local\lib\python3.11\site-packages\bonsai\tool\sequence.py"

        # Read the file
        with open(installer_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        print(f"Original file has {len(lines)} lines")

        # Find class boundaries
        class_start = None
        class_end = None

        for i, line in enumerate(lines):
            if line.strip().startswith('class Sequence('):
                class_start = i
                print(f"Sequence class starts at line {i+1}")
            elif class_start is not None and line.strip().startswith('class ') and 'Sequence' not in line:
                class_end = i
                print(f"Sequence class ends at line {i+1} (next class: {line.strip()[:50]})")
                break

        if class_end is None:
            print("ERROR: Could not find end of Sequence class")
            return False

        # Find optimized methods (they should be after class_end)
        optimized_methods = []
        method_start = None
        current_method_lines = []

        for i in range(class_end, len(lines)):
            line = lines[i]

            # Start of a new optimized method
            if line.strip().startswith('def ') and 'optimized' in line:
                # Save previous method if any
                if method_start is not None and current_method_lines:
                    optimized_methods.append((method_start, current_method_lines))

                # Start new method
                method_start = i
                current_method_lines = [line]
                print(f"Found optimized method at line {i+1}: {line.strip()[:50]}...")

            # Continue current method (indented lines or empty lines)
            elif method_start is not None and (line.startswith('    ') or line.strip() == ''):
                current_method_lines.append(line)

            # End of current method (non-indented, non-empty line)
            elif method_start is not None and line.strip() and not line.startswith('    '):
                # Save the method
                optimized_methods.append((method_start, current_method_lines))
                method_start = None
                current_method_lines = []
                break

        # Don't forget the last method if file ends
        if method_start is not None and current_method_lines:
            optimized_methods.append((method_start, current_method_lines))

        print(f"Found {len(optimized_methods)} optimized methods to move")

        if not optimized_methods:
            print("No optimized methods found outside class")
            return False

        # Create new file content
        new_lines = []

        # Add everything up to the end of Sequence class
        new_lines.extend(lines[:class_end])

        # Add the optimized methods before the class ends
        for method_start, method_lines in optimized_methods:
            new_lines.extend(method_lines)
            new_lines.append('\n')  # Add spacing

        # Add everything after the optimized methods
        # Find where optimized methods end
        if optimized_methods:
            last_method_start, last_method_lines = optimized_methods[-1]
            optimized_end = last_method_start + len(last_method_lines)

            # Find next non-empty, non-method line
            for i in range(optimized_end, len(lines)):
                if lines[i].strip() and not lines[i].startswith('    '):
                    new_lines.extend(lines[i:])
                    break

        print(f"New file will have {len(new_lines)} lines")

        # Write the corrected file
        with open(installer_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        print("SUCCESS: Moved optimized methods inside Sequence class")
        print("Methods are now properly part of the class")
        return True

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

# Run the fix
if __name__ == "__main__":
    success = fix_sequence_class_structure()
    if success:
        print("\nSUCCESS! Now restart Blender and test again with:")
        print("exec(open(r'C:\\Users\\fede_\\Desktop\\SVisuals\\Codigos\\Bonsai Bim\\4D\\Refactorizado\\bck\\v117_estable sin GN -MODIFICADO\\simple_test.py').read())")
    else:
        print("\nFAILED: Could not fix class structure")