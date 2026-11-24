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

MARCA = "Iter Animi"


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


# Paleta del frontend (frontend/src/styles/tokens.css, tema claro). Los correos usan estilos en
# línea y tablas: es lo único que respetan Gmail, Outlook y los clientes móviles.
_C = {
    "fondo": "#f6f8fc",
    "superficie": "#ffffff",
    "bruma": "#ecf1f7",
    "tinta": "#1e3350",
    "texto": "#1f2530",
    "suave": "#556070",
    "borde": "#e1e6ec",
    "accion": "#4269a5",
    "acento": "#9fb6d3",
    "panel_texto": "#e3eaf3",
}
# Sin comillas simples: los atributos `style` del HTML van entre comillas simples.
_FUENTE = 'Manrope,"Segoe UI",Helvetica,Arial,sans-serif'
# Etiqueta y color por tipo de aviso: (texto de la insignia, color, fondo, borde).
_TONOS = {
    T.CONVOCATORIA: ("Nueva convocatoria", "#335b88", "#eaf0fa", "#c9d7ec"),
    T.CODIGO_REGENERADO: ("Código actualizado", "#835410", "#fbf3e4", "#e8d4a8"),
    T.REPROGRAMACION: ("Cambio de programación", "#835410", "#fbf3e4", "#e8d4a8"),
    T.REVOCACION: ("Convocatoria retirada", "#a3404a", "#f8eced", "#e6c6c9"),
    T.RESULTADOS_DISPONIBLES: ("Resultados disponibles", "#2c6549", "#e9f3ee", "#c4ddd0"),
    T.CALIFICACION_ACTUALIZADA: ("Evaluación actualizada", "#2c6549", "#e9f3ee", "#c4ddd0"),
}
_BOTONES = {
    T.CONVOCATORIA: "Ingresar al simulador",
    T.CODIGO_REGENERADO: "Ingresar al simulador",
    T.REPROGRAMACION: "Abrir Iter Animi",
    T.RESULTADOS_DISPONIBLES: "Consultar mis resultados",
    T.CALIFICACION_ACTUALIZADA: "Ver mi evaluación",
}
_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
          "octubre", "noviembre", "diciembre")


def _fecha_larga(valor: datetime, tz: timezone) -> str:
    local = valor.astimezone(tz)
    return f"{_DIAS[local.weekday()].capitalize()} {local.day} de {_MESES[local.month - 1]} de {local.year}"


def _marca_html() -> str:
    """Logotipo de la app (dos aros enlazados) dibujado con CSS: sin imágenes externas."""
    aro = (
        "display:inline-block;width:18px;height:18px;border-radius:50%;"
        "vertical-align:middle;border:2px solid {color};"
    )
    return (
        "<table role='presentation' cellpadding='0' cellspacing='0' border='0'><tr>"
        "<td style='vertical-align:middle;padding-right:10px;'>"
        f"<span style='{aro.format(color='#ffffff')}'></span>"
        f"<span style='{aro.format(color=_C['acento'])}margin-left:-9px;'></span></td>"
        f"<td style='vertical-align:middle;font-family:{_FUENTE};font-size:18px;font-weight:700;"
        f"letter-spacing:0.2px;color:#ffffff;'>{html.escape(MARCA)}</td></tr></table>"
    )


