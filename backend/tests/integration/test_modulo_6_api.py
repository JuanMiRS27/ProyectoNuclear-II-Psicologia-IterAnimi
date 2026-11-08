"""Módulo 6 contra PostgreSQL real: outbox, Observer, entregas (Adapter de pruebas) y endpoints.

Nunca se envían correos reales: el worker recibe `AdaptadorCorreoPruebas`. El entorno es el
del módulo 4: sesión 08:00-10:00 con tres estudiantes convocados e iniciada a las 08:00.
"""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.modules.notifications.adapters import AdaptadorCorreoPruebas, ErrorCorreoPermanente, ErrorCorreoTemporal
from app.modules.notifications.services import procesador_eventos
from app.modules.notifications.services.entregas_service import EntregasService
from app.modules.notifications.services.procesador_eventos import ProcesadorEventosService, espera_reintento
from app.workers.notifications import ejecutar_una_vez
from tests.conftest import bearer
from tests.participations_helpers import PART_URL, contar, en_paralelo, entorno, fila, guardar  # noqa: F401
from tests.sessions_helpers import SESSIONS_URL, codigo_de, programar

URL_ACCESO = "https://internos.universidad.test"
NOTIF_URL = "/api/v1/notifications"
ENTREGAS_URL = "/api/v1/notification-deliveries"


@pytest.fixture(autouse=True)
def url_de_acceso(monkeypatch):
    monkeypatch.setattr(get_settings(), "SIMULATOR_ACCESS_URL", URL_ACCESO)


@pytest.fixture
def correo():
    return AdaptadorCorreoPruebas()


def worker(entorno, correo):
    return ejecutar_una_vez(reloj=entorno.reloj, correo=correo)


def contar_tabla(tabla: str, where: str = "true", **params) -> int:
    return contar(f"SELECT count(*) FROM {tabla} WHERE {where}", **params)


def estados_entregas(estudiante=None) -> list[tuple[str, str]]:
    sql = "SELECT n.tipo::text, e.estado::text FROM entrega_correo e JOIN notificacion n ON n.id = e.notificacion_id"
    params = {}
    if estudiante is not None:
        sql += " WHERE n.destinatario_id = :d"
        params["d"] = estudiante.id
    with engine.connect() as conn:
        return sorted(tuple(f) for f in conn.execute(text(sql + " ORDER BY e.creada_en"), params))


def texto_persistido() -> str:
    """Todo el contenido de las tablas del módulo 6, como texto, para buscar fugas."""
    with engine.connect() as conn:
        partes = [str(f) for t in ("evento_outbox", "notificacion", "entrega_correo") for f in conn.execute(text(f"SELECT * FROM {t}"))]
    return "\n".join(partes)


def intento(entorno, indice=0, correctas=1, finalizar=True) -> str:
    headers = entorno.headers(indice)
    participacion = entorno.iniciar(headers)
    for pregunta in entorno.preguntas[:correctas]:
        guardar(entorno.client, headers, participacion["id"], pregunta["id"], pregunta["opciones"][0]["id"])
    if finalizar:
        entorno.client.post(f"{PART_URL}/{participacion['id']}/finish", headers=headers)
    return participacion["id"]


def finalizar_sesion(entorno):
    assert entorno.client.post(f"{SESSIONS_URL}/{entorno.sesion_id}/finish", headers=entorno.docente_headers).status_code == 200


def evaluar(entorno):
    r = entorno.client.post(f"{SESSIONS_URL}/{entorno.sesion_id}/evaluations/process", headers=entorno.docente_headers)
    assert r.status_code == 200, r.text


def tipos_notificaciones(estudiante) -> list[str]:
    with engine.connect() as conn:
        return sorted(r[0] for r in conn.execute(text("SELECT tipo::text FROM notificacion WHERE destinatario_id = :d"), {"d": estudiante.id}))


# --- Outbox y convocatorias ------------------------------------------------------------------------


