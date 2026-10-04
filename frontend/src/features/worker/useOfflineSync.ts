import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { flushPending, loadPending } from '@/shared/lib/offlineQueue'
import { toast } from '@/shared/lib/toast'

const RETRY_MS = 15_000

/** Отправляет отложенные действия, как только появилась сеть, и раз в 15 секунд на всякий случай. */
export function useOfflineSync(): void {
  const queryClient = useQueryClient()
  const { t } = useTranslation()

  useEffect(() => {
    const sync = async () => {
      const { sent, rejected } = await flushPending()
      if (sent.length) {
        toast(t('offline.sent', { n: sent.length }))
        void queryClient.invalidateQueries({ queryKey: ['orders'] })
      }
      for (const [item, reason] of rejected) {
        toast(t('offline.rejected', { n: item.number, reason }), 'error')
      }
    }
    void loadPending().then(sync)
    const onOnline = () => void sync()
    window.addEventListener('online', onOnline)
    const timer = window.setInterval(() => void sync(), RETRY_MS)
    return () => {
      window.removeEventListener('online', onOnline)
      window.clearInterval(timer)
    }
  }, [queryClient, t])
}
