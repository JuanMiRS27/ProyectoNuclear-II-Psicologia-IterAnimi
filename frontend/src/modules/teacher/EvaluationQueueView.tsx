import { Link } from 'react-router'
import { SessionStatus } from '../../components/design-system/domain-status'
import { Notice, Page, PageHeader, Section } from '../../components/design-system/layout'
import { EmptyState, QueryBoundary } from '../../components/design-system/states'
import { useMySessions } from '../../hooks/use-academic'
import { formatRange, plural } from '../../lib/format'
import { pendingEvaluation } from '../../lib/session-rules'

/** Evaluación y seguimiento: sesiones con intentos cerrados sin nota primero, luego las que están al día. */
export function EvaluationQueueView() {
  const q = useMySessions()
  return (
    <Page>
      <PageHeader title="Evaluación" description="Procesa las notas, deja comentarios y revisa el seguimiento de cada sesión." />
      <QueryBoundary query={q} loading="Cargando sesiones…">
        {(page) => {
          const conIntentos = page.items.filter((s) => s.finalizados + s.expirados > 0)
          const pendientes = conIntentos.filter(pendingEvaluation)
          const alDia = conIntentos.filter((s) => !pendingEvaluation(s))
          if (conIntentos.length === 0)
            return (
              <EmptyState icon="clipboard" title="Todavía no hay intentos cerrados">
                Cuando tus estudiantes entreguen un caso o se cierre una sesión, aparecerá aquí para evaluar.
              </EmptyState>
            )
          return (
            <>
              <Notice tone="info">
                Los estudiantes ven su nota y tus comentarios cuando la sesión está finalizada y la evaluación quedó registrada.
              </Notice>
              <Section title="Por evaluar" description="Sesiones con intentos cerrados que aún no tienen nota registrada.">
                {pendientes.length === 0 ? (
                  <p className="muted">Estás al día.</p>
                ) : (
                  <ul className="rows">
                    {pendientes.map((s) => (
                      <li key={s.id}>
                        <div className="row">
                          <div>
                            <div className="row-title">
                              <Link to={`/docente/sesiones/${s.id}?tab=resultados`}>{s.caso.nombre}</Link>
                            </div>
                            <div className="row-meta">
                              <SessionStatus estado={s.estado} />
                              <span>{s.espacio_academico.nombre}</span>
                              <span>{formatRange(s.inicio, s.fin)}</span>
                              <span className="tag tag-warn">
                                {plural(s.finalizados + s.expirados - s.calificados, 'intento sin nota', 'intentos sin nota')}
                              </span>
                            </div>
                          </div>
                          <div className="row-side">
                            <Link className="btn btn-primary btn-sm" to={`/docente/sesiones/${s.id}?tab=resultados`}>
                              Evaluar
                            </Link>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>
              <Section title="Al día">
                {alDia.length === 0 ? (
                  <p className="muted">Ninguna sesión con todas sus notas registradas todavía.</p>
                ) : (
                  <ul className="rows">
                    {alDia.map((s) => (
                      <li key={s.id}>
                        <div className="row">
                          <div>
                            <div className="row-title">
                              <Link to={`/docente/sesiones/${s.id}?tab=resultados`}>{s.caso.nombre}</Link>
                            </div>
                            <div className="row-meta">
                              <SessionStatus estado={s.estado} />
                              <span>{s.espacio_academico.nombre}</span>
                              <span>{plural(s.calificados, 'intento con nota', 'intentos con nota')}</span>
                            </div>
                          </div>
                          <div className="row-side">
                            <Link className="btn btn-secondary btn-sm" to={`/docente/sesiones/${s.id}?tab=seguimiento`}>
                              Seguimiento
                            </Link>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>
            </>
          )
        }}
      </QueryBoundary>
    </Page>
  )
}
