import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { createOrder, fetchAssist, uploadPhotos } from '@/shared/api/orders'
import { fetchBrigades, fetchFaultCodes, REFERENCE_STALE, refKeys } from '@/shared/api/reference'
import type { Equipment, OrderDetail, OrderType, Priority } from '@/shared/api/types'
import { cn, hhmm } from '@/shared/lib/format'
import type { PickedPhoto } from '@/shared/lib/photos'
import { toast } from '@/shared/lib/toast'
import { useNow } from '@/shared/lib/useNow'
import { useSpeech } from '@/shared/lib/useSpeech'
import {
  BottomSheet,
  Button,
  Icon,
  PersonStatusRow,
  PhotoPicker,
  PriorityPicker,
  Select,
  Tabs,
  TextArea,
  ToggleRow,
} from '@/shared/ui'

import { EquipmentPicker } from './EquipmentPicker'

const SHOWN_CANDIDATES = 4
const DAY_START = 8
const NIGHT_START = 20

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), ms)
    return () => window.clearTimeout(timer)
  }, [value, ms])
  return debounced
}

function endOfShift(now: number): Date {
  const date = new Date(now)
  const hour = date.getHours()
  const end = new Date(date)
  if (hour >= DAY_START && hour < NIGHT_START) end.setHours(NIGHT_START, 0, 0, 0)
  else {
    if (hour >= NIGHT_START) end.setDate(end.getDate() + 1)
    end.setHours(DAY_START, 0, 0, 0)
  }
  return end
}

/**
 * Выдача наряда. Самый короткий путь — 5 нажатий: описание голосом, оборудование из недавних,
 * приоритет, исполнитель (рекомендация ИИ уже выбрана) и «Выдать». Остальное подставляется само.
 */
