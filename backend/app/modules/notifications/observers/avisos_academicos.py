"""Observador concreto: resultados disponibles y retroalimentación docente (RF-27).

Visibilidad (regla del módulo 5): un estudiante solo puede consultar resultados con la
sesión FINALIZADA, la convocatoria activa y al menos una nota registrada. Antes de eso no
se avisa nada que pueda anticipar una calificación. Se cubren los dos órdenes posibles:

- Caso A: se evalúa y después finaliza la sesión -> lo detecta SESION_FINALIZADA.
- Caso B: finaliza la sesión y después se evalúa -> lo detecta CALIFICACION_REGISTRADA.

Las claves de idempotencia (`resultados:<convocatoria>`, `retro:<participación>:<huella del
texto>`) hacen que el mismo hecho, llegue por el camino que llegue, se avise una sola vez.
"""

import hashlib

from app.modules.notifications import events as ev
from app.modules.notifications.events import EventoDominio
from app.modules.notifications.models import TipoNotificacionEnum as T
from app.modules.notifications.observers.base import ObservadorEvento
from app.modules.notifications.services.notificacion_service import NotificacionService
from app.modules.participations.models import Participacion
from app.modules.sessions.models import Convocatoria, EstadoSesionEnum


def clave_resultados(convocatoria: Convocatoria) -> str:
    return f"resultados:{convocatoria.id}"


def clave_retroalimentacion(participacion: Participacion) -> str:
    huella = hashlib.sha256((participacion.retroalimentacion_general or "").encode()).hexdigest()[:16]
    return f"retro:{participacion.id}:{huella}"


class ObservadorAvisosAcademicos(ObservadorEvento):
    tipos = frozenset(
        {
            ev.SESION_FINALIZADA,
            ev.RESULTADOS_DISPONIBLES,
            ev.CALIFICACION_REGISTRADA,
            ev.CALIFICACION_ACTUALIZADA,
            ev.RETROALIMENTACION_REGISTRADA,
        }
    )

    def __init__(self, servicio: NotificacionService) -> None:
        self._servicio = servicio
        self._repo = servicio.repo

    def actualizar(self, evento: EventoDominio) -> None:
        if evento.tipo in (ev.SESION_FINALIZADA, ev.RESULTADOS_DISPONIBLES):
            self._revisar_sesion(evento)
        elif evento.tipo == ev.CALIFICACION_REGISTRADA:
            if (convocatoria := self._visible(evento)) is not None:
                self._resultados(convocatoria, evento)
        elif evento.tipo == ev.CALIFICACION_ACTUALIZADA:
            self._calificacion_actualizada(evento)
        else:
            self._retroalimentacion(evento)

    # --- Reglas --------------------------------------------------------------------------------

    def _visible(self, evento: EventoDominio) -> Convocatoria | None:
        convocatoria = self._repo.convocatoria(evento.convocatoria_id) if evento.convocatoria_id else None
        if convocatoria is None or not convocatoria.activa or convocatoria.sesion.estado != EstadoSesionEnum.FINALIZADO:
            return None
        return convocatoria

    def _resultados(self, convocatoria: Convocatoria, evento: EventoDominio) -> bool:
        if not any(p.nota_final is not None for p in self._repo.participaciones(convocatoria.id)):
            return False  # nada calificado aún (o solo intentos SIN_CALIFICAR)
        return self._servicio.notificar(
            T.RESULTADOS_DISPONIBLES, convocatoria, clave=clave_resultados(convocatoria), evento_id=evento.id
        )

    def _revisar_sesion(self, evento: EventoDominio) -> None:
        sesion = self._repo.sesion(evento.sesion_id)
        if sesion is None or sesion.estado != EstadoSesionEnum.FINALIZADO:
            return
        for convocatoria in self._repo.convocatorias_activas(sesion.id):
            self._resultados(convocatoria, evento)
            for participacion in self._repo.participaciones(convocatoria.id):
                if participacion.retroalimentacion_general:  # registrada antes del cierre: se avisa ahora
                    self._servicio.notificar(
                        T.RETROALIMENTACION, convocatoria, clave=clave_retroalimentacion(participacion),
                        evento_id=evento.id, participacion=participacion,
                    )

    def _calificacion_actualizada(self, evento: EventoDominio) -> None:
        convocatoria = self._visible(evento)
        participacion = self._repo.participacion(evento.participacion_id) if evento.participacion_id else None
        if convocatoria is None or participacion is None:
            return
        ya_anunciados = self._repo.existe_clave(clave_resultados(convocatoria))
        self._resultados(convocatoria, evento)
        if ya_anunciados and participacion.nota_final is not None:
            self._servicio.notificar(
                T.CALIFICACION_ACTUALIZADA, convocatoria, clave=f"{evento.tipo}:{evento.id}",
                evento_id=evento.id, participacion=participacion,
            )

    def _retroalimentacion(self, evento: EventoDominio) -> None:
        convocatoria = self._visible(evento)
        participacion = self._repo.participacion(evento.participacion_id) if evento.participacion_id else None
        if convocatoria is None or participacion is None or not participacion.retroalimentacion_general:
            return  # aún no visible (se avisará al finalizar la sesión) o el docente la borró
        self._servicio.notificar(
            T.RETROALIMENTACION, convocatoria, clave=clave_retroalimentacion(participacion),
            evento_id=evento.id, participacion=participacion,
        )
