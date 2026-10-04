import { useTranslation } from 'react-i18next'

import type { OrderDetail } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'
import { Icon, InvPlate, StatusBadge } from '@/shared/ui'

const STRIPE = {
  emergency: 'hatch-red',
  high: 'bg-red',
  normal: 'bg-ink',
  planned: 'border-b-2 border-dashed border-ink-3 bg-surface',
} as const

/** Шапка карточки наряда: та же бирка, что в списке, но крупнее и со всеми реквизитами. */
export function OrderHeader({ order }: { order: OrderDetail }) {
  const { t } = useTranslation()
  return (
    <section className="overflow-hidden rounded-[8px] border border-line bg-surface">
      <div aria-hidden className={cn('h-2.5', STRIPE[order.priority])} />
      <div className="flex flex-col gap-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="cond text-[30px] leading-none font-bold">№{order.number}</span>
            <InvPlate inv={order.equipment.inv_number} />
          </div>
          <StatusBadge status={order.status} />
        </div>
        <div className="flex flex-wrap items-center gap-2 text-small">
          <span
            className={cn(
              'stamp inline-flex h-6 items-center rounded-tag px-1.5',
              order.priority === 'emergency' && 'bg-red-strong text-white',
              order.priority === 'high' && 'border-2 border-red text-red',
              (order.priority === 'normal' || order.priority === 'planned') && 'border-2 border-line text-ink-2',
            )}
          >
            {t(`priority.${order.priority}`)}
          </span>
          {order.priority !== 'planned' && (
            <span className="text-ink-3">
              {order.type === 'planned' ? t('issue.planned') : t('issue.unplanned')}
            </span>
          )}
        </div>
        <div>
          <h2 className="text-h2 font-semibold [overflow-wrap:anywhere]">{order.equipment.name}</h2>
          <p className="mt-0.5 text-ink-2">{order.section.name}</p>
        </div>
        {order.equipment_stopped && !['DONE', 'AI_REVIEW', 'CLOSED', 'CANCELLED'].includes(order.status) && (
          <p className="flex items-center gap-2 rounded-[6px] bg-red-soft px-3 py-2 text-small font-medium text-red">
            <Icon name="alert" size={18} />
            {t('worker.stopped')}
          </p>
        )}
      </div>
    </section>
  )
}
