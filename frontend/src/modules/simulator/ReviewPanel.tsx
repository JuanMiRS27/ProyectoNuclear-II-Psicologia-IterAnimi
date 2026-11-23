import type { RefObject } from 'react'
import { errorMessage } from '../../lib/errors'
import type { Progreso } from '../../types/api'
import { SimulatorActions } from './SimulatorActions'
import type { Step } from './steps'

/** Revisión final: progreso del servidor, decisiones pendientes con acceso directo y entrega. */
export function ReviewPanel({
  steps,
  saved,
  progress,
  headingRef,
  onJump,
  onFinish,
  finishError,
}: {
  steps: Step[]
  saved: Record<string, string>
  progress: Progreso
  headingRef: RefObject<HTMLHeadingElement | null>
  onJump: (i: number) => void
  onFinish: () => void
  finishError: unknown
}) {
  const pendientes = steps
    .map((s, i) => ({ s, i }))
    .filter((x): x is { s: Extract<Step, { kind: 'decision' }>; i: number } => x.s.kind === 'decision' && !saved[x.s.pregunta.id])
  const firstDecision = Math.max(0, steps.findIndex((s) => s.kind === 'decision'))
  return (
    <>
      <h1 id="scene-heading" ref={headingRef} tabIndex={-1} className="sim-heading">
        Revisión final
      </h1>
      <p className="sim-context">
        Has respondido {progress.respondidas} de {progress.total_preguntas} decisiones.
      </p>
      {pendientes.length > 0 ? (
        <div className="sim-pending">
          <p className="small muted">Quedan sin responder:</p>
          <ul className="rows">
            {pendientes.map(({ s, i }) => (
              <li key={s.pregunta.id}>
                <div className="row">
                  <div>
                    <div className="row-meta">
                      Escena {s.escenarioIndex + 1}, decisión {s.decisionIndex + 1}
                    </div>
                    <div>{s.pregunta.enunciado}</div>
                  </div>
                  <div className="row-side">
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => onJump(i)}>
                      Responder
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="muted">Todas las decisiones tienen una respuesta guardada. Puedes revisarlas antes de entregar.</p>
      )}
      {finishError ? <p className="field-error">{errorMessage(finishError)}</p> : null}
      <SimulatorActions
        back={
          <button type="button" className="btn btn-quiet" onClick={() => onJump(firstDecision)}>
            Revisar mis respuestas
          </button>
        }
        primary={
          <button type="button" className="btn btn-primary" onClick={onFinish}>
            Entregar caso
          </button>
        }
      />
    </>
  )
}
