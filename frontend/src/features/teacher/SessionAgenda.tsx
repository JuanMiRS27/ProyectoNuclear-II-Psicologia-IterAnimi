import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { sessionsApi } from '../../api/endpoints'
import type { SesionResumenReporte } from '../../api/types'
import { SessionStatus } from '../../components/domainStatus'
import { Glyph } from '../../components/Status'
import { InlineError } from '../../components/states'
import { formatShortDay, formatTime, plural } from '../../lib/format'
import { canOpenNow } from '../../lib/sessionRules'


function OpenSessionButton({ id }: { id: string }) {
  const qc = useQueryClient()
  const m = useMutation({ mutationFn: () => sessionsApi.start(id), onSuccess: () => qc.invalidateQueries() })
  return (
    <>
      <button type="button" className="btn btn-primary btn-sm" onClick={() => m.mutate()} disabled={m.isPending} aria-busy={m.isPending}>
        {m.isPending ? 'Abriendo…' : 'Abrir sesión'}
      </button>
      {m.error && <InlineError error={m.error} />}
    </>
  )
}

function Summary({ s }: { s: SesionResumenReporte }) {
  const cerrados = s.finalizados + s.expirados
  if (s.estado === 'SIN_INICIAR') return <>{plural(s.convocatorias_activas, 'estudiante convocado', 'estudiantes convocados')}</>
  if (s.estado === 'EN_CURSO')
    return (
      <>
        Han entrado {s.estudiantes_con_intento} de {plural(s.convocatorias_activas, 'convocado', 'convocados')}; {s.en_progreso}{' '}
        resolviendo ahora
      </>
    )
  return (
    <>
      {s.estudiantes_con_intento} de {s.convocatorias_activas} participaron; {s.calificados} de {plural(cerrados, 'intento', 'intentos')}{' '}
      con nota
    </>
  )
}

export function SessionAgenda({ sessions, showSpace = true }: { sessions: SesionResumenReporte[]; showSpace?: boolean }) {
  const [now] = useState(() => Date.now())
  return (
    <ol className="agenda">
      {sessions.map((s) => {
        const fill = s.estado === 'SIN_INICIAR' ? 'empty' : s.estado === 'EN_CURSO' ? 'half' : 'full'
        const evaluar = s.estado === 'FINALIZADO' && s.calificados < s.finalizados + s.expirados
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
                  <Link to={`/sesiones/${s.id}`}>{s.caso.nombre}</Link>
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
                <p className="small muted" style={{ marginTop: '0.35rem' }}>
                  <Summary s={s} />
                </p>
              </div>
              <div className="btn-row">
                {canOpenNow(s, now) && <OpenSessionButton id={s.id} />}
                {s.estado === 'EN_CURSO' && (
                  <Link className="btn btn-sm" to={`/sesiones/${s.id}?tab=convocados`}>
                    Seguir el avance
                  </Link>
                )}
                {s.estado === 'FINALIZADO' && (
                  <Link className={`btn btn-sm${evaluar ? ' btn-primary' : ''}`} to={`/sesiones/${s.id}?tab=resultados`}>
                    {evaluar ? 'Evaluar intentos' : 'Ver resultados'}
                  </Link>
                )}
              </div>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
