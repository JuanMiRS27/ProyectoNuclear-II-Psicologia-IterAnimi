"""Acceso a datos del módulo 5. Sin reglas académicas: solo consultas, bloqueos y escritura.

Respeta el orden de bloqueo común del sistema: sesion -> convocatoria -> participacion.
La sesión se bloquea en modo compartido (FOR SHARE): un cierre de sesión concurrente, que
la bloquea en exclusiva, se ejecuta antes o después de la evaluación, nunca intercalado.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.participations.models import EstadoParticipacionEnum, Participacion
from app.modules.sessions.models import Convocatoria, Sesion


class EvaluacionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Lectura ----------------------------------------------------------------------------

    def sesion_del_docente(self, sesion_id: uuid.UUID, docente_id: uuid.UUID, *, bloquear: bool = False) -> Sesion | None:
        stmt = select(Sesion).where(Sesion.id == sesion_id, Sesion.docente_id == docente_id)
        if bloquear:
            stmt = stmt.with_for_update(read=True, of=Sesion)
        return self._session.scalars(stmt.execution_options(populate_existing=True)).first()

    def participacion_con_sesion(self, participacion_id: uuid.UUID) -> tuple[Participacion, Sesion] | None:
        stmt = (
            select(Participacion, Sesion)
            .join(Convocatoria, Participacion.convocatoria_id == Convocatoria.id)
            .join(Sesion, Convocatoria.sesion_id == Sesion.id)
            .where(Participacion.id == participacion_id)
        )
        fila = self._session.execute(stmt).first()
        return (fila[0], fila[1]) if fila else None

    def participaciones_de_sesion(self, sesion_id: uuid.UUID) -> list[Participacion]:
        """Todas (incluidas las EN_PROGRESO), con convocatoria y estudiante, por estudiante e intento."""
        stmt = (
            select(Participacion)
            .join(Convocatoria, Participacion.convocatoria_id == Convocatoria.id)
            .where(Convocatoria.sesion_id == sesion_id)
            .options(joinedload(Participacion.convocatoria).joinedload(Convocatoria.estudiante))
            .order_by(Convocatoria.estudiante_id, Participacion.numero_intento)
        )
        return list(self._session.scalars(stmt))

    def de_convocatoria(self, convocatoria_id: uuid.UUID) -> list[Participacion]:
        stmt = select(Participacion).where(Participacion.convocatoria_id == convocatoria_id).order_by(Participacion.numero_intento)
        return list(self._session.scalars(stmt.execution_options(populate_existing=True)))

    # --- Bloqueo y escritura ------------------------------------------------------------------------

    def bloquear_cerradas_de_sesion(self, sesion_id: uuid.UUID) -> list[Participacion]:
        """FOR UPDATE en orden de id: dos procesos concurrentes se serializan sin interbloqueos."""
        stmt = (
            select(Participacion)
            .join(Convocatoria, Participacion.convocatoria_id == Convocatoria.id)
            .where(Convocatoria.sesion_id == sesion_id, Participacion.estado != EstadoParticipacionEnum.EN_PROGRESO)
            .order_by(Participacion.id)
            .with_for_update(of=Participacion)
        )
        return list(self._session.scalars(stmt.execution_options(populate_existing=True)))

    def bloquear_participacion(self, participacion_id: uuid.UUID) -> Participacion | None:
        stmt = select(Participacion).where(Participacion.id == participacion_id).with_for_update()
        return self._session.scalars(stmt.execution_options(populate_existing=True)).first()

    def registrar_nota(self, participacion: Participacion, nota: Decimal | None) -> None:
        """Solo cambia `nota_final`; los disparadores del módulo 4 protegen el resto del historial."""
        participacion.nota_final = nota
        self._session.flush()

    def registrar_retroalimentacion(self, participacion: Participacion, texto: str | None) -> None:
        participacion.retroalimentacion_general = texto
        self._session.flush()


__all__ = ["EvaluacionRepository"]
