// Portal del estudiante. Todo se lee con el token de su convocatoria (o el de resultados): nada amplía su alcance.
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { queryInvalidation } from '../lib/query-invalidation'
import { queryKeys } from '../lib/query-keys'
import { notificationService } from '../services/notification-service'
import { studentService } from '../services/student-service'
import type { UUID } from '../types/api'
import { useSession } from './use-session'

/** Sesión del token estudiantil (solo con la sesión EN_CURSO). */
export function useStudentAccess() {
  const { session } = useSession()
  const id = session?.kind === 'student' ? session.sesionId : ''
  return useQuery({ queryKey: queryKeys.student.session(id), queryFn: () => studentService.session(id), enabled: Boolean(id) })
}

export function useStudentAttempts() {
  const { session } = useSession()
  return useQuery({ queryKey: queryKeys.student.attempts(), queryFn: studentService.attempts, enabled: session?.kind === 'student' })
}

export function useStartAttempt() {
  const { session } = useSession()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => {
      if (session?.kind !== 'student') throw new Error('Se requiere el acceso con código.')
      return studentService.startOrResume(session.sesionId)
    },
    onSuccess: () => queryInvalidation.studentAttempts(qc),
  })
}

export const useAttemptState = (id: UUID) =>
  useQuery({ queryKey: queryKeys.student.attempt(id), queryFn: () => studentService.attempt(id), gcTime: 0 })

/** Resultados: solo con el token de resultados (sesión FINALIZADO). */
export function useStudentResults() {
  const { session } = useSession()
  return useQuery({ queryKey: queryKeys.student.results(), queryFn: studentService.results, enabled: session?.kind === 'results' })
}

export function useStudentResult(id: UUID) {
  const { session } = useSession()
  return useQuery({ queryKey: queryKeys.student.result(id), queryFn: () => studentService.result(id), enabled: session?.kind === 'results' })
}

export const useNotifications = () => useQuery({ queryKey: queryKeys.notifications.list(), queryFn: notificationService.list })

export function useMarkNotificationRead() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: UUID) => notificationService.markRead(id), onSuccess: () => queryInvalidation.notifications(qc) })
}

// --- Simulador ---

/** Cuestionario seguro (sin respuestas correctas). Se lee una vez por intento; el progreso se resincroniza aparte. */
export const useQuestionnaire = (id: UUID) =>
  useQuery({ queryKey: queryKeys.student.questionnaire(id), queryFn: () => studentService.questionnaire(id), staleTime: Infinity, gcTime: 0 })

export const useSaveAnswer = (id: UUID) =>
  useMutation({ mutationFn: ({ preguntaId, opcionId }: { preguntaId: UUID; opcionId: UUID }) => studentService.saveAnswer(id, preguntaId, opcionId) })

export function useFinishAttempt(id: UUID) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => studentService.finish(id), onSuccess: () => queryInvalidation.studentAttempts(qc) })
}

/** Lectura imperativa del estado del intento (tiempo, progreso, cierre) para resincronizar con el servidor. */
export function useAttemptSync(id: UUID) {
  const qc = useQueryClient()
  return () => qc.fetchQuery({ queryKey: queryKeys.student.attempt(id), queryFn: () => studentService.attempt(id), staleTime: 0 })
}

/** Detalle de varios intentos evaluados (para reunir los comentarios del docente). */
export function useStudentResultDetails(ids: UUID[]) {
  const { session } = useSession()
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: queryKeys.student.result(id),
      queryFn: () => studentService.result(id),
      enabled: session?.kind === 'results',
    })),
  })
}
