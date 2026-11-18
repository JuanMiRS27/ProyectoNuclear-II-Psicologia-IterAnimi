import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router'
import { ApiError } from '../../api/client'
import { studentApi } from '../../api/endpoints'
import type { Cuestionario, Progreso } from '../../api/types'
import { ConfirmDialog } from '../../components/Dialog'
import { SceneCharacter } from '../../components/SceneCharacter'
import { ErrorState, Loading } from '../../components/states'
import { errorMessage } from '../../lib/errors'
import { formatCountdown, optionLetter } from '../../lib/format'
import { buildSteps, countDecisions, initialStepIndex, nextStepIndex, paragraphs, savedFromQuestionnaire, type Step } from './steps'

/** Cuenta atrás de presentación. La fecha límite y el cierre los decide siempre el servidor. */
function useCountdown(deadline: number, onZero: () => void) {
  const [now, setNow] = useState(() => Date.now())
  const zeroRef = useRef(onZero)
  const firedFor = useRef<number | null>(null)
  useEffect(() => {
    zeroRef.current = onZero
  })
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  const left = Math.max(0, Math.ceil((deadline - now) / 1000))
  useEffect(() => {
    if (left === 0 && firedFor.current !== deadline) {
      firedFor.current = deadline
      zeroRef.current()
    }
  }, [left, deadline])
  return left
}

export function SimulatorPage() {
  const { participationId = '' } = useParams()
  const q = useQuery({
    queryKey: ['questionnaire', participationId],
    queryFn: () => studentApi.questionnaire(participationId),
    staleTime: Infinity,
    gcTime: 0,
  })

  if (q.isPending)
    return (
      <main className="page page-narrow" id="contenido">
        <Loading label="Preparando el caso…" />
      </main>
    )
  if (q.isError)
    return (
      <main className="page page-narrow" id="contenido">
        <ErrorState error={q.error} title="No se pudo abrir el caso" onRetry={() => q.refetch()} />
        <Link to="/estudiante">Volver a mi sesión</Link>
      </main>
    )
  if (q.data.estado !== 'EN_PROGRESO') return <Navigate to={`/estudiante/caso/${participationId}/cierre`} replace />
  return <Simulator key={q.data.participacion_id} data={q.data} />
}

