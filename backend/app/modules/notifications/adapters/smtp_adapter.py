"""Adaptador SMTP: traduce `MensajeCorreo` a `email.message.EmailMessage` y `smtplib`.

Es el único lugar del sistema que importa `smtplib`. Seguridad:

- TLS con `ssl.create_default_context()` (verifica certificado y nombre de host). No existe
  opción para desactivar la verificación.
- Sin cifrado solo hacia localhost (p. ej., Mailpit), validado en la fábrica.
- Tiempo máximo de conexión y de cada operación (`timeout`).
- Los errores se traducen a mensajes seguros: nunca incluyen la contraseña, el cuerpo ni la
  respuesta completa del servidor (que podría repetir datos del mensaje).
"""

import smtplib
import socket
import ssl
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate

from app.modules.notifications.adapters.base import (
    ErrorCorreoPermanente,
    ErrorCorreoTemporal,
    MensajeCorreo,
    ResultadoEnvio,
    ServicioCorreo,
)


class AdaptadorCorreoSMTP(ServicioCorreo):
    def __init__(
        self,
        *,
        host: str,
        puerto: int,
        remitente: str,
        nombre_remitente: str = "Inter Nos",
        usuario: str | None = None,
        clave: str | None = None,
        starttls: bool = True,
        ssl_implicito: bool = False,
        timeout: float = 10,
        contexto_tls: ssl.SSLContext | None = None,
        fabrica_smtp=None,
    ) -> None:
        self._host = host
        self._puerto = puerto
        self._remitente = remitente
        self._nombre_remitente = nombre_remitente
        self._usuario = usuario
        self._clave = clave
        self._starttls = starttls and not ssl_implicito
        self._ssl = ssl_implicito
        self._timeout = timeout
        self._contexto = contexto_tls or ssl.create_default_context()
        self._fabrica = fabrica_smtp  # inyectable en pruebas; por defecto smtplib

    def __repr__(self) -> str:  # nunca muestra la contraseña
        return f"<AdaptadorCorreoSMTP {self._host}:{self._puerto} tls={'ssl' if self._ssl else self._starttls}>"

    def construir(self, mensaje: MensajeCorreo) -> EmailMessage:
        """Adaptación del formato propio al formato MIME del proveedor."""
        correo = EmailMessage()
        usuario_dir, _, dominio = self._remitente.partition("@")
        correo["From"] = Address(self._nombre_remitente, usuario_dir, dominio)
        correo["To"] = mensaje.destinatario
        correo["Subject"] = mensaje.asunto
        correo["Date"] = formatdate(localtime=False)
        if mensaje.id_mensaje:
            correo["Message-ID"] = mensaje.id_mensaje
        for nombre, valor in mensaje.encabezados.items():
            correo[nombre] = valor
        correo.set_content(mensaje.texto)
        if mensaje.html:
            correo.add_alternative(mensaje.html, subtype="html")
        return correo

    def _conectar(self) -> smtplib.SMTP:
        if self._fabrica is not None:
            return self._fabrica(self._host, self._puerto, self._timeout, self._ssl, self._contexto)
        if self._ssl:
            return smtplib.SMTP_SSL(self._host, self._puerto, timeout=self._timeout, context=self._contexto)
        return smtplib.SMTP(self._host, self._puerto, timeout=self._timeout)

    def enviar(self, mensaje: MensajeCorreo) -> ResultadoEnvio:
        correo = self.construir(mensaje)
        try:
            with self._conectar() as smtp:
                if self._starttls:
                    smtp.starttls(context=self._contexto)
                if self._usuario:
                    smtp.login(self._usuario, self._clave or "")
                smtp.send_message(correo, from_addr=self._remitente, to_addrs=[mensaje.destinatario])
        except smtplib.SMTPAuthenticationError as exc:
            raise ErrorCorreoPermanente(f"SMTP rechazó la autenticación (código {exc.smtp_code}).") from None
        except smtplib.SMTPRecipientsRefused:
            raise ErrorCorreoPermanente("SMTP rechazó el destinatario.") from None
        except smtplib.SMTPResponseException as exc:
            # 5xx: rechazo definitivo; 4xx: fallo transitorio del servidor.
            tipo = ErrorCorreoPermanente if 500 <= exc.smtp_code < 600 else ErrorCorreoTemporal
            raise tipo(f"SMTP respondió con el código {exc.smtp_code}.") from None
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError) as exc:
            raise ErrorCorreoTemporal(f"No se pudo mantener la conexión SMTP ({type(exc).__name__}).") from None
        except ssl.SSLCertVerificationError:
            raise ErrorCorreoPermanente("El certificado TLS del servidor SMTP no es válido.") from None
        except (TimeoutError, socket.timeout):
            raise ErrorCorreoTemporal("Tiempo de espera agotado con el servidor SMTP.") from None
        except (OSError, smtplib.SMTPException) as exc:
            raise ErrorCorreoTemporal(f"Fallo de red o de protocolo SMTP ({type(exc).__name__}).") from None
        return ResultadoEnvio(mensaje.id_mensaje)
