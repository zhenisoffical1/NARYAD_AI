import { useTranslation } from 'react-i18next'

import type { OrderListItem, OrderStatus, Priority } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'

import { Countdown } from './Countdown'
import { Icon } from './Icon'
import { StatusBadge } from './StatusBadge'

const STRIPE: Record<Priority, string> = {
  emergency: 'hatch-red',
  high: 'bg-red bg-[linear-gradient(180deg,#ff7a45,#e5304a)]',
  normal: 'bg-ink-3/45',
  planned: 'border-r-2 border-dashed border-ink-3/60',
}

const DEADLINE_STOPPED: OrderStatus[] = ['DONE', 'AI_REVIEW', 'CLOSED', 'CANCELLED']

export type OrderTagData = Pick<
  OrderListItem,
  | 'number'
  | 'priority'
  | 'status'
  | 'description'
  | 'equipment'
  | 'section'
  | 'assignee'
  | 'deadline_at'
  | 'is_overdue'
  | 'equipment_stopped'
  | 'ai_score'
>

interface OrderTagProps {
  order: OrderTagData
  variant?: 'full' | 'compact'
  /** Подсветить как только что изменённую (живое обновление) */
  highlight?: boolean
  selected?: boolean
  showAssignee?: boolean
  /** Статус уже понятен из колонки канбана — не повторять его на бирке */
  hideStatus?: boolean
  onClick?: () => void
}

/** Бирка-допуск наряда — главный узнаваемый элемент интерфейса (docs/DESIGN.md). */
export function OrderTag({
  order,
  variant = 'full',
  highlight = false,
  selected = false,
  showAssignee = true,
  hideStatus = false,
  onClick,
}: OrderTagProps) {
  const { t } = useTranslation()
  const compact = variant === 'compact'
  const stopped = DEADLINE_STOPPED.includes(order.status)
  const Root = onClick ? 'button' : 'article'

  return (
    <Root
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      aria-label={onClick ? `№${order.number}, ${t(`status.${order.status}`)}` : undefined}
      className={cn(
        'group relative flex w-full overflow-hidden rounded-tag border bg-surface text-left text-ink shadow-card',
        selected ? 'border-accent bg-accent-soft/60 outline-2 outline-accent' : 'border-line',
        onClick && 'cursor-pointer transition-shadow hover:shadow-raised active:shadow-none',
        highlight && 'animate-flash',
      )}
    >
      <span aria-hidden className={cn('shrink-0', compact ? 'w-1.5' : 'w-2', STRIPE[order.priority])} />
      <span className="sr-only">{t(`priority.${order.priority}`)}</span>

      <span className={cn('flex min-w-0 flex-1 flex-col', compact ? 'gap-1 p-2.5' : 'gap-1.5 p-3.5 pl-4')}>
        <span className="flex flex-wrap items-start justify-between gap-2">
          <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <span className={cn('cond font-bold leading-none', compact ? 'text-[19px]' : 'text-[24px]')}>
              №{order.number}
            </span>
            <InvPlate inv={order.equipment.inv_number} compact={compact} />
            <PriorityStamp priority={order.priority} />
          </span>
          {!hideStatus && <StatusBadge status={order.status} size={compact ? 'sm' : 'md'} />}
        </span>

        <span className={cn('font-semibold', compact ? 'text-small' : 'text-body')}>
          {order.equipment.name}
        </span>
        <span
          className={cn(
            'line-clamp-2 text-ink-2 [overflow-wrap:anywhere]',
            compact ? 'text-small' : 'text-[16px] leading-[22px]',
          )}
        >
          {order.description}
        </span>

        <span
          className={cn(
            'mt-1 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t pt-2 text-small',
            order.is_overdue && !stopped ? 'border-dashed border-red' : 'border-line',
          )}
        >
          <span className="flex min-w-0 items-center gap-2 text-ink-2">
            {order.equipment_stopped && !stopped && (
              <span className="stamp inline-flex items-center gap-1 rounded-[5px] bg-red-soft px-1.5 py-0.5 text-red">
                <Icon name="alert" size={14} />
                {t('ui.downtime')}
              </span>
            )}
            {showAssignee && order.assignee && <Initials name={order.assignee.short_name} />}
            <span className="truncate">
              {showAssignee && order.assignee
                ? order.assignee.short_name
                : compact
                  ? null
                  : order.section.name}
            </span>
          </span>
          {order.ai_score !== null && stopped ? (
            <span className="inline-flex items-center gap-1 text-ink-2">
              <Icon name="spark" size={16} className="text-accent" />
              <span className="cond font-semibold text-ink">{order.ai_score}</span>
              <span>{t('verdict.score')}</span>
            </span>
          ) : (
            <Countdown deadline={order.deadline_at} stopped={stopped} compact={compact} />
          )}
        </span>
      </span>
    </Root>
  )
}

const AVATAR = ['#2f7d6d', '#7a5ba6', '#b0603a', '#466c9e', '#8c7a2e', '#5a6b7f', '#a2484e']

/** Кружок с инициалами — узнать человека в списке быстрее, чем по фамилии. */
export function Initials({ name, size = 22 }: { name: string; size?: number }) {
  const parts = name.replace(/\./g, ' ').split(/\s+/).filter(Boolean)
  const letters = ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase()
  let hash = 0
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, fontSize: size * 0.42, background: AVATAR[hash % AVATAR.length] }}
    >
      {letters}
    </span>
  )
}

export function InvPlate({ inv, compact = false }: { inv: string; compact?: boolean }) {
  const { t } = useTranslation()
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-[5px] border border-ink-3/35 bg-plate px-1.5 text-ink-2',
        compact ? 'h-6' : 'h-7',
      )}
      title={t('ui.inv')}
    >
      <span className={cn('cond font-semibold', compact ? 'text-[14px]' : 'text-[15px]')}>{inv}</span>
    </span>
  )
}

function PriorityStamp({ priority }: { priority: Priority }) {
  const { t } = useTranslation()
  if (priority === 'emergency') {
    return (
      <span className="stamp inline-flex h-6 items-center rounded-[6px] bg-red-strong bg-grad-alarm px-2 text-white">
        {t('priority.emergency')}
      </span>
    )
  }
  if (priority === 'high') {
    return (
      <span className="stamp inline-flex h-6 items-center rounded-[6px] bg-red-soft px-2 text-red">
        {t('priority.high')}
      </span>
    )
  }
  return null
}
