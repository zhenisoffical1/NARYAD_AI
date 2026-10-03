import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from './Icon'

interface StepperProps {
  value: number
  onChange: (value: number) => void
  unit: string
  step?: number
  min?: number
  max?: number
  label: string
}

const show = (v: number) => String(v).replace('.', ',')

/** Количество: «−» и «+» по 56 px, значение можно и ввести. Для штук шаг 1, для литров 0,5. */
export function Stepper({ value, onChange, unit, step = 1, min = 0, max = 9999, label }: StepperProps) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<string | null>(null)
  const clamp = (v: number) => Math.min(max, Math.max(min, Math.round(v * 1000) / 1000))
  const button =
    'inline-flex size-14 shrink-0 items-center justify-center rounded-control border-2 border-ink/80 bg-surface active:bg-plate disabled:opacity-40'

  const commit = () => {
    if (draft === null) return
    const parsed = Number(draft.replace(',', '.'))
    if (draft.trim() !== '' && !Number.isNaN(parsed)) onChange(clamp(parsed))
    setDraft(null)
  }

  return (
    <div className="flex items-center gap-2" role="group" aria-label={label}>
      <button
        type="button"
        className={button}
        onClick={() => onChange(clamp(value - step))}
        disabled={value <= min}
        aria-label={`${t('ui.decrease')}: ${label}`}
      >
        <Icon name="minus" size={26} />
      </button>
      <label className="flex h-14 min-w-0 flex-1 items-baseline justify-center gap-1.5 rounded-control border-2 border-line bg-surface px-2 pt-2.5 focus-within:border-accent">
        <input
          inputMode="decimal"
          value={draft ?? show(value)}
          onFocus={(e) => {
            setDraft(show(value))
            e.target.select()
          }}
          onChange={(e) => setDraft(e.target.value.replace(/[^\d.,]/g, ''))}
          onBlur={commit}
          onKeyDown={(e) => e.key === 'Enter' && commit()}
          aria-label={label}
          className="cond w-full min-w-0 bg-transparent text-right text-h1 font-semibold outline-none"
        />
        <span className="text-small text-ink-2">{unit}</span>
      </label>
      <button
        type="button"
        className={button}
        onClick={() => onChange(clamp(value + step))}
        disabled={value >= max}
        aria-label={`${t('ui.increase')}: ${label}`}
      >
        <Icon name="plus" size={26} />
      </button>
    </div>
  )
}
