"""¿Sigue siendo útil un correo con código? Regla única para el observador y para el envío.

Un código solo sirve si permite ingresar (reglas del módulo 3, `CicloVidaSesion`):

- la convocatoria está activa y la sesión no ha finalizado;
- un ingreso NUEVO se admite hasta `sesion.limite_ingreso` (mitad de la ventana) y nunca a
  partir de `sesion.fin`; antes del inicio la invitación es válida para el futuro;
- después del límite solo puede reingresar quien tiene un intento EN_PROGRESO con tiempo
  (política `ReingresoConParticipacionActiva` del módulo 4, reutilizada aquí). Por ejemplo, un
  código regenerado mientras el estudiante resuelve el cuestionario.

Fuera de esos casos el correo no permitiría participar: se cancela sin enviarse.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.participations.policies.integracion_sesiones import ReingresoConParticipacionActiva
from app.modules.sessions.models import Convocatoria, EstadoSesionEnum

PLAZO_VENCIDO = "El plazo de ingreso terminó: la invitación ya no permite participar."
SESION_FINALIZADA = "La sesión finalizó antes del envío."
CONVOCATORIA_REVOCADA = "Convocatoria revocada antes del envío."


def motivo_codigo_inutil(db: Session, convocatoria: Convocatoria, ahora: datetime) -> str | None:
    if not convocatoria.activa:
        return CONVOCATORIA_REVOCADA
    sesion = convocatoria.sesion
    if sesion.estado == EstadoSesionEnum.FINALIZADO:
        return SESION_FINALIZADA
    if ahora <= sesion.limite_ingreso and ahora < sesion.fin:
        return None
    if sesion.estado == EstadoSesionEnum.EN_CURSO and ReingresoConParticipacionActiva(db).permite_reingreso(convocatoria, ahora):
        return None
    return PLAZO_VENCIDO
