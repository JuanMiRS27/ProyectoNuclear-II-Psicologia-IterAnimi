import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { DataTable } from '../../components/design-system/DataTable'
import { CaseStatus } from '../../components/design-system/domain-status'
import { Page, PageHeader } from '../../components/design-system/layout'
import { EmptyState, QueryBoundary } from '../../components/design-system/states'
import { ButtonLink } from '../../components/ui/Button'
import { SearchField } from '../../components/ui/Field'
import { LinkTabs } from '../../components/ui/Tabs'
import { useCases } from '../../hooks/use-cases'
import { useSession } from '../../hooks/use-session'
import { formatDate } from '../../lib/format'
import type { EstadoCaso } from '../../types/api'

type Filter = 'todos' | EstadoCaso
const TABS: { id: Filter; label: string }[] = [
  { id: 'todos', label: 'Todos' },
  { id: 'PUBLICADO', label: 'Publicados' },
  { id: 'BORRADOR', label: 'Borradores' },
  { id: 'ARCHIVADO', label: 'Archivados' },
]

export function CasesListView() {
  const { session } = useSession()
  const canEdit = session?.kind === 'staff' && session.user.puede_crear_casos
  const [params] = useSearchParams()
  const filter = (TABS.find((t) => t.id === params.get('estado'))?.id ?? 'todos') as Filter
  const q = useCases(filter === 'todos' ? undefined : filter)
  const [search, setSearch] = useState('')

  return (
    <Page>
      <PageHeader
        title="Casos"
        description="Solo los casos publicados pueden programarse. Un caso publicado ya no se edita."
        actions={
          canEdit && (
            <ButtonLink to="/docente/casos/nuevo" variant="primary" icon="plus">
              Nuevo caso
            </ButtonLink>
          )
        }
      />
      <div className="toolbar">
        <LinkTabs label="Filtrar por estado" tabs={TABS} current={filter} param="estado" />
        <SearchField label="Buscar casos" value={search} onChange={setSearch} placeholder="Buscar por nombre" />
      </div>
      <QueryBoundary query={q} loading="Cargando casos…" errorTitle="No se pudieron cargar tus casos">
        {(page) => {
          const term = search.trim().toLowerCase()
          const rows = page.items.filter((c) => !term || c.nombre.toLowerCase().includes(term))
          return (
            <DataTable
              caption="Casos"
              rows={rows}
              rowKey={(c) => c.id}
              empty={
                <EmptyState
                  icon="book"
                  title={page.items.length === 0 ? (filter === 'todos' ? 'Aún no tienes casos' : 'No hay casos en este estado') : 'Ningún caso coincide'}
                  action={
                    canEdit && page.items.length === 0 && filter === 'todos' ? (
                      <ButtonLink to="/docente/casos/nuevo" variant="primary">
                        Crear o importar un caso
                      </ButtonLink>
                    ) : undefined
                  }
                >
                  {page.items.length === 0 && filter === 'todos' && !canEdit ? 'Tu cuenta no tiene permiso para crear casos. Pídelo a la administración.' : undefined}
                </EmptyState>
              }
              columns={[
                {
                  key: 'nombre',
                  header: 'Caso',
                  cell: (c) => (
                    <Link to={`/docente/casos/${c.id}`} className="cell-title">
                      {c.nombre}
                    </Link>
                  ),
                },
                { key: 'estado', header: 'Estado', cell: (c) => <CaseStatus estado={c.estado} /> },
                { key: 'tiempo', header: 'Tiempo estimado', numeric: true, cell: (c) => (c.tiempo_estimado_min ? `${c.tiempo_estimado_min} min` : '—') },
                { key: 'act', header: 'Actualizado', cell: (c) => formatDate(c.actualizado_en) },
              ]}
            />
          )
        }}
      </QueryBoundary>
    </Page>
  )
}
