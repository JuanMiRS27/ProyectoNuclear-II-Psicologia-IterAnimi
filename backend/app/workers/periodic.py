"""Workers ligeros dentro del proceso de la API para despliegues de una instancia."""

import logging
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


def iniciar_en_segundo_plano(nombre: str, intervalo: float, ejecutar: Callable[[], object]) -> threading.Event:
    detener = threading.Event()

    def procesar() -> None:
        while not detener.is_set():
            try:
                ejecutar()
            except Exception:
                logger.exception("Fallo en el worker %s; se reintentara en la siguiente pasada", nombre)
            detener.wait(intervalo)

    threading.Thread(target=procesar, name=nombre, daemon=True).start()
    return detener
