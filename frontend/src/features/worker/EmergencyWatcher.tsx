import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { ReasonSheet } from '@/features/orders/ReasonSheet'
import { REJECT_REASONS } from '@/features/orders/reasons'
import { useOrderAction } from '@/features/orders/useOrderAction'
import { fetchOrders, orderKeys } from '@/shared/api/orders'
import type { OrderListItem, OrderStatus } from '@/shared/api/types'
import { EmergencyOverlay } from '@/shared/ui'

const ISSUED_EMERGENCY = { status: ['ISSUED' as OrderStatus], priority: ['emergency' as const] }

/**
 * Аварийный наряд не пропустить: пока есть выданный мне аварийный наряд без ответа,
 * поверх всего — красный экран со звуком и вибрацией. Список обновляется живыми событиями.
 */
export function EmergencyWatcher() {
  const emergencies = useQuery({
    queryKey: orderKeys.list(ISSUED_EMERGENCY),
    queryFn: () => fetchOrders(ISSUED_EMERGENCY),
    refetchInterval: 30_000,
  })
  const order = emergencies.data?.[0]
  return order ? <Alarm key={order.id} order={order} /> : null
}

function Alarm({ order }: { order: OrderListItem }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const action = useOrderAction(order)
  const [rejecting, setRejecting] = useState(false)

  return (
    <>
      <EmergencyOverlay
        open={!rejecting}
        number={order.number}
        equipment={order.equipment.name}
        inv={order.equipment.inv_number}
        section={order.section.name}
        description={order.description}
        busy={action.isPending}
        onAccept={() =>
          action.mutate(
            { action: 'accept' },
            { onSuccess: () => navigate(`/w/orders/${order.id}`) },
          )
        }
        onReject={() => setRejecting(true)}
      />
      <ReasonSheet
        open={rejecting}
        title={t('reasons.rejectTitle')}
        reasons={REJECT_REASONS}
        busy={action.isPending}
        onClose={() => setRejecting(false)}
        onSubmit={(reason) => action.mutate({ action: 'reject', reason })}
      />
    </>
  )
}
