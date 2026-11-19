import { useParams } from 'react-router'
import { Notice, Page, PageHeader } from '../../components/design-system/layout'
import { ErrorState, LoadingState } from '../../components/design-system/states'
import { ButtonLink } from '../../components/ui/Button'
import { useStudentResult } from '../../hooks/use-student'
import { ApiError } from '../../services/http-client'
import { ResultBreakdown } from '../evaluation/ResultBreakdown'

export function StudentResultDetailView() {
  const { participationId = '' } = useParams()
  const q = useStudentResult(participationId)
  let body
  if (q.isPending) body = <LoadingState label="Cargando resultado…" />
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
