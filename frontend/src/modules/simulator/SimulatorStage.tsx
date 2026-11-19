import { CharacterSprite, type SpriteState } from './CharacterSprite'

/** Escenario: fondo azul grisáceo con profundidad, suelo, nombre del personaje y su expresión actual. */
export function SimulatorStage({ kicker, title, sprite, characterName }: { kicker: string; title: string; sprite?: SpriteState | null; characterName?: string }) {
  return (
    <div className="sim-stage">
      <div className="sim-stage-backdrop" aria-hidden="true" />
      <div className="sim-scene-label">
        <span>{kicker}</span>
        {title}
      </div>
      <CharacterSprite sprite={sprite ?? null} />
      {characterName && <p className="sim-nameplate">{characterName}</p>}
    </div>
  )
}
