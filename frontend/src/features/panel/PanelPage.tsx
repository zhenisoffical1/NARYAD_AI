import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { IssueOrderForm } from '@/features/master/IssueOrderForm'
import { OrderManageActions, OrderManageBody } from '@/features/master/OrderManage'
import { useShiftLabel, useShiftSummary } from '@/features/master/shift'
import { ShiftCounters } from '@/features/master/ShiftCounters'
import { NotificationsBell } from '@/features/orders/NotificationsBell'
import { setLanguage } from '@/i18n'
import { fetchOrder, fetchOrders, orderKeys } from '@/shared/api/orders'
import {
  fetchEquipment,
  fetchPeople,
  fetchSections,
  REFERENCE_STALE,
  refKeys,
  shiftKeys,
} from '@/shared/api/reference'
import type { OrderListItem, OrderStatus, PersonState, PersonStatus, Priority } from '@/shared/api/types'
import { cn, isToday } from '@/shared/lib/format'
import { useSession } from '@/shared/lib/session'
import { useHighlight } from '@/shared/lib/useLiveEvents'
import { Button, Drawer, Icon, LiveDot, OrderTag, PersonStatusRow, TagSkeleton } from '@/shared/ui'

const ACTIVE = { active: true, sort: 'urgency' as const, limit: 500 }
const CLOSED = { status: ['CLOSED' as OrderStatus], limit: 40 }

type ColumnKey = 'issued' | 'accepted' | 'inProgress' | 'queued' | 'done' | 'overdue'

/** main — статус, который колонка и так называет: его на бирке не повторяем */
const COLUMNS: { key: ColumnKey; title: string; statuses: OrderStatus[]; main?: OrderStatus }[] = [
  { key: 'issued', title: 'panel.colIssued', statuses: ['ISSUED', 'REJECTED'], main: 'ISSUED' },
  { key: 'accepted', title: 'panel.colAccepted', statuses: ['ACCEPTED'], main: 'ACCEPTED' },
  { key: 'inProgress', title: 'panel.colInProgress', statuses: ['IN_PROGRESS', 'PAUSED', 'REWORK'], main: 'IN_PROGRESS' },
  { key: 'queued', title: 'panel.colQueued', statuses: ['QUEUED'], main: 'QUEUED' },
  { key: 'done', title: 'panel.colDone', statuses: ['DONE', 'AI_REVIEW', 'CLOSED'] },
  { key: 'overdue', title: 'panel.colOverdue', statuses: [] },
]

const PEOPLE_GROUPS: PersonState[] = ['free', 'queue', 'busy', 'off_shift']
const GROUP_TITLE = {
  free: 'panel.groupFree',
  queue: 'panel.groupQueue',
  busy: 'panel.groupBusy',
  off_shift: 'panel.groupOff',
} as const
const RANK = { emergency: 0, high: 1, normal: 2, planned: 3 } as const

