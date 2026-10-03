import { type ReactNode, useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'

import { cn } from '@/shared/lib/format'

import { Icon } from './Icon'

interface BottomSheetProps {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  /** false — закрыть можно только кнопками внутри (например, аварийный ответ) */
  dismissible?: boolean
}

/** Выезжающий снизу лист. На широком экране — по центру, не шире 560 px. */
export function BottomSheet({
  open,
  title,
  onClose,
  children,
  footer,
  dismissible = true,
}: BottomSheetProps) {
  const { t } = useTranslation()
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    panel.current?.focus()
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && dismissible) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      previous?.focus()
    }
  }, [open, dismissible, onClose])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-40 flex items-end justify-center md:items-center">
      <div
        aria-hidden
        className="absolute inset-0 animate-fade-in bg-[var(--scrim)]"
        onClick={dismissible ? onClose : undefined}
      />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn(
          'relative flex max-h-[88dvh] w-full max-w-[560px] animate-sheet-in flex-col',
          'rounded-t-sheet bg-surface text-ink shadow-overlay outline-none md:rounded-sheet',
        )}
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 id={titleId} className="text-h2 font-semibold">
            {title}
          </h2>
          {dismissible && (
            <button
              type="button"
              onClick={onClose}
              className="-mr-2 inline-flex size-12 items-center justify-center rounded-control active:bg-plate"
              aria-label={t('common.close')}
            >
              <Icon name="x" />
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-3">{children}</div>
        {footer && (
          <div className="border-t border-line px-4 pt-3 pb-[max(12px,env(safe-area-inset-bottom))]">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
