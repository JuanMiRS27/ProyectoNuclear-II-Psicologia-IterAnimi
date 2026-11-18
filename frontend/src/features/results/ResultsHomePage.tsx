import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { studentApi } from '../../api/endpoints'
import { AttemptStatus } from '../../components/domainStatus'
import { Empty, ErrorState, Loading } from '../../components/states'
import { formatDecimal } from '../../lib/format'
import { CALIFICACION } from '../../lib/labels'

export function ResultsHomePage() {
  const q = useQuery({ queryKey: ['student-results'], queryFn: () => studentApi.results() })

  if (q.isPending)
    return (
      <main className="page page-narrow" id="contenido">
        <Loading label="Cargando tus resultados…" />
      </main>
    )
  if (q.isError)
    return (
      <main className="page page-narrow" id="contenido">
        <ErrorState error={q.error} title="No se pudieron cargar tus resultados" onRetry={() => q.refetch()} />
      </main>
    )

  const r = q.data
  return (
    <main className="page page-narrow" id="contenido">
      <div>
        <p className="muted">Resultados</p>
        <h1 style={{ marginTop: '0.35rem' }}>{r.caso_nombre}</h1>
        <p className="lede muted">La sesión terminó. Aquí puedes revisar cómo te fue en cada intento.</p>
      </div>

      {r.resultados.length === 0 ? (
        <Empty title="No registraste intentos en esta sesión">
          No iniciaste el caso durante la sesión, por lo que no hay calificación ni retroalimentación que mostrar.
        </Empty>
      ) : (
        <ul className="rows">
          {r.resultados.map((x) => (
            <li key={x.participacion_id}>
              <div className="row">
                <div>
                  <div className="row-title">Intento {x.numero_intento}</div>
                  <div className="row-meta">
                    <AttemptStatus estado={x.estado} motivo={x.motivo_cierre} />
                    <span>
                      {x.nota_final !== null
                        ? `Nota ${formatDecimal(x.nota_final)} de ${formatDecimal(x.escala_max)}`
                        : x.calificacion
                          ? CALIFICACION[x.calificacion]
                          : 'Evaluación pendiente'}
                    </span>
                  </div>
                </div>
                <div className="row-side">
                  {x.disponible ? (
                    <Link className="btn btn-primary btn-sm" to={`/resultados/${x.participacion_id}`}>
                      Ver resultado
                    </Link>
                  ) : (
                    <span className="small muted">Tu docente aún no registra esta evaluación.</span>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
