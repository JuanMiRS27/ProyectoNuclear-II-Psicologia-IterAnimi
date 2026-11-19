import type { ReactNode } from 'react'

/** Barra de acciones del simulador: fija abajo en móvil para que la confirmación siempre esté a mano. */
export function SimulatorActions({ back, hint, primary }: { back?: ReactNode; hint?: ReactNode; primary: ReactNode }) {
  return (
    <div className="sim-actions">
      {back ?? <span />}
      {hint && (
        <span className="hint" aria-live="polite">
          {hint}
        </span>
      )}
      {primary}
    </div>
  )
}
