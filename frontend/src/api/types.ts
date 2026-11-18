// Tipos de la API de Iter Animi (backend FastAPI, prefijo /api/v1).
// Nombres y campos tomados del OpenAPI del backend; los decimales llegan como texto ("3.40").

export type UUID = string
export type Decimal = string

export type Rol = 'ADMINISTRADOR' | 'DOCENTE' | 'ESTUDIANTE'
export type EstadoSesion = 'SIN_INICIAR' | 'EN_CURSO' | 'FINALIZADO'
export type EstadoCaso = 'BORRADOR' | 'PUBLICADO' | 'ARCHIVADO'
export type EstadoParticipacion = 'EN_PROGRESO' | 'FINALIZADA' | 'EXPIRADA'
export type MotivoCierre = 'VOLUNTARIO' | 'TIEMPO_AGOTADO' | 'CONVOCATORIA_REVOCADA' | 'SESION_FINALIZADA'
export type CondicionAcademica = 'COMPLETA' | 'INCOMPLETA' | 'AUSENCIA'
export type EstadoCalificacion = 'CALIFICADA' | 'SIN_CALIFICAR'
export type ResultadoPregunta = 'ACIERTO' | 'ERROR' | 'SIN_RESPUESTA'
export type PoliticaCriterio = 'NIVELES' | 'LINEAL' | 'SIN_EVIDENCIA'
export type CondicionConvocado = 'PARTICIPO' | 'PENDIENTE' | 'AUSENTE' | 'REVOCADA'
export type SituacionIntento = 'EN_PROGRESO' | 'CALIFICADO' | 'SIN_CALIFICAR' | 'PENDIENTE_CALIFICACION'

export interface Page<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

// --- Autenticación y usuarios ---

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface StudentTokenResponse extends TokenResponse {
  sesion_id: UUID
  convocatoria_id: UUID
}

export interface Usuario {
  id: UUID
  nombre_completo: string
  correo: string
  rol: Rol
  codigo_institucional: string | null
  puede_crear_casos: boolean
  activo: boolean
  creado_en: string
}

// --- Espacios académicos (aulas) ---

export interface Espacio {
  id: UUID
  nombre: string
  periodo: string
  activo: boolean
  creado_en: string
}

// --- Casos ---

export interface CasoResumen {
  id: UUID
  autor_id: UUID
  nombre: string
  tiempo_estimado_min: number | null
  estado: EstadoCaso
  creado_en: string
  actualizado_en: string
}

export interface OpcionRead {
  id: UUID
  pregunta_id: UUID
  orden: number
  texto: string
  es_correcta: boolean
  justificacion: string | null
}

export interface PreguntaRead {
  id: UUID
  escenario_id: UUID
  criterio_id: UUID | null
  orden: number
  enunciado: string
  opciones: OpcionRead[]
}

export interface EscenarioRead {
  id: UUID
  caso_id: UUID
  orden: number
  titulo: string
  contexto: string | null
  preguntas: PreguntaRead[]
}

export interface Nivel {
  nombre: string
  valor: Decimal
  min_aciertos_pct?: Decimal | null
}

export interface CriterioRead {
  id: UUID
  rubrica_id: UUID
  descripcion: string
  peso: Decimal
  niveles: Nivel[]
}

export interface RubricaRead {
  id: UUID
  caso_id: UUID
  escala_max: Decimal
  criterios: CriterioRead[]
}

export interface CasoDetalle extends CasoResumen {
  desarrollo_situacional: string | null
  historia: string | null
  escenarios: EscenarioRead[]
  rubrica: RubricaRead | null
}

export interface ErrorValidacion {
  codigo: string
  componente: string
  componente_id: UUID | null
  campo: string
  ruta: string
  mensaje: string
}

export interface ResultadoValidacion {
  valido: boolean
  errores: ErrorValidacion[]
}

// --- Sesiones y convocatorias ---

