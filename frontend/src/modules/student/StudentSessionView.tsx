import { AttemptStatus } from '../../components/design-system/domain-status'
import { Definitions, Notice, Page, PageHeader, Panel, Section } from '../../components/design-system/layout'
import { ErrorState, LoadingState } from '../../components/design-system/states'
import { formatDateTime, formatRange } from '../../lib/format'
import { StudentStatus } from './StudentDashboardView'
import { StudentPrimaryAction } from './StudentPrimaryAction'
import { useStudentPortal } from './use-student-portal'

/** Mi sesión: disponibilidad según el servidor, ventana, intentos y la acción que corresponde. */
export function StudentSessionView() {
  const portal = useStudentPortal()
  if (portal.isPending)
    return (
      <Page>
        <LoadingState label="Cargando tu sesión…" />
      </Page>
    )
  if (!portal.view)
    return (
      <Page>
        <ErrorState error={portal.error} title="No se pudo cargar tu sesión" onRetry={portal.refetch} />
      </Page>
    )
  const v = portal.view
  const attempts = [...portal.attempts].sort((a, b) => b.numero_intento - a.numero_intento)

  return (
    <Page>
      <PageHeader
        crumbs={[{ label: v.aula.nombre, to: '/estudiante/aula' }]}
        title={v.casoNombre}
        meta={
          <>
            <StudentStatus status={v.status} />
            {v.inicio && v.fin && <span>{formatRange(v.inicio, v.fin)}</span>}
          </>
        }
      />

      <div className="split">
        <div className="split-main">
          <StudentPrimaryAction view={v} from="/estudiante/sesion" />
          {v.mensaje && (
            <blockquote className="teacher-note">
              <span>Mensaje de tu docente</span>
              {v.mensaje}
            </blockquote>
          )}
          {v.mode === 'live' && (
            <Section title="Tus intentos">
              {attempts.length === 0 ? (
                <p className="muted">Todavía no has iniciado ningún intento.</p>
              ) : (
                <ul className="rows">
                  {attempts.map((p) => (
                    <li key={p.id}>
                      <div className="row">
                        <div>
                          <div className="row-title">Intento {p.numero_intento}</div>
                          <div className="row-meta">
                            <AttemptStatus estado={p.estado} motivo={p.motivo_cierre} />
                            <span>
                              {p.progreso.respondidas} de {p.progreso.total_preguntas} decisiones
                            </span>
                            <span>Iniciado {formatDateTime(p.inicio)}</span>
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          )}
        </div>
        <Panel tone="mist" className="split-side">
          {v.mode === 'live' ? (
            <Definitions
              items={[
                { term: 'Aula', value: `${v.aula.nombre} (${v.aula.periodo})` },
                ...(v.lugar ? [{ term: 'Lugar', value: v.lugar }] : []),
                { term: 'Tiempo por intento', value: `${v.tiempoMaxMin} minutos` },
                { term: 'Puedes empezar hasta', value: v.limiteIngreso ? formatDateTime(v.limiteIngreso) : '—' },
                { term: 'Intentos', value: `${v.intentosUsados} de ${v.intentosAutorizados}` },
              ]}
            />
          ) : (
            <Notice tone="info">La sesión terminó. Desde aquí solo puedes consultar tus resultados.</Notice>
          )}
        </Panel>
      </div>
    </Page>
  )
}
