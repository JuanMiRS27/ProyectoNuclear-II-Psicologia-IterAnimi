import { useState } from 'react'
import { useStaticVisualPackageByCaseName } from '../../hooks/use-visual'
import { SceneCharacter } from '../simulator/SceneCharacter'

/**
 * Personaje del caso en la tarjeta principal del inicio del estudiante: el que eligió el docente, en su expresión por
 * defecto (paquete visual publicado en el frontend). Sin paquete, o si la imagen no carga, el personaje sin rostro.
 * Es decorativo: el nombre del caso ya está en el texto de la tarjeta.
 */
export function HeroCharacter({ caseName }: { caseName: string | undefined }) {
  const pkg = useStaticVisualPackageByCaseName(caseName)
  const [failed, setFailed] = useState<string | null>(null)
  const manifest = pkg.data?.manifest
  const expression = manifest?.character.defaultExpression
  const src = expression ? (pkg.data?.spriteUrls[expression] ?? null) : null
  if (!src || failed === src) return <SceneCharacter className="hero-figure" decorative />
  return <img className="hero-figure hero-sprite" src={src} alt="" draggable={false} onError={() => setFailed(src)} />
}
