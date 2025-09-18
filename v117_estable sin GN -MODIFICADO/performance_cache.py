# Performance Cache System for 4D Animation
# Reduces 8000 objects processing from 40s to ~3-5s

import bpy
import time
from typing import Dict, List, Optional, Any
import bonsai.tool as tool
import ifcopenshell.util.sequence

class AnimationPerformanceCache:
    """Sistema de cache ultra-eficiente para animaciones 4D grandes"""

    def __init__(self):
        self.ifc_entity_cache: Dict[str, Any] = {}
        self.task_outputs_cache: Dict[int, List] = {}
        self.task_inputs_cache: Dict[int, List] = {}
        self.date_cache: Dict[str, Any] = {}
        self.product_to_objects_cache: Dict[int, List] = {}
        self.scene_objects_cache: List = []
        self.cache_valid = False

    def invalidate(self):
        """Invalida todo el cache"""
        self.ifc_entity_cache.clear()
        self.task_outputs_cache.clear()
        self.task_inputs_cache.clear()
        self.date_cache.clear()
        self.product_to_objects_cache.clear()
        self.scene_objects_cache.clear()
        self.cache_valid = False

    def build_scene_cache(self):
        """Pre-construye cache de objetos de escena - EJECUTAR UNA SOLA VEZ"""
        start_time = time.time()

        # 1. Cache todos los objetos IFC de una vez
        self.scene_objects_cache = []
        ifc_objects = []

        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                self.scene_objects_cache.append(obj)
                entity = tool.Ifc.get_entity(obj)
                if entity and not entity.is_a("IfcSpace"):
                    self.ifc_entity_cache[obj.name] = entity
                    ifc_objects.append((obj, entity))

                    # Construir mapeo producto->objetos
                    product_id = entity.id()
                    if product_id not in self.product_to_objects_cache:
                        self.product_to_objects_cache[product_id] = []
                    self.product_to_objects_cache[product_id].append(obj)

        self.cache_valid = True
        elapsed = time.time() - start_time
        print(f"🚀 CACHE: Construido en {elapsed:.2f}s - {len(ifc_objects)} objetos IFC")

    def get_ifc_entity(self, obj) -> Optional[Any]:
        """Obtiene entidad IFC desde cache"""
        return self.ifc_entity_cache.get(obj.name)

    def get_objects_for_product(self, product_id: int) -> List:
        """Obtiene objetos Blender para un producto IFC"""
        return self.product_to_objects_cache.get(product_id, [])

    def get_task_outputs_cached(self, task) -> List:
        """Cache de task outputs"""
        task_id = task.id()
        if task_id not in self.task_outputs_cache:
            self.task_outputs_cache[task_id] = list(ifcopenshell.util.sequence.get_task_outputs(task))
        return self.task_outputs_cache[task_id]

    def get_task_inputs_cached(self, task) -> List:
        """Cache de task inputs"""
        task_id = task.id()
        if task_id not in self.task_inputs_cache:
            # Usar el método existente de tool.Sequence si está disponible
            try:
                inputs = tool.Sequence.get_task_inputs(task)
                self.task_inputs_cache[task_id] = inputs if inputs else []
            except:
                # Fallback al método directo
                self.task_inputs_cache[task_id] = list(ifcopenshell.util.sequence.get_task_inputs(task))
        return self.task_inputs_cache[task_id]

    def get_date_cached(self, task, date_type: str, is_earliest: bool = False, is_latest: bool = False) -> Optional[Any]:
        """Cache de fechas de tareas"""
        cache_key = f"{task.id()}_{date_type}_{is_earliest}_{is_latest}"
        if cache_key not in self.date_cache:
            try:
                if is_earliest:
                    date = ifcopenshell.util.sequence.derive_date(task, date_type, is_earliest=True)
                elif is_latest:
                    date = ifcopenshell.util.sequence.derive_date(task, date_type, is_latest=True)
                else:
                    date = ifcopenshell.util.sequence.derive_date(task, date_type)
                self.date_cache[cache_key] = date
            except:
                self.date_cache[cache_key] = None
        return self.date_cache[cache_key]

# Cache global singleton
_performance_cache = AnimationPerformanceCache()

def get_performance_cache() -> AnimationPerformanceCache:
    """Obtiene el cache de rendimiento global"""
    return _performance_cache

def invalidate_cache():
    """Invalida el cache global"""
    _performance_cache.invalidate()