# Unicode Fix Script - Run to replace problematic unicode characters

def fix_unicode_in_sequence():
    """Fix unicode characters that cause encoding issues"""

    try:
        # Read the installer file
        with open(r"C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\.local\lib\python3.11\site-packages\bonsai\tool\sequence.py", 'r', encoding='utf-8') as f:
            content = f.read()

        # Define replacements for problematic unicode characters
        replacements = [
            ('🔍', '[CHECK]'),
            ('✅', '[OK]'),
            ('❌', '[ERROR]'),
            ('🚀', '[OPTIMIZED]'),
            ('⚡', '[FAST]'),
            ('📊', '[STATS]'),
            ('🧹', '[CLEAN]'),
            ('⏱️', '[TIME]'),
            ('🎬', '[ANIM]'),
            ('📈', '[PERF]'),
            ('⚠️', '[WARNING]'),
            ('💾', '[CACHE]'),
            ('🔧', '[PROCESS]'),
            ('🧪', '[TEST]'),
            ('🧽', '[CLEANUP]')
        ]

        # Apply replacements
        modified = False
        for unicode_char, ascii_replacement in replacements:
            if unicode_char in content:
                content = content.replace(unicode_char, ascii_replacement)
                modified = True
                print(f"Replaced {unicode_char} with {ascii_replacement}")

        if modified:
            # Write back the file
            with open(r"C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\.local\lib\python3.11\site-packages\bonsai\tool\sequence.py", 'w', encoding='utf-8') as f:
                f.write(content)
            print("SUCCESS: Fixed unicode characters in sequence.py")
            print("Now restart Blender and test with simple_test.py")
        else:
            print("No unicode characters found to replace")

        return True

    except Exception as e:
        print(f"Error: {e}")
        return False

# Auto-run
if __name__ == "__main__":
    fix_unicode_in_sequence()