"""Módulo 6: servicios de notificación, entregas, autenticación y worker (unitarias).

Complementa `test_modulo_6.py`, que prueba el Observer, el Adapter y las plantillas. Aquí se
verifica la creación idempotente de avisos, el ciclo de vida de una entrega, el enrutamiento
de los tres tipos de token y el worker. Los repositorios y el proveedor de correo son dobles.
"""

import smtplib
import ssl
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.core import security
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.modules.cases.models import CasoEstudio
from app.modules.evaluations.security import crear_token_resultados
from app.modules.notifications import templates as plantillas
from app.modules.notifications.adapters import (
    AdaptadorCorreoSMTP,
    ErrorCorreoPermanente,
    ErrorCorreoTemporal,
    MensajeCorreo,
)
from app.modules.notifications.dependencies import actor_notificaciones
from app.modules.notifications.models import EstadoEntregaEnum
from app.modules.notifications.models import TipoNotificacionEnum as T
from app.modules.notifications.services.entregas_service import EntregasService, ResumenEntregas
from app.modules.notifications.services.notificacion_service import NotificacionService
from app.modules.notifications.services.procesador_eventos import espera_reintento
from app.modules.sessions.security import crear_token_estudiante, huella_codigo
from app.workers.notifications import runner
from tests.conftest import RelojFijo
from tests.unit.fabricas import CODIGO, convocatoria, sesion, sesion_bd

AHORA = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)


def _convocatoria():
    """Convocatoria real (código cifrado de verdad) cuya sesión conoce su caso."""
    return convocatoria(sesion(caso=CasoEstudio(nombre="Conformidad en el aula"), lugar="Aula 301"))


# --- NotificacionService -----------------------------------------------------------------------


@pytest.fixture
def notificador():
    servicio = NotificacionService(sesion_bd(), RelojFijo(AHORA))
    servicio._repo = MagicMock()
    servicio._repo.insertar_notificacion.return_value = uuid.uuid4()
    return servicio


def test_aviso_nuevo_crea_notificacion_y_entrega_con_la_huella_del_codigo(notificador):
    conv = _convocatoria()

    assert notificador.notificar(T.CONVOCATORIA, conv, clave="CONVOCATORIA_CREADA:1", evento_id=None) is True

    datos = notificador._repo.insertar_notificacion.call_args.kwargs
    assert (datos["destinatario_id"], datos["convocatoria_id"], datos["clave_idempotencia"]) == (
        conv.estudiante_id,
        conv.id,
        "CONVOCATORIA_CREADA:1",
    )
    assert CODIGO not in datos["titulo"] + datos["mensaje"]  # el aviso interno nunca lleva el código
    notificador._repo.insertar_entrega.assert_called_once_with(
        notificador._repo.insertar_notificacion.return_value, huella_codigo(conv.codigo_autorizacion)
    )


def test_aviso_con_correo_sin_codigo_no_guarda_huella(notificador):
    notificador.notificar(T.REVOCACION, _convocatoria(), clave="x", evento_id=None)

    assert notificador._repo.insertar_entrega.call_args.args[1] is None


def test_aviso_repetido_no_duplica_la_entrega(notificador):
    notificador._repo.insertar_notificacion.return_value = None

    assert notificador.notificar(T.CONVOCATORIA, _convocatoria(), clave="x", evento_id=None) is False

    notificador._repo.insertar_entrega.assert_not_called()


@pytest.mark.parametrize(("tipo", "correo"), [(T.RETROALIMENTACION, True), (T.REPROGRAMACION, False)])
def test_avisos_solo_internos(notificador, tipo, correo):
    assert tipo not in plantillas.TIPOS_CON_CORREO or not correo

    assert notificador.notificar(tipo, _convocatoria(), clave="x", evento_id=None, correo=correo) is True

    notificador._repo.insertar_entrega.assert_not_called()


def test_notificacion_ajena_o_inexistente_es_404(notificador):
    notificador._repo.propia.return_value = None

    with pytest.raises(NotFoundError):
        notificador.obtener(uuid.uuid4(), uuid.uuid4(), None)
    with pytest.raises(NotFoundError):
        notificador.marcar_leida(uuid.uuid4(), uuid.uuid4(), None)

    notificador._session.rollback.assert_called_once()
    notificador._session.commit.assert_not_called()


