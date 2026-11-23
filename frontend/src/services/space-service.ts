// Aulas = espacios académicos (CU5). Crear y editar: administración; listar: administración y docentes.
import type { Espacio, EspacioReporte, Page, UUID } from '../types/api'
import { download, request } from './http-client'

const enc = encodeURIComponent

export const spaceService = {
  list: (q: { activo?: boolean } = {}) => request<Page<Espacio>>('/academic-spaces', { query: { limit: 100, ...q } }),
  get: (id: UUID) => request<Espacio>(`/academic-spaces/${enc(id)}`),
  create: (data: { nombre: string; periodo: string }) => request<Espacio>('/academic-spaces', { method: 'POST', body: data }),
  update: (id: UUID, data: { nombre?: string; periodo?: string }) =>
    request<Espacio>(`/academic-spaces/${enc(id)}`, { method: 'PATCH', body: data }),
  setStatus: (id: UUID, activo: boolean) =>
    request<Espacio>(`/academic-spaces/${enc(id)}/status`, { method: 'PATCH', body: { activo } }),
  /** CU36: solo las sesiones del docente autenticado en esa aula. */
  report: (id: UUID) => request<EspacioReporte>(`/academic-spaces/${enc(id)}/reports`, { query: { limit: 100 } }),
  exportCsv: (id: UUID) =>
    download(`/academic-spaces/${enc(id)}/reports/export`, 'reporte_aula.csv', { tipo: 'sesiones', formato: 'csv' }),
} as const
