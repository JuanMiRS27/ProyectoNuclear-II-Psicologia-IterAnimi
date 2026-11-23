// Casos académicos: listado, detalle, ciclo de vida y edición granular (CU6–CU11).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { queryInvalidation } from '../lib/query-invalidation'
import { queryKeys } from '../lib/query-keys'
import { caseService } from '../services/case-service'
import type { CasoCreate, CasoDetalle, EstadoCaso, UUID } from '../types/api'

export const useCases = (estado?: EstadoCaso) =>
  useQuery({ queryKey: queryKeys.cases.list(estado ?? 'todos'), queryFn: () => caseService.list(estado ? { estado } : {}) })
export const useCase = (id: UUID) => useQuery({ queryKey: queryKeys.cases.detail(id), queryFn: () => caseService.get(id) })

export function useCreateCase() {
  const qc = useQueryClient()
  return {
    blank: useMutation({ mutationFn: (data: CasoCreate) => caseService.create(data), onSuccess: () => queryInvalidation.cases(qc) }),
    fromDsl: useMutation({ mutationFn: (dsl: unknown) => caseService.importDsl(dsl), onSuccess: () => queryInvalidation.cases(qc) }),
  }
}

export function useCaseLifecycle(id: UUID) {
  const qc = useQueryClient()
  const setDetail = (data: CasoDetalle) => {
    qc.setQueryData(queryKeys.cases.detail(id), data)
    void queryInvalidation.cases(qc)
  }
  return {
    validate: useMutation({ mutationFn: () => caseService.validate(id) }),
    publish: useMutation({ mutationFn: () => caseService.publish(id), onSuccess: setDetail }),
    archive: useMutation({ mutationFn: () => caseService.archive(id), onSuccess: setDetail }),
    remove: useMutation({ mutationFn: () => caseService.remove(id), onSuccess: () => queryInvalidation.cases(qc) }),
    update: useMutation({ mutationFn: (data: Partial<CasoCreate>) => caseService.update(id, data), onSuccess: setDetail }),
    exportDsl: useMutation({ mutationFn: () => caseService.exportDsl(id) }),
  }
}

/**
 * Edición del contenido de un borrador. Cada operación devuelve un fragmento; tras cualquiera
 * se vuelve a leer el caso completo para que órdenes y renumeraciones vengan del servidor.
 */
export function useCaseEditor(id: UUID) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (op: (caseId: UUID) => Promise<unknown>) => op(id),
    onSettled: () => queryInvalidation.caseDetail(qc, id),
  })
}
