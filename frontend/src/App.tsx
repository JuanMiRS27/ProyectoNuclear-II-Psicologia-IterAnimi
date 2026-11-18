import { createBrowserRouter, RouterProvider } from 'react-router'
import { HomeRedirect, RequireZone } from './auth/guards'
import { AppShell } from './components/AppShell'
import { AdminSpacesPage } from './features/admin/AdminSpacesPage'
import { UsersPage } from './features/admin/UsersPage'
import { LoginPage } from './features/login/LoginPage'
import { NotFoundPage } from './features/NotFoundPage'
import { ResultDetailPage } from './features/results/ResultDetailPage'
import { ResultsHomePage } from './features/results/ResultsHomePage'
import { AttemptClosedPage } from './features/student/AttemptClosedPage'
import { SimulatorPage } from './features/student/SimulatorPage'
import { StudentHomePage } from './features/student/StudentHomePage'
import { CaseDetailPage } from './features/teacher/cases/CaseDetailPage'
import { CaseImportPage } from './features/teacher/cases/CaseImportPage'
import { CasesPage } from './features/teacher/cases/CasesPage'
import { DashboardPage } from './features/teacher/DashboardPage'
import { EvaluationDetailPage } from './features/teacher/sessions/EvaluationDetailPage'
import { ScheduleSessionPage } from './features/teacher/sessions/ScheduleSessionPage'
import { SessionDetailPage } from './features/teacher/sessions/SessionDetailPage'
import { SpaceDetailPage } from './features/teacher/spaces/SpaceDetailPage'
import { SpacesPage } from './features/teacher/spaces/SpacesPage'

const router = createBrowserRouter([
  { path: '/ingresar', element: <LoginPage /> },
  { path: '/', element: <HomeRedirect /> },
  {
    // El simulador ocupa toda la pantalla: modo de lectura sin la navegación general.
    element: <RequireZone zone="student" />,
    children: [{ path: '/estudiante/caso/:participationId', element: <SimulatorPage /> }],
  },
  {
    element: <AppShell />,
    children: [
      {
        element: <RequireZone zone="docente" />,
        children: [
          { path: '/inicio', element: <DashboardPage /> },
          { path: '/aulas', element: <SpacesPage /> },
          { path: '/aulas/:spaceId', element: <SpaceDetailPage /> },
          { path: '/aulas/:spaceId/asignar', element: <ScheduleSessionPage /> },
          { path: '/sesiones/:sessionId', element: <SessionDetailPage /> },
          { path: '/sesiones/:sessionId/intentos/:participationId', element: <EvaluationDetailPage /> },
          { path: '/casos', element: <CasesPage /> },
          { path: '/casos/importar', element: <CaseImportPage /> },
          { path: '/casos/:caseId', element: <CaseDetailPage /> },
        ],
      },
      {
        element: <RequireZone zone="admin" />,
        children: [
          { path: '/admin/usuarios', element: <UsersPage /> },
          { path: '/admin/aulas', element: <AdminSpacesPage /> },
        ],
      },
      {
        element: <RequireZone zone="student" />,
        children: [
          { path: '/estudiante', element: <StudentHomePage /> },
          { path: '/estudiante/caso/:participationId/cierre', element: <AttemptClosedPage /> },
        ],
      },
      {
        element: <RequireZone zone="results" />,
        children: [
          { path: '/resultados', element: <ResultsHomePage /> },
          { path: '/resultados/:participationId', element: <ResultDetailPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])

export function App() {
  return <RouterProvider router={router} />
}
