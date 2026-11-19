import { useMemo, useState } from 'react'
import type { VisualRuntime } from '../../lib/visual/runtime'
import type { CasoDetalle } from '../../types/api'
import { DecisionPanel } from './DecisionPanel'
import { NarrativePanel } from './NarrativePanel'
import { SimulatorActions } from './SimulatorActions'
import { SimulatorStage } from './SimulatorStage'
import { useStageExpression } from './use-stage-expression'

interface PreviewStep {
  escenarioId: string
  escenarioTitulo: string
  contexto: string | null
  escenarioIndex: number
  preguntaId: string
  enunciado: string
  opciones: { id: string; orden: number; texto: string }[]
}

/**
 * Vista previa jugable para el docente con los mismos componentes que ve el estudiante.
 * «Probar reacción» es local: no crea intentos, no envía respuestas y no toca notas.
 */
export function ScenePreview({ caso, runtime, spriteUrls }: { caso: CasoDetalle; runtime: VisualRuntime; spriteUrls: Record<string, string | null> }) {
  const steps = useMemo<PreviewStep[]>(() => {
    const out: PreviewStep[] = []
    ;[...caso.escenarios]
      .sort((a, b) => a.orden - b.orden)
      .forEach((e, ei) =>
        [...e.preguntas]
          .sort((a, b) => a.orden - b.orden)
          .forEach((p) =>
            out.push({
              escenarioId: e.id,
              escenarioTitulo: e.titulo,
              contexto: e.contexto,
              escenarioIndex: ei,
              preguntaId: p.id,
              enunciado: p.enunciado,
              opciones: p.opciones.map((o) => ({ id: o.id, orden: o.orden, texto: o.texto })),
            }),
          ),
      )
    return out
  }, [caso])
  const [index, setIndex] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [tested, setTested] = useState<string | null>(null)
  const step = steps[Math.min(index, steps.length - 1)]
  const stage = useStageExpression(runtime, step?.escenarioId ?? null)

  if (!step) return <p className="muted small">Añade escenas y decisiones al caso para probar las reacciones.</p>

  const shown = stage.shown
  const sprite = shown
    ? { expression: shown.expression, motion: shown.motion, src: spriteUrls[shown.expression] ?? null, alt: `${runtime.characterName || 'Personaje'}: ${runtime.label(shown.expression)}` }
    : null
  const goTo = (i: number) => {
    setIndex(i)
    setSelected(null)
    setTested(null)
  }
  const reaction = tested ? runtime.reactionFor(tested) : null

  return (
    <div className="preview">
      <div className="preview-toolbar">
        <label className="visually-hidden" htmlFor="preview-step">
          Decisión que se prueba
        </label>
        <select id="preview-step" value={index} onChange={(e) => goTo(Number(e.target.value))}>
          {steps.map((s, i) => (
            <option key={s.preguntaId} value={i}>
              Escena {s.escenarioIndex + 1}, decisión {i + 1}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn btn-quiet btn-sm"
          onClick={() => {
            stage.reset()
            goTo(0)
          }}
        >
          Volver al estado inicial
        </button>
      </div>
      <div className="preview-frame">
        <SimulatorStage kicker={`Escena ${step.escenarioIndex + 1} de ${caso.escenarios.length}`} title={step.escenarioTitulo} sprite={sprite} characterName={runtime.characterName || undefined} />
        <div className="preview-read">
          <NarrativePanel texts={[step.contexto]} />
          <DecisionPanel
            questionId={`preview-${step.preguntaId}`}
            prompt={step.enunciado}
            position={`Decisión ${index + 1} de ${steps.length}`}
            options={step.opciones}
            selectedId={selected}
            savedId={null}
            disabled={false}
            onSelect={setSelected}
          />
          <SimulatorActions
            back={
              index < steps.length - 1 ? (
                <button
                  type="button"
                  className="btn btn-quiet btn-sm"
                  onClick={() => {
                    // Igual que en el simulador: si se probó una reacción y la siguiente decisión es de otra
                    // escena, la reacción sigue visible un instante antes de la expresión inicial de la nueva.
                    const next = steps[index + 1]!
                    if (tested && next.escenarioId !== step.escenarioId) stage.react(tested, step.escenarioId, next.escenarioId)
                    goTo(index + 1)
                  }}
                >
                  Siguiente decisión
                </button>
              ) : undefined
            }
            hint={
              tested
                ? reaction
                  ? `Reacción: ${runtime.label(reaction.expression)}`
                  : 'Esta opción no cambia la expresión.'
                : 'Elige una opción y prueba su reacción.'
            }
            primary={
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={!selected}
                onClick={() => {
                  if (!selected) return
                  stage.react(selected, step.escenarioId, step.escenarioId)
                  setTested(selected)
                }}
              >
                Probar reacción
              </button>
            }
          />
        </div>
      </div>
      <p className="small muted">La vista previa no crea intentos, no envía respuestas y no modifica notas.</p>
    </div>
  )
}
