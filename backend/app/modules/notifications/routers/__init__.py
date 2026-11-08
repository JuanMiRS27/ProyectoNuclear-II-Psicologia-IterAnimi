"""Rutas del módulo 6. Ninguna crea notificaciones ni envía correos: eso solo ocurre como
consecuencia de operaciones académicas confirmadas (outbox -> observadores -> worker)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.core.database import OFFSET_MAXIMO
from app.modules.auth.schemas import MessageResponse
from app.modules.notifications.dependencies import ActorDep, AdminUser, EntregasServiceDep, NotificacionServiceDep
from app.modules.notifications.models import EstadoEntregaEnum
from app.modules.notifications.schemas import EntregaList, EntregaRead, NoLeidasRead, NotificacionList, NotificacionRead

router = APIRouter()
NO_STORE = {"Cache-Control": "no-store"}
_N = ["Notificaciones"]
_E = ["Entregas de correo"]


def _r(*codigos: int) -> dict:
    textos = {
        401: "No autenticado, o token inválido, expirado o revocado.",
        403: "Se requiere rol ADMINISTRADOR.",
        404: "Inexistente o de otro usuario.",
        409: "Solo se reintentan entregas FALLIDAS.",
    }
    return {c: {"model": MessageResponse, "description": textos[c]} for c in codigos}


@router.get("/notifications", response_model=NotificacionList, tags=_N, summary="Mis notificaciones", responses=_r(401))
def list_notifications(
    actor: ActorDep,
    service: NotificacionServiceDep,
    response: Response,
    no_leidas: bool = False,
    skip: Annotated[int, Query(ge=0, le=OFFSET_MAXIMO)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificacionList:
    response.headers.update(NO_STORE)
    items, total = service.listar(actor.usuario_id, actor.convocatoria_id, solo_no_leidas=no_leidas, skip=skip, limit=limit)
    return NotificacionList(items=[NotificacionRead.de(n) for n in items], total=total, skip=skip, limit=limit)


@router.get("/notifications/unread-count", response_model=NoLeidasRead, tags=_N, summary="Cantidad sin leer", responses=_r(401))
def unread_count(actor: ActorDep, service: NotificacionServiceDep, response: Response) -> NoLeidasRead:
    response.headers.update(NO_STORE)
    return NoLeidasRead(no_leidas=service.contar_no_leidas(actor.usuario_id, actor.convocatoria_id))


@router.get(
    "/notifications/{notification_id}", response_model=NotificacionRead, tags=_N, summary="Una notificación propia", responses=_r(401, 404)
)
def get_notification(notification_id: uuid.UUID, actor: ActorDep, service: NotificacionServiceDep, response: Response) -> NotificacionRead:
    response.headers.update(NO_STORE)
    return NotificacionRead.de(service.obtener(notification_id, actor.usuario_id, actor.convocatoria_id))


@router.patch(
    "/notifications/{notification_id}/read", response_model=NotificacionRead, tags=_N,
    summary="Marcar como leída (idempotente)", responses=_r(401, 404),
)
def mark_read(notification_id: uuid.UUID, actor: ActorDep, service: NotificacionServiceDep) -> NotificacionRead:
    return NotificacionRead.de(service.marcar_leida(notification_id, actor.usuario_id, actor.convocatoria_id))


@router.get(
    "/notification-deliveries", response_model=EntregaList, tags=_E,
    summary="Estado de las entregas de correo (administración)", responses=_r(401, 403),
)
def list_deliveries(
    _admin: AdminUser,
    service: EntregasServiceDep,
    estado: EstadoEntregaEnum | None = None,
    skip: Annotated[int, Query(ge=0, le=OFFSET_MAXIMO)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EntregaList:
    items, total = service.listar(estado, skip, limit)
    return EntregaList(items=[EntregaRead.de(e) for e in items], total=total, skip=skip, limit=limit)


@router.post(
    "/notification-deliveries/{delivery_id}/retry", response_model=EntregaRead, tags=_E,
    summary="Reintentar una entrega FALLIDA (se revalida antes de enviar)", responses=_r(401, 403, 404, 409),
)
def retry_delivery(delivery_id: uuid.UUID, _admin: AdminUser, service: EntregasServiceDep) -> EntregaRead:
    return EntregaRead.de(service.reintentar(delivery_id))
