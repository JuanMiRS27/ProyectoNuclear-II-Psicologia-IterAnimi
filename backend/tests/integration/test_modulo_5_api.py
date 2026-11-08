"""Módulo 5 por HTTP y servicios contra PostgreSQL real: evaluación, retroalimentación y resultados.

Caso de `dsl_valido()`: tres preguntas (E1P1 y E2P1 del criterio ANALISIS, peso 60; E1P2 del
criterio DECISION, peso 40), opción 0 correcta, escala 5 y niveles 0 % -> 1.00, 50 % -> 3.00,
85 % -> 5.00.
"""

import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal, engine
from app.modules.evaluations import eventos
from app.modules.evaluations.services.evaluacion_service import EvaluacionService
from tests.conftest import bearer
from tests.participations_helpers import PART_URL, contar, en_paralelo, entorno, fila, guardar, iniciar_participacion  # noqa: F401
from tests.sessions_helpers import ingresar

RESULTS_LOGIN_URL = "/api/v1/auth/student/results-login"
D = Decimal


class PublicadorDePrueba:
    """Registra los eventos y comprueba que la nota ya es visible desde OTRA conexión (post-commit)."""

    def __init__(self) -> None:
        self.eventos: list[eventos.EventoEvaluacion] = []
        self.visibles: list[bool] = []

    def publicar(self, evento: eventos.EventoEvaluacion) -> None:
        self.eventos.append(evento)
        if "participacion_id" in evento.datos and evento.tipo != eventos.RETROALIMENTACION_REGISTRADA:
            with engine.connect() as conn:
                nota = conn.execute(
                    text("SELECT nota_final FROM participacion WHERE id = :id"), {"id": evento.datos["participacion_id"]}
                ).scalar_one()
            self.visibles.append(nota is not None)

    def tipos(self) -> list[str]:
        return [e.tipo for e in self.eventos]


@pytest.fixture
def publicador():
    anterior = eventos.publicador()
    nuevo = PublicadorDePrueba()
    eventos.configurar(nuevo)
    yield nuevo
    eventos.configurar(anterior)


# --- Utilidades -------------------------------------------------------------------------------------


def responder(entorno, headers, participacion_id, elecciones: dict[int, int]):
    """elecciones: índice de pregunta -> índice de opción (0 es la correcta)."""
    for i, opcion in elecciones.items():
        pregunta = entorno.preguntas[i]
        r = guardar(entorno.client, headers, participacion_id, pregunta["id"], pregunta["opciones"][opcion]["id"])
        assert r.status_code == 200, r.text


def intento(entorno, indice=0, elecciones=None, finalizar=True) -> str:
    headers = entorno.headers(indice)
    participacion = entorno.iniciar(headers)
    responder(entorno, headers, participacion["id"], elecciones or {})
    if finalizar:
        assert entorno.client.post(f"{PART_URL}/{participacion['id']}/finish", headers=headers).status_code == 200
    return participacion["id"]


def finalizar_sesion(entorno):
    r = entorno.client.post(f"/api/v1/sessions/{entorno.sesion_id}/finish", headers=entorno.docente_headers)
    assert r.status_code == 200, r.text


def procesar(entorno, headers=None):
    return entorno.client.post(f"/api/v1/sessions/{entorno.sesion_id}/evaluations/process", headers=headers or entorno.docente_headers)


def nota_bd(participacion_id):
    return fila("SELECT nota_final FROM participacion WHERE id = :id", id=participacion_id).nota_final


def login_resultados(entorno, indice=0, codigo=None):
    estudiante = entorno.estudiantes[indice]
    return entorno.client.post(RESULTS_LOGIN_URL, json={"correo": estudiante.correo, "codigo": codigo or entorno.codigos[estudiante.correo]})


def headers_resultados(entorno, indice=0):
    r = login_resultados(entorno, indice)
    assert r.status_code == 200, r.text
    return bearer(r.json()["access_token"])


def historial(participacion_id):
    with engine.connect() as conn:
        p = conn.execute(
            text("SELECT numero_intento, inicio, fin, estado::text, motivo_cierre::text FROM participacion WHERE id = :id"),
            {"id": participacion_id},
        ).one()
        r = conn.execute(
            text("SELECT pregunta_id, opcion_id, respondida_en, actualizada_en FROM respuesta WHERE participacion_id = :id ORDER BY pregunta_id"),
            {"id": participacion_id},
        ).all()
    return tuple(p), [tuple(x) for x in r]