def test_convocatorias_registran_eventos_y_entregan_el_codigo_vigente(entorno, correo):
    assert contar_tabla("evento_outbox", "tipo = 'CONVOCATORIA_CREADA'") == 3  # en la transacción de la programación

    pasada = worker(entorno, correo)

    assert pasada.entregas.enviadas == 3
    for estudiante in entorno.estudiantes:
        [mensaje] = correo.para(estudiante.correo)
        codigo = entorno.codigos[estudiante.correo]
        assert codigo in mensaje.texto and URL_ACCESO in mensaje.texto and estudiante.correo in mensaje.texto
        assert "Conformidad en el aula" in mensaje.asunto
        assert mensaje.id_mensaje.startswith("<entrega-")
        otros = [e.correo for e in entorno.estudiantes if e is not estudiante]
        assert not any(o in mensaje.texto + (mensaje.html or "") for o in otros)  # sin datos de otros convocados
    persistido = texto_persistido()
    assert not any(c in persistido for c in entorno.codigos.values())  # el código nunca se guarda en claro
    assert contar_tabla("evento_outbox", "estado <> 'PROCESADO'") == 0


def test_operacion_academica_revertida_no_deja_eventos(entorno):
    antes = contar_tabla("evento_outbox")
    repetido = entorno.client.post(
        f"{SESSIONS_URL}/{entorno.sesion_id}/convocations", headers=entorno.docente_headers,
        json={"estudiantes": [entorno.estudiantes[0].correo]},
    )
    assert repetido.status_code == 409
    assert contar_tabla("evento_outbox") == antes


def test_codigo_regenerado_antes_del_envio_solo_envia_el_nuevo(entorno, correo):
    estudiante = entorno.estudiantes[0]
    anterior = entorno.codigos[estudiante.correo]
    r = entorno.client.post(entorno.conv_url(0, "/regenerate-code"), headers=entorno.docente_headers, json={"motivo": "Lo compartió"})
    nuevo = r.json()["codigo_autorizacion"]

    worker(entorno, correo)

    mensajes = correo.para(estudiante.correo)
    assert [m.asunto.split(":")[1].split("—")[0].strip() for m in mensajes] == ["Nuevo código de autorización"]
    assert nuevo in mensajes[0].texto and anterior not in mensajes[0].texto
    assert estados_entregas(estudiante) == [("CODIGO_REGENERADO", "ENVIADA"), ("CONVOCATORIA", "CANCELADA")]


def test_codigo_regenerado_despues_del_envio(entorno, correo):
    estudiante = entorno.estudiantes[0]
    worker(entorno, correo)
    nuevo = entorno.client.post(
        entorno.conv_url(0, "/regenerate-code"), headers=entorno.docente_headers, json={"motivo": "Lo compartió"}
    ).json()["codigo_autorizacion"]

    worker(entorno, correo)

    ultimo = correo.para(estudiante.correo)[-1]
    assert nuevo in ultimo.texto and entorno.codigos[estudiante.correo] not in ultimo.texto


def test_revocacion_antes_del_envio_no_entrega_nada(entorno, correo):
    estudiante = entorno.estudiantes[1]
    assert entorno.client.delete(entorno.conv_url(1), headers=entorno.docente_headers).status_code == 204

    worker(entorno, correo)

    assert correo.para(estudiante.correo) == []
    assert len(correo.enviados) == 2


def test_revocacion_tras_recibir_el_codigo_avisa_sin_codigo(entorno, correo):
    estudiante = entorno.estudiantes[1]
    worker(entorno, correo)
    entorno.client.delete(entorno.conv_url(1), headers=entorno.docente_headers)

    worker(entorno, correo)

    aviso = correo.para(estudiante.correo)[-1]
    assert "Convocatoria retirada" in aviso.asunto and entorno.codigos[estudiante.correo] not in aviso.texto


def test_reactivacion_usa_el_codigo_vigente(entorno, correo):
    estudiante = entorno.estudiantes[2]
    worker(entorno, correo)
    entorno.client.delete(entorno.conv_url(2), headers=entorno.docente_headers)
    r = entorno.client.post(
        f"{SESSIONS_URL}/{entorno.sesion_id}/convocations", headers=entorno.docente_headers, json={"estudiantes": [estudiante.correo]}
    )
    assert r.status_code == 201, r.text
    vigente = codigo_de(entorno.client, entorno.docente_headers, entorno.sesion_id, r.json()[0]["id"])

    worker(entorno, correo)

    ultimo = correo.para(estudiante.correo)[-1]
    assert "Convocatoria a una sesión" in ultimo.asunto and vigente in ultimo.texto
    assert entorno.codigos[estudiante.correo] not in ultimo.texto


