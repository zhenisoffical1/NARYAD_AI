import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/shared/lib/format'

import { Icon } from './Icon'

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'back'] as const

/** Цифровая клавиатура для ПИН: клавиши 72 px — набирается в перчатках. */
export function PinPad({
  value,
  onChange,
  length = 4,
  disabled = false,
  error = false,
}: {
  value: string
  onChange: (value: string) => void
  length?: number
  disabled?: boolean
  error?: boolean
}) {
  const { t } = useTranslation()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Цифры, набранные в поле ввода (например, в логине «master1»), — не ПИН
      const target = e.target as HTMLElement | null
      if (disabled || target?.closest('input, textarea, [contenteditable]')) return
      if (/^\d$/.test(e.key) && value.length < length) onChange(value + e.key)
      if (e.key === 'Backspace') onChange(value.slice(0, -1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [value, onChange, length, disabled])

  return (
    <div className="flex flex-col items-center gap-5">
      <div className="flex gap-4" aria-label={`${value.length} / ${length}`} role="status">
        {Array.from({ length }, (_, i) => (
          <span
            key={i}
            className={cn(
              'size-5 rounded-full border-2',
              error ? 'border-red' : 'border-ink',
              i < value.length && (error ? 'bg-red' : 'bg-ink'),
            )}
          />
        ))}
      </div>
      <div className="grid w-full max-w-xs grid-cols-3 gap-3">
        {KEYS.map((key, i) =>
          key === '' ? (
            <span key={i} />
          ) : (
            <button
              key={key}
              type="button"
              disabled={disabled || (key !== 'back' && value.length >= length)}
              onClick={() => {
                navigator.vibrate?.(8)
                onChange(key === 'back' ? value.slice(0, -1) : value + key)
              }}
              aria-label={key === 'back' ? t('ui.pinErase') : key}
              className={cn(
                'flex h-[72px] items-center justify-center rounded-control text-[30px] font-medium cond',
                key === 'back'
                  ? 'text-ink-2 active:bg-plate'
                  : 'border-2 border-line bg-surface active:bg-plate',
                'disabled:opacity-40',
              )}
            >
              {key === 'back' ? <Icon name="chevronLeft" size={30} /> : key}
            </button>
          ),
        )}
      </div>
    </div>
  )
}
