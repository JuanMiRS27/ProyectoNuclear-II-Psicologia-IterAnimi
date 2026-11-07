"""Adapter (GoF): contrato de correo independiente del proveedor.

Los servicios del módulo 6 solo conocen `ServicioCorreo` y `MensajeCorreo`. Cada adaptador
traduce ese contrato a un proveedor concreto (SMTP, captura en pruebas o, en el futuro, una
API HTTP) sin que cambien los servicios académicos ni el de notificaciones.

Los errores se clasifican en temporales (se reintenta) y permanentes (no tiene sentido
reintentar). Sus mensajes son seguros: nunca incluyen credenciales, códigos ni el cuerpo.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pydantic import TypeAdapter, ValidationError
from pydantic.networks import EmailStr

_CONTROL = re.compile(r"[\r\n\x00]")
_EMAIL = TypeAdapter(EmailStr)
LONGITUD_MAXIMA_ASUNTO = 200


class ErrorCorreo(Exception):
    """Error de envío con un mensaje apto para guardarse y mostrarse a un administrador."""

    temporal: bool = True

    def __init__(self, mensaje_seguro: str) -> None:
        super().__init__(mensaje_seguro)
        self.mensaje_seguro = mensaje_seguro


class ErrorCorreoTemporal(ErrorCorreo):
    temporal = True


class ErrorCorreoPermanente(ErrorCorreo):
    temporal = False


class ConfiguracionCorreoError(Exception):
    """Configuración incompleta o insegura al activar el envío real."""


class MensajeInvalidoError(ErrorCorreoPermanente):
    pass


def validar_direccion(direccion: str) -> str:
    if not isinstance(direccion, str) or _CONTROL.search(direccion):
        raise MensajeInvalidoError("Dirección de correo inválida.")
    try:
        return str(_EMAIL.validate_python(direccion.strip()))
    except ValidationError as exc:
        raise MensajeInvalidoError("Dirección de correo inválida.") from exc


@dataclass(frozen=True, slots=True)
class MensajeCorreo:
    """Mensaje en formato propio del sistema; los adaptadores lo traducen al proveedor.

    Valida al construirse: un único destinatario, sin saltos de línea en encabezados
    (impide la inyección de encabezados) y asunto acotado.
    """

    destinatario: str
    asunto: str
    texto: str
    html: str | None = None
    # Identificador estable de la entrega: el adaptador lo usa como Message-ID para que un
    # reenvío tras un fallo ambiguo pueda reconocerse como el mismo mensaje.
    id_mensaje: str | None = None
    encabezados: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "destinatario", validar_direccion(self.destinatario))
        if not self.asunto or _CONTROL.search(self.asunto) or len(self.asunto) > LONGITUD_MAXIMA_ASUNTO:
            raise MensajeInvalidoError("Asunto inválido.")
        if not self.texto:
            raise MensajeInvalidoError("El mensaje no tiene contenido.")
        for nombre, valor in self.encabezados.items():
            if _CONTROL.search(nombre) or _CONTROL.search(valor):
                raise MensajeInvalidoError("Encabezado inválido.")
        if self.id_mensaje is not None and _CONTROL.search(self.id_mensaje):
            raise MensajeInvalidoError("Identificador de mensaje inválido.")


@dataclass(frozen=True, slots=True)
class ResultadoEnvio:
    id_mensaje: str | None = None


class ServicioCorreo(ABC):
    """Interfaz objetivo (Target) del patrón Adapter."""

    @abstractmethod
    def enviar(self, mensaje: MensajeCorreo) -> ResultadoEnvio:
        """Envía el mensaje o lanza `ErrorCorreoTemporal` / `ErrorCorreoPermanente`."""