# --- Evaluación de participaciones ----------------------------------------------------------------------


def test_evalua_participacion_finalizada_y_persiste_la_nota(entorno, publicador):
    pid = intento(entorno, elecciones={0: 0})  # E1P1 correcta; E1P2 y E2P1 sin responder

    r = procesar(entorno)

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert (cuerpo["procesadas"], cuerpo["registradas"], cuerpo["sin_cambios"]) == (1, 1, 0)
    # ANALISIS 1/2 = 50 % -> Aceptable 3.00; DECISION 0/1 -> Insuficiente 1.00; 3×0.6 + 1×0.4 = 2.20
    assert cuerpo["resultados"][0] == {"participacion_id": pid, "condicion": "COMPLETA", "calificacion": "CALIFICADA", "nota_final": "2.20"}
    assert nota_bd(pid) == D("2.20")

    detalle = entorno.client.get(f"/api/v1/participations/{pid}/evaluation", headers=entorno.docente_headers).json()
    assert (detalle["nota_final"], detalle["nota_calculada"], detalle["evaluacion_registrada"]) == ("2.20", "2.20", True)
    assert detalle["estrategia"] == "EstrategiaEvaluacionCompleta"
    assert detalle["totales"] == {"total_preguntas": 3, "aciertos": 1, "errores": 0, "sin_responder": 2}
    niveles = {c["descripcion"]: (c["nivel"], c["porcentaje_aciertos"], c["politica"]) for c in detalle["criterios"]}
    assert niveles == {
        "Análisis del fenómeno social": ("Aceptable", "50.00", "NIVELES"),
        "Toma de decisiones éticas": ("Insuficiente", "0.00", "NIVELES"),
    }
    resultados = [p["resultado"] for p in detalle["preguntas"]]
    assert resultados.count("ACIERTO") == 1 and resultados.count("SIN_RESPUESTA") == 2
    assert all(p["opciones_correctas"][0]["justificacion"] == "Considera la presión grupal." for p in detalle["preguntas"])
    assert "Nota: 2.20 sobre 5.00." in detalle["retroalimentacion_automatica"]
    assert publicador.tipos() == [eventos.CALIFICACION_REGISTRADA]


def test_evalua_expirada_por_tiempo_con_las_respuestas_guardadas(entorno):
    headers = entorno.headers()
    pid = entorno.iniciar(headers)["id"]
    responder(entorno, headers, pid, {0: 0, 1: 0})
    entorno.reloj.avanzar(minutes=41)
    assert entorno.client.get(PART_URL, headers=headers).json()[0]["motivo_cierre"] == "TIEMPO_AGOTADO"

    assert procesar(entorno).status_code == 200

    # ANALISIS 50 % -> 3.00; DECISION 100 % -> 5.00; 1.8 + 2.0 = 3.80 (sin penalización por tiempo)
    assert nota_bd(pid) == D("3.80")
    detalle = entorno.client.get(f"/api/v1/participations/{pid}/evaluation", headers=entorno.docente_headers).json()
    assert (detalle["condicion"], detalle["motivo_cierre"]) == ("INCOMPLETA", "TIEMPO_AGOTADO")
    assert "Intento incompleto." in detalle["observaciones"]
    assert any("tiempo máximo" in o for o in detalle["observaciones"])


