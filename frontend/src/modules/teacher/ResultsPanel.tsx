import { DataTable } from '../../components/design-system/DataTable'
import { Link } from 'react-router'
import { AttemptStatus } from '../../components/design-system/domain-status'
import { Notice } from '../../components/design-system/layout'
import { EmptyState, ErrorState, InlineError, LoadingState } from '../../components/design-system/states'
import { Button } from '../../components/ui/Button'
import { useProcessEvaluations, useSessionEvaluations } from '../../hooks/use-academic'
import { formatDecimal, plural } from '../../lib/format'
import { CALIFICACION } from '../../lib/labels'
import type { Sesion } from '../../types/api'

/** Resultados: procesar la evaluación (CU22) y abrir el detalle de cada intento para comentar (CU24). */
export function ResultsPanel({ sesion }: { sesion: Sesion }) {
  const q = useSessionEvaluations(sesion.id)
  const process = useProcessEvaluations(sesion.id)

  if (q.isPending) return <LoadingState label="Cargando resultados…" />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />

  const r = q.data
  const finalizada = r.estado_sesion === 'FINALIZADO'
  const p = process.data

  return (
    <div className="section" style={{ gap: '1.75rem' }}>
      <div className="section-head">
        <dl className="figures">
          <div>
            <dt>completados</dt>
            <dd>{r.resumen.finalizadas}</dd>
          </div>
          <div>
            <dt>cerrados sin finalizar</dt>
            <dd>{r.resumen.expiradas}</dd>
          </div>
          <div>
            <dt>en curso</dt>
            <dd>{r.resumen.en_progreso}</dd>
          </div>
          <div>
            <dt>evaluados</dt>
            <dd>{r.resumen.evaluadas}</dd>
          </div>
          <div>
            <dt>por evaluar</dt>
            <dd>{r.resumen.pendientes}</dd>
          </div>
        </dl>
        <Button
          variant={r.resumen.pendientes > 0 ? 'primary' : 'secondary'}
          icon="clipboard"
          onClick={() => process.mutate()}
          pending={process.isPending}
          pendingLabel="Evaluando…"
        >
          Evaluar intentos cerrados
        </Button>
      </div>

      {!finalizada && (
        <p className="small muted">
          Puedes evaluar los intentos ya cerrados en cualquier momento. Los estudiantes verán su resultado cuando finalices la sesión.
        </p>
      )}
      <InlineError error={process.error} />
      {p && (
        <Notice tone="ok" title="Evaluación procesada.">
            {plural(p.procesadas, 'intento revisado', 'intentos revisados')}: {p.registradas} con nota nueva, {p.actualizadas} actualizadas,{' '}
            {p.sin_cambios} sin cambios y {p.sin_calificar} sin calificar.
          {p.en_progreso_omitidas > 0 && ` ${plural(p.en_progreso_omitidas, 'intento sigue', 'intentos siguen')} en curso y no se evaluó.`}
        </Notice>
      )}

      {r.participaciones.length === 0 ? (
        <EmptyState icon="clipboard" title="Todavía no hay intentos">Cuando los estudiantes empiecen el caso, sus intentos aparecerán aquí.</EmptyState>
      ) : (
        <DataTable
          caption="Intentos de la sesión"
          rows={r.participaciones}
          rowKey={(x) => x.participacion_id}
          columns={[
            { key: 'estudiante', header: 'Estudiante', cell: (x) => <>{x.estudiante_nombre}<div className="small muted">{x.estudiante_correo}</div></> },
            { key: 'intento', header: 'Intento', numeric: true, cell: (x) => x.numero_intento },
            { key: 'estado', header: 'Estado', cell: (x) => <AttemptStatus estado={x.estado} motivo={x.motivo_cierre} /> },
            { key: 'calificacion', header: 'Calificación', cell: (x) => <>
              {x.estado === 'EN_PROGRESO' ? <span className="muted">—</span> : !x.evaluacion_registrada ? 'Por evaluar' : x.calificacion ? CALIFICACION[x.calificacion] : '—'}
              {x.evaluacion_registrada && x.requiere_procesamiento && <div><span className="tag tag-alert">Nota desactualizada</span></div>}
            </> },
            { key: 'nota', header: 'Nota', numeric: true, cell: (x) => x.nota_final ? `${formatDecimal(x.nota_final)} / ${formatDecimal(r.escala_max)}` : '—' },
            { key: 'acciones', header: 'Acciones', srOnlyHeader: true, cell: (x) => x.estado !== 'EN_PROGRESO' && <Link className="btn btn-secondary btn-sm" to={`/docente/sesiones/${sesion.id}/intentos/${x.participacion_id}`}>Ver detalle</Link> },
          ]}
        />
      )}

      {r.ausencias.length > 0 && (
        <section className="section" aria-labelledby="h-ausencias">
          <div className="section-head">
            <h2 id="h-ausencias">{finalizada ? 'Ausencias' : 'Aún no han ingresado'}</h2>
            <p>{finalizada ? 'Convocados que no iniciaron ningún intento. No equivale a una nota de cero.' : 'Convocados sin ningún intento por ahora.'}</p>
          </div>
          <ul className="rows">
            {r.ausencias.map((a) => (
              <li key={a.convocatoria_id}>
                <div className="row">
                  <div>
                    <div className="row-title">{a.estudiante_nombre}</div>
                    <div className="row-meta">{a.estudiante_correo}</div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
