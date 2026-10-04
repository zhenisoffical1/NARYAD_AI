import { createBrowserRouter } from 'react-router'

import { LoginPage } from '@/features/auth/LoginPage'
import { DevUiPage } from '@/features/dev/DevUiPage'
import { MasterHome } from '@/features/master/MasterHome'
import { MasterOrderPage } from '@/features/master/MasterOrderPage'
import { NewOrderPage } from '@/features/master/NewOrderPage'
import { PanelPage } from '@/features/panel/PanelPage'
import { ClosePage } from '@/features/worker/ClosePage'
import { RatingPage } from '@/features/worker/RatingPage'
import { ResultPage } from '@/features/worker/ResultPage'
import { WorkerHome } from '@/features/worker/WorkerHome'
import { WorkerOrderPage } from '@/features/worker/WorkerOrderPage'
import { WorkerShell } from '@/features/worker/WorkerShell'

import { RequireRole } from './RequireRole'
import { HomeRedirect, Screen } from './RouteScreens'
import { NotFoundScreen } from './SystemScreens'

export const router = createBrowserRouter([
  { path: '/', element: <HomeRedirect /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/dev/ui', element: <DevUiPage /> },
  { path: '/demo', element: <Screen name="demo" /> },
  {
    element: <RequireRole roles={['worker']} />,
    children: [
      {
        path: '/w',
        element: <WorkerShell />,
        children: [
          { index: true, element: <WorkerHome /> },
          { path: 'rating', element: <RatingPage /> },
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
      { path: '/m/orders/:id', element: <MasterOrderPage /> },
    ],
  },
  {
    element: <RequireRole roles={['master', 'boss', 'admin']} />,
    children: [{ path: '/panel', element: <PanelPage /> }],
  },
  {
    element: <RequireRole roles={['boss', 'admin']} />,
    children: [{ path: '/boss/*', element: <Screen name="boss" /> }],
  },
  {
    element: <RequireRole roles={['admin']} />,
    children: [{ path: '/admin/*', element: <Screen name="admin" /> }],
  },
  { path: '*', element: <NotFoundScreen /> },
])
