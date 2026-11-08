"""Pruebas unitarias del módulo 6 (Observer, Adapter, plantillas y procesadores).

Sin PostgreSQL ni SMTP reales: dominio puro, dobles de prueba y un SMTP simulado.
"""

import smtplib
import socket
import ssl
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.modules.notifications import events as ev
from app.modules.notifications import templates as plantillas
from app.modules.notifications.adapters import (
    AdaptadorCorreoPruebas,
    AdaptadorCorreoSMTP,
    ConfiguracionCorreoError,
    ErrorCorreoPermanente,
    ErrorCorreoTemporal,
    MensajeCorreo,
    MensajeInvalidoError,
    ServicioCorreo,
    crear_servicio_correo,
    validar_url_acceso,
)
from app.modules.notifications.events import EventoDominio, RegistroEventosSQL
from app.modules.notifications.models import EstadoEntregaEnum, EstadoEventoEnum, EventoOutbox
from app.modules.notifications.models import TipoNotificacionEnum as T
from app.modules.notifications.observers.avisos_academicos import (
    ObservadorAvisosAcademicos,
    clave_resultados,
    clave_retroalimentacion,
)
from app.modules.notifications.observers.base import ObservadorEvento
from app.modules.notifications.observers.convocatorias import ObservadorConvocatorias
from app.modules.notifications.publishers import PublicadorEventos
from app.modules.notifications.services.entregas_service import EntregasService
from app.modules.notifications.services.procesador_eventos import ProcesadorEventosService, crear_publicador, espera_reintento
from app.modules.sessions.models import EstadoSesionEnum
from app.modules.sessions.security import huella_codigo
from tests.unit.fabricas import sesion_bd

AHORA = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)
CODIGO = "ABCDEFGH2345"


def evento(tipo: str, **datos) -> EventoDominio:
    return EventoDominio(uuid.uuid4(), tipo, uuid.uuid4(), AHORA, {k: str(v) for k, v in datos.items()})


# --- Observer: sujeto y contrato ---------------------------------------------------------------


class Registrador(ObservadorEvento):
    def __init__(self, *tipos: str, falla: bool = False) -> None:
        self.tipos = frozenset(tipos)
        self.recibidos: list[EventoDominio] = []
        self.falla = falla

    def actualizar(self, evento: EventoDominio) -> None:
        if self.falla:
            raise RuntimeError("fallo con datos ABCDEFGH2345")
        self.recibidos.append(evento)


class TestPublicador:
    def test_registra_y_distribuye_por_tipo(self):
        publicador, a = PublicadorEventos(), Registrador("A", "B")
        publicador.suscribir(a)
        e = evento("A")
        assert publicador.publicar(e) == ["Registrador"]
        assert a.recibidos == [e]

    def test_varios_observadores_en_orden_de_suscripcion(self):
        orden = []
        publicador = PublicadorEventos()
        for nombre in ("primero", "segundo"):
            o = MagicMock(spec=ObservadorEvento, tipos=frozenset({"A"}), nombre=nombre)
            o.actualizar.side_effect = lambda e, n=nombre: orden.append(n)
            publicador.suscribir(o)
        assert publicador.publicar(evento("A")) == ["primero", "segundo"]
        assert orden == ["primero", "segundo"]

    def test_eventos_de_otros_tipos_no_llegan(self):
        publicador, a, b = PublicadorEventos(), Registrador("A"), Registrador("B")
        publicador.suscribir(a)
        publicador.suscribir(b)
        publicador.publicar(evento("B"))
        assert (len(a.recibidos), len(b.recibidos)) == (0, 1)

    def test_evento_desconocido_no_es_error(self):
        publicador = PublicadorEventos()
        publicador.suscribir(Registrador("A"))
        assert publicador.publicar(evento("INTENTOS_MODIFICADOS")) == []

    def test_suscribir_dos_veces_no_duplica_y_desuscribir(self):
        publicador, a = PublicadorEventos(), Registrador("A")
        publicador.suscribir(a)
        publicador.suscribir(a)
        assert publicador.observadores_de("A") == [a]
        publicador.desuscribir(a)
        assert publicador.observadores_de("A") == []

    def test_el_fallo_se_propaga_para_revertir_el_evento(self):
        publicador = PublicadorEventos()
        publicador.suscribir(Registrador("A", falla=True))
        with pytest.raises(RuntimeError):
            publicador.publicar(evento("A"))

    def test_contrato_abstracto(self):
        with pytest.raises(TypeError):
            ObservadorEvento()  # type: ignore[abstract]

    def test_composicion_con_dos_observadores_y_responsabilidad_compartida(self):
        publicador = crear_publicador(sesion_bd(), AHORA)
        nombres = {o.nombre for o in publicador.observadores_de(ev.SESION_FINALIZADA)}
        assert nombres == {"ObservadorConvocatorias", "ObservadorAvisosAcademicos"}
        assert [o.nombre for o in publicador.observadores_de(ev.CONVOCATORIA_CREADA)] == ["ObservadorConvocatorias"]
        assert [o.nombre for o in publicador.observadores_de(ev.RETROALIMENTACION_REGISTRADA)] == ["ObservadorAvisosAcademicos"]


