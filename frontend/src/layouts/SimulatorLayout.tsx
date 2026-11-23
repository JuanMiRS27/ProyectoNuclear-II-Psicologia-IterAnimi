import { Outlet } from 'react-router'
import { RequireZone } from './guards'

/** Vista inmersiva del simulador: sin barra lateral, pero dentro de la misma guarda del portal estudiantil. */
export function SimulatorLayout() {
  return (
    <RequireZone zone="student">
      <Outlet />
    </RequireZone>
  )
}