def _documento(
    tipo: T,
    titulo: str,
    parrafos: list[str],
    d: DatosAviso,
    tz: timezone,
    *,
    con_programacion: bool,
    codigo: str | None,
    url: str | None,
) -> str:
    e = html.escape
    etiqueta, tono, tono_fondo, tono_borde = _TONOS[tipo]

    insignia = (
        f"<span style='display:inline-block;padding:5px 12px;border-radius:999px;font-size:12px;"
        f"font-weight:700;letter-spacing:0.4px;text-transform:uppercase;color:{tono};"
        f"background:{tono_fondo};border:1px solid {tono_borde};'>{e(etiqueta)}</span>"
    )
    cuerpo = "".join(
        f"<p style='margin:0 0 14px;font-size:15px;line-height:1.6;color:{_C['texto']};'>{e(p)}</p>"
        for p in parrafos
    )

    bloque_codigo = ""
    if codigo:
        bloque_codigo = (
            f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0' "
            f"style='margin:8px 0 22px;background:{_C['bruma']};border:1px dashed {_C['acento']};border-radius:14px;'>"
            "<tr><td align='center' style='padding:20px 16px;'>"
            f"<div style='font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;"
            f"color:{_C['suave']};margin-bottom:8px;'>Código de autorización</div>"
            f"<div style=\"font-family:Consolas,'Courier New',monospace;font-size:30px;font-weight:700;"
            f"letter-spacing:6px;color:{_C['tinta']};\">{e(codigo)}</div>"
            + (
                f"<div style='font-size:13px;color:{_C['suave']};margin-top:10px;'>Úsalo junto con "
                f"<strong style='color:{_C['texto']};'>{e(d.correo_estudiante)}</strong></div>"
                if d.correo_estudiante
                else ""
            )
            + "</td></tr></table>"
        )

    tarjeta = ""
    if con_programacion:
        filas = [
            ("Caso académico", d.caso_nombre),
            ("Horario", f"{d.inicio.astimezone(tz):%H:%M} – {_hora(d.fin, tz)}"),
            ("Tiempo máximo", f"{d.tiempo_max_min} minutos"),
        ]
        if d.lugar:
            filas.append(("Lugar o modalidad", d.lugar))
        celdas = "".join(
            "<tr>"
            f"<td style='padding:10px 0;border-top:1px solid {_C['borde']};font-size:13px;color:{_C['suave']};"
            f"width:42%;vertical-align:top;'>{e(k)}</td>"
            f"<td style='padding:10px 0;border-top:1px solid {_C['borde']};font-size:14px;font-weight:600;"
            f"color:{_C['texto']};vertical-align:top;'>{e(v)}</td></tr>"
            for k, v in filas
        )
        mensaje = ""
        if d.mensaje_docente:
            mensaje = (
                f"<tr><td colspan='2' style='padding:14px 0 0;'>"
                f"<div style='border-left:3px solid {_C['accion']};background:{_C['fondo']};"
                f"padding:12px 14px;border-radius:0 10px 10px 0;'>"
                f"<div style='font-size:12px;font-weight:700;color:{_C['suave']};margin-bottom:4px;'>"
                "Mensaje del docente</div>"
                f"<div style='font-size:14px;line-height:1.55;color:{_C['texto']};font-style:italic;'>"
                f"{e(d.mensaje_docente)}</div></div></td></tr>"
            )
        tarjeta = (
            f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0' "
            f"style='margin:4px 0 22px;border:1px solid {_C['borde']};border-radius:14px;'>"
            "<tr><td style='padding:18px 20px;'>"
            f"<div style='font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;"
            f"color:{_C['accion']};margin-bottom:4px;'>Sesión programada</div>"
            f"<div style='font-size:19px;font-weight:700;color:{_C['tinta']};margin-bottom:12px;'>"
            f"{e(_fecha_larga(d.inicio, tz))}</div>"
            f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0'>"
            f"{celdas}{mensaje}</table></td></tr></table>"
        )

    boton = ""
    if url and tipo in _BOTONES:
        boton = (
            "<table role='presentation' cellpadding='0' cellspacing='0' border='0' style='margin:4px 0 8px;'>"
            f"<tr><td style='border-radius:10px;background:{_C['accion']};'>"
            f"<a href='{e(url, quote=True)}' target='_blank' style='display:inline-block;padding:13px 26px;"
            f"font-family:{_FUENTE};font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;"
            f"border-radius:10px;'>{e(_BOTONES[tipo])} &rarr;</a></td></tr></table>"
            f"<p style='margin:8px 0 0;font-size:12px;color:{_C['suave']};'>O copia este enlace: "
            f"<a href='{e(url, quote=True)}' style='color:#335b88;'>{e(url)}</a></p>"
        )

    # Texto oculto de vista previa (lo que muestra la bandeja junto al asunto).
    previa = f"{etiqueta} · {d.caso_nombre}"
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{e(titulo)}</title></head>"
        f"<body style='margin:0;padding:0;background:{_C['fondo']};'>"
        f"<div style='display:none;max-height:0;overflow:hidden;opacity:0;'>{e(previa)}</div>"
        f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0' "
        f"style='background:{_C['fondo']};font-family:{_FUENTE};'><tr><td align='center' style='padding:32px 12px;'>"
        "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0' "
        f"style='max-width:580px;background:{_C['superficie']};border-radius:18px;overflow:hidden;"
        f"border:1px solid {_C['borde']};box-shadow:0 12px 32px -16px rgba(30,51,80,0.18);'>"
        # Cabecera con la marca
        f"<tr><td style='background:{_C['tinta']};padding:22px 28px;'>{_marca_html()}"
        f"<div style='font-size:12px;color:{_C['panel_texto']};margin-top:6px;letter-spacing:0.3px;'>"
        "Simulador de Psicología Social</div></td></tr>"
        f"<tr><td style='height:4px;background:{_C['accion']};line-height:4px;font-size:0;'>&nbsp;</td></tr>"
        # Cuerpo
        f"<tr><td style='padding:28px 28px 8px;'>{insignia}"
        f"<h1 style='margin:16px 0 16px;font-size:24px;line-height:1.3;font-weight:800;color:{_C['tinta']};'>"
        f"{e(titulo)}</h1>{cuerpo}{bloque_codigo}{tarjeta}{boton}</td></tr>"
        # Pie
        f"<tr><td style='padding:22px 28px 26px;'>"
        f"<div style='border-top:1px solid {_C['borde']};padding-top:16px;font-size:12px;line-height:1.6;"
        f"color:{_C['suave']};'>Mensaje automático de {e(MARCA)}. No respondas a este correo."
        + ("<br>Tu código es personal: no lo compartas con nadie." if codigo else "")
        + "</div></td></tr>"
        "</table></td></tr></table></body></html>"
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
    documento = _documento(
        tipo, titulo, parrafos, d, tz,
        con_programacion=tipo in (T.CONVOCATORIA, T.CODIGO_REGENERADO, T.REPROGRAMACION),
        codigo=codigo if tipo in (T.CONVOCATORIA, T.CODIGO_REGENERADO) else None,
        url=url,
    )
    return ContenidoCorreo(asunto, _texto(titulo, parrafos, filas), documento)


# Avisos que además se envían por correo (el resto son solo internos).
TIPOS_CON_CORREO = frozenset(
    {T.CONVOCATORIA, T.CODIGO_REGENERADO, T.REPROGRAMACION, T.REVOCACION, T.RESULTADOS_DISPONIBLES, T.CALIFICACION_ACTUALIZADA}
)
# Avisos cuyo correo incluye el código de autorización vigente.
TIPOS_CON_CODIGO = frozenset({T.CONVOCATORIA, T.CODIGO_REGENERADO})
