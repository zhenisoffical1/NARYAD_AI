import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { orderAction, orderKeys } from '@/shared/api/orders'
import type { OrderDetail } from '@/shared/api/types'
import { enqueue, isOffline, OFFLINE_ACTIONS } from '@/shared/lib/offlineQueue'
import { toast } from '@/shared/lib/toast'

export interface ActionVars {
  action: string
  reason?: string
  comment?: string
}

/** Действие по наряду: обновляет карточку и списки, сообщает результат тем же словом, что на кнопке. */
export function useOrderAction(order: { id: number; number: number }, onDone?: (d: OrderDetail) => void) {
  const queryClient = useQueryClient()
  const { t } = useTranslation()

  return useMutation({
    mutationFn: ({ action, reason, comment }: ActionVars) =>
      orderAction(order.id, action, { reason, comment }),
    onSuccess: (detail, vars) => {
      queryClient.setQueryData(orderKeys.detail(order.id), detail)
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: ['shift'] })
      toast(t(`done.${vars.action}` as 'done.accept', { n: order.number }))
      onDone?.(detail)
    },
    onError: (error, vars) => {
      // Нет сети — действие не теряется: ляжет в очередь и уйдёт само
      if (isOffline(error) && OFFLINE_ACTIONS.has(vars.action)) {
        void enqueue({ orderId: order.id, number: order.number, ...vars }).then(() =>
          toast(t('offline.queued', { action: t(`actions.` as 'actions.accept') }), 'info'),
        )
        return
      }
      toast(error.message, 'error')
    },
  })
}
