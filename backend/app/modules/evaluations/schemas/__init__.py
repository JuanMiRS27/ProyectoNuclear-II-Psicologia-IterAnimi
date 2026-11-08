"""Esquemas del módulo 5.

Los decimales se devuelven como texto con dos decimales ("3.40"), como en el módulo 2. Los
esquemas se construyen campo a campo (sin `from_attributes`): una serialización accidental
no puede filtrar datos que el destinatario no debe ver.

Ningún esquema de ENTRADA acepta `nota_final`: la nota la calcula siempre el servidor.
"""

import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.modules.evaluations.dominio import (
    CondicionAcademica,
    EstadoCalificacion,
    PoliticaCriterio,
    ResultadoPregunta,
)
from app.modules.participations.models import EstadoParticipacionEnum, MotivoCierreEnum
from app.modules.sessions.models import EstadoSesionEnum
from app.modules.sessions.schemas import StudentLoginRequest


def _vacio_a_none(valor: str | None) -> str | None:
    return valor or None


TextoRetroalimentacion = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000), AfterValidator(_vacio_a_none)]


# --- Entrada ------------------------------------------------------------------------------------


class RetroalimentacionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retroalimentacion_general: TextoRetroalimentacion | None = Field(
        description="Texto del docente. Vacío o null la elimina. No modifica la nota ni las justificaciones."
    )


class ResultadosLoginRequest(StudentLoginRequest):
    """Mismas credenciales que el ingreso a la resolución: correo institucional y código de convocatoria."""


# --- Salida: piezas comunes -----------------------------------------------------------------------


class ResultadosTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    alcance: str = "resultados:lectura"
    sesion_id: uuid.UUID
    convocatoria_id: uuid.UUID


class ResultadoCriterioRead(BaseModel):
    criterio_id: uuid.UUID
    descripcion: str
    peso: Decimal
    peso_efectivo: Decimal
    politica: PoliticaCriterio
    total_preguntas: int
    aciertos: int
    errores: int
    sin_responder: int
    porcentaje_aciertos: Decimal | None
    nivel: str | None
    puntaje: Decimal | None
    aporte: Decimal
    advertencia: str | None


class OpcionRetroRead(BaseModel):
    id: uuid.UUID
    texto: str
    justificacion: str | None


class RetroPreguntaRead(BaseModel):
    pregunta_id: uuid.UUID
    escenario: str
    enunciado: str
    criterio_id: uuid.UUID | None
    criterio: str | None
    resultado: ResultadoPregunta
    opcion_elegida: OpcionRetroRead | None
    opciones_correctas: list[OpcionRetroRead]
    mensaje: str


class TotalesRead(BaseModel):
    total_preguntas: int
    aciertos: int
    errores: int
    sin_responder: int


class EvaluacionDetalleRead(BaseModel):
    """Evaluación completa de un intento: nota, desglose y retroalimentación."""

    participacion_id: uuid.UUID
    convocatoria_id: uuid.UUID
    estudiante_id: uuid.UUID
    numero_intento: int
    estado: EstadoParticipacionEnum
    motivo_cierre: MotivoCierreEnum | None
    condicion: CondicionAcademica
    estrategia: str
    calificacion: EstadoCalificacion
    escala_max: Decimal | None
    nota_final: Decimal | None = Field(description="Nota REGISTRADA en la participación.")
    nota_calculada: Decimal | None = Field(description="Nota que produce hoy la política vigente con los mismos datos.")
    evaluacion_registrada: bool
    observaciones: list[str]
    totales: TotalesRead | None
    criterios: list[ResultadoCriterioRead]
    preguntas: list[RetroPreguntaRead]
    retroalimentacion_automatica: str
    retroalimentacion_general: str | None = Field(description="Texto escrito por el docente responsable.")


class ResultadoParticipacionResumen(BaseModel):
    participacion_id: uuid.UUID
    convocatoria_id: uuid.UUID
    estudiante_id: uuid.UUID
    estudiante_nombre: str
    estudiante_correo: str
    numero_intento: int
    estado: EstadoParticipacionEnum
    motivo_cierre: MotivoCierreEnum | None
    condicion: CondicionAcademica | None = Field(description="None mientras la participación siga EN_PROGRESO.")
    calificacion: EstadoCalificacion | None
    nota_final: Decimal | None
    evaluacion_registrada: bool
    requiere_procesamiento: bool = Field(description="La nota registrada no coincide con la que se calcularía hoy.")
    tiene_retroalimentacion_docente: bool


class AusenciaRead(BaseModel):
    convocatoria_id: uuid.UUID
    estudiante_id: uuid.UUID
    estudiante_nombre: str
    estudiante_correo: str
    condicion: CondicionAcademica = CondicionAcademica.AUSENCIA
    calificacion: EstadoCalificacion = EstadoCalificacion.SIN_CALIFICAR
    nota_final: None = None
    observaciones: list[str]


class ResumenSesionRead(BaseModel):
    finalizadas: int
    expiradas: int
    en_progreso: int
    ausencias: int
    evaluadas: int
    pendientes: int


class ResultadosSesionRead(BaseModel):
    sesion_id: uuid.UUID
    estado_sesion: EstadoSesionEnum
    escala_max: Decimal | None
    resumen: ResumenSesionRead
    participaciones: list[ResultadoParticipacionResumen] = Field(description="Todos los intentos; no se elige una nota definitiva.")
    ausencias: list[AusenciaRead]


class ResultadoProcesoRead(BaseModel):
    participacion_id: uuid.UUID
    condicion: CondicionAcademica
    calificacion: EstadoCalificacion
    nota_final: Decimal | None


class ProcesoEvaluacionRead(BaseModel):
    sesion_id: uuid.UUID
    procesadas: int
    registradas: int
    actualizadas: int
    sin_cambios: int
    sin_calificar: int
    en_progreso_omitidas: int
    ausencias: int
    resultados: list[ResultadoProcesoRead]


class RetroalimentacionRead(BaseModel):
    participacion_id: uuid.UUID
    retroalimentacion_general: str | None


# --- Salida: estudiante ---------------------------------------------------------------------------


class ResultadoEstudianteResumen(BaseModel):
    participacion_id: uuid.UUID
    numero_intento: int
    estado: EstadoParticipacionEnum
    motivo_cierre: MotivoCierreEnum | None
    condicion: CondicionAcademica
    calificacion: EstadoCalificacion | None = Field(description="None mientras la evaluación esté pendiente.")
    nota_final: Decimal | None
    escala_max: Decimal | None
    disponible: bool = Field(description="True si ya se puede consultar el detalle con la retroalimentación.")


class ResultadosEstudianteRead(BaseModel):
    sesion_id: uuid.UUID
    caso_nombre: str
    convocatoria_id: uuid.UUID
    resultados: list[ResultadoEstudianteResumen]


class ResultadoEstudianteDetalle(BaseModel):
    participacion_id: uuid.UUID
    numero_intento: int
    estado: EstadoParticipacionEnum
    motivo_cierre: MotivoCierreEnum | None
    condicion: CondicionAcademica
    calificacion: EstadoCalificacion
    escala_max: Decimal | None
    nota_final: Decimal | None
    observaciones: list[str]
    totales: TotalesRead | None
    criterios: list[ResultadoCriterioRead]
    preguntas: list[RetroPreguntaRead]
    retroalimentacion_automatica: str
    retroalimentacion_general: str | None