def test_marcar_leida_registra_la_hora_y_es_idempotente(notificador):
    notificacion = SimpleNamespace(leida=False, leida_en=None)
    notificador._repo.propia.return_value = notificacion

    notificador.marcar_leida(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    notificador._reloj.avanzar(hours=1)
    notificador.marcar_leida(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    assert (notificacion.leida, notificacion.leida_en) == (True, AHORA)
    assert notificador._repo.propia.call_args.kwargs == {"bloquear": True}


def test_consultas_filtran_por_destinatario_y_convocatoria(notificador):
    usuario_id, conv_id = uuid.uuid4(), uuid.uuid4()

    notificador.listar(usuario_id, conv_id, solo_no_leidas=True, skip=0, limit=10)
    notificador.contar_no_leidas(usuario_id, conv_id)

    notificador._repo.listar.assert_called_once_with(usuario_id, conv_id, True, 0, 10)
    notificador._repo.contar_no_leidas.assert_called_once_with(usuario_id, conv_id)


# --- EntregasService ---------------------------------------------------------------------------


@pytest.fixture
def entregas():
    servicio = EntregasService(sesion_bd(), MagicMock(), RelojFijo(AHORA))
    servicio._repo = MagicMock()
    servicio._settings = get_settings().model_copy(
        update={"SIMULATOR_ACCESS_URL": "https://simulador.universidad.edu.co", "SMTP_FROM_EMAIL": "avisos@universidad.edu.co"}
    )
    return servicio


def _entrega(estado=EstadoEntregaEnum.EN_PROCESO, intentos=1, tipo=T.CONVOCATORIA, conv=None, evento_id=None):
    conv = conv or _convocatoria()
    notificacion = SimpleNamespace(
        convocatoria_id=conv.id,
        participacion_id=None,
        tipo=tipo,
        evento_id=evento_id,
        destinatario=SimpleNamespace(correo=conv.estudiante.correo),
    )
    return SimpleNamespace(id=uuid.uuid4(), estado=estado, intentos=intentos, notificacion=notificacion, ultimo_error=None,
                           proximo_intento_en=None, enviada_en=None)


def test_envio_exitoso_marca_enviada(entregas):
    entrega = _entrega()
    entregas._repo.entrega_bloqueada.return_value = entrega
    resumen = ResumenEntregas()

    entregas._finalizar(entrega.id, None, resumen)

    assert (entrega.estado, entrega.enviada_en, entrega.proximo_intento_en) == (EstadoEntregaEnum.ENVIADA, AHORA, None)
    assert resumen.enviadas == 1
    entregas._session.commit.assert_called_once()


def test_error_temporal_reprograma_con_espera_progresiva(entregas):
    entrega = _entrega(intentos=2)
    entregas._repo.entrega_bloqueada.return_value = entrega
    resumen = ResumenEntregas()

    entregas._finalizar(entrega.id, ErrorCorreoTemporal("Servidor ocupado."), resumen)

    assert entrega.estado == EstadoEntregaEnum.PENDIENTE
    assert entrega.proximo_intento_en == AHORA + espera_reintento(2)
    assert (entrega.ultimo_error, resumen.reintentos) == ("Servidor ocupado.", 1)


def test_error_temporal_en_el_ultimo_intento_queda_fallida(entregas):
    entrega = _entrega(intentos=entregas._settings.NOTIFICATIONS_MAX_ATTEMPTS)
    entregas._repo.entrega_bloqueada.return_value = entrega
    resumen = ResumenEntregas()

    entregas._finalizar(entrega.id, ErrorCorreoTemporal("Servidor ocupado."), resumen)

    assert (entrega.estado, resumen.fallidas) == (EstadoEntregaEnum.FALLIDA, 1)


def test_mensaje_con_codigo_y_message_id_estable(entregas):
    conv = _convocatoria()
    entregas._repo.convocatoria.return_value = conv
    entrega = _entrega(conv=conv)

    mensaje = entregas.construir_mensaje(entrega)

    assert isinstance(mensaje, MensajeCorreo)
    assert mensaje.destinatario == conv.estudiante.correo
    assert CODIGO in mensaje.texto and "https://simulador.universidad.edu.co" in mensaje.texto
    assert mensaje.id_mensaje == f"<entrega-{entrega.id}@universidad.edu.co>"


def test_mensaje_sin_codigo_no_descifra(entregas):
    conv = _convocatoria()
    conv.codigo_autorizacion = "v1.dañado"  # descifrarlo fallaría
    entregas._repo.convocatoria.return_value = conv

    mensaje = entregas.construir_mensaje(_entrega(tipo=T.REVOCACION, conv=conv))

    assert CODIGO not in mensaje.texto


def test_reprogramacion_toma_los_cambios_del_evento(entregas):
    conv = _convocatoria()
    entregas._repo.convocatoria.return_value = conv
    entregas._repo.evento.return_value = SimpleNamespace(datos={"campos": "lugar,inicio"})
    with patch.object(plantillas, "correo", wraps=plantillas.correo) as correo:
        entregas.construir_mensaje(_entrega(tipo=T.REPROGRAMACION, conv=conv, evento_id=uuid.uuid4()))

    assert correo.call_args.kwargs["cambios"] == ["inicio", "lugar"]


def test_reintento_manual_solo_de_entregas_fallidas(entregas):
    entregas._repo.entrega_bloqueada.return_value = None
    with pytest.raises(NotFoundError):
        entregas.reintentar(uuid.uuid4())

    entregas._repo.entrega_bloqueada.return_value = _entrega(EstadoEntregaEnum.ENVIADA)
    with pytest.raises(ConflictError):
        entregas.reintentar(uuid.uuid4())

    assert entregas._session.rollback.call_count == 2
    entregas._session.commit.assert_not_called()


def test_reintento_manual_reinicia_el_contador(entregas):
    entrega = _entrega(EstadoEntregaEnum.FALLIDA, intentos=5)
    entrega.proximo_intento_en = AHORA
    entregas._repo.entrega_bloqueada.return_value = entrega

    assert entregas.reintentar(entrega.id) is entrega

    assert (entrega.estado, entrega.intentos, entrega.proximo_intento_en) == (EstadoEntregaEnum.PENDIENTE, 0, None)
    entregas._session.commit.assert_called_once()


def test_entrega_que_ya_no_corresponde_se_cancela_sin_enviar(entregas):
    entrega = _entrega(EstadoEntregaEnum.PENDIENTE, intentos=0)
    resumen = ResumenEntregas()
    with patch.object(entregas, "motivo_invalidez", return_value="La sesión finalizó antes del envío."):
        assert entregas._preparar(entrega, AHORA, resumen) is None

    assert (entrega.estado, entrega.ultimo_error, resumen.canceladas) == (
        EstadoEntregaEnum.CANCELADA,
        "La sesión finalizó antes del envío.",
        1,
    )


def test_listado_de_entregas_delega_en_el_repositorio(entregas):
    entregas.listar(EstadoEntregaEnum.FALLIDA, 5, 10)

    entregas._repo.listar_entregas.assert_called_once_with(EstadoEntregaEnum.FALLIDA, 5, 10)


# --- Enrutamiento de tokens ----------------------------------------------------------------------


def _actor(token):
    auth, acceso, resultados = MagicMock(), MagicMock(), MagicMock()
    actor = actor_notificaciones(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), auth, acceso, resultados)
    return actor, auth, acceso, resultados


def _claims():
    return {
        "estudiante_id": uuid.uuid4(),
        "convocatoria_id": uuid.uuid4(),
        "sesion_id": uuid.uuid4(),
        "version_usuario": 0,
        "huella_codigo": "abc",
        "duracion": timedelta(minutes=5),
    }


def test_token_estudiantil_usa_el_validador_del_modulo_3():
    actor, auth, acceso, resultados = _actor(crear_token_estudiante(**_claims()))

    acceso.resolver.assert_called_once()
    auth.get_user_from_token.assert_not_called()
    assert actor.convocatoria_id == acceso.resolver.return_value.convocatoria.id


def test_token_de_resultados_usa_el_validador_del_modulo_5():
    actor, auth, acceso, resultados = _actor(crear_token_resultados(**_claims()))

    resultados.resolver_resultados.assert_called_once()
    acceso.resolver.assert_not_called()
    assert actor.usuario_id == resultados.resolver_resultados.return_value.estudiante.id


@pytest.mark.parametrize("token", [security.create_access_token(uuid.uuid4(), "DOCENTE", 0), "basura"], ids=["access", "basura"])
def test_otros_tokens_los_valida_el_modulo_1(token):
    actor, auth, acceso, resultados = _actor(token)

    auth.get_user_from_token.assert_called_once_with(token)
    assert actor.convocatoria_id is None
    acceso.resolver.assert_not_called()
    resultados.resolver_resultados.assert_not_called()


@pytest.mark.parametrize("credenciales", [None, HTTPAuthorizationCredentials(scheme="Basic", credentials="x")])
def test_notificaciones_exigen_bearer(credenciales):
    with pytest.raises(AuthenticationError):
        actor_notificaciones(credenciales, MagicMock(), MagicMock(), MagicMock())


# --- Adaptador SMTP: rutas no cubiertas por test_modulo_6 -----------------------------------------


class SMTPDoble:
    def __init__(self, error=None):
        self.llamadas: list[str] = []
        self._error = error

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context):
        self.llamadas.append("starttls")

    def login(self, usuario, clave):
        self.llamadas.append(f"login:{usuario}")

    def send_message(self, *args, **kwargs):
        if self._error:
            raise self._error
        self.llamadas.append("send")


