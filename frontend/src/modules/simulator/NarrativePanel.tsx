import { paragraphs } from './steps'

/** Panel narrativo: el contexto de la escena en tipografía de lectura. Sin animaciones que obliguen a esperar. */
export function NarrativePanel({ texts, scroll = true }: { texts: (string | null | undefined)[]; scroll?: boolean }) {
  const items = texts.flatMap((t) => paragraphs(t))
  if (items.length === 0) return null
  return (
    <div className={`sim-context${scroll ? ' sim-context-scroll' : ''}`}>
      {items.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
    </div>
  )
}
