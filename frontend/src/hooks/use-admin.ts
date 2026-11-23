// Entregas de correo (CU30). Solo administración.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { queryInvalidation } from '../lib/query-invalidation'
import { queryKeys } from '../lib/query-keys'
import { deliveryService } from '../services/delivery-service'
import type { EstadoEntrega, UUID } from '../types/api'

export const useDeliveries = (estado?: EstadoEntrega) =>
  useQuery({ queryKey: queryKeys.deliveries.list(estado ?? 'todas'), queryFn: () => deliveryService.list(estado ? { estado } : {}) })

export function useRetryDelivery() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: UUID) => deliveryService.retry(id), onSuccess: () => queryInvalidation.deliveries(qc) })
}
