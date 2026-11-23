import { optionLetter } from '../../lib/format'
import type { OpcionCuestionario } from '../../types/api'

/**
 * Opciones de una decisión como grupo de radio: A, B, C, D… según la cantidad real que envía el backend.
 * Seleccionar no envía nada; el envío lo hace la barra de acciones al confirmar.
 */
export function DecisionPanel({
  questionId,
  prompt,
  position,
  options,
  selectedId,
  savedId,
  disabled,
  onSelect,
}: {
  questionId: string
  prompt: string
  position: string
  options: OpcionCuestionario[]
  selectedId: string | null
  savedId: string | null
  disabled: boolean
  onSelect: (optionId: string) => void
}) {
  const ordered = [...options].sort((a, b) => a.orden - b.orden)
  return (
    <fieldset className="choices">
      <legend className="sim-prompt">
        <span className="sim-prompt-label">{position}</span>
        {prompt}
      </legend>
      {ordered.map((o, i) => (
        <label key={o.id} className="choice">
          <input type="radio" name={`p-${questionId}`} value={o.id} checked={selectedId === o.id} onChange={() => onSelect(o.id)} disabled={disabled} />
          <span className="choice-letter" aria-hidden="true">
            {optionLetter(i)}
          </span>
          <span className="choice-text">
            <span className="visually-hidden">Opción {optionLetter(i)}: </span>
            {o.texto}
            {savedId === o.id && <span className="choice-saved">Respuesta guardada</span>}
          </span>
          <span className="choice-mark" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12.5 10 17.5 19 7" />
            </svg>
          </span>
        </label>
      ))}
    </fieldset>
  )
}
