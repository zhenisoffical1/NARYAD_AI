import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { NotificationsBell } from '@/features/orders/NotificationsBell'
import { useOrderAction } from '@/features/orders/useOrderAction'
import { fetchOrders, orderKeys } from '@/shared/api/orders'
import type { OrderListItem, OrderStatus } from '@/shared/api/types'
import { useSession } from '@/shared/lib/session'
import { useHighlight } from '@/shared/lib/useLiveEvents'
import { Button, EmptyState, OrderTag, SectionTitle, TagSkeleton, TopBar } from '@/shared/ui'

const PRIORITY_RANK = { emergency: 0, high: 1, normal: 2, planned: 3 } as const
const CURRENT: OrderStatus[] = ['IN_PROGRESS', 'PAUSED', 'REWORK', 'ACCEPTED']
const ACTIVE_QUERY = { active: true, limit: 100 }
const CLOSED_QUERY = { status: ['CLOSED' as OrderStatus], limit: 5 }

const byUrgency = (a: OrderListItem, b: OrderListItem) =>
  PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] ||
  a.deadline_at.localeCompare(b.deadline_at)

/** «Мои наряды»: что делаю сейчас, что ждёт ответа, очередь, проверка, недавно закрытые. */
export function WorkerHome() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const user = useSession((s) => s.user)
  const orders = useQuery({
    queryKey: orderKeys.list(ACTIVE_QUERY),
    queryFn: () => fetchOrders(ACTIVE_QUERY),
  })
  const recent = useQuery({
    queryKey: orderKeys.list(CLOSED_QUERY),
    queryFn: () => fetchOrders(CLOSED_QUERY),
  })

  const all = orders.data ?? []
  const current = all
    .filter((o) => CURRENT.includes(o.status))
    .sort((a, b) => CURRENT.indexOf(a.status) - CURRENT.indexOf(b.status) || byUrgency(a, b))
  const fresh = all.filter((o) => o.status === 'ISSUED').sort(byUrgency)
  const queue = all.filter((o) => o.status === 'QUEUED').sort(byUrgency)
  const review = all.filter((o) => o.status === 'DONE' || o.status === 'AI_REVIEW')
  const closed = recent.data ?? []
  const open = (o: OrderListItem) => navigate(`/w/orders/${o.id}`)
  const shift = user?.shift === 'night' ? t('worker.shift_night') : t('worker.shift_day')

  return (
    <>
      <TopBar
        title={t('worker.title')}
        subtitle={user ? `${user.short_name} · ${shift}` : undefined}
        right={<NotificationsBell />}
      />
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 pt-4 pb-8">
        {orders.isPending && (
          <div className="flex flex-col gap-3">
            <TagSkeleton />
            <TagSkeleton />
          </div>
        )}

        {orders.isSuccess && all.length === 0 && (
          <EmptyState icon="list" title={t('worker.empty')} hint={t('worker.emptyHint')} />
        )}

        {current.length > 0 && (
          <section className="flex flex-col gap-2.5">
            <SectionTitle>{t('worker.now')}</SectionTitle>
            {current.map((o) => (
              <Tag key={o.id} order={o} onOpen={open} />
            ))}
          </section>
        )}

        {fresh.length > 0 && (
          <section className="flex flex-col gap-2.5">
            <SectionTitle count={fresh.length} tone={fresh.some((o) => o.priority === 'emergency') ? 'danger' : 'default'}>
              {t('worker.new')}
            </SectionTitle>
            {fresh.map((o) => (
              <div key={o.id} className="flex flex-col gap-2">
                <Tag order={o} onOpen={open} />
                <QuickAnswer order={o} />
              </div>
            ))}
          </section>
        )}

        {queue.length > 0 && (
          <section className="flex flex-col gap-2.5">
            <SectionTitle count={queue.length}>{t('worker.queue')}</SectionTitle>
            {queue.map((o, i) => (
              <div key={o.id} className="flex flex-col gap-1">
                <span className="cond px-1 text-small text-ink-3">{t('worker.position', { n: i + 1 })}</span>
                <Tag order={o} onOpen={open} />
              </div>
            ))}
          </section>
        )}

        {review.length > 0 && (
          <section className="flex flex-col gap-2.5">
            <SectionTitle>{t('worker.review')}</SectionTitle>
            {review.map((o) => (
              <Tag key={o.id} order={o} onOpen={open} compact />
            ))}
          </section>
        )}

        {closed.length > 0 && (
          <section className="flex flex-col gap-2.5">
            <SectionTitle>{t('worker.closed')}</SectionTitle>
            {closed.map((o) => (
              <Tag key={o.id} order={o} onOpen={open} compact />
            ))}
          </section>
        )}
      </main>
    </>
  )
}

function Tag({
  order,
  onOpen,
  compact = false,
}: {
  order: OrderListItem
  onOpen: (o: OrderListItem) => void
  compact?: boolean
}) {
  const changed = useHighlight(order.id)
  return (
    <OrderTag
      key={changed}
      order={order}
      variant={compact ? 'compact' : 'full'}
      highlight={Boolean(changed)}
      showAssignee={false}
      onClick={() => onOpen(order)}
    />
  )
}

/** Ответ на новый наряд прямо из списка — два крупных нажатия вместо трёх. */
function QuickAnswer({ order }: { order: OrderListItem }) {
  const { t } = useTranslation()
  const action = useOrderAction(order)
  return (
    <div className="grid grid-cols-2 gap-2">
      <Button
        size="lg"
        loading={action.isPending && action.variables.action === 'accept'}
        disabled={action.isPending}
        onClick={() => action.mutate({ action: 'accept' })}
      >
        {t('actions.accept')}
      </Button>
      {order.priority !== 'emergency' && (
        <Button
          size="lg"
          variant="secondary"
          loading={action.isPending && action.variables.action === 'queue'}
          disabled={action.isPending}
          onClick={() => action.mutate({ action: 'queue' })}
        >
          {t('actions.queue')}
        </Button>
      )}
    </div>
  )
}
