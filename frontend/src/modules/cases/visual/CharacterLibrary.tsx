import { useState } from 'react'
import { Button } from '../../../components/ui/Button'
import { libraryBase, type LibraryCatalog, type LibraryCharacter } from '../../../lib/visual/library'
import { SceneCharacter } from '../../simulator/SceneCharacter'

interface Props {
  catalog: LibraryCatalog | null | undefined
  loading: boolean
  /** Personaje del sistema en uso (character.library) o null. */
  activeId: string | null
  defaultExpression: string
  onUse: (ch: LibraryCharacter) => void
  onDefaultExpression: (id: string) => void
}

const src = (file: string) => `${libraryBase()}${file}`

function Thumb({ file, alt, className }: { file?: string; alt: string; className?: string }) {
  const [failed, setFailed] = useState(false)
  if (!file || failed) return <SceneCharacter className={`lib-fallback ${className ?? ''}`} decorative />
  return <img className={className} src={src(file)} alt={alt} loading="lazy" draggable={false} onError={() => setFailed(true)} />
}

/**
 * Galería de personajes del sistema: tarjetas con miniatura y una vista previa amplia con todas sus expresiones.
 * Elegir un personaje solo guarda su id en el manifiesto; las imágenes son recursos estáticos del frontend.
 */
export function CharacterLibrary({ catalog, loading, activeId, defaultExpression, onUse, onDefaultExpression }: Props) {
  const characters = catalog?.characters ?? []
  const [focusId, setFocusId] = useState<string | null>(activeId)
  const focus = characters.find((c) => c.id === focusId) ?? characters.find((c) => c.id === activeId) ?? characters[0]
  const [exprId, setExprId] = useState<string | null>(null)

  if (loading) return <p className="muted small">Cargando la biblioteca de personajes…</p>
  if (!focus)
    return (
      <p className="empty-line">
        La biblioteca de personajes no está disponible en este despliegue. Puedes seguir usando tus propios sprites en «Mis personajes».
      </p>
    )

  const shownExpr = focus.expressions.find((e) => e.id === exprId) ?? focus.expressions.find((e) => e.id === focus.defaultExpression)!
  const isActive = focus.id === activeId
  const provisional = characters.some((c) => c.status === 'provisional')

  return (
    <div className="library">
      {provisional && (
        <p className="library-note" role="note">
          Arte provisional: estos sprites son ilustraciones de trabajo incluidas con Iter Animi mientras se instala el arte definitivo. Funcionan
          igual en la vista previa y en el simulador.
        </p>
      )}
      <ul className="library-grid" aria-label="Personajes del sistema">
        {characters.map((c) => {
          const neutral = c.expressions.find((e) => e.id === c.defaultExpression)
          const selected = c.id === focus.id
          return (
            <li key={c.id}>
              <button
                type="button"
                className={`library-card${selected ? ' is-focused' : ''}${c.id === activeId ? ' is-active' : ''}`}
                aria-pressed={selected}
                onClick={() => {
                  setFocusId(c.id)
                  setExprId(null)
                }}
              >
                <span className="library-card-art">
                  <Thumb file={neutral?.file} alt="" />
                </span>
                <span className="library-card-text">
                  <strong>{c.name}</strong>
                  <span>{c.profile}</span>
                </span>
                {c.id === activeId && <span className="library-badge">En uso</span>}
              </button>
            </li>
          )
        })}
      </ul>

      <section className="library-detail" aria-labelledby="lib-detail-name">
        <div className="library-stage">
          <Thumb key={`${focus.id}-${shownExpr.id}`} file={shownExpr.file} alt={`${focus.name}: ${shownExpr.label}`} className="library-stage-img" />
        </div>
        <div className="library-info">
          <div>
            <h4 id="lib-detail-name">
              {focus.name} <span className="muted">· {focus.profile}</span>
            </h4>
            <p className="small muted">{focus.description}</p>
          </div>
          <div className="library-expressions" role="radiogroup" aria-label={`Expresiones de ${focus.name}`}>
            {focus.expressions.map((e) => (
              <button
                key={e.id}
                type="button"
                role="radio"
                aria-checked={e.id === shownExpr.id}
                className={`library-expr${e.id === shownExpr.id ? ' is-shown' : ''}`}
                onClick={() => setExprId(e.id)}
              >
                <span className="library-expr-art">
                  <Thumb file={e.file} alt="" />
                </span>
                <span>{e.label}</span>
              </button>
            ))}
          </div>
          {isActive ? (
            <label className="inline-select">
              <span>Expresión por defecto</span>
              <select value={defaultExpression} onChange={(ev) => onDefaultExpression(ev.target.value)}>
                {focus.expressions.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.label}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <div>
              <Button variant="primary" icon="check" onClick={() => onUse(focus)}>
                Usar a {focus.name}
              </Button>
            </div>
          )}
          {isActive && <p className="small muted">En uso en este caso. Asigna sus expresiones en «Reacciones» y pruébalas en la vista previa.</p>}
        </div>
      </section>
    </div>
  )
}
