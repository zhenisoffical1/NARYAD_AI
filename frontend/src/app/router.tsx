import { createBrowserRouter } from 'react-router'

import { LoginPage } from '@/features/auth/LoginPage'
import { DevUiPage } from '@/features/dev/DevUiPage'

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
    children: [{ path: '/w/*', element: <Screen name="worker" /> }],
  },
  {
    element: <RequireRole roles={['master', 'admin']} />,
    children: [{ path: '/m/*', element: <Screen name="master" /> }],
  },
  {
    element: <RequireRole roles={['master', 'boss', 'admin']} />,
    children: [{ path: '/panel/*', element: <Screen name="panel" /> }],
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
