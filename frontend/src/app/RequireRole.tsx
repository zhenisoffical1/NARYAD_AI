import { Navigate, Outlet, useLocation } from 'react-router'

import type { Role } from '@/shared/api/types'
import { useSession } from '@/shared/lib/session'
import { useLiveEvents } from '@/shared/lib/useLiveEvents'

import { ForbiddenScreen } from './SystemScreens'

/** Пускает только указанные роли. Та же проверка повторяется на сервере (require_role). */
export function RequireRole({ roles }: { roles: Role[] }) {
  const user = useSession((s) => s.user)
  const location = useLocation()
  useLiveEvents()

  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  if (!roles.includes(user.role)) {
    return <ForbiddenScreen />
  }
  return <Outlet />
}
