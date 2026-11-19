import { createContext } from 'react'
import type { AppSession } from '../lib/auth-storage'

export type LogoutReason = 'manual' | 'expired' | 'password-changed'

export interface SessionContextValue {
  session: AppSession | null
  /** Motivo del último cierre automático, para explicarlo en la pantalla de acceso. */
  notice: LogoutReason | null
  loginStaff: (correo: string, clave: string) => Promise<AppSession>
  loginStudent: (correo: string, codigo: string) => Promise<AppSession>
  logout: (reason?: LogoutReason) => void
  clearNotice: () => void
}

export const SessionContext = createContext<SessionContextValue | undefined>(undefined)
