import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { fetchOrder, orderKeys } from '@/shared/api/orders'
import { ActionBar, TagSkeleton, TopBar } from '@/shared/ui'

import { OrderManageActions, OrderManageBody } from './OrderManage'

/** Карточка наряда для мастера на телефоне. */
export function MasterOrderPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const orderId = Number(useParams().id)
  const detail = useQuery({ queryKey: orderKeys.detail(orderId), queryFn: () => fetchOrder(orderId) })
  const order = detail.data

  return (
    <div className="flex min-h-dvh flex-col bg-bg text-ink">
      <TopBar
        title={order ? t('manage.order', { n: order.number }) : '…'}
        subtitle={order ? t(`status.${order.status}`) : undefined}
        onBack={() => navigate('/m')}
      />
      <main className="mx-auto w-full max-w-xl flex-1 px-4 pt-4 pb-6">
        {order ? <OrderManageBody order={order} /> : <TagSkeleton />}
      </main>
      {order && (
        <ActionBar>
          <OrderManageActions order={order} />
        </ActionBar>
      )}
    </div>
  )
}
