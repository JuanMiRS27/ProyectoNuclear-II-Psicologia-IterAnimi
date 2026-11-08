"""Observador concreto: invitaciones, códigos, revocaciones y cambios de programación (RF-20, RF-21)."""

from datetime import datetime

from app.modules.notifications import events as ev
from app.modules.notifications.events import EventoDominio
from app.modules.notifications.models import TipoNotificacionEnum as T
from app.modules.notifications.observers.base import ObservadorEvento
from app.modules.notifications.services.notificacion_service import NotificacionService
from app.modules.notifications.services.vigencia import motivo_codigo_inutil
from app.modules.sessions.models import Convocatoria, EstadoSesionEnum

# Cambios de SESION_MODIFICADA que el estudiante necesita conocer.
CAMPOS_PROGRAMACION = frozenset({"caso_id", "inicio", "fin", "tiempo_max_min", "lugar", "mensaje"})
AVISOS_CON_CODIGO = (T.CONVOCATORIA, T.CODIGO_REGENERADO)
AVISOS_DE_ACCESO = (T.CONVOCATORIA, T.CODIGO_REGENERADO, T.REPROGRAMACION)


class ObservadorConvocatorias(ObservadorEvento):
    tipos = frozenset(
        {
            ev.CONVOCATORIA_CREADA,
            ev.CONVOCATORIA_REACTIVADA,
            ev.CODIGO_REGENERADO,
            ev.CONVOCATORIA_RETIRADA,
            ev.SESION_MODIFICADA,
            ev.SESION_FINALIZADA,
        }
    )

    def __init__(self, servicio: NotificacionService, ahora: datetime, vigencia=motivo_codigo_inutil) -> None:
        self._servicio = servicio
        self._repo = servicio.repo
        self._ahora = ahora
        self._vigencia = vigencia

    def actualizar(self, evento: EventoDominio) -> None:
        manejadores = {
            ev.CONVOCATORIA_CREADA: self._invitar,
            ev.CONVOCATORIA_REACTIVADA: self._invitar,
            ev.CODIGO_REGENERADO: self._codigo_regenerado,
            ev.CONVOCATORIA_RETIRADA: self._revocada,
            ev.SESION_MODIFICADA: self._reprogramada,
            ev.SESION_FINALIZADA: self._sesion_finalizada,
        }
        manejadores[evento.tipo](evento)

    # --- Reacciones ------------------------------------------------------------------------------

    def _vigente(self, evento: EventoDominio) -> Convocatoria | None:
        """Convocatoria del evento si su código aún permite ingresar (estado REAL, no el del evento)."""
        convocatoria = self._repo.convocatoria(evento.convocatoria_id) if evento.convocatoria_id else None
        if convocatoria is None or self._vigencia(self._servicio.session, convocatoria, self._ahora) is not None:
            return None
        return convocatoria

    def _invitar(self, evento: EventoDominio) -> None:
        if (convocatoria := self._vigente(evento)) is not None:
            self._servicio.notificar(T.CONVOCATORIA, convocatoria, clave=f"{evento.tipo}:{evento.id}", evento_id=evento.id)

    def _codigo_regenerado(self, evento: EventoDominio) -> None:
        if (convocatoria := self._vigente(evento)) is None:
            return
        # Las entregas aún no enviadas llevarían el código obsoleto: se cancelan.
        self._repo.cancelar_entregas([convocatoria.id], AVISOS_CON_CODIGO, "Código regenerado: entrega obsoleta.", self._ahora)
        self._servicio.notificar(T.CODIGO_REGENERADO, convocatoria, clave=f"{evento.tipo}:{evento.id}", evento_id=evento.id)

    def _revocada(self, evento: EventoDominio) -> None:
        convocatoria = self._repo.convocatoria(evento.convocatoria_id) if evento.convocatoria_id else None
        if convocatoria is None or convocatoria.activa:  # reactivada después: el aviso ya no corresponde
            return
        self._repo.cancelar_entregas([convocatoria.id], AVISOS_DE_ACCESO, "Convocatoria revocada antes del envío.", self._ahora)
        # "Cuando corresponda": solo si el estudiante pudo tener el código (se le envió o llegó a
        # participar). Si su invitación no había salido, basta con cancelarla.
        if self._repo.algun_codigo_enviado(convocatoria.id) or self._repo.participaciones(convocatoria.id):
            self._servicio.notificar(T.REVOCACION, convocatoria, clave=f"{evento.tipo}:{evento.id}", evento_id=evento.id)

    def _reprogramada(self, evento: EventoDominio) -> None:
        campos = set(filter(None, evento.datos.get("campos", "").split(",")))
        sesion = self._repo.sesion(evento.sesion_id)
        if not (campos & CAMPOS_PROGRAMACION) or sesion is None or sesion.estado == EstadoSesionEnum.FINALIZADO:
            return
        for convocatoria in self._repo.convocatorias_activas(sesion.id):
            # Un aviso anterior aún no enviado quedaría superado por este: se cancela.
            self._repo.cancelar_entregas(
                [convocatoria.id], [T.REPROGRAMACION], "Reprogramación superada por un cambio posterior.", self._ahora
            )
            # El aviso interno siempre (identifica los cambios). El correo solo si el estudiante ya
            # recibió una invitación con los datos anteriores: si la invitación sigue pendiente,
            # saldrá con los datos vigentes y un correo de "cambio" sería redundante y confuso.
            self._servicio.notificar(
                T.REPROGRAMACION, convocatoria, clave=f"{evento.tipo}:{evento.id}:{convocatoria.id}", evento_id=evento.id,
                correo=self._repo.algun_codigo_enviado(convocatoria.id), cambios=sorted(campos & CAMPOS_PROGRAMACION),
            )

    def _sesion_finalizada(self, evento: EventoDominio) -> None:
        """Responsabilidad propia ante el cierre: ya no se envían invitaciones ni cambios de programación."""
        ids = [c.id for c in self._repo.convocatorias_de_sesion(evento.sesion_id)]
        self._repo.cancelar_entregas(ids, AVISOS_DE_ACCESO, "La sesión finalizó antes del envío.", self._ahora)
