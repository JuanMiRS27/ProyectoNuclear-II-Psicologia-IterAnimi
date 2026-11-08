"""Punto de integración con el módulo 6 (Notificaciones: Observer y Adapter).

Igual que el módulo 3 (`app/modules/sessions/eventos.py`), los servicios del módulo 5
publican hechos de dominio a través de un puerto, SOLO después de confirmar la transacción.
Aquí existe únicamente la implementación nula (deja rastro en el log); el módulo 6 aportará
la real sin modificar estos servicios.

Una recalificación que no cambia la nota no publica nada (no hay eventos duplicados).
Los eventos no incluyen la nota ni la retroalimentación: el módulo 6 las consultará por id.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger("inter_nos.evaluaciones.eventos")

CALIFICACION_REGISTRADA = "CALIFICACION_REGISTRADA"
CALIFICACION_ACTUALIZADA = "CALIFICACION_ACTUALIZADA"
RETROALIMENTACION_REGISTRADA = "RETROALIMENTACION_REGISTRADA"
RESULTADOS_DISPONIBLES = "RESULTADOS_DISPONIBLES"


@dataclass(frozen=True, slots=True)
class EventoEvaluacion:
    tipo: str
    sesion_id: uuid.UUID
    datos: dict[str, str] = field(default_factory=dict)


class PublicadorEventosEvaluacion(Protocol):
    def publicar(self, evento: EventoEvaluacion) -> None: ...


class PublicadorNulo:
    def publicar(self, evento: EventoEvaluacion) -> None:
        logger.info("evento=%s sesion=%s datos=%s", evento.tipo, evento.sesion_id, evento.datos)


_publicador: PublicadorEventosEvaluacion = PublicadorNulo()


def configurar(publicador: PublicadorEventosEvaluacion) -> None:
    """El módulo 6 registrará aquí su publicador real (desde `app/bootstrap.py`)."""
    global _publicador
    _publicador = publicador


def publicador() -> PublicadorEventosEvaluacion:
    return _publicador


def evento_participacion(tipo: str, sesion_id: uuid.UUID, participacion_id: uuid.UUID, convocatoria_id: uuid.UUID) -> EventoEvaluacion:
    return EventoEvaluacion(tipo, sesion_id, {"participacion_id": str(participacion_id), "convocatoria_id": str(convocatoria_id)})
