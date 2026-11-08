"""Esquemas del módulo 6.

Construidos campo a campo: una notificación muestra solo su propio contenido seguro, y una
entrega no expone la dirección de correo ni el mensaje enviado.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.notifications.models import EntregaCorreo, EstadoEntregaEnum, Notificacion, TipoNotificacionEnum


class NotificacionRead(BaseModel):
    id: uuid.UUID
    tipo: TipoNotificacionEnum
    titulo: str
    mensaje: str
    convocatoria_id: uuid.UUID
    participacion_id: uuid.UUID | None
    creada_en: datetime
    leida: bool
    leida_en: datetime | None

    @classmethod
    def de(cls, n: Notificacion) -> "NotificacionRead":
        return cls(
            id=n.id, tipo=n.tipo, titulo=n.titulo, mensaje=n.mensaje, convocatoria_id=n.convocatoria_id,
            participacion_id=n.participacion_id, creada_en=n.creada_en, leida=n.leida, leida_en=n.leida_en,
        )


class NotificacionList(BaseModel):
    items: list[NotificacionRead]
    total: int
    skip: int
    limit: int


class NoLeidasRead(BaseModel):
    no_leidas: int


class EntregaRead(BaseModel):
    id: uuid.UUID
    notificacion_id: uuid.UUID
    tipo: TipoNotificacionEnum
    destinatario_id: uuid.UUID
    estado: EstadoEntregaEnum
    intentos: int
    creada_en: datetime
    ultimo_intento_en: datetime | None
    proximo_intento_en: datetime | None
    enviada_en: datetime | None
    ultimo_error: str | None

    @classmethod
    def de(cls, e: EntregaCorreo) -> "EntregaRead":
        return cls(
            id=e.id, notificacion_id=e.notificacion_id, tipo=e.notificacion.tipo, destinatario_id=e.notificacion.destinatario_id,
            estado=e.estado, intentos=e.intentos, creada_en=e.creada_en, ultimo_intento_en=e.ultimo_intento_en,
            proximo_intento_en=e.proximo_intento_en, enviada_en=e.enviada_en, ultimo_error=e.ultimo_error,
        )


class EntregaList(BaseModel):
    items: list[EntregaRead]
    total: int
    skip: int
    limit: int
