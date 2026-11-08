"""Eventos de dominio que consume el módulo 6 y su registro en el outbox.

Se reutilizan los nombres que ya publican los módulos 3 (`sessions/eventos.py`) y 5
(`evaluations/eventos.py`); no se inventa un catálogo paralelo. Correspondencia con el
catálogo del enunciado: CONVOCATORIA_RETIRADA = revocación, CODIGO_REGENERADO = código de
convocatoria regenerado, SESION_MODIFICADA = reprogramación.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.modules.evaluations import eventos as ev5
from app.modules.notifications.models import EventoOutbox
from app.modules.sessions import eventos as ev3

# Claves de `datos` que nunca deben llegar al outbox (defensa en profundidad: los módulos 3 y 5
# no las envían). Un evento con alguna de ellas se rechaza y revierte la operación.
CLAVES_PROHIBIDAS = frozenset({"codigo", "codigo_autorizacion", "clave", "password", "token", "nota", "nota_final"})


@dataclass(frozen=True, slots=True)
class EventoDominio:
    """Hecho ocurrido en el sistema, tal como lo reciben los observadores."""

    id: uuid.UUID
    tipo: str
    sesion_id: uuid.UUID
    ocurrido_en: datetime
    datos: Mapping[str, str] = field(default_factory=dict)

    def uuid_de(self, clave: str) -> uuid.UUID | None:
        valor = self.datos.get(clave)
        try:
            return uuid.UUID(valor) if valor else None
        except ValueError:
            return None

    @property
    def convocatoria_id(self) -> uuid.UUID | None:
        return self.uuid_de("convocatoria_id")

    @property
    def participacion_id(self) -> uuid.UUID | None:
        return self.uuid_de("participacion_id")

    @classmethod
    def desde_outbox(cls, fila: EventoOutbox) -> "EventoDominio":
        return cls(fila.id, fila.tipo, fila.sesion_id, fila.registrado_en, dict(fila.datos or {}))


# Catálogo de los eventos que tienen observadores (el resto se marca procesado sin efectos).
CONVOCATORIA_CREADA = ev3.CONVOCATORIA_CREADA
CONVOCATORIA_REACTIVADA = ev3.CONVOCATORIA_REACTIVADA
CODIGO_REGENERADO = ev3.CODIGO_REGENERADO
CONVOCATORIA_RETIRADA = ev3.CONVOCATORIA_RETIRADA
SESION_MODIFICADA = ev3.SESION_MODIFICADA
SESION_FINALIZADA = ev3.SESION_FINALIZADA
CALIFICACION_REGISTRADA = ev5.CALIFICACION_REGISTRADA
CALIFICACION_ACTUALIZADA = ev5.CALIFICACION_ACTUALIZADA
RETROALIMENTACION_REGISTRADA = ev5.RETROALIMENTACION_REGISTRADA
RESULTADOS_DISPONIBLES = ev5.RESULTADOS_DISPONIBLES


class RegistroEventosSQL:
    """Implementación del puerto `app.core.outbox.RegistroEventos`: INSERT en la transacción en curso."""

    def registrar(self, db: Session, tipo: str, sesion_id: uuid.UUID, datos: Mapping[str, str]) -> None:
        prohibidas = CLAVES_PROHIBIDAS & {k.lower() for k in datos}
        if prohibidas:
            raise ValueError(f"El evento {tipo} incluye datos sensibles: {sorted(prohibidas)}.")
        db.execute(insert(EventoOutbox).values(tipo=tipo, sesion_id=sesion_id, datos={k: str(v) for k, v in datos.items()}))
