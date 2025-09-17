# Ultra-Fast IFC Entity Lookup System
# Precomputed mappings for instant access

import time
from typing import Dict, List, Set, Optional, Any
import bonsai.tool as tool
import ifcopenshell.util.sequence

class IFCLookupOptimizer:
    """Sistema de lookup ultra-rápido para entidades IFC y relaciones de tareas"""

    def __init__(self):
        self.product_to_output_tasks: Dict[int, List] = {}
        self.product_to_input_tasks: Dict[int, List] = {}
        self.task_to_outputs: Dict[int, List] = {}
        self.task_to_inputs: Dict[int, List] = {}
        self.task_hierarchy: Dict[int, List] = {}
        self.all_tasks_flat: List = []
        self.product_ids: Set[int] = set()
        self.lookup_built = False

    def build_lookup_tables(self, work_schedule):
        """Construye todas las tablas de lookup de una vez - 10x más rápido"""
        start_time = time.time()

        print("🔧 Construyendo lookup tables IFC...")

        # 1. Obtener todas las tareas de una vez
        root_tasks = ifcopenshell.util.sequence.get_root_tasks(work_schedule)
        self.all_tasks_flat = []

        def collect_all_tasks(task):
            self.all_tasks_flat.append(task)
            nested = ifcopenshell.util.sequence.get_nested_tasks(task)
            for subtask in nested:
                collect_all_tasks(subtask)

        for root_task in root_tasks:
            collect_all_tasks(root_task)

        print(f"📊 Encontradas {len(self.all_tasks_flat)} tareas")

        # 2. Pre-computar TODAS las relaciones de una vez
        for task in self.all_tasks_flat:
            task_id = task.id()

            # Outputs de la tarea
            try:
                outputs = list(ifcopenshell.util.sequence.get_task_outputs(task))
                self.task_to_outputs[task_id] = outputs

                for output in outputs:
                    product_id = output.id()
                    self.product_ids.add(product_id)

                    if product_id not in self.product_to_output_tasks:
                        self.product_to_output_tasks[product_id] = []
                    self.product_to_output_tasks[product_id].append(task)
            except:
                self.task_to_outputs[task_id] = []

            # Inputs de la tarea
            try:
                inputs = tool.Sequence.get_task_inputs(task) if hasattr(tool.Sequence, 'get_task_inputs') else []
                if not inputs:
                    inputs = list(ifcopenshell.util.sequence.get_task_inputs(task))
                self.task_to_inputs[task_id] = inputs

                for input_prod in inputs:
                    product_id = input_prod.id()
                    self.product_ids.add(product_id)

                    if product_id not in self.product_to_input_tasks:
                        self.product_to_input_tasks[product_id] = []
                    self.product_to_input_tasks[product_id].append(task)
            except:
                self.task_to_inputs[task_id] = []

        self.lookup_built = True
        elapsed = time.time() - start_time
        print(f"✅ Lookup tables construidas en {elapsed:.2f}s")
        print(f"📈 {len(self.product_ids)} productos, {len(self.all_tasks_flat)} tareas")

    def get_tasks_for_product(self, product_id: int) -> tuple[List, List]:
        """Obtiene tareas de input/output para un producto instantáneamente"""
        if not self.lookup_built:
            return [], []

        output_tasks = self.product_to_output_tasks.get(product_id, [])
        input_tasks = self.product_to_input_tasks.get(product_id, [])
        return input_tasks, output_tasks

    def get_outputs_for_task(self, task_id: int) -> List:
        """Obtiene outputs de una tarea instantáneamente"""
        return self.task_to_outputs.get(task_id, [])

    def get_inputs_for_task(self, task_id: int) -> List:
        """Obtiene inputs de una tarea instantáneamente"""
        return self.task_to_inputs.get(task_id, [])

    def get_all_products(self) -> Set[int]:
        """Obtiene todos los IDs de productos"""
        return self.product_ids.copy()

    def get_all_tasks(self) -> List:
        """Obtiene todas las tareas"""
        return self.all_tasks_flat.copy()

    def invalidate(self):
        """Invalida el lookup"""
        self.product_to_output_tasks.clear()
        self.product_to_input_tasks.clear()
        self.task_to_outputs.clear()
        self.task_to_inputs.clear()
        self.task_hierarchy.clear()
        self.all_tasks_flat.clear()
        self.product_ids.clear()
        self.lookup_built = False


class TaskDateCache:
    """Cache ultra-eficiente para fechas de tareas"""

    def __init__(self):
        self.date_cache: Dict[str, Optional[Any]] = {}

    def get_date(self, task, date_type: str, is_earliest: bool = False, is_latest: bool = False):
        """Obtiene fecha con cache"""
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

    def invalidate(self):
        """Limpia el cache"""
        self.date_cache.clear()


# Instancias globales singleton
_ifc_lookup = IFCLookupOptimizer()
_date_cache = TaskDateCache()

def get_ifc_lookup() -> IFCLookupOptimizer:
    """Obtiene el lookup optimizer global"""
    return _ifc_lookup

def get_date_cache() -> TaskDateCache:
    """Obtiene el cache de fechas global"""
    return _date_cache

def invalidate_all_lookups():
    """Invalida todos los caches y lookups"""
    _ifc_lookup.invalidate()
    _date_cache.invalidate()