// Navegación centralizada por rol, destino inicial y zonas permitidas.
// Las guardas solo ordenan la navegación: los permisos reales los aplica siempre la API.
import type { IconName } from '../components/ui/Icon'
import type { AppSession } from './auth-storage'

export type Zone = 'student' | 'teacher' | 'admin'

export interface NavItem {
  title: string
  href: string
  icon: IconName
  section: string
  /** Coincidencia exacta para marcar activo (inicio de cada portal). */
  end?: boolean
}

const studentNav: NavItem[] = [
  { title: 'Inicio', href: '/estudiante', icon: 'home', section: 'Mi actividad', end: true },
  { title: 'Mi aula', href: '/estudiante/aula', icon: 'classroom', section: 'Mi actividad' },
  { title: 'Mi sesión', href: '/estudiante/sesion', icon: 'calendar', section: 'Mi actividad' },
  { title: 'Resultados', href: '/estudiante/resultados', icon: 'chart', section: 'Seguimiento' },
  { title: 'Retroalimentación', href: '/estudiante/retroalimentacion', icon: 'message', section: 'Seguimiento' },
  { title: 'Avisos', href: '/estudiante/avisos', icon: 'bell', section: 'Seguimiento' },
]

const teacherNav: NavItem[] = [
  { title: 'Panel docente', href: '/docente', icon: 'home', section: 'Principal', end: true },
  { title: 'Aulas', href: '/docente/aulas', icon: 'classroom', section: 'Académico' },
  { title: 'Sesiones', href: '/docente/sesiones', icon: 'calendar', section: 'Académico' },
  { title: 'Casos', href: '/docente/casos', icon: 'book', section: 'Académico' },
  { title: 'Evaluación', href: '/docente/evaluacion', icon: 'clipboard', section: 'Evaluación y seguimiento' },
  { title: 'Mi cuenta', href: '/docente/cuenta', icon: 'key', section: 'Cuenta' },
]

const adminNav: NavItem[] = [
  { title: 'Inicio', href: '/admin', icon: 'home', section: 'Principal', end: true },
  { title: 'Usuarios', href: '/admin/usuarios', icon: 'users', section: 'Gestión' },
  { title: 'Aulas', href: '/admin/aulas', icon: 'classroom', section: 'Gestión' },
  { title: 'Entregas de correo', href: '/admin/entregas', icon: 'mail', section: 'Sistema' },
  { title: 'Mi cuenta', href: '/admin/cuenta', icon: 'key', section: 'Cuenta' },
]

export function zoneOf(session: AppSession): Zone {
  if (session.kind !== 'staff') return 'student'
  return session.user.rol === 'ADMINISTRADOR' ? 'admin' : 'teacher'
}

export function navigationFor(session: AppSession): NavItem[] {
  const zone = zoneOf(session)
  return zone === 'student' ? studentNav : zone === 'admin' ? adminNav : teacherNav
}

export function groupBySection(items: NavItem[]) {
  const groups: { section: string; items: NavItem[] }[] = []
  for (const item of items) {
    const last = groups[groups.length - 1]
    if (last && last.section === item.section) last.items.push(item)
    else groups.push({ section: item.section, items: [item] })
  }
  return groups
}

const ZONE_PREFIX: Record<Zone, string> = { student: '/estudiante', teacher: '/docente', admin: '/admin' }

/** Destino inicial según el tipo de token y el rol que devuelve el servidor. */
export function homePathFor(session: AppSession): string {
  return ZONE_PREFIX[zoneOf(session)]
}

/** Si una ruta pertenece a la zona de la sesión (para volver a ella tras ingresar). */
export function pathBelongsTo(session: AppSession, path: string): boolean {
  const prefix = ZONE_PREFIX[zoneOf(session)]
  return path === prefix || path.startsWith(`${prefix}/`)
}

export function roleLabel(session: AppSession): string {
  if (session.kind === 'student') return 'Estudiante'
  if (session.kind === 'results') return 'Estudiante (consulta de resultados)'
  return session.user.rol === 'ADMINISTRADOR' ? 'Administración' : 'Docente'
}

export function displayName(session: AppSession): string {
  return session.kind === 'staff' ? session.user.nombre_completo : session.correo
}
