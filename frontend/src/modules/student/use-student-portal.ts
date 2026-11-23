// Composición del portal estudiantil: el mismo modelo de vista con el token de la sesión en curso
// ("live") o con el de resultados ("results"). Ninguno amplía el alcance de su convocatoria.
import { useSession } from '../../hooks/use-session'
import { useStudentAccess, useStudentAttempts, useStudentResults } from '../../hooks/use-student'
import { fromLiveAccess, fromResults, type StudentSessionView } from '../../lib/student-session-adapters'
import type { Participacion, ResultadosEstudiante } from '../../types/api'

export interface StudentPortalState {
  isPending: boolean
  error: unknown
  refetch: () => void
  view?: StudentSessionView
  attempts: Participacion[]
  results?: ResultadosEstudiante
}

export function useStudentPortal(): StudentPortalState {
  const { session } = useSession()
  const access = useStudentAccess()
  const attempts = useStudentAttempts()
  const results = useStudentResults()

  if (session?.kind === 'results') {
    return {
      isPending: results.isPending,
      error: results.error,
      refetch: () => void results.refetch(),
      view: results.data ? fromResults(results.data) : undefined,
      attempts: [],
      results: results.data,
    }
  }
  return {
    isPending: access.isPending || attempts.isPending,
    error: access.error ?? attempts.error,
    refetch: () => {
      void access.refetch()
      void attempts.refetch()
    },
    view: access.data && attempts.data ? fromLiveAccess(access.data, attempts.data) : undefined,
    attempts: attempts.data ?? [],
  }
}
