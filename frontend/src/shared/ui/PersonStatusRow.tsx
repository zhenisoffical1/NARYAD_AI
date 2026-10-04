import { useTranslation } from 'react-i18next'

import type { PersonState } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'

import { Icon } from './Icon'
import { PersonBadge } from './StatusBadge'

const STATE_BAR: Record<PersonState, string> = {
  free: 'bg-green',
  busy: 'bg-yellow',
  queue: 'bg-queue',
  off_shift: 'bg-off',
}

interface PersonStatusRowProps {
  name: string
  specialty?: string | null
  state: PersonState
  orderNumber?: number | null
  queueCount?: number
  /** Подсказка ИИ: строка «почему именно он» */
  recommendation?: string
  selected?: boolean
  dense?: boolean
  /** Состояние уже понятно из группы (панель мастера) — метку не показывать */
  hideBadge?: boolean
  onClick?: () => void
}

export function PersonStatusRow({
  name,
  specialty,
  state,
  orderNumber,
  queueCount,
  recommendation,
  selected = false,
  dense = false,
  hideBadge = false,
  onClick,
}: PersonStatusRowProps) {
  const { t } = useTranslation()
  const Root = onClick ? 'button' : 'div'
  return (
    <Root
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      aria-pressed={onClick ? selected : undefined}
      className={cn(
        'flex w-full items-stretch gap-3 text-left',
        dense ? 'min-h-12 py-1.5' : 'min-h-14 py-2',
        onClick && 'rounded-control px-2 active:bg-plate',
        selected && 'bg-queue-soft outline-2 outline-accent',
        state === 'off_shift' && 'text-ink-3',
      )}
    >
      <span aria-hidden className={cn('w-1.5 shrink-0 rounded-[1px]', STATE_BAR[state])} />
      <span className="flex min-w-0 flex-1 flex-col justify-center gap-0.5">
        {recommendation && (
          <span className="stamp inline-flex items-center gap-1 text-accent">
            <Icon name="spark" size={14} />
            {t('ui.aiRecommended')}
          </span>
        )}
        <span className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <span className={cn('font-semibold', dense ? 'text-small' : 'text-body')}>{name}</span>
          {!hideBadge && (
            <PersonBadge
              state={state}
              orderNumber={orderNumber}
              queueCount={queueCount}
              size={dense ? 'sm' : 'md'}
            />
          )}
        </span>
        {(specialty || recommendation) && (
          <span className="text-small text-ink-2">
            {[specialty, recommendation].filter(Boolean).join(' · ')}
          </span>
        )}
      </span>
      {selected && <Icon name="check" className="self-center text-accent" />}
    </Root>
  )
}
