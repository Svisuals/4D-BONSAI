# Debug script para diagnosticar problemas con la clase Sequence

def debug_sequence_class():
    """Diagnóstico detallado de la clase Sequence"""
    print("🔍 SEQUENCE CLASS DIAGNOSIS")

    try:
        import bonsai.tool as tool

        # 1. Verificar que la clase existe
        print(f"📦 Sequence class type: {type(tool.Sequence)}")
        print(f"📦 Sequence class: {tool.Sequence}")
        print(f"📦 Sequence MRO: {tool.Sequence.__mro__}")

        # 2. Listar TODOS los métodos de la clase
        all_methods = [method for method in dir(tool.Sequence) if not method.startswith('_')]
        print(f"📊 Total methods in Sequence: {len(all_methods)}")

        # 3. Buscar métodos que contengan 'optimized'
        optimized_methods = [method for method in all_methods if 'optimized' in method.lower()]
        print(f"🔍 Methods containing 'optimized': {len(optimized_methods)}")
        for method in optimized_methods:
            print(f"  ✅ {method}")

        # 4. Buscar métodos que contengan 'animation'
        animation_methods = [method for method in all_methods if 'animation' in method.lower()]
        print(f"🎬 Methods containing 'animation': {len(animation_methods)}")
        for method in animation_methods[:10]:  # Mostrar primeros 10
            print(f"  📝 {method}")
        if len(animation_methods) > 10:
            print(f"  ... and {len(animation_methods) - 10} more")

        # 5. Verificar métodos específicos que esperamos
        expected_methods = [
            'get_animation_product_frames_enhanced_optimized',
            'animate_objects_with_ColorTypes_optimized',
            'clear_objects_animation_optimized',
            'check_optimizations_available'
        ]

        print(f"\n🎯 EXPECTED OPTIMIZATION METHODS:")
        for method in expected_methods:
            has_method = hasattr(tool.Sequence, method)
            status = "✅" if has_method else "❌"
            print(f"  {status} {method}")

            if has_method:
                # Verificar que es callable
                method_obj = getattr(tool.Sequence, method)
                is_callable = callable(method_obj)
                print(f"     Callable: {is_callable}")
                print(f"     Type: {type(method_obj)}")

        # 6. Intentar ejecutar check_optimizations_available si existe
        if hasattr(tool.Sequence, 'check_optimizations_available'):
            print(f"\n🔬 RUNNING BUILT-IN CHECK:")
            tool.Sequence.check_optimizations_available()

        # 7. Verificar si hay errores en el archivo sequence.py
        print(f"\n📄 CHECKING SEQUENCE.PY FILE...")
        try:
            with open(r"C:\Users\fede_\Desktop\SVisuals\Codigos\Bonsai Bim\4D\Refactorizado\bck\v117_estable sin GN -MODIFICADO\tool\sequence.py", 'r', encoding='utf-8') as f:
                content = f.read()

                # Buscar las definiciones de métodos optimizados
                optimized_defs = []
                for line_num, line in enumerate(content.split('\n'), 1):
                    if 'def ' in line and 'optimized' in line:
                        optimized_defs.append((line_num, line.strip()))

                print(f"📝 Found {len(optimized_defs)} optimized method definitions:")
                for line_num, line in optimized_defs:
                    print(f"  Line {line_num}: {line}")

                # Verificar indentación de métodos optimizados
                if optimized_defs:
                    print(f"\n🔧 CHECKING INDENTATION...")
                    lines = content.split('\n')
                    for line_num, _ in optimized_defs:
                        line = lines[line_num - 1]  # -1 because enumerate starts at 1
                        spaces = len(line) - len(line.lstrip())
                        print(f"  Line {line_num}: {spaces} spaces indentation")

                        # Verificar que está dentro de la clase (debería tener 4 espacios)
                        if spaces != 4:
                            print(f"    ⚠️ WARNING: Expected 4 spaces, got {spaces}")
                        else:
                            print(f"    ✅ Correct class method indentation")

        except Exception as file_error:
            print(f"❌ Error reading sequence.py: {file_error}")

        return len(optimized_methods) > 0

    except Exception as e:
        print(f"❌ Diagnosis failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def reload_and_debug():
    """Recarga módulos y ejecuta diagnóstico"""
    print("🔄 RELOAD AND DEBUG SEQUENCE")

    # Primero recargar
    try:
        import importlib
        import sys

        if 'bonsai.tool.sequence' in sys.modules:
            importlib.reload(sys.modules['bonsai.tool.sequence'])
            print("✅ Reloaded bonsai.tool.sequence")
    except Exception as e:
        print(f"⚠️ Reload failed: {e}")

    # Luego diagnosticar
    return debug_sequence_class()

# Auto-run
if __name__ == "__main__":
    debug_sequence_class()

# Para uso manual:
# debug_sequence_class()
# reload_and_debug()