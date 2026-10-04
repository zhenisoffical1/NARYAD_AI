import { cn } from '@/shared/lib/format'

/** Переключатель разделов: утопленная полоса, выбранный — как вдавленная клавиша пульта. */
export function Tabs<V extends string>({
  value,
  onChange,
  items,
  label,
}: {
  value: V
  onChange: (value: V) => void
  items: { value: V; label: string; count?: number }[]
  label: string
}) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 rounded-control bg-plate p-1">
      {items.map((item) => {
        const active = item.value === value
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(item.value)}
            className={cn(
              'flex min-h-12 flex-1 items-center justify-center gap-2 rounded-[6px] px-3 font-semibold',
              active ? 'bg-surface text-accent shadow-raised' : 'text-ink-2 hover:text-ink',
            )}
          >
            {item.label}
            {item.count !== undefined && (
              <span className={cn('cond text-small', active ? 'text-ink-2' : 'text-ink-3')}>
                {item.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
