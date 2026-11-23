import { useState } from 'react'
import type { Motion } from '../../lib/visual/types'
import { SceneCharacter } from './SceneCharacter'

export interface SpriteState {
  /** Identificador de la expresión mostrada (cambia → transición). */
  expression: string
  /** URL de la imagen; null = personaje sin imagen (monigote). */
  src: string | null
  /** Texto alternativo: nombre del personaje y expresión. */
  alt: string
  motion: Motion
}

/**
 * Personaje del escenario en un hueco de tamaño fijo: el cambio de expresión no mueve el texto.
 * Si no hay imagen o falla la carga, se muestra el monigote blanco sin rostro.
 * La transición es solo CSS (opacidad y desplazamiento) y desaparece con prefers-reduced-motion.
 */
export function CharacterSprite({ sprite }: { sprite: SpriteState | null }) {
  const [failed, setFailed] = useState<string | null>(null)
  const src = sprite?.src && failed !== sprite.src ? sprite.src : null
  const motionClass = sprite ? `motion-${sprite.motion}` : ''
  return (
    <div className="sim-character-slot" aria-live="polite">
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
  )
}
