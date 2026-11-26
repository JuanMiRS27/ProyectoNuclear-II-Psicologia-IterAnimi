import { useState } from 'react'
import { moodFor } from '../../lib/visual/mood'
import type { Motion } from '../../lib/visual/types'
import { SceneCharacter } from './SceneCharacter'

export interface SpriteState {
  /** Identificador de la expresión mostrada (cambia → transición). */
  expression: string
  /** Etiqueta de la expresión (ayuda a deducir el ánimo en expresiones propias del docente). */
  label?: string | null
  /** URL de la imagen; null = personaje sin imagen (monigote). */
  src: string | null
  /** Texto alternativo: nombre del personaje y expresión. */
  alt: string
  motion: Motion
}

/**
 * Personaje del escenario en un hueco de tamaño fijo: el cambio de expresión no mueve el texto.
 * Si no hay imagen o falla la carga, se muestra el monigote blanco sin rostro.
 * Dos capas de animación (solo CSS, desaparecen con prefers-reduced-motion):
 * - La de entrada (motion-*) al cambiar de expresión.
 * - La de ánimo (mood-*), continua mientras la expresión está en pantalla: respiración tranquila, respiración
 *   rápida si hay inquietud, sacudida y temblor si hay enojo, etc.
 */
export function CharacterSprite({ sprite }: { sprite: SpriteState | null }) {
  const [failed, setFailed] = useState<string | null>(null)
  const src = sprite?.src && failed !== sprite.src ? sprite.src : null
  const motionClass = sprite ? `motion-${sprite.motion}` : ''
  const mood = sprite ? moodFor(sprite.expression, sprite.label) : 'calm'
  return (
    <div className="sim-character-slot" aria-live="polite">
      <div key={sprite?.expression ?? 'base'} className={`sim-mood mood-${mood}`} data-mood={mood}>
        {src ? (
          <img
            key={`${sprite!.expression}|${src}`}
            className={`sim-sprite ${motionClass}`}
            src={src}
            alt={sprite!.alt}
            onError={() => setFailed(src)}
            draggable={false}
          />
        ) : (
          <div key={sprite?.expression ?? 'base'} className={`sim-sprite-fallback ${motionClass}`}>
            <SceneCharacter decorative={!sprite} />
            {sprite && <span className="visually-hidden">{sprite.alt}</span>}
          </div>
        )}
      </div>
    </div>
  )
}
