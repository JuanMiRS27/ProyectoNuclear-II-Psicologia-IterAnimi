import { useSearchParams } from 'react-router'
import { DataTable } from '../../components/design-system/DataTable'
import { Notice, Page, PageHeader } from '../../components/design-system/layout'
import { EmptyState, InlineError, QueryBoundary } from '../../components/design-system/states'
import { Status } from '../../components/design-system/Status'
import { Button } from '../../components/ui/Button'
import { LinkTabs } from '../../components/ui/Tabs'
import { useDeliveries, useRetryDelivery } from '../../hooks/use-admin'
import { formatDateTime } from '../../lib/format'
import { ESTADO_ENTREGA, TIPO_NOTIFICACION } from '../../lib/labels'
import type { EstadoEntrega } from '../../types/api'

type Filter = 'todas' | EstadoEntrega
const TABS: { id: Filter; label: string }[] = [
  { id: 'todas', label: 'Todas' },
  { id: 'FALLIDA', label: 'Fallidas' },
  { id: 'PENDIENTE', label: 'Pendientes' },
  { id: 'ENVIADA', label: 'Enviadas' },
  { id: 'CANCELADA', label: 'Canceladas' },
]

/** Entregas de correo (CU30): estado y reintento de las fallidas. La API no expone direcciones ni contenido. */
export function DeliveriesView() {
  const [params] = useSearchParams()
  const filter = (TABS.find((t) => t.id === params.get('estado'))?.id ?? 'todas') as Filter
  const q = useDeliveries(filter === 'todas' ? undefined : filter)
  const retry = useRetryDelivery()
  return (
    <Page>
      <PageHeader title="Entregas de correo" description="Cada aviso con correo genera una entrega. Las fallidas se pueden reintentar: se revalidan antes de enviar." />
      <Notice tone="info">
        Si el envío de correo está desactivado en el servidor (NOTIFICATIONS_EMAIL_ENABLED=false), las entregas quedan pendientes y no sale ningún mensaje.
      </Notice>
      <LinkTabs label="Filtrar por estado" tabs={TABS} current={filter} param="estado" />
      <InlineError error={retry.error} />
      <QueryBoundary query={q} loading="Cargando entregas…" errorTitle="No se pudieron cargar las entregas">
        {(page) => (
          <DataTable
            caption="Entregas de correo"
            rows={page.items}
            rowKey={(d) => d.id}
            empty={<EmptyState icon="mail" title="No hay entregas con este estado" />}
            columns={[
              { key: 't', header: 'Aviso', cell: (d) => TIPO_NOTIFICACION[d.tipo] ?? d.tipo },
              {
                key: 'e',
                header: 'Estado',
                cell: (d) => (
                  <Status fill={d.estado === 'ENVIADA' ? 'full' : d.estado === 'FALLIDA' ? 'alert' : d.estado === 'EN_PROCESO' ? 'half' : 'empty'} tone={d.estado === 'FALLIDA' ? 'alert' : d.estado === 'CANCELADA' ? 'muted' : undefined}>
                    {ESTADO_ENTREGA[d.estado]}
                  </Status>
                ),
              },
              { key: 'i', header: 'Intentos', numeric: true, cell: (d) => d.intentos },
              { key: 'c', header: 'Creada', cell: (d) => formatDateTime(d.creada_en) },
              { key: 'u', header: 'Último error', cell: (d) => (d.ultimo_error ? <span className="small">{d.ultimo_error}</span> : '—') },
              {
                key: 'a',
                header: 'Acciones',
                srOnlyHeader: true,
                cell: (d) =>
                  d.estado === 'FALLIDA' ? (
                    <Button size="sm" icon="refresh" onClick={() => retry.mutate(d.id)} disabled={retry.isPending}>
                      Reintentar
                    </Button>
                  ) : null,
              },
            ]}
          />
        )}
      </QueryBoundary>
    </Page>
  )
}