export function IssueOrderForm({ onIssued }: { onIssued: (order: OrderDetail) => void }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const now = useNow(60_000)
  const [photos, setPhotos] = useState<PickedPhoto[]>([])
  const [description, setDescription] = useState('')
  const [equipment, setEquipment] = useState<Equipment | null>(null)
  const [priority, setPriority] = useState<Priority | null>(null)
  const [assigneeId, setAssigneeId] = useState<number | null>(null)
  const [touched, setTouched] = useState(false)
  const [brigadeId, setBrigadeId] = useState<number | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [details, setDetails] = useState(false)
  const [typeOverride, setTypeOverride] = useState<OrderType | null>(null)
  const [deadlineOverride, setDeadlineOverride] = useState<Date | null>(null)
  const [stoppedOverride, setStoppedOverride] = useState<boolean | null>(null)
  const [faultId, setFaultId] = useState<number | null | undefined>(undefined)
  const [comment, setComment] = useState('')
  const [showMissing, setShowMissing] = useState(false)

  const speech = useSpeech(i18n.language, (text) =>
    setDescription((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text)),
  )
  const debouncedDescription = useDebounced(description.trim(), 600)

  const assist = useQuery({
    queryKey: ['assist', equipment?.id, debouncedDescription, priority],
    queryFn: () =>
      equipment
        ? fetchAssist({ equipment_id: equipment.id, description: debouncedDescription, priority })
        : Promise.reject(new Error('no equipment')),
    enabled: equipment !== null,
    staleTime: 30_000,
  })
  const codes = useQuery({ queryKey: refKeys.faultCodes, queryFn: fetchFaultCodes, staleTime: REFERENCE_STALE })
  const brigades = useQuery({ queryKey: refKeys.brigades, queryFn: fetchBrigades, staleTime: REFERENCE_STALE })

  // Рекомендация ИИ выбрана сама, пока мастер не выбрал другого — экономит нажатие
  const recommended = assist.data?.candidates.find((c) => c.recommended)
  const selectedId = touched ? assigneeId : (recommended?.person.employee.id ?? null)

  const suggestion = assist.data?.fault_code ?? null
  const chosenFault = faultId === undefined ? suggestion?.id ?? null : faultId
  const orderType: OrderType =
    typeOverride ?? (priority === 'planned' ? 'planned' : assist.data?.order_type ?? 'unplanned')
  const autoDeadline = new Date(now + (assist.data?.deadline_hours ?? 4) * 3_600_000)
  const deadline = deadlineOverride ?? autoDeadline
  const stopped = stoppedOverride ?? priority === 'emergency'

  const candidates = assist.data?.candidates ?? []
  const visible = showAll ? candidates : candidates.slice(0, SHOWN_CANDIDATES)
  const chosen = candidates.find((c) => c.person.employee.id === selectedId)

  const missing = [
    description.trim().length < 3 && t('issue.missingDescription'),
    !equipment && t('issue.missingEquipment'),
    !priority && t('issue.missingPriority'),
    !selectedId && !brigadeId && t('issue.missingAssignee'),
  ].filter(Boolean) as string[]

  const submit = useMutation({
    mutationFn: async () => {
      if (!equipment || !priority) throw new Error(t('issue.missing', { what: missing.join(', ') }))
      const order = await createOrder({
        description: description.trim(),
        equipment_id: equipment.id,
        priority,
        assignee_id: brigadeId ? null : selectedId,
        brigade_id: brigadeId,
        type: typeOverride,
        deadline_at: deadlineOverride ? deadlineOverride.toISOString() : null,
        fault_code_id: chosenFault,
        equipment_stopped: stoppedOverride,
        comment: comment.trim() || null,
      })
      if (photos.length) await uploadPhotos(order.id, 'before', photos.map((p) => p.file))
      return order
    },
    onSuccess: (order) => {
      navigator.vibrate?.(40)
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: ['shift'] })
      void queryClient.invalidateQueries({ queryKey: refKeys.recentEquipment })
      const name = order.assignee?.short_name ?? brigades.data?.find((b) => b.id === brigadeId)?.name ?? ''
      toast(t('done.issued', { n: order.number, name }))
      onIssued(order)
    },
    onError: (error) => toast(error.message, 'error'),
  })

  const onSubmit = () => {
    if (missing.length) {
      setShowMissing(true)
      navigator.vibrate?.([40, 60, 40])
      return
    }
    submit.mutate()
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-1 flex-col gap-6 px-4 pt-4 pb-6">
        <Step n={1} title={t('issue.photo')} optional>
          <PhotoPicker label="" value={photos} onChange={setPhotos} />
        </Step>

        <Step n={2} title={t('issue.description')}>
          <TextArea
            label={t('issue.description')}
            labelHidden
            placeholder={t('issue.descriptionPlaceholder')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            error={showMissing && description.trim().length < 3 ? t('issue.missingDescription') : null}
            action={
              speech.supported ? (
                <Button
                  size="sm"
                  variant={speech.listening ? 'primary' : 'quiet'}
                  icon="mic"
                  onClick={speech.listening ? speech.stop : speech.start}
                >
                  {speech.listening ? t('close.listening') : t('close.voice')}
                </Button>
              ) : undefined
            }
          />
        </Step>

        <Step n={3} title={t('issue.equipment')}>
          <EquipmentPicker
            value={equipment}
            onChange={(eq) => {
              setEquipment(eq)
              setTouched(false)
              setFaultId(undefined)
            }}
            error={showMissing && !equipment ? t('issue.missingEquipment') : null}
          />
        </Step>

        <Step n={4} title={t('issue.priority')}>
          <PriorityPicker label="" value={priority} onChange={setPriority} />
          {showMissing && !priority && (
            <p className="mt-1.5 text-small font-medium text-red">{t('issue.missingPriority')}</p>
          )}
          {equipment && priority && (
            <button
              type="button"
              onClick={() => setDetails(true)}
              className="mt-3 flex w-full items-center justify-between gap-3 rounded-control bg-plate px-3 py-2.5 text-left text-small"
            >
              <span className="min-w-0">
                <span className="block font-medium">
                  {t('issue.summary', {
                    type: orderType === 'planned' ? t('issue.planned') : t('issue.unplanned'),
                    time: hhmm(deadline),
                  })}
                </span>
                {suggestion && faultId === undefined && (
                  <span className="block text-ink-2">{t('issue.faultSuggested', { code: suggestion.code })}</span>
                )}
                {stopped && <span className="block text-red">{t('issue.stopped')}</span>}
              </span>
              <span className="shrink-0 font-semibold text-accent">{t('issue.change')}</span>
            </button>
          )}
        </Step>

        <Step n={5} title={t('issue.assignee')}>
          {!equipment && <p className="text-small text-ink-3">{t('issue.pickEquipmentFirst')}</p>}
          {equipment && assist.isPending && <p className="text-small text-ink-3">{t('issue.candidatesLoading')}</p>}
          {brigadeId === null && candidates.length > 0 && (
            <div className="divide-y divide-line rounded-[8px] border border-line bg-surface px-1">
              {visible.map((c) => (
                <PersonStatusRow
                  key={c.person.employee.id}
                  name={c.person.employee.full_name}
                  specialty={c.recommended ? undefined : c.specialty}
                  state={c.person.state}
                  orderNumber={c.person.current_order?.number}
                  queueCount={c.person.queue_count}
                  recommendation={c.recommended ? c.reason : undefined}
                  selected={c.person.employee.id === selectedId}
                  onClick={() => {
                    setTouched(true)
                    setAssigneeId(c.person.employee.id)
                  }}
                />
              ))}
            </div>
          )}
          {brigadeId === null && candidates.length > SHOWN_CANDIDATES && !showAll && (
            <Button variant="quiet" size="md" className="mt-1" onClick={() => setShowAll(true)}>
              {t('issue.showAll', { n: candidates.length })}
            </Button>
          )}
          {equipment && brigades.data && (
            <div className="mt-3">
              {brigadeId === null ? (
                <Button variant="quiet" size="md" icon="user" onClick={() => setBrigadeId(brigades.data[0]?.id ?? null)}>
                  {t('issue.brigade')}
                </Button>
              ) : (
                <div className="flex flex-col gap-2">
                  <Select
                    label={t('issue.brigade')}
                    value={brigadeId}
                    onChange={setBrigadeId}
                    options={brigades.data.map((b) => ({ value: b.id, label: b.name }))}
                  />
                  <p className="text-small text-ink-3">{t('issue.brigadeHint')}</p>
                  <Button variant="quiet" size="md" onClick={() => setBrigadeId(null)}>
                    {t('issue.assignee')}
                  </Button>
                </div>
              )}
            </div>
          )}
          {showMissing && !selectedId && !brigadeId && equipment && (
            <p className="mt-1.5 text-small font-medium text-red">{t('issue.missingAssignee')}</p>
          )}
        </Step>
      </div>

      <div className="sticky bottom-0 z-20 flex flex-col gap-2 border-t border-line bg-surface/95 px-4 pt-3 pb-[max(12px,env(safe-area-inset-bottom))] backdrop-blur-sm">
        {missing.length > 0 && (
          <p className={cn('text-center text-small', showMissing ? 'font-medium text-red' : 'text-ink-3')}>
            {t('issue.missing', { what: missing.join(', ') })}
          </p>
        )}
        {missing.length === 0 && chosen && (
          <p className="text-center text-small text-ink-2">
            {chosen.person.employee.short_name} · {t('issue.summary', {
              type: orderType === 'planned' ? t('issue.planned') : t('issue.unplanned'),
              time: hhmm(deadline),
            })}
          </p>
        )}
        <Button size="xl" block icon="send" loading={submit.isPending} onClick={onSubmit}>
          {t('issue.submit')}
        </Button>
      </div>

      <BottomSheet
        open={details}
        title={t('issue.details')}
        onClose={() => setDetails(false)}
        footer={
          <Button block size="lg" onClick={() => setDetails(false)}>
            {t('issue.done')}
          </Button>
        }
      >
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <p className="text-small font-semibold text-ink-2">{t('issue.deadline')}</p>
            <p className="text-small text-ink-3">
              {t('issue.deadlineAuto', { h: (assist.data?.deadline_hours ?? 4).toString().replace('.', ',') })}
            </p>
            <div className="flex flex-wrap gap-2">
              <Chip active={deadlineOverride === null} onClick={() => setDeadlineOverride(null)}>
                {hhmm(autoDeadline)}
              </Chip>
              {[1, 2, 4, 8].map((h) => (
                <Chip key={h} onClick={() => setDeadlineOverride(new Date(now + h * 3_600_000))}>
                  {t('issue.plusHours', { h })}
                </Chip>
              ))}
              <Chip onClick={() => setDeadlineOverride(endOfShift(now))}>{t('issue.endOfShift')}</Chip>
            </div>
            {deadlineOverride && (
              <p className="text-small font-medium">
                <Icon name="clock" size={16} className="mr-1 inline" />
                {hhmm(deadlineOverride)}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <p className="text-small font-semibold text-ink-2">{t('issue.type')}</p>
            <Tabs<OrderType>
              label={t('issue.type')}
              value={orderType}
              onChange={setTypeOverride}
              items={[
                { value: 'unplanned', label: t('issue.unplanned') },
                { value: 'planned', label: t('issue.planned') },
              ]}
            />
          </div>
          <ToggleRow
            checked={stopped}
            onChange={setStoppedOverride}
            label={t('issue.stopped')}
            hint={t('issue.stoppedHint')}
          />
          {codes.data && (
            <Select
              label={t('close.code')}
              value={chosenFault}
              onChange={setFaultId}
              searchable
              options={codes.data.map((c) => ({ value: c.id, label: `${c.code} · ${c.name}` }))}
            />
          )}
          <TextArea
            label={t('issue.comment')}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
          />
        </div>
      </BottomSheet>
    </div>
  )
}

function Step({
  n,
  title,
  optional = false,
  children,
}: {
  n: number
  title: string
  optional?: boolean
  children: ReactNode
}) {
  const { t } = useTranslation()
  return (
    <section className="flex flex-col gap-2.5">
      <h2 className="flex items-center gap-2.5 text-body font-semibold">
        <span className="cond inline-flex size-7 items-center justify-center rounded-[4px] bg-bar text-small text-on-bar">
          {n}
        </span>
        {title}
        {optional && <span className="text-small font-normal text-ink-3">· {t('issue.optional')}</span>}
      </h2>
      {children}
    </section>
  )
}

function Chip({
  active = false,
  onClick,
  children,
}: {
  active?: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'cond min-h-11 rounded-control border-2 px-3 font-semibold',
        active ? 'border-accent bg-queue-soft text-accent' : 'border-line bg-surface',
      )}
    >
      {children}
    </button>
  )
}
