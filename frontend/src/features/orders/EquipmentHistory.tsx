import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { fetchEquipmentHistory } from '@/shared/api/reference'
import { cn, ddmm, duration } from '@/shared/lib/format'
import { Button, Panel, Skeleton, StatusBadge } from '@/shared/ui'

const SHOWN = 5

/** История оборудования (ТЗ 5.5): наряды, ремонты и простои — видно, ломается ли узел снова. */
export function EquipmentHistory({ equipmentId, currentOrderId }: { equipmentId: number; currentOrderId?: number }) {
  const { t } = useTranslation()
  const [all, setAll] = useState(false)
  const history = useQuery({
    queryKey: ['ref', 'equipment', equipmentId, 'history'],
    queryFn: () => fetchEquipmentHistory(equipmentId),
  })
  const h = history.data
  const orders = (h?.orders ?? []).filter((o) => o.id !== currentOrderId)
  const shown = all ? orders : orders.slice(0, SHOWN)

  return (
    <Panel title={t('history.title')}>
      {!h ? (
        <Skeleton className="h-24" />
      ) : (
        <div className="flex flex-col gap-3">
          <dl className="grid grid-cols-3 gap-2 text-center">
            <Stat label={t('history.total')} value={String(h.orders_total)} />
            <Stat label={t('history.unplanned')} value={String(h.unplanned_total)} danger={h.unplanned_total > 0} />
            <Stat
              label={t('history.downtime')}
              value={h.downtime_minutes_total ? duration(h.downtime_minutes_total) : '0'}
              danger={h.downtime_minutes_total > 0}
            />
          </dl>
          {orders.length === 0 ? (
            <p className="text-small text-ink-3">{t('history.empty')}</p>
          ) : (
            <ul className="divide-y divide-line/70">
              {shown.map((o) => (
                <li key={o.id} className="flex items-start justify-between gap-3 py-2">
                  <div className="min-w-0">
                    <p className="text-small">
                      <span className="cond font-semibold">№{o.number}</span>
                      <span className="text-ink-3"> {ddmm(o.created_at)}</span>
                      <span className={cn('ml-2', o.type === 'unplanned' ? 'text-red' : 'text-ink-3')}>
                        {t(o.type === 'unplanned' ? 'issue.unplanned' : 'issue.planned')}
                      </span>
                    </p>
                    <p className="line-clamp-2 text-small text-ink-2">{o.description}</p>
                  </div>
                  <StatusBadge status={o.status} size="sm" />
                </li>
              ))}
            </ul>
          )}
          {orders.length > SHOWN && (
            <Button variant="quiet" size="sm" onClick={() => setAll((v) => !v)}>
              {all ? t('history.less') : t('history.more', { count: orders.length - SHOWN })}
            </Button>
          )}
        </div>
      )}
    </Panel>
  )
}

function Stat({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className="rounded-[8px] bg-plate/70 px-2 py-2">
      <dd className={cn('cond text-h2 font-bold', danger && 'text-red')}>{value}</dd>
      <dt className="text-stamp font-normal text-ink-3">{label}</dt>
    </div>
  )
}
