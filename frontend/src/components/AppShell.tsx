import { Navigate, NavLink, Outlet, useLocation } from 'react-router'
import { useAuth } from '../auth/useAuth'
import { ROL } from '../lib/labels'

export function BrandMark({ size = 22 }: { size?: number }) {
  // Dos círculos que se cruzan: el yo y el otro de la psicología social.
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="9" cy="12" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="15" cy="12" r="6.5" fill="none" stroke="#9fb8d6" strokeWidth="1.8" />
    </svg>
  )
}

interface NavItem {
  to: string
  label: string
  end?: boolean
}

export function AppShell() {
  const { session, logout } = useAuth()
  const location = useLocation()
  if (!session) return <Navigate to="/ingresar" replace state={{ from: location.pathname }} />

  let nav: NavItem[] = []
  let who = ''
  let role = ''
  if (session.kind === 'staff' && session.user.rol === 'DOCENTE') {
    nav = [
      { to: '/inicio', label: 'Inicio' },
      { to: '/aulas', label: 'Mis aulas' },
      { to: '/casos', label: 'Mis casos' },
    ]
    who = session.user.nombre_completo
    role = ROL.DOCENTE
  } else if (session.kind === 'staff') {
    nav = [
      { to: '/admin/usuarios', label: 'Usuarios' },
      { to: '/admin/aulas', label: 'Aulas' },
    ]
    who = session.user.nombre_completo
    role = ROL[session.user.rol]
  } else if (session.kind === 'student') {
    nav = [{ to: '/estudiante', label: 'Mi sesión', end: true }]
    who = session.correo
    role = ROL.ESTUDIANTE
  } else {
    nav = [{ to: '/resultados', label: 'Mis resultados', end: true }]
    who = session.correo
    role = 'Consulta de resultados'
  }

  return (
    <>
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>
      <header className="app-header">
        <div className="app-header-inner">
          <NavLink to={nav[0]?.to ?? '/'} className="brand">
            <BrandMark />
            Iter Animi
          </NavLink>
          <nav className="app-nav" aria-label="Navegación principal">
            {nav.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="app-user">
            <div className="who">
              <strong>{who}</strong>
              {role}
            </div>
            <button type="button" onClick={() => logout('manual')}>
              Cerrar sesión
            </button>
          </div>
        </div>
      </header>
      <Outlet />
    </>
  )
}
