// Sesión de la interfaz. El backend emite tres tipos de token y cada uno abre una zona distinta:
//  - staff:   token "access" de docente o administrador (correo + contraseña)
//  - student: token "student", limitado a UNA convocatoria y su sesión EN_CURSO (correo + código)
//  - results: token "student_results", de solo lectura, con la sesión FINALIZADA (correo + código)
import type { Usuario, UUID } from '../types/api'

export type AppSession =
  | { kind: 'staff'; token: string; expiresAt: number; user: Usuario }
  | { kind: 'student'; token: string; expiresAt: number; sesionId: UUID; convocatoriaId: UUID; correo: string }
  | { kind: 'results'; token: string; expiresAt: number; sesionId: UUID; convocatoriaId: UUID; correo: string }

const KEY = 'iter-animi.session'

// Copia en memoria: disponible de forma síncrona para el cliente HTTP desde la primera petición
// (antes de que se ejecute cualquier efecto) y también si el almacenamiento está bloqueado.
let current: AppSession | null = null
/** Si al cargar había una sesión guardada que ya venció (para explicarlo en el acceso). */
let expiredOnLoad = false

export function hadExpiredSession() {
  return expiredOnLoad
}

export function currentToken(now = Date.now()): string | null {
  return current && current.expiresAt > now ? current.token : null
}

export function loadSession(now = Date.now()): AppSession | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as AppSession
    if (!parsed?.token || typeof parsed.expiresAt !== 'number') return null
    if (parsed.expiresAt <= now) {
      localStorage.removeItem(KEY)
      expiredOnLoad = true
      return null
    }
    current = parsed
    return parsed
  } catch {
    return null
  }
}

export function saveSession(session: AppSession | null) {
  current = session
  try {
    if (session) localStorage.setItem(KEY, JSON.stringify(session))
    else localStorage.removeItem(KEY)
  } catch {
    // Almacenamiento no disponible (modo privado): la sesión vive solo en memoria.
  }
}

export function expiresAtFrom(expiresInSeconds: number, now = Date.now()) {
  return now + expiresInSeconds * 1000
}
