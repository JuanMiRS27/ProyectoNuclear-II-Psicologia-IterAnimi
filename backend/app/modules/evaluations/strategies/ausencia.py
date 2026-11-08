"""Estrategia para ausencias: convocatoria activa SIN ningún intento.

No crea participaciones ni respuestas, no calcula una rúbrica sobre datos inexistentes y
no asigna un cero: la condición es AUSENCIA y la nota queda SIN_CALIFICAR (`None`). Así una
ausencia nunca se confunde con una participación con cero aciertos.
"""

from app.core.exceptions import ConflictError
from app.modules.evaluations.dominio import CondicionAcademica, ResultadoEvaluacion, SituacionAcademica
from app.modules.evaluations.strategies.base import EstrategiaEvaluacion


class EstrategiaEvaluacionAusencia(EstrategiaEvaluacion):
    condicion = CondicionAcademica.AUSENCIA

    def aplica_a(self, situacion: SituacionAcademica) -> bool:
        return situacion.participacion_id is None

    def evaluar(self, situacion: SituacionAcademica) -> ResultadoEvaluacion:
        if not self.aplica_a(situacion):
            raise ConflictError("Una participación existente no es una ausencia.")
        return self._resultado(
            situacion,
            desglose=None,
            calificada=False,
            observaciones=["El estudiante no inició ningún intento en esta convocatoria.", "Ausencia: sin calificar."],
        )
