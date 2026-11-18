import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { casesApi } from '../../../api/endpoints'
import type { EstadoCaso } from '../../../api/types'
import { useAuth } from '../../../auth/useAuth'
import { CaseStatus } from '../../../components/domainStatus'
import { Empty, ErrorState, Loading } from '../../../components/states'
import { formatDate } from '../../../lib/format'

const FILTROS: { id: EstadoCaso | ''; label: string }[] = [
  { id: '', label: 'Todos' },
  { id: 'PUBLICADO', label: 'Publicados' },
  { id: 'BORRADOR', label: 'Borradores' },
  { id: 'ARCHIVADO', label: 'Archivados' },
]

export function CasesPage() {
  const { session } = useAuth()
  const puedeCrear = session?.kind === 'staff' && session.user.puede_crear_casos
  const [params] = useSearchParams()
  const estado = (FILTROS.find((f) => f.id === params.get('estado'))?.id ?? '') as EstadoCaso | ''
  const q = useQuery({ queryKey: ['cases', estado], queryFn: () => casesApi.list(estado ? { estado } : {}) })

  let body
  if (q.isPending) body = <Loading label="Cargando casos…" />
  else if (q.isError) body = <ErrorState error={q.error} title="No se pudieron cargar tus casos" onRetry={() => q.refetch()} />
  else if (q.data.items.length === 0)
    body = (
      <Empty
        title={estado ? 'No hay casos en este estado' : 'Aún no tienes casos'}
        action={
          puedeCrear && !estado ? (
            <Link className="btn btn-primary" to="/casos/importar">
              Importar un caso
            </Link>
          ) : undefined
        }
      >
        {!estado && (puedeCrear ? 'Importa un caso en formato CaseDSL para revisarlo, validarlo y publicarlo.' : 'Tu cuenta no tiene permiso para crear casos. Pídelo a la administración.')}
      </Empty>
    )
  else
    body = (
      <ul className="rows">
        {q.data.items.map((c) => (
          <li key={c.id}>
            <div className="row">
              <div>
                <div className="row-title">
                  <Link to={`/casos/${c.id}`}>{c.nombre}</Link>
                </div>
                <div className="row-meta">
                  <CaseStatus estado={c.estado} />
                  {c.tiempo_estimado_min && <span>{c.tiempo_estimado_min} min estimados</span>}
                  <span>Actualizado el {formatDate(c.actualizado_en)}</span>
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    )

  return (
    <main className="page" id="contenido">
      <div className="page-head">
        <div>
          <h1>Mis casos</h1>
          <p className="lede">Solo los casos publicados pueden asignarse a un aula. Un caso publicado ya no se edita.</p>
        </div>
        {puedeCrear && (
          <Link className="btn btn-primary" to="/casos/importar">
            Importar caso
          </Link>
        )}
      </div>
      <nav className="tabs" aria-label="Filtrar por estado">
        {FILTROS.map((f) => (
          <Link key={f.id} to={f.id ? `?estado=${f.id}` : '?'} replace aria-current={estado === f.id ? 'page' : undefined}>
            {f.label}
          </Link>
        ))}
      </nav>
      {body}
    </main>
  )
}
