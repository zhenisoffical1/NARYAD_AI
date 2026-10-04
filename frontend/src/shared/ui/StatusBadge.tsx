import { useTranslation } from 'react-i18next'

import type { OrderStatus, PersonState } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'

/**
 * Тон метки. Смысл цвета один для людей и нарядов:
 * жёлтый — в работе, синий — очередь, зелёный — готово/свободен, серый — неактивно,
 * красный — требует внимания.
 */
type Tone = 'work' | 'work-soft' | 'queue' | 'ok' | 'off' | 'danger' | 'danger-soft' | 'review' | 'issued'

const TONE: Record<Tone, { box: string; mark: string }> = {
  work: { box: 'bg-yellow-soft text-amber border-yellow', mark: 'bg-yellow' },
  'work-soft': { box: 'bg-surface text-amber border-yellow', mark: 'bg-yellow' },
  queue: { box: 'bg-queue-soft text-queue-strong border-queue-soft dark:text-queue', mark: 'bg-queue' },
  ok: { box: 'bg-green-soft text-green-strong border-green-soft dark:text-green', mark: 'bg-green' },
  off: { box: 'bg-plate text-ink-3 border-plate', mark: 'bg-off' },
  danger: { box: 'bg-red-strong text-white border-red-strong', mark: 'bg-white' },
  'danger-soft': { box: 'bg-red-soft text-red border-red-soft', mark: 'bg-red' },
  review: { box: 'bg-accent-soft text-accent border-accent-soft', mark: 'bg-accent' },
  issued: { box: 'bg-surface text-ink border-ink-3/40', mark: 'bg-ink' },
}

const ORDER_STATUS_TONE: Record<OrderStatus, Tone> = {
  ISSUED: 'issued',
  QUEUED: 'queue',
  ACCEPTED: 'work-soft',
  REJECTED: 'danger-soft',
  IN_PROGRESS: 'work',
  PAUSED: 'work-soft',
  DONE: 'review',
  AI_REVIEW: 'review',
  REWORK: 'danger',
  CLOSED: 'ok',
  CANCELLED: 'off',
}

const PERSON_TONE: Record<PersonState, Tone> = {
  free: 'ok',
  busy: 'work',
  queue: 'queue',
  off_shift: 'off',
}

function Stamp({ tone, children, size = 'md' }: { tone: Tone; children: string; size?: 'sm' | 'md' }) {
  const style = TONE[tone]
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 rounded-[6px] border stamp whitespace-nowrap',
        size === 'md' ? 'h-7 px-2.5' : 'h-6 px-2',
        style.box,
      )}
    >
      <span aria-hidden className={cn('size-2 rounded-full', style.mark)} />
      {children}
    </span>
  )
}

export function StatusBadge({ status, size }: { status: OrderStatus; size?: 'sm' | 'md' }) {
  const { t } = useTranslation()
  return (
    <Stamp tone={ORDER_STATUS_TONE[status]} size={size}>
      {t(`status.${status}`)}
    </Stamp>
  )
}

export function PersonBadge({
  state,
  orderNumber,
  queueCount,
  size,
}: {
  state: PersonState
  orderNumber?: number | null
  queueCount?: number
  size?: 'sm' | 'md'
}) {
  const { t } = useTranslation()
  const text =
    state === 'busy'
      ? orderNumber
        ? t('person.busy', { number: orderNumber })
        : t('person.busyPlain')
      : state === 'queue'
        ? t('person.queue', { count: queueCount ?? 0 })
        : t(`person.${state}`)
  return (
    <Stamp tone={PERSON_TONE[state]} size={size}>
      {text}
    </Stamp>
  )
}
