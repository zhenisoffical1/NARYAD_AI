import { useTranslation } from 'react-i18next'

import { usePending } from '@/shared/lib/offlineQueue'
import { Icon } from '@/shared/ui'

/** «Ожидает отправки» — действия, сделанные без сети. Для одного наряда или для всех. */
export function PendingBanner({ orderId }: { orderId?: number }) {
  const { t } = useTranslation()
  const items = usePending((s) => s.items).filter((i) => orderId === undefined || i.orderId === orderId)
  if (!items.length) return null
  return (
    <div role="status" className="flex items-start gap-3 border-b border-line bg-yellow-soft px-4 py-3">
      <Icon name="signal" size={22} className="mt-0.5 shrink-0 text-ink-2" />
      <div className="min-w-0">
        <p className="font-semibold">{t('offline.pending', { n: items.length })}</p>
        <p className="text-small text-ink-2">
          {items.map((i) => `№${i.number}: ${t(`actions.${i.action}` as 'actions.accept')}`).join(', ')}
        </p>
      </div>
    </div>
  )
}