class TestEventoDominio:
    def test_identificadores_y_valores_invalidos(self):
        cid = uuid.uuid4()
        e = evento(ev.CONVOCATORIA_CREADA, convocatoria_id=cid, participacion_id="no-es-uuid")
        assert e.convocatoria_id == cid and e.participacion_id is None

    def test_desde_outbox(self):
        fila = EventoOutbox(id=uuid.uuid4(), tipo="X", sesion_id=uuid.uuid4(), registrado_en=AHORA, datos={"a": "b"})
        e = EventoDominio.desde_outbox(fila)
        assert (e.id, e.tipo, e.datos) == (fila.id, "X", {"a": "b"})

    @pytest.mark.parametrize("clave", ["codigo", "Codigo_Autorizacion", "token", "nota_final", "password"])
    def test_registro_rechaza_datos_sensibles(self, clave):
        db = MagicMock()
        with pytest.raises(ValueError):
            RegistroEventosSQL().registrar(db, "X", uuid.uuid4(), {clave: "secreto"})
        db.execute.assert_not_called()

    def test_registro_inserta_en_la_transaccion_recibida(self):
        db = MagicMock()
        RegistroEventosSQL().registrar(db, ev.CONVOCATORIA_CREADA, uuid.uuid4(), {"convocatoria_id": "x"})
        db.execute.assert_called_once()
        db.commit.assert_not_called()  # el commit es de la operación académica


# --- Observadores concretos (con dobles) ---------------------------------------------------------------


def convocatoria(activa=True, estado=EstadoSesionEnum.EN_CURSO, codigo="v1.cifrado", limite=AHORA + timedelta(hours=1)):
    sesion = SimpleNamespace(estado=estado, limite_ingreso=limite, fin=limite + timedelta(hours=1))
    return SimpleNamespace(id=uuid.uuid4(), activa=activa, sesion=sesion, codigo_autorizacion=codigo, estudiante_id=uuid.uuid4())


def doble_servicio(conv=None, **repo):
    servicio = MagicMock()
    servicio.repo.convocatoria.return_value = conv
    for nombre, valor in repo.items():
        getattr(servicio.repo, nombre).return_value = valor
    return servicio


class TestObservadorConvocatorias:
    @pytest.mark.parametrize("tipo", [ev.CONVOCATORIA_CREADA, ev.CONVOCATORIA_REACTIVADA])
    def test_invita_si_la_convocatoria_sigue_vigente(self, tipo):
        conv = convocatoria()
        servicio = doble_servicio(conv)
        e = evento(tipo, convocatoria_id=conv.id)
        ObservadorConvocatorias(servicio, AHORA).actualizar(e)
        servicio.notificar.assert_called_once_with(T.CONVOCATORIA, conv, clave=f"{tipo}:{e.id}", evento_id=e.id)

    @pytest.mark.parametrize("conv", [None, convocatoria(activa=False), convocatoria(estado=EstadoSesionEnum.FINALIZADO)])
    def test_evento_obsoleto_no_invita(self, conv):
        servicio = doble_servicio(conv)
        ObservadorConvocatorias(servicio, AHORA).actualizar(evento(ev.CONVOCATORIA_CREADA, convocatoria_id=uuid.uuid4()))
        servicio.notificar.assert_not_called()

    def test_codigo_regenerado_cancela_entregas_obsoletas_y_avisa(self):
        conv = convocatoria()
        servicio = doble_servicio(conv)
        ObservadorConvocatorias(servicio, AHORA).actualizar(evento(ev.CODIGO_REGENERADO, convocatoria_id=conv.id))
        args = servicio.repo.cancelar_entregas.call_args.args
        assert args[0] == [conv.id] and set(args[1]) == {T.CONVOCATORIA, T.CODIGO_REGENERADO}
        assert servicio.notificar.call_args.args[0] == T.CODIGO_REGENERADO

    def test_revocacion_sin_codigo_entregado_solo_cancela(self):
        conv = convocatoria(activa=False)
        servicio = doble_servicio(conv, algun_codigo_enviado=False, participaciones=[])
        ObservadorConvocatorias(servicio, AHORA).actualizar(evento(ev.CONVOCATORIA_RETIRADA, convocatoria_id=conv.id))
        servicio.repo.cancelar_entregas.assert_called_once()
        servicio.notificar.assert_not_called()

    @pytest.mark.parametrize(("enviado", "participaciones"), [(True, []), (False, [object()])])
    def test_revocacion_avisa_si_pudo_tener_el_codigo(self, enviado, participaciones):
        conv = convocatoria(activa=False)
        servicio = doble_servicio(conv, algun_codigo_enviado=enviado, participaciones=participaciones)
        ObservadorConvocatorias(servicio, AHORA).actualizar(evento(ev.CONVOCATORIA_RETIRADA, convocatoria_id=conv.id))
        assert servicio.notificar.call_args.args[0] == T.REVOCACION

    def test_revocacion_ya_reactivada_no_avisa(self):
        servicio = doble_servicio(convocatoria(activa=True))
        ObservadorConvocatorias(servicio, AHORA).actualizar(evento(ev.CONVOCATORIA_RETIRADA, convocatoria_id=uuid.uuid4()))
        servicio.repo.cancelar_entregas.assert_not_called()
        servicio.notificar.assert_not_called()

    def test_reprogramacion_avisa_a_cada_convocatoria_activa(self):
        convs = [convocatoria(), convocatoria()]
        servicio = doble_servicio(sesion=SimpleNamespace(id=uuid.uuid4(), estado=EstadoSesionEnum.SIN_INICIAR), convocatorias_activas=convs)
        e = evento(ev.SESION_MODIFICADA, campos="inicio,lugar")
        ObservadorConvocatorias(servicio, AHORA).actualizar(e)
        claves = [c.kwargs["clave"] for c in servicio.notificar.call_args_list]
        assert claves == [f"{e.tipo}:{e.id}:{c.id}" for c in convs]

    @pytest.mark.parametrize("campos", ["espacio_academico_id", ""])
    def test_cambios_que_no_afectan_al_estudiante(self, campos):
        servicio = doble_servicio(sesion=SimpleNamespace(id=uuid.uuid4(), estado=EstadoSesionEnum.SIN_INICIAR))
        ObservadorConvocatorias(servicio, AHORA).actualizar(evento(ev.SESION_MODIFICADA, campos=campos))
        servicio.notificar.assert_not_called()

    def test_fin_de_sesion_cancela_invitaciones_pendientes(self):
        convs = [convocatoria(), convocatoria(activa=False)]
        servicio = doble_servicio(convocatorias_de_sesion=convs)
        ObservadorConvocatorias(servicio, AHORA).actualizar(evento(ev.SESION_FINALIZADA))
        assert servicio.repo.cancelar_entregas.call_args.args[0] == [c.id for c in convs]