def test_causas_administrativas_y_ausencia(entorno):
    revocado = intento(entorno, 0, {0: 0}, finalizar=False)
    assert entorno.client.delete(entorno.conv_url(0), headers=entorno.docente_headers).status_code == 204
    sin_respuestas = intento(entorno, 1, finalizar=False)
    finalizar_sesion(entorno)  # el estudiante 2 nunca inició: ausencia

    cuerpo = procesar(entorno).json()

    assert (cuerpo["procesadas"], cuerpo["registradas"], cuerpo["sin_calificar"], cuerpo["ausencias"]) == (2, 1, 1, 1)
    assert nota_bd(revocado) == D("2.20")  # rendimiento demostrado, sin penalización
    assert nota_bd(sin_respuestas) is None  # cierre administrativo sin evidencia: sin calificar, no un cero
    sesion = entorno.client.get(f"/api/v1/sessions/{entorno.sesion_id}/evaluations", headers=entorno.docente_headers).json()
    motivos = {p["participacion_id"]: (p["motivo_cierre"], p["calificacion"], p["nota_final"]) for p in sesion["participaciones"]}
    assert motivos == {
        revocado: ("CONVOCATORIA_REVOCADA", "CALIFICADA", "2.20"),
        sin_respuestas: ("SESION_FINALIZADA", "SIN_CALIFICAR", None),
    }
    assert sesion["resumen"] == {"finalizadas": 0, "expiradas": 2, "en_progreso": 0, "ausencias": 1, "evaluadas": 2, "pendientes": 0}
    ausente = sesion["ausencias"][0]
    assert (ausente["estudiante_correo"], ausente["condicion"], ausente["calificacion"], ausente["nota_final"]) == (
        entorno.estudiantes[2].correo, "AUSENCIA", "SIN_CALIFICAR", None,
    )


def test_ausencia_no_crea_participaciones_y_excluye_convocatorias_revocadas(entorno):
    intento(entorno, 0, {0: 0})
    assert entorno.client.delete(entorno.conv_url(1), headers=entorno.docente_headers).status_code == 204

    ausencias = entorno.client.get(f"/api/v1/sessions/{entorno.sesion_id}/absences", headers=entorno.docente_headers)
    procesar(entorno)

    assert ausencias.status_code == 200
    assert [a["estudiante_correo"] for a in ausencias.json()] == [entorno.estudiantes[2].correo]
    assert contar("SELECT count(*) FROM participacion") == 1
    assert contar("SELECT count(*) FROM respuesta") == 1


def test_varios_intentos_se_listan_sin_elegir_una_nota_definitiva(entorno):
    entorno.client.patch(entorno.conv_url(0, "/attempts"), headers=entorno.docente_headers, json={"intentos_autorizados": 2, "motivo": "Falla eléctrica"})
    primero = intento(entorno, 0, {0: 0})
    segundo = intento(entorno, 0, {0: 0, 1: 0, 2: 0})

    procesar(entorno)
    filas = entorno.client.get(f"/api/v1/sessions/{entorno.sesion_id}/evaluations", headers=entorno.docente_headers).json()["participaciones"]

    assert [(f["participacion_id"], f["numero_intento"], f["nota_final"]) for f in filas] == [(primero, 1, "2.20"), (segundo, 2, "5.00")]
    assert len({f["estudiante_id"] for f in filas}) == 1


def test_en_progreso_se_omite_y_no_se_puede_evaluar(entorno):
    pid = intento(entorno, finalizar=False)

    cuerpo = procesar(entorno).json()
    recalculo = entorno.client.post(f"/api/v1/participations/{pid}/evaluation/recalculate", headers=entorno.docente_headers)
    detalle = entorno.client.get(f"/api/v1/participations/{pid}/evaluation", headers=entorno.docente_headers)

    assert (cuerpo["procesadas"], cuerpo["en_progreso_omitidas"]) == (0, 1)
    assert (recalculo.status_code, detalle.status_code) == (409, 409)
    assert nota_bd(pid) is None


# --- Historial, idempotencia y recalificación -------------------------------------------------------------


def test_la_evaluacion_no_modifica_el_historial(entorno):
    pid = intento(entorno, 0, {0: 0, 1: 1})
    antes = historial(pid)

    procesar(entorno)
    entorno.client.post(f"/api/v1/participations/{pid}/evaluation/recalculate", headers=entorno.docente_headers)
    entorno.client.patch(f"/api/v1/participations/{pid}/feedback", headers=entorno.docente_headers, json={"retroalimentacion_general": "Bien."})

    assert historial(pid) == antes


