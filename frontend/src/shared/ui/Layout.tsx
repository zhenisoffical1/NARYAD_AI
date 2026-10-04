import type { ReactNode } from 'react'

import { cn } from '@/shared/lib/format'

import { Icon, type IconName } from './Icon'

/** Панель действий, закреплённая внизу экрана, — в зоне большого пальца. */
export function ActionBar({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'sticky bottom-0 z-20 flex flex-col gap-3 border-t border-line bg-surface/95 px-4 pt-3 backdrop-blur-sm',
        'pb-[max(12px,env(safe-area-inset-bottom))]',
        className,
      )}
    >
      {children}
    </div>
  )
}

/** Заголовок раздела на экране: подпись и, при необходимости, счётчик и действие справа. */
export function SectionTitle({
  children,
  count,
  tone = 'default',
  action,
}: {
  children: ReactNode
  count?: number
  tone?: 'default' | 'danger'
  action?: ReactNode
}) {
  return (
    <div className="flex min-h-8 items-center justify-between gap-3">
      <h2
        className={cn(
          'flex items-center gap-2 text-small font-semibold',
          tone === 'danger' ? 'text-red' : 'text-ink-2',
        )}
      >
        {children}
        {count !== undefined && (
          <span
            className={cn(
              'cond inline-flex h-5 min-w-5 items-center justify-center rounded-[3px] px-1 text-stamp',
              tone === 'danger' ? 'bg-red-strong text-white' : 'bg-plate text-ink-2',
            )}
          >
            {count}
          </span>
        )}
      </h2>
      {action}
    </div>
  )
}

/** Карточка-блок для группировки содержимого экрана. */
export function Panel({
  children,
  className,
  title,
  action,
}: {
  children: ReactNode
  className?: string
  title?: ReactNode
  action?: ReactNode
}) {
  return (
    <section className={cn('rounded-[8px] border border-line bg-surface', className)}>
      {title && (
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <h3 className="text-small font-semibold text-ink-2">{title}</h3>
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

/** Нижняя навигация приложения исполнителя: крупные вкладки под большой палец. */
export function TabBar({
  items,
}: {
  items: { key: string; label: string; icon: IconName; active: boolean; badge?: number; onClick: () => void }[]
}) {
  return (
    <nav className="sticky bottom-0 z-20 grid auto-cols-fr grid-flow-col border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={item.onClick}
          aria-current={item.active ? 'page' : undefined}
          className={cn(
            'relative flex min-h-16 flex-col items-center justify-center gap-1 text-small font-medium',
            item.active ? 'text-accent' : 'text-ink-3',
          )}
        >
          {item.active && <span aria-hidden className="absolute top-0 h-[3px] w-12 rounded-b bg-accent" />}
          <span className="relative">
            <Icon name={item.icon} size={26} />
            {item.badge ? (
              <span className="cond absolute -top-1.5 -right-3 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-strong px-1 text-stamp text-white">
                {item.badge}
              </span>
            ) : null}
          </span>
          {item.label}
        </button>
      ))}
    </nav>
  )
}

/** Строка «подпись — значение» для карточки наряда. */
export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/70 py-2.5 last:border-b-0">
      <dt className="shrink-0 text-small text-ink-3">{label}</dt>
      <dd className="min-w-0 text-right [overflow-wrap:anywhere]">{children}</dd>
    </div>
  )
}

/** Крупный переключатель-строка (перчатки): «Без материалов», «Оборудование остановлено». */
export function ToggleRow({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
  hint?: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="flex min-h-14 w-full items-center justify-between gap-4 rounded-control border-2 border-line bg-surface px-4 py-2 text-left active:bg-plate"
    >
      <span>
        <span className="block font-medium">{label}</span>
        {hint && <span className="block text-small text-ink-3">{hint}</span>}
      </span>
      <span
        aria-hidden
        className={cn(
          'relative inline-flex h-8 w-14 shrink-0 items-center rounded-full transition-colors',
          checked ? 'bg-accent' : 'bg-plate',
        )}
      >
        <span
          className={cn(
            'absolute size-6 rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-7' : 'translate-x-1',
          )}
        />
      </span>
    </button>
  )
}
