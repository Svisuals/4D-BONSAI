# Batch Processor for Blender Operations
# Procesa múltiples objetos en lotes para máximo rendimiento

import bpy
import time
from typing import List, Dict, Tuple, Any
from collections import defaultdict

class BlenderBatchProcessor:
    """Procesador batch ultra-eficiente para operaciones masivas en Blender"""

    def __init__(self, batch_size: int = 500):
        self.batch_size = batch_size
        self.visibility_operations = []
        self.color_operations = []
        self.keyframe_operations = []

    def add_visibility_operation(self, obj, frame: int, hide_viewport: bool, hide_render: bool):
        """Añade operación de visibilidad al batch"""
        self.visibility_operations.append({
            'obj': obj,
            'frame': frame,
            'hide_viewport': hide_viewport,
            'hide_render': hide_render
        })

    def add_color_operation(self, obj, frame: int, color: Tuple[float, float, float, float]):
        """Añade operación de color al batch"""
        self.color_operations.append({
            'obj': obj,
            'frame': frame,
            'color': color
        })

    def add_keyframe_operation(self, obj, frame: int, data_path: str, value: Any):
        """Añade operación de keyframe al batch"""
        self.keyframe_operations.append({
            'obj': obj,
            'frame': frame,
            'data_path': data_path,
            'value': value
        })

    def execute_visibility_batch(self):
        """Ejecuta todas las operaciones de visibilidad en batch"""
        if not self.visibility_operations:
            return

        start_time = time.time()

        # Agrupar por frame para minimizar cambios de contexto
        operations_by_frame = defaultdict(list)
        for op in self.visibility_operations:
            operations_by_frame[op['frame']].append(op)

        total_ops = 0
        for frame, ops in operations_by_frame.items():
            bpy.context.scene.frame_set(frame)

            # Procesar en lotes
            for i in range(0, len(ops), self.batch_size):
                batch = ops[i:i + self.batch_size]

                for op in batch:
                    obj = op['obj']
                    obj.hide_viewport = op['hide_viewport']
                    obj.hide_render = op['hide_render']

                total_ops += len(batch)

        elapsed = time.time() - start_time
        print(f"🚀 BATCH: {total_ops} ops de visibilidad en {elapsed:.2f}s")
        self.visibility_operations.clear()

    def execute_color_batch(self):
        """Ejecuta todas las operaciones de color en batch"""
        if not self.color_operations:
            return

        start_time = time.time()

        # Agrupar por frame
        operations_by_frame = defaultdict(list)
        for op in self.color_operations:
            operations_by_frame[op['frame']].append(op)

        total_ops = 0
        for frame, ops in operations_by_frame.items():
            bpy.context.scene.frame_set(frame)

            for i in range(0, len(ops), self.batch_size):
                batch = ops[i:i + self.batch_size]

                for op in batch:
                    op['obj'].color = op['color']

                total_ops += len(batch)

        elapsed = time.time() - start_time
        print(f"🚀 BATCH: {total_ops} ops de color en {elapsed:.2f}s")
        self.color_operations.clear()

    def execute_keyframe_batch(self):
        """Ejecuta todas las operaciones de keyframe en batch"""
        if not self.keyframe_operations:
            return

        start_time = time.time()

        # Agrupar por objeto y data_path para keyframes consecutivos
        grouped_ops = defaultdict(lambda: defaultdict(list))
        for op in self.keyframe_operations:
            obj_key = op['obj'].name
            grouped_ops[obj_key][op['data_path']].append(op)

        total_ops = 0
        for obj_name, data_paths in grouped_ops.items():
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                continue

            for data_path, ops in data_paths.items():
                # Ordenar por frame para keyframes secuenciales eficientes
                ops.sort(key=lambda x: x['frame'])

                for op in ops:
                    frame = op['frame']
                    value = op['value']

                    # Establecer valor
                    try:
                        if data_path == 'color':
                            obj.color = value
                        elif data_path == 'hide_viewport':
                            obj.hide_viewport = value
                        elif data_path == 'hide_render':
                            obj.hide_render = value

                        # Insertar keyframe
                        obj.keyframe_insert(data_path=data_path, frame=frame)
                        total_ops += 1
                    except Exception as e:
                        print(f"⚠️ Error keyframe {obj_name}.{data_path}@{frame}: {e}")

        elapsed = time.time() - start_time
        print(f"🚀 BATCH: {total_ops} keyframes en {elapsed:.2f}s")
        self.keyframe_operations.clear()

    def execute_all_batches(self):
        """Ejecuta todos los batches pendientes"""
        self.execute_visibility_batch()
        self.execute_color_batch()
        self.execute_keyframe_batch()

    def clear_all(self):
        """Limpia todos los batches pendientes"""
        self.visibility_operations.clear()
        self.color_operations.clear()
        self.keyframe_operations.clear()


class VisibilityBatchOptimizer:
    """Optimizador específico para operaciones de visibilidad masivas"""

    @staticmethod
    def batch_hide_objects(objects_to_hide: List, objects_to_show: List):
        """Oculta/muestra objetos en batch ultra-eficiente"""
        start_time = time.time()

        # Ocultar en batch
        for obj in objects_to_hide:
            obj.hide_viewport = True
            obj.hide_render = True

        # Mostrar en batch
        for obj in objects_to_show:
            obj.hide_viewport = False
            obj.hide_render = False

        elapsed = time.time() - start_time
        total = len(objects_to_hide) + len(objects_to_show)
        print(f"🚀 VISIBILITY BATCH: {total} objetos en {elapsed:.2f}s")

    @staticmethod
    def batch_set_colors(objects_with_colors: List[Tuple]):
        """Establece colores en batch (obj, color)"""
        start_time = time.time()

        for obj, color in objects_with_colors:
            obj.color = color

        elapsed = time.time() - start_time
        print(f"🚀 COLOR BATCH: {len(objects_with_colors)} colores en {elapsed:.2f}s")