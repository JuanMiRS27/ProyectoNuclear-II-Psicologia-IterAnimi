import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ThemeContext } from './theme-context'
import { applyTheme, readThemePref, resolveTheme, systemQuery, writeThemePref, type ResolvedTheme, type ThemePref } from '../lib/theme'


/**
 * Tema de la interfaz. Con «Sistema» sigue los cambios de prefers-color-scheme en vivo.
 * El primer valor coincide con el que ya aplicó index.html, así que montar el proveedor no provoca destellos.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>(readThemePref)
  const [systemDark, setSystemDark] = useState(() => systemQuery()?.matches ?? false)

  useEffect(() => {
    const mq = systemQuery()
    if (!mq) return
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    // Respaldo: al volver a la pestaña se relee el sistema por si el cambio ocurrió sin evento.
    const recheck = () => setSystemDark(mq.matches)
    const onVisible = () => document.visibilityState === 'visible' && recheck()
    mq.addEventListener('change', onChange)
    window.addEventListener('focus', recheck)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      mq.removeEventListener('change', onChange)
      window.removeEventListener('focus', recheck)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  // Otra pestaña cambió la preferencia: se sincroniza.
  useEffect(() => {
    const onStorage = () => setPrefState(readThemePref())
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const resolved: ResolvedTheme = pref === 'system' ? (systemDark ? 'dark' : 'light') : resolveTheme(pref)

  useEffect(() => applyTheme(resolved, pref), [resolved, pref])

  const setPref = useCallback((next: ThemePref) => {
    writeThemePref(next)
    setPrefState(next)
  }, [])

  const value = useMemo(() => ({ pref, resolved, setPref }), [pref, resolved, setPref])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