export interface Sesion {
  id: UUID
  caso_id: UUID
  espacio_academico_id: UUID
  docente_id: UUID
  inicio: string
  fin: string
  limite_ingreso: string
  tiempo_max_min: number
  lugar: string | null
  mensaje: string | null
  estado: EstadoSesion
  creada_en: string
  total_convocatorias: number
}

export interface SesionCreate {
  caso_id: UUID
  espacio_academico_id: UUID
  inicio: string
  fin: string
  tiempo_max_min: number
  lugar?: string | null
  mensaje?: string | null
  estudiantes: string[]
}

export type SesionUpdate = Partial<Omit<SesionCreate, 'estudiantes'>>

export interface Convocatoria {
  id: UUID
  sesion_id: UUID
  estudiante: {
    id: UUID
    nombre_completo: string
    correo: string
    codigo_institucional: string | null
  }
  intentos_autorizados: number
  creada_en: string
  activa: boolean
  revocada_en: string | null
}

export interface CodigoConvocatoria {
  convocatoria_id: UUID
  codigo_autorizacion: string
}

// --- Estudiante: sesión y participaciones ---

export interface AccesoEstudiantil {
  estudiante_id: UUID
  nombre_completo: string
  convocatoria_id: UUID
  intentos_autorizados: number
  puede_iniciar_participacion: boolean
  sesion: {
    id: UUID
    caso_nombre: string
    inicio: string
    fin: string
    limite_ingreso: string
    tiempo_max_min: number
    lugar: string | null
    mensaje: string | null
    estado: EstadoSesion
  }
}

export interface Progreso {
  total_preguntas: number
  respondidas: number
  pendientes: number
  porcentaje: number
}

export interface Participacion {
  id: UUID
  convocatoria_id: UUID
  sesion_id: UUID
  numero_intento: number
  estado: EstadoParticipacion
  motivo_cierre: MotivoCierre | null
  inicio: string
  fin: string | null
  fecha_limite: string
  tiempo_restante_segundos: number
  intentos_autorizados: number
  intentos_utilizados: number
  progreso: Progreso
}

export interface OpcionCuestionario {
  id: UUID
  orden: number
  texto: string
}

export interface PreguntaCuestionario {
  id: UUID
  orden: number
  enunciado: string
  opcion_seleccionada_id: UUID | null
  opciones: OpcionCuestionario[]
}

export interface EscenarioCuestionario {
  id: UUID
  orden: number
  titulo: string
  contexto: string | null
  preguntas: PreguntaCuestionario[]
}

export interface Cuestionario {
  participacion_id: UUID
  estado: EstadoParticipacion
  fecha_limite: string
  tiempo_restante_segundos: number
  caso: { nombre: string; desarrollo_situacional: string | null; historia: string | null }
  escenarios: EscenarioCuestionario[]
  progreso: Progreso
}

export interface RespuestaRead {
  pregunta_id: UUID
  opcion_id: UUID
  respondida_en: string
  actualizada_en: string
}

// --- Evaluación y resultados ---

export interface ResultadosTokenResponse extends StudentTokenResponse {
  alcance: string
}

export interface ResultadoCriterio {
  criterio_id: UUID
  descripcion: string
  peso: Decimal
  peso_efectivo: Decimal
  politica: PoliticaCriterio
  total_preguntas: number
  aciertos: number
  errores: number
  sin_responder: number
  porcentaje_aciertos: Decimal | null
  nivel: string | null
  puntaje: Decimal | null
  aporte: Decimal
  advertencia: string | null
}

export interface OpcionRetro {
  id: UUID
  texto: string
  justificacion: string | null
}

export interface RetroPregunta {
  pregunta_id: UUID
  escenario: string
  enunciado: string
  criterio_id: UUID | null
  criterio: string | null
  resultado: ResultadoPregunta
  opcion_elegida: OpcionRetro | null
  opciones_correctas: OpcionRetro[]
  mensaje: string
}

export interface Totales {
  total_preguntas: number
  aciertos: number
  errores: number
  sin_responder: number
}