def test_recalculo_idempotente_sin_eventos_duplicados(entorno, publicador):
    pid = intento(entorno, 0, {0: 0})
    procesar(entorno)

    segundo = procesar(entorno).json()
    recalculo = entorno.client.post(f"/api/v1/participations/{pid}/evaluation/recalculate", headers=entorno.docente_headers)

    assert (segundo["registradas"], segundo["actualizadas"], segundo["sin_cambios"]) == (0, 0, 1)
    assert recalculo.status_code == 200 and recalculo.json()["nota_final"] == "2.20"
    assert publicador.tipos() == [eventos.CALIFICACION_REGISTRADA]


def test_recalculo_corrige_una_nota_incoherente(entorno, publicador):
    pid = intento(entorno, 0, {0: 0})
    procesar(entorno)
    with engine.begin() as conn:  # dato alterado fuera de la aplicación
        conn.execute(text("UPDATE participacion SET nota_final = 4.00 WHERE id = :id"), {"id": pid})

    fila_lista = entorno.client.get(f"/api/v1/sessions/{entorno.sesion_id}/evaluations", headers=entorno.docente_headers).json()["participaciones"][0]
    recalculo = entorno.client.post(f"/api/v1/participations/{pid}/evaluation/recalculate", headers=entorno.docente_headers)

    assert (fila_lista["nota_final"], fila_lista["requiere_procesamiento"], fila_lista["evaluacion_registrada"]) == ("4.00", True, False)
    assert recalculo.json()["nota_final"] == "2.20" and nota_bd(pid) == D("2.20")
    assert publicador.tipos() == [eventos.CALIFICACION_REGISTRADA, eventos.CALIFICACION_ACTUALIZADA]


def test_eventos_se_publican_despues_del_commit(entorno, publicador):
    intento(entorno, 0, {0: 0})
    intento(entorno, 1, {1: 0})
    finalizar_sesion(entorno)

    procesar(entorno)

    assert publicador.tipos() == [eventos.CALIFICACION_REGISTRADA] * 2 + [eventos.RESULTADOS_DISPONIBLES]
    assert publicador.visibles == [True, True]


def test_rubrica_no_evaluable_no_registra_ninguna_nota(entorno, publicador):
    primero = intento(entorno, 0, {0: 0})
    segundo = intento(entorno, 1, {1: 0})
    # Caso antiguo: un nivel con valor superior a la escala (el módulo 2 lo aplazó y lo permite publicar).
    niveles = [{"nombre": "Bajo", "valor": 1, "min_aciertos_pct": 0}, {"nombre": "Alto", "valor": 9, "min_aciertos_pct": 50}]
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE criterio_rubrica SET niveles = CAST(:n AS jsonb) WHERE descripcion = 'Toma de decisiones éticas'"),
            {"n": json.dumps(niveles)},
        )

    r = procesar(entorno)

    assert r.status_code == 422
    assert r.json()["codigo"] == "NIVELES_VALOR_FUERA_DE_ESCALA"
    assert (nota_bd(primero), nota_bd(segundo)) == (None, None)
    assert publicador.eventos == []
    lista = entorno.client.get(f"/api/v1/sessions/{entorno.sesion_id}/evaluations", headers=entorno.docente_headers).json()
    assert lista["resumen"]["pendientes"] == 2 and lista["participaciones"][0]["calificacion"] is None


