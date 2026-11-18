import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { spacesApi } from '../../../api/endpoints'
import type { SesionResumenReporte } from '../../../api/types'
import { Empty, ErrorState, InlineError, Loading } from '../../../components/states'
import { formatDecimal, formatPercent } from '../../../lib/format'
import { SessionAgenda } from '../SessionAgenda'

const byStart = (a: SesionResumenReporte, b: SesionResumenReporte) => +new Date(a.inicio) - +new Date(b.inicio)

export function SpaceDetailPage() {
  const { spaceId = '' } = useParams()
  const space = useQuery({ queryKey: ['space', spaceId], queryFn: () => spacesApi.get(spaceId) })
  const report = useQuery({ queryKey: ['space-report', spaceId], queryFn: () => spacesApi.report(spaceId) })
  const exportCsv = useMutation({ mutationFn: () => spacesApi.exportCsv(spaceId) })

  if (space.isPending) return <main className="page" id="contenido"><Loading /></main>
  if (space.isError)
    return (
      <main className="page" id="contenido">
        <ErrorState error={space.error} onRetry={() => space.refetch()} />
      </main>
    )

  const e = space.data
  let body
  if (report.isPending) body = <Loading label="Cargando sesiones del aula…" />
  else if (report.isError) body = <ErrorState error={report.error} title="No se pudieron cargar las sesiones" onRetry={() => report.refetch()} />
  else {
    const r = report.data
    const items = r.sesiones.items
    const abiertas = items.filter((s) => s.estado !== 'FINALIZADO').sort(byStart)
    const cerradas = items.filter((s) => s.estado === 'FINALIZADO').sort((a, b) => byStart(b, a))
    body =
      items.length === 0 ? (
        <Empty
          title="Aún no has asignado casos en esta aula"
          action={
            <Link className="btn btn-primary" to={`/aulas/${e.id}/asignar`}>
              Asignar un caso
            </Link>
          }
        >
          Asignar un caso crea una sesión con fecha, tiempo máximo y la lista de estudiantes convocados.
        </Empty>
      ) : (
        <>
          <dl className="figures">
            <div>
              <dt>sesiones</dt>
              <dd>{r.sesiones_registradas}</dd>
            </div>
            <div>
              <dt>intentos registrados</dt>
              <dd>{r.totales.intentos}</dd>
            </div>
            <div>
              <dt>evaluaciones registradas</dt>
              <dd>{r.totales.evaluaciones_registradas}</dd>
            </div>
            {r.promedio_porcentaje_escala !== null && (
              <div>
                <dt>promedio sobre la escala</dt>
                <dd>{formatPercent(r.promedio_porcentaje_escala)}</dd>
              </div>
            )}
          </dl>

          <section className="section" aria-labelledby="h-activas">
            <div className="section-head">
              <h2 id="h-activas">En curso y próximas</h2>
            </div>
            {abiertas.length ? <SessionAgenda sessions={abiertas} showSpace={false} /> : <p className="muted">No hay sesiones abiertas ni programadas.</p>}
          </section>

          {cerradas.length > 0 && (
            <section className="section" aria-labelledby="h-cerradas">
              <div className="section-head">
                <h2 id="h-cerradas">Finalizadas</h2>
              </div>
              <SessionAgenda sessions={cerradas} showSpace={false} />
            </section>
          )}

          {r.casos_utilizados.length > 0 && (
            <section className="section" aria-labelledby="h-casos">
              <h2 id="h-casos">Casos usados en esta aula</h2>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Caso</th>
                      <th className="num">Sesiones</th>
                      <th className="num">Evaluaciones</th>
                      <th className="num">Promedio</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.casos_utilizados.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <Link to={`/casos/${c.id}`}>{c.nombre}</Link>
                        </td>
                        <td className="num">{c.sesiones}</td>
                        <td className="num">{c.evaluaciones_registradas}</td>
                        <td className="num">
                          {c.promedio ? `${formatDecimal(c.promedio)} / ${formatDecimal(c.escala_max)}` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )
  }

  return (
    <main className="page" id="contenido">
      <div className="page-head">
        <div>
          <div className="crumbs">
            <Link to="/aulas">Mis aulas</Link>
          </div>
          <h1>{e.nombre}</h1>
          <p className="lede">
            Periodo {e.periodo}. Aquí ves solo las sesiones que tú programaste en esta aula.
          </p>
        </div>
        <div className="btn-row">
          {report.data && report.data.sesiones_registradas > 0 && (
            <button type="button" className="btn" onClick={() => exportCsv.mutate()} disabled={exportCsv.isPending}>
              {exportCsv.isPending ? 'Preparando…' : 'Descargar CSV'}
            </button>
          )}
          {e.activo && (
            <Link className="btn btn-primary" to={`/aulas/${e.id}/asignar`}>
              Asignar caso
            </Link>
          )}
        </div>
      </div>
      {exportCsv.error && <InlineError error={exportCsv.error} />}
      {body}
    </main>
  )
}
