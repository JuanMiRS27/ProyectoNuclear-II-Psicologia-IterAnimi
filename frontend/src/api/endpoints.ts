// Operaciones de la API agrupadas por dominio. Solo rutas que existen en el backend.
import { download, request } from './client'
import type {
  AccesoEstudiantil,
  Ausencia,
  CasoDetalle,
  CasoResumen,
  CodigoConvocatoria,
  Convocatoria,
  CriteriosSesion,
  Cuestionario,
  Espacio,
  EspacioReporte,
  EstadoCaso,
  EstadoSesion,
  EstudiantesReporte,
  EvaluacionDetalle,
  NotasSesion,
  Notificacion,
  Page,
  Participacion,
  PreguntasSesion,
  ProcesoEvaluacion,
  ResultadoEstudianteDetalle,
  ResultadosEstudiante,
  ResultadosSesion,
  ResultadosTokenResponse,
  ResultadoValidacion,
  RespuestaRead,
  ResumenSesionReporte,
  Rol,
  Sesion,
  SesionCreate,
  SesionResumenReporte,
  SesionUpdate,
  StudentTokenResponse,
  TokenResponse,
  Usuario,
  UUID,
} from './types'

const enc = encodeURIComponent

export const authApi = {
  login: (correo: string, clave: string) =>
    request<TokenResponse>('/auth/login', { method: 'POST', body: { correo, clave }, token: null, skipAuthHandler: true }),
  me: (token?: string) => request<Usuario>('/auth/me', token ? { token, skipAuthHandler: true } : {}),
  studentLogin: (correo: string, codigo: string) =>
    request<StudentTokenResponse>('/auth/student/login', {
      method: 'POST',
      body: { correo, codigo },
      token: null,
      skipAuthHandler: true,
    }),
  resultsLogin: (correo: string, codigo: string) =>
    request<ResultadosTokenResponse>('/auth/student/results-login', {
      method: 'POST',
      body: { correo, codigo },
      token: null,
      skipAuthHandler: true,
    }),
  changePassword: (clave_actual: string, clave_nueva: string) =>
    request<void>('/auth/password', { method: 'PATCH', body: { clave_actual, clave_nueva } }),
}

export const usersApi = {
  list: (q: { rol?: Rol; activo?: boolean; skip?: number; limit?: number }) => request<Page<Usuario>>('/users', { query: q }),
  createTeacher: (data: { nombre_completo: string; correo: string; clave: string; codigo_institucional?: string | null }) =>
    request<Usuario>('/users/teachers', { method: 'POST', body: data }),
  createStudent: (data: { nombre_completo: string; correo: string; codigo_institucional?: string | null }) =>
    request<Usuario>('/users/students', { method: 'POST', body: data }),
  setStatus: (id: UUID, activo: boolean) => request<Usuario>(`/users/${enc(id)}/status`, { method: 'PATCH', body: { activo } }),
  setCasePermission: (id: UUID, puede_crear_casos: boolean) =>
    request<Usuario>(`/users/${enc(id)}/case-permission`, { method: 'PATCH', body: { puede_crear_casos } }),
}

export const spacesApi = {
  list: (q: { activo?: boolean; skip?: number; limit?: number } = {}) =>
    request<Page<Espacio>>('/academic-spaces', { query: { limit: 100, ...q } }),
  get: (id: UUID) => request<Espacio>(`/academic-spaces/${enc(id)}`),
  create: (data: { nombre: string; periodo: string }) => request<Espacio>('/academic-spaces', { method: 'POST', body: data }),
  update: (id: UUID, data: { nombre?: string; periodo?: string }) =>
    request<Espacio>(`/academic-spaces/${enc(id)}`, { method: 'PATCH', body: data }),
  setStatus: (id: UUID, activo: boolean) =>
    request<Espacio>(`/academic-spaces/${enc(id)}/status`, { method: 'PATCH', body: { activo } }),
  report: (id: UUID, q: { estado?: EstadoSesion; skip?: number; limit?: number } = {}) =>
    request<EspacioReporte>(`/academic-spaces/${enc(id)}/reports`, { query: { limit: 100, ...q } }),
  exportCsv: (id: UUID) => download(`/academic-spaces/${enc(id)}/reports/export`, 'reporte_aula.csv', { tipo: 'sesiones', formato: 'csv' }),
}

export const casesApi = {
  list: (q: { estado?: EstadoCaso; skip?: number; limit?: number } = {}) =>
    request<Page<CasoResumen>>('/cases', { query: { limit: 100, ...q } }),
  get: (id: UUID) => request<CasoDetalle>(`/cases/${enc(id)}`),
  importDsl: (dsl: unknown) => request<CasoDetalle>('/cases/full', { method: 'POST', body: dsl }),
  update: (
    id: UUID,
    data: { nombre?: string; desarrollo_situacional?: string | null; historia?: string | null; tiempo_estimado_min?: number | null },
  ) => request<CasoDetalle>(`/cases/${enc(id)}`, { method: 'PATCH', body: data }),
  remove: (id: UUID) => request<void>(`/cases/${enc(id)}`, { method: 'DELETE' }),
  validate: (id: UUID) => request<ResultadoValidacion>(`/cases/${enc(id)}/validate`, { method: 'POST' }),
  publish: (id: UUID) => request<CasoDetalle>(`/cases/${enc(id)}/publish`, { method: 'POST' }),
  archive: (id: UUID) => request<CasoDetalle>(`/cases/${enc(id)}/archive`, { method: 'POST' }),
  exportDsl: (id: UUID) => download(`/cases/${enc(id)}/dsl`, `caso_${id.slice(0, 8)}.json`),
}

