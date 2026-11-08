"""Contexto del patrón Strategy y selección explícita de la estrategia.

`ContextoEvaluacion` mantiene una referencia a una `EstrategiaEvaluacion` intercambiable y
delega en ella. `SelectorEstrategia` decide cuál corresponde a cada situación académica:

    situación sin participación  -> EstrategiaEvaluacionAusencia
    participación FINALIZADA     -> EstrategiaEvaluacionCompleta
    participación EXPIRADA       -> EstrategiaEvaluacionIncompleta
    participación EN_PROGRESO    -> ninguna (409: aún no se puede evaluar)
"""

from collections.abc import Sequence

from app.core.exceptions import ConflictError
from app.modules.evaluations.dominio import ResultadoEvaluacion, SituacionAcademica
from app.modules.evaluations.services.calculadora_rubrica import CalculadoraRubrica
from app.modules.evaluations.strategies.ausencia import EstrategiaEvaluacionAusencia
from app.modules.evaluations.strategies.base import EstrategiaEvaluacion
from app.modules.evaluations.strategies.completa import EstrategiaEvaluacionCompleta
from app.modules.evaluations.strategies.incompleta import EstrategiaEvaluacionIncompleta

PARTICIPACION_NO_EVALUABLE = "La participación sigue en progreso: solo se evalúan intentos cerrados."


class SelectorEstrategia:
    def __init__(self, estrategias: Sequence[EstrategiaEvaluacion] | None = None) -> None:
        if estrategias is None:
            calculadora = CalculadoraRubrica()  # una sola instancia compartida por las tres
            estrategias = (
                EstrategiaEvaluacionAusencia(calculadora),
                EstrategiaEvaluacionCompleta(calculadora),
                EstrategiaEvaluacionIncompleta(calculadora),
            )
        self._estrategias = tuple(estrategias)

    def seleccionar(self, situacion: SituacionAcademica) -> EstrategiaEvaluacion:
        candidatas = [e for e in self._estrategias if e.aplica_a(situacion)]
        if not candidatas:
            raise ConflictError(PARTICIPACION_NO_EVALUABLE)
        if len(candidatas) > 1:  # configuración ambigua: nunca se elige al azar
            raise RuntimeError("Más de una estrategia de evaluación aplica a la misma situación.")
        return candidatas[0]


class ContextoEvaluacion:
    def __init__(self, estrategia: EstrategiaEvaluacion) -> None:
        self._estrategia = estrategia

    @property
    def estrategia(self) -> EstrategiaEvaluacion:
        return self._estrategia

    def cambiar_estrategia(self, estrategia: EstrategiaEvaluacion) -> None:
        self._estrategia = estrategia

    def evaluar(self, situacion: SituacionAcademica) -> ResultadoEvaluacion:
        return self._estrategia.evaluar(situacion)

    @classmethod
    def para(cls, situacion: SituacionAcademica, selector: SelectorEstrategia | None = None) -> "ContextoEvaluacion":
        return cls((selector or SelectorEstrategia()).seleccionar(situacion))
