// Estudiante (CU16, CU18–CU21, CU25). El token cubre UNA convocatoria: nada aquí lee otras sesiones.
import type {
  AccesoEstudiantil,
  Cuestionario,
  Participacion,
  RespuestaRead,
  ResultadoEstudianteDetalle,
  ResultadosEstudiante,
  UUID,
} from '../types/api'
import { request } from './http-client'

const enc = encodeURIComponent

export const studentService = {
  // Token "student" (sesión EN_CURSO)
  session: (sessionId: UUID) => request<AccesoEstudiantil>(`/student/sessions/${enc(sessionId)}`),
  startOrResume: (sessionId: UUID) => request<Participacion>(`/student/sessions/${enc(sessionId)}/participations`, { method: 'POST' }),
  attempts: () => request<Participacion[]>('/student/participations'),
  attempt: (id: UUID) => request<Participacion>(`/student/participations/${enc(id)}`),
  questionnaire: (id: UUID) => request<Cuestionario>(`/student/participations/${enc(id)}/questionnaire`),
  saveAnswer: (id: UUID, questionId: UUID, opcion_id: UUID) =>
    request<RespuestaRead>(`/student/participations/${enc(id)}/answers/${enc(questionId)}`, { method: 'PUT', body: { opcion_id } }),
  finish: (id: UUID) => request<Participacion>(`/student/participations/${enc(id)}/finish`, { method: 'POST' }),

  // Token "student_results" (sesión FINALIZADO, solo lectura)
  results: () => request<ResultadosEstudiante>('/student/results'),
  result: (participationId: UUID) => request<ResultadoEstudianteDetalle>(`/student/results/${enc(participationId)}`),
} as const
