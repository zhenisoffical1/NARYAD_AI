import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { AssistantButton } from '@/features/assistant/Assistant'
import { NotificationsBell } from '@/features/orders/NotificationsBell'
import { fetchOrders, orderKeys } from '@/shared/api/orders'
import { fetchPeople, shiftKeys } from '@/shared/api/reference'
import type { OrderListItem } from '@/shared/api/types'
import { clock } from '@/shared/lib/format'
import { useSession } from '@/shared/lib/session'
import { useHighlight } from '@/shared/lib/useLiveEvents'
import {
  Button,
  EmptyState,
  Icon,
  OrderTag,
  PersonStatusRow,
  Tabs,
  TagSkeleton,
  TopBar,
} from '@/shared/ui'

import { useShiftLabel, useShiftSummary } from './shift'
import { ShiftCounters } from './ShiftCounters'

type Tab = 'decisions' | 'active' | 'people'

const ACTIVE = { active: true, sort: 'urgency' as const, limit: 300 }
const RANK = { emergency: 0, high: 1, normal: 2, planned: 3 } as const

/** Что требует решения мастера: проверенные ИИ, отклонённые, просроченные. */
function needsDecision(o: OrderListItem): boolean {
  return o.status === 'AI_REVIEW' || o.status === 'REJECTED' || o.is_overdue
}

/** Главный экран мастера на телефоне: табло, «Новый наряд», решения, наряды, люди. */
export function MasterHome() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const user = useSession((s) => s.user)
  const [tab, setTab] = useState<Tab>('decisions')
  const summary = useShiftSummary()
  const shiftLabel = useShiftLabel(summary.data)
  const orders = useQuery({ queryKey: orderKeys.list(ACTIVE), queryFn: () => fetchOrders(ACTIVE) })
  const people = useQuery({ queryKey: shiftKeys.people, queryFn: fetchPeople })

  const all = orders.data ?? []
  const decisions = all
    .filter(needsDecision)
    .sort((a, b) => Number(b.is_overdue) - Number(a.is_overdue) || RANK[a.priority] - RANK[b.priority])
  const active = all.filter((o) => !needsDecision(o))
  const onShift = (people.data ?? []).filter((p) => p.state !== 'off_shift')

  return (
    <div className="flex min-h-dvh flex-col bg-bg text-ink">
      <TopBar
        title={t('master.title')}
        subtitle={shiftLabel || user?.short_name}
        right={
          <>
            <AssistantButton variant="phone" />
            <NotificationsBell />
            <button
              type="button"
              onClick={() => navigate('/m/profile')}
              aria-label={t('profile.open')}
              className="inline-flex size-12 items-center justify-center rounded-control active:bg-white/10"
            >
              <Icon name="user" size={24} />
            </button>
          </>
        }
      />
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-4 px-4 pt-4 pb-8">
        <ShiftCounters summary={summary.data} layout="grid" onOverdue={() => setTab('decisions')} />

        <Button size="xl" block icon="plus" onClick={() => navigate('/m/new')}>
          {t('master.newOrder')}
        </Button>

        <Tabs<Tab>
          label={t('master.title')}
          value={tab}
          onChange={setTab}
          items={[
            { value: 'decisions', label: t('master.decisions'), count: decisions.length },
            { value: 'active', label: t('master.active'), count: active.length },
            { value: 'people', label: t('master.people'), count: onShift.length },
          ]}
        />

        {orders.isPending && <TagSkeleton />}

        {tab === 'decisions' &&
          (decisions.length === 0 && orders.isSuccess ? (
            <EmptyState icon="check" title={t('master.noDecisions')} hint={t('master.noDecisionsHint')} />
          ) : (
            <div className="flex flex-col gap-3">
              {decisions.map((o) => (
                <DecisionItem key={o.id} order={o} onOpen={() => navigate(`/m/orders/${o.id}`)} />
              ))}
            </div>
          ))}

        {tab === 'active' &&
          (active.length === 0 && orders.isSuccess ? (
            <EmptyState icon="list" title={t('master.noActive')} />
          ) : (
            <div className="flex flex-col gap-3">
              {active.map((o) => (
                <LiveTag key={o.id} order={o} onOpen={() => navigate(`/m/orders/${o.id}`)} />
              ))}
            </div>
          ))}

        {tab === 'people' && (
          <div className="divide-y divide-line rounded-[12px] border border-line bg-surface px-2">
            {(people.data ?? []).map((p) => (
              <PersonStatusRow
                key={p.employee.id}
                name={p.employee.full_name}
                specialty={p.employee.specialty}
                state={p.state}
                orderNumber={p.current_order?.number}
                queueCount={p.queue_count}
                onClick={p.current_order ? () => navigate(`/m/orders/${p.current_order?.id}`) : undefined}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

function LiveTag({ order, onOpen }: { order: OrderListItem; onOpen: () => void }) {
  const changed = useHighlight(order.id)
  return <OrderTag key={changed} order={order} highlight={Boolean(changed)} onClick={onOpen} />
}

function DecisionItem({ order, onOpen }: { order: OrderListItem; onOpen: () => void }) {
  const { t } = useTranslation()
  let hint: string
  if (order.status === 'AI_REVIEW') {
    hint =
      order.ai_score !== null && order.ai_verdict
        ? t('master.confirmHint', { verdict: t(`verdict.${order.ai_verdict}`).toLowerCase(), score: order.ai_score })
        : order.ai_score !== null
          ? t('master.reviewHint')
          : t('verdict.running')
  } else if (order.status === 'REJECTED') {
    hint = t('master.rejectedShort')
  } else {
    hint = t('master.overdueHint', { time: clock(order.overdue_minutes) })
  }
  const danger = order.status === 'REJECTED' || order.is_overdue || order.ai_verdict === 'rework'
  return (
    <div className="flex flex-col gap-1.5">
      <p className={danger ? 'px-1 text-small font-semibold text-red' : 'px-1 text-small font-semibold text-accent'}>
        {hint}
      </p>
      <LiveTag order={order} onOpen={onOpen} />
    </div>
  )
}