def test_reprogramacion_informa_los_datos_actualizados(client, creador_headers, reloj, espacio, caso_publicado, estudiantes, correo):
    sesion = programar(client, creador_headers, reloj, caso_publicado["id"], espacio.id, estudiantes[:2])
    ejecutar_una_vez(reloj=reloj, correo=correo)
    r = client.patch(f"{SESSIONS_URL}/{sesion['id']}", headers=creador_headers, json={"lugar": "Auditorio B"})
    assert r.status_code == 200, r.text

    ejecutar_una_vez(reloj=reloj, correo=correo)

    avisos = [m for m in correo.enviados if "Cambio de programación" in m.asunto]
    assert sorted(m.destinatario for m in avisos) == sorted(e.correo for e in estudiantes[:2])
    assert all("Auditorio B" in m.texto and "Código de autorización" not in m.texto for m in avisos)


# --- Resultados y retroalimentación (módulo 5) -------------------------------------------------------------


def test_caso_a_evaluar_y_luego_finalizar(entorno, correo):
    intento(entorno, 0)
    evaluar(entorno)  # sesión EN_CURSO: aún no visible
    worker(entorno, correo)
    assert "RESULTADOS_DISPONIBLES" not in tipos_notificaciones(entorno.estudiantes[0])

    finalizar_sesion(entorno)
    worker(entorno, correo)

    [aviso] = [m for m in correo.para(entorno.estudiantes[0].correo) if "Resultados disponibles" in m.asunto]
    assert "2.20" not in aviso.texto and "nota" not in aviso.texto.lower()
    assert tipos_notificaciones(entorno.estudiantes[1]).count("RESULTADOS_DISPONIBLES") == 0  # sin intento


def test_caso_b_finalizar_y_luego_evaluar(entorno, correo):
    intento(entorno, 0)
    finalizar_sesion(entorno)
    worker(entorno, correo)
    assert "RESULTADOS_DISPONIBLES" not in tipos_notificaciones(entorno.estudiantes[0])

    evaluar(entorno)
    worker(entorno, correo)

    assert tipos_notificaciones(entorno.estudiantes[0]).count("RESULTADOS_DISPONIBLES") == 1


def test_recalificacion_identica_no_duplica_y_un_cambio_avisa(entorno, correo):
    pid = intento(entorno, 0)
    finalizar_sesion(entorno)
    evaluar(entorno)
    worker(entorno, correo)
    evaluar(entorno)
    entorno.client.post(f"/api/v1/participations/{pid}/evaluation/recalculate", headers=entorno.docente_headers)
    worker(entorno, correo)
    assert tipos_notificaciones(entorno.estudiantes[0]).count("RESULTADOS_DISPONIBLES") == 1
    assert "CALIFICACION_ACTUALIZADA" not in tipos_notificaciones(entorno.estudiantes[0])

    with engine.begin() as conn:
        conn.execute(text("UPDATE participacion SET nota_final = 4.00 WHERE id = :id"), {"id": pid})
    entorno.client.post(f"/api/v1/participations/{pid}/evaluation/recalculate", headers=entorno.docente_headers)
    worker(entorno, correo)

    assert tipos_notificaciones(entorno.estudiantes[0]).count("CALIFICACION_ACTUALIZADA") == 1


def test_retroalimentacion_se_avisa_cuando_es_visible(entorno, correo):
    pid = intento(entorno, 0)
    evaluar(entorno)
    url = f"/api/v1/participations/{pid}/feedback"
    entorno.client.patch(url, headers=entorno.docente_headers, json={"retroalimentacion_general": "Revisa la presión grupal."})
    worker(entorno, correo)
    assert "RETROALIMENTACION" not in tipos_notificaciones(entorno.estudiantes[0])  # sesión aún en curso

    finalizar_sesion(entorno)
    worker(entorno, correo)
    entorno.client.patch(url, headers=entorno.docente_headers, json={"retroalimentacion_general": "Revisa la presión grupal."})
    worker(entorno, correo)
    assert tipos_notificaciones(entorno.estudiantes[0]).count("RETROALIMENTACION") == 1

    entorno.client.patch(url, headers=entorno.docente_headers, json={"retroalimentacion_general": "Nueva observación."})
    worker(entorno, correo)
    assert tipos_notificaciones(entorno.estudiantes[0]).count("RETROALIMENTACION") == 2
    assert contar_tabla("entrega_correo e JOIN notificacion n ON n.id = e.notificacion_id", "n.tipo = 'RETROALIMENTACION'") == 0
    assert "Revisa la presión" not in texto_persistido()  # el aviso no copia el texto del docente


