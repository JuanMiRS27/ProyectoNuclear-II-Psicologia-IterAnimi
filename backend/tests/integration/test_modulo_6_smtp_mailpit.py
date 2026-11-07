"""Prueba de extremo a extremo con un servidor SMTP REAL de captura (Mailpit), solo local.

Se ejecuta únicamente si se definen MAILPIT_SMTP_PORT y MAILPIT_API_URL apuntando a
localhost; si no, se omite. Nunca se conecta a un host que no sea local, así que ninguna
ejecución puede enviar correos hacia Internet:

    docker run -d --rm --name inter_nos_mailpit -p 127.0.0.1:1025:1025 -p 127.0.0.1:8025:8025 axllent/mailpit:v1.20.0
    MAILPIT_SMTP_PORT=1025 MAILPIT_API_URL=http://127.0.0.1:8025 pytest tests/integration/test_modulo_6_smtp_mailpit.py

Con MAILPIT_EVIDENCIA_DIR se guardan como evidencia el mensaje recibido y el estado de la
entrega, con el código de autorización REDACTADO.
"""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.modules.notifications.adapters import AdaptadorCorreoSMTP, crear_servicio_correo
from app.modules.notifications.services.procesador_eventos import espera_reintento
from app.workers.notifications import ejecutar_una_vez
from tests.participations_helpers import contar, entorno  # noqa: F401

SMTP_PORT = os.environ.get("MAILPIT_SMTP_PORT")
API_URL = os.environ.get("MAILPIT_API_URL", "")
LOCALES = {"localhost", "127.0.0.1", "::1"}
URL_ACCESO = "http://localhost:5173"
REMITENTE = "no-responder@internos-pruebas.edu.co"  # ficticio: el correo nunca sale de Mailpit

pytestmark = pytest.mark.skipif(
    not (SMTP_PORT and API_URL and urlparse(API_URL).hostname in LOCALES),
    reason="Mailpit local no configurado (MAILPIT_SMTP_PORT y MAILPIT_API_URL en localhost).",
)


@pytest.fixture
def mailpit():
    with httpx.Client(base_url=API_URL, timeout=5) as api:
        api.delete("/api/v1/messages").raise_for_status()
        yield api


@pytest.fixture
def smtp_local(monkeypatch):
    """Activa TEMPORALMENTE el envío real hacia el Mailpit local (sin TLS ni credenciales: solo localhost)."""
    settings = get_settings()
    for nombre, valor in {
        "NOTIFICATIONS_EMAIL_ENABLED": True,
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": int(SMTP_PORT or 0),
        "SMTP_USE_STARTTLS": False,
        "SMTP_USE_SSL": False,
        "SMTP_USERNAME": None,
        "SMTP_PASSWORD": None,
        "SMTP_FROM_EMAIL": REMITENTE,
        "SIMULATOR_ACCESS_URL": URL_ACCESO,
    }.items():
        monkeypatch.setattr(settings, nombre, valor)
    adaptador = crear_servicio_correo(settings)
    assert isinstance(adaptador, AdaptadorCorreoSMTP)
    assert settings.SMTP_HOST in LOCALES  # salvaguarda: nunca hacia Internet
    return settings


def entregas():
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT e.id, e.estado::text AS estado, e.intentos, e.ultimo_error, e.enviada_en, u.correo "
            "FROM entrega_correo e JOIN notificacion n ON n.id = e.notificacion_id JOIN usuario u ON u.id = n.destinatario_id "
            "ORDER BY u.correo"
        )).all()


def mensajes(api: httpx.Client) -> list[dict]:
    return api.get("/api/v1/messages").json()["messages"]


def guardar_evidencia(nombre: str, datos, codigos: list[str]) -> None:
    carpeta = os.environ.get("MAILPIT_EVIDENCIA_DIR")
    if not carpeta:
        return
    contenido = json.dumps(datos, ensure_ascii=False, indent=2, default=str)
    for codigo in codigos:
        contenido = contenido.replace(codigo, "[CÓDIGO DE PRUEBA REDACTADO]")
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    (Path(carpeta) / nombre).write_text(contenido, encoding="utf-8")


