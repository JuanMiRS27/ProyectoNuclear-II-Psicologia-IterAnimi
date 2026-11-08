"""Modelo relacional del módulo 6 (migración 0011).

Tres tablas con responsabilidades separadas:

- `evento_outbox`: hechos de dominio confirmados por los módulos 3 y 5 en SU transacción
  (Transactional Outbox). Solo identificadores y textos no sensibles.
- `notificacion`: aviso interno para UN destinatario (lo que ve en la plataforma). Mensaje
  seguro: sin códigos de autorización, notas ni datos de otros estudiantes.
- `entrega_correo`: intento de comunicar una notificación por correo, con su estado,
  reintentos y error seguro. Existir una notificación no implica que el correo se envió.

El contenido del correo NO se guarda: se genera en el momento del envío con los datos
vigentes (y el código vigente, descifrado solo entonces). Ninguna FK borra en cascada.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.auth.models import Usuario

LONGITUD_ERROR = 300


class EstadoEventoEnum(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    PROCESADO = "PROCESADO"
    FALLIDO = "FALLIDO"


class TipoNotificacionEnum(str, enum.Enum):
    CONVOCATORIA = "CONVOCATORIA"  # nueva convocatoria o reactivación (correo con código)
    CODIGO_REGENERADO = "CODIGO_REGENERADO"  # correo con el código NUEVO
    REPROGRAMACION = "REPROGRAMACION"  # cambio de programación de la sesión
    REVOCACION = "REVOCACION"  # pérdida de acceso
    RESULTADOS_DISPONIBLES = "RESULTADOS_DISPONIBLES"
    CALIFICACION_ACTUALIZADA = "CALIFICACION_ACTUALIZADA"
    RETROALIMENTACION = "RETROALIMENTACION"  # solo interna


class EstadoEntregaEnum(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    EN_PROCESO = "EN_PROCESO"
    ENVIADA = "ENVIADA"
    FALLIDA = "FALLIDA"
    CANCELADA = "CANCELADA"


def _enum(cls, nombre: str) -> Enum:
    return Enum(cls, name=nombre, values_callable=lambda c: [m.value for m in c])


class EventoOutbox(Base):
    __tablename__ = "evento_outbox"
    __table_args__ = (
        CheckConstraint("intentos >= 0", name="intentos_no_negativos"),
        CheckConstraint("(estado = 'PROCESADO') = (procesado_en IS NOT NULL)", name="procesado_segun_estado"),
        # Cola de pendientes: el worker la recorre en orden de llegada.
        Index("ix_evento_outbox_pendientes", "registrado_en", postgresql_where=text("estado = 'PENDIENTE'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    # RESTRICT: el historial de eventos no impide nada que hoy esté permitido (las sesiones no se borran).
    sesion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sesion.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # Hora de la transacción que lo registró (now() de PostgreSQL).
    registrado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    estado: Mapped[EstadoEventoEnum] = mapped_column(
        _enum(EstadoEventoEnum, "estado_evento_outbox"), nullable=False, server_default=text("'PENDIENTE'")
    )
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    proximo_intento_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    procesado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ultimo_error: Mapped[str | None] = mapped_column(String(LONGITUD_ERROR), nullable=True)


class Notificacion(Base):
    __tablename__ = "notificacion"
    __table_args__ = (
        CheckConstraint("(leida) = (leida_en IS NOT NULL)", name="lectura_coherente"),
        CheckConstraint("length(btrim(titulo)) > 0", name="titulo_no_vacio"),
        CheckConstraint(
            "tipo NOT IN ('CALIFICACION_ACTUALIZADA', 'RETROALIMENTACION') OR participacion_id IS NOT NULL",
            name="participacion_segun_tipo",
        ),
        Index("ix_notificacion_destinatario_creada", "destinatario_id", "creada_en"),
        Index("ix_notificacion_no_leidas", "destinatario_id", postgresql_where=text("NOT leida")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    destinatario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False
    )
    tipo: Mapped[TipoNotificacionEnum] = mapped_column(_enum(TipoNotificacionEnum, "tipo_notificacion"), nullable=False)
    # Origen académico: siempre una convocatoria; la participación cuando el aviso es de un intento.
    convocatoria_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("convocatoria.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    participacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participacion.id", ondelete="RESTRICT"), nullable=True
    )
    evento_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evento_outbox.id", ondelete="RESTRICT"), nullable=True
    )
    # Idempotencia: reprocesar un evento no duplica la notificación.
    clave_idempotencia: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    leida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    leida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    destinatario: Mapped[Usuario] = relationship()
    entrega: Mapped["EntregaCorreo | None"] = relationship(back_populates="notificacion", uselist=False)


class EntregaCorreo(Base):
    __tablename__ = "entrega_correo"
    __table_args__ = (
        CheckConstraint("intentos >= 0", name="intentos_no_negativos"),
        CheckConstraint("(estado = 'ENVIADA') = (enviada_en IS NOT NULL)", name="enviada_segun_estado"),
        Index(
            "ix_entrega_correo_pendientes",
            "proximo_intento_en",
            postgresql_where=text("estado IN ('PENDIENTE', 'EN_PROCESO')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    # UNIQUE: como máximo un correo por notificación.
    notificacion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notificacion.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    estado: Mapped[EstadoEntregaEnum] = mapped_column(
        _enum(EstadoEntregaEnum, "estado_entrega_correo"), nullable=False, server_default=text("'PENDIENTE'")
    )
    # HMAC del código CIFRADO vigente al preparar la entrega (no revela el código). Si al enviar
    # ya no coincide, el código se regeneró y la entrega se cancela.
    huella_codigo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ultimo_intento_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # NULL = disponible ya. En EN_PROCESO marca el vencimiento de la reserva del worker.
    proximo_intento_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enviada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ultimo_error: Mapped[str | None] = mapped_column(String(LONGITUD_ERROR), nullable=True)

    notificacion: Mapped[Notificacion] = relationship(back_populates="entrega")
