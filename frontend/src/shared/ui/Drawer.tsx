import { type ReactNode, useEffect, useId } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'

import { Icon } from './Icon'

/** Боковая панель справа (десктоп). На узком экране — во весь экран. */
export function Drawer({
  open,
  title,
  subtitle,
  onClose,
  children,
  footer,
  width = 560,
}: {
  open: boolean
  title: ReactNode
  subtitle?: ReactNode
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  width?: number
}) {
  const { t } = useTranslation()
  const titleId = useId()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-end">
      <div
        aria-hidden
        className="absolute inset-0 animate-fade-in bg-[var(--scrim)] md:bg-[rgb(16_22_27/0.25)]"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{ maxWidth: width }}
        className="relative flex h-full w-full animate-[drawer-in_180ms_ease-out] flex-col bg-bg shadow-overlay"
      >
        <header className="flex items-start justify-between gap-3 border-b border-line bg-surface px-5 py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-h2 font-semibold">
              {title}
            </h2>
            {subtitle && <div className="mt-0.5 text-small text-ink-2">{subtitle}</div>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('common.close')}
            className="-mr-2 inline-flex size-11 shrink-0 items-center justify-center rounded-control text-ink-2 hover:bg-plate"
          >
            <Icon name="x" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto">{children}</div>
        {footer && <footer className="border-t border-line bg-surface px-5 py-3">{footer}</footer>}
      </aside>
    </div>,
    document.body,
  )
}
