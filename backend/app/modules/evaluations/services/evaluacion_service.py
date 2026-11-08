"""Servicio de evaluación: coordina Strategy, persistencia y eventos.

- Toma los datos de `ConsultaEvaluacionService` (módulo 4), elige la estrategia con
  `SelectorEstrategia` y delega en `ContextoEvaluacion`.
- Solo escribe `participacion.nota_final` (y, a petición del docente,
  `retroalimentacion_general`). Respuestas, intento, fechas, estado y motivo nunca se tocan;
  los disparadores del módulo 4 lo garantizan también en la base de datos.
- Cada operación es UNA transacción: si cualquier participación no se puede evaluar, se
  revierte todo y no queda ninguna nota parcial.
- Es idempotente: con los mismos datos la nota es la misma y, si no cambia, no se escribe
  ni se publica ningún evento. Los eventos salen después del commit.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core import outbox
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.auth.models import Usuario
from app.modules.evaluations import eventos
from app.modules.evaluations.dominio import EvaluacionNoPosibleError, ResultadoEvaluacion, SituacionAcademica
from app.modules.evaluations.eventos import EventoEvaluacion, PublicadorEventosEvaluacion
from app.modules.evaluations.repositories import EvaluacionRepository
from app.modules.evaluations.services import mapeo
from app.modules.evaluations.strategies import ContextoEvaluacion, SelectorEstrategia
from app.modules.participations.models import EstadoParticipacionEnum, Participacion
from app.modules.participations.services import ConsultaEvaluacionService
from app.modules.sessions.models import EstadoSesionEnum, Sesion

SESION_NO_ENCONTRADA = "Sesión no encontrada."
PARTICIPACION_NO_ENCONTRADA = "Participación no encontrada."


@dataclass(frozen=True, slots=True)
class EvaluacionCalculada:
    """Resultado de la estrategia junto con los datos que lo produjeron (para la retroalimentación)."""

    situacion: SituacionAcademica
    resultado: ResultadoEvaluacion


@dataclass(slots=True)
class ResumenProceso:
    sesion_id: uuid.UUID
    registradas: int = 0
    actualizadas: int = 0
    sin_cambios: int = 0
    sin_calificar: int = 0
    en_progreso: int = 0
    ausencias: int = 0
    resultados: list[ResultadoEvaluacion] = field(default_factory=list)

    @property
    def procesadas(self) -> int:
        return len(self.resultados)


class EvaluacionService:
    def __init__(
        self,
        session: Session,
        eventos_publicador: PublicadorEventosEvaluacion | None = None,
        selector: SelectorEstrategia | None = None,
    ) -> None:
        self._session = session
        self._repo = EvaluacionRepository(session)
        self._consulta = ConsultaEvaluacionService(session)
        self._selector = selector or SelectorEstrategia()
        self._eventos = eventos_publicador or eventos.publicador()
        self._pendientes: list[EventoEvaluacion] = []

    # --- Evaluación (sin escribir) -----------------------------------------------------------

    def evaluar(self, participacion_id: uuid.UUID) -> EvaluacionCalculada:
        situacion = mapeo.situacion_de_participacion(self._consulta.obtener(participacion_id))
        return EvaluacionCalculada(situacion, ContextoEvaluacion.para(situacion, self._selector).evaluar(situacion))

    def evaluar_ausencias(self, sesion: Sesion) -> list[ResultadoEvaluacion]:
        """Reutiliza `ConsultaEvaluacionService.ausencias`: no cuenta convocatorias revocadas."""
        resultados = []
        for convocatoria in self._consulta.ausencias(sesion.id):
            situacion = mapeo.situacion_de_ausencia(convocatoria, sesion.id)
            resultados.append(ContextoEvaluacion.para(situacion, self._selector).evaluar(situacion))
        return resultados

    # --- Autorización ------------------------------------------------------------------------------

    def sesion_autorizada(self, sesion_id: uuid.UUID, docente: Usuario, *, bloquear: bool = False) -> Sesion:
        """Solo el docente responsable; una sesión ajena responde 404, igual que el módulo 3."""
        sesion = self._repo.sesion_del_docente(sesion_id, docente.id, bloquear=bloquear)
        if sesion is None:
            raise NotFoundError(SESION_NO_ENCONTRADA)
        return sesion

    def participacion_autorizada(self, participacion_id: uuid.UUID, docente: Usuario) -> tuple[Participacion, Sesion]:
        encontrada = self._repo.participacion_con_sesion(participacion_id)
        if encontrada is None or encontrada[1].docente_id != docente.id:
            raise NotFoundError(PARTICIPACION_NO_ENCONTRADA)
        return encontrada

    # --- Escritura -----------------------------------------------------------------------------------

    def procesar_sesion(self, sesion_id: uuid.UUID, docente: Usuario) -> ResumenProceso:
        """Evalúa TODAS las participaciones cerradas de la sesión en una sola transacción."""
        with self._transaction():
            sesion = self.sesion_autorizada(sesion_id, docente, bloquear=True)
            resumen = ResumenProceso(sesion.id)
            cambios = False
            for participacion in self._repo.bloquear_cerradas_de_sesion(sesion.id):
                resultado = self._evaluar_para_registro(participacion.id)
                cambios |= self._aplicar(participacion, resultado, sesion.id, resumen)
                resumen.resultados.append(resultado)
            resumen.en_progreso = sum(
                1 for p in self._repo.participaciones_de_sesion(sesion.id) if p.estado == EstadoParticipacionEnum.EN_PROGRESO
            )
            resumen.ausencias = len(self._consulta.ausencias(sesion.id))
            if cambios and sesion.estado == EstadoSesionEnum.FINALIZADO:
                self._pendientes.append(EventoEvaluacion(eventos.RESULTADOS_DISPONIBLES, sesion.id))
        return resumen

    def recalcular(self, participacion_id: uuid.UUID, docente: Usuario) -> EvaluacionCalculada:
        with self._transaction():
            participacion, sesion = self._bloquear_para_docente(participacion_id, docente)
            calculada = self.evaluar(participacion.id)
            self._aplicar(participacion, calculada.resultado, sesion.id, ResumenProceso(sesion.id))
        return calculada

    def actualizar_retroalimentacion(self, participacion_id: uuid.UUID, docente: Usuario, texto: str | None) -> Participacion:
        with self._transaction():
            participacion, sesion = self._bloquear_para_docente(participacion_id, docente)
            if participacion.retroalimentacion_general != texto:
                self._repo.registrar_retroalimentacion(participacion, texto)
                self._pendientes.append(
                    eventos.evento_participacion(
                        eventos.RETROALIMENTACION_REGISTRADA, sesion.id, participacion.id, participacion.convocatoria_id
                    )
                )
        return participacion

    # --- Internos ------------------------------------------------------------------------------------

    def _bloquear_para_docente(self, participacion_id: uuid.UUID, docente: Usuario) -> tuple[Participacion, Sesion]:
        _, sesion = self.participacion_autorizada(participacion_id, docente)
        sesion = self.sesion_autorizada(sesion.id, docente, bloquear=True)  # orden: sesión -> participación
        participacion = self._repo.bloquear_participacion(participacion_id)
        if participacion is None:
            raise NotFoundError(PARTICIPACION_NO_ENCONTRADA)
        if participacion.estado == EstadoParticipacionEnum.EN_PROGRESO:
            raise ConflictError("La participación sigue en progreso: solo se evalúan intentos cerrados.")
        return participacion, sesion

    def _evaluar_para_registro(self, participacion_id: uuid.UUID) -> ResultadoEvaluacion:
        try:
            return self.evaluar(participacion_id).resultado
        except EvaluacionNoPosibleError as exc:
            exc.extra["participacion_id"] = str(participacion_id)
            raise

    def _aplicar(self, participacion: Participacion, resultado: ResultadoEvaluacion, sesion_id: uuid.UUID, resumen: ResumenProceso) -> bool:
        nueva: Decimal | None = resultado.nota
        anterior = participacion.nota_final
        if not resultado.calificada:
            resumen.sin_calificar += 1
        if anterior == nueva:
            resumen.sin_cambios += 1
            return False
        self._repo.registrar_nota(participacion, nueva)
        if anterior is None:
            resumen.registradas += 1
            tipo = eventos.CALIFICACION_REGISTRADA
        else:
            resumen.actualizadas += 1
            tipo = eventos.CALIFICACION_ACTUALIZADA
        self._pendientes.append(eventos.evento_participacion(tipo, sesion_id, participacion.id, participacion.convocatoria_id))
        return True

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        try:
            yield
            # Módulo 6 (outbox): los eventos se guardan en ESTA transacción, junto con la nota.
            for evento in self._pendientes:
                outbox.registro().registrar(self._session, evento.tipo, evento.sesion_id, evento.datos)
            self._session.commit()
        except BaseException:
            self._session.rollback()
            self._pendientes.clear()
            raise
        pendientes, self._pendientes = self._pendientes, []
        for evento in pendientes:
            self._eventos.publicar(evento)
