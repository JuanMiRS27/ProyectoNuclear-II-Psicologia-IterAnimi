import { createBrowserRouter, RouterProvider } from 'react-router'
import { HomeRedirect } from '../layouts/guards'
import { NotFoundView } from './NotFoundView'
import { adminRoutes } from './routes/admin'
import { authRoutes } from './routes/auth'
import { simulatorRoutes, studentRoutes } from './routes/student'
import { teacherRoutes } from './routes/teacher'

// Acceso público → portales autenticados por rol → simulador inmersivo. Cada portal tiene su guarda.
const router = createBrowserRouter([
  authRoutes,
  { path: '/', element: <HomeRedirect /> },
  simulatorRoutes,
  studentRoutes,
  teacherRoutes,
  adminRoutes,
  { path: '*', element: <NotFoundView /> },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
