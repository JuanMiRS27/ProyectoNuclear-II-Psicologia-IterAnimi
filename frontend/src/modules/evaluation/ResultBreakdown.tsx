import type { DetalleResultadoBase } from '../../types/api'
import { CALIFICACION, CONDICION, MOTIVO_CIERRE, RESULTADO_PREGUNTA } from '../../lib/labels'
import { formatDecimal, formatPercent, plural } from '../../lib/format'
import { Status } from '../../components/design-system/Status'

/** Nota y desglose tal como los devuelve el servidor. No se recalcula nada en el cliente. */
export function ScoreLine({ nota, escala, calificacion }: { nota: string | null; escala: string | null; calificacion: string | null }) {
  if (nota !== null)
    return (
      <div className="score" aria-label={`Nota ${formatDecimal(nota)} de ${formatDecimal(escala)}`}>
        <strong>{formatDecimal(nota)}</strong>
        {escala && <span>de {formatDecimal(escala)}</span>}
      </div>
    )
  return (
    <p className="muted">
      {calificacion === 'SIN_CALIFICAR'
        ? 'Este intento no tiene nota: según la política de evaluación, no hubo evidencia suficiente para calificarlo (no equivale a un cero).'
        : 'La nota de este intento aún no está registrada.'}
    </p>
  )
}

function Paragraphs({ text }: { text: string }) {
  return (
    <div className="reading">
      {text
        .split(/\n{2,}|\n/)
        .filter((p) => p.trim())
        .map((p, i) => (
          <p key={i}>{p}</p>
        ))}
    </div>
  )
}

export function ResultBreakdown({ r, viewer = 'student' }: { r: DetalleResultadoBase; viewer?: 'student' | 'teacher' }) {
  return (
    <div style={{ display: 'grid', gap: '2.25rem' }}>
      <section className="panel" aria-labelledby="h-nota" style={{ display: 'grid', gap: '1rem' }}>
        <h2 id="h-nota" className="visually-hidden">
          Calificación
        </h2>
        <ScoreLine nota={r.nota_final} escala={r.escala_max} calificacion={r.calificacion} />
        <dl className="defs">
          <dt>Intento</dt>
          <dd>{r.numero_intento}</dd>
          <dt>Condición</dt>
          <dd>{CONDICION[r.condicion]}</dd>
          <dt>Calificación</dt>
          <dd>{CALIFICACION[r.calificacion]}</dd>
          {r.motivo_cierre && (
            <>
              <dt>Cierre</dt>
              <dd>{MOTIVO_CIERRE[r.motivo_cierre]}</dd>
            </>
          )}
          {r.totales && (
            <>
              <dt>Respuestas</dt>
              <dd>
                {plural(r.totales.aciertos, 'acierto', 'aciertos')}, {plural(r.totales.errores, 'no acertada', 'no acertadas')} y{' '}
                {r.totales.sin_responder} sin responder, de {plural(r.totales.total_preguntas, 'pregunta', 'preguntas')}
              </dd>
            </>
          )}
        </dl>
        {r.observaciones.length > 0 && (
          <ul className="small" style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {r.observaciones.map((o, i) => (
              <li key={i}>{o}</li>
            ))}
          </ul>
        )}
      </section>

      {r.retroalimentacion_general && (
        <section className="section" aria-labelledby="h-retro-docente">
          <h2 id="h-retro-docente">{viewer === 'student' ? 'Comentario de tu docente' : 'Comentario registrado'}</h2>
          <Paragraphs text={r.retroalimentacion_general} />
        </section>
      )}

      {r.criterios.length > 0 && (
        <section className="section" aria-labelledby="h-criterios">
          <h2 id="h-criterios">Desempeño por criterio</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Criterio</th>
                  <th className="num">Aciertos</th>
                  <th>Nivel</th>
                  <th className="num">Puntaje</th>
                  <th className="num">Peso</th>
                </tr>
              </thead>
              <tbody>
                {r.criterios.map((c) => (
                  <tr key={c.criterio_id}>
                    <td>
                      {c.descripcion}
                      {c.advertencia && <div className="small muted">{c.advertencia}</div>}
                    </td>
                    <td className="num">
                      {c.politica === 'SIN_EVIDENCIA' ? (
                        <span className="muted">Sin preguntas</span>
                      ) : (
                        <>
                          {c.aciertos} de {c.total_preguntas}
                          <div className="small muted">{formatPercent(c.porcentaje_aciertos)}</div>
                        </>
                      )}
                    </td>
                    <td>{c.nivel ?? <span className="muted">—</span>}</td>
                    <td className="num">{formatDecimal(c.puntaje)}</td>
                    <td className="num">{formatPercent(c.peso_efectivo)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {r.preguntas.length > 0 && (
        <section className="section" aria-labelledby="h-preguntas">
          <h2 id="h-preguntas">Retroalimentación por decisión</h2>
          <div className="panel" style={{ paddingBlock: '0.25rem' }}>
            {r.preguntas.map((p) => (
              <article key={p.pregunta_id} className="feedback-item">
                <div className="small muted">{p.escenario}</div>
                <h3 style={{ fontSize: 'var(--fs-md)' }}>{p.enunciado}</h3>
                <Status fill={p.resultado === 'ACIERTO' ? 'full' : p.resultado === 'ERROR' ? 'alert' : 'empty'} tone={p.resultado === 'ERROR' ? 'alert' : undefined}>
                  {RESULTADO_PREGUNTA[p.resultado]}
                </Status>
                {p.opcion_elegida && (
                  <div className="feedback-choice">
                    <strong>
                      {viewer === 'student' ? 'Tu elección' : 'Opción elegida'}: {p.opcion_elegida.texto}
                    </strong>
                    {p.opcion_elegida.justificacion && <span>{p.opcion_elegida.justificacion}</span>}
                  </div>
                )}
                {p.resultado !== 'ACIERTO' &&
                  p.opciones_correctas.map((o) => (
                    <div key={o.id} className="feedback-choice" style={{ background: 'var(--ok-bg)' }}>
                      <strong>Opción esperada: {o.texto}</strong>
                      {o.justificacion && <span>{o.justificacion}</span>}
                    </div>
                  ))}
                {p.mensaje && <p className="small muted">{p.mensaje}</p>}
              </article>
            ))}
          </div>
        </section>
      )}

      {r.retroalimentacion_automatica && (
        <section className="section" aria-labelledby="h-retro-auto">
          <h2 id="h-retro-auto">Resumen del sistema</h2>
          <Paragraphs text={r.retroalimentacion_automatica} />
        </section>
      )}
    </div>
  )
}
