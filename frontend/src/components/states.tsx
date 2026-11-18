import { Link } from 'react-router'
import { ApiError } from '../api/client'
import { errorMessage } from '../lib/errors'

export function Loading({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      {label}
    </div>
  )
}


/** Error de carga: distingue "no se pudo cargar" de "no hay datos". */
export function ErrorState({
  error,
  title = 'No se pudo cargar la información',
  onRetry,
}: {
  error: unknown
  title?: string
  onRetry?: () => void
}) {
  const status = error instanceof ApiError ? error.status : null
  if (status === 403) return <Forbidden />
  if (status === 404)
    return (
      <div className="state">
        <h2>No encontramos lo que buscas</h2>
        <p>Puede que no exista o que no tengas acceso a él.</p>
      </div>
    )
  return (
    <div className="state" role="alert">
      <h2>{title}</h2>
      <p>{errorMessage(error)}</p>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Reintentar
        </button>
      )}
    </div>
  )
}

export function Empty({ title, children, action }: { title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="state">
      <h2>{title}</h2>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function Forbidden({ homePath }: { homePath?: string }) {
  return (
    <main className="page page-narrow" id="contenido">
      <div className="state" role="alert">
        <h1>No tienes acceso a esta sección</h1>
        <p>Tu cuenta no tiene permiso para ver esta página. Si crees que es un error, consulta con la administración del simulador.</p>
        {homePath && (
          <Link className="btn" to={homePath}>
            Ir a mi inicio
          </Link>
        )}
      </div>
    </main>
  )
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <div className="notice notice-error" role="alert">
      <div>{errorMessage(error)}</div>
    </div>
  )
}
