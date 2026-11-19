// Entregas de correo (CU30): solo administración. La API no expone direcciones ni contenido.
import type { EntregaCorreo, EstadoEntrega, Page, UUID } from '../types/api'
import { request } from './http-client'

export const deliveryService = {
  list: (q: { estado?: EstadoEntrega } = {}) =>
    request<Page<EntregaCorreo>>('/notification-deliveries', { query: { limit: 100, ...q } }),
  retry: (id: UUID) => request<EntregaCorreo>(`/notification-deliveries/${encodeURIComponent(id)}/retry`, { method: 'POST' }),
} as const
