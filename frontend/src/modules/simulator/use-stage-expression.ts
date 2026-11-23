import { useCallback, useEffect, useRef, useState } from 'react'
import type { VisualRuntime } from '../../lib/visual/runtime'
import type { Motion } from '../../lib/visual/types'

export interface ShownExpression {
  expression: string
  motion: Motion
}

/** Tiempo que la reacción sigue visible tras pasar a otra escena (no bloquea el texto ni las acciones). */
export const CARRY_MS = 1400

/**
 * Expresión del personaje en escena.
 * - Sin reacción aceptada: la expresión inicial de la escena (o la por defecto).
 * - `react` se llama SOLO cuando el servidor acepta la respuesta (o en la vista previa local): seleccionar no
 *   cambia nada y un error de envío no toca la expresión.
 * - Si la respuesta lleva a otra escena, la reacción sigue visible un instante y después la nueva escena
 *   muestra su expresión inicial. La siguiente decisión aparece de inmediato.
 * - Al reanudar no hay reacción reconstruida: se usa la expresión inicial de la escena.
 */
export function useStageExpression(runtime: VisualRuntime | null, sceneId: string | null) {
  const [reacted, setReacted] = useState<(ShownExpression & { sceneId: string }) | null>(null)
  const [carry, setCarry] = useState<ShownExpression | null>(null)
  const timer = useRef<number | null>(null)

  useEffect(() => () => {
    if (timer.current) window.clearTimeout(timer.current)
  }, [])

  const react = useCallback(
    (opcionId: string, fromScene: string, nextScene: string | null) => {
      const r = runtime?.reactionFor(opcionId)
      if (!r) return // «Sin cambio» o asociación no válida: se conserva lo que había.
      setReacted({ sceneId: fromScene, expression: r.expression, motion: r.motion })
      if (nextScene !== fromScene) {
        if (timer.current) window.clearTimeout(timer.current)
        setCarry({ expression: r.expression, motion: r.motion })
        timer.current = window.setTimeout(() => setCarry(null), CARRY_MS)
      }
    },
    [runtime],
  )

  const reset = useCallback(() => {
    if (timer.current) window.clearTimeout(timer.current)
    setReacted(null)
    setCarry(null)
  }, [])

  let shown: ShownExpression | null = null
  if (runtime) {
    if (carry) shown = carry
    else if (reacted && reacted.sceneId === sceneId) shown = reacted
    else shown = { expression: sceneId ? runtime.initialFor(sceneId) : runtime.defaultExpression, motion: 'fade' }
  }
  return { shown, react, reset }
}
