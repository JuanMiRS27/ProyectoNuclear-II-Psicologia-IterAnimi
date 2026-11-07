"""Token de SOLO LECTURA para consultar resultados tras el cierre de la sesión.

Es distinto del token de resolución del módulo 3 (`type = "student"`), que deja de servir
cuando la sesión termina. Este se distingue por `type = "student_results"`: el decodificador
estudiantil, el de docentes y administradores (`type = "access"`) y este solo aceptan su
propio tipo, de modo que con él no se puede crear una participación, responder, ni entrar a
rutas docentes. Reutiliza la infraestructura JWT del módulo 1 (`app.core.security`).
"""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from app.core import security

TIPO_TOKEN_RESULTADOS = "student_results"


@dataclass(frozen=True, slots=True)
class ClaimsResultados:
    estudiante_id: uuid.UUID
    convocatoria_id: uuid.UUID
    sesion_id: uuid.UUID
    version_usuario: int
    huella_codigo: str


def crear_token_resultados(
    *,
    estudiante_id: uuid.UUID,
    convocatoria_id: uuid.UUID,
    sesion_id: uuid.UUID,
    version_usuario: int,
    huella_codigo: str,
    duracion: timedelta,
) -> str:
    claims = {
        "sub": str(estudiante_id),
        "conv": str(convocatoria_id),
        "ses": str(sesion_id),
        "ver": version_usuario,
        "cod": huella_codigo,
    }
    return security.encode_token(claims, TIPO_TOKEN_RESULTADOS, duracion)


def decodificar_token_resultados(token: str) -> ClaimsResultados:
    payload = security.decode_token(token, TIPO_TOKEN_RESULTADOS, ["conv", "ses", "ver", "cod"])
    try:
        return ClaimsResultados(
            estudiante_id=uuid.UUID(payload["sub"]),
            convocatoria_id=uuid.UUID(payload["conv"]),
            sesion_id=uuid.UUID(payload["ses"]),
            version_usuario=security.entero_estricto(payload["ver"]),
            huella_codigo=str(payload["cod"]),
        )
    except (ValueError, TypeError, AttributeError) as exc:
        raise security.InvalidTokenError() from exc
