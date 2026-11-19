// Preferencia visual: Claro, Oscuro o Sistema (por defecto).
// Solo se guarda la preferencia en localStorage, sin relación con la sesión ni las credenciales.
// index.html aplica el tema antes del primer render con la misma clave y la misma lógica, para evitar el destello.

export type ThemePref = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

export const THEME_KEY = 'iter-animi.theme'
export const THEME_OPTIONS: { id: ThemePref; label: string }[] = [
  { id: 'light', label: 'Claro' },
  { id: 'dark', label: 'Oscuro' },
  { id: 'system', label: 'Sistema' },
]

/** Color de la barra del navegador móvil para cada tema (coincide con --bg). */
const THEME_COLOR: Record<ResolvedTheme, string> = { light: '#fbfaf7', dark: '#131a24' }

export function readThemePref(): ThemePref {
  try {
    const v = localStorage.getItem(THEME_KEY)
    return v === 'light' || v === 'dark' || v === 'system' ? v : 'system'
  } catch {
    return 'system'
  }
}

export function writeThemePref(pref: ThemePref) {
  try {
    if (pref === 'system') localStorage.removeItem(THEME_KEY)
    else localStorage.setItem(THEME_KEY, pref)
  } catch {
    // Sin almacenamiento (modo privado estricto): la preferencia dura lo que la pestaña.
  }
}

export const systemQuery = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null)

export function resolveTheme(pref: ThemePref): ResolvedTheme {
  if (pref !== 'system') return pref
  return systemQuery()?.matches ? 'dark' : 'light'
}

export function applyTheme(theme: ResolvedTheme, pref: ThemePref) {
  const root = document.documentElement
  root.dataset.theme = theme
  root.dataset.themePref = pref
  root.style.colorScheme = theme
  root.style.backgroundColor = '' // el color provisional de index.html deja paso a --bg
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOR[theme])
}
