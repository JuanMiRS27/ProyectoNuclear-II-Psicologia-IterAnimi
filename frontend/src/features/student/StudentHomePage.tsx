import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { notificationsApi, studentApi } from '../../api/endpoints'
import type { Participacion } from '../../api/types'
import { useAuth } from '../../auth/useAuth'
import { ConfirmDialog } from '../../components/Dialog'
import { AttemptStatus } from '../../components/domainStatus'
import { Status } from '../../components/Status'
import { ErrorState, InlineError, Loading } from '../../components/states'
import { formatDateTime, formatRange, plural } from '../../lib/format'

function CaseState({ attempts }: { attempts: Participacion[] }) {
  if (attempts.some((a) => a.estado === 'EN_PROGRESO')) return <Status fill="half">En curso</Status>
  if (attempts.length) return <Status fill="full">Completado</Status>
  return <Status fill="empty">Pendiente</Status>
}

export function StudentHomePage() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const sesionId = session?.kind === 'student' ? session.sesionId : ''
  const acceso = useQuery({ queryKey: ['student-session', sesionId], queryFn: () => studentApi.session(sesionId) })
  const attempts = useQuery({ queryKey: ['student-attempts'], queryFn: () => studentApi.participations() })
  const avisos = useQuery({ queryKey: ['notifications'], queryFn: () => notificationsApi.list() })
  const [confirmStart, setConfirmStart] = useState(false)

  const start = useMutation({
    mutationFn: () => studentApi.startOrResume(sesionId),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ['student-attempts'] })
      navigate(`/estudiante/caso/${p.id}`)
    },
  })

  if (acceso.isPending || attempts.isPending)
    return (
      <main className="page page-narrow" id="contenido">
        <Loading label="Cargando tu sesión…" />
      </main>
    )
  if (acceso.isError || attempts.isError)
    return (
      <main className="page page-narrow" id="contenido">
        <ErrorState
          error={acceso.error ?? attempts.error}
          title="No se pudo cargar tu sesión"
          onRetry={() => {
            acceso.refetch()
            attempts.refetch()
          }}
        />
      </main>
    )

  const a = acceso.data
  const list = [...attempts.data].sort((x, y) => y.numero_intento - x.numero_intento)
  const enCurso = list.find((p) => p.estado === 'EN_PROGRESO')
  const usados = list.length
  const restantes = Math.max(0, a.intentos_autorizados - usados)
  const puedeNuevo = !enCurso && a.puede_iniciar_participacion && restantes > 0

  let action
  if (enCurso) {
    action = (
      <>
        <Link className="btn btn-primary" to={`/estudiante/caso/${enCurso.id}`}>
          Continuar caso
        </Link>
        <p className="small muted">
          Tu tiempo sigue corriendo: termina a las {formatDateTime(enCurso.fecha_limite)}; llevas {enCurso.progreso.respondidas} de{' '}
          {enCurso.progreso.total_preguntas} decisiones.
        </p>
      </>
    )
  } else if (puedeNuevo) {
    action = (
      <>
        <button type="button" className="btn btn-primary" onClick={() => setConfirmStart(true)}>
          {usados ? 'Iniciar otro intento' : 'Iniciar caso'}
        </button>
        <p className="small muted">
          Tendrás {a.sesion.tiempo_max_min} minutos desde que inicies. {plural(restantes, 'intento disponible', 'intentos disponibles')}.
        </p>
      </>
    )
  } else if (usados) {
    action = (
      <div className="notice notice-info">
        <div>
          <strong>Ya resolviste este caso.</strong>
          Los resultados estarán disponibles cuando tu docente finalice la sesión. Entonces vuelve a ingresar con tu correo y el mismo código.
        </div>
      </div>
    )
  } else {
    action = (
      <div className="notice notice-info">
        <div>
          <strong>Ya no es posible iniciar el caso.</strong>
          El plazo de ingreso terminó el {formatDateTime(a.sesion.limite_ingreso)}; si crees que es un error, comunícate con tu docente.
        </div>
      </div>
    )
  }

  return (
    <main className="page page-narrow" id="contenido">
      <div>
        <p className="muted">Hola, {a.nombre_completo}</p>
        <h1 style={{ marginTop: '0.35rem' }}>{a.sesion.caso_nombre}</h1>
        <div className="row-meta" style={{ marginTop: '0.6rem' }}>
          <CaseState attempts={list} />
          <span>{formatRange(a.sesion.inicio, a.sesion.fin)}</span>
          {a.sesion.lugar && <span>{a.sesion.lugar}</span>}
        </div>
      </div>

      {a.sesion.mensaje && (
        <section className="panel" aria-labelledby="h-msg">
          <h2 id="h-msg" style={{ fontSize: 'var(--fs-md)', marginBottom: '0.4rem' }}>
            Mensaje de tu docente
          </h2>
          <p>{a.sesion.mensaje}</p>
        </section>
      )}

      <section className="section" aria-label="Qué hacer ahora">
        <div className="btn-row" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
          {action}
        </div>
        <InlineError error={start.error} />
      </section>

      {list.length > 0 && (
        <section className="section" aria-labelledby="h-intentos">
          <h2 id="h-intentos">Tus intentos</h2>
          <ul className="rows">
            {list.map((p) => (
              <li key={p.id}>
                <div className="row">
                  <div>
                    <div className="row-title">Intento {p.numero_intento}</div>
                    <div className="row-meta">
                      <AttemptStatus estado={p.estado} motivo={p.motivo_cierre} />
                      <span>
                        {p.progreso.respondidas} de {p.progreso.total_preguntas} decisiones respondidas
                      </span>
                      <span>Iniciado {formatDateTime(p.inicio)}</span>
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {avisos.data && avisos.data.items.length > 0 && (
        <section className="section" aria-labelledby="h-avisos">
          <h2 id="h-avisos">Avisos</h2>
          <ul className="rows">
            {avisos.data.items.map((n) => (
              <li key={n.id}>
                <div className="row">
                  <div>
                    <div className="row-title">
                      {n.titulo} {!n.leida && <span className="tag">Nuevo</span>}
                    </div>
                    <p className="small" style={{ marginTop: '0.25rem' }}>
                      {n.mensaje}
                    </p>
                    <div className="row-meta">{formatDateTime(n.creada_en)}</div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <ConfirmDialog
        open={confirmStart}
        title="¿Iniciar el caso ahora?"
        confirmLabel="Iniciar"
        pending={start.isPending}
        error={<InlineError error={start.error} />}
        onConfirm={() => start.mutate()}
        onClose={() => setConfirmStart(false)}
      >
        <p>
          Al iniciar empieza a correr tu tiempo de {a.sesion.tiempo_max_min} minutos y se usa uno de tus intentos. El tiempo no se detiene
          si cierras la página, pero podrás retomar el caso donde lo dejaste.
        </p>
      </ConfirmDialog>
    </main>
  )
}
