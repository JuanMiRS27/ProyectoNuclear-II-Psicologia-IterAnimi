"""Envío de las entregas de correo con el Adapter configurado, reintentos y revalidación.

Ciclo de una entrega:

    PENDIENTE --reclamar (SKIP LOCKED)--> EN_PROCESO --enviar--> ENVIADA
        ^                                     |  error temporal (quedan intentos)
        +----------- espera progresiva -------+
                                              |  error permanente o intentos agotados
                                              v
                                           FALLIDA         (reintento manual del administrador)
    PENDIENTE --ya no es válida--> CANCELADA

Antes de enviar se comprueba el estado REAL: convocatoria activa, mismo código (huella),
sesión no finalizada (invitaciones y cambios) o finalizada (resultados). El código se
descifra en memoria solo para construir el mensaje; nunca se guarda ni se registra.

Límite inherente: SMTP no garantiza "exactamente una vez". Si el worker cae después de que
el servidor aceptó el mensaje y antes de marcar ENVIADA, la reserva vence y el mensaje
puede repetirse; el Message-ID estable (`<entrega-id@dominio>`) permite reconocerlo.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.clock import Reloj, RelojSistema
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.notifications import templates as plantillas
from app.modules.notifications.adapters import ErrorCorreo, MensajeCorreo, ServicioCorreo
from app.modules.notifications.models import EntregaCorreo, EstadoEntregaEnum
from app.modules.notifications.models import TipoNotificacionEnum as T
from app.modules.notifications.repositories import NotificacionRepository
from app.modules.notifications.services.notificacion_service import datos_aviso
from app.modules.notifications.services.procesador_eventos import espera_reintento
from app.modules.notifications.services.vigencia import motivo_codigo_inutil
from app.modules.sessions.models import EstadoSesionEnum
from app.modules.sessions.security import CodigoCifradoInvalidoError, descifrar_codigo, huella_codigo

logger = logging.getLogger("inter_nos.notificaciones.entregas")
TAMANO_LOTE = 100
REQUIEREN_SESION_ABIERTA = frozenset({T.CONVOCATORIA, T.CODIGO_REGENERADO, T.REPROGRAMACION})
REQUIEREN_RESULTADOS = frozenset({T.RESULTADOS_DISPONIBLES, T.CALIFICACION_ACTUALIZADA})


@dataclass(slots=True)
class ResumenEntregas:
    enviadas: int = 0
    reintentos: int = 0
    fallidas: int = 0
    canceladas: int = 0


class EntregasService:
    def __init__(self, session: Session, correo: ServicioCorreo | None, reloj: Reloj | None = None) -> None:
        self._session = session
        self._correo = correo
        self._reloj = reloj or RelojSistema()
        self._repo = NotificacionRepository(session)
        self._settings = get_settings()
        self._tz = plantillas.zona(self._settings.NOTIFICATIONS_UTC_OFFSET_HOURS)

    # --- Worker ------------------------------------------------------------------------------

    def procesar_pendientes(self, lote: int = TAMANO_LOTE) -> ResumenEntregas:
        resumen = ResumenEntregas()
        if self._correo is None:  # envío desactivado: las entregas esperan, nada se pierde
            return resumen
        for _ in range(lote):
            if not self._procesar_una(resumen):
                break
        return resumen

    def _procesar_una(self, resumen: ResumenEntregas) -> bool:
        ahora = self._reloj.ahora()
        try:
            entrega = self._repo.reclamar_entrega(ahora)
            if entrega is None:
                self._session.rollback()
                return False
            mensaje = self._preparar(entrega, ahora, resumen)
            self._session.commit()  # EN_PROCESO (o CANCELADA/FALLIDA) visible antes de la red
        except BaseException:
            self._session.rollback()
            raise
        if mensaje is None:
            return True

        try:
            self._correo.enviar(mensaje)  # type: ignore[union-attr]
            error: ErrorCorreo | None = None
        except ErrorCorreo as exc:
            error = exc
        self._finalizar(entrega.id, error, resumen)
        return True

    def _preparar(self, entrega: EntregaCorreo, ahora: datetime, resumen: ResumenEntregas) -> MensajeCorreo | None:
        if entrega.intentos >= self._settings.NOTIFICATIONS_MAX_ATTEMPTS:
            self._marcar_fallida(entrega, "Se agotaron los intentos de entrega.", resumen)
            return None
        motivo = self.motivo_invalidez(entrega)
        if motivo is not None:
            entrega.estado = EstadoEntregaEnum.CANCELADA
            entrega.ultimo_error = motivo
            entrega.proximo_intento_en = None
            resumen.canceladas += 1
            return None
        try:
            mensaje = self.construir_mensaje(entrega)
        except (ErrorCorreo, CodigoCifradoInvalidoError, ValueError) as exc:
            mensaje_seguro = exc.mensaje_seguro if isinstance(exc, ErrorCorreo) else "No se pudo preparar el mensaje."
            entrega.intentos += 1
            entrega.ultimo_intento_en = ahora
            self._marcar_fallida(entrega, mensaje_seguro, resumen)
            return None
        entrega.estado = EstadoEntregaEnum.EN_PROCESO
        entrega.intentos += 1
        entrega.ultimo_intento_en = ahora
        entrega.proximo_intento_en = ahora + timedelta(seconds=self._settings.NOTIFICATIONS_LEASE_SECONDS)
        return mensaje

    def _finalizar(self, entrega_id: uuid.UUID, error: ErrorCorreo | None, resumen: ResumenEntregas) -> None:
        ahora = self._reloj.ahora()
        try:
            entrega = self._repo.entrega_bloqueada(entrega_id)
            if entrega is None or entrega.estado != EstadoEntregaEnum.EN_PROCESO:
                self._session.rollback()
                return
            if error is None:
                entrega.estado = EstadoEntregaEnum.ENVIADA
                entrega.enviada_en = ahora
                entrega.proximo_intento_en = None
                entrega.ultimo_error = None
                resumen.enviadas += 1
            elif error.temporal and entrega.intentos < self._settings.NOTIFICATIONS_MAX_ATTEMPTS:
                entrega.estado = EstadoEntregaEnum.PENDIENTE
                entrega.proximo_intento_en = ahora + espera_reintento(entrega.intentos)
                entrega.ultimo_error = error.mensaje_seguro
                resumen.reintentos += 1
            else:
                self._marcar_fallida(entrega, error.mensaje_seguro, resumen)
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        logger.info("entrega=%s estado=%s intentos=%d", entrega.id, entrega.estado.value, entrega.intentos)

    @staticmethod
    def _marcar_fallida(entrega: EntregaCorreo, mensaje: str, resumen: ResumenEntregas) -> None:
        entrega.estado = EstadoEntregaEnum.FALLIDA
        entrega.ultimo_error = mensaje[:300]
        entrega.proximo_intento_en = None
        resumen.fallidas += 1

    # --- Validez y construcción ---------------------------------------------------------------------

    def motivo_invalidez(self, entrega: EntregaCorreo) -> str | None:
        """Revalida contra el estado ACTUAL (un evento puede llevar mucho tiempo pendiente)."""
        notificacion = entrega.notificacion
        convocatoria = self._repo.convocatoria(notificacion.convocatoria_id)
        if convocatoria is None:
            return "La convocatoria ya no existe."
        sesion = convocatoria.sesion
        tipo = notificacion.tipo
        if tipo == T.REVOCACION:
            return None if not convocatoria.activa else "La convocatoria se reactivó: el aviso de retiro ya no corresponde."
        if not convocatoria.activa:
            return "Convocatoria revocada antes del envío."
        if tipo in REQUIEREN_SESION_ABIERTA and sesion.estado == EstadoSesionEnum.FINALIZADO:
            return "La sesión finalizó antes del envío."
        if tipo in REQUIEREN_RESULTADOS and sesion.estado != EstadoSesionEnum.FINALIZADO:
            return "Los resultados aún no están disponibles."
        if entrega.huella_codigo is not None and entrega.huella_codigo != huella_codigo(convocatoria.codigo_autorizacion):
            return "Código regenerado: entrega obsoleta."
        if tipo in plantillas.TIPOS_CON_CODIGO:
            # Mismo límite real de ingreso que aplica el módulo 3 (y reingreso del módulo 4).
            return motivo_codigo_inutil(self._session, convocatoria, self._reloj.ahora())
        return None

    def construir_mensaje(self, entrega: EntregaCorreo) -> MensajeCorreo:
        notificacion = entrega.notificacion
        convocatoria = self._repo.convocatoria(notificacion.convocatoria_id)
        participacion = self._repo.participacion(notificacion.participacion_id) if notificacion.participacion_id else None
        datos = datos_aviso(convocatoria, convocatoria.sesion, participacion)  # type: ignore[arg-type]
        codigo = None
        if notificacion.tipo in plantillas.TIPOS_CON_CODIGO:
            codigo = descifrar_codigo(convocatoria.codigo_autorizacion, convocatoria.id)  # type: ignore[union-attr]
        cambios = None
        if notificacion.tipo == T.REPROGRAMACION and notificacion.evento_id is not None:
            evento = self._repo.evento(notificacion.evento_id)
            cambios = sorted(filter(None, (evento.datos or {}).get("campos", "").split(","))) if evento else None
        contenido = plantillas.correo(
            notificacion.tipo, datos, self._tz, codigo=codigo, url=self._settings.SIMULATOR_ACCESS_URL, cambios=cambios
        )
        dominio = (self._settings.SMTP_FROM_EMAIL or "inter-nos.local").partition("@")[2] or "inter-nos.local"
        return MensajeCorreo(
            destinatario=notificacion.destinatario.correo,
            asunto=contenido.asunto,
            texto=contenido.texto,
            html=contenido.html,
            id_mensaje=f"<entrega-{entrega.id}@{dominio}>",
        )

    # --- Administración ------------------------------------------------------------------------------

    def listar(self, estado: EstadoEntregaEnum | None, skip: int, limit: int):
        return self._repo.listar_entregas(estado, skip, limit)

    def reintentar(self, entrega_id: uuid.UUID) -> EntregaCorreo:
        """Solo una entrega FALLIDA vuelve a PENDIENTE (con el contador reiniciado); se revalida al enviar."""
        try:
            entrega = self._repo.entrega_bloqueada(entrega_id)
            if entrega is None:
                raise NotFoundError("Entrega no encontrada.")
            if entrega.estado != EstadoEntregaEnum.FALLIDA:
                raise ConflictError("Solo se pueden reintentar entregas FALLIDAS.")
            entrega.estado = EstadoEntregaEnum.PENDIENTE
            entrega.intentos = 0
            entrega.proximo_intento_en = None
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        return entrega


__all__ = ["EntregasService", "ResumenEntregas"]