def participacion(nota=None, retro=None, intento=1):
    return SimpleNamespace(id=uuid.uuid4(), nota_final=nota, retroalimentacion_general=retro, numero_intento=intento)


class TestObservadorAvisosAcademicos:
    def test_no_avisa_antes_de_finalizar_la_sesion(self):
        servicio = doble_servicio(convocatoria(estado=EstadoSesionEnum.EN_CURSO), participaciones=[participacion(3)])
        ObservadorAvisosAcademicos(servicio).actualizar(evento(ev.CALIFICACION_REGISTRADA, convocatoria_id=uuid.uuid4()))
        servicio.notificar.assert_not_called()

    def test_caso_b_calificacion_tras_el_cierre(self):
        conv = convocatoria(estado=EstadoSesionEnum.FINALIZADO)
        servicio = doble_servicio(conv, participaciones=[participacion(3)])
        ObservadorAvisosAcademicos(servicio).actualizar(evento(ev.CALIFICACION_REGISTRADA, convocatoria_id=conv.id))
        assert servicio.notificar.call_args.kwargs["clave"] == clave_resultados(conv)

    def test_solo_intentos_sin_calificar_no_generan_aviso(self):
        conv = convocatoria(estado=EstadoSesionEnum.FINALIZADO)
        servicio = doble_servicio(conv, participaciones=[participacion(None)])
        ObservadorAvisosAcademicos(servicio).actualizar(evento(ev.CALIFICACION_REGISTRADA, convocatoria_id=conv.id))
        servicio.notificar.assert_not_called()

    def test_revocada_no_recibe_resultados(self):
        servicio = doble_servicio(convocatoria(activa=False, estado=EstadoSesionEnum.FINALIZADO), participaciones=[participacion(3)])
        ObservadorAvisosAcademicos(servicio).actualizar(evento(ev.CALIFICACION_REGISTRADA, convocatoria_id=uuid.uuid4()))
        servicio.notificar.assert_not_called()

    def test_caso_a_cierre_tras_evaluar_avisa_resultados_y_retroalimentacion_previa(self):
        conv = convocatoria(estado=EstadoSesionEnum.FINALIZADO)
        p = participacion(4, retro="Revisa el sesgo.")
        servicio = doble_servicio(
            sesion=SimpleNamespace(id=uuid.uuid4(), estado=EstadoSesionEnum.FINALIZADO), convocatorias_activas=[conv], participaciones=[p]
        )
        ObservadorAvisosAcademicos(servicio).actualizar(evento(ev.SESION_FINALIZADA))
        tipos = [c.args[0] for c in servicio.notificar.call_args_list]
        assert tipos == [T.RESULTADOS_DISPONIBLES, T.RETROALIMENTACION]

    def test_actualizacion_tras_anunciar_genera_aviso_propio(self):
        conv = convocatoria(estado=EstadoSesionEnum.FINALIZADO)
        p = participacion(4)
        servicio = doble_servicio(conv, participaciones=[p], participacion=p, existe_clave=True)
        ObservadorAvisosAcademicos(servicio).actualizar(
            evento(ev.CALIFICACION_ACTUALIZADA, convocatoria_id=conv.id, participacion_id=p.id)
        )
        assert [c.args[0] for c in servicio.notificar.call_args_list] == [T.RESULTADOS_DISPONIBLES, T.CALIFICACION_ACTUALIZADA]

    def test_actualizacion_sin_anuncio_previo_solo_anuncia_resultados(self):
        conv = convocatoria(estado=EstadoSesionEnum.FINALIZADO)
        p = participacion(4)
        servicio = doble_servicio(conv, participaciones=[p], participacion=p, existe_clave=False)
        ObservadorAvisosAcademicos(servicio).actualizar(
            evento(ev.CALIFICACION_ACTUALIZADA, convocatoria_id=conv.id, participacion_id=p.id)
        )
        assert [c.args[0] for c in servicio.notificar.call_args_list] == [T.RESULTADOS_DISPONIBLES]

    def test_retroalimentacion_no_visible_se_difiere(self):
        p = participacion(4, retro="Texto")
        servicio = doble_servicio(convocatoria(estado=EstadoSesionEnum.EN_CURSO), participacion=p)
        ObservadorAvisosAcademicos(servicio).actualizar(evento(ev.RETROALIMENTACION_REGISTRADA, convocatoria_id=uuid.uuid4(), participacion_id=p.id))
        servicio.notificar.assert_not_called()

    def test_retroalimentacion_visible_y_borrada(self):
        conv = convocatoria(estado=EstadoSesionEnum.FINALIZADO)
        con_texto, sin_texto = participacion(4, retro="Texto"), participacion(4, retro=None)
        for p, esperado in ((con_texto, 1), (sin_texto, 0)):
            servicio = doble_servicio(conv, participacion=p)
            ObservadorAvisosAcademicos(servicio).actualizar(
                evento(ev.RETROALIMENTACION_REGISTRADA, convocatoria_id=conv.id, participacion_id=p.id)
            )
            assert servicio.notificar.call_count == esperado

    def test_clave_de_retroalimentacion_depende_del_texto(self):
        p = participacion(retro="A")
        igual, otra = participacion(retro="A"), participacion(retro="B")
        igual.id = otra.id = p.id
        assert clave_retroalimentacion(p) == clave_retroalimentacion(igual) != clave_retroalimentacion(otra)
        secreto = participacion(retro="Texto privado del docente")
        assert "privado" not in clave_retroalimentacion(secreto) and len(clave_retroalimentacion(secreto)) <= 120


