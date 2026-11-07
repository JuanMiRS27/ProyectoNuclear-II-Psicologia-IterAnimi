"""Procesador del outbox: reclama eventos pendientes y los distribuye con el publicador Observer.

Cada evento se procesa en SU transacción:

    SELECT ... FOR UPDATE SKIP LOCKED   (otro worker no puede tomarlo)
    SAVEPOINT -> publicar a los observadores -> notificaciones y entregas
    marcar PROCESADO -> COMMIT

Si un observador falla, se revierte el savepoint (no queda ningún aviso a medias), se anota
el intento con un error seguro y se reprograma con espera progresiva; al agotar los intentos
queda FALLIDO para diagnóstico. Un reinicio del worker no pierde nada: lo no confirmado
sigue PENDIENTE.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.clock import Reloj, RelojSistema
from app.core.config import get_settings
from app.modules.notifications.events import EventoDominio
from app.modules.notifications.models import EstadoEventoEnum, EventoOutbox
from app.modules.notifications.observers.avisos_academicos import ObservadorAvisosAcademicos
from app.modules.notifications.observers.convocatorias import ObservadorConvocatorias
from app.modules.notifications.publishers import PublicadorEventos
from app.modules.notifications.repositories import NotificacionRepository
from app.modules.notifications.services.notificacion_service import NotificacionService

logger = logging.getLogger("inter_nos.notificaciones.eventos")
TAMANO_LOTE = 200


def espera_reintento(intentos: int) -> timedelta:
    """Espera progresiva (exponencial) con tope: base, 2·base, 4·base, ..."""
    settings = get_settings()
    segundos = settings.NOTIFICATIONS_RETRY_BASE_SECONDS * 2 ** max(intentos - 1, 0)
    return timedelta(seconds=min(segundos, settings.NOTIFICATIONS_RETRY_MAX_SECONDS))


def crear_publicador(session: Session, ahora: datetime, reloj: Reloj | None = None) -> PublicadorEventos:
    """Composición del Observer: un sujeto y sus dos observadores concretos."""
    servicio = NotificacionService(session, reloj)
    publicador = PublicadorEventos()
    publicador.suscribir(ObservadorConvocatorias(servicio, ahora))
    publicador.suscribir(ObservadorAvisosAcademicos(servicio))
    return publicador


@dataclass(slots=True)
class ResumenEventos:
    procesados: int = 0
    reintentos: int = 0
    fallidos: int = 0
    sin_observadores: list[str] = field(default_factory=list)


class ProcesadorEventosService:
    def __init__(self, session: Session, reloj: Reloj | None = None, fabrica_publicador=crear_publicador) -> None:
        self._session = session
        self._reloj = reloj or RelojSistema()
        self._repo = NotificacionRepository(session)
        self._fabrica = fabrica_publicador

    def procesar_pendientes(self, lote: int = TAMANO_LOTE) -> ResumenEventos:
        resumen = ResumenEventos()
        for _ in range(lote):
            if not self._procesar_uno(resumen):
                break
        return resumen

    def _procesar_uno(self, resumen: ResumenEventos) -> bool:
        ahora = self._reloj.ahora()
        try:
            fila = self._repo.reclamar_evento(ahora)
            if fila is None:
                self._session.rollback()
                return False
            evento = EventoDominio.desde_outbox(fila)
            try:
                with self._session.begin_nested():
                    receptores = self._fabrica(self._session, ahora, self._reloj).publicar(evento)
            except Exception as exc:  # noqa: BLE001 - se registra de forma segura y se reintenta
                self._registrar_fallo(fila, exc, ahora, resumen)
            else:
                fila.estado = EstadoEventoEnum.PROCESADO
                fila.procesado_en = ahora
                fila.ultimo_error = None
                resumen.procesados += 1
                if not receptores:
                    resumen.sin_observadores.append(evento.tipo)
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        return True

    @staticmethod
    def _registrar_fallo(fila: EventoOutbox, exc: Exception, ahora: datetime, resumen: ResumenEventos) -> None:
        fila.intentos += 1
        fila.ultimo_error = f"{type(exc).__name__} al procesar el evento."  # nunca el mensaje: podría llevar datos
        if fila.intentos >= get_settings().NOTIFICATIONS_MAX_ATTEMPTS:
            fila.estado = EstadoEventoEnum.FALLIDO
            fila.proximo_intento_en = None
            resumen.fallidos += 1
        else:
            fila.proximo_intento_en = ahora + espera_reintento(fila.intentos)
            resumen.reintentos += 1
        logger.warning("evento=%s tipo=%s intento=%d fallo=%s", fila.id, fila.tipo, fila.intentos, type(exc).__name__)