def _adaptador(doble, **extra):
    return AdaptadorCorreoSMTP(
        host="smtp.universidad.edu.co", puerto=587, remitente="avisos@universidad.edu.co", fabrica_smtp=lambda *a: doble, **extra
    )


def _mensaje():
    return MensajeCorreo(destinatario="eva@universidad.edu.co", asunto="Aviso", texto="Hola")


def test_tls_antes_de_enviar_credenciales():
    doble = SMTPDoble()

    _adaptador(doble, usuario="avisos", clave="secreto").enviar(_mensaje())

    assert doble.llamadas == ["starttls", "login:avisos", "send"]


@pytest.mark.parametrize(
    ("error", "tipo"),
    [
        (smtplib.SMTPRecipientsRefused({"eva@universidad.edu.co": (550, b"no")}), ErrorCorreoPermanente),
        (smtplib.SMTPResponseException(421, b"ocupado"), ErrorCorreoTemporal),
        (smtplib.SMTPResponseException(554, b"rechazado"), ErrorCorreoPermanente),
        (ssl.SSLCertVerificationError("certificado"), ErrorCorreoPermanente),
        (TimeoutError(), ErrorCorreoTemporal),
        (ConnectionResetError(), ErrorCorreoTemporal),
    ],
    ids=["destinatario", "4xx", "5xx", "certificado", "timeout", "red"],
)
def test_clasificacion_de_errores_smtp(error, tipo):
    with pytest.raises(tipo) as capturado:
        _adaptador(SMTPDoble(error)).enviar(_mensaje())

    assert "secreto" not in capturado.value.mensaje_seguro
    assert capturado.value.__cause__ is None  # no se encadena la excepción original, que puede repetir datos


