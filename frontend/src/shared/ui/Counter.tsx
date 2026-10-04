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
        'flex min-w-0 flex-1 flex-col gap-1 bg-plate px-4 py-3 text-left',
        onClick && 'hover:bg-line/40',
      )}
    >
      <span className="stamp truncate text-ink-3">{label}</span>
      <span className={cn('cond text-display font-semibold', alert ? 'text-red' : 'text-ink')}>
        {value}
      </span>
      {hint && <span className="truncate text-small text-ink-2">{hint}</span>}
    </Root>
  )
}

/**
 * Табло счётчиков: одна утопленная полоса, ячейки разделены тонкими линиями.
 * columns — сетка (на телефоне 2×2), иначе — в строку.
 */
export function CounterBoard({
  children,
  columns,
  className,
}: {
  children: ReactNode
  columns?: number
  className?: string
}) {
  return (
    <div
      className={cn(
        'gap-px overflow-hidden rounded-[8px] border border-line bg-line',
        columns ? 'grid' : !className?.includes('grid') && 'flex flex-wrap',
        className,
      )}
      style={columns ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined}
    >
      {children}
    </div>
  )
}
