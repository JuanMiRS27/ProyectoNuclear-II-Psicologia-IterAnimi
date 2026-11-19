import { createContext } from 'react'
import type { ResolvedTheme, ThemePref } from '../lib/theme'

export interface ThemeContextValue {
  pref: ThemePref
  resolved: ResolvedTheme
  setPref: (pref: ThemePref) => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)
