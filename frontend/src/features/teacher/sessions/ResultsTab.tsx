import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { evaluationsApi } from '../../../api/endpoints'
import type { Sesion } from '../../../api/types'
import { AttemptStatus } from '../../../components/domainStatus'
import { Empty, ErrorState, InlineError, Loading } from '../../../components/states'
import { formatDecimal, plural } from '../../../lib/format'
import { CALIFICACION } from '../../../lib/labels'

export function ResultsTab({ sesion }: { sesion: Sesion }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['evaluations', sesion.id], queryFn: () => evaluationsApi.list(sesion.id) })
  const process = useMutation({
    mutationFn: () => evaluationsApi.process(sesion.id),
    onSuccess: () => qc.invalidateQueries(),
  })

  if (q.isPending) return <Loading label="Cargando resultados…" />
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
        <button
          type="button"
          className={`btn${r.resumen.pendientes > 0 ? ' btn-primary' : ''}`}
          onClick={() => process.mutate()}
          disabled={process.isPending}
          aria-busy={process.isPending}
        >
          {process.isPending ? 'Evaluando…' : 'Evaluar intentos cerrados'}
        </button>
      </div>

      {!finalizada && (
        <p className="small muted">
          Puedes evaluar los intentos ya cerrados en cualquier momento. Los estudiantes verán su resultado cuando finalices la sesión.
        </p>
      )}
      <InlineError error={process.error} />
      {p && (
        <div className="notice notice-ok" role="status">
          <div>
            <strong>Evaluación procesada.</strong>
            {plural(p.procesadas, 'intento revisado', 'intentos revisados')}: {p.registradas} con nota nueva, {p.actualizadas} actualizadas,{' '}
            {p.sin_cambios} sin cambios y {p.sin_calificar} sin calificar.
            {p.en_progreso_omitidas > 0 && ` ${plural(p.en_progreso_omitidas, 'intento sigue', 'intentos siguen')} en curso y no se evaluó.`}
          </div>
        </div>
      )}

      {r.participaciones.length === 0 ? (
        <Empty title="Todavía no hay intentos">Cuando los estudiantes empiecen el caso, sus intentos aparecerán aquí.</Empty>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">Intentos de la sesión</caption>
            <thead>
              <tr>
                <th>Estudiante</th>
                <th className="num">Intento</th>
                <th>Estado</th>
                <th>Calificación</th>
                <th className="num">Nota</th>
                <th>
                  <span className="visually-hidden">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {r.participaciones.map((x) => (
                <tr key={x.participacion_id}>
                  <td>
                    {x.estudiante_nombre}
                    <div className="small muted">{x.estudiante_correo}</div>
                  </td>
                  <td className="num">{x.numero_intento}</td>
                  <td>
                    <AttemptStatus estado={x.estado} motivo={x.motivo_cierre} />
                  </td>
                  <td>
                    {x.estado === 'EN_PROGRESO' ? (
                      <span className="muted">—</span>
                    ) : !x.evaluacion_registrada ? (
                      'Por evaluar'
                    ) : x.calificacion ? (
                      CALIFICACION[x.calificacion]
                    ) : (
                      '—'
                    )}
                    {x.evaluacion_registrada && x.requiere_procesamiento && (
                      <div>
                        <span className="tag tag-alert">Nota desactualizada</span>
                      </div>
                    )}
                  </td>
                  <td className="num">{x.nota_final ? `${formatDecimal(x.nota_final)} / ${formatDecimal(r.escala_max)}` : '—'}</td>
                  <td>
                    {x.estado !== 'EN_PROGRESO' && (
                      <Link className="btn btn-sm" to={`/sesiones/${sesion.id}/intentos/${x.participacion_id}`}>
                        Ver detalle
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