export interface DetalleResultadoBase {
  participacion_id: UUID
  numero_intento: number
  estado: EstadoParticipacion
  motivo_cierre: MotivoCierre | null
  condicion: CondicionAcademica
  calificacion: EstadoCalificacion
  escala_max: Decimal | null
  nota_final: Decimal | null
  observaciones: string[]
  totales: Totales | null
  criterios: ResultadoCriterio[]
  preguntas: RetroPregunta[]
  retroalimentacion_automatica: string
  retroalimentacion_general: string | null
}

export interface EvaluacionDetalle extends DetalleResultadoBase {
  convocatoria_id: UUID
  estudiante_id: UUID
  estrategia: string
  nota_calculada: Decimal | null
  evaluacion_registrada: boolean
}

export interface ResultadoParticipacionResumen {
  participacion_id: UUID
  convocatoria_id: UUID
  estudiante_id: UUID
  estudiante_nombre: string
  estudiante_correo: string
  numero_intento: number
  estado: EstadoParticipacion
  motivo_cierre: MotivoCierre | null
  condicion: CondicionAcademica | null
  calificacion: EstadoCalificacion | null
  nota_final: Decimal | null
  evaluacion_registrada: boolean
  requiere_procesamiento: boolean
  tiene_retroalimentacion_docente: boolean
}

export interface Ausencia {
  convocatoria_id: UUID
  estudiante_id: UUID
  estudiante_nombre: string
  estudiante_correo: string
  condicion: CondicionAcademica
  calificacion: EstadoCalificacion
  nota_final: null
  observaciones: string[]
}

export interface ResultadosSesion {
  sesion_id: UUID
  estado_sesion: EstadoSesion
  escala_max: Decimal | null
  resumen: {
    finalizadas: number
    expiradas: number
    en_progreso: number
    ausencias: number
    evaluadas: number
    pendientes: number
  }
  participaciones: ResultadoParticipacionResumen[]
  ausencias: Ausencia[]
}

export interface ProcesoEvaluacion {
  sesion_id: UUID
  procesadas: number
  registradas: number
  actualizadas: number
  sin_cambios: number
  sin_calificar: number
  en_progreso_omitidas: number
  ausencias: number
}

export interface ResultadoEstudianteResumen {
  participacion_id: UUID
  numero_intento: number
  estado: EstadoParticipacion
  motivo_cierre: MotivoCierre | null
  condicion: CondicionAcademica
  calificacion: EstadoCalificacion | null
  nota_final: Decimal | null
  escala_max: Decimal | null
  disponible: boolean
}

export interface ResultadosEstudiante {
  sesion_id: UUID
  caso_nombre: string
  convocatoria_id: UUID
  resultados: ResultadoEstudianteResumen[]
}

export type ResultadoEstudianteDetalle = DetalleResultadoBase

// --- Notificaciones ---

export interface Notificacion {
  id: UUID
  tipo: string
  titulo: string
  mensaje: string
  creada_en: string
  leida: boolean
  leida_en: string | null
}

// --- Reportes (módulo 7) ---

export interface Indicador {
  numerador: number
  denominador: number
  porcentaje: Decimal | null
}

export interface CasoRef {
  id: UUID
  nombre: string
  estado: EstadoCaso
}

export interface EspacioRef {
  id: UUID
  nombre: string
  periodo: string
}

export interface SesionResumenReporte {
  id: UUID
  caso: CasoRef
  espacio_academico: EspacioRef
  inicio: string
  fin: string
  estado: EstadoSesion
  convocatorias_activas: number
  convocatorias_revocadas: number
  estudiantes_con_intento: number
  intentos: number
  en_progreso: number
  finalizados: number
  expirados: number
  calificados: number
  tasa_participacion: Indicador
}

