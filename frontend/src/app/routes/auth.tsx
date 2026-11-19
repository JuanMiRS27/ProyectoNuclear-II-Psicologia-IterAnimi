// Grupo (auth): acceso público.
import type { RouteObject } from 'react-router'
import { AuthLayout } from '../../layouts/AuthLayout'
import { LoginView } from '../../modules/auth/LoginView'

export const authRoutes: RouteObject = {
  element: <AuthLayout />,
  children: [{ path: '/ingresar', element: <LoginView /> }],
}
