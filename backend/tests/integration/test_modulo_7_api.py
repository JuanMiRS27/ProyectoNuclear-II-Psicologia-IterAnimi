"""Módulo 7 por HTTP y servicios contra PostgreSQL real: seguimiento, estadísticas, permisos y exportación.

Caso de `dsl_valido()` (ver `tests/reports_helpers.py`): E1P1 y E2P1 del criterio ANALISIS (peso
60), E1P2 de DECISION (peso 40), opción 0 correcta, escala 5 y niveles 0 % -> 1.00,
50 % -> 3.00, 85 % -> 5.00. Todas las notas esperadas se derivan de esa rúbrica.
"""

import copy
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.database import SessionLocal, engine
from app.main import app
from app.modules.auth.models import RolUsuario
from app.modules.reports.dependencies import get_exportacion_service
from app.modules.reports.services import ExportacionService, ReportesSesionService
from tests.cases_helpers import crear_caso_completo, dsl_valido, publicar
from tests.conftest import bearer, login
from tests.participations_helpers import PART_URL, en_paralelo, entorno, fila, guardar  # noqa: F401
from tests.reports_helpers import (
    huella_academica,
    API,
    autorizar_intentos,
    finalizar_sesion,
    intento,
    leer_csv,
    obtener,
    procesar,
    responder,
    revocar,
    url_sesion,
)
from tests.sessions_helpers import SPACES_URL, codigo_de, convocatorias, iniciar, programar

D = Decimal
ENDPOINTS_SESION = ["summary", "students", "grades", "criteria", "questions", "export"]


def resumen(entorno):
    return obtener(entorno, url_sesion(entorno, "summary"))


def estudiantes(entorno, **filtros):
    return obtener(entorno, url_sesion(entorno, "students"), **filtros)


def exportar(entorno, headers=None, **params):
    return entorno.client.get(url_sesion(entorno, "export"), headers=headers or entorno.docente_headers, params=params)


def expirar_por_tiempo(entorno, indice, elecciones=None):
    headers = entorno.headers(indice)
    pid = entorno.iniciar(headers)["id"]
    responder(entorno, headers, pid, elecciones or {})
    entorno.reloj.avanzar(minutes=41)
    assert entorno.client.get(PART_URL, headers=headers).json()[0]["motivo_cierre"] == "TIEMPO_AGOTADO"
    return pid


# --- Resumen de sesión ---------------------------------------------------------------------------------------


def test_resumen_de_sesion_sin_convocatorias(client, creador_headers, reloj, espacio, caso_publicado):
    sesion = programar(client, creador_headers, reloj, caso_publicado["id"], espacio.id)
    base = f"{API}/sessions/{sesion['id']}/reports"

    r = client.get(f"{base}/summary", headers=creador_headers).json()

    assert r["sesion"]["estado"] == "SIN_INICIAR" and r["sesion"]["escala_max"] == "5.00"
    assert r["sesion"]["caso"]["id"] == caso_publicado["id"] and r["sesion"]["tiempo_max_min"] == 40
    assert set(r["convocatorias"].values()) == {0} and set(r["intentos"].values()) == {0}
    assert all(i == {"numerador": 0, "denominador": 0, "porcentaje": None} for i in r["indicadores"].values())
    notas = client.get(f"{base}/grades", headers=creador_headers).json()
    assert (notas["estadisticas"]["evaluados"], notas["estadisticas"]["promedio"]) == (0, None)
    assert client.get(f"{base}/students", headers=creador_headers).json()["items"] == []
    criterios = client.get(f"{base}/criteria", headers=creador_headers).json()
    assert criterios["intentos_considerados"] == 0
    assert all(c["porcentaje_aciertos"] is None and c["puntaje_promedio"] is None for c in criterios["criterios"])
    vacio = client.get(f"{base}/export", headers=creador_headers, params={"tipo": "estudiantes"})
    assert vacio.status_code == 200 and len(leer_csv(vacio.content)) == 1  # solo encabezados


def test_resumen_con_convocatorias_antes_de_iniciar(client, creador_headers, reloj, espacio, caso_publicado, estudiantes):
    sesion = programar(client, creador_headers, reloj, caso_publicado["id"], espacio.id, estudiantes)
    r = client.get(f"{API}/sessions/{sesion['id']}/reports/summary", headers=creador_headers).json()

    assert r["convocatorias"] | {} == {
        "activas": 3, "revocadas": 0, "activas_con_intento": 0, "activas_sin_intento": 3,
        "revocadas_con_intento": 0, "ausentes": 0, "pendientes": 3,
    }
    assert r["indicadores"]["tasa_participacion"] == {"numerador": 0, "denominador": 3, "porcentaje": "0.00"}
    lista = client.get(f"{API}/sessions/{sesion['id']}/reports/students", headers=creador_headers).json()
    assert {e["condicion"] for e in lista["items"]} == {"PENDIENTE"}


def test_participaciones_activas_no_declaran_ausencias_y_no_se_cierran_al_consultar(entorno):
    pid = intento(entorno, 0, {0: 0}, finalizar=False)
    entorno.reloj.avanzar(minutes=41)  # 08:41: tiempo agotado, plazo de ingreso (09:00) aún abierto

    r = resumen(entorno)

    assert (r["intentos"]["en_progreso"], r["intentos"]["vencidos_sin_cerrar"]) == (1, 1)
    assert (r["convocatorias"]["activas_con_intento"], r["convocatorias"]["pendientes"], r["convocatorias"]["ausentes"]) == (1, 2, 0)
    assert r["indicadores"]["tasa_finalizacion"] == {"numerador": 0, "denominador": 1, "porcentaje": "0.00"}
    # El reporte es de solo lectura: no cierra el intento vencido (lo hará el worker o la próxima petición).
    assert fila("SELECT estado::text FROM participacion WHERE id = :id", id=pid).estado == "EN_PROGRESO"
    entorno.reloj.avanzar(minutes=30)  # 09:11: plazo vencido, la sesión sigue EN_CURSO
    assert {e["condicion"] for e in estudiantes(entorno, condicion="PENDIENTE")["items"]} == {"PENDIENTE"}
    assert estudiantes(entorno, condicion="AUSENTE")["total"] == 0
    activo = estudiantes(entorno, intento_activo=True)
    assert activo["total"] == 1 and activo["items"][0]["intentos"][0]["situacion"] == "EN_PROGRESO"


