"""Acceso a datos del módulo 6. Sin reglas de negocio.

Los procesadores reclaman trabajo con `FOR UPDATE SKIP LOCKED`: varias ejecuciones del
worker a la vez nunca toman el mismo evento ni la misma entrega.
"""

import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload

from app.modules.notifications.models import (
    EntregaCorreo,
    EstadoEntregaEnum,
    EstadoEventoEnum,
    EventoOutbox,
    Notificacion,
    TipoNotificacionEnum,
)
from app.modules.participations.models import Participacion
from app.modules.sessions.models import Convocatoria, Sesion


class NotificacionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Outbox ----------------------------------------------------------------------------

    def reclamar_evento(self, ahora: datetime) -> EventoOutbox | None:
        stmt = (
            select(EventoOutbox)
            .where(
                EventoOutbox.estado == EstadoEventoEnum.PENDIENTE,
                or_(EventoOutbox.proximo_intento_en.is_(None), EventoOutbox.proximo_intento_en <= ahora),
            )
            .order_by(EventoOutbox.registrado_en, EventoOutbox.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return self._session.scalars(stmt.execution_options(populate_existing=True)).first()

    def evento(self, evento_id: uuid.UUID) -> EventoOutbox | None:
        return self._session.get(EventoOutbox, evento_id)

    # --- Notificaciones y entregas (idempotentes) ------------------------------------------

    def insertar_notificacion(self, **valores) -> uuid.UUID | None:
        """INSERT ... ON CONFLICT (clave_idempotencia) DO NOTHING: devuelve el id, o None si ya existía."""
        stmt = (
            insert(Notificacion)
            .values(**valores)
            .on_conflict_do_nothing(index_elements=[Notificacion.clave_idempotencia])
            .returning(Notificacion.id)
        )
        return self._session.execute(stmt).scalar()

    def insertar_entrega(self, notificacion_id: uuid.UUID, huella_codigo: str | None) -> None:
        stmt = (
            insert(EntregaCorreo)
            .values(notificacion_id=notificacion_id, huella_codigo=huella_codigo)
            .on_conflict_do_nothing(index_elements=[EntregaCorreo.notificacion_id])
        )
        self._session.execute(stmt)

    def existe_clave(self, clave: str) -> bool:
        return self._session.scalar(select(func.count()).where(Notificacion.clave_idempotencia == clave)) > 0

    def cancelar_entregas(
        self, convocatorias: Iterable[uuid.UUID], tipos: Iterable[TipoNotificacionEnum], motivo: str, ahora: datetime
    ) -> int:
        """Cancela las entregas PENDIENTES (no las que un worker está enviando) de esos avisos."""
        ids = list(convocatorias)
        if not ids:
            return 0
        sub = select(Notificacion.id).where(Notificacion.convocatoria_id.in_(ids), Notificacion.tipo.in_(list(tipos)))
        stmt = (
            update(EntregaCorreo)
            .where(EntregaCorreo.estado == EstadoEntregaEnum.PENDIENTE, EntregaCorreo.notificacion_id.in_(sub))
            .values(estado=EstadoEntregaEnum.CANCELADA, ultimo_error=motivo, proximo_intento_en=None, ultimo_intento_en=ahora)
        )
        return self._session.execute(stmt).rowcount or 0

    def algun_codigo_enviado(self, convocatoria_id: uuid.UUID) -> bool:
        """¿Salió (o está saliendo) algún correo con código para esta convocatoria?"""
        stmt = (
            select(func.count())
            .select_from(EntregaCorreo)
            .join(Notificacion, EntregaCorreo.notificacion_id == Notificacion.id)
            .where(
                Notificacion.convocatoria_id == convocatoria_id,
                Notificacion.tipo.in_([TipoNotificacionEnum.CONVOCATORIA, TipoNotificacionEnum.CODIGO_REGENERADO]),
                EntregaCorreo.estado.in_([EstadoEntregaEnum.ENVIADA, EstadoEntregaEnum.EN_PROCESO]),
            )
        )
        return (self._session.scalar(stmt) or 0) > 0

    # --- Entregas de correo -------------------------------------------------------------------

    def reclamar_entrega(self, ahora: datetime) -> EntregaCorreo | None:
        """PENDIENTE disponible, o EN_PROCESO cuya reserva venció (el worker que la tenía cayó)."""
        stmt = (
            select(EntregaCorreo)
            .where(
                or_(
                    (EntregaCorreo.estado == EstadoEntregaEnum.PENDIENTE)
                    & or_(EntregaCorreo.proximo_intento_en.is_(None), EntregaCorreo.proximo_intento_en <= ahora),
                    (EntregaCorreo.estado == EstadoEntregaEnum.EN_PROCESO) & (EntregaCorreo.proximo_intento_en <= ahora),
                )
            )
            .order_by(EntregaCorreo.creada_en, EntregaCorreo.id)
            .limit(1)
            .with_for_update(skip_locked=True, of=EntregaCorreo)
        )
        return self._session.scalars(stmt.execution_options(populate_existing=True)).first()

    def entrega_bloqueada(self, entrega_id: uuid.UUID) -> EntregaCorreo | None:
        stmt = select(EntregaCorreo).where(EntregaCorreo.id == entrega_id).with_for_update()
        return self._session.scalars(stmt.execution_options(populate_existing=True)).first()

    def listar_entregas(self, estado: EstadoEntregaEnum | None, skip: int, limit: int) -> tuple[list[EntregaCorreo], int]:
        base = select(EntregaCorreo)
        if estado is not None:
            base = base.where(EntregaCorreo.estado == estado)
        total = self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = base.options(joinedload(EntregaCorreo.notificacion)).order_by(EntregaCorreo.creada_en.desc(), EntregaCorreo.id)
        return list(self._session.scalars(stmt.offset(skip).limit(limit))), total

    # --- Consultas del destinatario ------------------------------------------------------------

    def _propias(self, destinatario_id: uuid.UUID, convocatoria_id: uuid.UUID | None):
        stmt = select(Notificacion).where(Notificacion.destinatario_id == destinatario_id)
        if convocatoria_id is not None:
            stmt = stmt.where(Notificacion.convocatoria_id == convocatoria_id)
        return stmt

    def listar(
        self, destinatario_id: uuid.UUID, convocatoria_id: uuid.UUID | None, solo_no_leidas: bool, skip: int, limit: int
    ) -> tuple[list[Notificacion], int]:
        stmt = self._propias(destinatario_id, convocatoria_id)
        if solo_no_leidas:
            stmt = stmt.where(Notificacion.leida.is_(False))
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = stmt.order_by(Notificacion.creada_en.desc(), Notificacion.id).offset(skip).limit(limit)
        return list(self._session.scalars(stmt)), total

    def contar_no_leidas(self, destinatario_id: uuid.UUID, convocatoria_id: uuid.UUID | None) -> int:
        stmt = self._propias(destinatario_id, convocatoria_id).where(Notificacion.leida.is_(False))
        return self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    def propia(
        self, notificacion_id: uuid.UUID, destinatario_id: uuid.UUID, convocatoria_id: uuid.UUID | None, *, bloquear: bool = False
    ) -> Notificacion | None:
        stmt = self._propias(destinatario_id, convocatoria_id).where(Notificacion.id == notificacion_id)
        if bloquear:
            stmt = stmt.with_for_update()
        return self._session.scalars(stmt.execution_options(populate_existing=True)).first()

    # --- Estado académico que consultan observadores y entregas -----------------------------------

    def convocatoria(self, convocatoria_id: uuid.UUID) -> Convocatoria | None:
        stmt = select(Convocatoria).where(Convocatoria.id == convocatoria_id).execution_options(populate_existing=True)
        return self._session.scalars(stmt).first()

    def sesion(self, sesion_id: uuid.UUID) -> Sesion | None:
        return self._session.scalars(select(Sesion).where(Sesion.id == sesion_id).execution_options(populate_existing=True)).first()

    def convocatorias_activas(self, sesion_id: uuid.UUID) -> list[Convocatoria]:
        stmt = (
            select(Convocatoria)
            .where(Convocatoria.sesion_id == sesion_id, Convocatoria.revocada_en.is_(None))
            .order_by(Convocatoria.id)
        )
        return list(self._session.scalars(stmt))

    def convocatorias_de_sesion(self, sesion_id: uuid.UUID) -> list[Convocatoria]:
        """Todas, también las revocadas."""
        return list(self._session.scalars(select(Convocatoria).where(Convocatoria.sesion_id == sesion_id)))

    def participacion(self, participacion_id: uuid.UUID) -> Participacion | None:
        stmt = select(Participacion).where(Participacion.id == participacion_id).execution_options(populate_existing=True)
        return self._session.scalars(stmt).first()

    def participaciones(self, convocatoria_id: uuid.UUID) -> list[Participacion]:
        stmt = select(Participacion).where(Participacion.convocatoria_id == convocatoria_id).order_by(Participacion.numero_intento)
        return list(self._session.scalars(stmt.execution_options(populate_existing=True)))


__all__ = ["NotificacionRepository"]
