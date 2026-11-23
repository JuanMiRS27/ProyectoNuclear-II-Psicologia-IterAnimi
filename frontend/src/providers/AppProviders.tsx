import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { ApiError } from '../services/http-client'
import { SessionProvider } from './SessionProvider'
import { ThemeProvider } from './ThemeProvider'

/** Proveedores de la app (equivalente a app-providers de Ágora): tema, estado remoto y sesión. */
export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            refetchOnWindowFocus: false,
            // Los errores de permisos, inexistencia o sesión no se reintentan.
            retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
          },
          mutations: { retry: false },
        },
      }),
  )
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>{children}</SessionProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
