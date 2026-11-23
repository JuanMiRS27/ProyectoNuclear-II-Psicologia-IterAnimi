import type {
  CondicionAcademica,
  CondicionConvocado,
  EstadoCalificacion,
  EstadoCaso,
  EstadoParticipacion,
  EstadoSesion,
  MotivoCierre,
  ResultadoPregunta,
  Rol,
  SituacionIntento,
} from '../types/api'

export const ROL: Record<Rol, string> = {
  ADMINISTRADOR: 'Administración',
  DOCENTE: 'Docente',
  ESTUDIANTE: 'Estudiante',
}

export const ESTADO_SESION: Record<EstadoSesion, string> = {
  SIN_INICIAR: 'Sin iniciar',
  EN_CURSO: 'En curso',
  FINALIZADO: 'Finalizada',
}

export const ESTADO_CASO: Record<EstadoCaso, string> = {
  BORRADOR: 'Borrador',
  PUBLICADO: 'Publicado',
  ARCHIVADO: 'Archivado',
}

export const ESTADO_PARTICIPACION: Record<EstadoParticipacion, string> = {
  EN_PROGRESO: 'En curso',
  FINALIZADA: 'Completado',
  EXPIRADA: 'Cerrado',
}

export const MOTIVO_CIERRE: Record<MotivoCierre, string> = {
  VOLUNTARIO: 'Finalizado por el estudiante',
  TIEMPO_AGOTADO: 'Se agotó el tiempo',
  CONVOCATORIA_REVOCADA: 'La convocatoria fue retirada',
  SESION_FINALIZADA: 'La sesión terminó',
}

export const CONDICION: Record<CondicionAcademica, string> = {
  COMPLETA: 'Completa',
  INCOMPLETA: 'Incompleta',
  AUSENCIA: 'Ausencia',
}

export const CALIFICACION: Record<EstadoCalificacion, string> = {
  CALIFICADA: 'Calificada',
  SIN_CALIFICAR: 'Sin calificar',
}

export const RESULTADO_PREGUNTA: Record<ResultadoPregunta, string> = {
  ACIERTO: 'Acierto',
  ERROR: 'Respuesta no acertada',
  SIN_RESPUESTA: 'Sin responder',
}

export const CONDICION_CONVOCADO: Record<CondicionConvocado, string> = {
  PARTICIPO: 'Participó',
  PENDIENTE: 'Pendiente',
  AUSENTE: 'Ausente',
  REVOCADA: 'Retirado',
}

export const SITUACION_INTENTO: Record<SituacionIntento, string> = {
  EN_PROGRESO: 'En curso',
  CALIFICADO: 'Calificado',
  SIN_CALIFICAR: 'Sin calificar',
  PENDIENTE_CALIFICACION: 'Por evaluar',
}

export const ESTADO_ENTREGA: Record<import('../types/api').EstadoEntrega, string> = {
  PENDIENTE: 'Pendiente',
  EN_PROCESO: 'Enviando',
  ENVIADA: 'Enviada',
  FALLIDA: 'Fallida',
  CANCELADA: 'Cancelada',
}

export const TIPO_NOTIFICACION: Record<import('../types/api').TipoNotificacion, string> = {
  CONVOCATORIA: 'Convocatoria',
  CODIGO_REGENERADO: 'Código regenerado',
  REPROGRAMACION: 'Cambio de programación',
  REVOCACION: 'Retiro de la convocatoria',
  RESULTADOS_DISPONIBLES: 'Resultados disponibles',
  CALIFICACION_ACTUALIZADA: 'Calificación actualizada',
  RETROALIMENTACION: 'Retroalimentación',
}
