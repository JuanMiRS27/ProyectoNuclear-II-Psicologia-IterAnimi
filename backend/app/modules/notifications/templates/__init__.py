"""Plantillas de los mensajes, separadas de la lógica de envío.

Dos salidas por tipo:

- `aviso_interno`: título y mensaje que se GUARDAN en `notificacion`. Nunca incluyen el
  código de autorización ni la nota.
- `correo`: asunto, texto y HTML que se generan en el momento del envío. Solo los correos
  de convocatoria y de código regenerado incluyen el código vigente. Ningún correo incluye
  la nota, las respuestas correctas ni las justificaciones.

Todo valor procedente de usuarios (nombre del caso, lugar, mensaje del docente, nombre del
estudiante) se escapa en el HTML con `html.escape`.
"""

import html
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.modules.notifications.models import TipoNotificacionEnum as T

MARCA = "Inter Nos"


@dataclass(frozen=True, slots=True)
class DatosAviso:
    """Datos vigentes de la sesión y del destinatario (se leen al preparar o enviar)."""

    caso_nombre: str
    inicio: datetime
    fin: datetime
    tiempo_max_min: int
    lugar: str | None = None
    mensaje_docente: str | None = None
    nombre_estudiante: str = ""
    correo_estudiante: str = ""
    numero_intento: int | None = None


@dataclass(frozen=True, slots=True)
class ContenidoCorreo:
    asunto: str
    texto: str
    html: str


def zona(offset_horas: int) -> timezone:
    return timezone(timedelta(hours=offset_horas))


def _fecha(valor: datetime, tz: timezone) -> str:
    return valor.astimezone(tz).strftime("%d/%m/%Y")


def _hora(valor: datetime, tz: timezone) -> str:
    """"08:00 (UTC-05:00)": la zona se indica siempre, el destinatario puede estar en otra."""
    local = valor.astimezone(tz)
    desfase = local.strftime("%z")  # "-0500"
    return f"{local:%H:%M} (UTC{desfase[:3]}:{desfase[3:]})"


def _programacion(d: DatosAviso, tz: timezone) -> list[tuple[str, str]]:
    filas = [
        ("Caso académico", d.caso_nombre),
        ("Fecha", _fecha(d.inicio, tz)),
        ("Hora de inicio", _hora(d.inicio, tz)),
        ("Hora de finalización", _hora(d.fin, tz)),
        ("Tiempo máximo de participación", f"{d.tiempo_max_min} minutos"),
    ]
    if d.lugar:
        filas.append(("Lugar o modalidad", d.lugar))
    if d.mensaje_docente:
        filas.append(("Mensaje del docente", d.mensaje_docente))
    return filas


# Nombres legibles de los campos de SESION_MODIFICADA.
CAMPOS_LEGIBLES = {
    "caso_id": "caso académico",
    "inicio": "fecha u hora de inicio",
    "fin": "hora de finalización",
    "tiempo_max_min": "tiempo máximo de participación",
    "lugar": "lugar o modalidad",
    "mensaje": "mensaje del docente",
}


def describir_cambios(cambios: list[str] | None) -> str:
    nombres = [CAMPOS_LEGIBLES[c] for c in (cambios or []) if c in CAMPOS_LEGIBLES]
    return ", ".join(nombres)


# --- Avisos internos (persistidos) ------------------------------------------------------------


def aviso_interno(tipo: T, d: DatosAviso, tz: timezone, *, cambios: list[str] | None = None) -> tuple[str, str]:
    cuando = f"{_fecha(d.inicio, tz)} a las {_hora(d.inicio, tz)}"
    detalle = f" Cambió: {describir_cambios(cambios)}." if describir_cambios(cambios) else ""
    textos = {
        T.CONVOCATORIA: (
            f"Convocatoria: {d.caso_nombre}",
            f"Has sido convocado a la sesión del caso «{d.caso_nombre}» el {cuando}. "
            "El código de autorización se envía únicamente a tu correo institucional.",
        ),
        T.CODIGO_REGENERADO: (
            f"Nuevo código de autorización: {d.caso_nombre}",
            "El docente generó un nuevo código de autorización para tu convocatoria. El código anterior "
            "ya no es válido; el nuevo se envía únicamente a tu correo institucional.",
        ),
        T.REPROGRAMACION: (
            f"Cambio de programación: {d.caso_nombre}",
            f"La sesión del caso «{d.caso_nombre}» cambió.{detalle} Programación vigente: {cuando}, hasta las "
            f"{_hora(d.fin, tz)}; tiempo máximo {d.tiempo_max_min} minutos.",
        ),
        T.REVOCACION: (
            f"Convocatoria retirada: {d.caso_nombre}",
            f"El docente retiró tu convocatoria a la sesión del caso «{d.caso_nombre}». Ya no puedes ingresar con su código.",
        ),
        T.RESULTADOS_DISPONIBLES: (
            f"Resultados disponibles: {d.caso_nombre}",
            f"La evaluación de la sesión del caso «{d.caso_nombre}» ya puede consultarse en la plataforma.",
        ),
        T.CALIFICACION_ACTUALIZADA: (
            f"Evaluación actualizada: {d.caso_nombre}",
            f"El docente actualizó la evaluación de tu intento {d.numero_intento} del caso «{d.caso_nombre}». "
            "Consúltala en la plataforma.",
        ),
        T.RETROALIMENTACION: (
            f"Retroalimentación del docente: {d.caso_nombre}",
            f"El docente agregó retroalimentación a tu intento {d.numero_intento} del caso «{d.caso_nombre}». "
            "Puedes consultarla en la plataforma.",
        ),
    }
    return textos[tipo]


