import { useState, type FormEvent } from 'react'
import { InlineError } from '../../components/design-system/states'
import { Button } from '../../components/ui/Button'
import { TextAreaField } from '../../components/ui/Field'
import { useSaveFeedback } from '../../hooks/use-academic'

/** Comentario del docente sobre un intento cerrado (CU24). No cambia la nota. */
export function FeedbackEditor({ sessionId, participationId, initial, finalizada }: { sessionId: string; participationId: string; initial: string; finalizada: boolean }) {
  const [texto, setTexto] = useState(initial)
  const [saved, setSaved] = useState(false)
  const save = useSaveFeedback(sessionId, participationId)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(texto.trim() || null, { onSuccess: () => setSaved(true) })
  }
  return (
    <form className="panel form-grid" aria-labelledby="h-retro" onSubmit={submit}>
      <h2 id="h-retro">Tu comentario para el estudiante</h2>
      <TextAreaField
        label="Comentario"
        hideLabel
        maxLength={5000}
        rows={6}
        value={texto}
        onChange={(e) => {
          setTexto(e.target.value)
          setSaved(false)
        }}
        hint={`${texto.length} de 5000 caracteres. No cambia la nota. Déjalo vacío para quitarlo. ${
          finalizada ? 'El estudiante lo verá en sus resultados.' : 'El estudiante lo verá cuando finalices la sesión.'
        }`}
      />
      <InlineError error={save.error} />
      <div className="btn-row">
        <Button type="submit" variant="primary" pending={save.isPending} pendingLabel="Guardando…">
          Guardar comentario
        </Button>
        {saved && !save.isPending && (
          <span role="status" className="saved-flag">
            Comentario guardado
          </span>
        )}
      </div>
    </form>
  )
}
