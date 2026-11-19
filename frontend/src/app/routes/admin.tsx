// Grupo (platform) de administración.
import type { RouteObject } from 'react-router'
import { PlatformLayout } from '../../layouts/PlatformLayout'
import { view } from './lazy'

export const adminRoutes: RouteObject = {
  path: '/admin',
  element: <PlatformLayout zone="admin" />,
  children: [
    { index: true, ...view(() => import('../../modules/admin/AdminDashboardView'), 'AdminDashboardView') },
    { path: 'usuarios', ...view(() => import('../../modules/admin/UsersView'), 'UsersView') },
    { path: 'aulas', ...view(() => import('../../modules/admin/AdminClassroomsView'), 'AdminClassroomsView') },
    { path: 'entregas', ...view(() => import('../../modules/admin/DeliveriesView'), 'DeliveriesView') },
    { path: 'cuenta', ...view(() => import('../../modules/auth/AccountView'), 'AccountView') },
  ],
}
