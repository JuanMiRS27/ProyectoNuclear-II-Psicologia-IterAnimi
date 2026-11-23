import { optionLetter } from '../../../lib/format'
import type { VisualRuntime } from '../../../lib/visual/runtime'
import { optionSignature, sceneSignature } from '../../../lib/visual/signature'
import type { Motion, VisualManifest } from '../../../lib/visual/types'
import type { CasoDetalle } from '../../../types/api'

const MOTION_LABEL: Record<Motion, string> = {
  fade: 'Fundido',
  rise: 'Aparición suave',
  breathe: 'Respiración sutil',
  none: 'Sin animación',
}

interface Props {
  caso: CasoDetalle
  manifest: VisualManifest
  runtime: VisualRuntime
  onChange: (next: VisualManifest) => void
}

/**
 * Zona 2: expresión inicial por escena y reacción por opción, asociadas por los ids reales del caso.
 * La letra es solo una etiqueta visual. Si el texto de una opción o escena cambió desde que se configuró,
 * la asociación queda «pendiente de revisión» y el simulador usa la expresión inicial hasta confirmarla.
 */
export function ReactionsPanel({ caso, manifest, runtime, onChange }: Props) {
  const changed = new Set(runtime.issues.filter((i) => i.kind === 'opcion-cambiada' || i.kind === 'escena-cambiada').map((i) => i.id))
  const reactionOf = (opcionId: string) => manifest.reactions.find((r) => r.opcionId === opcionId)
  const sceneOf = (escenarioId: string) => manifest.scenes.find((s) => s.escenarioId === escenarioId)

  const setScene = (escenarioId: string, titulo: string, initialExpression: string | null) => {
    const others = manifest.scenes.filter((s) => s.escenarioId !== escenarioId)
    onChange({ ...manifest, scenes: [...others, { escenarioId, signature: sceneSignature(titulo), initialExpression }] })
  }

  const setReaction = (
    o: { id: string; texto: string },
    p: { id: string; enunciado: string },
    escenarioId: string,
    patch: { expression?: string | null; motion?: Motion },
  ) => {
    const current = reactionOf(o.id)
    const expression = patch.expression !== undefined ? patch.expression : (current?.expression ?? null)
    const motion = patch.motion ?? current?.motion ?? 'fade'
    const others = manifest.reactions.filter((r) => r.opcionId !== o.id)
    // «Sin cambio» no necesita guardarse: la ausencia de reacción conserva la expresión actual.
    if (expression === null) return onChange({ ...manifest, reactions: others })
    onChange({
      ...manifest,
      reactions: [...others, { opcionId: o.id, preguntaId: p.id, escenarioId, signature: optionSignature(p.enunciado, o.texto), expression, motion }],
    })
  }

  return (
    <section className="visual-zone" aria-labelledby="h-reacciones">
      <h3 id="h-reacciones">Reacciones por decisión</h3>
      <p className="small muted">
        Las reacciones acompañan la narración y no indican si una opción es correcta. El estudiante las ve solo después de que el servidor acepta
        su respuesta.
      </p>
      {caso.escenarios.length === 0 && <p className="muted">El caso todavía no tiene escenas.</p>}
      {[...caso.escenarios]
        .sort((a, b) => a.orden - b.orden)
        .map((e) => {
          const scene = sceneOf(e.id)
          const sceneChanged = changed.has(e.id)
          return (
            <article key={e.id} className="reaction-scene">
              <header className="reaction-scene-head">
                <h4>
                  <span className="editor-order">Escena {e.orden}</span> {e.titulo}
                </h4>
                <label className="inline-select">
                  <span>Expresión inicial</span>
                  <select value={scene?.initialExpression ?? ''} onChange={(ev) => setScene(e.id, e.titulo, ev.target.value || null)}>
                    <option value="">Por defecto ({runtime.label(manifest.character.defaultExpression)})</option>
                    {manifest.expressions.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.label}
                      </option>
                    ))}
                  </select>
                </label>
              </header>
              {sceneChanged && (
                <p className="review-flag" role="status">
                  El título de la escena cambió. Elige de nuevo su expresión inicial para confirmarla.
                </p>
              )}
              {[...e.preguntas]
                .sort((a, b) => a.orden - b.orden)
                .map((p) => (
                  <div key={p.id} className="reaction-question">
                    <p className="question-text">{p.enunciado}</p>
                    <ul className="reaction-options">
                      {[...p.opciones]
                        .sort((a, b) => a.orden - b.orden)
                        .map((o, i) => {
                          const r = reactionOf(o.id)
                          const isChanged = changed.has(o.id)
                          return (
                            <li key={o.id} className={isChanged ? 'needs-review' : undefined}>
                              <span className="option-letter" aria-hidden="true">
                                {optionLetter(i)}
                              </span>
                              <span className="reaction-text">
                                {o.texto}
                                {isChanged && <span className="review-flag">Pendiente de revisión: el texto cambió desde que se asignó la reacción.</span>}
                              </span>
                              <label className="inline-select">
                                <span className="visually-hidden">Reacción a la opción {optionLetter(i)}</span>
                                <select value={r?.expression ?? ''} onChange={(ev) => setReaction(o, p, e.id, { expression: ev.target.value || null })}>
                                  <option value="">Sin cambio</option>
                                  {manifest.expressions.map((x) => (
                                    <option key={x.id} value={x.id}>
                                      {x.label}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <label className="inline-select">
                                <span className="visually-hidden">Movimiento de la opción {optionLetter(i)}</span>
                                <select value={r?.motion ?? 'fade'} disabled={!r?.expression} onChange={(ev) => setReaction(o, p, e.id, { motion: ev.target.value as Motion })}>
                                  {(Object.keys(MOTION_LABEL) as Motion[]).map((m) => (
                                    <option key={m} value={m}>
                                      {MOTION_LABEL[m]}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              {isChanged && r && (
                                <button type="button" className="btn btn-sm btn-secondary" onClick={() => setReaction(o, p, e.id, {})}>
                                  Confirmar
                                </button>
                              )}
                            </li>
                          )
                        })}
                    </ul>
                  </div>
                ))}
            </article>
          )
        })}
    </section>
  )
}
