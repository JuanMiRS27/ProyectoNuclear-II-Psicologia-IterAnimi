"""Worker de notificaciones: procesa el outbox (Observer) y envía las entregas (Adapter).

No depende de HTTP. Es seguro ejecutar varias instancias a la vez (FOR UPDATE SKIP LOCKED) y
reiniciarlo en cualquier momento: lo no confirmado sigue pendiente y se retoma.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.bootstrap import configurar_integraciones
from app.core.clock import Reloj, RelojSistema
from app.core.database import SessionLocal
from app.modules.notifications.adapters import ServicioCorreo, crear_servicio_correo
from app.modules.notifications.services.entregas_service import EntregasService, ResumenEntregas
from app.modules.notifications.services.procesador_eventos import ProcesadorEventosService, ResumenEventos

logger = logging.getLogger("inter_nos.workers.notifications")
_SIN_CONFIGURAR = object()


@dataclass(frozen=True, slots=True)
class ResumenPasada:
    eventos: ResumenEventos
    entregas: ResumenEntregas


def ejecutar_una_vez(
    session_factory: Callable[[], Session] = SessionLocal,
    reloj: Reloj | None = None,
    correo: ServicioCorreo | None | object = _SIN_CONFIGURAR,
) -> ResumenPasada:
    """Una pasada: primero los eventos (crean entregas), luego las entregas.

    Sin `correo` explícito se usa el adaptador configurado; con el envío desactivado
    (`NOTIFICATIONS_EMAIL_ENABLED=false`) los avisos internos se crean igual y las entregas
    quedan PENDIENTES. Una configuración de correo incompleta falla aquí, de forma explícita.
    """
    configurar_integraciones()
    reloj = reloj or RelojSistema()
    adaptador = crear_servicio_correo() if correo is _SIN_CONFIGURAR else correo
    with session_factory() as session:
        eventos = ProcesadorEventosService(session, reloj).procesar_pendientes()
    with session_factory() as session:
        entregas = EntregasService(session, adaptador, reloj).procesar_pendientes()  # type: ignore[arg-type]
    logger.info(
        "notificaciones: %d evento(s) procesado(s), %d correo(s) enviado(s), %d reintento(s), %d fallido(s), %d cancelado(s)",
        eventos.procesados, entregas.enviadas, entregas.reintentos, entregas.fallidas, entregas.canceladas,
    )
    return ResumenPasada(eventos, entregas)


def ejecutar_periodicamente(
    intervalo_segundos: int, reloj: Reloj | None = None, detener: threading.Event | None = None
) -> None:
    correo = crear_servicio_correo()  # valida la configuración una vez, al arrancar
    detener = detener or threading.Event()
    while not detener.is_set():
        try:
            ejecutar_una_vez(reloj=reloj, correo=correo)
        except Exception:  # noqa: BLE001 - se registra y se reintenta en la siguiente pasada
            logger.exception("fallo en la pasada de notificaciones")
        detener.wait(intervalo_segundos)


def iniciar_en_segundo_plano(intervalo_segundos: int) -> threading.Event:
    """Lanza el worker en un hilo daemon (uso desde la API). Devuelve el evento para detenerlo.

    La configuración de correo se valida aquí, en el hilo de arranque: si está incompleta, la
    API no arranca con un worker que fallaría en silencio.
    """
    crear_servicio_correo()
    detener = threading.Event()
    hilo = threading.Thread(
        target=ejecutar_periodicamente,
        kwargs={"intervalo_segundos": intervalo_segundos, "detener": detener},
        name="worker-notificaciones",
        daemon=True,
    )
    hilo.start()
    logger.info("worker de notificaciones integrado iniciado (cada %d s)", intervalo_segundos)
    return detener
