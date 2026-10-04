import type { ReactNode } from 'react'

import { cn } from '@/shared/lib/format'

type Tone = 'blue' | 'green' | 'red' | 'amber' | 'neutral'

/** Цвет плашки несёт смысл: синий — объём, зелёный — сделано, красный — просрочка, оранжевый — простой. */
const TONE: Record<Tone, string> = {
  blue: 'bg-accent bg-[linear-gradient(135deg,#0b3f8c,#2a74d8)] text-white',
  green: 'bg-green-strong bg-[linear-gradient(135deg,#17723a,#2aa35f)] text-white',
  red: 'bg-red-strong bg-[linear-gradient(135deg,#b5162e,#f0503a)] text-white',
  amber: 'bg-[#b04a00] bg-[linear-gradient(135deg,#b04a00,#e58a00)] text-white',
  neutral: 'bg-surface text-ink border border-line',
}

interface CounterProps {
  label: string
  value: number | string
  /** Значение требует внимания (просрочки, простой) — плашка красная */
  alert?: boolean
  /** Цвет плашки; без него — нейтральная, а при alert — красная */
  tone?: Tone
  hint?: string
  onClick?: () => void
}

/** Плашка табло: крупная цифра и подпись. */
export function Counter({ label, value, alert = false, tone, hint, onClick }: CounterProps) {
  const Root = onClick ? 'button' : 'div'
  const resolved: Tone = alert ? (tone ?? 'red') : tone && tone !== 'red' && tone !== 'amber' ? tone : 'neutral'
  const colored = resolved !== 'neutral'
  return (
    <Root
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={cn(
        'flex min-w-0 flex-1 flex-col gap-0.5 rounded-[10px] px-4 py-3 text-left shadow-card',
        TONE[resolved],
        onClick && 'hover:brightness-105',
      )}
    >
      <span className={cn('stamp truncate', colored ? 'text-white/85' : 'text-ink-3')}>{label}</span>
      <span className={cn('cond text-display font-bold', !colored && alert && 'text-red')}>{value}</span>
      {hint && <span className={cn('truncate text-small', colored ? 'text-white/85' : 'text-ink-2')}>{hint}</span>}
    </Root>
  )
}

/**
 * Табло счётчиков: отдельные плашки с промежутком.
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
        'gap-2',
        columns ? 'grid' : !className?.includes('grid') && 'flex flex-wrap',
        className,
      )}
      style={columns ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined}
    >
      {children}
    </div>
  )
}
