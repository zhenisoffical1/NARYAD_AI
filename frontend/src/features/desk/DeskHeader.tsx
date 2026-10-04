import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router'

import { NotificationsBell } from '@/features/orders/NotificationsBell'
import { setLanguage } from '@/i18n'
import { cn } from '@/shared/lib/format'
import { useSession } from '@/shared/lib/session'
import { Icon, LiveDot } from '@/shared/ui'

type NavKey = 'overview' | 'shift' | 'analytics' | 'reports' | 'rating'

const LINKS: { key: NavKey; to: string; roles: string[] }[] = [
  { key: 'overview', to: '/boss', roles: ['boss', 'admin'] },
  { key: 'shift', to: '/panel', roles: ['master', 'boss', 'admin'] },
  { key: 'analytics', to: '/panel/analytics', roles: ['master', 'boss', 'admin'] },
  { key: 'reports', to: '/panel/reports', roles: ['master', 'boss', 'admin'] },
  { key: 'rating', to: '/panel/rating', roles: ['master', 'boss', 'admin'] },
]

/**
 * Шапка рабочих мест на компьютере (мастер, руководитель): эмблема КМ, заголовок экрана,
 * разделы, связь, уведомления, язык, выход. Одна на все десктопные экраны.
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
  const links = LINKS.filter((l) => user && l.roles.includes(user.role))

  return (
    <header className="shrink-0 border-b-4 border-bar-line bg-bar text-on-bar">
      <div className="flex min-h-16 items-center gap-4 px-5">
        <img src="/brand/km-logo-white.png" alt="АО «Костанайские Минералы»" className="h-9 w-auto" />
        <span aria-hidden className="h-8 w-px bg-white/25" />
        <div className="min-w-0">
          <h1 className="text-h2 leading-tight font-semibold">{title}</h1>
          {subtitle && <p className="truncate text-small opacity-80">{subtitle}</p>}
        </div>

        <nav aria-label={t('desk.nav')} className="ml-3 hidden self-stretch xl:flex">
          {links.map((link) => (
            <NavLink
              key={link.key}
              to={link.to}
              end
              className={({ isActive }) =>
                cn(
                  'relative flex items-center px-3 text-body font-medium whitespace-nowrap opacity-80 hover:opacity-100',
                  isActive && 'opacity-100 after:absolute after:inset-x-3 after:-bottom-1 after:h-1 after:bg-white',
                )
              }
            >
              {t(`desk.${link.key}`)}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-1">
          <LiveDot withLabel />
          {actions}
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
      </div>

      {/* На узком экране разделы — вторая строка, чтобы не прятать навигацию в меню */}
      <nav aria-label={t('desk.nav')} className="flex gap-1 overflow-x-auto px-3 pb-1 xl:hidden">
        {links.map((link) => (
          <NavLink
            key={link.key}
            to={link.to}
            end
            className={({ isActive }) =>
              cn(
                'shrink-0 rounded-t-[4px] px-3 py-2 text-small font-medium',
                isActive ? 'bg-white/15' : 'opacity-80',
              )
            }
          >
            {t(`desk.${link.key}`)}
          </NavLink>
        ))}
      </nav>
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
    <div role="radiogroup" aria-label={label} className="flex rounded-control bg-plate p-1">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            'min-h-10 rounded-[4px] px-3.5 text-small font-semibold',
            o.value === value ? 'bg-surface text-ink shadow-raised' : 'text-ink-2 hover:text-ink',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
