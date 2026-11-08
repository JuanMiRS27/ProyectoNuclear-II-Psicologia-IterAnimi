"""Utilidades compartidas por las pruebas del módulo 7 (seguimiento y reportes).

Reutilizan el `entorno` del módulo 4: sesión 08:00-10:00 (límite de ingreso 09:00,
tiempo máximo 40 min) con tres estudiantes convocados y el caso de `dsl_valido()`:
E1P1 y E2P1 del criterio ANALISIS (peso 60), E1P2 de DECISION (peso 40), opción 0 correcta,
escala 5 y niveles 0 % -> 1.00, 50 % -> 3.00, 85 % -> 5.00.
"""

import csv
import io
import uuid
from typing import Any

from sqlalchemy import text

from app.core.database import engine
from tests.participations_helpers import PART_URL, guardar

API = "/api/v1"


def url_sesion(entorno, sufijo: str = "summary") -> str:
    return f"{API}/sessions/{entorno.sesion_id}/reports/{sufijo}"


def obtener(entorno, ruta: str, headers=None, **params) -> Any:
    r = entorno.client.get(ruta, headers=headers or entorno.docente_headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def responder(entorno, headers, participacion_id, elecciones: dict[int, int]) -> None:
    """elecciones: índice de pregunta -> índice de opción (0 es la correcta)."""
    for i, opcion in elecciones.items():
        pregunta = entorno.preguntas[i]
        r = guardar(entorno.client, headers, participacion_id, pregunta["id"], pregunta["opciones"][opcion]["id"])
        assert r.status_code == 200, r.text


def intento(entorno, indice: int = 0, elecciones: dict[int, int] | None = None, finalizar: bool = True) -> str:
    headers = entorno.headers(indice)
    participacion = entorno.iniciar(headers)
    responder(entorno, headers, participacion["id"], elecciones or {})
    if finalizar:
        r = entorno.client.post(f"{PART_URL}/{participacion['id']}/finish", headers=headers)
        assert r.status_code == 200, r.text
    return participacion["id"]


def procesar(entorno) -> dict:
    r = entorno.client.post(f"{API}/sessions/{entorno.sesion_id}/evaluations/process", headers=entorno.docente_headers)
    assert r.status_code == 200, r.text
    return r.json()


def finalizar_sesion(entorno) -> None:
    r = entorno.client.post(f"{API}/sessions/{entorno.sesion_id}/finish", headers=entorno.docente_headers)
    assert r.status_code == 200, r.text


def autorizar_intentos(entorno, indice: int, intentos: int) -> None:
    r = entorno.client.patch(
        entorno.conv_url(indice, "/attempts"),
        headers=entorno.docente_headers,
        json={"intentos_autorizados": intentos, "motivo": "Falla técnica del equipo"},
    )
    assert r.status_code == 200, r.text


def revocar(entorno, indice: int) -> None:
    r = entorno.client.delete(entorno.conv_url(indice), headers=entorno.docente_headers)
    assert r.status_code == 204, r.text


def leer_csv(contenido: bytes) -> list[list[str]]:
    assert contenido.startswith(b"\xef\xbb\xbf"), "El CSV debe ser UTF-8 con BOM."
    return list(csv.reader(io.StringIO(contenido.decode("utf-8-sig"), newline="")))


def huella_academica() -> dict[str, list[tuple]]:
    """Copia de las tablas académicas para comprobar que un reporte no modifica nada."""
    consultas = {
        "participacion": "SELECT id, estado::text, inicio, fin, motivo_cierre::text, nota_final, retroalimentacion_general FROM participacion ORDER BY id",
        "respuesta": "SELECT id, participacion_id, pregunta_id, opcion_id, actualizada_en FROM respuesta ORDER BY id",
        "convocatoria": "SELECT id, codigo_autorizacion, intentos_autorizados, revocada_en FROM convocatoria ORDER BY id",
        "sesion": "SELECT id, estado::text, inicio, fin FROM sesion ORDER BY id",
        "caso_estudio": "SELECT id, estado::text, actualizado_en FROM caso_estudio ORDER BY id",
        "evento_outbox": "SELECT id FROM evento_outbox ORDER BY id",
    }
    with engine.connect() as conn:
        return {tabla: [tuple(f) for f in conn.execute(text(sql))] for tabla, sql in consultas.items()}


def nuevo_uuid() -> str:
    return str(uuid.uuid4())
