import { useId, useState } from 'react'
import { Button } from '../../../components/ui/Button'
import { detectImage } from '../../../lib/visual/package'
import { LIMITS, type VisualManifest } from '../../../lib/visual/types'
import { SceneCharacter } from '../../simulator/SceneCharacter'

interface Props {
  manifest: VisualManifest
  urls: Record<string, string>
  onChange: (next: VisualManifest, images?: { set?: Record<string, Blob>; remove?: string[] }) => void
}

function slug(label: string, taken: Set<string>) {
  const base =
    label
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 24) || 'expresion'
  let id = base
  for (let i = 2; taken.has(id); i++) id = `${base}-${i}`
  return id
}

/** Zona 1: nombre del personaje y sus expresiones (etiquetas editables, imágenes PNG o WebP). */
export function CharacterPanel({ manifest, urls, onChange }: Props) {
  const nameId = useId()
  const [error, setError] = useState<string | null>(null)
  const [newLabel, setNewLabel] = useState('')

  const update = (patch: Partial<VisualManifest>, images?: Parameters<Props['onChange']>[1]) => onChange({ ...manifest, ...patch }, images)

  const pick = async (exprId: string, file: File | undefined) => {
    setError(null)
    if (!file) return
    if (file.size > LIMITS.maxImageBytes) return setError(`«${file.name}» supera los 2 MB por imagen.`)
    const kind = detectImage(new Uint8Array(await file.arrayBuffer()))
    if (!kind) return setError(`«${file.name}» no es una imagen PNG o WebP.`)
    update({}, { set: { [exprId]: file } })
  }

  const removeExpression = (id: string) => {
    update(
      {
        expressions: manifest.expressions.filter((e) => e.id !== id),
        scenes: manifest.scenes.map((s) => (s.initialExpression === id ? { ...s, initialExpression: null } : s)),
        reactions: manifest.reactions.filter((r) => r.expression !== id),
      },
      { remove: [id] },
    )
  }

  const addExpression = () => {
    const label = newLabel.trim()
    if (!label || manifest.expressions.length >= LIMITS.maxExpressions) return
    const id = slug(label, new Set(manifest.expressions.map((e) => e.id)))
    update({ expressions: [...manifest.expressions, { id, label: label.slice(0, LIMITS.labelMax), sprite: null }] })
    setNewLabel('')
  }

  return (
    <section className="visual-zone" aria-labelledby="h-personaje">
      <h3 id="h-personaje">Personaje y sprites</h3>
      <div className="field">
        <label htmlFor={nameId}>Nombre visible del entrevistado</label>
        <input
          id={nameId}
          maxLength={LIMITS.nameMax}
          value={manifest.character.name}
          placeholder="Por ejemplo, Laura"
          onChange={(e) => update({ character: { ...manifest.character, name: e.target.value } })}
        />
        <span className="hint">Se muestra sobre el escenario. Puedes dejarlo vacío.</span>
      </div>

      <fieldset className="expression-list">
        <legend>Expresiones</legend>
        <p className="small muted">
          Las etiquetas son dirección narrativa, no categorías clínicas ni pistas de acierto. Sin imagen se usa el personaje blanco sin rostro.
        </p>
        {manifest.expressions.map((e) => {
          const url = urls[e.id]
          const isDefault = manifest.character.defaultExpression === e.id
          return (
            <div key={e.id} className={`expression-row${isDefault ? ' is-default' : ''}`}>
              <div className="expression-thumb">{url ? <img src={url} alt="" /> : <SceneCharacter className="thumb-figure" decorative />}</div>
              <div className="expression-fields">
                <label className="visually-hidden" htmlFor={`label-${e.id}`}>
                  Etiqueta de la expresión
                </label>
                <input
                  id={`label-${e.id}`}
                  value={e.label}
                  maxLength={LIMITS.labelMax}
                  onChange={(ev) => update({ expressions: manifest.expressions.map((x) => (x.id === e.id ? { ...x, label: ev.target.value } : x)) })}
                />
                <label className="check">
                  <input
                    type="radio"
                    name="expresion-por-defecto"
                    checked={isDefault}
                    onChange={() => update({ character: { ...manifest.character, defaultExpression: e.id } })}
                  />
                  Por defecto
                </label>
              </div>
              <div className="expression-actions">
                <label className="btn btn-secondary btn-sm file-btn">
                  {url ? 'Reemplazar' : 'Cargar imagen'}
                  <input
                    type="file"
                    accept="image/png,image/webp"
                    className="visually-hidden"
                    data-expression={e.id}
                    onChange={(ev) => {
                      void pick(e.id, ev.target.files?.[0])
                      ev.target.value = ''
                    }}
                  />
                </label>
                {url && (
                  <Button size="sm" variant="quiet" onClick={() => update({}, { remove: [e.id] })}>
                    Retirar imagen
                  </Button>
                )}
                {!isDefault && manifest.expressions.length > 1 && (
                  <Button size="sm" variant="quiet" icon="trash" onClick={() => removeExpression(e.id)} aria-label={`Eliminar la expresión ${e.label}`}>
                    {''}
                  </Button>
                )}
              </div>
            </div>
          )
        })}
        {manifest.expressions.length < LIMITS.maxExpressions && (
          <div className="expression-add">
            <label className="visually-hidden" htmlFor="nueva-expresion">
              Nueva expresión
            </label>
            <input id="nueva-expresion" placeholder="Nueva expresión" value={newLabel} maxLength={LIMITS.labelMax} onChange={(e) => setNewLabel(e.target.value)} />
            <Button size="sm" icon="plus" onClick={addExpression} disabled={!newLabel.trim()}>
              Añadir
            </Button>
          </div>
        )}
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <p className="small muted">PNG o WebP, hasta 2 MB por imagen. Se recomienda fondo transparente y la misma proporción en todas.</p>
      </fieldset>
    </section>
  )
}
