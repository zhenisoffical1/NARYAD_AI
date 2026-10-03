import type { ReactNode } from 'react'

import { Icon, type IconName } from './Icon'

/** Пустой экран: что здесь будет и что сделать. Без иллюстраций. */
export function EmptyState({
  icon = 'list',
  title,
  hint,
  action,
}: {
  icon?: IconName
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-tag border border-dashed border-line px-4 py-6">
      <span className="inline-flex size-12 items-center justify-center rounded-tag bg-plate text-ink-2">
        <Icon name={icon} size={26} />
      </span>
      <div>
        <p className="text-body-lg font-semibold">{title}</p>
        {hint && <p className="mt-1 text-ink-2">{hint}</p>}
      </div>
      {action}
    </div>
  )
}
