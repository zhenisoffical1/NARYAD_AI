import { useState } from 'react'
import { useTranslation } from 'react-i18next'

export type Days = 7 | 30 | 90

/** Период «7 / 30 / 90 дней» и подписи к нему — общий для обзора, аналитики и рейтинга. */
export function useDays(initial: Days) {
  const { t } = useTranslation()
  const [days, setDays] = useState<Days>(initial)
  const options: { value: Days; label: string }[] = [
    { value: 7, label: t('desk.days7') },
    { value: 30, label: t('desk.days30') },
    { value: 90, label: t('desk.days90') },
  ]
  return [days, setDays, options] as const
}
