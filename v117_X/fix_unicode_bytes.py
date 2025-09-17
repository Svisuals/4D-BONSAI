# Unicode Fix Script using bytes approach

def fix_unicode_sequence_file():
    """Fix unicode characters by working with bytes"""

    try:
        installer_path = r"C:\Users\fede_\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\.local\lib\python3.11\site-packages\bonsai\tool\sequence.py"

        # Read as bytes
        with open(installer_path, 'rb') as f:
            content_bytes = f.read()

        # Convert to string for replacement
        content = content_bytes.decode('utf-8')

        # Simple ASCII-only replacements
        unicode_patterns = [
            # Check mark variants
            ('🔍', '[CHECK]'),
            ('✅', '[OK]'),
            ('❌', '[ERROR]'),
            # Other common ones
            ('🚀', '[OPTIMIZED]'),
            ('📊', '[STATS]'),
            ('🧹', '[CLEAN]'),
            ('⚡', '[FAST]'),
            ('⏱', '[TIME]'),
            ('🎬', '[ANIM]'),
            ('📈', '[PERF]'),
            ('⚠', '[WARNING]'),
            ('💾', '[CACHE]'),
            ('🔧', '[PROCESS]'),
            ('🧪', '[TEST]'),
            ('🧽', '[CLEANUP]')
        ]

        changes_made = 0
        for unicode_char, replacement in unicode_patterns:
            original_content = content
            content = content.replace(unicode_char, replacement)
            if content != original_content:
                changes_made += 1

        if changes_made > 0:
            # Write back as bytes
            with open(installer_path, 'wb') as f:
                f.write(content.encode('utf-8'))

            print(f"Fixed {changes_made} unicode patterns in sequence.py")
            print("Unicode characters replaced with ASCII equivalents")
            return True
        else:
            print("No unicode characters found to replace")
            return False

    except Exception as e:
        print(f"Error fixing unicode: {e}")
        return False

# Run the fix
if __name__ == "__main__":
    success = fix_unicode_sequence_file()
    if success:
        print("\nSUCCESS! Now:")
        print("1. Restart Blender")
        print("2. Run this in Blender console:")
        print("exec(open(r'C:\\Users\\fede_\\Desktop\\SVisuals\\Codigos\\Bonsai Bim\\4D\\Refactorizado\\bck\\v117_estable sin GN -MODIFICADO\\simple_test.py').read())")