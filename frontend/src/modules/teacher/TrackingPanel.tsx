import { ErrorState, InlineError, LoadingState } from '../../components/design-system/states'
import { Button } from '../../components/ui/Button'
import { useCriteriaReport, useExportSession, useGrades, useQuestionsReport, useSessionSummary } from '../../hooks/use-academic'
import { formatDecimal, formatPercent } from '../../lib/format'
import type { Indicador, Sesion } from '../../types/api'

function Rate({ label, i }: { label: string; i: Indicador }) {
  return (
    <div>
      <dt>
        {label}
        <br />
        <span className="small">
          {i.numerador} de {i.denominador}
        </span>
      </dt>
      <dd>{i.porcentaje === null ? '—' : formatPercent(i.porcentaje)}</dd>
    </div>
  )
}

function Bar({ value }: { value: string | null }) {
  const n = value === null ? 0 : Math.max(0, Math.min(100, Number(value)))
  return (
    <div className="bar" aria-hidden="true">
      <span style={{ width: `${n}%` }} />
    </div>
  )
}

const EXPORTS = [
  { tipo: 'resumen', label: 'Resumen' },
  { tipo: 'estudiantes', label: 'Estudiantes' },
  { tipo: 'intentos', label: 'Intentos' },
  { tipo: 'criterios', label: 'Criterios' },
  { tipo: 'preguntas', label: 'Preguntas' },
] as const

/** Seguimiento (CU31–CU35): participación, notas, criterios, preguntas y exportación CSV. */
export function TrackingPanel({ sesion }: { sesion: Sesion }) {
  const summary = useSessionSummary(sesion.id)
  const grades = useGrades(sesion.id)
  const criteria = useCriteriaReport(sesion.id)
  const questions = useQuestionsReport(sesion.id)
  const exp = useExportSession(sesion.id)

  if (summary.isPending) return <LoadingState label="Cargando seguimiento…" />
  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => summary.refetch()} />
  const s = summary.data
  const g = grades.data?.estadisticas

  return (
    <div className="section" style={{ gap: '2.25rem' }}>
      <section className="section" aria-labelledby="h-ind">
        <h2 id="h-ind">Participación</h2>
        <dl className="figures">
          <Rate label="estudiantes que participaron" i={s.indicadores.tasa_participacion} />
          <Rate label="intentos completados" i={s.indicadores.tasa_finalizacion} />
          <Rate label="intentos cerrados sin finalizar" i={s.indicadores.tasa_expiracion} />
          <Rate label="intentos cerrados con nota" i={s.indicadores.tasa_calificacion} />
        </dl>
        {s.intentos.vencidos_sin_cerrar > 0 && (
          <p className="small muted">
            {s.intentos.vencidos_sin_cerrar} intento(s) agotaron su tiempo y el sistema los cerrará en breve.
          </p>
        )}
      </section>

      <section className="section" aria-labelledby="h-notas">
        <h2 id="h-notas">Notas</h2>
        {grades.isError ? (
          <InlineError error={grades.error} />
        ) : !g ? (
          <LoadingState />
        ) : g.evaluados === 0 ? (
          <p className="muted">Aún no hay intentos con nota registrada.</p>
        ) : (
          <>
            <dl className="figures">
              <div>
                <dt>promedio</dt>
                <dd>{formatDecimal(g.promedio)}</dd>
              </div>
              <div>
                <dt>mediana</dt>
                <dd>{formatDecimal(g.mediana)}</dd>
              </div>
              <div>
                <dt>mínima</dt>
                <dd>{formatDecimal(g.minimo)}</dd>
              </div>
              <div>
                <dt>máxima</dt>
                <dd>{formatDecimal(g.maximo)}</dd>
              </div>
              <div>
                <dt>intentos evaluados</dt>
                <dd>{g.evaluados}</dd>
              </div>
            </dl>
            <p className="small muted">Sobre una escala de {formatDecimal(g.escala_max)}. Cada intento cuenta por separado.</p>
            <div className="table-wrap">
              <table className="table">
                <caption className="visually-hidden">Distribución de notas</caption>
                <thead>
                  <tr>
                    <th>Rango</th>
                    <th className="num">Intentos</th>
                    <th style={{ width: '45%' }}>Proporción</th>
                  </tr>
                </thead>
                <tbody>
                  {g.distribucion.map((t, i) => (
                    <tr key={i}>
                      <td className="num" style={{ textAlign: 'left' }}>
                        {formatDecimal(t.desde)} a {formatDecimal(t.hasta)}
                        {t.incluye_hasta ? '' : ' (sin incluir)'}
                      </td>
                      <td className="num">{t.cantidad}</td>
                      <td>
                        <Bar value={t.porcentaje} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <section className="section" aria-labelledby="h-crit">
        <h2 id="h-crit">Desempeño por criterio</h2>
        {criteria.isError ? (
          <InlineError error={criteria.error} />
        ) : !criteria.data ? (
          <LoadingState />
        ) : criteria.data.intentos_considerados === 0 ? (
          <p className="muted">Se mostrará cuando haya intentos cerrados.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Criterio</th>
                  <th className="num">Aciertos</th>
                  <th style={{ width: '30%' }}>Porcentaje</th>
                  <th className="num">Puntaje medio</th>
                </tr>
              </thead>
              <tbody>
                {criteria.data.criterios.map((c) => (
                  <tr key={c.criterio_id}>
                    <td>
                      {c.descripcion}
                      {c.advertencia && <div className="small muted">{c.advertencia}</div>}
                    </td>
                    <td className="num">{c.evaluable ? `${c.aciertos}` : '—'}</td>
                    <td>
                      {c.evaluable ? (
                        <>
                          <span className="small">{formatPercent(c.porcentaje_aciertos)}</span>
                          <Bar value={c.porcentaje_aciertos} />
                        </>
                      ) : (
                        <span className="muted small">Sin preguntas asociadas</span>
                      )}
                    </td>
                    <td className="num">{formatDecimal(c.puntaje_promedio)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="section" aria-labelledby="h-preg">
        <h2 id="h-preg">Desempeño por decisión</h2>
        {questions.isError ? (
          <InlineError error={questions.error} />
        ) : !questions.data ? (
          <LoadingState />
        ) : questions.data.intentos_considerados === 0 ? (
          <p className="muted">Se mostrará cuando haya intentos cerrados.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Pregunta</th>
                  <th className="num">Aciertos</th>
                  <th className="num">No acertadas</th>
                  <th className="num">Sin responder</th>
                  <th className="num">% aciertos</th>
                </tr>
              </thead>
              <tbody>
                {questions.data.preguntas.map((p) => (
                  <tr key={p.pregunta_id}>
                    <td>
                      <div className="small muted">{p.escenario}</div>
                      {p.enunciado}
                    </td>
                    <td className="num">{p.aciertos ?? '—'}</td>
                    <td className="num">{p.errores ?? '—'}</td>
                    <td className="num">{p.sin_responder}</td>
                    <td className="num">{p.corregible ? formatPercent(p.porcentaje_aciertos) : 'No corregible'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="section" aria-labelledby="h-exp">
        <h2 id="h-exp">Descargar en CSV</h2>
        <div className="btn-row">
          {EXPORTS.map((e) => (
            <Button key={e.tipo} size="sm" icon="download" onClick={() => exp.mutate(e.tipo)} disabled={exp.isPending}>
              {e.label}
            </Button>
          ))}
        </div>
        <InlineError error={exp.error} />
      </section>
    </div>
  )
}
