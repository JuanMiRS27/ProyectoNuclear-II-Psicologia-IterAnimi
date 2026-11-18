import { Navigate, Outlet, useLocation } from 'react-router'
import type { Rol } from '../api/types'
import { Forbidden } from '../components/states'
import { useAuth } from './useAuth'
import { homePathFor, type AppSession } from './session'

type Zone = 'docente' | 'admin' | 'student' | 'results'

function allowed(session: AppSession, zone: Zone) {
  const rol: Rol | null = session.kind === 'staff' ? session.user.rol : null
  switch (zone) {
    case 'docente':
      return rol === 'DOCENTE'
    case 'admin':
      return rol === 'ADMINISTRADOR'
    case 'student':
      return session.kind === 'student'
    case 'results':
      return session.kind === 'results'
  }
}

/** Protege una zona. Ocultar opciones no sustituye los permisos del backend: es solo navegación. */
export function RequireZone({ zone }: { zone: Zone }) {
  const { session } = useAuth()
  const location = useLocation()
  if (!session) return <Navigate to="/ingresar" replace state={{ from: location.pathname }} />
  if (!allowed(session, zone)) return <Forbidden homePath={homePathFor(session)} />
  return <Outlet />
}

export function HomeRedirect() {
  const { session } = useAuth()
  return <Navigate to={session ? homePathFor(session) : '/ingresar'} replace />
}