def test_finalizar_cancela_invitaciones_pendientes(entorno, correo):
    with SessionLocal() as session:  # las invitaciones ya están preparadas, aún sin enviar
        ProcesadorEventosService(session, entorno.reloj).procesar_pendientes()
    finalizar_sesion(entorno)
    worker(entorno, correo)
    assert correo.enviados == []
    assert {estado for _, estado in estados_entregas()} == {"CANCELADA"}


def test_evento_obsoleto_no_crea_invitaciones(entorno, correo):
    finalizar_sesion(entorno)  # los CONVOCATORIA_CREADA se procesan cuando la sesión ya terminó
    worker(entorno, correo)
    assert correo.enviados == [] and contar_tabla("notificacion", "tipo = 'CONVOCATORIA'") == 0


# --- Notificaciones internas y permisos -----------------------------------------------------------------


def test_notificaciones_propias_durante_y_despues_de_la_sesion(entorno, correo):
    worker(entorno, correo)
    propio, ajeno = entorno.headers(0), entorno.headers(1)

    lista = entorno.client.get(NOTIF_URL, headers=propio)
    [aviso] = lista.json()["items"]
    contador = entorno.client.get(f"{NOTIF_URL}/unread-count", headers=propio).json()
    detalle_ajeno = entorno.client.get(f"{NOTIF_URL}/{aviso['id']}", headers=ajeno)
    marcar_ajeno = entorno.client.patch(f"{NOTIF_URL}/{aviso['id']}/read", headers=ajeno)
    primera = entorno.client.patch(f"{NOTIF_URL}/{aviso['id']}/read", headers=propio).json()
    segunda = entorno.client.patch(f"{NOTIF_URL}/{aviso['id']}/read", headers=propio).json()

    assert lista.status_code == 200 and lista.headers["cache-control"] == "no-store"
    assert aviso["tipo"] == "CONVOCATORIA" and entorno.codigos[entorno.estudiantes[0].correo] not in aviso["mensaje"]
    assert contador == {"no_leidas": 1}
    assert (detalle_ajeno.status_code, marcar_ajeno.status_code) == (404, 404)
    assert primera["leida"] and primera["leida_en"] == segunda["leida_en"]
    assert entorno.client.get(f"{NOTIF_URL}/unread-count", headers=propio).json() == {"no_leidas": 0}
    assert entorno.client.get(f"{NOTIF_URL}?no_leidas=true", headers=propio).json()["total"] == 0

    finalizar_sesion(entorno)
    estudiante = entorno.estudiantes[0]
    r = entorno.client.post("/api/v1/auth/student/results-login", json={"correo": estudiante.correo, "codigo": entorno.codigos[estudiante.correo]})
    resultados = bearer(r.json()["access_token"])
    assert entorno.client.get(NOTIF_URL, headers=resultados).json()["total"] == 1
    assert entorno.client.post(f"/api/v1/student/sessions/{entorno.sesion_id}/participations", headers=resultados).status_code == 401


def test_docente_no_ve_notificaciones_de_estudiantes(entorno, correo):
    worker(entorno, correo)
    aviso = entorno.client.get(NOTIF_URL, headers=entorno.headers(0)).json()["items"][0]
    assert entorno.client.get(NOTIF_URL, headers=entorno.docente_headers).json()["total"] == 0
    assert entorno.client.get(f"{NOTIF_URL}/{aviso['id']}", headers=entorno.docente_headers).status_code == 404


@pytest.mark.parametrize("cabeceras", [{}, {"Authorization": "Bearer basura"}, {"Authorization": "Basic x"}])
def test_notificaciones_exigen_autenticacion(client, cabeceras):
    assert client.get(NOTIF_URL, headers=cabeceras).status_code == 401
    assert client.get(f"{NOTIF_URL}/{uuid.uuid4()}", headers=cabeceras).status_code == 401


