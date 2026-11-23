import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { Page, PageHeader } from '../../components/design-system/layout'
import { EmptyState, QueryBoundary } from '../../components/design-system/states'
import { ButtonLink } from '../../components/ui/Button'
import { SearchField } from '../../components/ui/Field'
import { Icon } from '../../components/ui/Icon'
import { useMySessions, useSpaces } from '../../hooks/use-academic'
import { plural } from '../../lib/format'

/** Aulas activas para el docente, con el número de sesiones propias en cada una. */
export function ClassroomsView() {
  const spaces = useSpaces({ activo: true })
  const sessions = useMySessions()
  const [search, setSearch] = useState('')

  const stats = useMemo(() => {
    const m = new Map<string, { total: number; abiertas: number }>()
    for (const s of sessions.data?.items ?? []) {
      const st = m.get(s.espacio_academico.id) ?? { total: 0, abiertas: 0 }
      st.total += 1
      if (s.estado === 'EN_CURSO') st.abiertas += 1
      m.set(s.espacio_academico.id, st)
    }
    return m
  }, [sessions.data])

  return (
    <Page>
      <PageHeader title="Aulas" description="Elige un aula para ver tus sesiones en ella o programar una nueva." />
      <QueryBoundary query={spaces} loading="Cargando aulas…" errorTitle="No se pudieron cargar las aulas">
        {(page) => {
          const term = search.trim().toLowerCase()
          const rows = page.items.filter((e) => !term || `${e.nombre} ${e.periodo}`.toLowerCase().includes(term))
          if (page.items.length === 0)
            return (
              <EmptyState icon="classroom" title="No hay aulas activas">
                Las aulas las crea la administración del simulador. Cuando exista una, podrás programar sesiones en ella.
              </EmptyState>
            )
          return (
            <>
              {page.items.length > 6 && <SearchField label="Buscar aulas" value={search} onChange={setSearch} placeholder="Buscar por nombre o periodo" />}
              <ul className="classroom-grid">
                {rows.map((e) => {
                  const st = stats.get(e.id)
                  return (
                    <li key={e.id} className="classroom-item">
                      <span className="classroom-icon">
                        <Icon name="classroom" size={22} />
                      </span>
                      <div className="classroom-text">
                        <Link to={`/docente/aulas/${e.id}`} className="cell-title">
                          {e.nombre}
                        </Link>
                        <div className="row-meta">
                          <span>Periodo {e.periodo}</span>
                          {sessions.isSuccess && <span>{st ? plural(st.total, 'sesión tuya', 'sesiones tuyas') : 'Sin sesiones tuyas'}</span>}
                          {st && st.abiertas > 0 && <span className="tag">{plural(st.abiertas, 'en curso', 'en curso')}</span>}
                        </div>
                      </div>
                      <ButtonLink size="sm" to={`/docente/aulas/${e.id}/programar`} icon="plus">
                        Programar
                      </ButtonLink>
                    </li>
                  )
                })}
              </ul>
              {rows.length === 0 && <p className="muted">Ningún aula coincide con la búsqueda.</p>}
            </>
          )
        }}
      </QueryBoundary>
    </Page>
  )
}
