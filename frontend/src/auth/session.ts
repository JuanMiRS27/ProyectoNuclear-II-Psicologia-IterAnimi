// Sesión de la interfaz. El backend emite tres tipos de token y cada uno abre una zona distinta:
//  - staff:   token "access" de docente o administrador (correo + contraseña)
//  - student: token "student", limitado a UNA convocatoria y su sesión EN_CURSO (correo + código)
//  - results: token "student_results", de solo lectura, con la sesión FINALIZADA (correo + código)
import type { Usuario, UUID } from '../api/types'

export type AppSession =
  | { kind: 'staff'; token: string; expiresAt: number; user: Usuario }
  | { kind: 'student'; token: string; expiresAt: number; sesionId: UUID; convocatoriaId: UUID; correo: string }
  | { kind: 'results'; token: string; expiresAt: number; sesionId: UUID; convocatoriaId: UUID; correo: string }

const KEY = 'iter-animi.session'

// Copia en memoria: disponible de forma síncrona para el cliente HTTP desde la primera petición
// (antes de que se ejecute cualquier efecto) y también si el almacenamiento está bloqueado.
let current: AppSession | null = null

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

const ZONAS_DOCENTE = ['/inicio', '/aulas', '/casos', '/sesiones']

/** Si una ruta pertenece a la zona de la sesión (para volver a ella tras ingresar). */
export function pathBelongsTo(session: AppSession, path: string): boolean {
  const starts = (p: string) => path === p || path.startsWith(`${p}/`)
  if (session.kind === 'student') return starts('/estudiante')
  if (session.kind === 'results') return starts('/resultados')
  if (session.user.rol === 'ADMINISTRADOR') return starts('/admin')
  return ZONAS_DOCENTE.some(starts)
}

/** Ruta inicial de cada tipo de sesión; para el personal decide el rol que devuelve el servidor. */
export function homePathFor(session: AppSession): string {
  if (session.kind === 'student') return '/estudiante'
  if (session.kind === 'results') return '/resultados'
  return session.user.rol === 'ADMINISTRADOR' ? '/admin/usuarios' : '/inicio'
}
