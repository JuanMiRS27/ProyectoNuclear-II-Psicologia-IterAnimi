"""Modelo de dominio PURO del módulo 5 (sin SQLAlchemy ni FastAPI).

La calculadora y las estrategias trabajan con estas estructuras inmutables. Así se prueban
de forma aislada y su resultado depende solo de los datos recibidos (determinismo). El
paso desde las entidades ORM de los módulos 2 a 4 está en `services/mapeo.py`.

Toda magnitud académica es `Decimal`; nunca `float`.
"""

import enum
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.core.exceptions import UnprocessableEntityError
from app.modules.participations.models import EstadoParticipacionEnum, MotivoCierreEnum

CERO = Decimal("0")
CIEN = Decimal("100")
DOS_DECIMALES = Decimal("0.01")
# Redondeo final de la nota y de las cifras mostradas: medio hacia arriba (2.345 -> 2.35).
MODO_REDONDEO = ROUND_HALF_UP
# Máximo que admite `participacion.nota_final` (NUMERIC(4, 2)).
NOTA_MAXIMA_ALMACENABLE = Decimal("99.99")


def redondear(valor: Decimal) -> Decimal:
    return valor.quantize(DOS_DECIMALES, rounding=MODO_REDONDEO)


# --- Clasificaciones --------------------------------------------------------------------------


class CondicionAcademica(str, enum.Enum):
    COMPLETA = "COMPLETA"  # participación FINALIZADA por el estudiante
    INCOMPLETA = "INCOMPLETA"  # participación EXPIRADA (tiempo, revocación o fin de sesión)
    AUSENCIA = "AUSENCIA"  # convocatoria activa sin ninguna participación


class EstadoCalificacion(str, enum.Enum):
    CALIFICADA = "CALIFICADA"
    SIN_CALIFICAR = "SIN_CALIFICAR"


class ResultadoPregunta(str, enum.Enum):
    ACIERTO = "ACIERTO"
    ERROR = "ERROR"
    SIN_RESPUESTA = "SIN_RESPUESTA"


class PoliticaCriterio(str, enum.Enum):
    NIVELES = "NIVELES"  # todos los niveles tienen `min_aciertos_pct`: se elige un nivel
    LINEAL = "LINEAL"  # umbrales incompletos o ausentes: escala_max × porcentaje / 100
    SIN_EVIDENCIA = "SIN_EVIDENCIA"  # criterio sin preguntas: excluido del cálculo


# --- Errores ------------------------------------------------------------------------------------


class EvaluacionNoPosibleError(UnprocessableEntityError):
    """La configuración académica o los datos impiden calcular una nota coherente.

    Nunca se persiste una nota en este caso: la transacción completa se revierte.
    """

    default_detail = "La participación no se puede evaluar con la configuración académica actual."

    def __init__(self, codigo: str, detail: str) -> None:
        super().__init__(detail, extra={"codigo": codigo})
        self.codigo = codigo


# --- Entradas -------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Nivel:
    nombre: str
    valor: Decimal
    min_aciertos_pct: Decimal | None


@dataclass(frozen=True, slots=True)
class CriterioEvaluable:
    id: uuid.UUID
    descripcion: str
    peso: Decimal
    niveles: tuple[Nivel, ...]
    # Si los niveles almacenados no se pudieron interpretar (JSON con otra forma).
    niveles_invalidos: bool = False


@dataclass(frozen=True, slots=True)
class RubricaEvaluable:
    escala_max: Decimal
    criterios: tuple[CriterioEvaluable, ...]


@dataclass(frozen=True, slots=True)
class OpcionEvaluable:
    id: uuid.UUID
    texto: str
    es_correcta: bool
    justificacion: str | None


@dataclass(frozen=True, slots=True)
class PreguntaEvaluable:
    id: uuid.UUID
    enunciado: str
    criterio_id: uuid.UUID | None
    opciones: tuple[OpcionEvaluable, ...]
    escenario: str = ""


@dataclass(frozen=True, slots=True)
class SituacionAcademica:
    """Lo que la estrategia necesita saber de un estudiante convocado.

    `participacion_id is None` representa una ausencia: no existe ningún intento y no se
    inventa uno.
    """

    estudiante_id: uuid.UUID
    convocatoria_id: uuid.UUID
    sesion_id: uuid.UUID
    rubrica: RubricaEvaluable | None
    preguntas: tuple[PreguntaEvaluable, ...]
    participacion_id: uuid.UUID | None = None
    numero_intento: int | None = None
    estado: EstadoParticipacionEnum | None = None
    motivo_cierre: MotivoCierreEnum | None = None
    # pregunta_id -> opcion_id efectivamente guardada (nunca se completan respuestas)
    respuestas: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)


# --- Resultados ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CorreccionPregunta:
    pregunta_id: uuid.UUID
    criterio_id: uuid.UUID | None
    resultado: ResultadoPregunta
    opcion_elegida_id: uuid.UUID | None
    opciones_correctas: tuple[uuid.UUID, ...]

    @property
    def acertada(self) -> bool:
        return self.resultado == ResultadoPregunta.ACIERTO


@dataclass(frozen=True, slots=True)
class ResultadoCriterio:
    criterio_id: uuid.UUID
    descripcion: str
    peso: Decimal
    politica: PoliticaCriterio
    total_preguntas: int
    aciertos: int
    errores: int
    sin_responder: int
    # Valores EXACTOS (sin redondear); los esquemas de salida los presentan con dos decimales.
    porcentaje_aciertos: Decimal | None
    peso_efectivo: Decimal
    puntaje: Decimal | None
    aporte: Decimal
    nivel: str | None = None
    advertencia: str | None = None

    @property
    def evaluable(self) -> bool:
        return self.politica != PoliticaCriterio.SIN_EVIDENCIA


@dataclass(frozen=True, slots=True)
class DesgloseRubrica:
    escala_max: Decimal
    criterios: tuple[ResultadoCriterio, ...]
    correcciones: tuple[CorreccionPregunta, ...]
    nota_exacta: Decimal
    nota: Decimal  # redondeada a dos decimales (MODO_REDONDEO)

    @property
    def aciertos(self) -> int:
        return sum(1 for c in self.correcciones if c.resultado == ResultadoPregunta.ACIERTO)

    @property
    def errores(self) -> int:
        return sum(1 for c in self.correcciones if c.resultado == ResultadoPregunta.ERROR)

    @property
    def sin_responder(self) -> int:
        return sum(1 for c in self.correcciones if c.resultado == ResultadoPregunta.SIN_RESPUESTA)


@dataclass(frozen=True, slots=True)
class ResultadoEvaluacion:
    """Contrato común que devuelven TODAS las estrategias."""

    condicion: CondicionAcademica
    calificacion: EstadoCalificacion
    estudiante_id: uuid.UUID
    convocatoria_id: uuid.UUID
    nota: Decimal | None
    observaciones: tuple[str, ...]
    desglose: DesgloseRubrica | None = None
    participacion_id: uuid.UUID | None = None
    numero_intento: int | None = None
    estado: EstadoParticipacionEnum | None = None
    motivo_cierre: MotivoCierreEnum | None = None
    escala_max: Decimal | None = None
    estrategia: str = ""

    @property
    def calificada(self) -> bool:
        return self.calificacion == EstadoCalificacion.CALIFICADA
