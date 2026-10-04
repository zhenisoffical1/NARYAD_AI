import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { fetchSummary, shiftKeys } from '@/shared/api/reference'
import type { ShiftSummary } from '@/shared/api/types'
import { hhmm } from '@/shared/lib/format'

export function useShiftSummary() {
  return useQuery({ queryKey: shiftKeys.summary, queryFn: fetchSummary, refetchInterval: 60_000 })
}

/** «Дневная смена 08:00–20:00» по границам смены с сервера. */
export function useShiftLabel(summary: ShiftSummary | undefined): string {
  const { t } = useTranslation()
  if (!summary) return ''
  const startHour = new Date(summary.shift_start).getHours()
  const name = startHour < 12 ? t('panel.shiftDay') : t('panel.shiftNight')
  return `${name} ${hhmm(summary.shift_start)}–${hhmm(summary.shift_end)}`
}
