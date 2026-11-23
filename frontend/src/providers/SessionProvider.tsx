import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { expiresAtFrom, hadExpiredSession, loadSession, saveSession, type AppSession } from '../lib/auth-storage'
import { authService } from '../services/auth-service'
import { ApiError, configureClient } from '../services/http-client'
import { SessionContext, type LogoutReason, type SessionContextValue } from './session-context'

/**
 * Arranque y ciclo de vida de la sesión (equivalente a AuthSessionSync de Ágora):
 * restaura el token sin peticiones prematuras, revalida el perfil del personal sin vaciar la caché,
 * cierra al expirar y limpia todos los datos privados al cambiar de identidad.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState<AppSession | null>(() => loadSession())
  const [notice, setNotice] = useState<LogoutReason | null>(() => (session ? null : hadExpiredSession() ? 'expired' : null))
  const sessionRef = useRef(session)
  sessionRef.current = session

  const apply = useCallback(
    (next: AppSession | null, resetCache = true) => {
      sessionRef.current = next
      saveSession(next)
      setSession(next)
      // Al cambiar de identidad, ningún dato de la sesión anterior debe verse en la siguiente.
      // (Refrescar el perfil de la misma cuenta no vacía la caché: dejaría consultas en vuelo sin dueño.)
      if (resetCache) queryClient.clear()
    },
    [queryClient],
  )

  const logout = useCallback(
    (reason: LogoutReason = 'manual') => {
      if (!sessionRef.current) return
      apply(null)
      setNotice(reason === 'manual' ? null : reason)
    },
    [apply],
  )

  useEffect(() => {
    configureClient({ onUnauthorized: () => logout('expired') })
  }, [logout])

  // Cierre automático al vencer el token, aunque la pestaña quede abierta.
  useEffect(() => {
    if (!session) return
    const ms = session.expiresAt - Date.now()
    const timer = window.setTimeout(() => logout('expired'), Math.max(ms, 0))
    return () => window.clearTimeout(timer)
  }, [session, logout])

  // El rol y el estado de la cuenta se revalidan con el servidor al recargar.
  useEffect(() => {
    const current = sessionRef.current
    if (current?.kind !== 'staff') return
    authService
      .me()
      .then((user) => {
        if (sessionRef.current?.kind === 'staff') apply({ ...sessionRef.current, user }, false)
      })
      .catch(() => {
        /* Un 401 ya cierra la sesión desde el cliente; otros errores no la invalidan. */
      })
    // Solo al montar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loginStaff = useCallback(
    async (correo: string, clave: string) => {
      const token = await authService.login(correo, clave)
      const user = await authService.me(token.access_token)
      const next: AppSession = { kind: 'staff', token: token.access_token, expiresAt: expiresAtFrom(token.expires_in), user }
      setNotice(null)
      apply(next)
      return next
    },
    [apply],
  )

  const loginStudent = useCallback(
    async (correo: string, codigo: string) => {
      let next: AppSession
      try {
        const t = await authService.studentLogin(correo, codigo)
        next = {
          kind: 'student',
          token: t.access_token,
          expiresAt: expiresAtFrom(t.expires_in),
          sesionId: t.sesion_id,
          convocatoriaId: t.convocatoria_id,
          correo,
        }
      } catch (err) {
        // Con credenciales correctas el servidor responde 403 cuando la sesión no admite el ingreso
        // (no iniciada, finalizada, plazo vencido...). Si ya finalizó, el mismo código abre la
        // consulta de resultados; si no, se muestra el motivo original del servidor.
        if (!(err instanceof ApiError) || err.status !== 403) throw err
        let r
        try {
          r = await authService.resultsLogin(correo, codigo)
        } catch {
          throw err
        }
        next = {
          kind: 'results',
          token: r.access_token,
          expiresAt: expiresAtFrom(r.expires_in),
          sesionId: r.sesion_id,
          convocatoriaId: r.convocatoria_id,
          correo,
        }
      }
      setNotice(null)
      apply(next)
      return next
    },
    [apply],
  )

  const value = useMemo<SessionContextValue>(
    () => ({ session, notice, loginStaff, loginStudent, logout, clearNotice: () => setNotice(null) }),
    [session, notice, loginStaff, loginStudent, logout],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