/** Панель смены для мастера и руководителя (десктоп). */
export function PanelPage() {
  const { t, i18n } = useTranslation()
  const [params, setParams] = useSearchParams()
  const user = useSession((s) => s.user)
  const signOut = useSession((s) => s.signOut)
  const summary = useShiftSummary()
  const shiftLabel = useShiftLabel(summary.data)
  const canIssue = user?.role === 'master' || user?.role === 'admin'

  const active = useQuery({ queryKey: orderKeys.list(ACTIVE), queryFn: () => fetchOrders(ACTIVE) })
  const closed = useQuery({ queryKey: orderKeys.list(CLOSED), queryFn: () => fetchOrders(CLOSED) })
  const people = useQuery({ queryKey: shiftKeys.people, queryFn: fetchPeople })
  const sections = useQuery({ queryKey: refKeys.sections, queryFn: fetchSections, staleTime: REFERENCE_STALE })
  const equipment = useQuery({ queryKey: refKeys.equipment, queryFn: fetchEquipment, staleTime: REFERENCE_STALE })

  const filter = {
    section: Number(params.get('section')) || null,
    equipment: Number(params.get('equipment')) || null,
    person: Number(params.get('person')) || null,
    priority: (params.get('priority') as Priority | null) || null,
  }
  const setFilter = (key: string, value: string | number | null) => {
    const next = new URLSearchParams(params)
    if (value === null || value === '') next.delete(key)
    else next.set(key, String(value))
    if (key === 'section') next.delete('equipment')
    setParams(next, { replace: true })
  }
  const openOrder = Number(params.get('order')) || null
  const creating = params.get('new') === '1'

  const orders = useMemo(() => {
    const todayClosed = (closed.data ?? []).filter((o) => o.closed_at && isToday(o.closed_at))
    return [...(active.data ?? []), ...todayClosed].filter(
      (o) =>
        (!filter.section || o.section.id === filter.section) &&
        (!filter.equipment || o.equipment.id === filter.equipment) &&
        (!filter.person || o.assignee?.id === filter.person) &&
        (!filter.priority || o.priority === filter.priority),
    )
  }, [active.data, closed.data, filter.section, filter.equipment, filter.person, filter.priority])

  const columns = COLUMNS.map((column) => ({
    ...column,
    items: orders
      .filter((o) =>
        column.key === 'overdue' ? o.is_overdue : !o.is_overdue && column.statuses.includes(o.status),
      )
      .sort((a, b) => RANK[a.priority] - RANK[b.priority] || a.deadline_at.localeCompare(b.deadline_at)),
  }))

  const anyFilter = filter.section || filter.equipment || filter.person || filter.priority

  return (
    <div className="flex h-dvh flex-col bg-bg text-ink">
      <header className="flex h-16 shrink-0 items-center gap-4 border-b-4 border-bar-line bg-bar px-5 text-on-bar">
        <img src="/brand/km-logo-white.png" alt="АО «Костанайские Минералы»" className="h-9 w-auto" />
        <span aria-hidden className="h-8 w-px bg-white/25" />
        <div className="min-w-0">
          <p className="text-h2 leading-tight font-semibold">{t('panel.title')}</p>
          <p className="truncate text-small opacity-80">{shiftLabel}</p>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <LiveDot withLabel />
          {canIssue && (
            <Button variant="inverse" size="md" icon="plus" className="ml-2" onClick={() => setFilter('new', '1')}>
              {t('master.newOrder')}
            </Button>
          )}
          <NotificationsBell />
          <span aria-hidden className="mx-1 h-8 w-px bg-white/25" />
          <div className="hidden text-right lg:block">
            <p className="text-small font-semibold">{user?.short_name}</p>
            <p className="text-stamp opacity-75">{user ? t(`roles.${user.role}`) : ''}</p>
          </div>
          <button
            type="button"
            onClick={() => setLanguage(i18n.language === 'kk' ? 'ru' : 'kk')}
            className="ml-2 min-h-10 rounded-control px-2.5 text-small font-semibold hover:bg-white/10"
          >
            {t('common.switchLanguage')}
          </button>
          <button
            type="button"
            onClick={signOut}
            aria-label={t('common.logout')}
            title={t('common.logout')}
            className="inline-flex size-10 items-center justify-center rounded-control hover:bg-white/10"
          >
            <Icon name="logout" size={22} />
          </button>
        </div>
      </header>

      <div className="flex shrink-0 flex-wrap items-stretch gap-4 border-b border-line bg-surface px-5 py-3">
        <div className="min-w-[520px] flex-1">
          <ShiftCounters summary={summary.data} onOverdue={() => setFilter('priority', null)} />
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <FilterSelect
            label={t('panel.section')}
            value={filter.section}
            onChange={(v) => setFilter('section', v)}
            all={t('panel.allSections')}
            options={(sections.data ?? []).map((s) => ({ value: s.id, label: s.name }))}
          />
          <FilterSelect
            label={t('panel.equipment')}
            value={filter.equipment}
            onChange={(v) => setFilter('equipment', v)}
            all={t('panel.allEquipment')}
            options={(equipment.data ?? [])
              .filter((e) => !filter.section || e.section_id === filter.section)
              .map((e) => ({ value: e.id, label: `${e.inv_number} · ${e.name}` }))}
          />
          <FilterSelect
            label={t('panel.person')}
            value={filter.person}
            onChange={(v) => setFilter('person', v)}
            all={t('panel.allPeople')}
            options={(people.data ?? []).map((p) => ({ value: p.employee.id, label: p.employee.full_name }))}
          />
          <FilterSelect
            label={t('panel.priority')}
            value={filter.priority}
            onChange={(v) => setFilter('priority', v)}
            all={t('panel.allPriorities')}
            options={(['emergency', 'high', 'normal', 'planned'] as const).map((p) => ({
              value: p,
              label: t(`priority.${p}`),
            }))}
          />
          {anyFilter ? (
            <Button
              variant="quiet"
              size="md"
              icon="x"
              onClick={() => setParams(new URLSearchParams(openOrder ? { order: String(openOrder) } : {}), { replace: true })}
            >
              {t('panel.reset')}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-[264px] shrink-0 flex-col overflow-y-auto border-r border-line bg-surface">
          <h2 className="sticky top-0 z-10 border-b border-line bg-surface px-4 py-3 text-small font-semibold text-ink-2">
            {t('panel.peopleTitle')}
          </h2>
          <PeopleColumn
            people={people.data ?? []}
            selected={filter.person}
            onSelect={(id) => setFilter('person', id === filter.person ? null : id)}
          />
        </aside>

        <main className="min-w-0 flex-1 overflow-x-auto">
          <div className="grid h-full min-w-[1020px] grid-cols-6 gap-2.5 p-3">
            {columns.map((column) => (
              <section key={column.key} className="flex min-h-0 flex-col rounded-[8px] bg-plate/60">
                <h3
                  className={cn(
                    'flex items-center justify-between gap-2 border-b-2 px-3 py-2.5 text-small font-semibold',
                    column.key === 'overdue' ? 'border-red text-red' : 'border-line text-ink-2',
                  )}
                >
                  {t(column.title as 'panel.colIssued')}
                  <span
                    className={cn(
                      'cond inline-flex h-6 min-w-6 items-center justify-center rounded-[3px] px-1.5',
                      column.key === 'overdue' && column.items.length ? 'bg-red-strong text-white' : 'bg-surface text-ink',
                    )}
                  >
                    {column.items.length}
                  </span>
                </h3>
                <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
                  {active.isPending && <TagSkeleton />}
                  {column.items.map((order) => (
                    <KanbanCard
                      key={order.id}
                      order={order}
                      hideStatus={order.status === column.main}
                      selected={order.id === openOrder}
                      onOpen={() => setFilter('order', order.id)}
                    />
                  ))}
                  {active.isSuccess && column.items.length === 0 && (
                    <p className="px-2 py-6 text-center text-small text-ink-3">{t('panel.empty')}</p>
                  )}
                </div>
              </section>
            ))}
          </div>
        </main>
      </div>

      {openOrder && <OrderDrawer orderId={openOrder} onClose={() => setFilter('order', null)} />}

      <Drawer open={creating} title={t('issue.title')} onClose={() => setFilter('new', null)} width={520}>
        {creating && (
          <IssueOrderForm
            onIssued={(order) => {
              const next = new URLSearchParams(params)
              next.delete('new')
              next.set('order', String(order.id))
              setParams(next, { replace: true })
            }}
          />
        )}
      </Drawer>
    </div>
  )
}

function KanbanCard({
  order,
  selected,
  hideStatus,
  onOpen,
}: {
  order: OrderListItem
  selected: boolean
  hideStatus: boolean
  onOpen: () => void
}) {
  const changed = useHighlight(order.id)
  return (
    <OrderTag
      key={changed}
      order={order}
      variant="compact"
      highlight={Boolean(changed)}
      selected={selected}
      hideStatus={hideStatus}
      onClick={onOpen}
    />
  )
}

function PeopleColumn({
  people,
  selected,
  onSelect,
}: {
  people: PersonStatus[]
  selected: number | null
  onSelect: (id: number) => void
}) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col pb-4">
      {PEOPLE_GROUPS.map((state) => {
        const group = people.filter((p) => p.state === state)
        if (!group.length) return null
        return (
          <section key={state} className="px-2 pt-3">
            <p className="flex items-center justify-between px-2 pb-1 text-small font-semibold text-ink-3">
              {t(GROUP_TITLE[state])}
              <span className="cond">{group.length}</span>
            </p>
            {group.map((p) => (
              <PersonStatusRow
                key={p.employee.id}
                dense
                name={p.employee.full_name}
                specialty={p.employee.specialty}
                state={p.state}
                orderNumber={p.current_order?.number}
                queueCount={p.queue_count}
                selected={selected === p.employee.id}
                hideBadge={p.state === 'free' || p.state === 'off_shift'}
                onClick={() => onSelect(p.employee.id)}
              />
            ))}
          </section>
        )
      })}
    </div>
  )
}

