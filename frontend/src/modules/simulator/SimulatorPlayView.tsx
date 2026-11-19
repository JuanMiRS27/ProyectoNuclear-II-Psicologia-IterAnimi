// Orquestador del simulador (equivalente a simulator-play-view de Ágora con la dinámica de Iter Animi):
// una decisión a la vez, seleccionar ≠ confirmar, sin doble envío, selección conservada ante error,
// reanudación desde lo guardado y tiempo/progreso/cierre siempre según el servidor.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router'
import { ErrorState, LoadingState } from '../../components/design-system/states'
import { ConfirmDialog } from '../../components/ui/Dialog'
import { useCountdown } from '../../hooks/use-countdown'
import { useAttemptSync, useFinishAttempt, useQuestionnaire, useSaveAnswer } from '../../hooks/use-student'
import { useStaticVisualPackage } from '../../hooks/use-visual'
import { buildRuntime } from '../../lib/visual/runtime'
import { errorMessage } from '../../lib/errors'
import { ApiError } from '../../services/http-client'
import type { Cuestionario, Progreso } from '../../types/api'
import { DecisionPanel } from './DecisionPanel'
import { NarrativePanel } from './NarrativePanel'
import { ReviewPanel } from './ReviewPanel'
import { SimulatorActions } from './SimulatorActions'
import { SimulatorHeader } from './SimulatorHeader'
import { SimulatorStage } from './SimulatorStage'
import { buildSteps, countDecisions, initialStepIndex, nextStepIndex, savedFromQuestionnaire, type Step } from './steps'
import { useStageExpression } from './use-stage-expression'

const EXITS: Record<string, string> = {
  '/estudiante': 'Volver al inicio',
  '/estudiante/sesion': 'Volver a mi sesión',
  '/estudiante/aula': 'Volver a mi aula',
}

export function SimulatorPlayView() {
  const { participationId = '' } = useParams()
  const q = useQuestionnaire(participationId)
  if (q.isPending)
    return (
      <main className="page page-narrow" id="contenido">
        <LoadingState label="Preparando el caso…" />
      </main>
    )
  if (q.isError)
    return (
      <main className="page page-narrow" id="contenido">
        <ErrorState error={q.error} title="No se pudo abrir el caso" onRetry={() => q.refetch()} />
        <Link to="/estudiante/sesion">Volver a mi sesión</Link>
      </main>
    )
  if (q.data.estado !== 'EN_PROGRESO') return <Navigate to={`/estudiante/caso/${participationId}/cierre`} replace />
  return <Play key={q.data.participacion_id} data={q.data} />
}

