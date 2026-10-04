import { useTranslation } from 'react-i18next'

import type { OrderListItem, OrderStatus, Priority } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'

import { Countdown } from './Countdown'
import { Icon } from './Icon'
import { StatusBadge } from './StatusBadge'

const STRIPE: Record<Priority, string> = {
  emergency: 'hatch-red',
  high: 'bg-red',
  normal: 'bg-ink',
  planned: 'bg-surface border-r-2 border-dashed border-ink-3',
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
        'group relative flex w-full rounded-tag border bg-surface text-left text-ink',
        selected ? 'border-accent outline-2 outline-accent' : 'border-line',
        onClick && 'cursor-pointer hover:shadow-raised active:shadow-none',
        highlight && 'animate-flash',
      )}
    >
      {/* Полоса приоритета с «люверсом» бирки */}
      <span
        aria-hidden
        className={cn(
          'relative shrink-0 rounded-l-tag',
          compact ? 'w-2.5' : 'w-3.5',
          STRIPE[order.priority],
        )}
      >
        <span
          className={cn(
            'absolute left-1/2 -translate-x-1/2 rounded-full border border-line bg-bg',
            compact ? 'top-2 size-1.5' : 'top-2.5 size-2',
          )}
        />
      </span>
      <span className="sr-only">{t(`priority.${order.priority}`)}</span>

      <span className={cn('flex min-w-0 flex-1 flex-col', compact ? 'gap-1 p-2.5' : 'gap-2 p-3')}>
        <span className="flex flex-wrap items-start justify-between gap-2">
          <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <span
              className={cn('cond font-bold leading-none', compact ? 'text-[22px]' : 'text-tagnum')}
            >
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
            compact && 'text-small',
          )}
        >
          {order.description}
        </span>

        <span
          className={cn(
            'mt-0.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t pt-2 text-small',
            order.is_overdue && !stopped ? 'border-dashed border-red' : 'border-line',
          )}
        >
          <span className="flex min-w-0 items-center gap-1.5 text-ink-2">
            {order.equipment_stopped && !stopped && (
              <span className="stamp inline-flex items-center gap-1 text-red">
                <Icon name="alert" size={14} />
                {t('ui.downtime')}
              </span>
            )}
            <span className="truncate">
              {compact ? null : order.section.name}
              {showAssignee && order.assignee && (
                <>
                  {compact ? '' : ' · '}
                  {order.assignee.short_name}
                </>
              )}
            </span>
          </span>
          {order.ai_score !== null && stopped ? (
            <span className="inline-flex items-center gap-1 text-ink-2">
              <Icon name="spark" size={16} />
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

export function InvPlate({ inv, compact = false }: { inv: string; compact?: boolean }) {
  const { t } = useTranslation()
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-[2px] border-2 border-ink-2 bg-surface px-1.5',
        compact ? 'h-6' : 'h-7',
      )}
    >
      <span className="stamp text-ink-3">{t('ui.inv')}</span>
      <span className={cn('cond font-semibold', compact ? 'text-small' : 'text-body')}>{inv}</span>
    </span>
  )
}

function PriorityStamp({ priority }: { priority: Priority }) {
  const { t } = useTranslation()
  if (priority === 'emergency') {
    return (
      <span className="stamp inline-flex h-6 items-center rounded-tag bg-red-strong px-1.5 text-white">
        {t('priority.emergency')}
      </span>
    )
  }
  if (priority === 'high') {
    return (
      <span className="stamp inline-flex h-6 items-center rounded-tag border-2 border-red px-1 text-red">
        {t('priority.high')}
      </span>
    )
  }
  return null
}
