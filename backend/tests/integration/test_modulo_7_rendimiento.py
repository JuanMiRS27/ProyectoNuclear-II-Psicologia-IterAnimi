"""Eficiencia del módulo 7 con volúmenes mayores (PostgreSQL real).

No fija tiempos absolutos (dependen del equipo). Comprueba lo que sí es verificable:

- La CANTIDAD de consultas por petición no crece con el número de estudiantes ni de intentos
  (sin N+1): se mide con 5 estudiantes y con 200, y debe ser la misma.
- Las FILAS que PostgreSQL devuelve están acotadas por la agregación (por sesión, criterio o
  pregunta), no por el número de respuestas almacenadas.
- Los listados respetan la paginación y la exportación su máximo de filas.

Los datos se insertan en bloque con SQL (sin pasar por la API) respetando los disparadores del
módulo 4: convocatoria activa, sesión EN_CURSO, respuestas solo con el intento EN_PROGRESO y
cierre posterior. Las notas son ficticias: aquí solo importa el volumen.

Con REPORTES_EVIDENCIA_DIR se guarda la medición en JSON (ver docs/REPORTE_PRUEBAS_MODULO_7.md).
"""

import json
import os
import time
import tracemalloc
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import event, text

from app.core.database import engine
from app.main import app
from app.modules.reports.dependencies import get_exportacion_service
from app.modules.reports.services import ExportacionService
from tests.participations_helpers import entorno  # noqa: F401
from tests.reports_helpers import API, leer_csv, url_sesion

INTENTOS_POR_ESTUDIANTE = 2


@contextmanager
def medir():
    """Cuenta las sentencias y las filas devueltas por PostgreSQL durante el bloque."""
    medicion = {"consultas": 0, "filas": 0}

    def contar(conn, cursor, statement, parameters, context, executemany):
        medicion["consultas"] += 1
        if cursor.description is not None and cursor.rowcount > 0:
            medicion["filas"] += cursor.rowcount

    event.listen(engine, "after_cursor_execute", contar)
    inicio = time.perf_counter()
    try:
        yield medicion
    finally:
        medicion["ms"] = round((time.perf_counter() - inicio) * 1000, 1)
        event.remove(engine, "after_cursor_execute", contar)


