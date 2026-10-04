import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { NotificationsBell } from '@/features/orders/NotificationsBell'
import { setLanguage } from '@/i18n'
import { cn } from '@/shared/lib/format'
import { useSession } from '@/shared/lib/session'
import { Icon, Initials, LiveDot } from '@/shared/ui'

/**
 * Шапка рабочих мест на компьютере (мастер, руководитель): градиент КМ, заголовок экрана,
 * связь, уведомления, язык, выход. Разделы — в левом меню (DeskShell).
 */
export function DeskHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  const { t, i18n } = useTranslation()
  const user = useSession((s) => s.user)
  const signOut = useSession((s) => s.signOut)

  return (
    <header className="shrink-0 bg-bar bg-grad-bar text-on-bar">
      <div className="flex min-h-[72px] items-center gap-4 px-6">
        <div className="min-w-0">
          <h1 className="text-[22px] leading-tight font-bold">{title}</h1>
          {subtitle && <p className="truncate text-small text-white/80">{subtitle}</p>}
        </div>

        <div className="ml-auto flex items-center gap-1">
          <LiveDot withLabel />
          {actions}
          <NotificationsBell />
          <span aria-hidden className="mx-2 h-8 w-px bg-white/25" />
          {user && <Initials name={user.short_name} size={34} />}
          <div className="ml-1 hidden text-left lg:block">
            <p className="text-small leading-tight font-semibold">{user?.short_name}</p>
            <p className="text-stamp font-normal text-white/75">{user ? t(`roles.${user.role}`) : ''}</p>
          </div>
          <button
            type="button"
            onClick={() => setLanguage(i18n.language === 'kk' ? 'ru' : 'kk')}
            className="ml-3 min-h-10 rounded-control px-2.5 text-small font-semibold hover:bg-white/12"
          >
            {t('common.switchLanguage')}
          </button>
          <button
            type="button"
            onClick={signOut}
            aria-label={t('common.logout')}
            title={t('common.logout')}
            className="inline-flex size-10 items-center justify-center rounded-control hover:bg-white/12"
          >
            <Icon name="logout" size={22} />
          </button>
        </div>
      </div>
    </header>
  )
}

/** Выбор периода — кнопки-пресеты в одну строку над содержимым (правило dataviz). */
export function PeriodPicker<V extends number | string>({
  value,
  onChange,
  options,
  label,
}: {
  value: V
  onChange: (value: V) => void
  options: { value: V; label: string }[]
  label: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex rounded-control border border-line bg-surface p-1 shadow-card">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            'min-h-10 rounded-[6px] px-3.5 text-small font-semibold',
            o.value === value ? 'bg-accent bg-grad-primary text-on-accent' : 'text-ink-2 hover:text-ink',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
