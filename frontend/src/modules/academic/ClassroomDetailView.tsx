import { Link, useParams } from 'react-router'
import { DataTable } from '../../components/design-system/DataTable'
import { Figures, Page, PageHeader, Section } from '../../components/design-system/layout'
import { EmptyState, ErrorState, InlineError, LoadingState, QueryBoundary } from '../../components/design-system/states'
import { Button, ButtonLink } from '../../components/ui/Button'
import { useExportSpace, useSpace, useSpaceReport } from '../../hooks/use-academic'
import { formatDecimal, formatPercent } from '../../lib/format'
import type { SesionResumenReporte } from '../../types/api'
import { SessionAgenda } from './SessionAgenda'

const byStart = (a: SesionResumenReporte, b: SesionResumenReporte) => +new Date(a.inicio) - +new Date(b.inicio)

/** Detalle del aula para el docente: solo sus sesiones en ella, casos usados y acceso a programar. */
export function ClassroomDetailView() {
  const { spaceId = '' } = useParams()
  const space = useSpace(spaceId)
  const report = useSpaceReport(spaceId)
  const exportCsv = useExportSpace(spaceId)

  if (space.isPending)
    return (
      <Page>
        <LoadingState />
      </Page>
    )
  if (space.isError)
    return (
      <Page>
        <ErrorState error={space.error} onRetry={() => space.refetch()} />
      </Page>
    )
  const e = space.data

  return (
    <Page>
      <PageHeader
        crumbs={[{ label: 'Aulas', to: '/docente/aulas' }]}
        title={e.nombre}
        meta={<span>Periodo {e.periodo}</span>}
        description="Aquí ves solo las sesiones que tú programaste en esta aula."
        actions={
          <>
            {report.data && report.data.sesiones_registradas > 0 && (
              <Button icon="download" onClick={() => exportCsv.mutate()} pending={exportCsv.isPending} pendingLabel="Preparando…">
                CSV
              </Button>
            )}
            {e.activo && (
              <ButtonLink to={`/docente/aulas/${e.id}/programar`} variant="primary" icon="plus">
                Programar sesión
              </ButtonLink>
            )}
          </>
        }
      />
      <InlineError error={exportCsv.error} />
      <QueryBoundary query={report} loading="Cargando sesiones del aula…" errorTitle="No se pudieron cargar las sesiones">
        {(r) => {
          const items = r.sesiones.items
          if (items.length === 0)
            return (
              <EmptyState
                icon="calendar"
                title="Aún no has programado sesiones en esta aula"
                action={
                  e.activo && (
                    <ButtonLink to={`/docente/aulas/${e.id}/programar`} variant="primary">
                      Programar una sesión
                    </ButtonLink>
                  )
                }
              >
                Programar una sesión fija el caso, la ventana, el tiempo máximo y la lista de estudiantes convocados.
              </EmptyState>
            )
          const abiertas = items.filter((s) => s.estado !== 'FINALIZADO').sort(byStart)
          const cerradas = items.filter((s) => s.estado === 'FINALIZADO').sort((a, b) => byStart(b, a))
          return (
            <>
              <Figures
                items={[
                  { label: 'sesiones', value: r.sesiones_registradas },
                  { label: 'intentos registrados', value: r.totales.intentos },
                  { label: 'evaluaciones registradas', value: r.totales.evaluaciones_registradas },
                  ...(r.promedio_porcentaje_escala !== null ? [{ label: 'promedio sobre la escala', value: formatPercent(r.promedio_porcentaje_escala) }] : []),
                ]}
              />
              <Section title="En curso y próximas">
                {abiertas.length ? <SessionAgenda sessions={abiertas} showSpace={false} /> : <p className="muted">No hay sesiones abiertas ni programadas.</p>}
              </Section>
              {cerradas.length > 0 && (
                <Section title="Finalizadas">
                  <SessionAgenda sessions={cerradas} showSpace={false} />
                </Section>
              )}
              {r.casos_utilizados.length > 0 && (
                <Section title="Casos usados en esta aula">
                  <DataTable
                    caption="Casos usados en esta aula"
                    rows={r.casos_utilizados}
                    rowKey={(c) => c.id}
                    columns={[
                      { key: 'caso', header: 'Caso', cell: (c) => <Link to={`/docente/casos/${c.id}`}>{c.nombre}</Link> },
                      { key: 'ses', header: 'Sesiones', numeric: true, cell: (c) => c.sesiones },
                      { key: 'ev', header: 'Evaluaciones', numeric: true, cell: (c) => c.evaluaciones_registradas },
                      {
                        key: 'prom',
                        header: 'Promedio',
                        numeric: true,
                        cell: (c) => (c.promedio ? `${formatDecimal(c.promedio)} / ${formatDecimal(c.escala_max)}` : '—'),
                      },
                    ]}
                  />
                </Section>
              )}
            </>
          )
        }}
      </QueryBoundary>
    </Page>
  )
}
