import { useParams } from 'react-router'
import { Notice, Page, PageHeader } from '../../components/design-system/layout'
import { ErrorState, InlineError, LoadingState } from '../../components/design-system/states'
import { Button } from '../../components/ui/Button'
import { useEvaluationDetail, useRecalculate, useSessionEvaluations, useSessionSummary } from '../../hooks/use-academic'
import { formatDecimal } from '../../lib/format'
import { FeedbackEditor } from './FeedbackEditor'
import { ResultBreakdown } from './ResultBreakdown'

/** Evaluación de un intento (CU22–CU24): nota registrada frente a calculada, desglose y comentario del docente. */
export function TeacherEvaluationView() {
  const { sessionId = '', participationId = '' } = useParams()
  const q = useEvaluationDetail(participationId)
  const summary = useSessionSummary(sessionId)
  const list = useSessionEvaluations(sessionId)
  const recalc = useRecalculate(sessionId, participationId)
  const estudiante = list.data?.participaciones.find((p) => p.participacion_id === participationId)
  const finalizada = list.data?.estado_sesion === 'FINALIZADO'

  return (
    <Page width="reading">
      <PageHeader
        crumbs={[
          { label: 'Sesiones', to: '/docente/sesiones' },
          { label: summary.data ? `${summary.data.sesion.caso.nombre}: resultados` : 'Resultados', to: `/docente/sesiones/${sessionId}?tab=resultados` },
        ]}
        title={estudiante?.estudiante_nombre ?? 'Evaluación del intento'}
        description={estudiante?.estudiante_correo}
      />

      {q.isPending && <LoadingState label="Cargando evaluación…" />}
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.data && (
        <>
          {q.data.nota_calculada !== q.data.nota_final && (
            <Notice tone="warn" title={q.data.nota_final === null ? 'Este intento aún no tiene nota registrada.' : 'La nota registrada no coincide con la calculada.'}>
              Registrada: {formatDecimal(q.data.nota_final)}. Calculada con la política vigente: {formatDecimal(q.data.nota_calculada)}. El estudiante
              solo ve el detalle cuando la nota está registrada.
              <div className="notice-action">
                <Button size="sm" variant="primary" onClick={() => recalc.mutate()} pending={recalc.isPending} pendingLabel="Registrando…">
                  Registrar nota calculada
                </Button>
              </div>
            </Notice>
          )}
          <InlineError error={recalc.error} />
          <ResultBreakdown r={q.data} viewer="teacher" />
          <FeedbackEditor key={q.data.participacion_id} sessionId={sessionId} participationId={participationId} initial={q.data.retroalimentacion_general ?? ''} finalizada={finalizada} />
        </>
      )}
    </Page>
  )
}
