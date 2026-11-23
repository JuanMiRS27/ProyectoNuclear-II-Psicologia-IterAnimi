// Invalidaciones por efecto de negocio: cada mutación refresca solo lo que cambió.
import type { QueryClient } from '@tanstack/react-query'
import { queryKeys } from './query-keys'

export const queryInvalidation = {
  users: (qc: QueryClient) => qc.invalidateQueries({ queryKey: queryKeys.users.all() }),
  spaces: (qc: QueryClient) => qc.invalidateQueries({ queryKey: queryKeys.spaces.all() }),
  cases: (qc: QueryClient) => qc.invalidateQueries({ queryKey: queryKeys.cases.all() }),
  caseDetail: (qc: QueryClient, id: string) =>
    Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.cases.detail(id) }),
      qc.invalidateQueries({ queryKey: queryKeys.cases.list(undefined), exact: false }),
    ]),
  /** Crear, abrir, finalizar o editar una sesión: listados, agenda del docente, aulas y la propia sesión. */
  sessionChanged: (qc: QueryClient, id?: string) =>
    Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.sessions.list() }),
      qc.invalidateQueries({ queryKey: queryKeys.sessions.mine() }),
      qc.invalidateQueries({ queryKey: queryKeys.spaces.all() }),
      id ? qc.invalidateQueries({ queryKey: queryKeys.sessions.detail(id) }) : Promise.resolve(),
    ]),
  /** Convocar, retirar, regenerar o dar intentos: convocados, reportes de estudiantes y resumen. */
  convocationsChanged: (qc: QueryClient, id: string) =>
    Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.sessions.convocations(id) }),
      qc.invalidateQueries({ queryKey: queryKeys.sessions.students(id) }),
      qc.invalidateQueries({ queryKey: queryKeys.sessions.summary(id) }),
      qc.invalidateQueries({ queryKey: queryKeys.sessions.mine() }),
    ]),
  /** Evaluar o recalificar: resultados, reportes de la sesión, agenda y detalle de evaluación. */
  evaluated: (qc: QueryClient, sessionId: string, participationId?: string) =>
    Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.sessions.evaluations(sessionId) }),
      qc.invalidateQueries({ queryKey: ['sessions', sessionId, 'reports'] }),
      qc.invalidateQueries({ queryKey: queryKeys.sessions.mine() }),
      participationId
        ? qc.invalidateQueries({ queryKey: queryKeys.evaluations.detail(participationId) })
        : qc.invalidateQueries({ queryKey: ['evaluations'] }),
    ]),
  /** Guardar retroalimentación: detalle del intento y la tabla de resultados (marca «con comentario»). */
  feedbackSaved: (qc: QueryClient, sessionId: string, participationId: string) =>
    Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.evaluations.detail(participationId) }),
      qc.invalidateQueries({ queryKey: queryKeys.sessions.evaluations(sessionId) }),
    ]),
  studentAttempts: (qc: QueryClient) => qc.invalidateQueries({ queryKey: queryKeys.student.attempts() }),
  notifications: (qc: QueryClient) => qc.invalidateQueries({ queryKey: queryKeys.notifications.all() }),
  deliveries: (qc: QueryClient) => qc.invalidateQueries({ queryKey: queryKeys.deliveries.all() }),
} as const
