"""Adapter: contrato `ServicioCorreo` y fábrica del adaptador configurado."""

from urllib.parse import urlparse

from app.core.config import Settings, get_settings
from app.modules.notifications.adapters.base import (
    ConfiguracionCorreoError,
    ErrorCorreo,
    ErrorCorreoPermanente,
    ErrorCorreoTemporal,
    MensajeCorreo,
    MensajeInvalidoError,
    ResultadoEnvio,
    ServicioCorreo,
    validar_direccion,
)
from app.modules.notifications.adapters.fake_adapter import AdaptadorCorreoPruebas
from app.modules.notifications.adapters.smtp_adapter import AdaptadorCorreoSMTP

_LOCALES = {"localhost", "127.0.0.1", "::1"}


def validar_url_acceso(url: str | None) -> str:
    """URL configurada del simulador: absoluta, http(s) y con host. HTTP solo hacia localhost."""
    if not url:
        raise ConfiguracionCorreoError("Defina SIMULATOR_ACCESS_URL antes de enviar convocatorias por correo.")
    partes = urlparse(url)
    if partes.scheme not in {"https", "http"} or not partes.hostname:
        raise ConfiguracionCorreoError("SIMULATOR_ACCESS_URL debe ser una URL absoluta http(s).")
    if partes.scheme == "http" and partes.hostname not in _LOCALES:
        raise ConfiguracionCorreoError("SIMULATOR_ACCESS_URL debe usar https fuera de localhost.")
    return url


def crear_servicio_correo(settings: Settings | None = None) -> ServicioCorreo | None:
    """Adaptador según la configuración; `None` si el envío está desactivado.

    Con el envío activado exige una configuración completa y segura, y falla de forma
    explícita (sin mostrar secretos) en lugar de intentar enviar con datos incompletos.
    """
    settings = settings or get_settings()
    if not settings.NOTIFICATIONS_EMAIL_ENABLED:
        return None
    faltan = [n for n in ("SMTP_HOST", "SMTP_FROM_EMAIL", "SIMULATOR_ACCESS_URL") if not getattr(settings, n)]
    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD is None:
        faltan.append("SMTP_PASSWORD")
    if faltan:
        raise ConfiguracionCorreoError(f"Configuración de correo incompleta: {', '.join(faltan)}.")
    try:
        validar_direccion(settings.SMTP_FROM_EMAIL)  # type: ignore[arg-type]
    except ErrorCorreo as exc:
        raise ConfiguracionCorreoError("SMTP_FROM_EMAIL no es una dirección válida.") from exc
    validar_url_acceso(settings.SIMULATOR_ACCESS_URL)
    cifrado = settings.SMTP_USE_SSL or settings.SMTP_USE_STARTTLS
    if not cifrado and settings.SMTP_HOST not in _LOCALES:
        raise ConfiguracionCorreoError("El envío sin TLS solo se admite hacia un servidor SMTP local.")
    if not cifrado and settings.SMTP_USERNAME:
        raise ConfiguracionCorreoError("No se envían credenciales SMTP sin TLS.")
    return AdaptadorCorreoSMTP(
        host=settings.SMTP_HOST,  # type: ignore[arg-type]
        puerto=settings.SMTP_PORT,
        remitente=settings.SMTP_FROM_EMAIL,  # type: ignore[arg-type]
        nombre_remitente=settings.SMTP_FROM_NAME,
        usuario=settings.SMTP_USERNAME,
        clave=settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD else None,
        starttls=settings.SMTP_USE_STARTTLS,
        ssl_implicito=settings.SMTP_USE_SSL,
        timeout=settings.SMTP_TIMEOUT_SECONDS,
    )


__all__ = [
    "AdaptadorCorreoPruebas",
    "AdaptadorCorreoSMTP",
    "ConfiguracionCorreoError",
    "ErrorCorreo",
    "ErrorCorreoPermanente",
    "ErrorCorreoTemporal",
    "MensajeCorreo",
    "MensajeInvalidoError",
    "ResultadoEnvio",
    "ServicioCorreo",
    "crear_servicio_correo",
    "validar_direccion",
    "validar_url_acceso",
]
