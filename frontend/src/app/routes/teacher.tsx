// Grupo (platform) del docente.
import type { RouteObject } from 'react-router'
import { PlatformLayout } from '../../layouts/PlatformLayout'
import { view } from './lazy'

export const teacherRoutes: RouteObject = {
  path: '/docente',
  element: <PlatformLayout zone="teacher" />,
  children: [
    { index: true, ...view(() => import('../../modules/teacher/TeacherDashboardView'), 'TeacherDashboardView') },
    { path: 'aulas', ...view(() => import('../../modules/academic/ClassroomsView'), 'ClassroomsView') },
    { path: 'aulas/:spaceId', ...view(() => import('../../modules/academic/ClassroomDetailView'), 'ClassroomDetailView') },
    { path: 'aulas/:spaceId/programar', ...view(() => import('../../modules/academic/ScheduleSessionView'), 'ScheduleSessionView') },
    { path: 'sesiones', ...view(() => import('../../modules/teacher/SessionsListView'), 'SessionsListView') },
    { path: 'sesiones/:sessionId', ...view(() => import('../../modules/teacher/SessionDetailView'), 'SessionDetailView') },
    {
      path: 'sesiones/:sessionId/intentos/:participationId',
      ...view(() => import('../../modules/evaluation/TeacherEvaluationView'), 'TeacherEvaluationView'),
    },
    { path: 'casos', ...view(() => import('../../modules/cases/CasesListView'), 'CasesListView') },
    { path: 'casos/nuevo', ...view(() => import('../../modules/cases/CaseCreateView'), 'CaseCreateView') },
    { path: 'casos/:caseId', ...view(() => import('../../modules/cases/CaseDetailView'), 'CaseDetailView') },
    { path: 'evaluacion', ...view(() => import('../../modules/teacher/EvaluationQueueView'), 'EvaluationQueueView') },
    { path: 'cuenta', ...view(() => import('../../modules/auth/AccountView'), 'AccountView') },
  ],
}