# --- Procesador del outbox ------------------------------------------------------------------------


class TestProcesadorEventos:
    def _procesador(self, fila, publicador):
        session = sesion_bd()
        procesador = ProcesadorEventosService(session, SimpleNamespace(ahora=lambda: AHORA), lambda *_: publicador)
        procesador._repo = MagicMock()
        procesador._repo.reclamar_evento.side_effect = [fila, None]
        return procesador, session

    def _fila(self, intentos=0):
        return EventoOutbox(id=uuid.uuid4(), tipo=ev.CONVOCATORIA_CREADA, sesion_id=uuid.uuid4(), registrado_en=AHORA,
                            datos={}, estado=EstadoEventoEnum.PENDIENTE, intentos=intentos)

    def test_procesa_y_marca(self):
        fila, publicador = self._fila(), MagicMock()
        publicador.publicar.return_value = ["ObservadorConvocatorias"]
        procesador, session = self._procesador(fila, publicador)
        resumen = procesador.procesar_pendientes()
        assert (resumen.procesados, fila.estado, fila.procesado_en) == (1, EstadoEventoEnum.PROCESADO, AHORA)
        session.commit.assert_called()

    def test_evento_sin_observadores_se_procesa(self):
        fila, publicador = self._fila(), MagicMock()
        publicador.publicar.return_value = []
        procesador, _ = self._procesador(fila, publicador)
        assert procesador.procesar_pendientes().sin_observadores == [ev.CONVOCATORIA_CREADA]

    def test_fallo_reprograma_con_error_seguro(self):
        fila, publicador = self._fila(), MagicMock()
        publicador.publicar.side_effect = RuntimeError(f"datos {CODIGO}")
        procesador, _ = self._procesador(fila, publicador)
        resumen = procesador.procesar_pendientes()
        assert (resumen.reintentos, fila.intentos, fila.estado) == (1, 1, EstadoEventoEnum.PENDIENTE)
        assert fila.proximo_intento_en == AHORA + espera_reintento(1)
        assert CODIGO not in fila.ultimo_error and "RuntimeError" in fila.ultimo_error

    def test_agotar_intentos_lo_deja_fallido(self):
        fila, publicador = self._fila(intentos=get_settings().NOTIFICATIONS_MAX_ATTEMPTS - 1), MagicMock()
        publicador.publicar.side_effect = RuntimeError()
        procesador, _ = self._procesador(fila, publicador)
        assert procesador.procesar_pendientes().fallidos == 1
        assert (fila.estado, fila.proximo_intento_en) == (EstadoEventoEnum.FALLIDO, None)

    def test_espera_progresiva_con_tope(self):
        base, tope = get_settings().NOTIFICATIONS_RETRY_BASE_SECONDS, get_settings().NOTIFICATIONS_RETRY_MAX_SECONDS
        assert [espera_reintento(n).total_seconds() for n in (1, 2, 3)] == [base, 2 * base, 4 * base]
        assert espera_reintento(30).total_seconds() == tope


# --- Adapter ---------------------------------------------------------------------------------


class TestMensajeCorreo:
    def test_mensaje_valido(self):
        m = MensajeCorreo("ana@universidad.edu.co", "Asunto", "Cuerpo", "<p>x</p>", "<entrega-1@u.edu.co>")
        assert m.destinatario == "ana@universidad.edu.co"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"destinatario": "no-es-correo"},
            {"destinatario": "ana@u.edu.co\r\nBcc: todos@u.edu.co"},
            {"destinatario": "ana@u.edu.co, otro@u.edu.co"},
            {"asunto": "Hola\r\nBcc: x@y.co"},
            {"asunto": ""},
            {"asunto": "x" * 201},
            {"texto": ""},
            {"encabezados": {"X-A": "v\nBcc: x@y.co"}},
            {"id_mensaje": "<a>\r\nX: y"},
        ],
    )
    def test_rechaza_inyeccion_y_datos_invalidos(self, kwargs):
        datos = {"destinatario": "ana@u.edu.co", "asunto": "Asunto", "texto": "Cuerpo"} | kwargs
        with pytest.raises(MensajeInvalidoError):
            MensajeCorreo(**datos)


class TestAdaptadorPruebas:
    def test_captura_y_simula_fallos(self):
        adaptador = AdaptadorCorreoPruebas()
        assert isinstance(adaptador, ServicioCorreo)
        adaptador.fallar_con(ErrorCorreoTemporal("caído"))
        with pytest.raises(ErrorCorreoTemporal):
            adaptador.enviar(MensajeCorreo("ana@u.edu.co", "A", "B"))
        adaptador.enviar(MensajeCorreo("ana@u.edu.co", "A", "B"))
        assert len(adaptador.para("ana@u.edu.co")) == 1