function OrderDrawer({ orderId, onClose }: { orderId: number; onClose: () => void }) {
  const { t } = useTranslation()
  const detail = useQuery({ queryKey: orderKeys.detail(orderId), queryFn: () => fetchOrder(orderId) })
  const order = detail.data
  return (
    <Drawer
      open
      onClose={onClose}
      title={order ? t('manage.order', { n: order.number }) : '…'}
      subtitle={order ? `${order.equipment.name} · ${t(`status.${order.status}`)}` : undefined}
      footer={order ? <OrderManageActions order={order} layout="row" /> : undefined}
    >
      <div className="p-5">{order ? <OrderManageBody order={order} /> : <TagSkeleton />}</div>
    </Drawer>
  )
}

function FilterSelect<V extends string | number>({
  label,
  value,
  onChange,
  options,
  all,
}: {
  label: string
  value: V | null
  onChange: (value: V | null) => void
  options: { value: V; label: string }[]
  all: string
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-stamp font-semibold text-ink-3">{label}</span>
      <select
        value={value ?? ''}
        onChange={(e) => {
          const raw = e.target.value
          if (!raw) return onChange(null)
          const match = options.find((o) => String(o.value) === raw)
          onChange(match ? match.value : null)
        }}
        className={cn(
          'h-10 max-w-[220px] rounded-control border-2 bg-surface px-2.5 text-small',
          value ? 'border-accent font-semibold text-accent' : 'border-line text-ink',
        )}
      >
        <option value="">{all}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}
