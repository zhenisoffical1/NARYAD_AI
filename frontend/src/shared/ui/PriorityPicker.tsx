import { useTranslation } from 'react-i18next'

import type { Priority } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'

const ORDER: Priority[] = ['emergency', 'high', 'normal', 'planned']

const SWATCH: Record<Priority, string> = {
  emergency: 'hatch-red',
  high: 'bg-red',
  normal: 'bg-ink',
  planned: 'border-2 border-dashed border-ink-3',
}

/** Приоритет — четыре крупные кнопки, одна выбрана. Аварийный выделяется штриховкой. */
export function PriorityPicker({
  value,
  onChange,
  label,
}: {
  value: Priority | null
  onChange: (value: Priority) => void
  label: string
}) {
  const { t } = useTranslation()
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1.5 text-small font-semibold text-ink-2">{label}</legend>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="radiogroup">
        {ORDER.map((priority) => {
          const active = priority === value
          return (
            <button
              key={priority}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(priority)}
              className={cn(
                'flex min-h-16 items-center gap-3 rounded-control border-2 px-3 text-left font-semibold',
                active
                  ? priority === 'emergency'
                    ? 'border-red-strong bg-red-strong text-white'
                    : 'border-accent bg-accent text-on-accent'
                  : 'border-line bg-surface text-ink active:bg-plate',
              )}
            >
              <span
                aria-hidden
                className={cn('h-9 w-2.5 shrink-0 rounded-[1px]', SWATCH[priority], active && 'ring-2 ring-white/70')}
              />
              <span className="leading-tight">{t(`priority.${priority}`)}</span>
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
