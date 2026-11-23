import { Navigate, useParams } from 'react-router'
import { AttemptStatus } from '../../components/design-system/domain-status'
import { Definitions, Notice, Page, PageHeader, Panel } from '../../components/design-system/layout'
import { QueryBoundary } from '../../components/design-system/states'
import { ButtonLink } from '../../components/ui/Button'
import { useAttemptState } from '../../hooks/use-student'
import { formatDateTime } from '../../lib/format'
import { MOTIVO_CIERRE } from '../../lib/labels'

/** Estado del intento al salir del simulador, tal como lo informa el servidor. */
export function AttemptClosedView() {
  const { participationId = '' } = useParams()
  const q = useAttemptState(participationId)
  return (
    <Page width="narrow">
      <QueryBoundary query={q} loading="Consultando tu intento…">
        {(p) =>
          p.estado === 'EN_PROGRESO' ? (
            <Navigate to={`/estudiante/caso/${p.id}`} replace />
          ) : (
            <>
              <PageHeader
                title={p.estado === 'FINALIZADA' ? 'Entregaste el caso' : 'Tu intento se cerró'}
                meta={
                  <>
                    <AttemptStatus estado={p.estado} motivo={p.motivo_cierre} />
                    <span>
                      Intento {p.numero_intento} de {p.intentos_autorizados}
                    </span>
                  </>
                }
              />
              <Panel>
                <Definitions
                  items={[
                    { term: 'Decisiones respondidas', value: `${p.progreso.respondidas} de ${p.progreso.total_preguntas}` },
                    ...(p.fin ? [{ term: 'Cierre', value: formatDateTime(p.fin) }] : []),
                    ...(p.motivo_cierre ? [{ term: 'Motivo', value: MOTIVO_CIERRE[p.motivo_cierre] }] : []),
                  ]}
                />
              </Panel>
              <Notice tone="info" title="Tu resultado aún no está disponible.">
                Podrás consultar tu calificación y la retroalimentación cuando tu docente finalice la sesión. Para verlas, vuelve a ingresar
                con tu correo y el mismo código de acceso.
              </Notice>
              <div className="btn-row">
                <ButtonLink to="/estudiante/sesion" variant="primary">
                  Volver a mi sesión
                </ButtonLink>
                <ButtonLink to="/estudiante">Ir al inicio</ButtonLink>
              </div>
            </>
          )
        }
      </QueryBoundary>
    </Page>
  )
}
