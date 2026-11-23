// Usuarios (CU2, CU4): solo administración.
import type { Page, Rol, Usuario, UUID } from '../types/api'
import { request } from './http-client'

const enc = encodeURIComponent

export interface UserFilters {
  rol?: Rol
  activo?: boolean
}

export const userService = {
  list: (filters: UserFilters = {}) => request<Page<Usuario>>('/users', { query: { limit: 100, ...filters } }),
  createTeacher: (data: { nombre_completo: string; correo: string; clave: string; codigo_institucional?: string | null }) =>
    request<Usuario>('/users/teachers', { method: 'POST', body: data }),
  createStudent: (data: { nombre_completo: string; correo: string; codigo_institucional?: string | null }) =>
    request<Usuario>('/users/students', { method: 'POST', body: data }),
  update: (id: UUID, data: { nombre_completo?: string; correo?: string; codigo_institucional?: string | null }) =>
    request<Usuario>(`/users/${enc(id)}`, { method: 'PATCH', body: data }),
  setStatus: (id: UUID, activo: boolean) => request<Usuario>(`/users/${enc(id)}/status`, { method: 'PATCH', body: { activo } }),
  setCasePermission: (id: UUID, puede_crear_casos: boolean) =>
    request<Usuario>(`/users/${enc(id)}/case-permission`, { method: 'PATCH', body: { puede_crear_casos } }),
} as const
