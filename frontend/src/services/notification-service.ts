// Avisos internos (CU29): cada token ve solo los suyos (el estudiante, los de su convocatoria).
import type { NoLeidas, Notificacion, Page, UUID } from '../types/api'
import { request } from './http-client'

export const notificationService = {
  list: () => request<Page<Notificacion>>('/notifications', { query: { limit: 50 } }),
  unreadCount: () => request<NoLeidas>('/notifications/unread-count'),
  markRead: (id: UUID) => request<Notificacion>(`/notifications/${encodeURIComponent(id)}/read`, { method: 'PATCH' }),
} as const
