import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { evaluationsApi, reportsApi } from '../../../api/endpoints'
import { ResultBreakdown } from '../../../components/ResultBreakdown'
import { ErrorState, InlineError, Loading } from '../../../components/states'
import { formatDecimal } from '../../../lib/format'

export function EvaluationDetailPage() {
  const { sessionId = '', participationId = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['evaluation', participationId], queryFn: () => evaluationsApi.detail(participationId) })
  const summary = useQuery({ queryKey: ['session-summary', sessionId], queryFn: () => reportsApi.summary(sessionId) })
  const list = useQuery({ queryKey: ['evaluations', sessionId], queryFn: () => evaluationsApi.list(sessionId) })
  const recalc = useMutation({
    mutationFn: () => evaluationsApi.recalculate(participationId),
    onSuccess: (data) => {
      qc.setQueryData(['evaluation', participationId], data)
      qc.invalidateQueries({ queryKey: ['evaluations', sessionId] })
    },
  })

  const estudiante = list.data?.participaciones.find((p) => p.participacion_id === participationId)

  return (
    <main className="page page-narrow" id="contenido" style={{ maxWidth: '58rem' }}>
      <div>
        <div className="crumbs">
          <Link to={`/sesiones/${sessionId}?tab=resultados`}>{summary.data?.sesion.caso.nombre ?? 'Sesión'}: resultados</Link>
        </div>
        <h1>{estudiante?.estudiante_nombre ?? 'Evaluación del intento'}</h1>
        {estudiante && <p className="lede muted">{estudiante.estudiante_correo}</p>}
      </div>

      {q.isPending && <Loading label="Cargando evaluación…" />}
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.data && (
        <>
          {q.data.nota_calculada !== q.data.nota_final && (
            <div className="notice notice-info">
              <div>
                <strong>
                  {q.data.nota_final === null ? 'Este intento aún no tiene nota registrada.' : 'La nota registrada no coincide con la calculada.'}
                </strong>
                Registrada: {formatDecimal(q.data.nota_final)}. Calculada con la política vigente: {formatDecimal(q.data.nota_calculada)}. El
                estudiante solo ve el detalle cuando la nota está registrada.
                <div style={{ marginTop: '0.6rem' }}>
                  <button type="button" className="btn btn-sm btn-primary" onClick={() => recalc.mutate()} disabled={recalc.isPending}>
                    {recalc.isPending ? 'Registrando…' : 'Registrar nota calculada'}
                  </button>
                </div>
              </div>
            </div>
          )}
          <InlineError error={recalc.error} />

          <ResultBreakdown r={q.data} viewer="teacher" />

          <FeedbackEditor
            key={q.data.participacion_id}
            participationId={participationId}
            sessionId={sessionId}
            initial={q.data.retroalimentacion_general ?? ''}
          />
        </>
      )}
    </main>
  )
}

function FeedbackEditor({ participationId, sessionId, initial }: { participationId: string; sessionId: string; initial: string }) {
  const qc = useQueryClient()
  const [texto, setTexto] = useState(initial)
  const [saved, setSaved] = useState(false)
  const save = useMutation({
    mutationFn: () => evaluationsApi.feedback(participationId, texto.trim() || null),
    onSuccess: () => {
      setSaved(true)
      qc.invalidateQueries({ queryKey: ['evaluation', participationId] })
      qc.invalidateQueries({ queryKey: ['evaluations', sessionId] })
    },
  })
  return (
    <section className="panel form-grid" aria-labelledby="h-retro">
      <h2 id="h-retro">Tu comentario para el estudiante</h2>
      <div className="field">
        <label htmlFor="retro" className="visually-hidden">
          Comentario
        </label>
        <textarea
          id="retro"
          maxLength={5000}
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value)
            setSaved(false)
          }}
          style={{ minHeight: '9rem' }}
          aria-describedby="retro-hint"
        />
        <span className="hint" id="retro-hint">
          {texto.length} de 5000 caracteres. No cambia la nota. Déjalo vacío para quitarlo. El estudiante lo verá cuando la sesión
          esté finalizada.
        </span>
      </div>
      <InlineError error={save.error} />
      <div className="btn-row">
        <button type="button" className="btn btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? 'Guardando…' : 'Guardar comentario'}
        </button>
        {saved && !save.isPending && (
          <span role="status" className="small" style={{ color: 'var(--ok)', fontWeight: 600 }}>
            Comentario guardado
          </span>
        )}
      </div>
    </section>
  )
}