class SMTPFalso:
    def __init__(self, error=None) -> None:
        self.error, self.llamadas, self.enviado = error, [], None

    def __call__(self, host, puerto, timeout, ssl_implicito, contexto):
        self.llamadas.append(("conectar", host, puerto, timeout, ssl_implicito))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context):
        self.llamadas.append(("starttls", context.verify_mode == ssl.CERT_REQUIRED, context.check_hostname))

    def login(self, usuario, clave):
        self.llamadas.append(("login", usuario))
        if isinstance(self.error, smtplib.SMTPAuthenticationError):
            raise self.error

    def send_message(self, correo, from_addr, to_addrs):
        if self.error is not None and not isinstance(self.error, smtplib.SMTPAuthenticationError):
            raise self.error
        self.enviado = (correo, from_addr, to_addrs)


def adaptador_smtp(fabrica, **extra) -> AdaptadorCorreoSMTP:
    datos = dict(host="smtp.u.edu.co", puerto=587, remitente="no-responder@u.edu.co", usuario="robot", clave="ClaveSMTP#123",
                 fabrica_smtp=fabrica)
    return AdaptadorCorreoSMTP(**(datos | extra))


MENSAJE = MensajeCorreo("ana@u.edu.co", "Inter Nos: aviso", "Texto plano", "<p>HTML</p>", "<entrega-1@u.edu.co>")


class TestAdaptadorSMTP:
    def test_adapta_el_formato_y_usa_tls_verificado(self):
        smtp = SMTPFalso()
        adaptador_smtp(smtp).enviar(MENSAJE)
        correo, remitente, destinatarios = smtp.enviado
        assert (correo["To"], correo["Subject"], correo["Message-ID"]) == ("ana@u.edu.co", "Inter Nos: aviso", "<entrega-1@u.edu.co>")
        assert "no-responder@u.edu.co" in correo["From"] and correo.is_multipart()
        assert (remitente, destinatarios) == ("no-responder@u.edu.co", ["ana@u.edu.co"])
        assert smtp.llamadas[1] == ("starttls", True, True)
        assert smtp.llamadas[2] == ("login", "robot")
        assert smtp.llamadas[0][3] == 10  # timeout

    def test_ssl_implicito_sin_starttls(self):
        smtp = SMTPFalso()
        adaptador_smtp(smtp, ssl_implicito=True, puerto=465).enviar(MENSAJE)
        assert smtp.llamadas[0][4] is True and not any(c[0] == "starttls" for c in smtp.llamadas)

    @pytest.mark.parametrize(
        ("error", "tipo"),
        [
            (smtplib.SMTPAuthenticationError(535, b"bad ClaveSMTP#123"), ErrorCorreoPermanente),
            (smtplib.SMTPRecipientsRefused({"ana@u.edu.co": (550, b"no")}), ErrorCorreoPermanente),
            (smtplib.SMTPDataError(554, b"rechazado"), ErrorCorreoPermanente),
            (smtplib.SMTPDataError(451, b"intente luego"), ErrorCorreoTemporal),
            (smtplib.SMTPServerDisconnected("caído"), ErrorCorreoTemporal),
            (socket.timeout("lento"), ErrorCorreoTemporal),
            (ConnectionRefusedError("rechazada"), ErrorCorreoTemporal),
            (ssl.SSLCertVerificationError("cert"), ErrorCorreoPermanente),
        ],
    )
    def test_errores_del_proveedor_se_traducen_sin_filtrar_secretos(self, error, tipo):
        with pytest.raises(tipo) as exc:
            adaptador_smtp(SMTPFalso(error)).enviar(MENSAJE)
        assert "ClaveSMTP#123" not in str(exc.value) and "Texto plano" not in str(exc.value)
        assert exc.value.__cause__ is None  # sin encadenar la excepción original (podría llevar datos)

    def test_repr_no_muestra_la_clave(self):
        assert "ClaveSMTP#123" not in repr(adaptador_smtp(SMTPFalso()))


def settings(**extra) -> Settings:
    base = {
        "DATABASE_URL": get_settings().DATABASE_URL,
        "JWT_SECRET_KEY": "x" * 40,
        "CONVOCATION_CODE_ENCRYPTION_KEY": get_settings().CONVOCATION_CODE_ENCRYPTION_KEY,
        "NOTIFICATIONS_EMAIL_ENABLED": True,
        "SMTP_HOST": "smtp.u.edu.co",
        "SMTP_FROM_EMAIL": "no-responder@u.edu.co",
        "SIMULATOR_ACCESS_URL": "https://internos.u.edu.co",
        "SMTP_USERNAME": "robot",
        "SMTP_PASSWORD": SecretStr("ClaveSMTP#123"),
    }
    return Settings(_env_file=None, **(base | extra))


