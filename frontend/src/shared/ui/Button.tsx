import {
  type ButtonHTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/shared/lib/format'

import { Icon, type IconName } from './Icon'

type Variant = 'primary' | 'secondary' | 'quiet' | 'danger' | 'inverse'
type Size = 'xl' | 'lg' | 'md' | 'sm'

const HOLD_MS = 800

const SIZE: Record<Size, string> = {
  xl: 'min-h-16 px-6 text-body-lg font-semibold gap-3',
  lg: 'min-h-14 px-5 text-body font-semibold gap-2.5',
  md: 'min-h-11 px-4 text-body font-medium gap-2',
  sm: 'min-h-9 px-3 text-small font-medium gap-1.5',
}

const VARIANT: Record<Variant, string> = {
  primary: 'bg-accent text-on-accent active:bg-accent-press',
  secondary: 'bg-surface text-ink border-2 border-ink/80 active:bg-plate',
  quiet: 'bg-transparent text-ink active:bg-plate',
  danger: 'bg-surface text-red border-2 border-red',
  inverse: 'bg-on-steel text-steel active:opacity-90',
}

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  variant?: Variant
  size?: Size
  block?: boolean
  icon?: IconName
  loading?: boolean
  children: ReactNode
  /** Подтверждение удержанием: действие срабатывает, только если держать 800 мс. */
  onHoldConfirm?: () => void
}

export function Button({
  variant = 'primary',
  size = 'lg',
  block = false,
  icon,
  loading = false,
  children,
  className,
  disabled,
  onHoldConfirm,
  type = 'button',
  ...rest
}: ButtonProps) {
  const isHold = Boolean(onHoldConfirm)
  const hold = useHold(onHoldConfirm, disabled || loading)
  const { t } = useTranslation()

  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'relative inline-flex select-none items-center justify-center overflow-hidden rounded-control',
        'transition-colors duration-100 disabled:cursor-not-allowed disabled:opacity-45',
        'touch-manipulation',
        SIZE[size],
        VARIANT[variant],
        block && 'w-full',
        className,
      )}
      {...(isHold ? hold.handlers : {})}
      {...rest}
    >
      {isHold && (
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 bg-red"
          style={{
            width: `${hold.progress * 100}%`,
            transition: hold.progress === 0 ? 'width 150ms ease-out' : 'none',
          }}
        />
      )}
      <span
        className={cn(
          'relative inline-flex items-center gap-[inherit]',
          isHold && hold.progress > 0.5 && 'text-white',
        )}
      >
        {loading ? <Spinner /> : icon && <Icon name={icon} size={size === 'sm' ? 18 : 22} />}
        <span className="flex flex-col items-start leading-tight">
          <span>{children}</span>
          {isHold && (
            <span className="text-stamp font-normal opacity-80">{t('ui.hold')}</span>
          )}
        </span>
      </span>
    </button>
  )
}

function Spinner() {
  return (
    <span
      aria-hidden
      className="inline-block size-5 animate-spin rounded-full border-2 border-current border-r-transparent"
    />
  )
}

function useHold(onConfirm: (() => void) | undefined, disabled: boolean | undefined) {
  const [holding, setHolding] = useState(false)
  const [progress, setProgress] = useState(0)
  const confirmRef = useRef(onConfirm)
  useEffect(() => {
    confirmRef.current = onConfirm
  })

  useEffect(() => {
    if (!holding) return
    const startedAt = performance.now()
    let frame = 0
    const step = () => {
      const value = Math.min(1, (performance.now() - startedAt) / HOLD_MS)
      setProgress(value)
      if (value >= 1) {
        navigator.vibrate?.(40)
        confirmRef.current?.()
        setHolding(false)
        window.setTimeout(() => setProgress(0), 250)
        return
      }
      frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [holding])

  const start = useCallback(() => {
    if (disabled) return
    navigator.vibrate?.(10)
    setHolding(true)
  }, [disabled])

  const stop = useCallback(() => {
    setHolding(false)
    setProgress((p) => (p >= 1 ? p : 0))
  }, [])

  return {
    progress,
    handlers: {
      onPointerDown: start,
      onPointerUp: stop,
      onPointerLeave: stop,
      onPointerCancel: stop,
      onContextMenu: (e: { preventDefault: () => void }) => e.preventDefault(),
      onKeyDown: (e: KeyboardEvent) => {
        if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) {
          e.preventDefault()
          start()
        }
      },
      onKeyUp: (e: KeyboardEvent) => {
        if (e.key === ' ' || e.key === 'Enter') stop()
      },
    },
  }
}