function Play({ data }: { data: Cuestionario }) {
  const pid = data.participacion_id
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from
  const exitTo = from && EXITS[from] ? from : '/estudiante/sesion'
  const steps = useMemo(() => buildSteps(data), [data])
  const totalDecisions = countDecisions(steps)

  const [saved, setSaved] = useState<Record<string, string>>(() => savedFromQuestionnaire(data))
  const [selected, setSelected] = useState<Record<string, string>>(() => savedFromQuestionnaire(data))
  const [index, setIndex] = useState(() => initialStepIndex(steps, savedFromQuestionnaire(data)))
  const [progress, setProgress] = useState<Progreso>(data.progreso)
  const [deadline, setDeadline] = useState(() => Date.now() + data.tiempo_restante_segundos * 1000)
  const [error, setError] = useState<{ message: string; closed: boolean } | null>(null)
  const [confirmFinish, setConfirmFinish] = useState(false)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const sendingRef = useRef(false)

  const save = useSaveAnswer(pid)
  const finish = useFinishAttempt(pid)
  const fetchAttempt = useAttemptSync(pid)
  const step = steps[index]!

  // Paquete visual instalado en el frontend (opcional): sin él, el caso se juega con el personaje sin imagen.
  const escenarioIds = useMemo(() => data.escenarios.map((e) => e.id), [data])
  const visual = useStaticVisualPackage(escenarioIds)
  const runtime = useMemo(() => (visual.data ? buildRuntime(visual.data.manifest, data) : null), [visual.data, data])
  const sceneOf = (st: Step | undefined) =>
    st?.kind === 'decision' ? st.escenario.id : st?.kind === 'review' ? (lastSceneId(steps) ?? null) : (data.escenarios[0]?.id ?? null)
  const stage = useStageExpression(runtime, sceneOf(step))
  const sprite = stage.shown
    ? {
        expression: stage.shown.expression,
        motion: stage.shown.motion,
        src: visual.data?.spriteUrls[stage.shown.expression] ?? null,
        alt: `${runtime?.characterName || 'Personaje'}: ${runtime?.label(stage.shown.expression) ?? ''}`,
      }
    : null

  const goToClosed = useCallback(() => navigate(`/estudiante/caso/${pid}/cierre`, { replace: true }), [navigate, pid])

  const resync = useCallback(async () => {
    try {
      const p = await fetchAttempt()
      if (p.estado !== 'EN_PROGRESO') return goToClosed()
      setProgress(p.progreso)
      setDeadline(Date.now() + p.tiempo_restante_segundos * 1000)
    } catch {
      /* La próxima acción mostrará el error si persiste. */
    }
  }, [fetchAttempt, goToClosed])

  const secondsLeft = useCountdown(deadline, resync)

  // Al cambiar de escena, el foco va al título para que el lector de pantalla anuncie el cambio.
  useEffect(() => {
    headingRef.current?.focus()
    window.scrollTo({ top: 0 })
  }, [index])

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
      const next = nextStepIndex(steps, index, nextSaved)
      setSaved(nextSaved)
      // La reacción se aplica solo con la confirmación del servidor y no retrasa el avance.
      stage.react(r.opcion_id, step.escenario.id, sceneOf(steps[next]))
      void resync()
      setIndex(next)
    } catch (err) {
      const closed = err instanceof ApiError && (err.status === 409 || err.status === 401)
      setError({ message: errorMessage(err), closed })
    } finally {
      sendingRef.current = false
    }
  }

  const sceneLabel =
    step.kind === 'decision'
      ? { kicker: `Escena ${step.escenarioIndex + 1} de ${data.escenarios.length}`, title: step.escenario.titulo }
      : step.kind === 'prologue'
        ? { kicker: 'Antes de empezar', title: data.caso.nombre }
        : { kicker: 'Final del caso', title: 'Revisa y entrega' }

  return (
    <div className="sim">
      <SimulatorHeader title={data.caso.nombre} progress={progress} secondsLeft={secondsLeft} exitTo={exitTo} exitLabel={EXITS[exitTo]!} />

      <main className="sim-stage-wrap" id="contenido">
        <SimulatorStage kicker={sceneLabel.kicker} title={sceneLabel.title} sprite={sprite} characterName={runtime?.characterName || undefined} />

        <section className="sim-read" aria-labelledby="scene-heading">
          {step.kind === 'prologue' && (
            <>
              <h1 id="scene-heading" ref={headingRef} tabIndex={-1} className="sim-heading">
                {data.caso.nombre}
              </h1>
              <NarrativePanel texts={[data.caso.desarrollo_situacional, data.caso.historia]} />
              <SimulatorActions
                hint="Lee con calma: el tiempo corre desde que iniciaste el intento."
                primary={
                  <button type="button" className="btn btn-primary" onClick={() => setIndex(index + 1)}>
                    Comenzar
                  </button>
                }
              />
            </>
          )}

          {step.kind === 'decision' && (
            <form
              className="sim-decision"
              onSubmit={(e) => {
                e.preventDefault()
                void confirmAnswer()
              }}
            >
              <h1 id="scene-heading" ref={headingRef} tabIndex={-1} className="visually-hidden">
                Escena {step.escenarioIndex + 1}: {step.escenario.titulo}. Decisión {step.decisionIndex + 1} de {totalDecisions}.
              </h1>
              <NarrativePanel texts={[step.escenario.contexto]} />
              <DecisionPanel
                questionId={step.pregunta.id}
                prompt={step.pregunta.enunciado}
                position={`Decisión ${step.decisionIndex + 1} de ${totalDecisions}`}
                options={step.pregunta.opciones}
                selectedId={selected[step.pregunta.id] ?? null}
                savedId={saved[step.pregunta.id] ?? null}
                disabled={save.isPending}
                onSelect={(id) => {
                  setSelected((s) => ({ ...s, [step.pregunta.id]: id }))
                  setError(null)
                }}
              />
              {error && (
                <div className="notice notice-error" role="alert">
                  <div>
                    {error.message}
                    {error.closed ? (
                      <div style={{ marginTop: '0.5rem' }}>
                        <button type="button" className="btn btn-secondary btn-sm" onClick={goToClosed}>
                          Ver el estado de mi intento
                        </button>
                      </div>
                    ) : (
                      <> Tu selección se conservó: puedes volver a confirmarla.</>
                    )}
                  </div>
                </div>
              )}
              <DecisionActions
                selectedId={selected[step.pregunta.id] ?? null}
                savedId={saved[step.pregunta.id] ?? null}
                pending={save.isPending}
                onBack={index > 0 ? () => setIndex(index - 1) : undefined}
              />
            </form>
          )}

          {step.kind === 'review' && (
            <ReviewPanel
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
        onConfirm={() => finish.mutate(undefined, { onSuccess: goToClosed })}
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

function DecisionActions({ selectedId, savedId, pending, onBack }: { selectedId: string | null; savedId: string | null; pending: boolean; onBack?: () => void }) {
  const unchanged = selectedId !== null && selectedId === savedId
  return (
    <SimulatorActions
      back={
        onBack && (
          <button type="button" className="btn btn-quiet" onClick={onBack} disabled={pending}>
            Anterior
          </button>
        )
      }
      hint={!selectedId ? 'Elige una opción para continuar.' : unchanged ? 'Esta respuesta ya está guardada.' : 'Tu elección se guarda al confirmar.'}
      primary={
        <button type="submit" className="btn btn-primary" disabled={!selectedId || pending} aria-busy={pending || undefined}>
          {pending ? 'Guardando…' : unchanged ? 'Continuar' : 'Confirmar respuesta'}
        </button>
      }
    />
  )
}

function lastSceneId(steps: Step[]) {
  for (let i = steps.length - 1; i >= 0; i--) {
    const s = steps[i]!
    if (s.kind === 'decision') return s.escenario.id
  }
  return null
}
