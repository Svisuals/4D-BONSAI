# Test Required Imports - Run in Blender Console
# This will show exactly which imports are failing

def test_required_imports():
    """Test if all required modules for optimization are available"""
    try:
        print("=== TESTING IMPORTS FOR OPTIMIZATION ===")

        # Test basic bonsai import
        try:
            import bonsai.tool as tool
            print("✅ bonsai.tool: OK")
        except ImportError as e:
            print(f"❌ bonsai.tool: FAIL - {e}")
            return

        # Test ifc_lookup import
        try:
            from bonsai.bim.module.sequence import ifc_lookup
            print("✅ ifc_lookup: OK")

            # Test if functions exist
            lookup = ifc_lookup.get_ifc_lookup()
            print(f"  get_ifc_lookup(): {type(lookup)}")

            date_cache = ifc_lookup.get_date_cache()
            print(f"  get_date_cache(): {type(date_cache)}")

        except ImportError as e:
            print(f"❌ ifc_lookup: FAIL - {e}")
        except Exception as e:
            print(f"❌ ifc_lookup functions: FAIL - {e}")

        # Test performance_cache import
        try:
            from bonsai.bim.module.sequence import performance_cache
            print("✅ performance_cache: OK")

            # Test if functions exist
            cache = performance_cache.get_performance_cache()
            print(f"  get_performance_cache(): {type(cache)}")

        except ImportError as e:
            print(f"❌ performance_cache: FAIL - {e}")
        except Exception as e:
            print(f"❌ performance_cache functions: FAIL - {e}")

        # Test batch_processor import
        try:
            from bonsai.bim.module.sequence import batch_processor
            print("✅ batch_processor: OK")

            # Test if classes exist
            batch = batch_processor.BlenderBatchProcessor()
            print(f"  BlenderBatchProcessor(): {type(batch)}")

        except ImportError as e:
            print(f"❌ batch_processor: FAIL - {e}")
        except Exception as e:
            print(f"❌ batch_processor functions: FAIL - {e}")

        print("\n=== TESTING COMPLETE ===")
        print("If any modules show FAIL, the optimization cannot work")

    except Exception as e:
        print(f"GENERAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_required_imports()