def test_participaciones_cerradas_conservan_su_motivo(entorno):
    intento(entorno, 0, {0: 0})
    expirar_por_tiempo(entorno, 1, {0: 0})  # 08:41
    intento(entorno, 2, {}, finalizar=False)  # iniciado a las 08:41: se cerrará con la sesión, no por tiempo
    finalizar_sesion(entorno)

    i = resumen(entorno)["intentos"]

    assert (i["total"], i["finalizados"], i["expirados"]) == (3, 1, 2)
    assert (i["expirados_por_tiempo"], i["expirados_por_fin_de_sesion"], i["expirados_por_revocacion"]) == (1, 1, 0)
    assert i["en_progreso"] == 0
    motivos = {x["motivo_cierre"] for e in estudiantes(entorno)["items"] for x in e["intentos"]}
    assert motivos == {"VOLUNTARIO", "TIEMPO_AGOTADO", "SESION_FINALIZADA"}


def test_ausencias_se_declaran_al_finalizar_y_coinciden_con_el_modulo_5(entorno):
    intento(entorno, 0, {0: 0})
    finalizar_sesion(entorno)

    r = resumen(entorno)
    modulo_5 = entorno.client.get(f"{API}/sessions/{entorno.sesion_id}/absences", headers=entorno.docente_headers).json()

    assert (r["convocatorias"]["ausentes"], r["convocatorias"]["pendientes"]) == (2, 0) and len(modulo_5) == 2
    ausentes = estudiantes(entorno, condicion="AUSENTE")
    assert {e["estudiante_id"] for e in ausentes["items"]} == {a["estudiante_id"] for a in modulo_5}
    assert all(e["intentos"] == [] for e in ausentes["items"])  # no se inventan participaciones


def test_convocatorias_revocadas_no_son_ausencias_y_conservan_su_historial(entorno):
    intento(entorno, 0, {0: 0})
    intento(entorno, 1, {0: 0}, finalizar=False)
    revocar(entorno, 1)  # con un intento en curso: se cierra como CONVOCATORIA_REVOCADA
    revocar(entorno, 2)  # sin intentos
    finalizar_sesion(entorno)

    r = resumen(entorno)

    assert r["convocatorias"] | {} == {
        "activas": 1, "revocadas": 2, "activas_con_intento": 1, "activas_sin_intento": 0,
        "revocadas_con_intento": 1, "ausentes": 0, "pendientes": 0,
    }
    assert r["intentos"]["expirados_por_revocacion"] == 1
    assert r["indicadores"]["tasa_participacion"] == {"numerador": 1, "denominador": 1, "porcentaje": "100.00"}
    revocadas = estudiantes(entorno, convocatoria="revocadas")["items"]
    assert {e["condicion"] for e in revocadas} == {"REVOCADA"} and len(revocadas) == 2
    assert sorted(len(e["intentos"]) for e in revocadas) == [0, 1]  # el intento revocado sigue en el historial
    assert all(e["revocada_en"] is not None and not e["convocatoria_activa"] for e in revocadas)


# --- Calificaciones -----------------------------------------------------------------------------------------------


def test_estadisticas_de_notas_registradas_coinciden_con_el_modulo_5(entorno):
    intento(entorno, 0, {0: 0, 1: 0, 2: 0})  # 100 % y 100 % -> 5.00
    intento(entorno, 1, {0: 0})  # ANALISIS 50 % -> 3.00; DECISION 0 % -> 1.00 -> 2.20
    intento(entorno, 2, {})  # 1.00
    procesar(entorno)

    r = obtener(entorno, url_sesion(entorno, "grades"))
    modulo_5 = obtener(entorno, f"{API}/sessions/{entorno.sesion_id}/evaluations")

    e = r["estadisticas"]
    assert sorted(p["nota_final"] for p in modulo_5["participaciones"]) == ["1.00", "2.20", "5.00"]
    assert (e["evaluados"], e["minimo"], e["maximo"], e["mediana"]) == (3, "1.00", "5.00", "2.20")
    assert (e["promedio"], e["promedio_porcentaje_escala"], e["escala_max"]) == ("2.73", "54.67", "5.00")  # 8.20 / 3
    assert [t["cantidad"] for t in e["distribucion"]] == [0, 1, 1, 0, 1]
    assert (r["intentos_cerrados"], r["intentos_sin_nota"], r["estudiantes_con_nota"]) == (3, 0, 3)


def test_notas_nulas_no_se_promedian_como_cero(entorno):
    intento(entorno, 0, {0: 0})  # 2.20
    intento(entorno, 1, {}, finalizar=False)  # cierre administrativo sin respuestas -> SIN_CALIFICAR
    intento(entorno, 2, {1: 0}, finalizar=False)  # cierre administrativo con una respuesta -> se califica
    finalizar_sesion(entorno)

    antes = resumen(entorno)["intentos"]
    assert (antes["calificados"], antes["pendientes_de_calificacion"], antes["sin_calificar"]) == (0, 2, 1)

    procesar(entorno)
    despues = resumen(entorno)["intentos"]
    r = obtener(entorno, url_sesion(entorno, "grades"))

    assert (despues["calificados"], despues["pendientes_de_calificacion"], despues["sin_calificar"]) == (2, 0, 1)
    # 2.20 y 2.60 (ANALISIS 0 % -> 1.00; DECISION 100 % -> 5.00): el intento sin calificar no entra como 0.
    assert (r["estadisticas"]["evaluados"], r["estadisticas"]["promedio"], r["intentos_sin_nota"]) == (2, "2.40", 1)
    sin_nota = obtener(entorno, url_sesion(entorno, f"students/{entorno.estudiantes[1].id}"))["intentos"][0]
    assert (sin_nota["nota_final"], sin_nota["situacion"], sin_nota["preguntas_respondidas"]) == (None, "SIN_CALIFICAR", 0)


def test_estadisticas_distinguen_finalizadas_de_expiradas(entorno):
    intento(entorno, 0, {0: 0, 1: 0})  # 3.00×0.6 + 5.00×0.4 = 3.80
    expirar_por_tiempo(entorno, 1, {0: 0, 1: 0, 2: 0})  # 5.00
    procesar(entorno)

    r = obtener(entorno, url_sesion(entorno, "grades"))

    assert (r["por_estado"]["finalizados"]["evaluados"], r["por_estado"]["finalizados"]["promedio"]) == (1, "3.80")
    assert (r["por_estado"]["expirados"]["evaluados"], r["por_estado"]["expirados"]["promedio"]) == (1, "5.00")
    condiciones = {
        x["estado"]: x["condicion"]
        for i in (0, 1)
        for x in obtener(entorno, url_sesion(entorno, f"students/{entorno.estudiantes[i].id}"))["intentos"]
    }
    assert condiciones == {"FINALIZADA": "COMPLETA", "EXPIRADA": "INCOMPLETA"}


