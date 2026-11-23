import { Page, PageHeader } from '../../components/design-system/layout'
import { EmptyState, InlineError, QueryBoundary } from '../../components/design-system/states'
import { Button } from '../../components/ui/Button'
import { useMarkNotificationRead, useNotifications } from '../../hooks/use-student'
import { formatDateTime } from '../../lib/format'
import { TIPO_NOTIFICACION } from '../../lib/labels'

/** Avisos internos (CU29): solo los de la convocatoria del token. */
export function StudentNoticesView() {
  const q = useNotifications()
  const mark = useMarkNotificationRead()
  return (
    <Page width="narrow">
      <PageHeader title="Avisos" description="Convocatorias, cambios y resultados de esta sesión." />
      <InlineError error={mark.error} />
      <QueryBoundary query={q} loading="Cargando avisos…" errorTitle="No se pudieron cargar tus avisos">
        {(page) =>
          page.items.length === 0 ? (
            <EmptyState icon="bell" title="No tienes avisos">
              Aquí aparecerán los cambios de tu convocatoria y el aviso de resultados.
            </EmptyState>
          ) : (
            <ul className="rows">
              {page.items.map((n) => (
                <li key={n.id} className={n.leida ? 'is-read' : undefined}>
                  <div className="row">
                    <div>
                      <div className="row-title">
                        {n.titulo} {!n.leida && <span className="tag">Nuevo</span>}
                      </div>
                      <p className="small" style={{ marginTop: '0.25rem' }}>
                        {n.mensaje}
                      </p>
                      <div className="row-meta">
                        <span>{TIPO_NOTIFICACION[n.tipo] ?? n.tipo}</span>
                        <span>{formatDateTime(n.creada_en)}</span>
                      </div>
                    </div>
                    {!n.leida && (
                      <div className="row-side">
                        <Button size="sm" variant="quiet" icon="check" onClick={() => mark.mutate(n.id)} disabled={mark.isPending}>
                          Marcar como leído
                        </Button>
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )
        }
      </QueryBoundary>
    </Page>
  )
}
