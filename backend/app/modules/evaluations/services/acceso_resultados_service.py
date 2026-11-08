"""Acceso estudiantil de solo lectura a los resultados, una vez FINALIZADA la sesión.

Hereda de `AccesoEstudiantilService` (módulo 3) la verificación de credenciales: descifrado
de los códigos y comparación en tiempo constante, sin duplicarla. Usa el MISMO limitador de
intentos fallidos que el ingreso a la resolución, así que los fallos se cuentan juntos en
ambos endpoints y la protección contra fuerza bruta no se puede eludir alternándolos.

El token emitido (ver `security/`) tiene otro tipo y otro alcance que el de resolución.
"""

import hmac
import uuid
from dataclasses import dataclass
from datetime import timedelta

from app.core import security
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.modules.auth.models import RolUsuario, Usuario
from app.modules.evaluations.security import crear_token_resultados, decodificar_token_resultados
from app.modules.sessions.models import LONGITUD_CODIGO, Convocatoria, EstadoSesionEnum, Sesion
from app.modules.sessions.security import LimitadorIntentos, huella_codigo
from app.modules.sessions.services import AccesoEstudiantilService
from app.modules.sessions.services.acceso_service import CREDENCIALES_INVALIDAS

ACCESO_RESULTADOS_INVALIDO = "Acceso a resultados inválido, expirado o revocado."
RESULTADOS_NO_DISPONIBLES = "Los resultados estarán disponibles cuando la sesión finalice."


@dataclass(frozen=True, slots=True)
class AccesoResultados:
    estudiante: Usuario
    convocatoria: Convocatoria
    sesion: Sesion


@dataclass(frozen=True, slots=True)
class TokenResultados:
    access_token: str
    expires_in: int
    sesion_id: uuid.UUID
    convocatoria_id: uuid.UUID


class AccesoResultadosService(AccesoEstudiantilService):
    def ingresar_resultados(self, correo: str, codigo: str, ip: str, limitador: LimitadorIntentos) -> TokenResultados:
        limitador.verificar(correo, ip)
        convocatoria = self._buscar_por_codigo(correo, codigo) if len(codigo) == LONGITUD_CODIGO else None
        if convocatoria is None:
            limitador.registrar_fallo(correo, ip)
            raise AuthenticationError(CREDENCIALES_INVALIDAS)
        limitador.registrar_exito(correo)

        # Credenciales correctas: se puede informar el motivo concreto.
        estudiante, sesion = convocatoria.estudiante, convocatoria.sesion
        if not convocatoria.activa:
            raise PermissionDeniedError("La convocatoria fue revocada por el docente.")
        if not estudiante.activo:
            raise PermissionDeniedError("La cuenta del estudiante está desactivada.")
        if sesion.estado != EstadoSesionEnum.FINALIZADO:
            raise PermissionDeniedError(RESULTADOS_NO_DISPONIBLES)

        duracion = timedelta(minutes=get_settings().STUDENT_RESULTS_TOKEN_EXPIRE_MINUTES)
        token = crear_token_resultados(
            estudiante_id=estudiante.id,
            convocatoria_id=convocatoria.id,
            sesion_id=sesion.id,
            version_usuario=estudiante.version_token,
            huella_codigo=huella_codigo(convocatoria.codigo_autorizacion),
            duracion=duracion,
        )
        return TokenResultados(token, int(duracion.total_seconds()), sesion.id, convocatoria.id)

    def resolver_resultados(self, token: str) -> AccesoResultados:
        """Revalida contra el estado ACTUAL: convocatoria activa, mismo código, cuenta vigente, sesión FINALIZADA."""
        try:
            claims = decodificar_token_resultados(token)
        except security.InvalidTokenError as exc:
            raise AuthenticationError(ACCESO_RESULTADOS_INVALIDO) from exc

        convocatoria = self._convocatorias.get_by_id(claims.convocatoria_id)
        if (
            convocatoria is None
            or not convocatoria.activa
            or convocatoria.estudiante_id != claims.estudiante_id
            or convocatoria.sesion_id != claims.sesion_id
            or not hmac.compare_digest(huella_codigo(convocatoria.codigo_autorizacion), claims.huella_codigo)
        ):
            raise AuthenticationError(ACCESO_RESULTADOS_INVALIDO)
        estudiante, sesion = convocatoria.estudiante, convocatoria.sesion
        if (
            not estudiante.activo
            or estudiante.rol != RolUsuario.ESTUDIANTE
            or estudiante.version_token != claims.version_usuario
            or sesion.estado != EstadoSesionEnum.FINALIZADO
        ):
            raise AuthenticationError(ACCESO_RESULTADOS_INVALIDO)
        return AccesoResultados(estudiante, convocatoria, sesion)
