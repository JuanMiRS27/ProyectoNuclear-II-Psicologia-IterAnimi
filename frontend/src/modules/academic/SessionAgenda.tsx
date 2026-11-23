import { useState } from 'react'
import { Link } from 'react-router'
import { SessionStatus } from '../../components/design-system/domain-status'
import { InlineError } from '../../components/design-system/states'
import { Glyph } from '../../components/design-system/Status'
import { Button, ButtonLink } from '../../components/ui/Button'
import { useStartSession } from '../../hooks/use-academic'
import { formatShortDay, formatTime, plural } from '../../lib/format'
import { canOpenNow, pendingEvaluation } from '../../lib/session-rules'
import type { SesionResumenReporte } from '../../types/api'

function Summary({ s }: { s: SesionResumenReporte }) {
  const cerrados = s.finalizados + s.expirados
  if (s.estado === 'SIN_INICIAR') return <>{plural(s.convocatorias_activas, 'estudiante convocado', 'estudiantes convocados')}</>
  if (s.estado === 'EN_CURSO')
    return (
      <>
        Han entrado {s.estudiantes_con_intento} de {plural(s.convocatorias_activas, 'convocado', 'convocados')}; {s.en_progreso} resolviendo ahora
      </>
    )
  return (
    <>
      {s.estudiantes_con_intento} de {s.convocatorias_activas} participaron; {s.calificados} de {plural(cerrados, 'intento', 'intentos')} con nota
    </>
  )
}

function OpenButton({ id }: { id: string }) {
  const start = useStartSession()
  return (
    <>
      <Button variant="primary" size="sm" icon="play" onClick={() => start.mutate(id)} pending={start.isPending} pendingLabel="Abriendo…">
        Abrir sesión
      </Button>
      <InlineError error={start.error} />
    </>
  )
}

/** Agenda cronológica de sesiones: cada fila muestra solo la acción válida para su estado. */
export function SessionAgenda({ sessions, showSpace = true }: { sessions: SesionResumenReporte[]; showSpace?: boolean }) {
  const [now] = useState(() => Date.now())
  return (
    <ol className="agenda">
      {sessions.map((s) => {
        const fill = s.estado === 'SIN_INICIAR' ? 'empty' : s.estado === 'EN_CURSO' ? 'half' : 'full'
        const evaluar = s.estado === 'FINALIZADO' && pendingEvaluation(s)
        return (
          <li key={s.id}>
            <div className="agenda-when">
              <strong>{formatTime(s.inicio)}</strong>
              {formatShortDay(s.inicio)}
            </div>
            <div className="agenda-rail">
              <Glyph fill={fill} size={18} />
            </div>
            <div className="agenda-body">
              <div>
                <div className="row-title">
                  <Link to={`/docente/sesiones/${s.id}`}>{s.caso.nombre}</Link>
                </div>
                <div className="row-meta">
                  <SessionStatus estado={s.estado} />
                  {showSpace && (
                    <span>
                      {s.espacio_academico.nombre} ({s.espacio_academico.periodo})
                    </span>
                  )}
                  <span>hasta {formatTime(s.fin)}</span>
                </div>
                <p className="small muted agenda-summary">
                  <Summary s={s} />
                </p>
              </div>
              <div className="btn-row">
                {canOpenNow(s, now) && <OpenButton id={s.id} />}
                {s.estado === 'EN_CURSO' && (
                  <ButtonLink size="sm" to={`/docente/sesiones/${s.id}?tab=convocados`}>
                    Seguir el avance
                  </ButtonLink>
                )}
                {s.estado === 'FINALIZADO' && (
                  <ButtonLink size="sm" variant={evaluar ? 'primary' : 'secondary'} to={`/docente/sesiones/${s.id}?tab=resultados`}>
                    {evaluar ? 'Evaluar intentos' : 'Ver resultados'}
                  </ButtonLink>
                )}
              </div>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
