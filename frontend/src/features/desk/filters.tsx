import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  fetchBrigades,
  fetchEquipment,
  fetchPeople,
  fetchSections,
  REFERENCE_STALE,
  refKeys,
  shiftKeys,
} from '@/shared/api/reference'
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

export interface ReportSlice {
  section: number | null
  equipment: number | null
  employee: number | null
  brigade: number | null
}

/** Срез отчёта (ТЗ, раздел 7): участок, оборудование участка, исполнитель, бригада. */
export function ReportFilters({ value, onChange }: { value: ReportSlice; onChange: (v: ReportSlice) => void }) {
  const { t } = useTranslation()
  const equipment = useQuery({ queryKey: refKeys.equipment, queryFn: fetchEquipment, staleTime: REFERENCE_STALE })
  const people = useQuery({ queryKey: shiftKeys.people, queryFn: fetchPeople })
  const brigades = useQuery({ queryKey: refKeys.brigades, queryFn: fetchBrigades, staleTime: REFERENCE_STALE })
  return (
    <>
      <SectionFilter value={value.section} onChange={(section) => onChange({ ...value, section, equipment: null })} />
      <FilterSelect
        label={t('panel.equipment')}
        value={value.equipment}
        onChange={(equipment) => onChange({ ...value, equipment })}
        all={t('panel.allEquipment')}
        options={(equipment.data ?? [])
          .filter((e) => !value.section || e.section_id === value.section)
          .map((e) => ({ value: e.id, label: `${e.inv_number} ${e.name}` }))}
      />
      <FilterSelect
        label={t('panel.person')}
        value={value.employee}
        onChange={(employee) => onChange({ ...value, employee })}
        all={t('panel.allPeople')}
        options={(people.data ?? []).map((p) => ({ value: p.employee.id, label: p.employee.full_name }))}
      />
      <FilterSelect
        label={t('reports.brigade')}
        value={value.brigade}
        onChange={(brigade) => onChange({ ...value, brigade })}
        all={t('reports.allBrigades')}
        options={(brigades.data ?? []).map((b) => ({ value: b.id, label: b.name }))}
      />
    </>
  )
}
