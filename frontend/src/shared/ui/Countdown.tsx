import { useTranslation } from 'react-i18next'

import { clock, cn, hhmm, minutesUntil } from '@/shared/lib/format'
import { useNow } from '@/shared/lib/useNow'

import { Icon } from './Icon'

/**
 * Срок с обратным отсчётом: «до 11:40 · осталось 0:42» или красное «просрочен на 0:45».
 * compact — для узких карточек канбана: «0:42» или «−0:45».
 */
export function Countdown({
  deadline,
  stopped = false,
  compact = false,
  className,
}: {
  deadline: string
  /** Наряд уже исполнен — срок больше не тикает */
  stopped?: boolean
  compact?: boolean
  className?: string
}) {
  const { t } = useTranslation()
  const now = useNow(stopped ? null : 30_000)
  const left = minutesUntil(deadline, now)
  const overdue = !stopped && left < 0
  const label = overdue
    ? t('deadline.overdue', { time: clock(-left) })
    : t('deadline.left', { time: clock(left) })

  if (compact) {
    return (
      <span
        title={`${t('deadline.until', { time: hhmm(deadline) })} · ${label}`}
        className={cn(
          'cond inline-flex items-center gap-1 whitespace-nowrap',
          overdue ? 'font-semibold text-red' : 'text-ink-2',
          className,
        )}
      >
        <Icon name={overdue ? 'alert' : 'clock'} size={16} />
        {stopped ? hhmm(deadline) : `${overdue ? '−' : ''}${clock(Math.abs(left))}`}
        <span className="sr-only">{label}</span>
      </span>
    )
  }

  return (
    <span
      className={cn(
        'inline-flex flex-wrap items-center gap-x-1.5 tabular',
        overdue ? 'font-semibold text-red' : 'text-ink-2',
        className,
      )}
    >
      <Icon name={overdue ? 'alert' : 'clock'} size={18} />
      <span className="whitespace-nowrap">{t('deadline.until', { time: hhmm(deadline) })}</span>
      {!stopped && (
        <span
          className={cn('cond whitespace-nowrap', !overdue && left < 30 && 'font-semibold text-ink')}
        >
          · {label}
        </span>
      )}
    </span>
  )
}
