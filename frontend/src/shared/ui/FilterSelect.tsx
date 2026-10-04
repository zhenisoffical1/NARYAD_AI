import { cn } from '@/shared/lib/format'

/** Компактный фильтр для десктопных экранов: нативный список, выбранное — акцентом. */
export function FilterSelect<V extends string | number>({
  label,
  value,
  onChange,
  options,
  all,
}: {
  label: string
  value: V | null
  onChange: (value: V | null) => void
  options: { value: V; label: string }[]
  all: string
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-stamp font-semibold text-ink-3">{label}</span>
      <select
        value={value ?? ''}
        onChange={(e) => {
          const raw = e.target.value
          if (!raw) return onChange(null)
          const match = options.find((o) => String(o.value) === raw)
          onChange(match ? match.value : null)
        }}
        className={cn(
          'h-10 max-w-[220px] rounded-control border-2 bg-surface px-2.5 text-small',
          value ? 'border-accent font-semibold text-accent' : 'border-line text-ink',
        )}
      >
        <option value="">{all}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}
