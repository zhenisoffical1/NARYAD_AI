import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/shared/lib/format'

import { BottomSheet } from './BottomSheet'
import { FieldShell } from './Field'
import { Icon } from './Icon'

export interface SelectOption<V extends string | number> {
  value: V
  label: string
  hint?: string
}

interface SelectProps<V extends string | number> {
  label: string
  options: SelectOption<V>[]
  value: V | null
  onChange: (value: V) => void
  placeholder?: string
  error?: string | null
  /** Поиск появляется сам, если пунктов больше 8 */
  searchable?: boolean
}

/** Поле выбора: открывает лист с крупными пунктами (56 px) и поиском. */
export function Select<V extends string | number>({
  label,
  options,
  value,
  onChange,
  placeholder,
  error,
  searchable,
}: SelectProps<V>) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const selected = options.find((o) => o.value === value)
  const withSearch = searchable ?? options.length > 8

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return options
    return options.filter(
      (o) => o.label.toLowerCase().includes(q) || o.hint?.toLowerCase().includes(q),
    )
  }, [options, query])

  const close = () => {
    setOpen(false)
    setQuery('')
  }

  return (
    <FieldShell label={label} error={error}>
      {(id, describedBy) => (
        <>
          <button
            id={id}
            type="button"
            aria-haspopup="dialog"
            aria-describedby={describedBy}
            aria-invalid={Boolean(error) || undefined}
            onClick={() => setOpen(true)}
            className={cn(
              'flex min-h-14 w-full items-center justify-between gap-3 rounded-control border-2 bg-surface px-4 text-left',
              error ? 'border-red' : 'border-line',
            )}
          >
            <span className="min-w-0">
              <span className={cn('block truncate', !selected && 'text-ink-3')}>
                {selected?.label ?? placeholder ?? t('ui.choose')}
              </span>
              {selected?.hint && (
                <span className="block truncate text-small text-ink-2">{selected.hint}</span>
              )}
            </span>
            <Icon name="chevronDown" className="shrink-0 text-ink-2" />
          </button>
          <BottomSheet open={open} title={label} onClose={close}>
            {withSearch && (
              <div className="sticky top-0 -mx-4 -mt-3 mb-2 bg-surface px-4 pt-3 pb-2">
                <label className="flex min-h-14 items-center gap-2 rounded-control border-2 border-line px-3 focus-within:border-accent">
                  <Icon name="search" className="text-ink-3" />
                  <input
                    autoFocus
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={t('ui.search')}
                    aria-label={t('ui.search')}
                    className="min-w-0 flex-1 bg-transparent text-body outline-none placeholder:text-ink-3"
                  />
                </label>
              </div>
            )}
            <ul className="flex flex-col" role="listbox" aria-label={label}>
              {visible.map((option) => {
                const active = option.value === value
                return (
                  <li key={option.value} role="option" aria-selected={active}>
                    <button
                      type="button"
                      onClick={() => {
                        onChange(option.value)
                        close()
                      }}
                      className={cn(
                        'flex min-h-14 w-full items-center justify-between gap-3 border-b border-line px-1 py-2 text-left active:bg-plate',
                        active && 'font-semibold',
                      )}
                    >
                      <span className="min-w-0">
                        <span className="block [overflow-wrap:anywhere]">{option.label}</span>
                        {option.hint && (
                          <span className="block text-small text-ink-2">{option.hint}</span>
                        )}
                      </span>
                      {active && <Icon name="check" className="shrink-0 text-accent" />}
                    </button>
                  </li>
                )
              })}
              {visible.length === 0 && (
                <li className="py-6 text-center text-ink-2">{t('ui.nothingFound')}</li>
              )}
            </ul>
          </BottomSheet>
        </>
      )}
    </FieldShell>
  )
}