function Simulator({ data }: { data: Cuestionario }) {
  const pid = data.participacion_id
  const navigate = useNavigate()
  const qc = useQueryClient()
  const steps = useMemo(() => buildSteps(data), [data])
  const totalDecisions = countDecisions(steps)
  const totalScenes = data.escenarios.length

  // `saved`: lo que el servidor confirmó. `selected`: la elección en pantalla, aún sin confirmar.
  const [saved, setSaved] = useState<Record<string, string>>(() => savedFromQuestionnaire(data))
  const [selected, setSelected] = useState<Record<string, string>>(() => savedFromQuestionnaire(data))
  const [index, setIndex] = useState(() => initialStepIndex(steps, savedFromQuestionnaire(data)))
  const [progress, setProgress] = useState<Progreso>(data.progreso)
  const [deadline, setDeadline] = useState(() => Date.now() + data.tiempo_restante_segundos * 1000)
  const [error, setError] = useState<{ message: string; closed: boolean } | null>(null)
  const [confirmFinish, setConfirmFinish] = useState(false)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const sendingRef = useRef(false)

  const step = steps[index]!

  const goToClosed = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['student-attempts'] })
    navigate(`/estudiante/caso/${pid}/cierre`, { replace: true })
  }, [navigate, pid, qc])

  /** Sincroniza progreso y tiempo con el servidor; si el intento ya se cerró, sale del simulador. */
  const resync = useCallback(async () => {
    try {
      const p = await studentApi.participation(pid)
      if (p.estado !== 'EN_PROGRESO') return goToClosed()
      setProgress(p.progreso)
      setDeadline(Date.now() + p.tiempo_restante_segundos * 1000)
    } catch {
      /* La siguiente acción mostrará el error si persiste. */
    }
  }, [pid, goToClosed])

  const left = useCountdown(deadline, resync)

  // Al cambiar de escena, el foco va al título para que el lector de pantalla anuncie el cambio.
  useEffect(() => {
    headingRef.current?.focus()
    window.scrollTo({ top: 0 })
  }, [index])

  const save = useMutation({
    mutationFn: ({ preguntaId, opcionId }: { preguntaId: string; opcionId: string }) => studentApi.saveAnswer(pid, preguntaId, opcionId),
  })
  const finish = useMutation({ mutationFn: () => studentApi.finish(pid), onSuccess: goToClosed })

  const confirmAnswer = async () => {
    if (step.kind !== 'decision' || sendingRef.current) return
    const preguntaId = step.pregunta.id
    const opcionId = selected[preguntaId]
    if (!opcionId) return
    if (saved[preguntaId] === opcionId) {
      setIndex(Math.min(index + 1, steps.length - 1))
      return
    }
    sendingRef.current = true
    setError(null)
    try {
      const r = await save.mutateAsync({ preguntaId, opcionId })
      const nextSaved = { ...saved, [preguntaId]: r.opcion_id }
      setSaved(nextSaved)
      void resync()
      setIndex(nextStepIndex(steps, index, nextSaved))
    } catch (err) {
      // La selección se conserva para reintentar. Un 409 significa que el intento ya no admite cambios.
      const closed = err instanceof ApiError && (err.status === 409 || err.status === 401)
      setError({ message: errorMessage(err), closed })
    } finally {
      sendingRef.current = false
    }
  }

  const lowTime = left <= 300
  const pct = progress.total_preguntas ? Math.floor((progress.respondidas / progress.total_preguntas) * 100) : 0

  return (
    <div className="sim">
      <header className="sim-top">
        <div className="sim-top-inner">
          <Link className="sim-back" to="/estudiante">
            Volver a mi sesión
          </Link>
          <p className="sim-title">{data.caso.nombre}</p>
          <div className="sim-meta">
            <span>
              Respondidas <strong>{progress.respondidas}</strong> de {progress.total_preguntas}
            </span>
            {(
              <span className={lowTime ? 'sim-time-low' : undefined} role="timer" aria-live={lowTime ? 'polite' : 'off'}>
                Tiempo <strong>{formatCountdown(left)}</strong>
              </span>
            )}
          </div>
        </div>
        <div
          className="sim-progress"
          role="progressbar"
          aria-label="Decisiones respondidas"
          aria-valuemin={0}
          aria-valuemax={progress.total_preguntas}
          aria-valuenow={progress.respondidas}
        >
          <span style={{ width: `${pct}%` }} />
        </div>
      </header>

      <main className="sim-stage-wrap" id="contenido">
        <div className="sim-stage" aria-hidden={step.kind === 'review' ? true : undefined}>
          <div className="sim-scene-label">
            {step.kind === 'decision' ? (
              <>
                <span>
                  Escena {step.escenarioIndex + 1} de {totalScenes}
                </span>
                {step.escenario.titulo}
              </>
            ) : step.kind === 'prologue' ? (
              <>
                <span>Antes de empezar</span>
                {data.caso.nombre}
              </>
            ) : (
              <>
                <span>Final del caso</span>
                Revisa y entrega
              </>
            )}
          </div>
          <SceneCharacter />
        </div>

        <section className="sim-read" aria-labelledby="scene-heading">
          {step.kind === 'prologue' && (
            <Prologue data={data} headingRef={headingRef} onStart={() => setIndex(index + 1)} />
          )}

          {step.kind === 'decision' && (
            <Decision
              step={step}
              totalDecisions={totalDecisions}
              headingRef={headingRef}
              selectedId={selected[step.pregunta.id] ?? null}
              savedId={saved[step.pregunta.id] ?? null}
              disabled={save.isPending}
              onSelect={(id) => {
                setSelected((s) => ({ ...s, [step.pregunta.id]: id }))
                setError(null)
              }}
              onConfirm={confirmAnswer}
              onBack={index > 0 ? () => setIndex(index - 1) : undefined}
              error={error}
              onClosed={goToClosed}
            />
          )}

          {step.kind === 'review' && (
            <Review
              steps={steps}
              saved={saved}
              progress={progress}
              headingRef={headingRef}
              onJump={setIndex}
              onFinish={() => setConfirmFinish(true)}
              finishError={finish.error}
            />
          )}
        </section>
      </main>

      <ConfirmDialog
        open={confirmFinish}
        title="¿Entregar el caso?"
        confirmLabel="Entregar"
        pending={finish.isPending}
        error={finish.error ? <p className="field-error">{errorMessage(finish.error)}</p> : undefined}
        onConfirm={() => finish.mutate()}
        onClose={() => setConfirmFinish(false)}
      >
        <p>
          Has respondido {progress.respondidas} de {progress.total_preguntas} decisiones.
          {progress.pendientes > 0 && ' Las que queden sin responder contarán como no respondidas.'}
        </p>
        <p>Después de entregar ya no podrás cambiar tus respuestas.</p>
      </ConfirmDialog>
    </div>
  )
}

type HeadingRef = React.RefObject<HTMLHeadingElement | null>

function Prologue({ data, headingRef, onStart }: { data: Cuestionario; headingRef: HeadingRef; onStart: () => void }) {
  return (
    <>
      <h1 id="scene-heading" ref={headingRef} tabIndex={-1} style={{ fontSize: 'var(--fs-xl)' }}>
        {data.caso.nombre}
      </h1>
      <div className="sim-context sim-context-scroll">
        {paragraphs(data.caso.desarrollo_situacional).map((p, i) => (
          <p key={`d${i}`}>{p}</p>
        ))}
        {paragraphs(data.caso.historia).map((p, i) => (
          <p key={`h${i}`}>{p}</p>
        ))}
      </div>
      <div className="sim-actions">
        <span className="hint">Lee con calma: el tiempo corre desde que iniciaste el intento.</span>
        <button type="button" className="btn btn-primary" onClick={onStart}>
          Comenzar
        </button>
      </div>
    </>
  )
}

