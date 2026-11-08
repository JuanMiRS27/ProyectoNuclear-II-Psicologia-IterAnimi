"""Strategy (GoF): abstracción común de las estrategias de evaluación.

Cada estrategia concreta encapsula el TRATAMIENTO ACADÉMICO de una situación (participación
completa, incompleta o ausencia): qué situaciones admite, qué verificaciones exige, si la
nota se registra y qué se le comunica al estudiante. El algoritmo matemático de la rúbrica
no se repite en ellas: lo aporta `CalculadoraRubrica`, que reciben por composición.
"""

from abc import ABC, abstractmethod

from app.modules.evaluations.dominio import (
    CondicionAcademica,
    DesgloseRubrica,
    EstadoCalificacion,
    ResultadoEvaluacion,
    SituacionAcademica,
)
from app.modules.evaluations.services.calculadora_rubrica import CalculadoraRubrica


class EstrategiaEvaluacion(ABC):
    condicion: CondicionAcademica

    def __init__(self, calculadora: CalculadoraRubrica | None = None) -> None:
        self._calculadora = calculadora or CalculadoraRubrica()

    @property
    def nombre(self) -> str:
        return type(self).__name__

    @abstractmethod
    def aplica_a(self, situacion: SituacionAcademica) -> bool:
        """¿Es esta la estrategia adecuada para la situación?"""

    @abstractmethod
    def evaluar(self, situacion: SituacionAcademica) -> ResultadoEvaluacion:
        """Evalúa la situación. Nunca modifica la participación ni sus respuestas."""

    # --- Ayudas para las estrategias concretas -----------------------------------------------

    def _calcular(self, situacion: SituacionAcademica) -> DesgloseRubrica:
        return self._calculadora.calcular(situacion.rubrica, situacion.preguntas, situacion.respuestas)

    def _resultado(
        self,
        situacion: SituacionAcademica,
        *,
        desglose: DesgloseRubrica | None,
        calificada: bool,
        observaciones: list[str],
    ) -> ResultadoEvaluacion:
        return ResultadoEvaluacion(
            condicion=self.condicion,
            calificacion=EstadoCalificacion.CALIFICADA if calificada else EstadoCalificacion.SIN_CALIFICAR,
            estudiante_id=situacion.estudiante_id,
            convocatoria_id=situacion.convocatoria_id,
            nota=desglose.nota if (calificada and desglose is not None) else None,
            observaciones=tuple(observaciones),
            desglose=desglose,
            participacion_id=situacion.participacion_id,
            numero_intento=situacion.numero_intento,
            estado=situacion.estado,
            motivo_cierre=situacion.motivo_cierre,
            escala_max=situacion.rubrica.escala_max if situacion.rubrica is not None else None,
            estrategia=self.nombre,
        )
