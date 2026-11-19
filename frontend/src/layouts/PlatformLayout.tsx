import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation } from 'react-router'
import { ForbiddenState } from '../components/design-system/states'
import { Icon } from '../components/ui/Icon'
import { useSession } from '../hooks/use-session'
import { homePathFor, type Zone } from '../lib/navigation'
import { BrandMark } from './BrandMark'
import { RequireZone } from './guards'
import { Sidebar } from './Sidebar'

/** Portal autenticado (equivalente a (platform)/layout de Ágora): guarda + barra lateral + contenido. */
export function PlatformLayout({ zone }: { zone: Zone }) {
  return (
    <RequireZone zone={zone} forbidden={(home) => <Shell forbiddenHome={home} />}>
      <Shell />
    </RequireZone>
  )
}

function Shell({ forbiddenHome }: { forbiddenHome?: string }) {
  const { session } = useSession()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const drawerRef = useRef<HTMLDialogElement>(null)

  // Cerrar el menú móvil al navegar.
  useEffect(() => {
    const d = drawerRef.current
    if (d?.open) d.close()
  }, [location.pathname])

  useEffect(() => {
    const d = drawerRef.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])

  return (
    <div className="shell">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>
      <aside className="sidebar" aria-label="Menú">
        <Sidebar />
      </aside>

      <header className="topbar">
        <button type="button" className="topbar-menu" onClick={() => setOpen(true)} aria-label="Abrir menú">
          <Icon name="menu" size={22} />
        </button>
        <span className="topbar-brand">
          <BrandMark size={22} />
          Iter Animi
        </span>
      </header>

      <dialog ref={drawerRef} className="drawer" onClose={() => setOpen(false)} aria-label="Menú">
        <button type="button" className="drawer-close" onClick={() => setOpen(false)} aria-label="Cerrar menú">
          <Icon name="close" size={22} />
        </button>
        {open && <Sidebar onNavigate={() => setOpen(false)} />}
      </dialog>

      <div className="shell-main">
        {forbiddenHome ? <ForbiddenPage home={session ? homePathFor(session) : forbiddenHome} /> : <Outlet />}
      </div>
    </div>
  )
}

function ForbiddenPage({ home }: { home: string }) {
  return (
    <main className="page page-narrow" id="contenido">
      <ForbiddenState homePath={home} />
    </main>
  )
}