# --- Worker --------------------------------------------------------------------------------------


def test_pasada_procesa_eventos_antes_que_entregas():
    orden = []
    with (
        patch.object(runner, "configurar_integraciones"),
        patch.object(runner, "ProcesadorEventosService") as procesador,
        patch.object(runner, "EntregasService") as servicio_entregas,
    ):
        procesador.return_value.procesar_pendientes.side_effect = lambda: orden.append("eventos") or MagicMock(procesados=1)
        servicio_entregas.return_value.procesar_pendientes.side_effect = lambda: orden.append("entregas") or ResumenEntregas()
        correo = MagicMock()
        resumen = runner.ejecutar_una_vez(MagicMock(), RelojFijo(AHORA), correo=correo)

    assert orden == ["eventos", "entregas"]
    assert servicio_entregas.call_args.args[1] is correo
    assert resumen.entregas == ResumenEntregas()


def test_sin_adaptador_explicito_usa_el_configurado():
    with (
        patch.object(runner, "configurar_integraciones"),
        patch.object(runner, "crear_servicio_correo", return_value=None) as fabrica,
        patch.object(runner, "ProcesadorEventosService"),
        patch.object(runner, "EntregasService") as servicio_entregas,
    ):
        runner.ejecutar_una_vez(MagicMock())

    fabrica.assert_called_once()
    assert servicio_entregas.call_args.args[1] is None


def test_bucle_valida_el_correo_una_vez_y_sobrevive_a_fallos(caplog):
    class Detener(Exception):
        pass

    with (
        patch.object(runner, "crear_servicio_correo") as fabrica,
        patch.object(runner, "ejecutar_una_vez", side_effect=[RuntimeError("bd caída"), None]) as pasada,
        patch.object(runner.time, "sleep", side_effect=[None, Detener]),
    ):
        with pytest.raises(Detener):
            runner.ejecutar_periodicamente(30)

    fabrica.assert_called_once()
    assert pasada.call_count == 2
    assert "fallo en la pasada de notificaciones" in caplog.text
