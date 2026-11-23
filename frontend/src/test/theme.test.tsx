import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ThemeSwitcher } from '../components/ui/ThemeSwitcher'
import { THEME_KEY } from '../lib/theme'
import { ThemeProvider } from '../providers/ThemeProvider'

// matchMedia controlable: permite simular el cambio de tema del sistema operativo.
function mockSystem(dark: boolean) {
  const listeners = new Set<(e: MediaQueryListEvent) => void>()
  const mq = {
    matches: dark,
    media: '(prefers-color-scheme: dark)',
    addEventListener: (_: string, fn: (e: MediaQueryListEvent) => void) => listeners.add(fn),
    removeEventListener: (_: string, fn: (e: MediaQueryListEvent) => void) => listeners.delete(fn),
  }
  vi.stubGlobal('matchMedia', () => mq)
  return {
    set(next: boolean) {
      mq.matches = next
      listeners.forEach((fn) => fn({ matches: next } as MediaQueryListEvent))
    },
  }
}

const root = () => document.documentElement

function renderSwitcher() {
  render(
    <ThemeProvider>
      <ThemeSwitcher />
    </ThemeProvider>,
  )
}

describe('tema claro, oscuro y del sistema', () => {
  beforeEach(() => {
    localStorage.clear()
    delete root().dataset.theme
  })
  afterEach(() => vi.unstubAllGlobals())

  it('por defecto usa Sistema y sigue sus cambios en vivo', () => {
    const system = mockSystem(false)
    renderSwitcher()
    expect(screen.getByRole('radio', { name: /Sistema/ })).toBeChecked()
    expect(root().dataset.theme).toBe('light')
    act(() => system.set(true))
    expect(root().dataset.theme).toBe('dark')
    expect(root().style.colorScheme).toBe('dark')
    act(() => system.set(false))
    expect(root().dataset.theme).toBe('light')
    expect(localStorage.getItem(THEME_KEY)).toBeNull()
  })

  it('una elección manual se guarda, se impone al sistema y vuelve a Sistema al pedirlo', async () => {
    const system = mockSystem(false)
    renderSwitcher()
    await userEvent.click(screen.getByRole('radio', { name: /Oscuro/ }))
    expect(root().dataset.theme).toBe('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    act(() => system.set(false))
    expect(root().dataset.theme).toBe('dark') // con Oscuro elegido, el sistema no manda
    await userEvent.click(screen.getByRole('radio', { name: /Sistema/ }))
    expect(root().dataset.theme).toBe('light')
    expect(localStorage.getItem(THEME_KEY)).toBeNull()
    // Solo se guarda la preferencia visual: nada relacionado con la sesión.
    expect(Object.keys(localStorage)).toEqual([])
  })

  it('al recargar respeta la preferencia guardada', () => {
    mockSystem(true)
    localStorage.setItem(THEME_KEY, 'light')
    renderSwitcher()
    expect(screen.getByRole('radio', { name: /Claro/ })).toBeChecked()
    expect(root().dataset.theme).toBe('light')
  })
})
