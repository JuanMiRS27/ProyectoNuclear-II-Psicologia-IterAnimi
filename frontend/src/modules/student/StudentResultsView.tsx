import { Link } from 'react-router'
import { AttemptStatus } from '../../components/design-system/domain-status'
import { Notice, Page, PageHeader } from '../../components/design-system/layout'
import { EmptyState, QueryBoundary } from '../../components/design-system/states'
import { Status } from '../../components/design-system/Status'
import { useSession } from '../../hooks/use-session'
import { useStudentResults } from '../../hooks/use-student'
import { formatDecimal } from '../../lib/format'
import { CALIFICACION } from '../../lib/labels'

/** Resultados: historial de intentos de esta convocatoria, separando los evaluados de los que esperan revisión. */
export function StudentResultsView() {
  const { session } = useSession()
  const q = useStudentResults()

  if (session?.kind !== 'results')
    return (
      <Page width="narrow">
        <PageHeader title="Resultados" />
        <EmptyState icon="clock" title="Tus resultados aparecerán cuando termine la sesión">
          Mientras la sesión sigue en curso no se muestran notas. Cuando tu docente la finalice, vuelve a ingresar con tu correo y el mismo código
          de acceso: entrarás directamente a tus resultados.
        </EmptyState>
      </Page>
    )

  return (
    <Page width="narrow">
      <QueryBoundary query={q} loading="Cargando tus resultados…" errorTitle="No se pudieron cargar tus resultados">
        {(r) => {
          const evaluados = r.resultados.filter((x) => x.disponible)
          const pendientes = r.resultados.filter((x) => !x.disponible)
          return (
            <>
              <PageHeader title="Resultados" meta={<span>{r.caso_nombre}</span>} description={`${r.espacio_academico.nombre} (${r.espacio_academico.periodo})`} />
              {r.resultados.length === 0 && (
                <EmptyState title="No registraste intentos en esta sesión">
                  No iniciaste el caso durante la sesión, así que no hay calificación ni retroalimentación que mostrar.
                </EmptyState>
              )}
              {evaluados.length > 0 && (
                <section className="section" aria-labelledby="h-evaluados">
                  <h2 id="h-evaluados">Evaluados</h2>
                  <ul className="rows">
                    {evaluados.map((x) => (
                      <li key={x.participacion_id}>
                        <div className="row">
                          <div>
                            <div className="row-title">
                              <Link to={`/estudiante/resultados/${x.participacion_id}`}>Intento {x.numero_intento}</Link>
                            </div>
                            <div className="row-meta">
                              <AttemptStatus estado={x.estado} motivo={x.motivo_cierre} />
                              <span>
                                {x.nota_final !== null
                                  ? `Nota ${formatDecimal(x.nota_final)} de ${formatDecimal(x.escala_max)}`
                                  : x.calificacion
                                    ? CALIFICACION[x.calificacion]
                                    : '—'}
                              </span>
                            </div>
                          </div>
                          <div className="row-side">
                            <Link className="btn btn-primary btn-sm" to={`/estudiante/resultados/${x.participacion_id}`}>
                              Ver resultado
                            </Link>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {pendientes.length > 0 && (
                <section className="section" aria-labelledby="h-pendientes">
                  <h2 id="h-pendientes">En revisión</h2>
                  <Notice tone="warn">Tu docente aún no ha registrado la evaluación de estos intentos. Vuelve a consultarlos más tarde.</Notice>
                  <ul className="rows">
                    {pendientes.map((x) => (
                      <li key={x.participacion_id}>
                        <div className="row">
                          <div>
                            <div className="row-title">Intento {x.numero_intento}</div>
                            <div className="row-meta">
                              <AttemptStatus estado={x.estado} motivo={x.motivo_cierre} />
                              <Status fill="empty" tone="muted">
                                Pendiente de revisión
                              </Status>
                            </div>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )
        }}
      </QueryBoundary>
    </Page>
  )
}
