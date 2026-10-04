import { useTranslation } from 'react-i18next'

import type { ShiftSummary } from '@/shared/api/types'
import { Counter, CounterBoard } from '@/shared/ui'

/** Табло смены: выдано / выполнено / просрочено / оборудование в простое. */
export function ShiftCounters({
  summary,
  layout = 'row',
  onOverdue,
}: {
  summary: ShiftSummary | undefined
  layout?: 'row' | 'grid'
  onOverdue?: () => void
}) {
  const { t } = useTranslation()
  const value = (n: number | undefined) => (n === undefined ? '—' : n)
  return (
    <CounterBoard columns={layout === 'grid' ? 2 : undefined}>
      <Counter tone="blue" label={t('master.issued')} value={value(summary?.issued)} />
      <Counter tone="green" label={t('master.done')} value={value(summary?.done)} />
      <Counter
        label={t('master.overdue')}
        value={value(summary?.overdue)}
        alert={Boolean(summary?.overdue)}
        onClick={onOverdue}
      />
      <Counter
        tone="amber"
        label={t('master.downtime')}
        value={value(summary?.equipment_down)}
        alert={Boolean(summary?.equipment_down)}
      />
    </CounterBoard>
  )
}
