import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/shared/lib/format'
import { useLiveStatus } from '@/shared/lib/useLiveEvents'

import { Icon } from './Icon'

const LIVE_DOT = {
  online: 'bg-green',
  connecting: 'bg-yellow',
  offline: 'bg-red',
} as const

/** Стальная плашка сверху экрана: назад, заголовок, связь, действия справа. */
export function TopBar({
  title,
  subtitle,
  onBack,
  right,
}: {
  title: string
  subtitle?: string
  onBack?: () => void
  right?: ReactNode
}) {
  const { t } = useTranslation()
  return (
    <header className="sticky top-0 z-30 flex min-h-14 items-center gap-1 border-b-4 border-bar-line bg-bar pt-[env(safe-area-inset-top)] pr-2 pl-1 text-on-bar">
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          aria-label={t('common.back')}
          className="inline-flex size-12 shrink-0 items-center justify-center rounded-control active:bg-white/10"
        >
          <Icon name="chevronLeft" size={28} />
        </button>
      ) : (
        <span className="w-3" />
      )}
      <div className="min-w-0 flex-1 py-2">
        <h1 className="truncate text-h2 font-semibold">{title}</h1>
        {subtitle && <p className="truncate text-small opacity-80">{subtitle}</p>}
      </div>
      <LiveDot />
      {right}
    </header>
  )
}

export function LiveDot({ withLabel = false }: { withLabel?: boolean }) {
  const { t } = useTranslation()
  const status = useLiveStatus((s) => s.status)
  return (
    <span
      role="status"
      title={t(`live.${status}`)}
      className="inline-flex min-h-12 items-center gap-2 px-2 text-small"
    >
      <span className={cn('size-2.5 rounded-full', LIVE_DOT[status])} aria-hidden />
      <span className={withLabel ? '' : 'sr-only'}>{t(`live.${status}`)}</span>
    </span>
  )
}
