import type { ReactNode } from 'react'

import { cn } from '@/shared/lib/format'

interface CounterProps {
  label: string
  value: number | string
  /** Красным, если значение требует внимания (просрочки, простой) */
  alert?: boolean
  hint?: string
  onClick?: () => void
}

/** Ячейка табло: подпись-штамп и крупная узкая цифра. */
export function Counter({ label, value, alert = false, hint, onClick }: CounterProps) {
  const Root = onClick ? 'button' : 'div'
  return (
    <Root
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={cn(
        'flex min-w-0 flex-1 flex-col gap-1 px-4 py-3 text-left',
        onClick && 'hover:bg-surface/60',
      )}
    >
      <span className="stamp truncate text-ink-3">{label}</span>
      <span
        className={cn(
          'cond text-display font-semibold',
          alert ? 'text-red' : 'text-ink',
        )}
      >
        {value}
      </span>
      {hint && <span className="truncate text-small text-ink-2">{hint}</span>}
    </Root>
  )
}

/** Табло счётчиков смены: одна утопленная полоса с разделителями. */
export function CounterBoard({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'flex flex-wrap divide-x divide-line rounded-tag border border-line bg-plate',
        className,
      )}
    >
      {children}
    </div>
  )
}
