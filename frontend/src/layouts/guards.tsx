import { Navigate, useLocation } from 'react-router'
import type { ReactNode } from 'react'
import { ForbiddenState } from '../components/design-system/states'
import { useSession } from '../hooks/use-session'
import { homePathFor, zoneOf, type Zone } from '../lib/navigation'

/**
 * Exige sesión y la zona correcta. La sesión se restaura de forma síncrona desde el almacenamiento,
 * así que no hay peticiones antes de conocer el token ni pantallas en blanco al refrescar.
 */
export function RequireZone({ zone, children, forbidden }: { zone: Zone; children: ReactNode; forbidden?: (home: string) => ReactNode }) {
  const { session } = useSession()
  const location = useLocation()
  if (!session) return <Navigate to="/ingresar" replace state={{ from: location.pathname }} />
  if (zoneOf(session) !== zone) {
    const home = homePathFor(session)
    return <>{forbidden ? forbidden(home) : <ForbiddenState homePath={home} />}</>
  }
  return <>{children}</>
}

export function HomeRedirect() {
  const { session } = useSession()
  return <Navigate to={session ? homePathFor(session) : '/ingresar'} replace />
}
