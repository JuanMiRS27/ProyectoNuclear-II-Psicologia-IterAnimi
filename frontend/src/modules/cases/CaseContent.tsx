import { Section } from '../../components/design-system/layout'
import { DataTable } from '../../components/design-system/DataTable'
import { formatDecimal, optionLetter } from '../../lib/format'
import type { CasoDetalle } from '../../types/api'

function Text({ value }: { value: string | null }) {
  if (!value) return <p className="muted">Sin contenido.</p>
  return (
    <div className="reading">
      {value
        .split(/\n+/)
        .filter((p) => p.trim())
        .map((p, i) => (
          <p key={i}>{p}</p>
        ))}
    </div>
  )
}

/** Contenido del caso en solo lectura (vista docente: incluye opciones correctas y rúbrica). */
export function CaseContent({ caso, only }: { caso: CasoDetalle; only?: 'general' }) {
  const general = (
    <div className="case-general">
      <div>
        <h3>Desarrollo situacional</h3>
        <Text value={caso.desarrollo_situacional} />
      </div>
      <div>
        <h3>Historia</h3>
        <Text value={caso.historia} />
      </div>
    </div>
  )
  if (only === 'general') return general
  const criterios = new Map((caso.rubrica?.criterios ?? []).map((c) => [c.id, c.descripcion]))
  return (
    <>
      <Section title="Información general">{general}</Section>
      <Section title="Escenas y decisiones" description="Las opciones marcadas son las correctas. Esto nunca se muestra al estudiante durante el caso.">
        {caso.escenarios.length === 0 && <p className="muted">Este caso no tiene escenas.</p>}
        {[...caso.escenarios]
          .sort((a, b) => a.orden - b.orden)
          .map((e) => (
            <article key={e.id} className="scenario">
              <h3>
                Escena {e.orden}. {e.titulo}
              </h3>
              <Text value={e.contexto} />
              {[...e.preguntas]
                .sort((a, b) => a.orden - b.orden)
                .map((p) => (
                  <div key={p.id} className="question-block">
                    <strong>{p.enunciado}</strong>
                    <span className="small muted">{p.criterio_id ? `Criterio: ${criterios.get(p.criterio_id) ?? '—'}` : 'Sin criterio'}</span>
                    <ol className="option-list">
                      {[...p.opciones]
                        .sort((a, b) => a.orden - b.orden)
                        .map((o, i) => (
                          <li key={o.id} className={o.es_correcta ? 'option-correct' : undefined}>
                            <span className="option-letter" aria-hidden="true">
                              {optionLetter(i)}
                            </span>
                            <span>
                              {o.texto}
                              {o.es_correcta && <strong> (correcta)</strong>}
                              {o.justificacion && <span className="muted"> {o.justificacion}</span>}
                            </span>
                          </li>
                        ))}
                    </ol>
                  </div>
                ))}
            </article>
          ))}
      </Section>
      <Section title="Rúbrica">
        {!caso.rubrica ? (
          <p className="muted">Sin rúbrica.</p>
        ) : (
          <>
            <p className="small muted">Escala máxima: {formatDecimal(caso.rubrica.escala_max)}</p>
            <DataTable
              caption="Criterios de la rúbrica"
              rows={caso.rubrica.criterios}
              rowKey={(c) => c.id}
              columns={[
                { key: 'd', header: 'Criterio', cell: (c) => c.descripcion },
                { key: 'p', header: 'Peso', numeric: true, cell: (c) => `${formatDecimal(c.peso)} %` },
                {
                  key: 'n',
                  header: 'Niveles',
                  cell: (c) =>
                    c.niveles.length === 0
                      ? '—'
                      : c.niveles.map((n) => `${n.nombre}: ${formatDecimal(n.valor)}${n.min_aciertos_pct != null ? ` (desde ${formatDecimal(n.min_aciertos_pct, 0)} %)` : ''}`).join('; '),
                },
              ]}
            />
          </>
        )}
      </Section>
    </>
  )
}
