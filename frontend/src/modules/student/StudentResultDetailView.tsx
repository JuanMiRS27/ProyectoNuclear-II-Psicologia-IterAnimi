import { useParams } from 'react-router'
import { Notice, Page, PageHeader } from '../../components/design-system/layout'
import { EmptyState, ErrorState, LoadingState } from '../../components/design-system/states'
import { ButtonLink } from '../../components/ui/Button'
import { useSession } from '../../hooks/use-session'
import { useStudentResult } from '../../hooks/use-student'
import { ApiError } from '../../services/http-client'
import { ResultBreakdown } from '../evaluation/ResultBreakdown'

export function StudentResultDetailView() {
  const { participationId = '' } = useParams()
  const { session } = useSession()
  const q = useStudentResult(participationId)
  let body
  // Con la sesión en curso el token no permite leer notas: se explica en lugar de quedarse cargando.
  if (session?.kind !== 'results')
    body = (
      <EmptyState icon="clock" title="Tus resultados aparecerán cuando termine la sesión">
        Mientras la sesión sigue en curso no se muestran notas. Cuando tu docente la finalice, vuelve a ingresar con tu correo y el mismo código de acceso.
      </EmptyState>
    )
  else if (q.isPending) body = <LoadingState label="Cargando resultado…" />
  else if (q.isError)
    body =
      q.error instanceof ApiError && q.error.status === 409 ? (
        <Notice tone="warn" title="Este resultado está pendiente de revisión.">
          Tu docente aún no ha registrado la evaluación de este intento. Vuelve a consultarlo más tarde.
        </Notice>
      ) : (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      )
  else body = <ResultBreakdown r={q.data} viewer="student" />

  return (
    <Page width="reading">
      <PageHeader crumbs={[{ label: 'Resultados', to: '/estudiante/resultados' }]} title={q.data ? `Intento ${q.data.numero_intento}` : 'Resultado'} />
      {body}
      <div className="btn-row">
        <ButtonLink to="/estudiante/resultados" icon="chevronLeft">
          Volver a mis resultados
        </ButtonLink>
        <ButtonLink to="/estudiante/retroalimentacion" variant="quiet">
          Ver comentarios del docente
        </ButtonLink>
      </div>
    </Page>
  )
}
