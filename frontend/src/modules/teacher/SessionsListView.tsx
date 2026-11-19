import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { DataTable } from '../../components/design-system/DataTable'
import { SessionStatus } from '../../components/design-system/domain-status'
import { Page, PageHeader } from '../../components/design-system/layout'
import { EmptyState, QueryBoundary } from '../../components/design-system/states'
import { ButtonLink } from '../../components/ui/Button'
import { SearchField } from '../../components/ui/Field'
import { LinkTabs } from '../../components/ui/Tabs'
import { useMySessions } from '../../hooks/use-academic'
import { formatRange } from '../../lib/format'
import { pendingEvaluation } from '../../lib/session-rules'
import type { EstadoSesion, SesionResumenReporte } from '../../types/api'

type Filter = 'todas' | EstadoSesion

const TABS: { id: Filter; label: string }[] = [
  { id: 'todas', label: 'Todas' },
  { id: 'EN_CURSO', label: 'En curso' },
  { id: 'SIN_INICIAR', label: 'Próximas' },
  { id: 'FINALIZADO', label: 'Finalizadas' },
]

/** Todas las sesiones del docente, con filtro por estado y búsqueda por caso o aula. */
export function SessionsListView() {
  const q = useMySessions()
  const [params] = useSearchParams()
  const filter = (TABS.find((t) => t.id === params.get('estado'))?.id ?? 'todas') as Filter
  const [search, setSearch] = useState('')

  const filterRows = useMemo(
    () => (items: SesionResumenReporte[]) => {
      const term = search.trim().toLowerCase()
      return items
        .filter((s) => filter === 'todas' || s.estado === filter)
        .filter((s) => !term || `${s.caso.nombre} ${s.espacio_academico.nombre}`.toLowerCase().includes(term))
        .sort((a, b) => +new Date(b.inicio) - +new Date(a.inicio))
    },
    [filter, search],
  )

  return (
    <Page>
      <PageHeader
        title="Sesiones"
        description="Cada sesión es un caso programado en un aula con su lista de convocados."
        actions={
          <ButtonLink to="/docente/aulas" icon="plus" variant="primary">
            Programar sesión
          </ButtonLink>
        }
      />
      <div className="toolbar">
        <LinkTabs label="Filtrar por estado" tabs={TABS} current={filter} param="estado" />
        <SearchField label="Buscar sesiones" value={search} onChange={setSearch} placeholder="Buscar por caso o aula" />
      </div>
      <QueryBoundary query={q} loading="Cargando sesiones…" errorTitle="No se pudieron cargar tus sesiones">
        {(page) => {
          const rows = filterRows(page.items)
          return (
            <DataTable
              caption="Sesiones"
              rows={rows}
              rowKey={(s) => s.id}
              empty={
                <EmptyState icon="calendar" title={page.items.length === 0 ? 'Aún no tienes sesiones' : 'Ninguna sesión coincide'}>
                  {page.items.length === 0 ? 'Programa una desde el detalle de un aula.' : 'Prueba con otro filtro o término de búsqueda.'}
                </EmptyState>
              }
              columns={[
                {
                  key: 'caso',
                  header: 'Caso',
                  cell: (s) => (
                    <>
                      <Link to={`/docente/sesiones/${s.id}`} className="cell-title">
                        {s.caso.nombre}
                      </Link>
                      <div className="small muted">{formatRange(s.inicio, s.fin)}</div>
                    </>
                  ),
                },
                { key: 'aula', header: 'Aula', cell: (s) => `${s.espacio_academico.nombre} (${s.espacio_academico.periodo})` },
                { key: 'estado', header: 'Estado', cell: (s) => <SessionStatus estado={s.estado} /> },
                {
                  key: 'part',
                  header: 'Participación',
                  numeric: true,
                  cell: (s) => `${s.estudiantes_con_intento} de ${s.convocatorias_activas}`,
                },
                {
                  key: 'nota',
                  header: 'Con nota',
                  numeric: true,
                  cell: (s) => (
                    <>
                      {s.calificados} de {s.finalizados + s.expirados}
                      {s.estado === 'FINALIZADO' && pendingEvaluation(s) && (
                        <div>
                          <span className="tag tag-warn">Por evaluar</span>
                        </div>
                      )}
                    </>
                  ),
                },
              ]}
            />
          )
        }}
      </QueryBoundary>
    </Page>
  )
}
