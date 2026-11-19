import { SceneCharacter } from './SceneCharacter'

/** Escenario: fondo azul grisáceo, suelo y personaje. Solo ambientación; el texto vive en el panel narrativo. */
export function SimulatorStage({ kicker, title }: { kicker: string; title: string }) {
  return (
    <div className="sim-stage">
      <div className="sim-scene-label">
        <span>{kicker}</span>
        {title}
      </div>
      <SceneCharacter decorative />
    </div>
  )
}
