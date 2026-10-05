import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { DeskHeader } from '@/features/desk/DeskHeader'
import {
  type AdminKind,
  type AdminRecord,
  adminKeys,
  fetchAdminList,
  importAdminCsv,
} from '@/shared/api/admin'
import { cn } from '@/shared/lib/format'
import { toast } from '@/shared/lib/toast'
import { Button, EmptyState, Icon, Initials, Skeleton, Tabs } from '@/shared/ui'

import { downloadTemplate, type FieldDef, KINDS, type KindDef } from './kinds'
import { type OptionLists, RecordForm } from './RecordForm'
import { SystemTab } from './SystemTab'

type TabKey = AdminKind | 'system'

/** Администратор: люди, оборудование и справочники, импорт из 1С (CSV), состояние системы. */
export function AdminPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as TabKey | null) ?? 'employees'
  const def = KINDS.find((k) => k.kind === tab)

  return (
    <div className="flex min-h-dvh flex-col bg-bg bg-grad-page text-ink">
      <DeskHeader title={t('admin.title')} subtitle={t('admin.subtitle')} />
      <main className="mx-auto flex w-full max-w-[1280px] flex-col gap-5 px-6 py-5">
        <Tabs<TabKey>
          label={t('admin.title')}
          value={tab}
          onChange={(v) => setParams(v === 'employees' ? {} : { tab: v }, { replace: true })}
          items={[
            ...KINDS.map((k) => ({
              value: k.kind,
              label: t(`admin.tab.${k.kind}`),
            })),
            { value: 'system' as const, label: t('admin.tab.system') },
          ]}
        />
        {def ? <Directory key={def.kind} def={def} /> : <SystemTab />}
      </main>
    </div>
  )
}

