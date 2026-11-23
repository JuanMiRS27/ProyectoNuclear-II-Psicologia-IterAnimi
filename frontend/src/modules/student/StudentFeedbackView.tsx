import { Link } from 'react-router'
import { Page, PageHeader } from '../../components/design-system/layout'
import { EmptyState, ErrorState, LoadingState } from '../../components/design-system/states'
import { useSession } from '../../hooks/use-session'
import { useStudentResultDetails, useStudentResults } from '../../hooks/use-student'

/**
 * Retroalimentación: los comentarios que escribió el docente en cada intento evaluado, con su contexto
 * y enlace al resultado. Se distinguen del resumen automático que genera el sistema.
 */
export function StudentFeedbackView() {
  const { session } = useSession()
  const results = useStudentResults()
  const disponibles = (results.data?.resultados ?? []).filter((r) => r.disponible)
  const details = useStudentResultDetails(disponibles.map((r) => r.participacion_id))

  if (session?.kind !== 'results')
    return (
      <Page width="narrow">
        <PageHeader title="Retroalimentación" />
        <EmptyState icon="message" title="Los comentarios llegarán con tus resultados">
          Tu docente puede escribir comentarios sobre tu intento después de evaluarlo. Los verás aquí cuando la sesión haya finalizado y vuelvas a
          ingresar con tu código.
        </EmptyState>
      </Page>
    )

  if (results.isPending || details.some((d) => d.isPending))
    return (
      <Page width="narrow">
        <LoadingState label="Cargando comentarios…" />
      </Page>
    )
  if (results.isError)
    return (
      <Page width="narrow">
        <ErrorState error={results.error} onRetry={() => results.refetch()} />
      </Page>
    )
  const failed = details.find((d) => d.isError)
  const withComment = details.map((d) => d.data).filter((d) => d && d.retroalimentacion_general)

  return (
    <Page width="reading">
      <PageHeader title="Retroalimentación" description={`Comentarios de tu docente sobre «${results.data.caso_nombre}».`} />
      {failed && <ErrorState error={failed.error} title="No se pudieron cargar algunos comentarios" />}
      {withComment.length === 0 && !failed ? (
        <EmptyState icon="message" title="Tu docente aún no ha dejado comentarios">
          Puedes revisar el resumen automático de cada intento en <Link to="/estudiante/resultados">tus resultados</Link>.
        </EmptyState>
      ) : (
        <ul className="feedback-list">
          {withComment.map((d) => (
            <li key={d!.participacion_id}>
              <article className="feedback-card">
                <header>
                  <span className="feedback-source">Comentario del docente</span>
                  <h2>Intento {d!.numero_intento}</h2>
                </header>
                <div className="reading">
                  {d!.retroalimentacion_general!
                    .split(/\n+/)
                    .filter((p) => p.trim())
                    .map((p, i) => (
                      <p key={i}>{p}</p>
                    ))}
                </div>
                <details className="auto-summary">
                  <summary>Ver el resumen automático del sistema</summary>
                  <p className="small">{d!.retroalimentacion_automatica}</p>
                </details>
                <Link to={`/estudiante/resultados/${d!.participacion_id}`} className="side-link">
                  Ver el resultado completo
                </Link>
              </article>
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}