def test_varios_intentos_se_cuentan_por_intento_y_por_estudiante(entorno):
    intento(entorno, 0, {})  # 1.00
    autorizar_intentos(entorno, 0, 2)
    intento(entorno, 0, {0: 0, 1: 0, 2: 0})  # 5.00
    procesar(entorno)

    r = resumen(entorno)
    detalle = obtener(entorno, url_sesion(entorno, f"students/{entorno.estudiantes[0].id}"))
    fila_estudiante = next(e for e in estudiantes(entorno)["items"] if e["estudiante_id"] == str(entorno.estudiantes[0].id))
    notas = obtener(entorno, url_sesion(entorno, "grades"))

    assert (r["intentos"]["total"], r["convocatorias"]["activas_con_intento"]) == (2, 1)
    assert r["indicadores"]["tasa_participacion"] == {"numerador": 1, "denominador": 3, "porcentaje": "33.33"}
    assert [(i["numero_intento"], i["nota_final"]) for i in detalle["intentos"]] == [(1, "1.00"), (2, "5.00")]
    assert "nota_consolidada" not in detalle and "promedio" not in detalle
    assert (fila_estudiante["intentos_utilizados"], fila_estudiante["intentos_autorizados"], fila_estudiante["intentos_calificados"]) == (2, 2, 2)
    assert (notas["estadisticas"]["evaluados"], notas["estudiantes_con_nota"], notas["estadisticas"]["unidad"]) == (2, 1, "intento")


def test_criterios_y_preguntas_coinciden_con_el_desglose_del_modulo_5(entorno):
    pid = intento(entorno, 0, {0: 0, 1: 1})  # E1P1 acierto, E1P2 error, E2P1 sin responder
    procesar(entorno)

    criterios = obtener(entorno, url_sesion(entorno, "criteria"))
    preguntas = obtener(entorno, url_sesion(entorno, "questions"))
    detalle = obtener(entorno, f"{API}/participations/{pid}/evaluation")

    por_id = {c["criterio_id"]: c for c in criterios["criterios"]}
    for c in detalle["criterios"]:
        r = por_id[c["criterio_id"]]
        assert (r["aciertos"], r["errores"], r["sin_responder"], r["total_preguntas"]) == (c["aciertos"], c["errores"], c["sin_responder"], c["total_preguntas"])
        assert (r["porcentaje_aciertos"], r["puntaje_promedio"], r["peso"]) == (c["porcentaje_aciertos"], c["puntaje"], c["peso"])
    resultados = {p["pregunta_id"]: p["resultado"] for p in detalle["preguntas"]}
    for p in preguntas["preguntas"]:
        esperado = {"ACIERTO": (1, 0, 0), "ERROR": (0, 1, 0), "SIN_RESPUESTA": (0, 0, 1)}[resultados[p["pregunta_id"]]]
        assert (p["aciertos"], p["errores"], p["sin_responder"]) == esperado and p["intentos_considerados"] == 1
    assert [(p["orden_escenario"], p["orden"]) for p in preguntas["preguntas"]] == [(1, 1), (1, 2), (2, 1)]


def test_preguntas_con_varias_opciones_correctas_usan_la_regla_del_modulo_5(entorno):
    pregunta = entorno.preguntas[0]
    with engine.begin() as conn:  # dato histórico: la segunda opción también es correcta (no es multiselección)
        conn.execute(text("UPDATE opcion SET es_correcta = true WHERE id = :id"), {"id": pregunta["opciones"][1]["id"]})
    intento(entorno, 0, {0: 1})
    intento(entorno, 1, {0: 2})

    p = obtener(entorno, url_sesion(entorno, "questions"))["preguntas"][0]

    assert (p["aciertos"], p["errores"], p["porcentaje_aciertos"]) == (1, 1, "50.00")


class TestCriterioSinPreguntas:
    @pytest.fixture
    def caso_publicado(self, client, creador_headers):
        documento = dsl_valido()
        rubrica = documento["rubrica"]["criterios"]
        rubrica[0]["peso"], rubrica[1]["peso"] = 50, 30
        rubrica.append(copy.deepcopy(rubrica[1]) | {"clave": "EXTRA", "descripcion": "Criterio sin preguntas", "peso": 20})
        caso = crear_caso_completo(client, creador_headers, documento)
        r = publicar(client, creador_headers, caso["id"])
        assert r.status_code == 200, r.text
        return r.json()

    def test_se_reporta_como_no_evaluable(self, entorno):
        pid = intento(entorno, 0, {0: 0, 1: 0, 2: 0})
        procesar(entorno)

        criterios = {c["descripcion"]: c for c in obtener(entorno, url_sesion(entorno, "criteria"))["criterios"]}
        detalle = obtener(entorno, f"{API}/participations/{pid}/evaluation")

        extra = criterios["Criterio sin preguntas"]
        assert (extra["evaluable"], extra["total_preguntas"], extra["porcentaje_aciertos"], extra["puntaje_promedio"]) == (False, 0, None, None)
        assert "no evaluable" in extra["advertencia"]
        assert {c["politica"] for c in detalle["criterios"] if c["descripcion"] == "Criterio sin preguntas"} == {"SIN_EVIDENCIA"}
        assert detalle["nota_final"] == "5.00"  # el módulo 5 renormaliza; el reporte no altera la nota


# --- Espacio, caso y listado de sesiones ------------------------------------------------------------------------------


def _sesion_de_otro_docente(entorno, make_user, espacio):
    otro = make_user(RolUsuario.DOCENTE, puede_crear_casos=True)
    headers = bearer(login(entorno.client, otro.correo))
    caso = crear_caso_completo(entorno.client, headers)
    assert publicar(entorno.client, headers, caso["id"]).status_code == 200
    estudiante = make_user(RolUsuario.ESTUDIANTE, clave=None)
    sesion = programar(entorno.client, headers, entorno.reloj, caso["id"], espacio.id, [estudiante])
    entorno.reloj.avanzar(hours=1)  # 09:00: inicio de la sesión ajena (y límite de ingreso de la del entorno)
    assert iniciar(entorno.client, headers, sesion["id"]).status_code == 200
    conv = convocatorias(entorno.client, headers, sesion["id"])[0]
    codigo = codigo_de(entorno.client, headers, sesion["id"], conv["id"])
    token = entorno.client.post(f"{API}/auth/student/login", json={"correo": estudiante.correo, "codigo": codigo}).json()["access_token"]
    r = entorno.client.post(f"{API}/student/sessions/{sesion['id']}/participations", headers=bearer(token))
    assert r.status_code in (200, 201), r.text
    return headers, sesion, caso, estudiante