class TestConfiguracionCorreo:
    def test_desactivado_no_crea_adaptador(self):
        assert crear_servicio_correo(settings(NOTIFICATIONS_EMAIL_ENABLED=False)) is None

    def test_configuracion_completa(self):
        assert isinstance(crear_servicio_correo(settings()), AdaptadorCorreoSMTP)

    def test_el_secreto_no_aparece_en_la_configuracion(self):
        assert "ClaveSMTP#123" not in repr(settings()) and "ClaveSMTP#123" not in str(settings().model_dump())

    @pytest.mark.parametrize(
        ("extra", "fragmento"),
        [
            ({"SMTP_HOST": None}, "SMTP_HOST"),
            ({"SIMULATOR_ACCESS_URL": None}, "SIMULATOR_ACCESS_URL"),
            ({"SMTP_PASSWORD": None}, "SMTP_PASSWORD"),
            ({"SMTP_FROM_EMAIL": "no es correo"}, "SMTP_FROM_EMAIL"),
            ({"SMTP_USE_STARTTLS": False}, "sin TLS"),
            ({"SMTP_USE_STARTTLS": False, "SMTP_HOST": "localhost"}, "credenciales"),
            ({"SIMULATOR_ACCESS_URL": "http://internos.u.edu.co"}, "https"),
            ({"SIMULATOR_ACCESS_URL": "internos"}, "absoluta"),
        ],
    )
    def test_configuracion_invalida_falla_de_forma_explicita(self, extra, fragmento):
        with pytest.raises(ConfiguracionCorreoError) as exc:
            crear_servicio_correo(settings(**extra))
        assert fragmento in str(exc.value) and "ClaveSMTP#123" not in str(exc.value)

    def test_smtp_local_sin_tls_para_desarrollo(self):
        adaptador = crear_servicio_correo(settings(SMTP_USE_STARTTLS=False, SMTP_HOST="localhost", SMTP_USERNAME=None, SMTP_PASSWORD=None))
        assert isinstance(adaptador, AdaptadorCorreoSMTP)

    def test_url_local_http_admitida(self):
        assert validar_url_acceso("http://localhost:5173") == "http://localhost:5173"


# --- Plantillas ------------------------------------------------------------------------------------

TZ = plantillas.zona(-5)
DATOS = plantillas.DatosAviso(
    caso_nombre="Conformidad <script>alert(1)</script>",
    inicio=datetime(2026, 11, 10, 13, 0, tzinfo=UTC),
    fin=datetime(2026, 11, 10, 15, 0, tzinfo=UTC),
    tiempo_max_min=40,
    lugar="Aula 301 & virtual",
    mensaje_docente="Traigan audífonos",
    nombre_estudiante="Ana Pérez",
    correo_estudiante="ana@u.edu.co",
    numero_intento=2,
)


class TestPlantillas:
    def test_convocatoria_completa(self):
        c = plantillas.correo(T.CONVOCATORIA, DATOS, TZ, codigo=CODIGO, url="https://internos.u.edu.co")
        for dato in ("Inter Nos", "10/11/2026", "08:00 (UTC-05:00)", "10:00 (UTC-05:00)", "40 minutos", "Aula 301 & virtual",
                     "ana@u.edu.co", CODIGO, "https://internos.u.edu.co", "Traigan audífonos"):
            assert dato in c.texto
        assert CODIGO in c.html and "Conformidad" in c.asunto

    def test_html_escapa_el_contenido_de_usuarios(self):
        c = plantillas.correo(T.REPROGRAMACION, DATOS, TZ)
        assert "<script>" not in c.html and "&lt;script&gt;" in c.html and "Aula 301 &amp; virtual" in c.html

    @pytest.mark.parametrize("tipo", [T.CONVOCATORIA, T.CODIGO_REGENERADO])
    def test_correo_con_codigo_lo_exige(self, tipo):
        with pytest.raises(ValueError):
            plantillas.correo(tipo, DATOS, TZ, url="https://x.co")

    def test_codigo_regenerado_anuncia_el_nuevo(self):
        c = plantillas.correo(T.CODIGO_REGENERADO, DATOS, TZ, codigo=CODIGO, url="https://x.co")
        assert "nuevo código" in c.texto.lower() and "dejó de ser válido" in c.texto and c.texto.count(CODIGO) == 1

    @pytest.mark.parametrize("tipo", [T.REPROGRAMACION, T.REVOCACION, T.RESULTADOS_DISPONIBLES, T.CALIFICACION_ACTUALIZADA])
    def test_correos_sin_codigo(self, tipo):
        c = plantillas.correo(tipo, DATOS, TZ)
        assert CODIGO not in c.texto + c.html and "Código de autorización" not in c.texto

    def test_reprogramacion_muestra_datos_actualizados(self):
        c = plantillas.correo(T.REPROGRAMACION, DATOS, TZ)
        assert "10/11/2026" in c.texto and "08:00" in c.texto and "40 minutos" in c.texto

    def test_resultados_sin_nota_ni_respuestas(self):
        c = plantillas.correo(T.RESULTADOS_DISPONIBLES, DATOS, TZ)
        assert "consultarse en la plataforma" in c.texto
        assert not any(p in c.texto.lower() for p in ("nota", "correcta", "justificación"))

    def test_retroalimentacion_es_solo_interna(self):
        assert T.RETROALIMENTACION not in plantillas.TIPOS_CON_CORREO
        with pytest.raises(ValueError):
            plantillas.correo(T.RETROALIMENTACION, DATOS, TZ)
        titulo, mensaje = plantillas.aviso_interno(T.RETROALIMENTACION, DATOS, TZ)
        assert "retroalimentación" in mensaje and "intento 2" in mensaje

    @pytest.mark.parametrize("tipo", list(T))
    def test_avisos_internos_nunca_llevan_codigo_ni_nota(self, tipo):
        titulo, mensaje = plantillas.aviso_interno(tipo, DATOS, TZ)
        assert titulo and mensaje and CODIGO not in mensaje and "nota" not in mensaje.lower()

    def test_solo_convocatoria_y_codigo_llevan_codigo(self):
        assert plantillas.TIPOS_CON_CODIGO == {T.CONVOCATORIA, T.CODIGO_REGENERADO}


# --- Revalidación de entregas ------------------------------------------------------------------------


