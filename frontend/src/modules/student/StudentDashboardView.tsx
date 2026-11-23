import { useState } from 'react'
import { Link } from 'react-router'
import { DashboardIntro, Figures, Page } from '../../components/design-system/layout'
import { ErrorState, LoadingState } from '../../components/design-system/states'
import { Status, type Fill } from '../../components/design-system/Status'
import { Icon } from '../../components/ui/Icon'
import { useNotifications } from '../../hooks/use-student'
import { formatDateTime, formatRange, formatTime, formatShortDay } from '../../lib/format'
import { agendaOf, STATUS_LABEL, type StudentSessionStatus, type StudentSessionView } from '../../lib/student-session-adapters'
import { SceneCharacter } from '../simulator/SceneCharacter'
import { StudentPrimaryAction } from './StudentPrimaryAction'
import { useStudentPortal } from './use-student-portal'

const FILL: Record<StudentSessionStatus, Fill> = {
  disponible: 'empty',
  en_curso: 'half',
  completado: 'full',
  plazo_cerrado: 'empty',
  finalizada: 'full',
}

export function StudentStatus({ status }: { status: StudentSessionStatus }) {
  return (
    <Status fill={FILL[status]} tone={status === 'plazo_cerrado' ? 'muted' : undefined}>
      {STATUS_LABEL[status]}
    </Status>
  )
}

/** Inicio del estudiante: la sesión prioritaria con su próxima acción, y una zona secundaria con agenda y avisos. */
export function StudentDashboardView() {
  const portal = useStudentPortal()
  const notices = useNotifications()
  const [now] = useState(() => Date.now())

  if (portal.isPending)
    return (
      <Page>
        <LoadingState label="Cargando tu sesión…" />
      </Page>
    )
  if (!portal.view) return <Page><ErrorState error={portal.error} title="No se pudo cargar tu sesión" onRetry={portal.refetch} /></Page>

  const v = portal.view
  const agenda = agendaOf(v)
  const recientes = (notices.data?.items ?? []).slice(0, 4)

  return (
    <Page className="dashboard dashboard-student">
      <DashboardIntro
        eyebrow={v.estudiante ? `Hola, ${v.estudiante.split(' ')[0]}` : 'Espacio del estudiante'}
        title={v.status === 'finalizada' ? 'Tus resultados ya están aquí' : 'Tu próxima decisión te espera'}
        description="Un momento para observar, comprender y descubrir nuevas perspectivas."
      />

      <div className="dash-student">
        <div className="dash-primary">
          <section className="hero-session" aria-labelledby="h-prioritaria">
            <div className="hero-scene" aria-hidden="true">
              <SceneCharacter className="hero-figure" decorative />
            </div>
            <div className="hero-body">
              <p className="eyebrow">{v.mode === 'results' ? 'Tu experiencia' : v.intentoEnCurso ? 'Continúa tu experiencia' : 'Tu siguiente experiencia'}</p>
              <p className="hero-kicker">
                {v.aula.nombre} ({v.aula.periodo})
              </p>
              <h2 id="h-prioritaria">{v.casoNombre}</h2>
              <div className="row-meta">
                <StudentStatus status={v.status} />
                {v.inicio && v.fin && <span>{formatRange(v.inicio, v.fin)}</span>}
                {v.lugar && <span>{v.lugar}</span>}
              </div>
              {v.mensaje && (
                <blockquote className="teacher-note">
                  <span>Mensaje de tu docente</span>
                  {v.mensaje}
                </blockquote>
              )}
              <StudentPrimaryAction view={v} from="/estudiante" />
            </div>
          </section>

          <Figures items={[
            { label: 'intentos realizados', value: v.intentosUsados, icon: 'clipboard' },
            ...(v.intentosAutorizados !== undefined ? [{ label: 'intentos autorizados', value: v.intentosAutorizados, icon: 'key' as const }] : []),
            ...(v.tiempoMaxMin !== undefined ? [{ label: 'por intento', value: `${v.tiempoMaxMin} min`, icon: 'clock' as const }] : []),
          ]} />
          <nav className="student-shortcuts" aria-label="Accesos a tu aprendizaje">
            <Link to="/estudiante/aula"><span className="figure-icon"><Icon name="classroom" /></span><span>Mi aula<small>{v.aula.nombre}</small></span><Icon name="chevronRight" size={16} /></Link>
            <Link to={v.mode === 'results' ? '/estudiante/resultados' : '/estudiante/sesion'}><span className="figure-icon"><Icon name={v.mode === 'results' ? 'chart' : 'calendar'} /></span><span>{v.mode === 'results' ? 'Mis resultados' : 'Mi sesión'}<small>{v.mode === 'results' ? 'Consulta tu recorrido' : 'Revisa los detalles de tu actividad'}</small></span><Icon name="chevronRight" size={16} /></Link>
          </nav>
        </div>

        <aside className="dash-side" aria-label="Agenda y avisos">
          {agenda.length > 0 && (
            <section className="side-card" aria-labelledby="h-agenda">
              <h2 id="h-agenda">
                <Icon name="calendar" /> Agenda
              </h2>
              <ol className="mini-agenda">
                {agenda.map((a) => (
                  <li key={a.label} className={new Date(a.when).getTime() < now ? 'past' : undefined}>
                    <span className="mini-when">
                      {formatShortDay(a.when)}
                      <strong>{formatTime(a.when)}</strong>
                    </span>
                    <span>{a.label}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}

          <section className="side-card" aria-labelledby="h-avisos">
            <h2 id="h-avisos">
              <Icon name="bell" /> Avisos recientes
            </h2>
            {notices.isPending ? (
              <LoadingState label="Cargando avisos…" />
            ) : notices.isError ? (
              <p className="small muted">No se pudieron cargar los avisos.</p>
            ) : recientes.length === 0 ? (
              <p className="small muted">No tienes avisos de esta convocatoria.</p>
            ) : (
              <ul className="mini-list">
                {recientes.map((n) => (
                  <li key={n.id}>
                    <strong>
                      {n.titulo} {!n.leida && <span className="tag">Nuevo</span>}
                    </strong>
                    <span className="small muted">{formatDateTime(n.creada_en)}</span>
                  </li>
                ))}
              </ul>
            )}
            <Link to="/estudiante/avisos" className="side-link">
              Ver todos los avisos
            </Link>
          </section>

          {v.mode === 'results' ? (
            <section className="side-card" aria-labelledby="h-retro">
              <h2 id="h-retro">
                <Icon name="message" /> Retroalimentación
              </h2>
              <p className="small">Tu docente puede haber dejado comentarios en tus intentos.</p>
              <Link to="/estudiante/retroalimentacion" className="side-link">
                Ver comentarios
              </Link>
            </section>
          ) : (
            <IntentosResumen view={v} />
          )}
        </aside>
      </div>
    </Page>
  )
}

function IntentosResumen({ view }: { view: StudentSessionView }) {
  return (
    <section className="side-card" aria-labelledby="h-intentos">
      <h2 id="h-intentos">
        <Icon name="clipboard" /> Tus intentos
      </h2>
      <p className="small">
        Has usado {view.intentosUsados} de {view.intentosAutorizados} {view.intentosAutorizados === 1 ? 'intento' : 'intentos'}.
      </p>
      {view.intentosAutorizados !== undefined && view.intentosAutorizados > 0 && (
        <meter className="attempt-meter" min={0} max={view.intentosAutorizados} value={view.intentosUsados} aria-label="Intentos usados de los autorizados" />
      )}
      <Link to="/estudiante/sesion" className="side-link">
        Ver detalle de la sesión
      </Link>
    </section>
  )
}