def test_espacio_compartido_solo_agrega_las_sesiones_del_docente(entorno, make_user, espacio):
    intento(entorno, 0, {0: 0})
    otro_headers, sesion_ajena, caso_ajeno, _ = _sesion_de_otro_docente(entorno, make_user, espacio)

    propio = obtener(entorno, f"{SPACES_URL}/{espacio.id}/reports")
    ajeno = obtener(entorno, f"{SPACES_URL}/{espacio.id}/reports", headers=otro_headers)

    assert (propio["sesiones_registradas"], propio["totales"]["intentos"], propio["alcance"]) == (1, 1, "sesiones_del_docente")
    assert [s["id"] for s in propio["sesiones"]["items"]] == [entorno.sesion_id]
    assert caso_ajeno["id"] not in {c["id"] for c in propio["casos_utilizados"]}
    assert (ajeno["sesiones_registradas"], ajeno["totales"]["intentos"], ajeno["totales"]["en_progreso"]) == (1, 1, 1)
    assert [s["id"] for s in ajeno["sesiones"]["items"]] == [sesion_ajena["id"]]
    exportado = entorno.client.get(f"{SPACES_URL}/{espacio.id}/reports/export", headers=entorno.docente_headers)
    filas = leer_csv(exportado.content)
    assert len(filas) == 2 and filas[1][0] == entorno.sesion_id and sesion_ajena["id"] not in exportado.text


def test_espacio_promedia_notas_normalizadas_y_por_caso(entorno):
    intento(entorno, 0, {0: 0, 1: 0, 2: 0})  # 5.00
    intento(entorno, 1, {0: 0})  # 2.20
    procesar(entorno)

    r = obtener(entorno, f"{SPACES_URL}/{entorno.sesion['espacio_academico_id']}/reports")

    assert r["promedio_porcentaje_escala"] == "72.00"  # (100 % + 44 %) / 2
    caso = r["casos_utilizados"][0]
    assert (caso["promedio"], caso["escala_max"], caso["evaluaciones_registradas"], caso["sesiones"]) == ("3.60", "5.00", 2, 1)
    assert (r["sesiones_por_estado"]["en_curso"], r["totales"]["evaluaciones_registradas"]) == (1, 2)


def test_espacio_inactivo_visible_solo_con_historial_propio(entorno, admin_headers, otro_creador_headers):
    espacio_id = entorno.sesion["espacio_academico_id"]
    r = entorno.client.patch(f"{SPACES_URL}/{espacio_id}/status", headers=admin_headers, json={"activo": False})
    assert r.status_code == 200, r.text

    assert entorno.client.get(f"{SPACES_URL}/{espacio_id}/reports", headers=entorno.docente_headers).status_code == 200
    assert entorno.client.get(f"{SPACES_URL}/{espacio_id}/reports", headers=otro_creador_headers).status_code == 404
    assert entorno.client.get(f"{SPACES_URL}/{espacio_id}/reports/export", headers=otro_creador_headers).status_code == 404
    assert entorno.client.get(f"{SPACES_URL}/{espacio_id}/reports", headers=admin_headers).status_code == 403


def test_caso_archivado_conserva_su_historial(entorno):
    intento(entorno, 0, {0: 0})  # 2.20
    intento(entorno, 1, {0: 0, 1: 0, 2: 0})  # 5.00
    finalizar_sesion(entorno)
    procesar(entorno)
    assert entorno.client.post(f"{API}/cases/{entorno.caso['id']}/archive", headers=entorno.docente_headers).status_code == 200

    r = obtener(entorno, f"{API}/cases/{entorno.caso['id']}/reports")

    assert (r["caso"]["estado"], r["sesiones_registradas"], r["sesiones_por_estado"]["finalizadas"]) == ("ARCHIVADO", 1, 1)
    assert (r["totales"]["intentos"], r["totales"]["evaluaciones_registradas"]) == (2, 2)
    assert (r["estadisticas"]["promedio"], r["estadisticas"]["evaluados"]) == ("3.60", 2)
    assert r["criterios"]["intentos_considerados"] == 2 and len(r["criterios"]["criterios"]) == 2
    assert r["sesiones"]["items"][0]["id"] == entorno.sesion_id


def test_mis_sesiones_con_filtros_y_rango_semiabierto(entorno):
    inicio = entorno.sesion["inicio"]
    url = f"{API}/reports/my-sessions"

    assert obtener(entorno, url)["total"] == 1
    assert obtener(entorno, url, estado="EN_CURSO")["total"] == 1
    assert obtener(entorno, url, estado="FINALIZADO")["total"] == 0
    assert obtener(entorno, url, desde=inicio)["total"] == 1  # desde incluido
    assert obtener(entorno, url, hasta=inicio)["total"] == 0  # hasta excluido
    assert obtener(entorno, url, caso_id=entorno.caso["id"], espacio_academico_id=entorno.sesion["espacio_academico_id"])["total"] == 1
    for invalido in ({"desde": "2026-11-04T00:00:00Z", "hasta": "2026-11-03T00:00:00Z"}, {"desde": "2026-11-03T00:00:00"}, {"limit": 101}):
        assert entorno.client.get(url, headers=entorno.docente_headers, params=invalido).status_code == 422


# --- Autorización ---------------------------------------------------------------------------------------------------


def test_autorizacion_de_todos_los_endpoints(entorno, admin_headers, otro_creador_headers, estudiante_headers):
    token_estudiante = entorno.headers(0)
    intento(entorno, 0, {0: 0})
    estudiante_id = entorno.estudiantes[0].id
    rutas = [url_sesion(entorno, e) for e in ENDPOINTS_SESION] + [
        url_sesion(entorno, f"students/{estudiante_id}"),
        f"{API}/academic-spaces/{entorno.sesion['espacio_academico_id']}/reports",
        f"{API}/academic-spaces/{entorno.sesion['espacio_academico_id']}/reports/export",
        f"{API}/cases/{entorno.caso['id']}/reports",
        f"{API}/reports/my-sessions",
    ]
    finalizar_sesion(entorno)
    estudiante = entorno.estudiantes[0]
    login_resultados = entorno.client.post(
        f"{API}/auth/student/results-login", json={"correo": estudiante.correo, "codigo": entorno.codigos[estudiante.correo]}
    )
    token_resultados = bearer(login_resultados.json()["access_token"])

    for ruta in rutas:
        assert entorno.client.get(ruta, headers=entorno.docente_headers).status_code == 200, ruta
        assert entorno.client.get(ruta).status_code == 401, ruta
        assert entorno.client.get(ruta, headers=token_estudiante).status_code == 401, ruta
        assert entorno.client.get(ruta, headers=token_resultados).status_code == 401, ruta
        assert entorno.client.get(ruta, headers=admin_headers).status_code == 403, ruta
        assert entorno.client.get(ruta, headers=estudiante_headers).status_code == 403, ruta
        # Otro docente: el espacio activo y su propio listado responden 200, pero vacíos (ver abajo); el resto, 404.
        alcance_propio = "academic-spaces" in ruta or ruta.endswith("my-sessions")
        assert entorno.client.get(ruta, headers=otro_creador_headers).status_code == (200 if alcance_propio else 404), ruta
    assert obtener(entorno, f"{API}/reports/my-sessions", headers=otro_creador_headers)["total"] == 0
    espacio = obtener(entorno, f"{API}/academic-spaces/{entorno.sesion['espacio_academico_id']}/reports", headers=otro_creador_headers)
    assert (espacio["sesiones_registradas"], espacio["totales"]["intentos"], espacio["casos_utilizados"]) == (0, 0, [])