function Directory({ def }: { def: KindDef }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<string | null>(null)
  const [editing, setEditing] = useState<AdminRecord | 'new' | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const list = useQuery({
    queryKey: adminKeys.list(def.kind),
    queryFn: () => fetchAdminList(def.kind),
  })
  const needsSections = def.fields.some((f) => f.options === 'sections')
  const needsBrigades = def.fields.some((f) => f.options === 'brigades')
  const sections = useQuery({
    queryKey: adminKeys.list('sections'),
    queryFn: () => fetchAdminList('sections'),
    enabled: needsSections,
  })
  const brigades = useQuery({
    queryKey: adminKeys.list('brigades'),
    queryFn: () => fetchAdminList('brigades'),
    enabled: needsBrigades,
  })

  const options: OptionLists = useMemo(
    () => ({
      roles: (['worker', 'master', 'boss', 'admin'] as const).map((r) => ({
        value: r,
        label: t(`roles.${r}`),
      })),
      shifts: (['day', 'night'] as const).map((s) => ({
        value: s,
        label: t(`admin.shift.${s}`),
      })),
      criticality: (['A', 'B', 'C'] as const).map((c) => ({
        value: c,
        label: t(`admin.crit.${c}`),
      })),
      sections: (sections.data ?? []).map((s) => ({
        value: s.id,
        label: String(s.name),
      })),
      brigades: (brigades.data ?? []).map((b) => ({
        value: b.id,
        label: String(b.name),
      })),
    }),
    [t, sections.data, brigades.data],
  )

  const importCsv = useMutation({
    mutationFn: (file: File) => importAdminCsv(def.kind, file),
    onSuccess: (r) => {
      void queryClient.invalidateQueries({ queryKey: ['admin'] })
      void queryClient.invalidateQueries({ queryKey: ['ref'] })
      if (r.errors.length) toast(r.errors.join('\n'), 'error')
      else toast(t('admin.imported', { created: r.created, updated: r.updated }))
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const rows = (list.data ?? []).filter((r) => {
    if (roleFilter && r.role !== roleFilter) return false
    const q = query.trim().toLowerCase()
    return (
      !q ||
      def.search.some((k) =>
        String(r[k] ?? '')
          .toLowerCase()
          .includes(q),
      )
    )
  })
  const columns = def.fields.filter((f) => f.column)
  const isPeople = def.kind === 'employees'

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex min-w-[280px] flex-1 items-center gap-2 rounded-control border-2 border-line bg-surface px-3 focus-within:border-accent">
          <Icon name="search" size={20} className="text-ink-3" />
          <span className="sr-only">{t('admin.search')}</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t(`admin.searchHint.${def.kind}`)}
            className="h-11 flex-1 bg-transparent text-body outline-none placeholder:text-ink-3"
          />
        </label>
        {isPeople && (
          <div
            role="radiogroup"
            aria-label={t('admin.f.role')}
            className="flex rounded-control border border-line bg-surface p-1 shadow-card"
          >
            {[null, 'worker', 'master', 'boss', 'admin'].map((r) => (
              <button
                key={r ?? 'all'}
                type="button"
                role="radio"
                aria-checked={roleFilter === r}
                onClick={() => setRoleFilter(r)}
                className={cn(
                  'min-h-9 rounded-[6px] px-3 text-small font-semibold',
                  roleFilter === r ? 'bg-accent bg-grad-primary text-on-accent' : 'text-ink-2 hover:text-ink',
                )}
              >
                {r ? t(`admin.rolesPlural.${r as 'worker'}`) : t('admin.all')}
              </button>
            ))}
          </div>
        )}
        <div className="ml-auto flex gap-2">
          <Button variant="quiet" size="md" icon="doc" onClick={() => downloadTemplate(def)}>
            {t('admin.template')}
          </Button>
          <Button
            variant="secondary"
            size="md"
            icon="report"
            loading={importCsv.isPending}
            onClick={() => fileRef.current?.click()}
          >
            {t('admin.import')}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) importCsv.mutate(file)
              e.target.value = ''
            }}
          />
          <Button variant="cta" size="md" icon="plus" onClick={() => setEditing('new')}>
            {t(`admin.new.${def.kind}`)}
          </Button>
        </div>
      </div>

      <div className="overflow-hidden rounded-[12px] border border-line bg-surface shadow-card">
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5 text-small text-ink-3">
          <span>{t('admin.count', { count: rows.length })}</span>
          <span>{t('admin.importNote')}</span>
        </div>
        {list.isPending ? (
          <div className="flex flex-col gap-2 p-4">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState icon="search" title={t('admin.empty')} hint={t('admin.emptyHint')} />
        ) : (
          <table className="w-full text-left text-small">
            <thead className="bg-plate/60 text-ink-3">
              <tr>
                {columns.map((c) => (
                  <th key={c.key} className="px-4 py-2.5 font-semibold">
                    {t(`admin.f.${c.key}` as 'admin.f.name')}
                  </th>
                ))}
                {isPeople && <th className="px-4 py-2.5 font-semibold">{t('admin.f.telegram')}</th>}
                {isPeople && <th className="px-4 py-2.5 font-semibold">{t('admin.f.state')}</th>}
                {def.kind === 'fault-codes' && (
                  <th className="px-4 py-2.5 font-semibold">{t('admin.f.norm')}</th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.id}
                  tabIndex={0}
                  onClick={() => setEditing(r)}
                  onKeyDown={(e) => e.key === 'Enter' && setEditing(r)}
                  className={cn(
                    'cursor-pointer border-t border-line/70 hover:bg-accent-soft/50 focus-visible:bg-accent-soft/60',
                    isPeople && r.is_active === false && 'text-ink-3',
                  )}
                >
                  {columns.map((c, i) => (
                    <td key={c.key} className="px-4 py-2.5 align-middle">
                      <Cell field={c} record={r} options={options} first={i === 0 && isPeople} />
                    </td>
                  ))}
                  {isPeople && (
                    <td className="px-4 py-2.5">
                      {r.telegram_linked ? (
                        <span className="inline-flex items-center gap-1 text-green-strong dark:text-green">
                          <Icon name="check" size={16} />
                          {t('admin.linked')}
                        </span>
                      ) : (
                        <span className="text-ink-3">{t('admin.notLinked')}</span>
                      )}
                    </td>
                  )}
                  {isPeople && (
                    <td className="px-4 py-2.5">
                      <span
                        className={cn(
                          'stamp inline-flex h-6 items-center gap-1.5 rounded-[6px] px-2',
                          r.is_active === false
                            ? 'bg-plate text-ink-3'
                            : r.on_shift
                              ? 'bg-green-soft text-green-strong dark:text-green'
                              : 'bg-accent-soft text-accent',
                        )}
                      >
                        {r.is_active === false
                          ? t('admin.disabled')
                          : r.on_shift
                            ? t('admin.onShift')
                            : t('admin.active')}
                      </span>
                    </td>
                  )}
                  {def.kind === 'fault-codes' && (
                    <td className="px-4 py-2.5 text-ink-2">
                      {r.norm_hours
                        ? t('admin.normValue', {
                            hours: String(r.norm_hours),
                            count: Array.isArray(r.norm_materials) ? r.norm_materials.length : 0,
                          })
                        : '—'}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editing && (
        <RecordForm
          def={def}
          record={editing === 'new' ? null : editing}
          options={options}
          onClose={() => setEditing(null)}
        />
      )}
    </section>
  )
}

function Cell({
  field,
  record,
  options,
  first,
}: {
  field: FieldDef
  record: AdminRecord
  options: OptionLists
  first: boolean
}) {
  const value = record[field.key]
  if (value === null || value === undefined || value === '') return <span className="text-ink-3">—</span>
  if (field.options) {
    const label =
      options[field.options].find((o) => String(o.value) === String(value))?.label ?? String(value)
    if (field.options === 'criticality') {
      return (
        <span
          className={cn(
            'cond inline-flex size-7 items-center justify-center rounded-[6px] font-bold',
            value === 'A'
              ? 'bg-red-soft text-red'
              : value === 'B'
                ? 'bg-yellow-soft text-amber'
                : 'bg-plate text-ink-2',
          )}
          title={label}
        >
          {String(value)}
        </span>
      )
    }
    return <span>{label}</span>
  }
  if (first) {
    return (
      <span className="flex items-center gap-2.5 font-semibold text-ink">
        <Initials name={String(value)} size={28} />
        {String(value)}
      </span>
    )
  }
  if (field.key === 'inv_number' || field.key === 'code')
    return <span className="cond font-semibold">{String(value)}</span>
  return <span>{String(value)}</span>
}