export interface ResumenSesionReporte {
  generado_en: string
  sesion: {
    id: UUID
    caso: CasoRef
    espacio_academico: EspacioRef
    docente: { id: UUID; nombre_completo: string }
    inicio: string
    fin: string
    limite_ingreso: string
    estado: EstadoSesion
    tiempo_max_min: number
    escala_max: Decimal | null
  }
  convocatorias: {
    activas: number
    revocadas: number
    activas_con_intento: number
    activas_sin_intento: number
    revocadas_con_intento: number
    ausentes: number
    pendientes: number
  }
  intentos: {
    total: number
    en_progreso: number
    finalizados: number
    expirados: number
    expirados_por_tiempo: number
    expirados_por_revocacion: number
    expirados_por_fin_de_sesion: number
    calificados: number
    pendientes_de_calificacion: number
    sin_calificar: number
    vencidos_sin_cerrar: number
  }
  indicadores: {
    tasa_participacion: Indicador
    tasa_finalizacion: Indicador
    tasa_expiracion: Indicador
    tasa_calificacion: Indicador
  }
}

export interface EstudianteReporte {
  estudiante_id: UUID
  nombre_completo: string
  correo: string
  codigo_institucional: string | null
  convocatoria_id: UUID
  convocatoria_activa: boolean
  revocada_en: string | null
  intentos_autorizados: number
  intentos_utilizados: number
  intento_activo: boolean
  intentos_calificados: number
  condicion: CondicionConvocado
  intentos: {
    participacion_id: UUID
    numero_intento: number
    estado: EstadoParticipacion
    motivo_cierre: MotivoCierre | null
    nota_final: Decimal | null
    situacion: SituacionIntento
  }[]
}

export interface EstudiantesReporte extends Page<EstudianteReporte> {
  sesion_id: UUID
  estado_sesion: EstadoSesion
}

export interface EstadisticasNotas {
  evaluados: number
  escala_max: Decimal | null
  minimo: Decimal | null
  maximo: Decimal | null
  promedio: Decimal | null
  mediana: Decimal | null
  promedio_porcentaje_escala: Decimal | null
  distribucion: { desde: Decimal; hasta: Decimal; incluye_hasta: boolean; cantidad: number; porcentaje: Decimal | null }[]
}

export interface NotasSesion {
  sesion_id: UUID
  estado_sesion: EstadoSesion
  intentos_cerrados: number
  intentos_sin_nota: number
  estudiantes_con_nota: number
  estadisticas: EstadisticasNotas
}

export interface CriteriosSesion {
  sesion_id: UUID
  escala_max: Decimal | null
  intentos_considerados: number
  preguntas_sin_criterio: number
  criterios: {
    criterio_id: UUID
    descripcion: string
    peso: Decimal
    evaluable: boolean
    total_preguntas: number
    intentos_considerados: number
    aciertos: number
    errores: number
    sin_responder: number
    porcentaje_aciertos: Decimal | null
    intentos_calificados: number
    puntaje_promedio: Decimal | null
    advertencia: string | null
  }[]
}

export interface PreguntasSesion {
  sesion_id: UUID
  intentos_considerados: number
  preguntas: {
    pregunta_id: UUID
    enunciado: string
    escenario: string
    orden_escenario: number
    orden: number
    criterio: string | null
    intentos_considerados: number
    aciertos: number | null
    errores: number | null
    sin_responder: number
    porcentaje_aciertos: Decimal | null
    corregible: boolean
  }[]
}

export interface EspacioReporte {
  generado_en: string
  espacio_academico: EspacioRef
  activo: boolean
  sesiones_registradas: number
  sesiones_por_estado: { sin_iniciar: number; en_curso: number; finalizadas: number }
  totales: {
    intentos: number
    en_progreso: number
    finalizados: number
    expirados: number
    evaluaciones_registradas: number
  }
  promedio_porcentaje_escala: Decimal | null
  casos_utilizados: {
    id: UUID
    nombre: string
    estado: EstadoCaso
    escala_max: Decimal | null
    sesiones: number
    evaluaciones_registradas: number
    promedio: Decimal | null
  }[]
  sesiones: Page<SesionResumenReporte>
}