def entrega(tipo, conv, huella="auto"):
    notificacion = SimpleNamespace(tipo=tipo, convocatoria_id=conv.id if conv else uuid.uuid4())
    huella = huella_codigo(conv.codigo_autorizacion) if huella == "auto" and conv else (None if huella == "auto" else huella)
    return SimpleNamespace(notificacion=notificacion, huella_codigo=huella)


class TestRevalidacionEntregas:
    def _servicio(self, conv):
        servicio = EntregasService(sesion_bd(), AdaptadorCorreoPruebas(), SimpleNamespace(ahora=lambda: AHORA))
        servicio._repo = MagicMock()
        servicio._repo.convocatoria.return_value = conv
        return servicio

    @pytest.mark.parametrize(
        ("tipo", "conv", "motivo"),
        [
            (T.CONVOCATORIA, convocatoria(activa=False), "revocada"),
            (T.CONVOCATORIA, convocatoria(estado=EstadoSesionEnum.FINALIZADO), "finalizó"),
            (T.REPROGRAMACION, convocatoria(estado=EstadoSesionEnum.FINALIZADO), "finalizó"),
            (T.RESULTADOS_DISPONIBLES, convocatoria(estado=EstadoSesionEnum.EN_CURSO), "aún no"),
            (T.REVOCACION, convocatoria(activa=True), "reactivó"),
            (T.CONVOCATORIA, None, "no existe"),
        ],
    )
    def test_entregas_obsoletas_se_cancelan(self, tipo, conv, motivo):
        assert motivo in self._servicio(conv).motivo_invalidez(entrega(tipo, conv))

    def test_codigo_regenerado_invalida_la_entrega(self):
        conv = convocatoria()
        assert "regenerado" in self._servicio(conv).motivo_invalidez(entrega(T.CODIGO_REGENERADO, conv, huella="otra"))

    @pytest.mark.parametrize(
        ("tipo", "conv"),
        [
            (T.CONVOCATORIA, convocatoria()),
            (T.REVOCACION, convocatoria(activa=False)),
            (T.RESULTADOS_DISPONIBLES, convocatoria(estado=EstadoSesionEnum.FINALIZADO)),
        ],
    )
    def test_entregas_vigentes(self, tipo, conv):
        assert self._servicio(conv).motivo_invalidez(entrega(tipo, conv)) is None

    def test_envio_desactivado_no_procesa(self):
        servicio = EntregasService(sesion_bd(), None)
        servicio._repo = MagicMock()
        assert servicio.procesar_pendientes().enviadas == 0
        servicio._repo.reclamar_entrega.assert_not_called()

    def test_estados_de_entrega(self):
        assert {e.value for e in EstadoEntregaEnum} == {"PENDIENTE", "EN_PROCESO", "ENVIADA", "FALLIDA", "CANCELADA"}


def test_reloj_de_referencia_utc():
    assert AHORA.utcoffset() == timedelta(0)


# --- Caminos de error del envío ------------------------------------------------------------------


class TestCaminosDeEnvio:
    def _servicio(self, entrega, correo=None):
        session = sesion_bd()
        servicio = EntregasService(session, correo or AdaptadorCorreoPruebas(), SimpleNamespace(ahora=lambda: AHORA))
        servicio._repo = MagicMock()
        servicio._repo.reclamar_entrega.side_effect = [entrega, None]
        servicio._repo.entrega_bloqueada.return_value = entrega
        servicio.motivo_invalidez = lambda e: None
        return servicio, session

    def _entrega(self, intentos=0):
        from app.modules.notifications.models import EntregaCorreo

        return EntregaCorreo(id=uuid.uuid4(), estado=EstadoEntregaEnum.PENDIENTE, intentos=intentos)

    def test_intentos_agotados_al_reclamar(self):
        entrega = self._entrega(get_settings().NOTIFICATIONS_MAX_ATTEMPTS)
        servicio, _ = self._servicio(entrega)
        assert servicio.procesar_pendientes().fallidas == 1 and entrega.estado == EstadoEntregaEnum.FALLIDA

    @pytest.mark.parametrize(
        ("error", "texto"),
        [(MensajeInvalidoError("Dirección de correo inválida."), "Dirección de correo inválida."), (ValueError(CODIGO), "No se pudo preparar")],
    )
    def test_mensaje_imposible_de_preparar_queda_fallido_sin_filtrar_datos(self, error, texto):
        entrega = self._entrega()
        servicio, _ = self._servicio(entrega)
        servicio.construir_mensaje = MagicMock(side_effect=error)
        assert servicio.procesar_pendientes().fallidas == 1
        assert texto in entrega.ultimo_error and CODIGO not in entrega.ultimo_error and entrega.intentos == 1

    def test_error_permanente_del_proveedor(self):
        entrega, correo = self._entrega(), AdaptadorCorreoPruebas()
        correo.fallar_con(ErrorCorreoPermanente("SMTP respondió con el código 554."))
        servicio, _ = self._servicio(entrega, correo)
        servicio.construir_mensaje = MagicMock(return_value=MENSAJE)
        assert servicio.procesar_pendientes().fallidas == 1
        assert (entrega.estado, entrega.ultimo_error) == (EstadoEntregaEnum.FALLIDA, "SMTP respondió con el código 554.")

    def test_si_otra_ejecucion_ya_la_cerro_no_se_sobrescribe(self):
        entrega = self._entrega()
        servicio, session = self._servicio(entrega)
        servicio.construir_mensaje = MagicMock(return_value=MENSAJE)
        enviar = servicio._correo.enviar

        def enviar_y_cerrar(mensaje):
            entrega.estado = EstadoEntregaEnum.CANCELADA  # p. ej., un administrador o un reinicio
            return enviar(mensaje)

        servicio._correo.enviar = enviar_y_cerrar
        assert servicio.procesar_pendientes().enviadas == 0 and entrega.estado == EstadoEntregaEnum.CANCELADA

    def test_un_fallo_inesperado_revierte_la_preparacion(self):
        entrega = self._entrega()
        servicio, session = self._servicio(entrega)
        servicio.construir_mensaje = MagicMock(side_effect=RuntimeError("bd caída"))
        with pytest.raises(RuntimeError):
            servicio.procesar_pendientes()
        session.rollback.assert_called()