def test_conocer_un_uuid_no_autoriza_el_acceso(entorno, make_user, espacio):
    otro_headers, sesion_ajena, caso_ajeno, estudiante_ajeno = _sesion_de_otro_docente(entorno, make_user, espacio)

    for ruta in (
        f"{API}/sessions/{sesion_ajena['id']}/reports/summary",
        f"{API}/sessions/{sesion_ajena['id']}/reports/students/{estudiante_ajeno.id}",
        f"{API}/sessions/{sesion_ajena['id']}/reports/export?tipo=intentos",
        url_sesion(entorno, f"students/{estudiante_ajeno.id}"),  # estudiante solo de una sesión ajena
        f"{API}/cases/{caso_ajeno['id']}/reports",
    ):
        r = entorno.client.get(ruta, headers=entorno.docente_headers)
        assert r.status_code == 404, ruta
        assert estudiante_ajeno.correo not in r.text
    assert entorno.client.get(f"{API}/sessions/{sesion_ajena['id']}/reports/summary", headers=otro_headers).status_code == 200


def test_parametros_desconocidos_no_amplian_el_alcance(entorno, otro_creador_headers, docente):
    for ruta, params in (
        (f"{API}/reports/my-sessions", {"docente_id": str(docente.id)}),
        (url_sesion(entorno, "students"), {"incluir_ajenos": "true"}),
        (url_sesion(entorno, "export"), {"tipo": "estudiantes", "columnas": "codigo_autorizacion"}),
        (url_sesion(entorno, "export"), {"formato": "xlsx"}),
    ):
        assert entorno.client.get(ruta, headers=otro_creador_headers, params=params).status_code == 422
        assert entorno.client.get(ruta, headers=entorno.docente_headers, params=params).status_code == 422


def test_las_rutas_de_reportes_solo_admiten_lectura(entorno):
    """Las 11 rutas del módulo 7 rechazan toda escritura (405) y la base no cambia."""
    from app.modules.reports.routers import router

    intento(entorno, 0, {0: 0})
    valores = {
        "session_id": entorno.sesion_id,
        "student_id": str(entorno.estudiantes[0].id),
        "space_id": entorno.sesion["espacio_academico_id"],
        "case_id": entorno.caso["id"],
    }
    rutas = [API + r.path.format(**valores) for r in router.routes]
    antes = huella_academica()
    assert len(rutas) == 11
    for ruta in rutas:
        for metodo in ("post", "put", "patch", "delete"):
            respuesta = getattr(entorno.client, metodo)(ruta, headers=entorno.docente_headers)
            assert respuesta.status_code == 405, (metodo, ruta)
    assert huella_academica() == antes


# --- Exportación --------------------------------------------------------------------------------------------------------


def test_exportaciones_csv_correctas_y_sin_datos_secretos(entorno):
    intento(entorno, 0, {0: 0})  # 2.20
    intento(entorno, 1, {}, finalizar=False)
    finalizar_sesion(entorno)  # el intento 2 queda SIN_CALIFICAR (cierre administrativo sin respuestas)
    procesar(entorno)
    cifrados = [f.codigo_autorizacion for f in _convocatorias_bd(entorno)]

    for tipo, columnas in (("resumen", 2), ("estudiantes", 12), ("intentos", 19), ("criterios", 13), ("preguntas", 12)):
        r = exportar(entorno, tipo=tipo)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "text/csv; charset=utf-8"
        assert r.headers["content-disposition"].startswith(f'attachment; filename="reporte_sesion_{tipo}_')
        assert r.headers["cache-control"] == "no-store"
        filas = leer_csv(r.content)
        assert {len(f) for f in filas} == {columnas}
        texto = r.content.decode("utf-8-sig")
        assert not any(c in texto for c in cifrados) and not any(c in texto for c in entorno.codigos.values())
        assert "clave" not in texto.lower() and "token" not in texto.lower()

    intentos = leer_csv(exportar(entorno, tipo="intentos").content)
    encabezado = intentos[0]
    por_nota = {f[encabezado.index("Situación")]: f for f in intentos[1:]}
    assert por_nota["CALIFICADO"][encabezado.index("Nota final")] == "2.20"
    assert por_nota["SIN_CALIFICAR"][encabezado.index("Nota final")] == ""  # nula, no 0
    assert por_nota["CALIFICADO"][encabezado.index("Inicio (UTC)")] == "2026-11-03T08:00:00Z"
    resumen_csv = dict(leer_csv(exportar(entorno, tipo="resumen").content)[1:])
    assert resumen_csv["Intentos sin calificar (política del módulo 5)"] == "1"
    assert resumen_csv["Tasa de participación (porcentaje)"] == "66.67"


def _convocatorias_bd(entorno):
    with engine.connect() as conn:
        return conn.execute(text("SELECT codigo_autorizacion FROM convocatoria WHERE sesion_id = :s"), {"s": entorno.sesion_id}).all()


def test_exportacion_respeta_los_filtros_de_la_consulta(entorno):
    intento(entorno, 0, {0: 0})
    intento(entorno, 1, {}, finalizar=False)
    nombre = entorno.estudiantes[1].nombre_completo

    participantes = leer_csv(exportar(entorno, tipo="estudiantes", condicion="PARTICIPO", intento_activo=False).content)
    intentos = leer_csv(exportar(entorno, tipo="intentos", buscar=nombre).content)
    consulta = estudiantes(entorno, condicion="PARTICIPO", intento_activo=False)

    assert [f[0] for f in participantes[1:]] == [e["estudiante_id"] for e in consulta["items"]] == [str(entorno.estudiantes[0].id)]
    assert [f[1] for f in intentos[1:]] == [nombre]


