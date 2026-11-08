"""Esquemas del módulo 7. Solo de SALIDA para docentes, salvo los filtros de consulta.

- Se construyen campo a campo (sin `from_attributes`): una serialización accidental no puede
  filtrar columnas como `codigo_autorizacion`, `clave_hash` o `version_token`, que ningún
  esquema declara.
- Los decimales se devuelven como texto con dos decimales ("3.40"), igual que el módulo 5.
- Una nota o un porcentaje sin datos es `null`, nunca 0.
- No hay esquemas para estudiantes: los reportes son docentes y no reemplazan a los
  resultados estudiantiles del módulo 5.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.database import OFFSET_MAXIMO
from app.modules.cases.models import EstadoCasoEnum
from app.modules.evaluations.dominio import CondicionAcademica
from app.modules.participations.models import EstadoParticipacionEnum, MotivoCierreEnum
from app.modules.reports.calculations import CondicionConvocado, SituacionIntento
from app.modules.sessions.models import EstadoSesionEnum

LIMITE_PAGINA = 100


def _a_utc(valor: datetime) -> datetime:
    try:
        return valor.astimezone(UTC)
    except OverflowError as exc:
        raise ValueError("La fecha está fuera del rango admitido.") from exc


Instante = Annotated[AwareDatetime, AfterValidator(_a_utc)]
Busqueda = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


# --- Filtros (entrada por query string) ------------------------------------------------------------


class _Filtros(BaseModel):
    # extra="forbid": un parámetro desconocido (p. ej., `docente_id`) responde 422 en lugar de ignorarse.
    model_config = ConfigDict(extra="forbid")


class Paginacion(_Filtros):
    skip: int = Field(0, ge=0, le=OFFSET_MAXIMO)
    limit: int = Field(20, ge=1, le=LIMITE_PAGINA)


class RangoFechas(_Filtros):
    desde: Instante | None = Field(None, description="Sesiones con `inicio >= desde` (con zona horaria; se normaliza a UTC).")
    hasta: Instante | None = Field(None, description="Sesiones con `inicio < hasta` (intervalo semiabierto).")

    @model_validator(mode="after")
    def _rango(self) -> "RangoFechas":
        if self.desde is not None and self.hasta is not None and self.desde >= self.hasta:
            raise ValueError("`desde` debe ser anterior a `hasta`.")
        return self


class FiltrosSesiones(RangoFechas):
    estado: EstadoSesionEnum | None = None
    espacio_academico_id: uuid.UUID | None = None
    caso_id: uuid.UUID | None = None
    skip: int = Field(0, ge=0, le=OFFSET_MAXIMO)
    limit: int = Field(20, ge=1, le=LIMITE_PAGINA)


class FiltrosSesionesEspacio(RangoFechas):
    estado: EstadoSesionEnum | None = None
    caso_id: uuid.UUID | None = None
    skip: int = Field(0, ge=0, le=OFFSET_MAXIMO)
    limit: int = Field(20, ge=1, le=LIMITE_PAGINA)


class FiltrosSesionesCaso(RangoFechas):
    estado: EstadoSesionEnum | None = None
    espacio_academico_id: uuid.UUID | None = None
    skip: int = Field(0, ge=0, le=OFFSET_MAXIMO)
    limit: int = Field(20, ge=1, le=LIMITE_PAGINA)


class FiltrosEstudiantes(_Filtros):
    convocatoria: Literal["activas", "revocadas", "todas"] = "todas"
    condicion: CondicionConvocado | None = None
    estado_participacion: EstadoParticipacionEnum | None = Field(None, description="Estudiantes con al menos un intento en ese estado.")
    con_nota: bool | None = Field(None, description="true: con al menos un intento calificado; false: sin ninguno.")
    intento_activo: bool | None = None
    buscar: Busqueda | None = Field(None, description="Coincidencia parcial en nombre, correo o código institucional.")
    skip: int = Field(0, ge=0, le=OFFSET_MAXIMO)
    limit: int = Field(20, ge=1, le=LIMITE_PAGINA)


TipoExportacionSesion = Literal["resumen", "estudiantes", "intentos", "criterios", "preguntas"]


class ExportacionSesion(_Filtros):
    tipo: TipoExportacionSesion = "resumen"
    formato: Literal["csv"] = "csv"
    # Mismos filtros que /reports/students (solo se aplican a tipo=estudiantes e intentos).
    convocatoria: Literal["activas", "revocadas", "todas"] = "todas"
    condicion: CondicionConvocado | None = None
    estado_participacion: EstadoParticipacionEnum | None = None
    con_nota: bool | None = None
    intento_activo: bool | None = None
    buscar: Busqueda | None = None


class ExportacionEspacio(RangoFechas):
    tipo: Literal["sesiones"] = "sesiones"
    formato: Literal["csv"] = "csv"
    estado: EstadoSesionEnum | None = None
    caso_id: uuid.UUID | None = None


# --- Piezas comunes ---------------------------------------------------------------------------------


class IndicadorRead(BaseModel):
    numerador: int
    denominador: int
    porcentaje: Decimal | None = Field(description="numerador × 100 / denominador; null si el denominador es 0.")


class ConvocatoriasRead(BaseModel):
    activas: int = Field(description="Convocatorias vigentes (estudiantes convocados vigentes).")
    revocadas: int
    activas_con_intento: int = Field(description="Estudiantes vigentes que iniciaron al menos un intento.")
    activas_sin_intento: int = Field(description="Estudiantes vigentes sin participaciones (PENDIENTES o AUSENTES).")
    revocadas_con_intento: int
    ausentes: int = Field(description="Ausencias del módulo 5; solo se declaran con la sesión FINALIZADA.")
    pendientes: int = Field(description="Sin intentos, con la sesión aún no finalizada: todavía no son ausencias.")


class IntentosRead(BaseModel):
    total: int = Field(description="Intentos registrados (participaciones), no estudiantes.")
    en_progreso: int
    finalizados: int
    expirados: int
    expirados_por_tiempo: int
    expirados_por_revocacion: int
    expirados_por_fin_de_sesion: int
    calificados: int = Field(description="Intentos con `nota_final` registrada.")
    pendientes_de_calificacion: int = Field(description="Cerrados que el módulo 5 calificaría, aún sin nota registrada.")
    sin_calificar: int = Field(description="Cerrados sin nota por la política del módulo 5 (no son un cero).")
    vencidos_sin_cerrar: int = Field(description="EN_PROGRESO con el tiempo agotado; se cerrarán como EXPIRADOS.")


class IndicadoresRead(BaseModel):
    tasa_participacion: IndicadorRead
    tasa_finalizacion: IndicadorRead
    tasa_expiracion: IndicadorRead
    tasa_calificacion: IndicadorRead


class TramoRead(BaseModel):
    desde: Decimal
    hasta: Decimal
    incluye_hasta: bool
    cantidad: int
    porcentaje: Decimal | None


class EstadisticasNotasRead(BaseModel):
    unidad: Literal["intento"] = Field("intento", description="Estadísticas por intento evaluado, no por estudiante.")
    evaluados: int
    escala_max: Decimal | None
    minimo: Decimal | None
    maximo: Decimal | None
    promedio: Decimal | None
    mediana: Decimal | None
    promedio_porcentaje_escala: Decimal | None
    distribucion: list[TramoRead]


class CasoRef(BaseModel):
    id: uuid.UUID
    nombre: str
    estado: EstadoCasoEnum


class EspacioRef(BaseModel):
    id: uuid.UUID
    nombre: str
    periodo: str


class DocenteRef(BaseModel):
    id: uuid.UUID
    nombre_completo: str


# --- Sesión ------------------------------------------------------------------------------------------


class SesionInfoRead(BaseModel):
    id: uuid.UUID
    caso: CasoRef
    espacio_academico: EspacioRef
    docente: DocenteRef
    inicio: datetime
    fin: datetime
    limite_ingreso: datetime
    estado: EstadoSesionEnum
    tiempo_max_min: int
    escala_max: Decimal | None


class ResumenSesionRead(BaseModel):
    generado_en: datetime = Field(description="Instante del reporte (UTC); refleja el estado de PostgreSQL en ese momento.")
    sesion: SesionInfoRead
    convocatorias: ConvocatoriasRead
    intentos: IntentosRead
    indicadores: IndicadoresRead


class IntentoBreveRead(BaseModel):
    participacion_id: uuid.UUID
    numero_intento: int
    estado: EstadoParticipacionEnum
    motivo_cierre: MotivoCierreEnum | None
    nota_final: Decimal | None
    situacion: SituacionIntento


class EstudianteReporteRead(BaseModel):
    estudiante_id: uuid.UUID
    nombre_completo: str
    correo: str
    codigo_institucional: str | None
    convocatoria_id: uuid.UUID
    convocatoria_activa: bool
    revocada_en: datetime | None
    intentos_autorizados: int
    intentos_utilizados: int
    intento_activo: bool
    intentos_calificados: int
    condicion: CondicionConvocado
    intentos: list[IntentoBreveRead]


class EstudiantesReporteList(BaseModel):
    sesion_id: uuid.UUID
    estado_sesion: EstadoSesionEnum
    items: list[EstudianteReporteRead]
    total: int
    skip: int
    limit: int


class IntentoDetalleRead(BaseModel):
    participacion_id: uuid.UUID
    numero_intento: int
    inicio: datetime
    fin: datetime | None
    duracion_segundos: int | None
    estado: EstadoParticipacionEnum
    motivo_cierre: MotivoCierreEnum | None
    condicion: CondicionAcademica | None = Field(description="COMPLETA (FINALIZADA) o INCOMPLETA (EXPIRADA), según el módulo 5.")
    preguntas_totales: int
    preguntas_respondidas: int
    preguntas_sin_responder: int
    aciertos: int | None = Field(description="null mientras el intento está EN_PROGRESO.")
    errores: int | None
    nota_final: Decimal | None
    escala_max: Decimal | None
    situacion: SituacionIntento


class DesempenoEstudianteRead(BaseModel):
    sesion_id: uuid.UUID
    estado_sesion: EstadoSesionEnum
    estudiante_id: uuid.UUID
    nombre_completo: str
    correo: str
    codigo_institucional: str | None
    convocatoria_id: uuid.UUID
    convocatoria_activa: bool
    intentos_autorizados: int
    condicion: CondicionConvocado
    intentos: list[IntentoDetalleRead] = Field(
        description="Todos los intentos, por número de intento. Cada uno conserva su nota: no se consolida (módulo 5)."
    )


class NotasPorEstadoRead(BaseModel):
    finalizados: EstadisticasNotasRead
    expirados: EstadisticasNotasRead


class NotasSesionRead(BaseModel):
    sesion_id: uuid.UUID
    estado_sesion: EstadoSesionEnum
    intentos_cerrados: int
    intentos_sin_nota: int = Field(description="Cerrados sin nota (pendientes + sin calificar); no se promedian.")
    estudiantes_con_nota: int = Field(description="Estudiantes con al menos un intento calificado.")
    estadisticas: EstadisticasNotasRead
    por_estado: NotasPorEstadoRead


class CriterioReporteRead(BaseModel):
    criterio_id: uuid.UUID
    descripcion: str
    peso: Decimal
    evaluable: bool
    total_preguntas: int
    intentos_considerados: int
    aciertos: int
    errores: int
    sin_responder: int
    porcentaje_aciertos: Decimal | None
    intentos_calificados: int
    puntaje_promedio: Decimal | None = Field(description="Promedio del puntaje del módulo 5 en los intentos calificados.")
    advertencia: str | None


class CriteriosReporteRead(BaseModel):
    escala_max: Decimal | None
    intentos_considerados: int = Field(description="Intentos cerrados (FINALIZADOS y EXPIRADOS).")
    preguntas_sin_criterio: int
    criterios: list[CriterioReporteRead]


class CriteriosSesionRead(CriteriosReporteRead):
    sesion_id: uuid.UUID


class PreguntaReporteRead(BaseModel):
    pregunta_id: uuid.UUID
    enunciado: str
    escenario: str
    orden_escenario: int
    orden: int
    criterio_id: uuid.UUID | None
    criterio: str | None
    intentos_considerados: int
    aciertos: int | None
    errores: int | None
    sin_responder: int
    porcentaje_aciertos: Decimal | None
    corregible: bool


class PreguntasSesionRead(BaseModel):
    sesion_id: uuid.UUID
    intentos_considerados: int
    preguntas: list[PreguntaReporteRead]


# --- Listados de sesiones, espacios y casos -------------------------------------------------------


class SesionResumenRead(BaseModel):
    id: uuid.UUID
    caso: CasoRef
    espacio_academico: EspacioRef
    inicio: datetime
    fin: datetime
    estado: EstadoSesionEnum
    convocatorias_activas: int
    convocatorias_revocadas: int
    estudiantes_con_intento: int
    intentos: int
    en_progreso: int
    finalizados: int
    expirados: int
    calificados: int
    tasa_participacion: IndicadorRead


class SesionesReporteList(BaseModel):
    items: list[SesionResumenRead]
    total: int
    skip: int
    limit: int


class SesionesPorEstadoRead(BaseModel):
    sin_iniciar: int
    en_curso: int
    finalizadas: int


class TotalesAcademicosRead(BaseModel):
    intentos: int
    en_progreso: int
    finalizados: int
    expirados: int
    evaluaciones_registradas: int


class CasoUtilizadoRead(BaseModel):
    id: uuid.UUID
    nombre: str
    estado: EstadoCasoEnum
    escala_max: Decimal | None
    sesiones: int
    evaluaciones_registradas: int
    promedio: Decimal | None = Field(description="Promedio de las notas de este caso, en su propia escala.")


class EspacioReporteRead(BaseModel):
    generado_en: datetime
    espacio_academico: EspacioRef
    activo: bool
    alcance: Literal["sesiones_del_docente"] = Field(
        "sesiones_del_docente", description="Solo se agregan las sesiones del docente autenticado."
    )
    sesiones_registradas: int
    sesiones_por_estado: SesionesPorEstadoRead
    totales: TotalesAcademicosRead
    promedio_porcentaje_escala: Decimal | None = Field(
        description="Promedio de las notas normalizadas (nota × 100 / escala de su rúbrica): comparable entre casos."
    )
    casos_utilizados: list[CasoUtilizadoRead]
    sesiones: SesionesReporteList


class CasoReporteRead(BaseModel):
    generado_en: datetime
    caso: CasoRef
    escala_max: Decimal | None
    alcance: Literal["sesiones_del_docente"] = "sesiones_del_docente"
    sesiones_registradas: int
    sesiones_por_estado: SesionesPorEstadoRead
    totales: TotalesAcademicosRead
    estadisticas: EstadisticasNotasRead
    criterios: CriteriosReporteRead
    sesiones: SesionesReporteList
