import type { Cuestionario, EscenarioCuestionario, PreguntaCuestionario } from '../../api/types'

export type Step =
  | { kind: 'prologue' }
  | {
      kind: 'decision'
      escenario: EscenarioCuestionario
      escenarioIndex: number
      pregunta: PreguntaCuestionario
      /** Posición de la decisión dentro del caso (0..total-1). */
      decisionIndex: number
    }
  | { kind: 'review' }

/** Recorre el cuestionario en el orden que define el servidor: una decisión por paso. */
export function buildSteps(c: Cuestionario): Step[] {
  const steps: Step[] = []
  if (c.caso.desarrollo_situacional?.trim() || c.caso.historia?.trim()) steps.push({ kind: 'prologue' })
  const escenarios = [...c.escenarios].sort((a, b) => a.orden - b.orden)
  let decisionIndex = 0
  escenarios.forEach((escenario, escenarioIndex) => {
    ;[...escenario.preguntas]
      .sort((a, b) => a.orden - b.orden)
      .forEach((pregunta) => {
        steps.push({ kind: 'decision', escenario, escenarioIndex, pregunta, decisionIndex })
        decisionIndex += 1
      })
  })
  steps.push({ kind: 'review' })
  return steps
}

export function countDecisions(steps: Step[]) {
  return steps.filter((s) => s.kind === 'decision').length
}

/**
 * Paso con el que se retoma un intento: el prólogo si aún no hay respuestas guardadas,
 * la primera decisión sin responder o, si todas tienen respuesta, la revisión final.
 */
export function initialStepIndex(steps: Step[], saved: Record<string, string>) {
  const answered = Object.keys(saved).length
  if (answered === 0) return 0
  const firstPending = steps.findIndex((s) => s.kind === 'decision' && !saved[s.pregunta.id])
  return firstPending >= 0 ? firstPending : steps.length - 1
}

/** Siguiente paso tras confirmar: la próxima decisión sin responder hacia adelante, o la revisión. */
export function nextStepIndex(steps: Step[], current: number, saved: Record<string, string>) {
  for (let i = current + 1; i < steps.length; i++) {
    const s = steps[i]!
    if (s.kind === 'review') return i
    if (s.kind === 'decision' && !saved[s.pregunta.id]) return i
  }
  return steps.length - 1
}

export function savedFromQuestionnaire(c: Cuestionario): Record<string, string> {
  const saved: Record<string, string> = {}
  for (const e of c.escenarios) for (const p of e.preguntas) if (p.opcion_seleccionada_id) saved[p.id] = p.opcion_seleccionada_id
  return saved
}

export function paragraphs(text: string | null | undefined) {
  return (text ?? '')
    .split(/\n{2,}|\r?\n/)
    .map((p) => p.trim())
    .filter(Boolean)
}
