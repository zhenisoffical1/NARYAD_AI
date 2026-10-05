import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { EquipmentHistory } from '@/features/orders/EquipmentHistory'
import { type AdminRecord, createAdminRecord, deleteAdminRecord, updateAdminRecord } from '@/shared/api/admin'
import { cn } from '@/shared/lib/format'
import { toast } from '@/shared/lib/toast'
import { Button, Drawer, FieldShell, TextField, ToggleRow } from '@/shared/ui'
import { QrCode } from '@/shared/ui/QrCode'

import type { FieldDef, KindDef } from './kinds'

export type OptionLists = Record<
  NonNullable<FieldDef['options']>,
  { value: string | number; label: string }[]
>

const SELECT =
  'min-h-14 w-full rounded-control border-2 border-line bg-surface px-3 text-body text-ink focus:border-accent focus:outline-none'

/** Форма записи справочника в боковой панели: добавить, изменить, удалить. */
export function RecordForm({
  def,
  record,
  options,
  onClose,
}: {
  def: KindDef
  /** null — новая запись */
  record: AdminRecord | null
  options: OptionLists
  onClose: () => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const isNew = record === null
  const [values, setValues] = useState<Record<string, unknown>>(() => initial(def, record))
  const [error, setError] = useState<string | null>(null)

  const done = (text: string) => {
    void queryClient.invalidateQueries({ queryKey: ['admin'] })
    void queryClient.invalidateQueries({ queryKey: ['ref'] })
    void queryClient.invalidateQueries({ queryKey: ['shift'] })
    toast(text)
    onClose()
  }

  const save = useMutation({
    mutationFn: () => {
      const data = payload(def, values, record)
      return isNew ? createAdminRecord(def.kind, data) : updateAdminRecord(def.kind, record.id, data)
    },
    onSuccess: () => done(isNew ? t('admin.created') : t('admin.saved')),
    onError: (e: Error) => setError(e.message),
  })
  const remove = useMutation({
    mutationFn: () => deleteAdminRecord(def.kind, record?.id ?? 0),
    onSuccess: () => done(t('admin.deleted')),
    onError: (e: Error) => setError(e.message),
  })

  const set = (key: string, value: unknown) => {
    setError(null)
    setValues((v) => ({ ...v, [key]: value }))
  }
  const missing = def.fields.some(
    (f) => (f.required || (f.type === 'pin' && isNew && def.kind === 'employees')) && empty(values[f.key]),
  )

  return (
    <Drawer
      open
      onClose={onClose}
      width={520}
      title={isNew ? t(`admin.new.${def.kind}`) : def.title(record)}
      subtitle={t(`admin.tab.${def.kind}`)}
      footer={
        <div className="flex flex-col gap-3">
          {error && (
            <p role="alert" className="rounded-control bg-red-soft px-3 py-2 text-small font-medium text-red">
              {error}
            </p>
          )}
          <div className="flex items-center gap-4">
            <Button
              icon="check"
              className="flex-1"
              disabled={missing}
              loading={save.isPending}
              onClick={() => save.mutate()}
            >
              {isNew ? t('admin.add') : t('admin.save')}
            </Button>
            {!isNew && (
              <Button
                variant="danger"
                icon="trash"
                loading={remove.isPending}
                onHoldConfirm={() => remove.mutate()}
              >
                {t('admin.delete')}
              </Button>
            )}
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-4 p-5">
        {def.fields.map((f) => (
          <Field
            key={f.key}
            def={def}
            field={f}
            isNew={isNew}
            value={values[f.key]}
            options={f.options ? options[f.options] : []}
            onChange={(v) => set(f.key, v)}
          />
        ))}
        {def.kind === 'equipment' && !isNew && <EquipmentQr record={record} />}
        {def.kind === 'equipment' && !isNew && <EquipmentHistory equipmentId={record.id} />}
      </div>
    </Drawer>
  )
}

function Field({
  def,
  field,
  isNew,
  value,
  options,
  onChange,
}: {
  def: KindDef
  field: FieldDef
  isNew: boolean
  value: unknown
  options: { value: string | number; label: string }[]
  onChange: (value: unknown) => void
}) {
  const { t } = useTranslation()
  const label = t(`admin.f.${field.key}` as 'admin.f.name') + (field.required ? ' *' : '')
  const hint = field.hint ? t(`admin.hint.${field.key}` as 'admin.hint.login') : undefined

  if (field.type === 'bool') {
    return (
      <ToggleRow
        checked={Boolean(value)}
        onChange={onChange}
        label={t(`admin.f.${field.key}` as 'admin.f.name')}
        hint={t(`admin.hint.${field.key}` as 'admin.hint.login')}
      />
    )
  }
  if (field.type === 'select') {
    return (
      <FieldShell label={label} hint={hint}>
        {(id, describedBy) => (
          <select
            id={id}
            aria-describedby={describedBy}
            className={SELECT}
            value={value === null || value === undefined ? '' : String(value)}
            onChange={(e) => {
              const raw = e.target.value
              const match = options.find((o) => String(o.value) === raw)
              onChange(raw === '' ? null : match ? match.value : raw)
            }}
          >
            <option value="">{field.required ? t('admin.choose') : t('admin.none')}</option>
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        )}
      </FieldShell>
    )
  }
  if (field.type === 'pin') {
    return (
      <TextField
        label={isNew ? `${t('admin.f.pin')} *` : t('admin.f.newPin')}
        hint={isNew ? t('admin.hint.pin') : t('admin.hint.newPin')}
        inputMode="numeric"
        maxLength={4}
        autoComplete="new-password"
        value={String(value ?? '')}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 4))}
      />
    )
  }
  return (
    <TextField
      label={label}
      hint={hint}
      type={field.type === 'number' ? 'number' : 'text'}
      step={field.type === 'number' ? 'any' : undefined}
      value={value === null || value === undefined ? '' : String(value)}
      disabled={def.kind === 'employees' && field.key === 'login' && !isNew}
      className={cn(field.key === 'inv_number' || field.key === 'code' ? 'cond font-semibold' : undefined)}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

function EquipmentQr({ record }: { record: AdminRecord }) {
  const { t } = useTranslation()
  const code = String(record.qr_code || record.inv_number)
  return (
    <section className="flex items-center gap-4 rounded-[12px] border border-line bg-plate/60 p-4">
      <QrCode
        value={code}
        label={t('admin.qrFor', { inv: record.inv_number })}
        className="size-28 shrink-0 rounded-[6px]"
      />
      <div className="flex flex-col gap-2">
        <p className="text-small text-ink-2">{t('admin.qrHint')}</p>
        <p className="cond font-semibold">{code}</p>
        <Button
          variant="secondary"
          size="sm"
          icon="qr"
          onClick={() => printQr(code, String(record.name), String(record.inv_number))}
        >
          {t('admin.qrPrint')}
        </Button>
      </div>
    </section>
  )
}

/** Печать таблички с QR: открываем отдельное окно с одним SVG и подписью. */
function printQr(code: string, name: string, inv: string) {
  const svg = document.querySelector(`svg[aria-label*="${CSS.escape(inv)}"]`)?.outerHTML ?? ''
  const win = window.open('', '_blank', 'width=420,height=560')
  if (!win) return
  win.document.write(
    `<!doctype html><meta charset="utf-8"><title>${inv}</title>` +
      `<body style="font-family:sans-serif;text-align:center;padding:24px">` +
      `<div style="width:260px;margin:0 auto">${svg}</div>` +
      `<h1 style="font-size:28px;margin:12px 0 4px">${inv}</h1><p style="margin:0">${name}</p>` +
      `<p style="color:#666;font-size:12px">${code}</p></body>`,
  )
  win.document.close()
  win.focus()
  win.print()
}

function initial(def: KindDef, record: AdminRecord | null): Record<string, unknown> {
  if (record) return { ...record, pin: '' }
  const values: Record<string, unknown> = {}
  for (const f of def.fields) values[f.key] = f.type === 'bool' ? f.key === 'is_active' : null
  if (def.kind === 'equipment') values.criticality = 'B'
  if (def.kind === 'employees') values.role = 'worker'
  return values
}

function empty(value: unknown): boolean {
  return value === null || value === undefined || value === ''
}

/** Только поля формы; пустые строки — null; ПИН — только если введён; при изменении — только изменённое. */
function payload(def: KindDef, values: Record<string, unknown>, record: AdminRecord | null) {
  const data: Record<string, unknown> = {}
  for (const f of def.fields) {
    let v = values[f.key]
    if (f.type === 'pin') {
      if (typeof v === 'string' && v.length === 4) data.pin = v
      continue
    }
    if (v === '') v = null
    if (f.type === 'number' && v !== null && v !== undefined) v = Number(v)
    if (f.key === 'login' && typeof v === 'string') v = v.trim().toLowerCase()
    if (!record || record[f.key] !== v) data[f.key] = v
  }
  return data
}
