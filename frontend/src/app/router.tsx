import { createBrowserRouter } from 'react-router'

import { AdminPage } from '@/features/admin/AdminPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { DemoEnterPage } from '@/features/demo/DemoEnterPage'
import { DemoPage } from '@/features/demo/DemoPage'
import { DevUiPage } from '@/features/dev/DevUiPage'
import { AnalyticsPage } from '@/features/desk/AnalyticsPage'
import { BossPage } from '@/features/desk/BossPage'
import { DeskShell } from '@/features/desk/DeskShell'
import { RatingDeskPage } from '@/features/desk/RatingDeskPage'
import { ReportsPage } from '@/features/desk/ReportsPage'
import { MasterHome } from '@/features/master/MasterHome'
import { MasterOrderPage } from '@/features/master/MasterOrderPage'
import { NewOrderPage } from '@/features/master/NewOrderPage'
import { PanelPage } from '@/features/panel/PanelPage'
import { MasterProfilePage } from '@/features/profile/MasterProfilePage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { ClosePage } from '@/features/worker/ClosePage'
import { RatingPage } from '@/features/worker/RatingPage'
import { ResultPage } from '@/features/worker/ResultPage'
import { WorkerHome } from '@/features/worker/WorkerHome'
import { WorkerOrderPage } from '@/features/worker/WorkerOrderPage'
import { WorkerShell } from '@/features/worker/WorkerShell'

import { RequireRole } from './RequireRole'
import { HomeRedirect } from './RouteScreens'
import { NotFoundScreen } from './SystemScreens'

export const router = createBrowserRouter([
  { path: '/', element: <HomeRedirect /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/dev/ui', element: <DevUiPage /> },
  { path: '/demo', element: <DemoPage /> },
  { path: '/demo/enter', element: <DemoEnterPage /> },
  {
    element: <RequireRole roles={['worker']} />,
    children: [
      {
        path: '/w',
        element: <WorkerShell />,
        children: [
          { index: true, element: <WorkerHome /> },
          { path: 'rating', element: <RatingPage /> },
          { path: 'profile', element: <ProfilePage /> },
          { path: 'orders/:id', element: <WorkerOrderPage /> },
          { path: 'orders/:id/close', element: <ClosePage /> },
          { path: 'orders/:id/result', element: <ResultPage /> },
        ],
      },
    ],
  },
  {
    element: <RequireRole roles={['master', 'admin']} />,
    children: [
      { path: '/m', element: <MasterHome /> },
      { path: '/m/new', element: <NewOrderPage /> },
      { path: '/m/profile', element: <MasterProfilePage /> },
      { path: '/m/orders/:id', element: <MasterOrderPage /> },
    ],
  },
  {
    element: <RequireRole roles={['master', 'boss', 'admin']} />,
    children: [
      {
        element: <DeskShell />,
        children: [
          { path: '/panel', element: <PanelPage /> },
          { path: '/panel/analytics', element: <AnalyticsPage /> },
          { path: '/panel/reports', element: <ReportsPage /> },
          { path: '/panel/rating', element: <RatingDeskPage /> },
        ],
      },
    ],
  },
  {
    element: <RequireRole roles={['boss', 'admin']} />,
    children: [{ element: <DeskShell />, children: [{ path: '/boss', element: <BossPage /> }] }],
  },
  {
    element: <RequireRole roles={['admin']} />,
    children: [{ element: <DeskShell />, children: [{ path: '/admin', element: <AdminPage /> }] }],
  },
  { path: '*', element: <NotFoundScreen /> },
])
