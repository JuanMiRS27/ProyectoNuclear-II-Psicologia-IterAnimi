import { NavLink } from 'react-router'
import { Icon } from '../components/ui/Icon'
import { useSession } from '../hooks/use-session'
import { displayName, groupBySection, homePathFor, navigationFor, roleLabel } from '../lib/navigation'
import { BrandMark } from './BrandMark'

/** Navegación agrupada por secciones, según el rol que determinó el servidor. */
export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { session, logout } = useSession()
  if (!session) return null
  const groups = groupBySection(navigationFor(session))
  const name = displayName(session)
  const initials = name
    .replace(/@.*/, '')
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join('')

  return (
    <div className="sidebar-inner">
      <NavLink to={homePathFor(session)} className="brand" onClick={onNavigate}>
        <BrandMark />
        <span>
          Iter Animi
          <small>{roleLabel(session)}</small>
        </span>
      </NavLink>

      <nav className="side-nav" aria-label="Navegación principal">
        {groups.map((g) => (
          <div key={g.section} className="side-group">
            <p className="side-group-title">{g.section}</p>
            <ul>
              {g.items.map((item) => (
                <li key={item.href}>
                  <NavLink to={item.href} end={item.end} onClick={onNavigate}>
                    <Icon name={item.icon} />
                    <span>{item.title}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="side-user">
        <span className="avatar" aria-hidden="true">
          {initials || '·'}
        </span>
        <span className="side-user-name" title={name}>
          {name}
        </span>
        <button type="button" className="side-logout" onClick={() => logout('manual')}>
          <Icon name="logout" />
          <span>Cerrar sesión</span>
        </button>
      </div>
    </div>
  )
}