def test_exportacion_neutraliza_formulas(entorno):
    estudiante = entorno.estudiantes[0]
    with engine.begin() as conn:
        conn.execute(text("UPDATE usuario SET nombre_completo = '=HYPERLINK(\"http://x\")' WHERE id = :id"), {"id": estudiante.id})
    intento(entorno, 0, {0: 0})

    for tipo in ("estudiantes", "intentos"):
        filas = leer_csv(exportar(entorno, tipo=tipo).content)
        assert "'=HYPERLINK(\"http://x\")" in [f[1] for f in filas]
    assert estudiantes(entorno, buscar="HYPERLINK")["items"][0]["nombre_completo"] == '=HYPERLINK("http://x")'  # la API JSON no se altera


def test_exportacion_neutraliza_formulas_tras_caracteres_invisibles(entorno):
    """Nombres guardados en PostgreSQL con espacios, controles o caracteres de formato antes del indicador."""
    nombres = ["  =1+1", "​@SUM(A1)", "\x0b+cmd", "﻿-2+3"]
    with engine.begin() as conn:
        for estudiante, nombre in zip(entorno.estudiantes, nombres, strict=False):
            conn.execute(text("UPDATE usuario SET nombre_completo = :n WHERE id = :id"), {"n": nombre, "id": estudiante.id})
        caso_id = entorno.caso["id"]
        conn.execute(
            text("UPDATE escenario SET titulo = :t WHERE caso_id = :c AND orden = 1"), {"t": " =IMPORTXML(\"x\")", "c": caso_id}
        )
    for i in range(3):
        intento(entorno, i, {0: 0})

    exportados = {f[1] for tipo in ("estudiantes", "intentos") for f in leer_csv(exportar(entorno, tipo=tipo).content)[1:]}
    escenarios = {f[1] for f in leer_csv(exportar(entorno, tipo="preguntas").content)[1:]}

    assert exportados == {"'" + n for n in nombres[:3]}
    assert "' =IMPORTXML(\"x\")" in escenarios


def test_descargas_sin_permisos(entorno, admin_headers, otro_creador_headers):
    assert exportar(entorno, headers=otro_creador_headers).status_code == 404
    assert exportar(entorno, headers=admin_headers).status_code == 403
    assert entorno.client.get(url_sesion(entorno, "export")).status_code == 401


def test_exportacion_que_supera_el_limite_responde_422(entorno):
    intento(entorno, 0, {0: 0})
    app.dependency_overrides[get_exportacion_service] = lambda: ExportacionService(SessionLocal(), entorno.reloj, limite=1)
    try:
        r = exportar(entorno, tipo="estudiantes")
        assert r.status_code == 422 and r.json()["codigo"] == "EXPORTACION_EXCEDE_LIMITE" and r.json()["limite"] == 1
        assert exportar(entorno, tipo="estudiantes", condicion="PARTICIPO").status_code == 200  # filtrado cabe
    finally:
        app.dependency_overrides.pop(get_exportacion_service, None)


# --- Concurrencia y coherencia ----------------------------------------------------------------------------------------


def _servicio(entorno):
    return ReportesSesionService(SessionLocal(), entorno.reloj)


def test_consulta_mientras_finaliza_una_participacion_ve_una_instantanea(entorno):
    headers = entorno.headers(0)
    pid = entorno.iniciar(headers)["id"]
    servicio = _servicio(entorno)
    docente_id = entorno.sesion["docente_id"]

    with servicio._lectura():
        antes = servicio._resumen(entorno.sesion_id, docente_id)
        assert entorno.client.post(f"{PART_URL}/{pid}/finish", headers=headers).status_code == 200  # otra transacción
        durante = servicio._resumen(entorno.sesion_id, docente_id)
    despues = servicio.resumen(entorno.sesion_id, docente_id)

    assert durante == antes and (antes.intentos.en_progreso, antes.intentos.finalizados) == (1, 0)
    assert (despues.intentos.en_progreso, despues.intentos.finalizados) == (0, 1)


def test_consulta_durante_el_registro_de_calificaciones(entorno):
    intento(entorno, 0, {0: 0})
    servicio = _servicio(entorno)

    with servicio._lectura():
        notas_antes = servicio._repo.agregado_notas([entorno.sesion_id], D("5.00"))
        procesar(entorno)  # registra la nota en otra transacción
        notas_durante = servicio._repo.agregado_notas([entorno.sesion_id], D("5.00"))
        conteos = servicio._repo.conteos_intentos([entorno.sesion_id], entorno.reloj.ahora())
    assert notas_antes == notas_durante and notas_durante[None].evaluados == 0
    assert conteos[next(iter(conteos))].calificados == 0
    assert servicio.notas(entorno.sesion_id, entorno.sesion["docente_id"]).estadisticas.promedio == D("2.20")


def test_revocacion_durante_el_calculo_no_produce_totales_contradictorios(entorno):
    servicio = _servicio(entorno)
    with servicio._lectura():
        antes = servicio._repo.conteos_convocatorias([entorno.sesion_id])
        revocar(entorno, 2)
        durante = servicio._repo.conteos_convocatorias([entorno.sesion_id])
    assert antes == durante
    assert servicio.resumen(entorno.sesion_id, entorno.sesion["docente_id"]).convocatorias.revocadas == 1


def test_la_transaccion_de_reportes_es_de_solo_lectura(entorno):
    servicio = _servicio(entorno)
    with pytest.raises(DBAPIError) as exc, servicio._lectura():
        servicio._session.execute(text("UPDATE participacion SET nota_final = 0"))
    assert "read-only" in str(exc.value.orig).lower()


def test_integridad_de_agregados_con_escrituras_concurrentes(entorno):
    for i in range(3):
        intento(entorno, i, {0: 0})
    docente_id = entorno.sesion["docente_id"]

    def consultar():
        observados = []
        for _ in range(15):
            r = _servicio(entorno).resumen(entorno.sesion_id, docente_id)
            it = r.intentos
            assert it.calificados + it.pendientes_de_calificacion + it.sin_calificar == it.finalizados + it.expirados
            observados.append(it.calificados)
        return observados

    def calificar():
        procesar(entorno)
        return "ok"

    observados, resultado = en_paralelo(consultar, calificar)
    assert resultado == "ok", resultado
    assert not isinstance(observados, Exception), observados
    assert set(observados) <= {0, 3}  # todo o nada: nunca una calificación parcial
    assert _servicio(entorno).resumen(entorno.sesion_id, docente_id).intentos.calificados == 3


