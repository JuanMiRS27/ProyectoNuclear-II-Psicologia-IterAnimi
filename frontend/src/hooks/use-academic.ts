// Aulas, sesiones, convocatorias, evaluación y reportes del docente; aulas y usuarios de administración.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { queryInvalidation } from '../lib/query-invalidation'
import { queryKeys } from '../lib/query-keys'
import { evaluationService } from '../services/evaluation-service'
import { reportService, type ExportType } from '../services/report-service'
import { sessionService } from '../services/session-service'
import { spaceService } from '../services/space-service'
import { userService, type UserFilters } from '../services/user-service'
import type { SesionCreate, SesionUpdate, UUID } from '../types/api'

// --- Aulas ---
export const useSpaces = (filters: { activo?: boolean } = {}) =>
  useQuery({ queryKey: queryKeys.spaces.list(filters), queryFn: () => spaceService.list(filters) })
export const useSpace = (id: UUID) => useQuery({ queryKey: queryKeys.spaces.detail(id), queryFn: () => spaceService.get(id) })
export const useSpaceReport = (id: UUID) =>
  useQuery({ queryKey: queryKeys.spaces.report(id), queryFn: () => spaceService.report(id) })

export function useSaveSpace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id?: UUID; data: { nombre: string; periodo: string } }) =>
      id ? spaceService.update(id, data) : spaceService.create(data),
    onSuccess: () => queryInvalidation.spaces(qc),
  })
}
export function useSetSpaceStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, activo }: { id: UUID; activo: boolean }) => spaceService.setStatus(id, activo),
    onSuccess: () => queryInvalidation.spaces(qc),
  })
}

// --- Usuarios (administración) ---
export const useUsers = (filters: UserFilters) =>
  useQuery({ queryKey: queryKeys.users.list(filters), queryFn: () => userService.list(filters) })

export function useUserMutations() {
  const qc = useQueryClient()
  const done = () => queryInvalidation.users(qc)
  return {
    createTeacher: useMutation({ mutationFn: userService.createTeacher, onSuccess: done }),
    createStudent: useMutation({ mutationFn: userService.createStudent, onSuccess: done }),
    update: useMutation({
      mutationFn: ({ id, data }: { id: UUID; data: Parameters<typeof userService.update>[1] }) => userService.update(id, data),
      onSuccess: done,
    }),
    setStatus: useMutation({
      mutationFn: ({ id, activo }: { id: UUID; activo: boolean }) => userService.setStatus(id, activo),
      onSuccess: done,
    }),
    setCasePermission: useMutation({
      mutationFn: ({ id, value }: { id: UUID; value: boolean }) => userService.setCasePermission(id, value),
      onSuccess: done,
    }),
  }
}

// --- Sesiones del docente ---
export const useMySessions = () => useQuery({ queryKey: queryKeys.sessions.mine(), queryFn: reportService.mySessions })
export const useSessionDetail = (id: UUID) => useQuery({ queryKey: queryKeys.sessions.detail(id), queryFn: () => sessionService.get(id) })
export const useSessionSummary = (id: UUID) =>
  useQuery({ queryKey: queryKeys.sessions.summary(id), queryFn: () => reportService.summary(id) })

export function useCreateSession() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: SesionCreate) => sessionService.create(data), onSuccess: () => queryInvalidation.sessionChanged(qc) })
}

export function useSessionLifecycle(id: UUID) {
  const qc = useQueryClient()
  const done = () => queryInvalidation.sessionChanged(qc, id)
  return {
    start: useMutation({ mutationFn: () => sessionService.start(id), onSuccess: done }),
    finish: useMutation({
      mutationFn: () => sessionService.finish(id),
      // Finalizar cierra intentos: también cambian resultados y reportes.
      onSuccess: () => Promise.all([done(), queryInvalidation.evaluated(qc, id)]),
    }),
    update: useMutation({ mutationFn: (data: SesionUpdate) => sessionService.update(id, data), onSuccess: done }),
  }
}

/** Abrir una sesión desde un listado (agenda), sin conocer el id de antemano. */
export function useStartSession() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: UUID) => sessionService.start(id), onSuccess: (_d, id) => queryInvalidation.sessionChanged(qc, id) })
}

// --- Convocatorias ---
export const useConvocations = (id: UUID) =>
  useQuery({ queryKey: queryKeys.sessions.convocations(id), queryFn: () => sessionService.convocations(id) })
export const useStudentsReport = (id: UUID) =>
  useQuery({ queryKey: queryKeys.sessions.students(id), queryFn: () => reportService.students(id) })
export const useConvocationCode = (id: UUID, cid: UUID) =>
  useQuery({ queryKey: queryKeys.sessions.code(id, cid), queryFn: () => sessionService.code(id, cid), gcTime: 0, staleTime: 0 })

export function useConvocationMutations(id: UUID) {
  const qc = useQueryClient()
  const done = () => queryInvalidation.convocationsChanged(qc, id)
  return {
    convoke: useMutation({ mutationFn: (emails: string[]) => sessionService.convoke(id, emails), onSuccess: done }),
    revoke: useMutation({ mutationFn: (cid: UUID) => sessionService.revoke(id, cid), onSuccess: done }),
    regenerate: useMutation({
      mutationFn: ({ cid, motivo }: { cid: UUID; motivo: string }) => sessionService.regenerateCode(id, cid, motivo),
      onSuccess: done,
    }),
    attempts: useMutation({
      mutationFn: ({ cid, n, motivo }: { cid: UUID; n: number; motivo: string }) => sessionService.setAttempts(id, cid, n, motivo),
      onSuccess: done,
    }),
  }
}

// --- Evaluación ---
export const useSessionEvaluations = (id: UUID) =>
  useQuery({ queryKey: queryKeys.sessions.evaluations(id), queryFn: () => evaluationService.bySession(id) })
export const useEvaluationDetail = (participationId: UUID) =>
  useQuery({ queryKey: queryKeys.evaluations.detail(participationId), queryFn: () => evaluationService.detail(participationId) })

export function useProcessEvaluations(sessionId: UUID) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => evaluationService.process(sessionId), onSuccess: () => queryInvalidation.evaluated(qc, sessionId) })
}
export function useRecalculate(sessionId: UUID, participationId: UUID) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => evaluationService.recalculate(participationId),
    onSuccess: () => queryInvalidation.evaluated(qc, sessionId, participationId),
  })
}
export function useSaveFeedback(sessionId: UUID, participationId: UUID) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (text: string | null) => evaluationService.saveFeedback(participationId, text),
    onSuccess: () => queryInvalidation.feedbackSaved(qc, sessionId, participationId),
  })
}

// --- Reportes ---
export const useGrades = (id: UUID) => useQuery({ queryKey: queryKeys.sessions.grades(id), queryFn: () => reportService.grades(id) })
export const useCriteriaReport = (id: UUID) =>
  useQuery({ queryKey: queryKeys.sessions.criteria(id), queryFn: () => reportService.criteria(id) })
export const useQuestionsReport = (id: UUID) =>
  useQuery({ queryKey: queryKeys.sessions.questions(id), queryFn: () => reportService.questions(id) })
export const useExportSession = (id: UUID) => useMutation({ mutationFn: (tipo: ExportType) => reportService.exportCsv(id, tipo) })
export const useExportSpace = (id: UUID) => useMutation({ mutationFn: () => spaceService.exportCsv(id) })