def test_administracion_de_entregas_solo_administrador(entorno, correo, admin_headers):
    correo.fallar_con(*(ErrorCorreoPermanente("SMTP rechazó el destinatario.") for _ in range(3)))
    worker(entorno, correo)

    lista = entorno.client.get(f"{ENTREGAS_URL}?estado=FALLIDA", headers=admin_headers)
    assert lista.status_code == 200 and lista.json()["total"] == 3
    item = lista.json()["items"][0]
    assert item["ultimo_error"] == "SMTP rechazó el destinatario." and "correo" not in item and "mensaje" not in item
    for headers in (entorno.docente_headers, entorno.headers(0), {}):
        assert entorno.client.get(ENTREGAS_URL, headers=headers).status_code in (401, 403)
        assert entorno.client.post(f"{ENTREGAS_URL}/{item['id']}/retry", headers=headers).status_code in (401, 403)

    reintento = entorno.client.post(f"{ENTREGAS_URL}/{item['id']}/retry", headers=admin_headers)
    repetido = entorno.client.post(f"{ENTREGAS_URL}/{item['id']}/retry", headers=admin_headers)
    worker(entorno, correo)

    assert (reintento.status_code, reintento.json()["estado"], repetido.status_code) == (200, "PENDIENTE", 409)
    assert len(correo.enviados) == 1
    assert entorno.client.post(f"{ENTREGAS_URL}/{uuid.uuid4()}/retry", headers=admin_headers).status_code == 404


# --- Reintentos, concurrencia y reinicios ------------------------------------------------------------------


def test_error_temporal_reintenta_con_espera_progresiva(entorno, correo):
    correo.fallar_con(ErrorCorreoTemporal("Tiempo de espera agotado con el servidor SMTP."))
    worker(entorno, correo)
    pendiente = fila("SELECT estado::text AS e, intentos, proximo_intento_en, ultimo_error FROM entrega_correo WHERE intentos = 1 AND estado = 'PENDIENTE'")
    assert pendiente.proximo_intento_en is not None and "Tiempo de espera" in pendiente.ultimo_error

    worker(entorno, correo)  # misma hora: aún no toca
    assert len(correo.enviados) == 2
    entorno.reloj.avanzar(seconds=get_settings().NOTIFICATIONS_RETRY_BASE_SECONDS)
    worker(entorno, correo)

    assert len(correo.enviados) == 3
    assert {e for _, e in estados_entregas()} == {"ENVIADA"}


def test_intentos_agotados_quedan_fallidos(entorno, correo):
    maximo = get_settings().NOTIFICATIONS_MAX_ATTEMPTS
    for n in range(1, maximo + 1):  # en cada pasada falla el primer envío: siempre la misma entrega pendiente
        correo.fallar_con(ErrorCorreoTemporal("caído"))
        worker(entorno, correo)
        entorno.reloj.avanzar(seconds=espera_reintento(n).total_seconds())  # dentro del plazo de ingreso
    assert sorted(e for _, e in estados_entregas()) == ["ENVIADA", "ENVIADA", "FALLIDA"]
    assert fila("SELECT intentos FROM entrega_correo WHERE estado = 'FALLIDA'").intentos == maximo
    worker(entorno, correo)  # una FALLIDA no se reintenta sola
    assert len(correo.enviados) == 2


def test_worker_repetido_es_idempotente(entorno, correo):
    worker(entorno, correo)
    antes = (contar_tabla("notificacion"), contar_tabla("entrega_correo"), len(correo.enviados))
    segunda = worker(entorno, correo)
    assert (contar_tabla("notificacion"), contar_tabla("entrega_correo"), len(correo.enviados)) == antes
    assert (segunda.eventos.procesados, segunda.entregas.enviadas) == (0, 0)


def test_workers_concurrentes_no_duplican(entorno):
    correo = AdaptadorCorreoPruebas()
    resultados = en_paralelo(*(lambda: ejecutar_una_vez(reloj=entorno.reloj, correo=correo) for _ in range(3)))
    assert not any(isinstance(r, Exception) for r in resultados), resultados
    assert sum(r.eventos.procesados for r in resultados) == contar_tabla("evento_outbox")
    assert len(correo.enviados) == 3 and len({m.destinatario for m in correo.enviados}) == 3


def test_reserva_vencida_tras_caida_se_retoma(entorno, correo):
    with SessionLocal() as session:
        ProcesadorEventosService(session, entorno.reloj).procesar_pendientes()
    with engine.begin() as conn:  # un worker reclamó una entrega y cayó antes de enviarla
        conn.execute(text(
            "UPDATE entrega_correo SET estado = 'EN_PROCESO', intentos = 1, proximo_intento_en = :t "
            "WHERE id = (SELECT id FROM entrega_correo ORDER BY creada_en LIMIT 1)"
        ), {"t": entorno.reloj.actual + timedelta(minutes=1)})

    worker(entorno, correo)
    assert len(correo.enviados) == 2  # la reservada sigue reservada hasta que vence
    entorno.reloj.avanzar(minutes=1)
    worker(entorno, correo)

    assert len(correo.enviados) == 3