def test_filtros_de_estudiantes_combinados(entorno):
    intento(entorno, 0, {0: 0})  # FINALIZADA
    intento(entorno, 1, {}, finalizar=False)  # EN_PROGRESO
    revocar(entorno, 2)
    procesar(entorno)
    ids = [str(e.id) for e in entorno.estudiantes]

    def solo(**filtros):
        return sorted(e["estudiante_id"] for e in estudiantes(entorno, **filtros)["items"])

    assert solo(convocatoria="activas") == sorted(ids[:2])
    assert solo(condicion="REVOCADA") == [ids[2]]
    assert solo(estado_participacion="FINALIZADA") == [ids[0]]
    assert solo(estado_participacion="EN_PROGRESO") == [ids[1]]
    assert solo(con_nota=True) == [ids[0]]
    assert solo(con_nota=False) == sorted(ids[1:])
    assert solo(buscar="100%_inexistente") == []  # los comodines del usuario son literales


def test_exportacion_de_espacio_sobre_el_limite(entorno):
    app.dependency_overrides[get_exportacion_service] = lambda: ExportacionService(SessionLocal(), entorno.reloj, limite=0)
    try:
        r = entorno.client.get(f"{SPACES_URL}/{entorno.sesion['espacio_academico_id']}/reports/export", headers=entorno.docente_headers)
        assert r.status_code == 422 and r.json()["codigo"] == "EXPORTACION_EXCEDE_LIMITE"
    finally:
        app.dependency_overrides.pop(get_exportacion_service, None)


# --- Revisión final: autoría del caso frente a responsabilidad de la sesión -------------------------------------

NOMBRE_PRIVADO, CORREO_PRIVADO = "Estudiante Privado de B", "privado.b@universidad.edu.co"


def _sesion_de_b_con_el_caso_de_a(entorno, make_user):
    """El docente B es responsable de una sesión que usa el caso del docente A (autor).

    La API del módulo 3 solo deja programar casos propios, pero PostgreSQL lo admite (el disparador
    no exige autoría), así que se inserta directamente: es el peor caso para la autorización.
    """
    docente_b = make_user(RolUsuario.DOCENTE)
    estudiante = make_user(RolUsuario.ESTUDIANTE, clave=None)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE usuario SET nombre_completo = :n, correo = :c WHERE id = :id"),
            {"n": NOMBRE_PRIVADO, "c": CORREO_PRIVADO, "id": estudiante.id},
        )
        sesion_id = conn.execute(
            text(
                "INSERT INTO sesion (caso_id, espacio_academico_id, docente_id, inicio, fin, tiempo_max_min, estado) "
                "VALUES (:caso, :espacio, :docente, TIMESTAMPTZ '2026-11-03 08:00+00', TIMESTAMPTZ '2026-11-03 10:00+00', 40, "
                "'EN_CURSO') RETURNING id"
            ),
            {"caso": entorno.caso["id"], "espacio": entorno.sesion["espacio_academico_id"], "docente": docente_b.id},
        ).scalar_one()
        conv = conn.execute(
            text("INSERT INTO convocatoria (sesion_id, estudiante_id, codigo_autorizacion) VALUES (:s, :e, 'v1.privada') RETURNING id"),
            {"s": sesion_id, "e": estudiante.id},
        ).scalar_one()
        pid = conn.execute(
            text(
                "INSERT INTO participacion (convocatoria_id, numero_intento, inicio, estado) "
                "VALUES (:c, 1, TIMESTAMPTZ '2026-11-03 08:00+00', 'EN_PROGRESO') RETURNING id"
            ),
            {"c": conv},
        ).scalar_one()
        pregunta = entorno.preguntas[0]
        conn.execute(
            text(
                "INSERT INTO respuesta (participacion_id, pregunta_id, opcion_id, respondida_en, actualizada_en) "
                "VALUES (:p, :q, :o, now(), now())"
            ),
            {"p": pid, "q": pregunta["id"], "o": pregunta["opciones"][0]["id"]},
        )
        conn.execute(
            text("UPDATE participacion SET estado = 'FINALIZADA', motivo_cierre = 'VOLUNTARIO', fin = inicio + interval '5 minutes' WHERE id = :p"),
            {"p": pid},
        )
        conn.execute(text("UPDATE participacion SET nota_final = 4.75 WHERE id = :p"), {"p": pid})
    return bearer(login(entorno.client, docente_b.correo)), str(sesion_id), estudiante


def test_el_autor_del_caso_no_accede_a_la_sesion_de_otro_docente(entorno, make_user):
    intento(entorno, 0, {0: 0})  # sesión propia del docente A (autor): 2.20
    procesar(entorno)
    headers_b, sesion_b, estudiante_b = _sesion_de_b_con_el_caso_de_a(entorno, make_user)
    headers_a = entorno.docente_headers
    espacio_url = f"{SPACES_URL}/{entorno.sesion['espacio_academico_id']}/reports"
    base = f"{API}/sessions/{sesion_b}/reports"
    rutas_de_b = [f"{base}/{e}" for e in ("summary", "students", "grades", "criteria", "questions")]
    rutas_de_b += [f"{base}/students/{estudiante_b.id}"]
    rutas_de_b += [f"{base}/export?tipo={t}" for t in ("resumen", "estudiantes", "intentos", "criterios", "preguntas")]

    for ruta in rutas_de_b:
        a = entorno.client.get(ruta, headers=headers_a)
        assert a.status_code == 404, ruta  # misma respuesta que una sesión inexistente (módulos 3 y 5)
        assert a.json() == {"detail": "Sesión no encontrada."}
        assert entorno.client.get(ruta, headers=headers_b).status_code == 200, ruta  # B sí consulta sus reportes

    # Reportes agregados del docente A: solo su sesión, aunque el caso sea suyo y el espacio compartido.
    caso = obtener(entorno, f"{API}/cases/{entorno.caso['id']}/reports")
    espacio = obtener(entorno, espacio_url)
    mias = obtener(entorno, f"{API}/reports/my-sessions")
    for reporte in (caso, espacio):
        assert reporte["sesiones_registradas"] == 1 and reporte["totales"]["intentos"] == 1
        assert [s["id"] for s in reporte["sesiones"]["items"]] == [entorno.sesion_id]
    assert (caso["estadisticas"]["evaluados"], caso["estadisticas"]["promedio"]) == (1, "2.20")  # sin la nota 4.75 de B
    assert caso["criterios"]["intentos_considerados"] == 1
    assert (espacio["promedio_porcentaje_escala"], espacio["casos_utilizados"][0]["sesiones"]) == ("44.00", 1)
    assert [s["id"] for s in mias["items"]] == [entorno.sesion_id]
    exportado = entorno.client.get(f"{espacio_url}/export", headers=headers_a)
    for respuesta in (caso, espacio, mias, exportado.text):
        texto = str(respuesta)
        assert sesion_b not in texto and NOMBRE_PRIVADO not in texto and CORREO_PRIVADO not in texto and "4.75" not in texto

    # Docente B: ve su sesión, pero el historial del caso es del autor (regla del módulo 2, sin cambios).
    assert entorno.client.get(f"{API}/cases/{entorno.caso['id']}/reports", headers=headers_b).status_code == 404
    espacio_b = obtener(entorno, espacio_url, headers=headers_b)
    assert [s["id"] for s in espacio_b["sesiones"]["items"]] == [sesion_b] and espacio_b["promedio_porcentaje_escala"] == "95.00"
    assert [s["id"] for s in obtener(entorno, f"{API}/reports/my-sessions", headers=headers_b)["items"]] == [sesion_b]
    assert entorno.estudiantes[0].correo not in str(espacio_b)
    detalle_b = obtener(entorno, f"{base}/students/{estudiante_b.id}", headers=headers_b)
    assert (detalle_b["correo"], detalle_b["intentos"][0]["nota_final"]) == (CORREO_PRIVADO, "4.75")


