"""Estrategia para participaciones FINALIZADAS por el propio estudiante.

FINALIZADA no significa "todo respondido": el módulo 4 permite terminar voluntariamente con
preguntas pendientes. Se corrigen TODAS las preguntas del caso y las no respondidas cuentan
como no acertadas; como el cierre fue una decisión del estudiante, la nota siempre se
registra, aunque no haya respondido ninguna.
"""

from app.core.exceptions import ConflictError
from app.modules.evaluations.dominio import CondicionAcademica, ResultadoEvaluacion, SituacionAcademica
from app.modules.evaluations.strategies.base import EstrategiaEvaluacion
from app.modules.participations.models import EstadoParticipacionEnum, MotivoCierreEnum


class EstrategiaEvaluacionCompleta(EstrategiaEvaluacion):
    condicion = CondicionAcademica.COMPLETA

    def aplica_a(self, situacion: SituacionAcademica) -> bool:
        return situacion.participacion_id is not None and situacion.estado == EstadoParticipacionEnum.FINALIZADA

    def evaluar(self, situacion: SituacionAcademica) -> ResultadoEvaluacion:
        if not self.aplica_a(situacion) or situacion.motivo_cierre != MotivoCierreEnum.VOLUNTARIO:
            raise ConflictError("Solo se evalúan como completas las participaciones finalizadas voluntariamente.")

        desglose = self._calcular(situacion)
        observaciones = ["Participación finalizada por el estudiante."]
        if desglose.sin_responder:
            observaciones.append(
                f"Finalizó con {desglose.sin_responder} de {len(desglose.correcciones)} preguntas sin responder; "
                "se consideran no acertadas."
            )
        return self._resultado(situacion, desglose=desglose, calificada=True, observaciones=observaciones)
