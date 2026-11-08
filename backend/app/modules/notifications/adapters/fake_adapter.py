"""Adaptador de pruebas: captura los mensajes en memoria, sin red. Puede simular fallos."""

from collections import deque

from app.modules.notifications.adapters.base import ErrorCorreo, MensajeCorreo, ResultadoEnvio, ServicioCorreo


class AdaptadorCorreoPruebas(ServicioCorreo):
    def __init__(self) -> None:
        self.enviados: list[MensajeCorreo] = []
        self._fallos: deque[ErrorCorreo] = deque()

    def fallar_con(self, *errores: ErrorCorreo) -> None:
        """Los próximos envíos lanzan estos errores, en orden."""
        self._fallos.extend(errores)

    def enviar(self, mensaje: MensajeCorreo) -> ResultadoEnvio:
        if self._fallos:
            raise self._fallos.popleft()
        self.enviados.append(mensaje)
        return ResultadoEnvio(mensaje.id_mensaje)

    def para(self, destinatario: str) -> list[MensajeCorreo]:
        return [m for m in self.enviados if m.destinatario == destinatario.lower() or m.destinatario == destinatario]
