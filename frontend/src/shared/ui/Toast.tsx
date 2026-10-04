import { cn } from '@/shared/lib/format'
import { type ToastTone, useToasts } from '@/shared/lib/toast'

import { Icon, type IconName } from './Icon'

const STYLE: Record<ToastTone, { icon: IconName; bar: string }> = {
  ok: { icon: 'check', bar: 'bg-green' },
  error: { icon: 'alert', bar: 'bg-red' },
  info: { icon: 'bell', bar: 'bg-accent' },
}

/** Тосты над нижней панелью действий; на десктопе — у нижнего края. */
export function Toaster() {
  const items = useToasts((s) => s.items)
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-[calc(96px+env(safe-area-inset-bottom))] z-50 flex flex-col items-center gap-2 px-4 md:bottom-6"
    >
      {items.map((item) => (
        <div
          key={item.id}
          role={item.tone === 'error' ? 'alert' : 'status'}
          className="pointer-events-auto flex w-full max-w-md animate-sheet-in overflow-hidden rounded-[10px] bg-steel bg-[linear-gradient(90deg,#13324f,#0e5560)] text-on-steel shadow-overlay"
        >
          <span aria-hidden className={cn('w-1.5 shrink-0', STYLE[item.tone].bar)} />
          <span className="flex items-start gap-2 px-3 py-3">
            <Icon name={STYLE[item.tone].icon} size={22} className="shrink-0" />
            <span className="text-body">{item.text}</span>
          </span>
        </div>
      ))}
    </div>
  )
}
