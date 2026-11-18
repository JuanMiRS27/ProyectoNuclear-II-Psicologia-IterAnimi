import { useQuery } from '@tanstack/react-query'
import { Link, Navigate, useParams } from 'react-router'
import { studentApi } from '../../api/endpoints'
import { AttemptStatus } from '../../components/domainStatus'
import { ErrorState, Loading } from '../../components/states'
import { formatDateTime } from '../../lib/format'
import { MOTIVO_CIERRE } from '../../lib/labels'

/** Estado del intento tras salir del simulador, tal como lo informa el servidor. */
export function AttemptClosedPage() {
  const { participationId = '' } = useParams()
  const q = useQuery({ queryKey: ['participation', participationId], queryFn: () => studentApi.participation(participationId), gcTime: 0 })

  if (q.isPending)
    return (
      <main className="page page-narrow" id="contenido">
        <Loading />
      </main>
    )
  if (q.isError)
    return (
      <main className="page page-narrow" id="contenido">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </main>
    )

  const p = q.data
  if (p.estado === 'EN_PROGRESO') return <Navigate to={`/estudiante/caso/${p.id}`} replace />

  return (
    <main className="page page-narrow" id="contenido">
      <div>
        <h1>{p.estado === 'FINALIZADA' ? 'Entregaste el caso' : 'Tu intento se cerró'}</h1>
        <div className="row-meta" style={{ marginTop: '0.6rem' }}>
          <AttemptStatus estado={p.estado} motivo={p.motivo_cierre} />
          <span>Intento {p.numero_intento} de {p.intentos_autorizados}</span>
        </div>
      </div>

      <section className="panel" style={{ display: 'grid', gap: '1rem' }}>
        <dl className="defs">
          <dt>Decisiones respondidas</dt>
          <dd>
            {p.progreso.respondidas} de {p.progreso.total_preguntas}
          </dd>
          {p.fin && (
            <>
              <dt>Cierre</dt>
              <dd>{formatDateTime(p.fin)}</dd>
            </>
          )}
          {p.motivo_cierre && (
            <>
              <dt>Motivo</dt>
              <dd>{MOTIVO_CIERRE[p.motivo_cierre]}</dd>
            </>
          )}
        </dl>
        <div className="notice notice-info">
          <div>
            <strong>Tu resultado aún no está disponible.</strong>
            Podrás consultar tu calificación y la retroalimentación cuando tu docente finalice la sesión. Para verlas, vuelve a ingresar con tu
            correo y el mismo código de acceso.
          </div>
        </div>
      </section>

      <div>
        <Link className="btn btn-primary" to="/estudiante">
          Volver a mi sesión
        </Link>
      </div>
    </main>
  )
}