def test_convocatoria_llega_a_mailpit_y_la_entrega_queda_enviada(entorno, smtp_local, mailpit):
    # 4-5. La programación del entorno creó tres convocatorias y sus eventos en el outbox.
    assert contar("SELECT count(*) FROM evento_outbox WHERE tipo = 'CONVOCATORIA_CREADA' AND estado = 'PENDIENTE'") == 3

    # 6-8. Worker real, con el adaptador SMTP que construye la configuración.
    pasada = ejecutar_una_vez(reloj=entorno.reloj)

    assert (pasada.eventos.procesados >= 3, pasada.entregas.enviadas) == (True, 3)
    recibidos = mensajes(mailpit)
    assert len(recibidos) == 3
    estudiante = entorno.estudiantes[0]
    codigo = entorno.codigos[estudiante.correo]
    resumen = next(m for m in recibidos if m["To"][0]["Address"] == estudiante.correo)
    detalle = mailpit.get(f"/api/v1/message/{resumen['ID']}").json()

    # 9-10. Destinatario único, asunto, cuerpo, URL de acceso y código vigente.
    assert [t["Address"] for t in detalle["To"]] == [estudiante.correo] and not detalle.get("Cc") and not detalle.get("Bcc")
    assert detalle["From"]["Address"] == REMITENTE
    assert detalle["Subject"] == "Inter Nos: Convocatoria a una sesión académica — Conformidad en el aula"
    assert codigo in detalle["Text"] and URL_ACCESO in detalle["Text"] and estudiante.correo in detalle["Text"]
    assert "Tiempo máximo de participación: 40 minutos" in detalle["Text"] and "Aula 301" in detalle["Text"]
    assert codigo in detalle["HTML"]
    otros = [e.correo for e in entorno.estudiantes[1:]]
    assert not any(o in detalle["Text"] + detalle["HTML"] for o in otros)
    assert detalle["MessageID"].startswith("entrega-") and detalle["MessageID"].endswith("@internos-pruebas.edu.co")

    # 11. Persistencia: ENVIADA, sin error y sin el código en la base de datos.
    filas = entregas()
    assert {f.estado for f in filas} == {"ENVIADA"} and all(f.enviada_en and f.intentos == 1 and f.ultimo_error is None for f in filas)
    with engine.connect() as conn:
        volcado = "\n".join(str(r) for t in ("evento_outbox", "notificacion", "entrega_correo") for r in conn.execute(text(f"SELECT * FROM {t}")))
    assert not any(c in volcado for c in entorno.codigos.values())

    guardar_evidencia("mailpit_mensaje.json", {k: detalle[k] for k in ("From", "To", "Subject", "MessageID", "Date", "Text")}, list(entorno.codigos.values()))
    guardar_evidencia("entregas_enviadas.json", [dict(f._mapping) for f in filas], list(entorno.codigos.values()))


def test_fallo_de_conexion_smtp_se_reintenta_y_luego_se_entrega(entorno, smtp_local, mailpit, monkeypatch):
    monkeypatch.setattr(smtp_local, "SMTP_PORT", 1)  # puerto local cerrado: conexión rechazada

    caida = ejecutar_una_vez(reloj=entorno.reloj)

    assert (caida.entregas.enviadas, caida.entregas.reintentos) == (0, 3)
    filas = entregas()
    assert {(f.estado, f.intentos) for f in filas} == {("PENDIENTE", 1)}
    assert {f.ultimo_error for f in filas} == {"Fallo de red o de protocolo SMTP (ConnectionRefusedError)."}
    assert mensajes(mailpit) == []
    guardar_evidencia("entregas_tras_fallo_smtp.json", [dict(f._mapping) for f in filas], list(entorno.codigos.values()))

    monkeypatch.setattr(smtp_local, "SMTP_PORT", int(SMTP_PORT))  # el servidor vuelve
    entorno.reloj.avanzar(seconds=espera_reintento(1).total_seconds())
    recuperada = ejecutar_una_vez(reloj=entorno.reloj)

    assert recuperada.entregas.enviadas == 3 and len(mensajes(mailpit)) == 3
    assert {(f.estado, f.intentos) for f in entregas()} == {("ENVIADA", 2)}
