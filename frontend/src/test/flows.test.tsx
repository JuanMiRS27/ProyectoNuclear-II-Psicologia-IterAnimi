import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { LoginPage } from '../features/login/LoginPage'
import { SimulatorPage } from '../features/student/SimulatorPage'
import { questionnaire } from './fixtures'

type Reply = { status: number; body?: unknown }
type Handler = (url: string, init: RequestInit) => Reply | Promise<Reply> | undefined

function mockFetch(handler: Handler) {
  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = typeof input === 'string' ? input : input.toString()
    const r = (await handler(url, init)) ?? { status: 404, body: { detail: 'no mock' } }
    return new Response(r.body === undefined ? null : JSON.stringify(r.body), {
      status: r.status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

function renderAt(path: string, routes: { path: string; element: ReactNode }[]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  )
  return router
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.unstubAllGlobals())

describe('acceso', () => {
  it('valida los campos antes de llamar al servidor', async () => {
    const fetch = mockFetch(() => undefined)
    renderAt('/ingresar', [{ path: '/ingresar', element: <LoginPage /> }])
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByText('Escribe tu correo institucional.')).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('con la sesión finalizada, el mismo código abre la consulta de resultados', async () => {
    mockFetch((url) => {
      if (url.endsWith('/auth/student/login')) return { status: 403, body: { detail: 'La sesión ya finalizó.' } }
      if (url.endsWith('/auth/student/results-login'))
        return { status: 200, body: { access_token: 'r', token_type: 'bearer', expires_in: 3600, sesion_id: 's1', convocatoria_id: 'c1', alcance: 'resultados:lectura' } }
    })
    const router = renderAt('/ingresar', [
      { path: '/ingresar', element: <LoginPage /> },
      { path: '/resultados', element: <p>Zona de resultados</p> },
    ])
    await userEvent.click(screen.getByLabelText('Con código de acceso'))
    await userEvent.type(screen.getByLabelText('Correo institucional'), 'est@uni.edu.co')
    await userEvent.type(screen.getByLabelText('Código de acceso'), 'ABCD-EFGH-JKMN')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByText('Zona de resultados')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/resultados')
  })

  it('muestra el motivo del servidor si la sesión aún no admite ingresos', async () => {
    mockFetch((url) => {
      if (url.endsWith('/auth/student/login')) return { status: 403, body: { detail: 'La sesión aún no ha sido iniciada por el docente.' } }
      if (url.endsWith('/auth/student/results-login'))
        return { status: 403, body: { detail: 'Los resultados estarán disponibles cuando la sesión finalice.' } }
    })
    renderAt('/ingresar', [{ path: '/ingresar', element: <LoginPage /> }])
    await userEvent.click(screen.getByLabelText('Con código de acceso'))
    await userEvent.type(screen.getByLabelText('Correo institucional'), 'est@uni.edu.co')
    await userEvent.type(screen.getByLabelText('Código de acceso'), 'ABCDEFGHJKMN')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByText('La sesión aún no ha sido iniciada por el docente.')).toBeInTheDocument()
  })
})

describe('simulador', () => {
  beforeEach(() => {
    localStorage.setItem(
      'iter-animi.session',
      JSON.stringify({ kind: 'student', token: 'tok', expiresAt: Date.now() + 3_600_000, sesionId: 's1', convocatoriaId: 'c1', correo: 'e@u.co' }),
    )
  })

  it('confirma una sola vez, conserva la selección ante un error y avanza solo con la confirmación del servidor', async () => {
    let puts = 0
    let release: (r: Reply) => void = () => {}
    mockFetch((url, init) => {
      if (url.endsWith('/questionnaire')) return { status: 200, body: questionnaire({ caso: { nombre: 'Caso de prueba', desarrollo_situacional: null, historia: null } }) }
      if (init.method === 'PUT') {
        puts += 1
        return new Promise<Reply>((resolve) => {
          release = resolve
        })
      }
      if (url.endsWith('/student/participations/p1'))
        return { status: 200, body: { estado: 'EN_PROGRESO', tiempo_restante_segundos: 1000, progreso: { total_preguntas: 3, respondidas: 1, pendientes: 2, porcentaje: 33 } } }
    })
    renderAt('/estudiante/caso/p1', [{ path: '/estudiante/caso/:participationId', element: <SimulatorPage /> }])

    const confirm = await screen.findByRole('button', { name: 'Confirmar respuesta' })
    expect(confirm).toBeDisabled()
    expect(screen.getByText('Pregunta 1')).toBeInTheDocument()

    await userEvent.click(screen.getByLabelText(/Opción B/))
    await userEvent.dblClick(confirm)
    // Mientras se envía, el botón queda bloqueado: un doble clic no duplica el envío.
    expect(await screen.findByRole('button', { name: 'Guardando…' })).toBeDisabled()
    expect(puts).toBe(1)

    release({ status: 500, body: null })
    expect(await screen.findByRole('alert')).toHaveTextContent('Tu selección se conservó')
    expect(screen.getByLabelText(/Opción B/)).toBeChecked()
    expect(screen.getByText('Pregunta 1')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar respuesta' }))
    release({ status: 200, body: { pregunta_id: 'q1', opcion_id: 'o2', respondida_en: 'x', actualizada_en: 'x' } })
    await waitFor(() => expect(screen.getByText('Pregunta 2')).toBeInTheDocument())
    expect(puts).toBe(2)
  })
})