def test_eventos_pendientes_sobreviven_a_un_fallo_y_se_reintentan(entorno, correo, monkeypatch):
    original = procesador_eventos.crear_publicador

    def roto(*args, **kwargs):
        raise RuntimeError("caída simulada")

    monkeypatch.setattr(procesador_eventos, "crear_publicador", roto)
    with SessionLocal() as session:
        resumen = ProcesadorEventosService(session, entorno.reloj, roto).procesar_pendientes()
    assert resumen.reintentos == contar_tabla("evento_outbox") and contar_tabla("notificacion") == 0
    assert contar_tabla("evento_outbox", "ultimo_error = 'RuntimeError al procesar el evento.'") == resumen.reintentos

    monkeypatch.setattr(procesador_eventos, "crear_publicador", original)
    entorno.reloj.avanzar(seconds=get_settings().NOTIFICATIONS_RETRY_BASE_SECONDS)
    worker(entorno, correo)

    assert contar_tabla("evento_outbox", "estado <> 'PROCESADO'") == 0 and len(correo.enviados) == 3


def test_envio_desactivado_crea_avisos_y_deja_entregas_pendientes(entorno):
    pasada = ejecutar_una_vez(reloj=entorno.reloj, correo=None)
    assert pasada.eventos.procesados > 0 and pasada.entregas.enviadas == 0
    assert {e for _, e in estados_entregas()} == {"PENDIENTE"}
    assert contar_tabla("notificacion", "tipo = 'CONVOCATORIA'") == 3


def test_el_procesador_usa_la_configuracion_por_defecto_sin_envio(entorno):
    assert get_settings().NOTIFICATIONS_EMAIL_ENABLED is False
    assert ejecutar_una_vez(reloj=entorno.reloj).entregas.enviadas == 0


def test_programar_con_docente_ajeno_no_registra_eventos(client, otro_creador_headers, entorno):
    antes = contar_tabla("evento_outbox")
    r = client.post(f"{SESSIONS_URL}/{entorno.sesion_id}/finish", headers=otro_creador_headers)
    assert r.status_code == 404 and contar_tabla("evento_outbox") == antes


@pytest.mark.parametrize(
    ("cambio", "motivo"),
    [
        ("UPDATE convocatoria SET revocada_en = now() WHERE estudiante_id = :e", "Convocatoria revocada antes del envío."),
        ("UPDATE convocatoria SET codigo_autorizacion = 'v1.otro' WHERE estudiante_id = :e", "Código regenerado: entrega obsoleta."),
    ],
)
def test_cambio_concurrente_se_detecta_al_enviar(entorno, correo, cambio, motivo):
    """El estado cambia entre la preparación y el envío (sin que el worker vea aún su evento)."""
    estudiante = entorno.estudiantes[0]
    with SessionLocal() as session:
        ProcesadorEventosService(session, entorno.reloj).procesar_pendientes()
    with engine.begin() as conn:
        conn.execute(text(cambio), {"e": estudiante.id})
    with SessionLocal() as session:
        resumen = EntregasService(session, correo, entorno.reloj).procesar_pendientes()

    assert (resumen.enviadas, resumen.canceladas) == (2, 1) and correo.para(estudiante.correo) == []
    assert fila(
        "SELECT e.ultimo_error FROM entrega_correo e JOIN notificacion n ON n.id = e.notificacion_id WHERE n.destinatario_id = :d",
        d=estudiante.id,
    ).ultimo_error == motivo


# --- Entregas que quedaron pendientes con el envío desactivado --------------------------------------


def pendientes(reloj):
    """Pasada con el correo desactivado: se crean avisos y entregas, nada se envía."""
    pasada = ejecutar_una_vez(reloj=reloj, correo=None)
    assert pasada.entregas.enviadas == 0
    return pasada


def motivos(estado="CANCELADA") -> list[str]:
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT ultimo_error FROM entrega_correo WHERE estado::text = :e"), {"e": estado})]


def test_pendiente_valida_antes_del_inicio_se_envia_al_activar(client, creador_headers, reloj, espacio, caso_publicado, estudiantes, correo):
    programar(client, creador_headers, reloj, caso_publicado["id"], espacio.id, estudiantes[:2])  # 07:00, inicio 08:00
    pendientes(reloj)
    assert {e for _, e in estados_entregas()} == {"PENDIENTE"}

    ejecutar_una_vez(reloj=reloj, correo=correo)

    assert len(correo.enviados) == 2 and {e for _, e in estados_entregas()} == {"ENVIADA"}


