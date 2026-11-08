"""Dependencias del módulo 6: quién consulta notificaciones y con qué alcance.

Se reutiliza la autenticación existente, sin crear otra:

| Token (`type`)    | Quién                    | Alcance de las notificaciones                      |
|-------------------|--------------------------|----------------------------------------------------|
| `access`          | Docente o administrador  | Las propias                                        |
| `student`         | Estudiante (sesión EN_CURSO) | Las propias de la convocatoria del token       |
| `student_results` | Estudiante (sesión FINALIZADA) | Las propias de la convocatoria del token     |

El tipo se lee del token solo para elegir el validador; ese validador verifica después la
firma, la expiración y el estado actual en la base de datos, como en los módulos 1, 3 y 5.
Marcar una notificación como leída no permite modificar participaciones ni otra cosa.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError
from app.modules.auth.dependencies import require_admin
from app.modules.auth.dependencies.auth import DbSession, get_auth_service
from app.modules.auth.models import Usuario
from app.modules.auth.services import AuthService
from app.modules.evaluations.dependencies import AccesoResultadosServiceDep
from app.modules.evaluations.security import TIPO_TOKEN_RESULTADOS
from app.modules.notifications.services.entregas_service import EntregasService
from app.modules.notifications.services.notificacion_service import NotificacionService
from app.modules.sessions.dependencies import AccesoServiceDep, RelojDep
from app.modules.sessions.security import TIPO_TOKEN_ESTUDIANTIL

_bearer = HTTPBearer(auto_error=False, description="Token de usuario, estudiantil o de resultados")


@dataclass(frozen=True, slots=True)
class ActorNotificaciones:
    usuario_id: uuid.UUID
    # Para estudiantes: la convocatoria de su token. None para docentes y administradores.
    convocatoria_id: uuid.UUID | None


def _tipo(token: str) -> str | None:
    try:  # solo para enrutar: la verificación real la hace el validador elegido
        return jwt.decode(token, options={"verify_signature": False}).get("type")
    except jwt.PyJWTError:
        return None


def actor_notificaciones(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    acceso: AccesoServiceDep,
    resultados: AccesoResultadosServiceDep,
) -> ActorNotificaciones:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Se requiere autenticación.")
    token = credentials.credentials
    tipo = _tipo(token)
    if tipo == TIPO_TOKEN_ESTUDIANTIL:
        a = acceso.resolver(token)
        return ActorNotificaciones(a.estudiante.id, a.convocatoria.id)
    if tipo == TIPO_TOKEN_RESULTADOS:
        r = resultados.resolver_resultados(token)
        return ActorNotificaciones(r.estudiante.id, r.convocatoria.id)
    usuario = auth.get_user_from_token(token)  # rechaza cualquier otro tipo con 401
    return ActorNotificaciones(usuario.id, None)


ActorDep = Annotated[ActorNotificaciones, Depends(actor_notificaciones)]


def get_notificacion_service(db: DbSession, reloj: RelojDep) -> NotificacionService:
    return NotificacionService(db, reloj)


def get_entregas_service(db: DbSession, reloj: RelojDep) -> EntregasService:
    # Administración: no envía nada, así que no necesita adaptador de correo.
    return EntregasService(db, None, reloj)


NotificacionServiceDep = Annotated[NotificacionService, Depends(get_notificacion_service)]
EntregasServiceDep = Annotated[EntregasService, Depends(get_entregas_service)]
AdminUser = Annotated[Usuario, Depends(require_admin)]