def test_el_historial_individual_solo_contiene_al_estudiante_consultado(entorno):
    propios = {intento(entorno, 0, {0: 0})}
    autorizar_intentos(entorno, 0, 2)
    propios.add(intento(entorno, 0, {}))
    ajenos = {intento(entorno, 1, {0: 0, 1: 0, 2: 0}), intento(entorno, 2, {})}
    procesar(entorno)

    detalle = obtener(entorno, url_sesion(entorno, f"students/{entorno.estudiantes[0].id}"))
    filas = leer_csv(exportar(entorno, tipo="intentos", buscar=entorno.estudiantes[0].correo).content)

    recibidos = {i["participacion_id"] for i in detalle["intentos"]}
    assert recibidos == propios and not ajenos & recibidos
    assert (detalle["estudiante_id"], detalle["correo"]) == (str(entorno.estudiantes[0].id), entorno.estudiantes[0].correo)
    texto = str(detalle)
    assert all(e.correo not in texto and e.nombre_completo not in texto for e in entorno.estudiantes[1:])
    assert {f[2] for f in filas[1:]} == {entorno.estudiantes[0].correo} and len(filas) == 3


def test_escalas_distintas_se_normalizan_en_el_espacio(entorno, make_user):
    intento(entorno, 0, {0: 0, 1: 0, 2: 0})  # caso de escala 5: 5.00 (100 %)
    procesar(entorno)
    documento = dsl_valido()
    documento["caso"]["nombre"] = "Caso con escala 10"
    documento["rubrica"]["escalaMax"] = 10.00  # mismos niveles (1, 3, 5): el máximo alcanzable es 5.00 sobre 10
    headers = entorno.docente_headers
    caso_10 = crear_caso_completo(entorno.client, headers, documento)
    assert publicar(entorno.client, headers, caso_10["id"]).status_code == 200
    estudiante = make_user(RolUsuario.ESTUDIANTE, clave=None)
    sesion = programar(entorno.client, headers, entorno.reloj, caso_10["id"], entorno.sesion["espacio_academico_id"], [estudiante])
    entorno.reloj.avanzar(hours=1)
    assert iniciar(entorno.client, headers, sesion["id"]).status_code == 200
    conv = convocatorias(entorno.client, headers, sesion["id"])[0]
    codigo = codigo_de(entorno.client, headers, sesion["id"], conv["id"])
    login_estudiante = entorno.client.post(f"{API}/auth/student/login", json={"correo": estudiante.correo, "codigo": codigo})
    token = bearer(login_estudiante.json()["access_token"])
    pid = entorno.client.post(f"{API}/student/sessions/{sesion['id']}/participations", headers=token).json()["id"]
    for p in (p for e in caso_10["escenarios"] for p in e["preguntas"]):
        assert guardar(entorno.client, token, pid, p["id"], p["opciones"][0]["id"]).status_code == 200
    assert entorno.client.post(f"{PART_URL}/{pid}/finish", headers=token).status_code == 200
    assert entorno.client.post(f"{API}/sessions/{sesion['id']}/evaluations/process", headers=headers).status_code == 200

    r = obtener(entorno, f"{SPACES_URL}/{entorno.sesion['espacio_academico_id']}/reports")

    casos = {c["nombre"]: (c["escala_max"], c["promedio"]) for c in r["casos_utilizados"]}
    assert casos == {"Conformidad en el aula": ("5.00", "5.00"), "Caso con escala 10": ("10.00", "5.00")}
    # Normalizado: (100 % + 50 %) / 2 = 75 %. Sin normalizar, ambas notas 5.00 parecerían el mismo desempeño.
    assert r["promedio_porcentaje_escala"] == "75.00"
    notas = obtener(entorno, f"{API}/sessions/{sesion['id']}/reports/grades")["estadisticas"]
    assert (notas["escala_max"], notas["promedio_porcentaje_escala"], notas["distribucion"][-1]["hasta"]) == ("10.00", "50.00", "10.00")


FILTROS_EQUIVALENTES = [
    {},
    {"convocatoria": "activas"},
    {"convocatoria": "revocadas"},
    {"condicion": "PARTICIPO"},
    {"condicion": "PENDIENTE"},
    {"condicion": "REVOCADA"},
    {"estado_participacion": "FINALIZADA"},
    {"estado_participacion": "EN_PROGRESO"},
    {"con_nota": "true"},
    {"con_nota": "false"},
    {"intento_activo": "true"},
    {"buscar": "estudiante"},
    {"convocatoria": "activas", "con_nota": "false", "intento_activo": "false"},
]


def test_csv_y_json_aplican_los_mismos_filtros_y_permisos(entorno, otro_creador_headers):
    intento(entorno, 0, {0: 0})
    intento(entorno, 1, {}, finalizar=False)
    revocar(entorno, 2)
    procesar(entorno)

    for filtros in FILTROS_EQUIVALENTES:
        consulta = estudiantes(entorno, limit=100, **filtros)
        csv_estudiantes = leer_csv(exportar(entorno, tipo="estudiantes", **filtros).content)[1:]
        csv_intentos = leer_csv(exportar(entorno, tipo="intentos", **filtros).content)[1:]
        ids = [e["estudiante_id"] for e in consulta["items"]]
        assert [f[0] for f in csv_estudiantes] == ids, filtros
        assert sorted(f[0] for f in csv_intentos) == sorted(e["estudiante_id"] for e in consulta["items"] for _ in e["intentos"]), filtros
        assert entorno.client.get(url_sesion(entorno, "students"), headers=otro_creador_headers, params=filtros).status_code == 404
        assert exportar(entorno, headers=otro_creador_headers, tipo="estudiantes", **filtros).status_code == 404
