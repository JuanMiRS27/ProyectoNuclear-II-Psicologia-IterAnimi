// Grupo (platform) del estudiante y vista inmersiva del simulador (misma guarda, sin barra lateral).
import type { RouteObject } from 'react-router'
import { PlatformLayout } from '../../layouts/PlatformLayout'
import { SimulatorLayout } from '../../layouts/SimulatorLayout'
import { view } from './lazy'

export const studentRoutes: RouteObject = {
  path: '/estudiante',
  element: <PlatformLayout zone="student" />,
  children: [
    { index: true, ...view(() => import('../../modules/student/StudentDashboardView'), 'StudentDashboardView') },
    { path: 'aula', ...view(() => import('../../modules/student/StudentClassroomView'), 'StudentClassroomView') },
    { path: 'sesion', ...view(() => import('../../modules/student/StudentSessionView'), 'StudentSessionView') },
    { path: 'resultados', ...view(() => import('../../modules/student/StudentResultsView'), 'StudentResultsView') },
    { path: 'resultados/:participationId', ...view(() => import('../../modules/student/StudentResultDetailView'), 'StudentResultDetailView') },
    { path: 'retroalimentacion', ...view(() => import('../../modules/student/StudentFeedbackView'), 'StudentFeedbackView') },
    { path: 'avisos', ...view(() => import('../../modules/student/StudentNoticesView'), 'StudentNoticesView') },
    { path: 'caso/:participationId/cierre', ...view(() => import('../../modules/simulator/AttemptClosedView'), 'AttemptClosedView') },
  ],
}

export const simulatorRoutes: RouteObject = {
  element: <SimulatorLayout />,
  children: [{ path: '/estudiante/caso/:participationId', ...view(() => import('../../modules/simulator/SimulatorPlayView'), 'SimulatorPlayView') }],
}