function Decision({
  step,
  totalDecisions,
  headingRef,
  selectedId,
  savedId,
  disabled,
  onSelect,
  onConfirm,
  onBack,
  error,
  onClosed,
}: {
  step: Extract<Step, { kind: 'decision' }>
  totalDecisions: number
  headingRef: HeadingRef
  selectedId: string | null
  savedId: string | null
  disabled: boolean
  onSelect: (id: string) => void
  onConfirm: () => void
  onBack?: () => void
  error: { message: string; closed: boolean } | null
  onClosed: () => void
}) {
  const opciones = [...step.pregunta.opciones].sort((a, b) => a.orden - b.orden)
  const unchanged = selectedId !== null && selectedId === savedId
  const contexto = paragraphs(step.escenario.contexto)
  return (
    <>
      <h1 id="scene-heading" ref={headingRef} tabIndex={-1} className="visually-hidden">
        Escena {step.escenarioIndex + 1}: {step.escenario.titulo}. Decisión {step.decisionIndex + 1} de {totalDecisions}.
      </h1>
      {contexto.length > 0 && (
        <div className="sim-context sim-context-scroll">
          {contexto.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          onConfirm()
        }}
        style={{ display: 'grid', gap: '1.25rem' }}
      >
        <fieldset className="choices">
          <legend className="sim-prompt" style={{ marginBottom: '0.9rem', padding: 0, paddingTop: contexto.length ? '1.25rem' : 0 }}>
            <span className="sim-prompt-label">
              Decisión {step.decisionIndex + 1} de {totalDecisions}
            </span>
            {step.pregunta.enunciado}
          </legend>
          {opciones.map((o, i) => (
            <label key={o.id} className="choice">
              <input
                type="radio"
                name={`p-${step.pregunta.id}`}
                value={o.id}
                checked={selectedId === o.id}
                onChange={() => onSelect(o.id)}
                disabled={disabled}
              />
              <span className="choice-letter" aria-hidden="true">
                {optionLetter(i)}
              </span>
              <span className="choice-text">
                <span className="visually-hidden">Opción {optionLetter(i)}: </span>
                {o.texto}
                {savedId === o.id && <span className="choice-saved">Respuesta guardada</span>}
              </span>
              <span className="choice-mark" aria-hidden="true">
                ✓
              </span>
            </label>
          ))}
        </fieldset>

        {error && (
          <div className="notice notice-error" role="alert">
            <div>
              {error.message}
              {error.closed ? (
                <div style={{ marginTop: '0.5rem' }}>
                  <button type="button" className="btn btn-sm" onClick={onClosed}>
                    Ver el estado de mi intento
                  </button>
                </div>
              ) : (
                <> Tu selección se conservó: puedes volver a confirmarla.</>
              )}
            </div>
          </div>
        )}

        <div className="sim-actions">
          {onBack ? (
            <button type="button" className="btn btn-quiet" onClick={onBack} disabled={disabled}>
              Anterior
            </button>
          ) : (
            <span />
          )}
          <span className="hint" aria-live="polite">
            {!selectedId ? 'Elige una opción para continuar.' : unchanged ? 'Esta respuesta ya está guardada.' : 'Tu elección se guarda al confirmar.'}
          </span>
          <button type="submit" className="btn btn-primary" disabled={!selectedId || disabled} aria-busy={disabled}>
            {disabled ? 'Guardando…' : unchanged ? 'Continuar' : 'Confirmar respuesta'}
          </button>
        </div>
      </form>
    </>
  )
}

function Review({
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
  headingRef: HeadingRef
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
      <h1 id="scene-heading" ref={headingRef} tabIndex={-1} style={{ fontSize: 'var(--fs-xl)' }}>
        Revisión final
      </h1>
      <p className="sim-context" style={{ display: 'block' }}>
        Has respondido {progress.respondidas} de {progress.total_preguntas} decisiones.
      </p>
      {pendientes.length > 0 ? (
        <div style={{ display: 'grid', gap: '0.6rem' }}>
          <p className="small muted">Quedan sin responder:</p>
          <ul className="rows">
            {pendientes.map(({ s, i }) => (
              <li key={s.pregunta.id}>
                <div className="row">
                  <div>
                    <div className="row-meta" style={{ marginTop: 0 }}>
                      Escena {s.escenarioIndex + 1}, decisión {s.decisionIndex + 1}
                    </div>
                    <div>{s.pregunta.enunciado}</div>
                  </div>
                  <div className="row-side">
                    <button type="button" className="btn btn-sm" onClick={() => onJump(i)}>
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
      <div className="sim-actions">
        <button type="button" className="btn btn-quiet" onClick={() => onJump(firstDecision)}>
          Revisar mis respuestas
        </button>
        <button type="button" className="btn btn-primary" onClick={onFinish}>
          Entregar caso
        </button>
      </div>
    </>
  )
}
