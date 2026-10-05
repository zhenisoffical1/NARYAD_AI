import type { AdminKind, AdminRecord } from '@/shared/api/admin'

/** Как показать и редактировать поле справочника. Подписи — ключи admin.f.* */
export interface FieldDef {
  key: string
  type: 'text' | 'number' | 'select' | 'bool' | 'pin'
  required?: boolean
  /** Источник вариантов для select: фиксированный список или другой справочник */
  options?: 'roles' | 'shifts' | 'criticality' | 'sections' | 'brigades'
  /** В таблице показывать */
  column?: boolean
  /** Нельзя менять после создания (например, логин) */
  hint?: boolean
}

export interface KindDef {
  kind: AdminKind
  /** Чем назвать запись в заголовке формы */
  title: (r: AdminRecord) => string
  /** Поля, по которым ищет строка поиска */
  search: string[]
  fields: FieldDef[]
  /** Заголовок CSV-шаблона: section/brigade — по названию, а не по id */
  csv: string[]
}

export const KINDS: KindDef[] = [
  {
    kind: 'employees',
    title: (r) => String(r.full_name ?? ''),
    search: ['full_name', 'login', 'specialty'],
    fields: [
      { key: 'full_name', type: 'text', required: true, column: true },
      { key: 'login', type: 'text', required: true, column: true, hint: true },
      {
        key: 'role',
        type: 'select',
        options: 'roles',
        required: true,
        column: true,
      },
      { key: 'specialty', type: 'text', column: true },
      { key: 'grade', type: 'number' },
      { key: 'brigade_id', type: 'select', options: 'brigades', column: true },
      { key: 'shift', type: 'select', options: 'shifts', column: true },
      { key: 'on_shift', type: 'bool' },
      { key: 'is_active', type: 'bool' },
      { key: 'pin', type: 'pin' },
      { key: 'external_id', type: 'text' },
    ],
    csv: ['login', 'full_name', 'role', 'specialty', 'grade', 'brigade', 'shift', 'pin', 'external_id'],
  },
  {
    kind: 'equipment',
    title: (r) => `${String(r.inv_number ?? '')} ${String(r.name ?? '')}`,
    search: ['name', 'inv_number', 'type'],
    fields: [
      { key: 'inv_number', type: 'text', required: true, column: true },
      { key: 'name', type: 'text', required: true, column: true },
      {
        key: 'section_id',
        type: 'select',
        options: 'sections',
        required: true,
        column: true,
      },
      { key: 'type', type: 'text', required: true, column: true },
      {
        key: 'criticality',
        type: 'select',
        options: 'criticality',
        required: true,
        column: true,
      },
      { key: 'qr_code', type: 'text', hint: true },
      { key: 'external_id', type: 'text' },
    ],
    csv: ['inv_number', 'name', 'section', 'type', 'criticality', 'qr_code', 'external_id'],
  },
  {
    kind: 'sections',
    title: (r) => String(r.name ?? ''),
    search: ['name'],
    fields: [
      { key: 'name', type: 'text', required: true, column: true },
      { key: 'external_id', type: 'text', column: true },
    ],
    csv: ['name', 'external_id'],
  },
  {
    kind: 'brigades',
    title: (r) => String(r.name ?? ''),
    search: ['name'],
    fields: [
      { key: 'name', type: 'text', required: true, column: true },
      { key: 'external_id', type: 'text', column: true },
    ],
    csv: ['name', 'external_id'],
  },
  {
    kind: 'fault-codes',
    title: (r) => `${String(r.code ?? '')} ${String(r.name ?? '')}`,
    search: ['code', 'name'],
    fields: [
      { key: 'code', type: 'text', required: true, column: true },
      { key: 'name', type: 'text', required: true, column: true },
      {
        key: 'category',
        type: 'text',
        required: true,
        column: true,
        hint: true,
      },
      { key: 'norm_hours', type: 'number', hint: true },
      { key: 'external_id', type: 'text' },
    ],
    csv: ['code', 'category', 'name', 'norm_hours', 'external_id'],
  },
  {
    kind: 'materials',
    title: (r) => String(r.name ?? ''),
    search: ['name', 'category'],
    fields: [
      { key: 'name', type: 'text', required: true, column: true },
      { key: 'unit', type: 'text', required: true, column: true },
      { key: 'category', type: 'text', column: true },
      { key: 'external_id', type: 'text', column: true },
    ],
    csv: ['name', 'unit', 'category', 'external_id'],
  },
]

/** Скачать пустой CSV-шаблон справочника (UTF-8 с BOM — откроется в Excel без кракозябр). */
export function downloadTemplate(def: KindDef) {
  const blob = new Blob([`${String.fromCharCode(0xfeff)}${def.csv.join(';')}\n`], {
    type: 'text/csv;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${def.kind}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
