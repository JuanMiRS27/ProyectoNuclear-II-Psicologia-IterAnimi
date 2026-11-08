"""Observer (GoF): contrato común de los observadores de eventos."""

from abc import ABC, abstractmethod

from app.modules.notifications.events import EventoDominio


class ObservadorEvento(ABC):
    """Recibe los eventos de los tipos que declara en `tipos`.

    `actualizar` se ejecuta dentro de la transacción del procesador de eventos: lo que el
    observador registra (notificaciones, entregas) se confirma junto con la marca de evento
    procesado, o no se confirma nada. Debe ser idempotente: reprocesar el mismo evento no
    produce efectos duplicados.
    """

    tipos: frozenset[str] = frozenset()

    @property
    def nombre(self) -> str:
        return type(self).__name__

    @abstractmethod
    def actualizar(self, evento: EventoDominio) -> None: ...
