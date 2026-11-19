import { useContext } from 'react'
import { SessionContext } from '../providers/session-context'

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession debe usarse dentro de SessionProvider')
  return ctx
}
