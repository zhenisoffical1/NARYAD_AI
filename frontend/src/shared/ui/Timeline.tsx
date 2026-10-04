import { useTranslation } from 'react-i18next'

import type { OrderEvent, OrderStatus } from '@/shared/api/types'
import { cn, ddmm, hhmm, isToday } from '@/shared/lib/format'

const DOT: Partial<Record<OrderStatus, string>> = {
  ISSUED: 'bg-ink',
  QUEUED: 'bg-queue',
  ACCEPTED: 'bg-yellow',
  IN_PROGRESS: 'bg-yellow',
  PAUSED: 'bg-yellow',
  REJECTED: 'bg-red',
  REWORK: 'bg-red',
  DONE: 'bg-accent',
  AI_REVIEW: 'bg-accent',
  CLOSED: 'bg-green',
  CANCELLED: 'bg-off',
}

/** Хронология наряда: время, что произошло, кто, причина или комментарий. */
export function Timeline({ events }: { events: OrderEvent[] }) {
  const { t } = useTranslation()
  return (
    <ol className="relative flex flex-col">
      {events.map((event, i) => {
        const last = i === events.length - 1
        const title = t(`event.${event.action}`, { defaultValue: event.action })
        const note = event.reason ?? event.comment
        return (
          <li key={event.id} className="relative flex gap-3 pb-3">
            <span className="cond w-12 shrink-0 pt-0.5 text-right text-small text-ink-2 tabular">
              {hhmm(event.created_at)}
              {!isToday(event.created_at) && (
                <span className="block text-stamp text-ink-3">{ddmm(event.created_at)}</span>
              )}
            </span>
            <span className="relative flex w-3 shrink-0 justify-center">
              {!last && <span aria-hidden className="absolute top-3 bottom-[-12px] w-0.5 bg-line" />}
              <span
                aria-hidden
                className={cn(
                  'relative mt-1.5 size-3 rounded-full border-2 border-surface',
                  (event.to_status && DOT[event.to_status]) || 'bg-ink-3',
                )}
              />
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="font-medium">{title}</span>
              {event.actor && <span className="text-small text-ink-2">{event.actor.short_name}</span>}
              {!event.actor && event.to_status && (
                <span className="text-small text-ink-3">{t('event.system')}</span>
              )}
              {note && (
                <span className="mt-0.5 text-small text-ink [overflow-wrap:anywhere]">«{note}»</span>
              )}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
