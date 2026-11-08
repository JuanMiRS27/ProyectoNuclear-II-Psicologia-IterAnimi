"""Regresión: el módulo 7 solo consulta; los módulos 4, 5 y 6 siguen funcionando igual."""

from decimal import Decimal

from alembic.script import ScriptDirectory

from tests.conftest import alembic_config
from tests.participations_helpers import PART_URL, contar, entorno, fila, guardar  # noqa: F401
from tests.reports_helpers import API, finalizar_sesion, huella_academica, intento, procesar, url_sesion

TIPOS_EXPORTACION = ("resumen", "estudiantes", "intentos", "criterios", "preguntas")


def _consultar_todo(entorno) -> None:
    ids = [e.id for e in entorno.estudiantes]
    rutas = [url_sesion(entorno, s) for s in ("summary", "students", "grades", "criteria", "questions")]
    rutas += [url_sesion(entorno, f"students/{i}") for i in ids]
    rutas += [
        f"{API}/reports/my-sessions",
        f"{API}/academic-spaces/{entorno.sesion['espacio_academico_id']}/reports",
        f"{API}/academic-spaces/{entorno.sesion['espacio_academico_id']}/reports/export",
        f"{API}/cases/{entorno.caso['id']}/reports",
    ]
    rutas += [f"{url_sesion(entorno, 'export')}?tipo={t}" for t in TIPOS_EXPORTACION]
    for ruta in rutas:
        assert entorno.client.get(ruta, headers=entorno.docente_headers).status_code == 200, ruta


def test_el_modulo_7_no_agrega_migraciones():
    """Los reportes se resuelven con las tablas e índices existentes (ver README, "Módulo 7")."""
    script = ScriptDirectory.from_config(alembic_config())
    assert script.get_heads() == ["0011_notificaciones_eventos"]


def test_ningun_reporte_modifica_informacion_academica(entorno):
    intento(entorno, 0, {0: 0})
    intento(entorno, 1, {}, finalizar=False)
    procesar(entorno)
    antes = huella_academica()

    _consultar_todo(entorno)

    assert huella_academica() == antes
    finalizar_sesion(entorno)
    antes = huella_academica()
    _consultar_todo(entorno)
    assert huella_academica() == antes


def test_el_modulo_4_sigue_guardando_respuestas_tras_consultar_reportes(entorno):
    headers = entorno.headers(0)
    pid = entorno.iniciar(headers)["id"]
    _consultar_todo(entorno)
    pregunta = entorno.preguntas[0]

    r = guardar(entorno.client, headers, pid, pregunta["id"], pregunta["opciones"][1]["id"])

    assert r.status_code == 200, r.text
    assert contar("SELECT count(*) FROM respuesta WHERE participacion_id = :id", id=pid) == 1
    assert entorno.client.post(f"{PART_URL}/{pid}/finish", headers=headers).status_code == 200


def test_el_modulo_5_sigue_calculando_igual(entorno):
    pid = intento(entorno, 0, {0: 0})
    _consultar_todo(entorno)

    resultado = procesar(entorno)

    assert resultado["resultados"][0]["nota_final"] == "2.20"
    assert fila("SELECT nota_final FROM participacion WHERE id = :id", id=pid).nota_final == Decimal("2.20")
    assert procesar(entorno)["sin_cambios"] == 1  # sigue siendo idempotente


def test_el_modulo_6_sigue_registrando_eventos_y_los_reportes_no_agregan_ninguno(entorno):
    eventos = "SELECT count(*) FROM evento_outbox"
    intento(entorno, 0, {0: 0})
    antes = contar(eventos)
    _consultar_todo(entorno)
    assert contar(eventos) == antes

    finalizar_sesion(entorno)

    assert contar("SELECT count(*) FROM evento_outbox WHERE tipo = 'SESION_FINALIZADA'") == 1