export const sessionsApi = {
  list: (q: { estado?: EstadoSesion; skip?: number; limit?: number } = {}) =>
    request<Page<Sesion>>('/sessions', { query: { limit: 100, ...q } }),
  get: (id: UUID) => request<Sesion>(`/sessions/${enc(id)}`),
  create: (data: SesionCreate) => request<Sesion>('/sessions', { method: 'POST', body: data }),
  update: (id: UUID, data: SesionUpdate) => request<Sesion>(`/sessions/${enc(id)}`, { method: 'PATCH', body: data }),
  start: (id: UUID) => request<Sesion>(`/sessions/${enc(id)}/start`, { method: 'POST' }),
  finish: (id: UUID) => request<Sesion>(`/sessions/${enc(id)}/finish`, { method: 'POST' }),
  convocations: (id: UUID, incluirRevocadas = true) =>
    request<Convocatoria[]>(`/sessions/${enc(id)}/convocations`, { query: { incluir_revocadas: incluirRevocadas } }),
  addConvocations: (id: UUID, estudiantes: string[]) =>
    request<Convocatoria[]>(`/sessions/${enc(id)}/convocations`, { method: 'POST', body: { estudiantes } }),
  revoke: (id: UUID, cid: UUID) => request<void>(`/sessions/${enc(id)}/convocations/${enc(cid)}`, { method: 'DELETE' }),
  code: (id: UUID, cid: UUID) => request<CodigoConvocatoria>(`/sessions/${enc(id)}/convocations/${enc(cid)}/code`),
  regenerateCode: (id: UUID, cid: UUID, motivo: string) =>
    request<CodigoConvocatoria>(`/sessions/${enc(id)}/convocations/${enc(cid)}/regenerate-code`, {
      method: 'POST',
      body: { motivo },
    }),
  setAttempts: (id: UUID, cid: UUID, intentos_autorizados: number, motivo: string) =>
    request<Convocatoria>(`/sessions/${enc(id)}/convocations/${enc(cid)}/attempts`, {
      method: 'PATCH',
      body: { intentos_autorizados, motivo },
    }),
}

export const evaluationsApi = {
  process: (sessionId: UUID) => request<ProcesoEvaluacion>(`/sessions/${enc(sessionId)}/evaluations/process`, { method: 'POST' }),
  list: (sessionId: UUID) => request<ResultadosSesion>(`/sessions/${enc(sessionId)}/evaluations`),
  absences: (sessionId: UUID) => request<Ausencia[]>(`/sessions/${enc(sessionId)}/absences`),
  detail: (participationId: UUID) => request<EvaluacionDetalle>(`/participations/${enc(participationId)}/evaluation`),
  recalculate: (participationId: UUID) =>
    request<EvaluacionDetalle>(`/participations/${enc(participationId)}/evaluation/recalculate`, { method: 'POST' }),
  feedback: (participationId: UUID, retroalimentacion_general: string | null) =>
    request<{ participacion_id: UUID; retroalimentacion_general: string | null }>(
      `/participations/${enc(participationId)}/feedback`,
      { method: 'PATCH', body: { retroalimentacion_general } },
    ),
}

export const reportsApi = {
  mySessions: (q: { estado?: EstadoSesion; espacio_academico_id?: UUID; skip?: number; limit?: number } = {}) =>
    request<Page<SesionResumenReporte>>('/reports/my-sessions', { query: { limit: 100, ...q } }),
  summary: (sessionId: UUID) => request<ResumenSesionReporte>(`/sessions/${enc(sessionId)}/reports/summary`),
  students: (sessionId: UUID) =>
    request<EstudiantesReporte>(`/sessions/${enc(sessionId)}/reports/students`, { query: { limit: 100 } }),
  grades: (sessionId: UUID) => request<NotasSesion>(`/sessions/${enc(sessionId)}/reports/grades`),
  criteria: (sessionId: UUID) => request<CriteriosSesion>(`/sessions/${enc(sessionId)}/reports/criteria`),
  questions: (sessionId: UUID) => request<PreguntasSesion>(`/sessions/${enc(sessionId)}/reports/questions`),
  exportCsv: (sessionId: UUID, tipo: 'resumen' | 'estudiantes' | 'intentos' | 'criterios' | 'preguntas') =>
    download(`/sessions/${enc(sessionId)}/reports/export`, `reporte_${tipo}.csv`, { tipo, formato: 'csv' }),
}

export const studentApi = {
  session: (sessionId: UUID) => request<AccesoEstudiantil>(`/student/sessions/${enc(sessionId)}`),
  startOrResume: (sessionId: UUID) =>
    request<Participacion>(`/student/sessions/${enc(sessionId)}/participations`, { method: 'POST' }),
  participations: () => request<Participacion[]>('/student/participations'),
  participation: (id: UUID) => request<Participacion>(`/student/participations/${enc(id)}`),
  questionnaire: (id: UUID) => request<Cuestionario>(`/student/participations/${enc(id)}/questionnaire`),
  saveAnswer: (id: UUID, questionId: UUID, opcion_id: UUID) =>
    request<RespuestaRead>(`/student/participations/${enc(id)}/answers/${enc(questionId)}`, {
      method: 'PUT',
      body: { opcion_id },
    }),
  finish: (id: UUID) => request<Participacion>(`/student/participations/${enc(id)}/finish`, { method: 'POST' }),
  results: () => request<ResultadosEstudiante>('/student/results'),
  result: (participationId: UUID) => request<ResultadoEstudianteDetalle>(`/student/results/${enc(participationId)}`),
}

export const notificationsApi = {
  list: () => request<Page<Notificacion>>('/notifications', { query: { limit: 20 } }),
  markRead: (id: UUID) => request<Notificacion>(`/notifications/${enc(id)}/read`, { method: 'PATCH' }),
}
