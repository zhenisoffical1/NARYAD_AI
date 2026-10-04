import {
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
  useId,
} from 'react'

import { cn } from '@/shared/lib/format'

const CONTROL =
  'w-full rounded-control border-2 border-line bg-surface px-4 text-body text-ink ' +
  'placeholder:text-ink-3 focus:border-accent focus:outline-none aria-[invalid=true]:border-red'

interface FieldShellProps {
  label: string
  /** Подпись только для экранного диктора — когда над полем уже есть заголовок */
  labelHidden?: boolean
  hint?: string
  error?: string | null
  /** Кнопка справа от подписи (например, голосовой ввод) */
  action?: ReactNode
  children: (id: string, describedBy: string | undefined) => ReactNode
}

export function FieldShell({ label, labelHidden, hint, error, action, children }: FieldShellProps) {
  const id = useId()
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <div className="flex flex-col gap-1.5">
      {(!labelHidden || action) && (
        <div
          className={cn(
            'flex min-h-6 items-end gap-2',
            labelHidden ? 'justify-end' : 'justify-between',
          )}
        >
          <label
            htmlFor={id}
            className={cn('text-small font-semibold text-ink-2', labelHidden && 'sr-only')}
          >
            {label}
          </label>
          {action}
        </div>
      )}
      {labelHidden && !action && (
        <label htmlFor={id} className="sr-only">
          {label}
        </label>
      )}
      {children(id, describedBy)}
      {error ? (
        <p id={`${id}-error`} className="flex gap-1.5 text-small font-medium text-red" role="alert">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="text-small text-ink-3">
            {hint}
          </p>
        )
      )}
    </div>
  )
}

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  labelHidden?: boolean
  hint?: string
  error?: string | null
  action?: ReactNode
}

export function TextField({
  label,
  labelHidden,
  hint,
  error,
  action,
  className,
  ...rest
}: TextFieldProps) {
  return (
    <FieldShell label={label} labelHidden={labelHidden} hint={hint} error={error} action={action}>
      {(id, describedBy) => (
        <input
          id={id}
          aria-describedby={describedBy}
          aria-invalid={Boolean(error) || undefined}
          className={cn(CONTROL, 'min-h-14', className)}
          {...rest}
        />
      )}
    </FieldShell>
  )
}

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
  labelHidden?: boolean
  hint?: string
  error?: string | null
  action?: ReactNode
}

export function TextArea({
  label,
  labelHidden,
  hint,
  error,
  action,
  className,
  rows = 3,
  ...rest
}: TextAreaProps) {
  return (
    <FieldShell label={label} labelHidden={labelHidden} hint={hint} error={error} action={action}>
      {(id, describedBy) => (
        <textarea
          id={id}
          rows={rows}
          aria-describedby={describedBy}
          aria-invalid={Boolean(error) || undefined}
          className={cn(CONTROL, 'min-h-14 resize-y py-3 leading-6 field-sizing-content', className)}
          {...rest}
        />
      )}
    </FieldShell>
  )
}
