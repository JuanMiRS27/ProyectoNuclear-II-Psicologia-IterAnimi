import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { reportsApi } from '../../api/endpoints'
import type { SesionResumenReporte } from '../../api/types'
import { useAuth } from '../../auth/useAuth'
import { Empty, ErrorState, Loading } from '../../components/states'
import { formatLongDate } from '../../lib/format'
import { SessionAgenda } from './SessionAgenda'

const byStart = (a: SesionResumenReporte, b: SesionResumenReporte) => +new Date(a.inicio) - +new Date(b.inicio)

export function DashboardPage() {
  const { session } = useAuth()
  const q = useQuery({ queryKey: ['my-sessions'], queryFn: () => reportsApi.mySessions() })
  const [today] = useState(() => new Date().toISOString())
  const nombre = session?.kind === 'staff' ? session.user.nombre_completo.split(' ')[0] : ''

  let body
  if (q.isPending) body = <Loading label="Cargando tus sesiones…" />
  else if (q.isError) body = <ErrorState error={q.error} title="No se pudieron cargar tus sesiones" onRetry={() => q.refetch()} />
  else {
    const items = q.data.items
    const enCurso = items.filter((s) => s.estado === 'EN_CURSO').sort(byStart)
    const proximas = items.filter((s) => s.estado === 'SIN_INICIAR').sort(byStart)
    const finalizadas = items
      .filter((s) => s.estado === 'FINALIZADO')
      .sort((a, b) => byStart(b, a))
      .slice(0, 5)
    const porEvaluar = items.filter((s) => s.estado === 'FINALIZADO' && s.calificados < s.finalizados + s.expirados).length

    body =
      items.length === 0 ? (
        <Empty
          title="Aún no tienes sesiones"
          action={
            <Link className="btn btn-primary" to="/aulas">
              Elegir un aula para asignar un caso
            </Link>
          }
        >
          Para que tus estudiantes resuelvan un caso, asígnalo a una de tus aulas con una fecha y una lista de convocados.
        </Empty>
      ) : (
        <>
          {porEvaluar > 0 && (
            <div className="notice notice-info">
              <div>
                <strong>
                  {porEvaluar === 1 ? 'Una sesión finalizada tiene' : `${porEvaluar} sesiones finalizadas tienen`} intentos sin nota
                  registrada.
                </strong>
                Abre sus resultados y procesa la evaluación para que los estudiantes puedan consultarla.
              </div>
            </div>
          )}
          <section className="section" aria-labelledby="h-ahora">
            <div className="section-head">
              <h2 id="h-ahora">En curso</h2>
              <p>Sesiones abiertas: los estudiantes pueden ingresar con su código.</p>
            </div>
            {enCurso.length ? <SessionAgenda sessions={enCurso} /> : <p className="muted">No hay sesiones abiertas en este momento.</p>}
          </section>
          <section className="section" aria-labelledby="h-proximas">
            <div className="section-head">
              <h2 id="h-proximas">Próximas</h2>
              <p>Ábrelas cuando llegue su hora de inicio.</p>
            </div>
            {proximas.length ? <SessionAgenda sessions={proximas} /> : <p className="muted">No tienes sesiones programadas.</p>}
          </section>
          {finalizadas.length > 0 && (
            <section className="section" aria-labelledby="h-finalizadas">
              <div className="section-head">
                <h2 id="h-finalizadas">Finalizadas recientemente</h2>
              </div>
              <SessionAgenda sessions={finalizadas} />
            </section>
          )}
        </>
      )
  }

  return (
    <main className="page" id="contenido">
      <div className="page-head">
        <div>
          <h1>Hola{nombre ? `, ${nombre}` : ''}</h1>
          <p className="lede">{formatLongDate(today)}</p>
        </div>
        <Link className="btn" to="/aulas">
          Asignar un caso
        </Link>
      </div>
      {body}
    </main>
  )
}
