// Seguimiento y reportes del docente (CU31–CU36). Solo lectura.
import type {
  CriteriosSesion,
  EstudiantesReporte,
  NotasSesion,
  Page,
  PreguntasSesion,
  ResumenSesionReporte,
  SesionResumenReporte,
  UUID,
} from '../types/api'
import { download, request } from './http-client'

const enc = encodeURIComponent
const base = (id: UUID) => `/sessions/${enc(id)}/reports`

export type ExportType = 'resumen' | 'estudiantes' | 'intentos' | 'criterios' | 'preguntas'

export const reportService = {
  mySessions: () => request<Page<SesionResumenReporte>>('/reports/my-sessions', { query: { limit: 100 } }),
  summary: (id: UUID) => request<ResumenSesionReporte>(`${base(id)}/summary`),
  students: (id: UUID) => request<EstudiantesReporte>(`${base(id)}/students`, { query: { limit: 100 } }),
  grades: (id: UUID) => request<NotasSesion>(`${base(id)}/grades`),
  criteria: (id: UUID) => request<CriteriosSesion>(`${base(id)}/criteria`),
  questions: (id: UUID) => request<PreguntasSesion>(`${base(id)}/questions`),
  exportCsv: (id: UUID, tipo: ExportType) => download(`${base(id)}/export`, `reporte_${tipo}.csv`, { tipo, formato: 'csv' }),
} as const
