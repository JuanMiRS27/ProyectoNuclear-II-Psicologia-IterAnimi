"""Observer (GoF): sujeto que registra observadores y les distribuye los eventos."""

from collections import defaultdict

from app.modules.notifications.events import EventoDominio
from app.modules.notifications.observers.base import ObservadorEvento


class PublicadorEventos:
    def __init__(self) -> None:
        self._observadores: dict[str, list[ObservadorEvento]] = defaultdict(list)

    def suscribir(self, observador: ObservadorEvento) -> None:
        """Suscribe el observador a todos los tipos que declara (sin duplicarlo)."""
        for tipo in observador.tipos:
            if observador not in self._observadores[tipo]:
                self._observadores[tipo].append(observador)

    def desuscribir(self, observador: ObservadorEvento) -> None:
        for lista in self._observadores.values():
            if observador in lista:
                lista.remove(observador)

    def observadores_de(self, tipo: str) -> list[ObservadorEvento]:
        return list(self._observadores.get(tipo, ()))

    def publicar(self, evento: EventoDominio) -> list[str]:
        """Notifica en orden de suscripción y devuelve quiénes lo recibieron.

        Un tipo sin observadores no es un error: el evento no requiere notificaciones. Si un
        observador falla, la excepción se propaga para que el procesador revierta TODO el
        evento y lo reintente (nada queda a medias).
        """
        receptores = self.observadores_de(evento.tipo)
        for observador in receptores:
            observador.actualizar(evento)
        return [o.nombre for o in receptores]