def test_cli_del_worker(monkeypatch):
    from app.workers.notifications import __main__ as cli

    llamadas = []
    monkeypatch.setattr(cli, "ejecutar_una_vez", lambda: llamadas.append("una"))
    monkeypatch.setattr(cli, "ejecutar_periodicamente", lambda intervalo: llamadas.append(intervalo))
    assert cli.main([]) == 0 and cli.main(["--intervalo", "30"]) == 0
    assert llamadas == ["una", 30]


# --- Vigencia de los correos con código (límite real de ingreso) --------------------------------


class TestVigenciaCodigo:
    def _conv(self, estado=EstadoSesionEnum.EN_CURSO, activa=True):
        return convocatoria(activa=activa, estado=estado, limite=AHORA)

    @pytest.mark.parametrize(
        ("ahora", "estado", "esperado"),
        [
            (AHORA - timedelta(hours=2), EstadoSesionEnum.SIN_INICIAR, None),  # invitación para el futuro
            (AHORA, EstadoSesionEnum.EN_CURSO, None),  # el instante exacto del límite está permitido
            (AHORA + timedelta(seconds=1), EstadoSesionEnum.EN_CURSO, "plazo de ingreso"),
            (AHORA + timedelta(seconds=1), EstadoSesionEnum.SIN_INICIAR, "plazo de ingreso"),
            (AHORA, EstadoSesionEnum.FINALIZADO, "finalizó"),
        ],
    )
    def test_limite_de_ingreso(self, monkeypatch, ahora, estado, esperado):
        from app.modules.notifications.services import vigencia

        monkeypatch.setattr(vigencia, "ReingresoConParticipacionActiva", lambda db: SimpleNamespace(permite_reingreso=lambda c, a: False))
        motivo = vigencia.motivo_codigo_inutil(MagicMock(), self._conv(estado), ahora)
        assert motivo is None if esperado is None else esperado in motivo

    def test_reingreso_con_intento_en_curso_mantiene_util_el_codigo(self, monkeypatch):
        from app.modules.notifications.services import vigencia

        monkeypatch.setattr(vigencia, "ReingresoConParticipacionActiva", lambda db: SimpleNamespace(permite_reingreso=lambda c, a: True))
        assert vigencia.motivo_codigo_inutil(MagicMock(), self._conv(), AHORA + timedelta(minutes=10)) is None

    def test_revocada(self):
        from app.modules.notifications.services import vigencia

        assert "revocada" in vigencia.motivo_codigo_inutil(MagicMock(), self._conv(activa=False), AHORA)

    def test_el_observador_no_invita_fuera_de_plazo(self):
        conv = convocatoria(limite=AHORA - timedelta(minutes=1))
        servicio = doble_servicio(conv)
        ObservadorConvocatorias(servicio, AHORA, vigencia=lambda *a: "fuera de plazo").actualizar(
            evento(ev.CONVOCATORIA_CREADA, convocatoria_id=conv.id)
        )
        servicio.notificar.assert_not_called()


class TestReprogramacionVigente:
    def test_sin_invitacion_previa_solo_aviso_interno(self):
        convs = [convocatoria()]
        servicio = doble_servicio(
            sesion=SimpleNamespace(id=uuid.uuid4(), estado=EstadoSesionEnum.SIN_INICIAR), convocatorias_activas=convs, algun_codigo_enviado=False
        )
        ObservadorConvocatorias(servicio, AHORA).actualizar(evento(ev.SESION_MODIFICADA, campos="lugar,inicio"))
        kwargs = servicio.notificar.call_args.kwargs
        assert kwargs["correo"] is False and kwargs["cambios"] == ["inicio", "lugar"]

    def test_con_invitacion_enviada_cancela_avisos_superados_y_envia(self):
        convs = [convocatoria()]
        servicio = doble_servicio(
            sesion=SimpleNamespace(id=uuid.uuid4(), estado=EstadoSesionEnum.SIN_INICIAR), convocatorias_activas=convs, algun_codigo_enviado=True
        )
        ObservadorConvocatorias(servicio, AHORA).actualizar(evento(ev.SESION_MODIFICADA, campos="fin"))
        assert servicio.repo.cancelar_entregas.call_args.args[1] == [T.REPROGRAMACION]
        assert servicio.notificar.call_args.kwargs["correo"] is True

    def test_los_mensajes_identifican_el_cambio(self):
        titulo, mensaje = plantillas.aviso_interno(T.REPROGRAMACION, DATOS, TZ, cambios=["lugar", "inicio", "desconocido"])
        assert "Cambió: lugar o modalidad, fecha u hora de inicio." in mensaje and "Programación vigente" in mensaje
        c = plantillas.correo(T.REPROGRAMACION, DATOS, TZ, cambios=["fin"])
        assert "Cambió: hora de finalización." in c.texto and "vigentes al momento de este envío" in c.texto
        assert plantillas.describir_cambios(None) == ""
