"""Estrategia para participaciones EXPIRADAS (intento incompleto).

Reglas del módulo 5:

- Solo cuentan las respuestas efectivamente guardadas; no se agregan respuestas ni se toca
  la participación. Se aplica la MISMA rúbrica (calculadora común) que a una completa.
- No hay penalización adicional por la causa del cierre.
- La causa se conserva y se explica. TIEMPO_AGOTADO es el único cierre atribuible al
  estudiante (dispuso de todo su tiempo): el intento se califica aunque no tenga respuestas.
- CONVOCATORIA_REVOCADA y SESION_FINALIZADA son cierres ADMINISTRATIVOS: no se asume que el
  estudiante abandonó. Si guardó al menos una respuesta, se califica el rendimiento
  demostrado; si no guardó ninguna, no hay evidencia y el intento queda SIN_CALIFICAR (no
  se registra un cero que el estudiante no pudo evitar).
"""

from app.core.exceptions import ConflictError
from app.modules.evaluations.dominio import CondicionAcademica, ResultadoEvaluacion, SituacionAcademica
from app.modules.evaluations.strategies.base import EstrategiaEvaluacion
from app.modules.participations.models import EstadoParticipacionEnum, MotivoCierreEnum

EXPLICACION_CAUSA = {
    MotivoCierreEnum.TIEMPO_AGOTADO: "El intento se cerró al agotarse el tiempo máximo de participación.",
    MotivoCierreEnum.CONVOCATORIA_REVOCADA: "El intento se cerró porque el docente retiró la convocatoria.",
    MotivoCierreEnum.SESION_FINALIZADA: "El intento se cerró porque la sesión fue finalizada.",
}
CIERRES_ADMINISTRATIVOS = frozenset({MotivoCierreEnum.CONVOCATORIA_REVOCADA, MotivoCierreEnum.SESION_FINALIZADA})


class EstrategiaEvaluacionIncompleta(EstrategiaEvaluacion):
    condicion = CondicionAcademica.INCOMPLETA

    def aplica_a(self, situacion: SituacionAcademica) -> bool:
        return situacion.participacion_id is not None and situacion.estado == EstadoParticipacionEnum.EXPIRADA

    def evaluar(self, situacion: SituacionAcademica) -> ResultadoEvaluacion:
        if not self.aplica_a(situacion) or situacion.motivo_cierre not in EXPLICACION_CAUSA:
            raise ConflictError("Solo se evalúan como incompletas las participaciones expiradas con una causa de cierre válida.")

        desglose = self._calcular(situacion)
        guardadas = len(situacion.respuestas)
        observaciones = [
            "Intento incompleto.",
            EXPLICACION_CAUSA[situacion.motivo_cierre],  # type: ignore[index]
            f"Se evaluaron solo las {guardadas} respuestas guardadas antes del cierre, sin penalización adicional.",
        ]
        calificada = self.permite_calificar(situacion)
        if not calificada:
            observaciones.append(
                "No se guardó ninguna respuesta antes de un cierre administrativo: no hay evidencia evaluable y "
                "el intento queda sin calificar."
            )
        return self._resultado(situacion, desglose=desglose, calificada=calificada, observaciones=observaciones)

    @staticmethod
    def permite_calificar(situacion: SituacionAcademica) -> bool:
        return bool(situacion.respuestas) or situacion.motivo_cierre not in CIERRES_ADMINISTRATIVOS