def test_invitacion_con_plazo_de_ingreso_vencido_se_cancela(entorno, correo):
    pendientes(entorno.reloj)
    entorno.reloj.avanzar(hours=1, seconds=1)  # 09:00:01: pasó el límite de ingreso (09:00)

    worker(entorno, correo)

    assert correo.enviados == []
    assert motivos() == ["El plazo de ingreso terminó: la invitación ya no permite participar."] * 3
    assert not any(c in texto_persistido() for c in entorno.codigos.values())


def test_codigo_regenerado_tras_el_plazo_solo_llega_a_quien_puede_reingresar(entorno, correo):
    """Sesión 08:00-10:00, límite de ingreso 09:00, intentos de 40 minutos."""
    entorno.reloj.avanzar(minutes=50)  # 08:50: el estudiante 0 inicia (dentro del plazo); dura hasta 09:30
    intento(entorno, 0, finalizar=False)
    entorno.reloj.avanzar(minutes=15)  # 09:05: plazo vencido
    nuevos = {}
    for indice in (0, 1):
        r = entorno.client.post(entorno.conv_url(indice, "/regenerate-code"), headers=entorno.docente_headers, json={"motivo": "Lo compartió"})
        nuevos[indice] = r.json()["codigo_autorizacion"]

    worker(entorno, correo)

    [mensaje] = correo.enviados  # solo quien tiene un intento en curso puede reingresar con el código nuevo
    assert mensaje.destinatario == entorno.estudiantes[0].correo and nuevos[0] in mensaje.texto
    assert "Nuevo código" in mensaje.asunto
    assert correo.para(entorno.estudiantes[1].correo) == [] and correo.para(entorno.estudiantes[2].correo) == []


def test_sesion_finalizada_mientras_estaba_pendiente(entorno, correo):
    pendientes(entorno.reloj)
    finalizar_sesion(entorno)
    worker(entorno, correo)
    assert correo.enviados == [] and motivos() == ["La sesión finalizó antes del envío."] * 3


def test_convocatoria_revocada_mientras_estaba_pendiente(entorno, correo):
    pendientes(entorno.reloj)
    entorno.client.delete(entorno.conv_url(1), headers=entorno.docente_headers)
    worker(entorno, correo)
    assert len(correo.enviados) == 2 and correo.para(entorno.estudiantes[1].correo) == []
    assert motivos() == ["Convocatoria revocada antes del envío."]
    assert entorno.codigos[entorno.estudiantes[1].correo] not in texto_persistido()


def test_codigo_regenerado_despues_de_crear_la_entrega(entorno, correo):
    pendientes(entorno.reloj)
    estudiante = entorno.estudiantes[0]
    nuevo = entorno.client.post(
        entorno.conv_url(0, "/regenerate-code"), headers=entorno.docente_headers, json={"motivo": "Lo compartió"}
    ).json()["codigo_autorizacion"]

    worker(entorno, correo)

    [mensaje] = correo.para(estudiante.correo)
    assert nuevo in mensaje.texto and entorno.codigos[estudiante.correo] not in mensaje.texto
    assert dict(estados_entregas(estudiante)) == {"CODIGO_REGENERADO": "ENVIADA", "CONVOCATORIA": "CANCELADA"}


def test_reprogramada_antes_de_procesar_la_invitacion(client, creador_headers, reloj, espacio, caso_publicado, estudiantes, correo):
    sesion = programar(client, creador_headers, reloj, caso_publicado["id"], espacio.id, estudiantes[:1])
    client.patch(f"{SESSIONS_URL}/{sesion['id']}", headers=creador_headers, json={"lugar": "Auditorio B"})

    ejecutar_una_vez(reloj=reloj, correo=correo)

    [invitacion] = correo.enviados  # sin correo de "cambio": la invitación ya lleva los datos vigentes
    assert "Convocatoria a una sesión" in invitacion.asunto and "Auditorio B" in invitacion.texto
    aviso = fila("SELECT mensaje FROM notificacion WHERE tipo = 'REPROGRAMACION'")
    assert "Cambió: lugar o modalidad." in aviso.mensaje and "Programación vigente" in aviso.mensaje
    assert contar_tabla("entrega_correo e JOIN notificacion n ON n.id = e.notificacion_id", "n.tipo = 'REPROGRAMACION'") == 0


