// Estados de pantalla diseñados a propósito. Nunca se confunde «sin datos» con «no se pudo cargar».
import type { ReactNode } from 'react'
import { ApiError } from '../../services/http-client'
import { errorMessage } from '../../lib/errors'
import { ButtonLink } from '../ui/Button'
import { Icon, type IconName } from '../ui/Icon'

function StateFrame({ icon, tone, title, children, action, role }: { icon: IconName; tone: 'neutral' | 'alert' | 'lock'; title: string; children?: ReactNode; action?: ReactNode; role?: string }) {
  return (
    <div className={`state state-${tone}`} role={role}>
      <span className="state-icon">
        <Icon name={icon} size={22} />
      </span>
      <div className="state-body">
        <h2>{title}</h2>
        {children && <p>{children}</p>}
        {action && <div className="btn-row">{action}</div>}
      </div>
    </div>
  )
}

export function LoadingState({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="loading-bar" aria-hidden="true" />
      {label}
    </div>
  )
}

/** Vacío: invita a actuar. */
export function EmptyState({ title, children, action, icon = 'inbox' }: { title: string; children?: ReactNode; action?: ReactNode; icon?: IconName }) {
  return (
    <StateFrame icon={icon} tone="neutral" title={title} action={action}>
      {children}
    </StateFrame>
  )
}

/** Error de carga: explica qué pasó y permite reintentar. 403/404 se presentan como tales. */
export function ErrorState({ error, title = 'No se pudo cargar la información', onRetry }: { error: unknown; title?: string; onRetry?: () => void }) {
  const status = error instanceof ApiError ? error.status : null
  if (status === 403) return <ForbiddenState />
  if (status === 404)
    return (
      <StateFrame icon="search" tone="neutral" title="No encontramos lo que buscas">
        Puede que no exista o que tu cuenta no tenga acceso a ello.
      </StateFrame>
    )
  return (
    <StateFrame
      icon="alert"
      tone="alert"
      role="alert"
      title={title}
      action={
        onRetry && (
          <button type="button" className="btn btn-secondary" onClick={onRetry}>
            Reintentar
          </button>
        )
      }
    >
      {errorMessage(error)}
    </StateFrame>
  )
}

export function ForbiddenState({ homePath }: { homePath?: string }) {
  return (
    <StateFrame
      icon="lock"
      tone="lock"
      role="alert"
      title="No tienes acceso a esta sección"
      action={
        homePath && (
          <ButtonLink to={homePath} icon="home">
            Ir a mi inicio
          </ButtonLink>
        )
      }
    >
      Tu cuenta no tiene permiso para ver esta página. Si crees que es un error, consulta con la administración del simulador.
    </StateFrame>
  )
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <div className="notice notice-error" role="alert">
      <Icon name="alert" size={18} />
      <div>{errorMessage(error)}</div>
    </div>
  )
}

/** Helper para vistas: resuelve carga y error de una consulta antes de pintar su contenido. */
export function QueryBoundary<T>({
  query,
  loading,
  errorTitle,
  children,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown; data: T | undefined; refetch: () => unknown }
  loading?: string
  errorTitle?: string
  children: (data: T) => ReactNode
}) {
  if (query.isPending) return <LoadingState label={loading} />
  if (query.isError || query.data === undefined)
    return <ErrorState error={query.error} title={errorTitle} onRetry={() => void query.refetch()} />
  return <>{children(query.data)}</>
}
