import { useState } from 'react'
import { Link } from 'react-router'
import { Figures, Page, PageHeader, Section } from '../../components/design-system/layout'
import { EmptyState, QueryBoundary } from '../../components/design-system/states'
import { ButtonLink } from '../../components/ui/Button'
import { Icon, type IconName } from '../../components/ui/Icon'
import { useMySessions } from '../../hooks/use-academic'
import { useSession } from '../../hooks/use-session'
import { formatLongDate, formatTime, plural } from '../../lib/format'
import { canOpenNow, pendingEvaluation } from '../../lib/session-rules'
import type { SesionResumenReporte } from '../../types/api'
import { SessionAgenda } from '../academic/SessionAgenda'

const byStart = (a: SesionResumenReporte, b: SesionResumenReporte) => +new Date(a.inicio) - +new Date(b.inicio)

interface Todo {
  key: string
  icon: IconName
  title: string
  detail: string
  to: string
  cta: string
}

/** Panel docente: qué organizar y evaluar ahora, luego la agenda. */
export function TeacherDashboardView() {
  const { session } = useSession()
  const q = useMySessions()
  const [now] = useState(() => Date.now())
  const nombre = session?.kind === 'staff' ? session.user.nombre_completo.split(' ')[0] : ''

  return (
    <Page>
      <PageHeader
        title={`Hola${nombre ? `, ${nombre}` : ''}`}
        description={formatLongDate(new Date(now).toISOString())}
        actions={
          <ButtonLink to="/docente/aulas" icon="plus" variant="primary">
            Programar sesión
          </ButtonLink>
        }
      />
      <QueryBoundary query={q} loading="Cargando tus sesiones…" errorTitle="No se pudieron cargar tus sesiones">
        {(page) => {
          const items = page.items
          if (items.length === 0)
            return (
              <EmptyState
                icon="calendar"
                title="Aún no tienes sesiones"
                action={
                  <ButtonLink to="/docente/aulas" variant="primary">
                    Elegir un aula
                  </ButtonLink>
                }
              >
                Para que tus estudiantes resuelvan un caso, prográmalo en una de tus aulas con una fecha y una lista de convocados.
              </EmptyState>
            )
          const enCurso = items.filter((s) => s.estado === 'EN_CURSO').sort(byStart)
          const proximas = items.filter((s) => s.estado === 'SIN_INICIAR').sort(byStart)
          const finalizadas = items.filter((s) => s.estado === 'FINALIZADO').sort((a, b) => byStart(b, a))
          const porEvaluar = finalizadas.filter(pendingEvaluation)

          const todos: Todo[] = [
            ...proximas
              .filter((s) => canOpenNow(s, now))
              .map((s) => ({
                key: `open-${s.id}`,
                icon: 'play' as const,
                title: `Abrir «${s.caso.nombre}»`,
                detail: `Programada para las ${formatTime(s.inicio)} en ${s.espacio_academico.nombre}. Los estudiantes no pueden entrar hasta que la abras.`,
                to: `/docente/sesiones/${s.id}`,
                cta: 'Ir a la sesión',
              })),
            ...enCurso.map((s) => ({
              key: `live-${s.id}`,
              icon: 'users' as const,
              title: `«${s.caso.nombre}» está en curso`,
              detail: `${s.en_progreso} resolviendo ahora; ${s.estudiantes_con_intento} de ${s.convocatorias_activas} han entrado.`,
              to: `/docente/sesiones/${s.id}?tab=convocados`,
              cta: 'Seguir el avance',
            })),
            ...porEvaluar.map((s) => ({
              key: `eval-${s.id}`,
              icon: 'clipboard' as const,
              title: `Evaluar «${s.caso.nombre}»`,
              detail: `${plural(s.finalizados + s.expirados - s.calificados, 'intento cerrado', 'intentos cerrados')} sin nota registrada.`,
              to: `/docente/sesiones/${s.id}?tab=resultados`,
              cta: 'Evaluar',
            })),
          ]

          return (
            <div className="dash-teacher">
              <div className="dash-teacher-figures">
                <Figures
                  items={[
                    { label: 'en curso', value: enCurso.length },
                    { label: 'próximas', value: proximas.length },
                    { label: 'por evaluar', value: porEvaluar.length },
                    { label: 'finalizadas', value: finalizadas.length },
                  ]}
                />
              </div>

              <div className="dash-teacher-todo">
                <Section title="Para hacer ahora" description="Acciones que dependen de ti, según el estado real de tus sesiones.">
                  {todos.length === 0 ? (
                    <p className="empty-line">Nada pendiente por ahora. Aquí aparecerán las sesiones que puedes abrir y los intentos cerrados sin nota.</p>
                  ) : (
                    <ul className="todo-list">
                      {todos.map((t) => (
                        <li key={t.key}>
                          <span className="todo-icon">
                            <Icon name={t.icon} />
                          </span>
                          <div>
                            <strong>{t.title}</strong>
                            <p className="small muted">{t.detail}</p>
                          </div>
                          <Link className="btn btn-secondary btn-sm" to={t.to}>
                            {t.cta}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </Section>
              </div>

              <div className="two-col dash-teacher-agenda">
                <Section title="Próximas sesiones">
                  {proximas.length ? <SessionAgenda sessions={proximas.slice(0, 5)} /> : <p className="muted">No tienes sesiones programadas.</p>}
                </Section>
                <Section title="Finalizadas recientemente" actions={<Link to="/docente/sesiones">Ver todas</Link>}>
                  {finalizadas.length ? (
                    <SessionAgenda sessions={finalizadas.slice(0, 4)} />
                  ) : (
                    <p className="muted">Todavía no has finalizado ninguna sesión.</p>
                  )}
                </Section>
              </div>
            </div>
          )
        }}
      </QueryBoundary>
    </Page>
  )
}
