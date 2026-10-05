import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router'

import { cn } from '@/shared/lib/format'
import { useSession } from '@/shared/lib/session'
import { Icon, type IconName } from '@/shared/ui'

type NavKey = 'overview' | 'shift' | 'analytics' | 'reports' | 'rating'

const LINKS: { key: NavKey; to: string; icon: IconName; roles: string[] }[] = [
  { key: 'overview', to: '/boss', icon: 'signal', roles: ['boss', 'admin'] },
  {
    key: 'shift',
    to: '/panel',
    icon: 'list',
    roles: ['master', 'boss', 'admin'],
  },
  {
    key: 'analytics',
    to: '/panel/analytics',
    icon: 'chart',
    roles: ['master', 'boss', 'admin'],
  },
  {
    key: 'reports',
    to: '/panel/reports',
    icon: 'report',
    roles: ['master', 'boss', 'admin'],
  },
  {
    key: 'rating',
    to: '/panel/rating',
    icon: 'flag',
    roles: ['master', 'boss', 'admin'],
  },
]

/** Каркас рабочих мест на компьютере: слева меню разделов с эмблемой КМ, справа экран. */
export function DeskShell() {
  const { t } = useTranslation()
  const user = useSession((s) => s.user)
  const links = LINKS.filter((l) => user && l.roles.includes(user.role))

  return (
    <div className="flex min-h-dvh bg-bg">
      <div className="w-[76px] shrink-0 bg-bar bg-grad-rail">
        <nav
          aria-label={t('desk.nav')}
          className="sticky top-0 flex h-dvh flex-col items-center gap-1 py-3 text-on-bar"
        >
          <span className="mb-3 flex size-12 items-center justify-center overflow-hidden rounded-[10px] bg-white">
            <img
              src="/brand/km-logo.png"
              alt="АО «Костанайские Минералы»"
              className="h-7 w-10 object-cover object-top"
            />
          </span>
          {links.map((link) => (
            <NavLink
              key={link.key}
              to={link.to}
              end
              className={({ isActive }) =>
                cn(
                  'flex w-[64px] flex-col items-center gap-1 rounded-[10px] px-1 py-2 text-center text-[11.5px] leading-tight font-medium',
                  isActive ? 'bg-white/16 text-white' : 'text-white/70 hover:bg-white/8 hover:text-white',
                )
              }
            >
              <Icon name={link.icon} size={22} />
              {t(`desk.${link.key}`)}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  )
}
