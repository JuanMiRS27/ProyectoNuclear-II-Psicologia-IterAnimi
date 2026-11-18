import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { reportsApi, spacesApi } from '../../../api/endpoints'
import { Empty, ErrorState, Loading } from '../../../components/states'
import { plural } from '../../../lib/format'

export function SpacesPage() {
  const spaces = useQuery({ queryKey: ['spaces', 'active'], queryFn: () => spacesApi.list({ activo: true }) })
  const sessions = useQuery({ queryKey: ['my-sessions'], queryFn: () => reportsApi.mySessions() })

  let body
  if (spaces.isPending) body = <Loading label="Cargando aulas…" />
  else if (spaces.isError) body = <ErrorState error={spaces.error} title="No se pudieron cargar las aulas" onRetry={() => spaces.refetch()} />
  else if (spaces.data.items.length === 0)
    body = (
      <Empty title="No hay aulas activas">
        Las aulas (espacios académicos) las crea la administración del simulador. Cuando exista una, podrás asignarle casos aquí.
      </Empty>
    )
  else {
    const stats = new Map<string, { total: number; abiertas: number }>()
    for (const s of sessions.data?.items ?? []) {
      const st = stats.get(s.espacio_academico.id) ?? { total: 0, abiertas: 0 }
      st.total += 1
      if (s.estado === 'EN_CURSO') st.abiertas += 1
      stats.set(s.espacio_academico.id, st)
    }
    body = (
      <ul className="rows">
        {spaces.data.items.map((e) => {
          const st = stats.get(e.id)
          return (
            <li key={e.id}>
              <div className="row">
                <div>
                  <div className="row-title">
                    <Link to={`/aulas/${e.id}`}>{e.nombre}</Link>
                  </div>
                  <div className="row-meta">
                    <span>Periodo {e.periodo}</span>
                    {sessions.isSuccess && <span>{st ? plural(st.total, 'sesión tuya', 'sesiones tuyas') : 'Sin sesiones tuyas todavía'}</span>}
                    {st && st.abiertas > 0 && <span className="tag">{plural(st.abiertas, 'sesión en curso', 'sesiones en curso')}</span>}
                  </div>
                </div>
                <div className="row-side">
                  <Link className="btn btn-sm" to={`/aulas/${e.id}/asignar`}>
                    Asignar caso
                  </Link>
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    )
  }

  return (
    <main className="page" id="contenido">
      <div className="page-head">
        <div>
          <h1>Mis aulas</h1>
          <p className="lede">Elige un aula para ver sus sesiones o asignarle un caso a un grupo de estudiantes.</p>
        </div>
      </div>
      {body}
    </main>
  )
}
