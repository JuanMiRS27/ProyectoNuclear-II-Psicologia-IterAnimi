import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { ApiError } from '../../api/client'
import { studentApi } from '../../api/endpoints'
import { ResultBreakdown } from '../../components/ResultBreakdown'
import { ErrorState, Loading } from '../../components/states'

export function ResultDetailPage() {
  const { participationId = '' } = useParams()
  const q = useQuery({ queryKey: ['student-result', participationId], queryFn: () => studentApi.result(participationId) })

  let body
  if (q.isPending) body = <Loading label="Cargando resultado…" />
  else if (q.isError)
    body =
      q.error instanceof ApiError && q.error.status === 409 ? (
        <div className="notice notice-info" role="status">
          <div>
            <strong>Este resultado está pendiente de revisión.</strong>
            Tu docente aún no ha registrado la evaluación de este intento. Vuelve a consultarlo más tarde.
          </div>
        </div>
      ) : (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      )
  else body = <ResultBreakdown r={q.data} viewer="student" />

  return (
    <main className="page page-narrow" id="contenido" style={{ maxWidth: '56rem' }}>
      <div>
        <div className="crumbs">
          <Link to="/resultados">Mis resultados</Link>
        </div>
        <h1>{q.data ? `Intento ${q.data.numero_intento}` : 'Resultado'}</h1>
      </div>
      {body}
      <div>
        <Link className="btn" to="/resultados">
          Volver a mis resultados
        </Link>
      </div>
    </main>
  )
}