def test_varios_cambios_pendientes_envian_un_solo_aviso_vigente(client, creador_headers, reloj, espacio, caso_publicado, estudiantes, correo):
    sesion = programar(client, creador_headers, reloj, caso_publicado["id"], espacio.id, estudiantes[:1])
    ejecutar_una_vez(reloj=reloj, correo=correo)  # invitación enviada
    client.patch(f"{SESSIONS_URL}/{sesion['id']}", headers=creador_headers, json={"lugar": "Auditorio B"})
    client.patch(f"{SESSIONS_URL}/{sesion['id']}", headers=creador_headers, json={"lugar": "Sala 5"})

    ejecutar_una_vez(reloj=reloj, correo=correo)

    [cambio] = [m for m in correo.enviados if "Cambio de programación" in m.asunto]
    assert "Sala 5" in cambio.texto and "Auditorio B" not in cambio.texto and "Cambió: lugar o modalidad." in cambio.texto
    assert motivos() == ["Reprogramación superada por un cambio posterior."]


# --- Privacidad de la administración de entregas ------------------------------------------------------


def test_administracion_de_entregas_no_expone_secretos(entorno, correo, admin_headers, caplog, monkeypatch):
    from pydantic import SecretStr

    clave_smtp = "ClaveSMTP-Prueba#2026"
    monkeypatch.setattr(get_settings(), "SMTP_PASSWORD", SecretStr(clave_smtp))
    caplog.set_level("DEBUG")
    correo.fallar_con(ErrorCorreoPermanente("SMTP rechazó la autenticación (código 535)."), ErrorCorreoTemporal("caído"))
    worker(entorno, correo)
    lista = entorno.client.get(ENTREGAS_URL, headers=admin_headers)
    fallida = next(i for i in lista.json()["items"] if i["estado"] == "FALLIDA")
    reintento = entorno.client.post(f"{ENTREGAS_URL}/{fallida['id']}/retry", headers=admin_headers)
    conflicto = entorno.client.post(f"{ENTREGAS_URL}/{fallida['id']}/retry", headers=admin_headers)
    inexistente = entorno.client.post(f"{ENTREGAS_URL}/{uuid.uuid4()}/retry", headers=admin_headers)

    settings = get_settings()
    secretos = [
        *entorno.codigos.values(),
        clave_smtp,
        settings.CONVOCATION_CODE_ENCRYPTION_KEY,
        settings.JWT_SECRET_KEY,
        admin_headers["Authorization"].split()[1],
        entorno.docente_headers["Authorization"].split()[1],
    ]
    expuesto = "\n".join([lista.text, reintento.text, conflicto.text, inexistente.text, caplog.text, texto_persistido()])
    assert not [s for s in secretos if s in expuesto]
    assert set(fallida) == {
        "id", "notificacion_id", "tipo", "destinatario_id", "estado", "intentos", "creada_en",
        "ultimo_intento_en", "proximo_intento_en", "enviada_en", "ultimo_error",
    }  # sin dirección de correo, asunto ni cuerpo
    assert not any(e.correo in lista.text for e in entorno.estudiantes)
    assert (conflicto.json(), inexistente.json()) == (
        {"detail": "Solo se pueden reintentar entregas FALLIDAS."}, {"detail": "Entrega no encontrada."}
    )


@pytest.mark.parametrize("actor", ["anonimo", "docente", "estudiante_access", "token_estudiantil", "token_resultados"])
def test_administracion_de_entregas_rechaza_a_no_administradores(entorno, correo, actor, estudiante_headers):
    worker(entorno, correo)
    entrega_id = fila("SELECT id FROM entrega_correo LIMIT 1").id
    if actor == "token_resultados":
        finalizar_sesion(entorno)
        estudiante = entorno.estudiantes[0]
        r = entorno.client.post("/api/v1/auth/student/results-login", json={"correo": estudiante.correo, "codigo": entorno.codigos[estudiante.correo]})
        headers = bearer(r.json()["access_token"])
    else:
        headers = {
            "anonimo": {}, "docente": entorno.docente_headers, "estudiante_access": estudiante_headers,
            "token_estudiantil": entorno.headers(0),
        }[actor]
    esperado = 403 if actor in ("docente", "estudiante_access") else 401
    listado = entorno.client.get(ENTREGAS_URL, headers=headers)
    reintento = entorno.client.post(f"{ENTREGAS_URL}/{entrega_id}/retry", headers=headers)
    assert (listado.status_code, reintento.status_code) == (esperado, esperado)
    assert "items" not in listado.text
