import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { fetchSections, REFERENCE_STALE, refKeys } from '@/shared/api/reference'
import { FilterSelect } from '@/shared/ui'

/** Фильтр по участку — справочник участков, «Все участки» по умолчанию. */
export function SectionFilter({
  value,
  onChange,
}: {
  value: number | null
  onChange: (value: number | null) => void
}) {
  const { t } = useTranslation()
  const sections = useQuery({ queryKey: refKeys.sections, queryFn: fetchSections, staleTime: REFERENCE_STALE })
  return (
    <FilterSelect
      label={t('desk.section')}
      value={value}
      onChange={onChange}
      all={t('desk.allSections')}
      options={(sections.data ?? []).map((s) => ({ value: s.id, label: s.name }))}
    />
  )
}
