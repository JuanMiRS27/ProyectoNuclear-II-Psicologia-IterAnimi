"""Puerto del Transactional Outbox (módulo 6), sin dependencias entre módulos.

Los servicios académicos (módulos 3 y 5) registran sus eventos con `registro().registrar(...)`
DENTRO de la misma transacción que la operación académica, justo antes del commit: o se
confirman ambos o ninguno. Un worker los procesa después; el envío de correo nunca forma
parte de la transacción académica, así que un SMTP caído no hace fallar una convocatoria.

Por defecto no se registra nada. El módulo 6 conecta su implementación desde
`app/bootstrap.py`, igual que los demás puertos de integración.

Los `datos` solo llevan identificadores y textos no sensibles: nunca códigos de
autorización, contraseñas, tokens ni notas.
"""

import uuid
from collections.abc import Mapping
from typing import Protocol

from sqlalchemy.orm import Session


class RegistroEventos(Protocol):
    def registrar(self, db: Session, tipo: str, sesion_id: uuid.UUID, datos: Mapping[str, str]) -> None: ...


class _SinRegistro:
    def registrar(self, db: Session, tipo: str, sesion_id: uuid.UUID, datos: Mapping[str, str]) -> None:
        return None


_registro: RegistroEventos = _SinRegistro()


def configurar(registro: RegistroEventos) -> None:
    global _registro
    _registro = registro


def registro() -> RegistroEventos:
    return _registro
