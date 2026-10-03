import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router'

import { homeFor, useSession } from '@/shared/lib/session'

import { StubScreen } from './StubScreen'

export function HomeRedirect() {
  const user = useSession((s) => s.user)
  return <Navigate to={user ? homeFor(user.role) : '/login'} replace />
}

export type ScreenKey = 'worker' | 'master' | 'panel' | 'boss' | 'admin' | 'devUi' | 'demo'

export function Screen({ name }: { name: ScreenKey }) {
  const { t } = useTranslation()
  return <StubScreen title={t(`screens.${name}`)} />
}
