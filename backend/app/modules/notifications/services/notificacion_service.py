"""Creación idempotente de avisos y consultas del destinatario.

`notificar` crea el aviso interno (mensaje seguro) y, si el tipo se comunica por correo,
una `entrega_correo` PENDIENTE. Ambas inserciones son idempotentes por
`clave_idempotencia`: reprocesar un evento no duplica nada.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import Reloj, RelojSistema
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.modules.notifications import templates as plantillas
from app.modules.notifications.models import Notificacion, TipoNotificacionEnum
from app.modules.notifications.repositories import NotificacionRepository
from app.modules.participations.models import Participacion
from app.modules.sessions.models import Convocatoria, Sesion
from app.modules.sessions.security import huella_codigo

NOTIFICACION_NO_ENCONTRADA = "Notificación no encontrada."


def datos_aviso(convocatoria: Convocatoria, sesion: Sesion, participacion: Participacion | None = None) -> plantillas.DatosAviso:
    estudiante = convocatoria.estudiante
    return plantillas.DatosAviso(
        caso_nombre=sesion.caso.nombre,
        inicio=sesion.inicio,
        fin=sesion.fin,
        tiempo_max_min=sesion.tiempo_max_min,
        lugar=sesion.lugar,
        mensaje_docente=sesion.mensaje,
        nombre_estudiante=estudiante.nombre_completo,
        correo_estudiante=estudiante.correo,
        numero_intento=participacion.numero_intento if participacion is not None else None,
    )


class NotificacionService:
    def __init__(self, session: Session, reloj: Reloj | None = None) -> None:
        self._session = session
        self._reloj = reloj or RelojSistema()
        self._repo = NotificacionRepository(session)
        self._tz = plantillas.zona(get_settings().NOTIFICATIONS_UTC_OFFSET_HOURS)

    @property
    def repo(self) -> NotificacionRepository:
        return self._repo

    @property
    def session(self) -> Session:
        return self._session

    # --- Creación (la usan los observadores) ---------------------------------------------------

    def notificar(
        self,
        tipo: TipoNotificacionEnum,
        convocatoria: Convocatoria,
        *,
        clave: str,
        evento_id: uuid.UUID | None,
        participacion: Participacion | None = None,
        correo: bool = True,
        cambios: list[str] | None = None,
    ) -> bool:
        """Crea el aviso para el estudiante de la convocatoria. Devuelve False si ya existía.

        `correo=False` registra solo el aviso interno aunque el tipo admita correo.
        """
        datos = datos_aviso(convocatoria, convocatoria.sesion, participacion)
        titulo, mensaje = plantillas.aviso_interno(tipo, datos, self._tz, cambios=cambios)
        notificacion_id = self._repo.insertar_notificacion(
            destinatario_id=convocatoria.estudiante_id,
            tipo=tipo,
            convocatoria_id=convocatoria.id,
            participacion_id=participacion.id if participacion is not None else None,
            evento_id=evento_id,
            clave_idempotencia=clave,
            titulo=titulo,
            mensaje=mensaje,
        )
        if notificacion_id is None:
            return False
        if correo and tipo in plantillas.TIPOS_CON_CORREO:
            # Solo la HUELLA del código cifrado vigente: permite detectar al enviar si se regeneró.
            huella = huella_codigo(convocatoria.codigo_autorizacion) if tipo in plantillas.TIPOS_CON_CODIGO else None
            self._repo.insertar_entrega(notificacion_id, huella)
        return True

    # --- Consultas del destinatario -------------------------------------------------------------

    def listar(self, destinatario_id: uuid.UUID, convocatoria_id: uuid.UUID | None, *, solo_no_leidas: bool, skip: int, limit: int):
        return self._repo.listar(destinatario_id, convocatoria_id, solo_no_leidas, skip, limit)

    def contar_no_leidas(self, destinatario_id: uuid.UUID, convocatoria_id: uuid.UUID | None) -> int:
        return self._repo.contar_no_leidas(destinatario_id, convocatoria_id)

    def obtener(self, notificacion_id: uuid.UUID, destinatario_id: uuid.UUID, convocatoria_id: uuid.UUID | None) -> Notificacion:
        notificacion = self._repo.propia(notificacion_id, destinatario_id, convocatoria_id)
        if notificacion is None:  # inexistente o ajena: indistinguibles
            raise NotFoundError(NOTIFICACION_NO_ENCONTRADA)
        return notificacion

    def marcar_leida(self, notificacion_id: uuid.UUID, destinatario_id: uuid.UUID, convocatoria_id: uuid.UUID | None) -> Notificacion:
        """Idempotente: una notificación ya leída conserva su fecha de lectura."""
        try:
            notificacion = self._repo.propia(notificacion_id, destinatario_id, convocatoria_id, bloquear=True)
            if notificacion is None:
                raise NotFoundError(NOTIFICACION_NO_ENCONTRADA)
            if not notificacion.leida:
                notificacion.leida = True
                notificacion.leida_en = self._ahora()
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        return notificacion

    def _ahora(self) -> datetime:
        return self._reloj.ahora()
