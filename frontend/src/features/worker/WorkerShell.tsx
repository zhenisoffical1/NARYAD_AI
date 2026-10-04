import { useTranslation } from 'react-i18next'
import { Outlet, useLocation, useNavigate } from 'react-router'

import { TabBar } from '@/shared/ui'

import { EmergencyWatcher } from './EmergencyWatcher'

/** Каркас приложения исполнителя: экран + нижние вкладки (кроме карточки наряда — там свои кнопки). */
export function WorkerShell() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const inOrder = pathname.startsWith('/w/orders/')

  return (
    <div className="flex min-h-dvh flex-col bg-bg text-ink">
      <div className="flex flex-1 flex-col">
        <Outlet />
      </div>
      {!inOrder && (
        <TabBar
          items={[
            {
              key: 'orders',
              label: t('worker.tabOrders'),
              icon: 'list',
              active: pathname === '/w' || pathname === '/w/',
              onClick: () => navigate('/w'),
            },
            {
              key: 'rating',
              label: t('worker.tabRating'),
              icon: 'chart',
              active: pathname.startsWith('/w/rating'),
              onClick: () => navigate('/w/rating'),
            },
            {
              key: 'profile',
              label: t('worker.tabProfile'),
              icon: 'user',
              active: pathname.startsWith('/w/profile'),
              onClick: () => navigate('/w/profile'),
            },
          ]}
        />
      )}
      <EmergencyWatcher />
    </div>
  )
}