def poblar(entorno, desde: int, hasta: int) -> None:
    """Estudiantes `desde..hasta-1` con dos intentos cerrados (respuestas en todas las preguntas)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO usuario (nombre_completo, correo, rol, codigo_institucional) "
                "SELECT 'Estudiante ficticio ' || lpad(n::text, 4, '0'), 'ficticio' || n || '@universidad.edu.co', "
                "'ESTUDIANTE', 'F' || n FROM generate_series(:desde, :hasta - 1) AS n"
            ),
            {"desde": desde, "hasta": hasta},
        )
        conn.execute(
            text(
                "INSERT INTO convocatoria (sesion_id, estudiante_id, codigo_autorizacion, intentos_autorizados) "
                "SELECT :sesion, u.id, 'v1.rendimiento', :intentos FROM usuario u "
                "WHERE u.correo LIKE 'ficticio%' AND NOT EXISTS (SELECT 1 FROM convocatoria c WHERE c.estudiante_id = u.id)"
            ),
            {"sesion": entorno.sesion_id, "intentos": INTENTOS_POR_ESTUDIANTE},
        )
        for numero in range(1, INTENTOS_POR_ESTUDIANTE + 1):
            nuevos = conn.execute(
                text(
                    "INSERT INTO participacion (convocatoria_id, numero_intento, inicio, estado) "
                    "SELECT c.id, :numero, TIMESTAMPTZ '2026-11-03 08:00:00+00', 'EN_PROGRESO' FROM convocatoria c "
                    "WHERE c.sesion_id = :sesion AND c.codigo_autorizacion = 'v1.rendimiento' "
                    "AND NOT EXISTS (SELECT 1 FROM participacion p WHERE p.convocatoria_id = c.id AND p.numero_intento = :numero) "
                    "RETURNING id"
                ),
                {"numero": numero, "sesion": entorno.sesion_id},
            ).scalars().all()
            conn.execute(
                text(
                    "INSERT INTO respuesta (participacion_id, pregunta_id, opcion_id, respondida_en, actualizada_en) "
                    "SELECT p.id, q.id, o.id, p.inicio, p.inicio FROM participacion p "
                    "JOIN convocatoria c ON c.id = p.convocatoria_id JOIN sesion s ON s.id = c.sesion_id "
                    "JOIN escenario e ON e.caso_id = s.caso_id JOIN pregunta q ON q.escenario_id = e.id "
                    "JOIN opcion o ON o.pregunta_id = q.id AND o.orden = 1 + abs(hashtext(p.id::text || q.id::text)) % 3 "
                    "WHERE p.id = ANY(:ids)"
                ),
                {"ids": nuevos},
            )
            conn.execute(
                text(
                    "UPDATE participacion SET estado = CASE WHEN numero_intento = 1 THEN 'FINALIZADA' ELSE 'EXPIRADA' END::estado_participacion, "
                    "motivo_cierre = CASE WHEN numero_intento = 1 THEN 'VOLUNTARIO' ELSE 'TIEMPO_AGOTADO' END::motivo_cierre_participacion, "
                    "fin = inicio + interval '10 minutes' WHERE id = ANY(:ids)"
                ),
                {"ids": nuevos},
            )
            conn.execute(text("UPDATE participacion SET nota_final = 3.00 WHERE id = ANY(:ids) AND numero_intento = 1"), {"ids": nuevos})


def _rutas(entorno, estudiante_id) -> dict[str, str]:
    espacio = entorno.sesion["espacio_academico_id"]
    return {
        "summary": url_sesion(entorno, "summary"),
        "students": url_sesion(entorno, "students"),
        "student": url_sesion(entorno, f"students/{estudiante_id}"),
        "grades": url_sesion(entorno, "grades"),
        "criteria": url_sesion(entorno, "criteria"),
        "questions": url_sesion(entorno, "questions"),
        "export_estudiantes": url_sesion(entorno, "export") + "?tipo=estudiantes",
        "export_intentos": url_sesion(entorno, "export") + "?tipo=intentos",
        "my_sessions": f"{API}/reports/my-sessions",
        "space": f"{API}/academic-spaces/{espacio}/reports",
        "case": f"{API}/cases/{entorno.caso['id']}/reports",
    }


def _medir_todo(entorno, estudiante_id) -> dict[str, dict]:
    resultados = {}
    for nombre, ruta in _rutas(entorno, estudiante_id).items():
        with medir() as m:
            r = entorno.client.get(ruta, headers=entorno.docente_headers)
        assert r.status_code == 200, (nombre, r.text)
        resultados[nombre] = m | {"bytes": len(r.content)}
    return resultados


def _id_ficticio():
    with engine.connect() as conn:
        return conn.execute(text("SELECT id FROM usuario WHERE correo = 'ficticio0@universidad.edu.co'")).scalar_one()


def test_las_consultas_no_crecen_con_el_volumen(entorno):
    poblar(entorno, 0, 5)
    estudiante = _id_ficticio()
    pequeno = _medir_todo(entorno, estudiante)
    poblar(entorno, 5, 200)
    grande = _medir_todo(entorno, estudiante)

    for nombre in pequeno:
        assert grande[nombre]["consultas"] == pequeno[nombre]["consultas"], nombre  # sin N+1

    intentos = 200 * INTENTOS_POR_ESTUDIANTE
    respuestas = intentos * len(entorno.preguntas)
    # Agregación en PostgreSQL: las filas devueltas no dependen de las 1 200 respuestas almacenadas.
    for nombre in ("summary", "grades", "questions", "my_sessions", "space"):
        assert grande[nombre]["filas"] < 50, (nombre, grande[nombre])
    assert grande["criteria"]["filas"] <= intentos * 2 + 50 < respuestas  # intento × criterio, no intento × pregunta
    assert grande["students"]["filas"] <= 20 * INTENTOS_POR_ESTUDIANTE + 50  # solo la página

    _guardar_evidencia({"pequeno_5_estudiantes": pequeno, "grande_200_estudiantes": grande, "respuestas": respuestas})


def test_listados_paginados_y_exportaciones_acotadas(entorno):
    poblar(entorno, 0, 120)
    url = url_sesion(entorno, "students")

    pagina = entorno.client.get(url, headers=entorno.docente_headers).json()
    ultima = entorno.client.get(url, headers=entorno.docente_headers, params={"skip": 120, "limit": 100}).json()

    assert (len(pagina["items"]), pagina["total"], pagina["limit"]) == (20, 123, 20)
    assert len(ultima["items"]) == 3
    assert entorno.client.get(url, headers=entorno.docente_headers, params={"limit": 101}).status_code == 422

    tracemalloc.start()
    r = entorno.client.get(url_sesion(entorno, "export"), headers=entorno.docente_headers, params={"tipo": "intentos"})
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert r.status_code == 200 and len(leer_csv(r.content)) == 1 + 120 * INTENTOS_POR_ESTUDIANTE
    _guardar_evidencia({"exportacion_240_intentos": {"bytes": len(r.content), "pico_memoria_kib": round(pico / 1024)}}, "memoria")

    app.dependency_overrides[get_exportacion_service] = lambda: ExportacionService(next(_db()), entorno.reloj, limite=100)
    try:
        r = entorno.client.get(url_sesion(entorno, "export"), headers=entorno.docente_headers, params={"tipo": "intentos"})
        assert r.status_code == 422 and r.json()["codigo"] == "EXPORTACION_EXCEDE_LIMITE"
    finally:
        app.dependency_overrides.pop(get_exportacion_service, None)


def _db():
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        yield session


def _guardar_evidencia(datos: dict, sufijo: str = "consultas") -> None:
    destino = os.environ.get("REPORTES_EVIDENCIA_DIR")
    print(json.dumps(datos, indent=2, ensure_ascii=False))
    if destino:
        Path(destino).mkdir(parents=True, exist_ok=True)
        (Path(destino) / f"rendimiento_{sufijo}.json").write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")


def test_sesion_sin_datos_no_hace_mas_consultas_que_con_datos(entorno):
    """Sin intentos se omiten las consultas de corrección: nunca se hacen más consultas que con datos."""
    vacio = _medir_todo(entorno, entorno.estudiantes[0].id)
    poblar(entorno, 0, 3)
    con_datos = _medir_todo(entorno, entorno.estudiantes[0].id)
    assert all(vacio[n]["consultas"] <= con_datos[n]["consultas"] for n in vacio)
