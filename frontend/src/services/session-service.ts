// Sesiones y convocatorias (CU12–CU15): solo el docente responsable.
import type { CodigoConvocatoria, Convocatoria, Page, Sesion, SesionCreate, SesionUpdate, UUID } from '../types/api'
import { request } from './http-client'

const enc = encodeURIComponent
const base = (id: UUID) => `/sessions/${enc(id)}`

export const sessionService = {
  list: () => request<Page<Sesion>>('/sessions', { query: { limit: 100 } }),
  get: (id: UUID) => request<Sesion>(base(id)),
  create: (data: SesionCreate) => request<Sesion>('/sessions', { method: 'POST', body: data }),
  update: (id: UUID, data: SesionUpdate) => request<Sesion>(base(id), { method: 'PATCH', body: data }),
  start: (id: UUID) => request<Sesion>(`${base(id)}/start`, { method: 'POST' }),
  finish: (id: UUID) => request<Sesion>(`${base(id)}/finish`, { method: 'POST' }),
  convocations: (id: UUID) => request<Convocatoria[]>(`${base(id)}/convocations`, { query: { incluir_revocadas: true } }),
  convoke: (id: UUID, estudiantes: string[]) =>
    request<Convocatoria[]>(`${base(id)}/convocations`, { method: 'POST', body: { estudiantes } }),
  revoke: (id: UUID, cid: UUID) => request<void>(`${base(id)}/convocations/${enc(cid)}`, { method: 'DELETE' }),
  code: (id: UUID, cid: UUID) => request<CodigoConvocatoria>(`${base(id)}/convocations/${enc(cid)}/code`),
  regenerateCode: (id: UUID, cid: UUID, motivo: string) =>
    request<CodigoConvocatoria>(`${base(id)}/convocations/${enc(cid)}/regenerate-code`, { method: 'POST', body: { motivo } }),
  setAttempts: (id: UUID, cid: UUID, intentos_autorizados: number, motivo: string) =>
    request<Convocatoria>(`${base(id)}/convocations/${enc(cid)}/attempts`, {
      method: 'PATCH',
      body: { intentos_autorizados, motivo },
    }),
} as const
