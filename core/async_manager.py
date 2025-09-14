# EN: core/async_manager.py
import threading
import queue
import time

# Usamos colas porque son seguras para la comunicación entre hilos
task_queue = queue.Queue()
result_queue = queue.Queue()

# Diccionario global para que la UI sepa el estado del proceso
task_status = {
    "running": False,
    "progress": 0.0,
    "message": "Listo"
}

def background_worker():
    """
    Esta es la función que se ejecuta constantemente en el hilo secundario.
    Espera tareas en la cola, las ejecuta y pone el resultado en la cola de resultados.
    """
    while True:
        try:
            func, args, kwargs = task_queue.get()

            task_status["running"] = True
            task_status["message"] = "Iniciando proceso..."
            task_status["progress"] = 0.0

            # Ejecuta la función pesada (nuestro horneado de atributos)
            result = func(*args, **kwargs)
            result_queue.put(('SUCCESS', result))
        except Exception as e:
            result_queue.put(('ERROR', str(e)))
        finally:
            task_status["running"] = False
            task_status["message"] = "Proceso finalizado"
            task_status["progress"] = 100.0
            task_queue.task_done()

# Variable para controlar si ya se inició el hilo
_worker_started = False

def ensure_worker_started():
    """Inicia el hilo de trabajo una sola vez"""
    global _worker_started
    if not _worker_started:
        worker_thread = threading.Thread(target=background_worker, daemon=True)
        worker_thread.start()
        _worker_started = True

def submit_task(func, *args, **kwargs):
    """
    La función que usamos para enviar un trabajo al hilo secundario.
    """
    ensure_worker_started()

    if task_status["running"]:
        return False

    task_queue.put((func, args, kwargs))
    return True

def update_progress(percent, message=""):
    """Actualiza el progreso de la tarea actual"""
    task_status["progress"] = percent
    if message:
        task_status["message"] = message

def is_task_running():
    """Verifica si hay una tarea ejecutándose"""
    return task_status["running"]

def get_task_status():
    """Obtiene el estado actual de la tarea"""
    return task_status.copy()