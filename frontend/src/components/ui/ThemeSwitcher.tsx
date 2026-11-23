import { useId } from 'react'
import { useTheme } from '../../hooks/use-theme'
import { THEME_OPTIONS, type ThemePref } from '../../lib/theme'
import { Icon, type IconName } from './Icon'

const ICON: Record<ThemePref, IconName> = { light: 'sun', dark: 'moon', system: 'monitor' }

/**
 * Selector Claro / Oscuro / Sistema como grupo de radios nativos: se recorre con flechas y el estado
 * activo se indica con el radio marcado y el fondo. En compacto las etiquetas se conservan para lectores de pantalla.
 */
export function ThemeSwitcher({ compact = false }: { compact?: boolean }) {
  const { pref, resolved, setPref } = useTheme()
  const name = useId()
  return (
    <fieldset className={`theme-switch${compact ? ' is-compact' : ''}`}>
      <legend className={compact ? 'visually-hidden' : 'theme-switch-legend'}>Tema</legend>
      {THEME_OPTIONS.map((o) => (
        <label key={o.id} className="theme-option" title={o.id === 'system' ? `Sigue al sistema (ahora ${resolved === 'dark' ? 'oscuro' : 'claro'})` : o.label}>
          <input type="radio" name={name} value={o.id} checked={pref === o.id} onChange={() => setPref(o.id)} />
          <Icon name={ICON[o.id]} size={16} />
          <span className={compact ? 'visually-hidden' : undefined}>{o.label}</span>
        </label>
      ))}
    </fieldset>
  )
}