def test_criterio_sin_preguntas_se_excluye_y_renormaliza(entorno):
    """Regresión del módulo 2: se puede publicar un criterio sin preguntas; no penaliza al estudiante."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE pregunta SET criterio_id = (SELECT id FROM criterio_rubrica WHERE descripcion = 'Análisis del fenómeno social') "
                "WHERE criterio_id = (SELECT id FROM criterio_rubrica WHERE descripcion = 'Toma de decisiones éticas')"
            )
        )
    pid = intento(entorno, 0, {0: 0, 1: 0, 2: 0})

    procesar(entorno)
    detalle = entorno.client.get(f"/api/v1/participations/{pid}/evaluation", headers=entorno.docente_headers).json()

    assert detalle["nota_final"] == "5.00"
    decision = next(c for c in detalle["criterios"] if c["descripcion"] == "Toma de decisiones éticas")
    assert (decision["politica"], decision["peso_efectivo"], decision["total_preguntas"]) == ("SIN_EVIDENCIA", "0.00", 0)


def test_procesos_concurrentes_no_duplican_registros_ni_eventos(entorno, creador, publicador):
    intento(entorno, 0, {0: 0})
    intento(entorno, 1, {0: 0, 1: 0})

    def tarea():
        with SessionLocal() as session:
            return EvaluacionService(session, eventos_publicador=publicador).procesar_sesion(uuid.UUID(entorno.sesion_id), creador)

    a, b = en_paralelo(tarea, tarea)

    assert not isinstance(a, Exception) and not isinstance(b, Exception), (a, b)
    assert a.registradas + b.registradas == 2
    assert a.sin_cambios + b.sin_cambios == 2
    assert publicador.tipos().count(eventos.CALIFICACION_REGISTRADA) == 2


def test_triggers_del_modulo_4_siguen_protegiendo_los_intentos_cerrados(entorno):
    pid = intento(entorno, 0, {0: 0})
    procesar(entorno)

    with pytest.raises(IntegrityError) as exc, engine.begin() as conn:
        conn.execute(text("UPDATE respuesta SET opcion_id = opcion_id WHERE participacion_id = :id"), {"id": pid})
    assert exc.value.orig.diag.constraint_name == "ck_respuesta_participacion_en_progreso"
    with pytest.raises(IntegrityError) as exc, engine.begin() as conn:
        conn.execute(text("UPDATE participacion SET motivo_cierre = 'TIEMPO_AGOTADO', estado = 'EXPIRADA' WHERE id = :id"), {"id": pid})
    assert exc.value.orig.diag.constraint_name == "ck_participacion_cerrada_inmutable"
    assert nota_bd(pid) == D("2.20")


# --- Retroalimentación del docente -------------------------------------------------------------------


def test_retroalimentacion_general_del_docente(entorno, publicador):
    pid = intento(entorno, 0, {0: 0})
    procesar(entorno)
    url = f"/api/v1/participations/{pid}/feedback"

    creada = entorno.client.patch(url, headers=entorno.docente_headers, json={"retroalimentacion_general": "  Revisa la presión grupal.  "})
    repetida = entorno.client.patch(url, headers=entorno.docente_headers, json={"retroalimentacion_general": "Revisa la presión grupal."})
    entorno.client.post(f"/api/v1/participations/{pid}/evaluation/recalculate", headers=entorno.docente_headers)
    procesar(entorno)

    assert creada.status_code == 200 and creada.json()["retroalimentacion_general"] == "Revisa la presión grupal."
    assert repetida.status_code == 200
    detalle = entorno.client.get(f"/api/v1/participations/{pid}/evaluation", headers=entorno.docente_headers).json()
    assert detalle["retroalimentacion_general"] == "Revisa la presión grupal."  # la recalificación no la sobrescribe
    assert publicador.tipos() == [eventos.CALIFICACION_REGISTRADA, eventos.RETROALIMENTACION_REGISTRADA]
    justificaciones = fila("SELECT count(*) AS n FROM opcion WHERE justificacion = 'Considera la presión grupal.'").n
    assert justificaciones == 3  # las justificaciones originales no cambian

    borrada = entorno.client.patch(url, headers=entorno.docente_headers, json={"retroalimentacion_general": ""})
    assert borrada.json()["retroalimentacion_general"] is None


@pytest.mark.parametrize("cuerpo", [{"retroalimentacion_general": "x", "nota_final": "5.00"}, {"nota_final": "5.00"}, {}])
def test_no_se_acepta_nota_del_cliente(entorno, cuerpo):
    pid = intento(entorno, 0, {0: 0})
    r = entorno.client.patch(f"/api/v1/participations/{pid}/feedback", headers=entorno.docente_headers, json=cuerpo)
    assert r.status_code == 422
    assert nota_bd(pid) is None


def test_retroalimentacion_en_progreso_rechazada(entorno):
    pid = intento(entorno, finalizar=False)
    r = entorno.client.patch(f"/api/v1/participations/{pid}/feedback", headers=entorno.docente_headers, json={"retroalimentacion_general": "x"})
    assert r.status_code == 409


# --- Autorización docente -------------------------------------------------------------------------------


def _rutas_docentes(entorno, pid):
    s, p = entorno.sesion_id, pid
    return [
        ("post", f"/api/v1/sessions/{s}/evaluations/process", None),
        ("get", f"/api/v1/sessions/{s}/evaluations", None),
        ("get", f"/api/v1/sessions/{s}/absences", None),
        ("get", f"/api/v1/participations/{p}/evaluation", None),
        ("post", f"/api/v1/participations/{p}/evaluation/recalculate", None),
        ("patch", f"/api/v1/participations/{p}/feedback", {"retroalimentacion_general": "x"}),
    ]


def test_otro_docente_recibe_404(entorno, otro_creador_headers):
    pid = intento(entorno, 0, {0: 0})
    for metodo, ruta, cuerpo in _rutas_docentes(entorno, pid):
        r = entorno.client.request(metodo, ruta, headers=otro_creador_headers, json=cuerpo)
        assert r.status_code == 404, (ruta, r.text)
    assert nota_bd(pid) is None


@pytest.mark.parametrize("actor", ["anonimo", "estudiante_access", "token_resolucion", "admin", "token_resultados"])
def test_rechazo_de_actores_no_docentes(entorno, actor, estudiante_headers, admin_headers):
    pid = intento(entorno, 0, {0: 0})
    headers = {
        "anonimo": {},
        "estudiante_access": estudiante_headers,
        "token_resolucion": entorno.headers(1),
        "admin": admin_headers,
    }.get(actor)
    if actor == "token_resultados":
        finalizar_sesion(entorno)
        headers = headers_resultados(entorno, 0)
    esperado = 403 if actor in ("estudiante_access", "admin") else 401
    for metodo, ruta, cuerpo in _rutas_docentes(entorno, pid):
        r = entorno.client.request(metodo, ruta, headers=headers, json=cuerpo)
        assert r.status_code == esperado, (actor, ruta, r.status_code)
    assert nota_bd(pid) is None


def test_ruta_inexistente_responde_404(entorno):
    falso = uuid.uuid4()
    assert entorno.client.get(f"/api/v1/participations/{falso}/evaluation", headers=entorno.docente_headers).status_code == 404
    assert entorno.client.post(f"/api/v1/sessions/{falso}/evaluations/process", headers=entorno.docente_headers).status_code == 404


# --- Resultados del estudiante ------------------------------------------------------------------------------


def test_resultados_bloqueados_antes_de_finalizar_la_sesion(entorno):
    pid = intento(entorno, 0, {0: 0})
    procesar(entorno)  # el docente ya evaluó, pero la sesión sigue EN_CURSO

    r = login_resultados(entorno, 0)
    cuestionario = entorno.client.get(f"{PART_URL}/{pid}/questionnaire", headers=entorno.headers(0)).json()

    assert r.status_code == 403
    assert r.json()["detail"] == "Los resultados estarán disponibles cuando la sesión finalice."
    assert "es_correcta" not in json.dumps(cuestionario) and "justificacion" not in json.dumps(cuestionario)


def test_token_de_resolucion_no_sirve_para_resultados(entorno):
    intento(entorno, 0, {0: 0})
    headers = entorno.headers(0)
    finalizar_sesion(entorno)
    procesar(entorno)

    assert entorno.client.get("/api/v1/student/results", headers=headers).status_code == 401


def test_consulta_segura_de_resultados_tras_el_cierre(entorno):
    pid = intento(entorno, 0, {0: 0, 1: 1})
    ajeno = intento(entorno, 1, {0: 0})
    finalizar_sesion(entorno)

    login = login_resultados(entorno, 0)
    headers = bearer(login.json()["access_token"])
    pendiente = entorno.client.get(f"/api/v1/student/results/{pid}", headers=headers)
    lista_pendiente = entorno.client.get("/api/v1/student/results", headers=headers).json()
    procesar(entorno)
    lista = entorno.client.get("/api/v1/student/results", headers=headers)
    detalle = entorno.client.get(f"/api/v1/student/results/{pid}", headers=headers)
    otro = entorno.client.get(f"/api/v1/student/results/{ajeno}", headers=headers)

    assert login.status_code == 200 and login.headers["cache-control"] == "no-store"
    assert login.json()["alcance"] == "resultados:lectura"
    assert pendiente.status_code == 409
    assert lista_pendiente["resultados"][0]["disponible"] is False and lista_pendiente["resultados"][0]["nota_final"] is None
    assert lista.status_code == 200 and lista.headers["cache-control"] == "no-store"
    assert [(r["participacion_id"], r["nota_final"], r["disponible"]) for r in lista.json()["resultados"]] == [(pid, "2.20", True)]
    assert detalle.status_code == 200
    cuerpo = detalle.json()
    assert cuerpo["nota_final"] == "2.20"
    assert [p["resultado"] for p in cuerpo["preguntas"]] == ["ACIERTO", "ERROR", "SIN_RESPUESTA"]
    assert cuerpo["preguntas"][1]["opcion_elegida"]["justificacion"] == "Ignora el contexto social."
    assert cuerpo["preguntas"][2]["opciones_correctas"][0]["texto"].endswith("respuesta adecuada")
    assert "nota_calculada" not in cuerpo and "estudiante_id" not in cuerpo
    assert otro.status_code == 404


def test_token_de_resultados_es_de_solo_lectura(entorno):
    intento(entorno, 0, {0: 0})
    finalizar_sesion(entorno)
    headers = headers_resultados(entorno, 0)
    preguntas = entorno.preguntas

    assert iniciar_participacion(entorno.client, headers, entorno.sesion_id).status_code == 401
    assert entorno.client.get(PART_URL, headers=headers).status_code == 401
    assert guardar(entorno.client, headers, uuid.uuid4(), preguntas[0]["id"], preguntas[0]["opciones"][0]["id"]).status_code == 401
    assert entorno.client.get(f"/api/v1/student/sessions/{entorno.sesion_id}", headers=headers).status_code == 401
    assert entorno.client.get("/api/v1/sessions", headers=headers).status_code == 401
    assert entorno.client.get("/api/v1/users/me", headers=headers).status_code == 401


def test_estudiante_ausente_ve_lista_vacia(entorno):
    intento(entorno, 0, {0: 0})
    finalizar_sesion(entorno)
    assert entorno.client.get("/api/v1/student/results", headers=headers_resultados(entorno, 2)).json()["resultados"] == []


def test_intento_sin_calificar_visible_para_el_estudiante(entorno):
    pid = intento(entorno, 0, finalizar=False)
    finalizar_sesion(entorno)
    procesar(entorno)

    detalle = entorno.client.get(f"/api/v1/student/results/{pid}", headers=headers_resultados(entorno, 0)).json()

    assert (detalle["calificacion"], detalle["nota_final"], detalle["condicion"]) == ("SIN_CALIFICAR", None, "INCOMPLETA")
    assert any("sin calificar" in o for o in detalle["observaciones"])


@pytest.mark.parametrize("caso", ["revocada", "codigo_regenerado"])
def test_resultados_revalidan_el_estado_actual(entorno, caso):
    intento(entorno, 0, {0: 0})
    if caso == "revocada":
        finalizar_sesion(entorno)
        headers = headers_resultados(entorno, 0)
        with engine.begin() as conn:
            conn.execute(text("UPDATE convocatoria SET revocada_en = now() WHERE estudiante_id = :e"), {"e": entorno.estudiantes[0].id})
        assert entorno.client.get("/api/v1/student/results", headers=headers).status_code == 401
        assert login_resultados(entorno, 0).status_code == 403
    else:
        finalizar_sesion(entorno)
        headers = headers_resultados(entorno, 0)
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE convocatoria SET codigo_autorizacion = 'v1.otro' WHERE estudiante_id = :e"), {"e": entorno.estudiantes[0].id}
            )
        assert entorno.client.get("/api/v1/student/results", headers=headers).status_code == 401


def test_fuerza_bruta_comparte_el_limite_con_el_ingreso_estudiantil(entorno):
    finalizar_sesion(entorno)
    correo = entorno.estudiantes[0].correo
    for _ in range(3):
        assert ingresar(entorno.client, correo, "ZZZZZZZZZZZZ").status_code == 401
    for _ in range(2):
        assert login_resultados(entorno, 0, codigo="ZZZZZZZZZZZZ").status_code == 401

    bloqueado = login_resultados(entorno, 0)  # incluso con el código correcto

    assert bloqueado.status_code == 429
    assert "retry-after" in bloqueado.headers