# --- Correos (no se persisten) -------------------------------------------------------------------


def _documento(titulo: str, parrafos: list[str], filas: list[tuple[str, str]]) -> str:
    e = html.escape
    tabla = "".join(f"<tr><th align='left'>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in filas)
    cuerpo = "".join(f"<p>{e(p)}</p>" for p in parrafos)
    return (
        f"<!doctype html><html><body><h1>{e(MARCA)}</h1><h2>{e(titulo)}</h2>{cuerpo}"
        f"{'<table>' + tabla + '</table>' if filas else ''}"
        "<p><small>Mensaje automático. No respondas a este correo.</small></p></body></html>"
    )


def _texto(titulo: str, parrafos: list[str], filas: list[tuple[str, str]]) -> str:
    lineas = [MARCA, "", titulo, "", *parrafos]
    if filas:
        lineas += ["", *(f"{k}: {v}" for k, v in filas)]
    lineas += ["", "Mensaje automático. No respondas a este correo."]
    return "\n".join(lineas)


def correo(
    tipo: T, d: DatosAviso, tz: timezone, *, codigo: str | None = None, url: str | None = None, cambios: list[str] | None = None
) -> ContenidoCorreo:
    if tipo in (T.CONVOCATORIA, T.CODIGO_REGENERADO) and not (codigo and url):
        raise ValueError("Los correos de convocatoria requieren el código vigente y la URL de acceso.")
    saludo = f"Hola, {d.nombre_estudiante}." if d.nombre_estudiante else "Hola."
    acceso = [("Correo institucional", d.correo_estudiante), ("Código de autorización", codigo or ""), ("Acceso", url or "")]

    if tipo == T.CONVOCATORIA:
        titulo, parrafos = "Convocatoria a una sesión académica", [
            saludo,
            "Has sido convocado a una sesión del simulador. Ingresa con tu correo institucional y este código:",
        ]
        filas = _programacion(d, tz) + acceso
    elif tipo == T.CODIGO_REGENERADO:
        titulo, parrafos = "Nuevo código de autorización", [
            saludo,
            "El docente generó un nuevo código para tu convocatoria. Cualquier código anterior dejó de ser válido.",
        ]
        filas = _programacion(d, tz) + acceso
    elif tipo == T.REPROGRAMACION:
        cambio = f" Cambió: {describir_cambios(cambios)}." if describir_cambios(cambios) else ""
        titulo, parrafos = "Cambio de programación", [
            saludo,
            f"La sesión a la que estás convocado cambió.{cambio} Estos son los datos vigentes al momento de este envío:",
        ]
        filas = _programacion(d, tz)
    elif tipo == T.REVOCACION:
        titulo, parrafos = "Convocatoria retirada", [
            saludo,
            f"El docente retiró tu convocatoria a la sesión del caso «{d.caso_nombre}». El código que recibiste ya no permite ingresar.",
        ]
        filas = []
    elif tipo == T.RESULTADOS_DISPONIBLES:
        titulo, parrafos = "Resultados disponibles", [
            saludo,
            f"La evaluación de la sesión del caso «{d.caso_nombre}» ya puede consultarse en la plataforma con tu "
            "correo institucional y tu código de convocatoria.",
        ]
        filas = []
    elif tipo == T.CALIFICACION_ACTUALIZADA:
        titulo, parrafos = "Evaluación actualizada", [
            saludo,
            f"El docente actualizó la evaluación de tu intento {d.numero_intento} del caso «{d.caso_nombre}». Consúltala en la plataforma.",
        ]
        filas = []
    else:
        raise ValueError(f"El aviso {tipo.value} no se envía por correo.")
    asunto = f"{MARCA}: {titulo} — {d.caso_nombre}"[:200]
    return ContenidoCorreo(asunto, _texto(titulo, parrafos, filas), _documento(titulo, parrafos, filas))


# Avisos que además se envían por correo (el resto son solo internos).
TIPOS_CON_CORREO = frozenset(
    {T.CONVOCATORIA, T.CODIGO_REGENERADO, T.REPROGRAMACION, T.REVOCACION, T.RESULTADOS_DISPONIBLES, T.CALIFICACION_ACTUALIZADA}
)
# Avisos cuyo correo incluye el código de autorización vigente.
TIPOS_CON_CODIGO = frozenset({T.CONVOCATORIA, T.CODIGO_REGENERADO})
