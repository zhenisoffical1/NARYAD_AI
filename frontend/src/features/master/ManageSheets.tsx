import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  changePriority,
  fetchAssist,
  orderKeys,
  overrideAssessment,
  reassignOrder,
} from '@/shared/api/orders'
import type { OrderDetail, Priority } from '@/shared/api/types'
import { toast } from '@/shared/lib/toast'
import { BottomSheet, Button, PersonStatusRow, PriorityPicker, Stepper, TextArea } from '@/shared/ui'

function useRefresh(order: OrderDetail) {
  const queryClient = useQueryClient()
  return (detail: OrderDetail) => {
    queryClient.setQueryData(orderKeys.detail(order.id), detail)
    void queryClient.invalidateQueries({ queryKey: ['orders'] })
    void queryClient.invalidateQueries({ queryKey: ['shift'] })
  }
}

/** Переназначение: кандидаты от ИИ с объяснением, текущий исполнитель исключён. */
export function ReassignSheet({ order, onClose }: { order: OrderDetail; onClose: () => void }) {
  const { t } = useTranslation()
  const refresh = useRefresh(order)
  const assist = useQuery({
    queryKey: ['assist', order.equipment.id, order.description, order.priority],
    queryFn: () =>
      fetchAssist({ equipment_id: order.equipment.id, description: order.description, priority: order.priority }),
  })
  const mutation = useMutation({
    mutationFn: (assigneeId: number) => reassignOrder(order.id, assigneeId),
    onSuccess: (detail) => {
      refresh(detail)
      toast(t('done.reassign', { n: order.number, name: detail.assignee?.short_name ?? '' }))
      onClose()
    },
    onError: (e) => toast(e.message, 'error'),
  })
  const candidates = (assist.data?.candidates ?? []).filter(
    (c) => c.person.employee.id !== order.assignee?.id,
  )

  return (
    <BottomSheet open title={t('manage.reassignTitle')} onClose={onClose}>
      {assist.isPending && <p className="py-4 text-ink-3">{t('issue.candidatesLoading')}</p>}
      <div className="divide-y divide-line">
        {candidates.map((c) => (
          <PersonStatusRow
            key={c.person.employee.id}
            name={c.person.employee.full_name}
            specialty={c.recommended ? undefined : c.specialty}
            state={c.person.state}
            orderNumber={c.person.current_order?.number}
            queueCount={c.person.queue_count}
            recommendation={c.recommended ? c.reason : undefined}
            onClick={() => mutation.mutate(c.person.employee.id)}
          />
        ))}
      </div>
    </BottomSheet>
  )
}

export function PrioritySheet({ order, onClose }: { order: OrderDetail; onClose: () => void }) {
  const { t } = useTranslation()
  const refresh = useRefresh(order)
  const mutation = useMutation({
    mutationFn: (priority: Priority) => changePriority(order.id, priority),
    onSuccess: (detail) => {
      refresh(detail)
      toast(t('done.priority', { n: order.number, p: t(`priority.${detail.priority}`) }))
      onClose()
    },
    onError: (e) => toast(e.message, 'error'),
  })
  return (
    <BottomSheet open title={t('manage.priorityTitle')} onClose={onClose}>
      <PriorityPicker
        label=""
        value={order.priority}
        onChange={(p) => p !== order.priority && mutation.mutate(p)}
      />
    </BottomSheet>
  )
}

export function OverrideSheet({ order, onClose }: { order: OrderDetail; onClose: () => void }) {
  const { t } = useTranslation()
  const refresh = useRefresh(order)
  const current = order.assessment?.final_score ?? order.assessment?.score_0_100 ?? 80
  const [score, setScore] = useState(current)
  const [comment, setComment] = useState('')
  const mutation = useMutation({
    mutationFn: () => overrideAssessment(order.id, score, comment.trim()),
    onSuccess: (detail) => {
      refresh(detail)
      toast(t('done.override', { n: order.number, score }))
      onClose()
    },
    onError: (e) => toast(e.message, 'error'),
  })
  return (
    <BottomSheet
      open
      title={t('manage.overrideTitle')}
      onClose={onClose}
      footer={
        <Button block size="lg" disabled={comment.trim().length < 3} loading={mutation.isPending} onClick={() => mutation.mutate()}>
          {t('common.save')}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-small font-semibold text-ink-2">{t('manage.score')}</span>
          <Stepper label={t('manage.score')} unit={t('verdict.score')} value={score} onChange={setScore} step={5} min={0} max={100} />
        </div>
        <TextArea
          label={t('manage.overrideComment')}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
          autoFocus
        />
      </div>
    </BottomSheet>
  )
}

const REWORK_CHIPS = ['chipNoPhoto', 'chipMess', 'chipNotFixed', 'chipOveruse'] as const

/** Возврат на доработку: что именно исправить — исполнитель увидит это первым на экране наряда. */
export function ReworkSheet({
  order,
  onClose,
  onSubmit,
  busy,
}: {
  order: OrderDetail
  onClose: () => void
  onSubmit: (text: string) => void
  busy: boolean
}) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  return (
    <BottomSheet
      open
      title={t('manage.reworkTitle')}
      onClose={onClose}
      footer={
        <Button block size="lg" variant="danger" disabled={text.trim().length < 3} loading={busy} onClick={() => onSubmit(text.trim())}>
          {t('actions.send_to_rework')}
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-small text-ink-2">{t('manage.order', { n: order.number })} · {order.assignee?.short_name}</p>
        <div className="flex flex-wrap gap-2">
          {REWORK_CHIPS.map((key) => t(`manage.${key}`)).map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => setText((prev) => (prev ? `${prev}; ${chip.toLowerCase()}` : chip))}
              className="min-h-11 rounded-control border-2 border-line bg-surface px-3 text-small font-medium active:bg-plate"
            >
              {chip}
            </button>
          ))}
        </div>
        <TextArea
          label={t('manage.reworkTitle')}
          labelHidden
          placeholder={t('manage.reworkPlaceholder')}
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
        />
      </div>
    </BottomSheet>
  )
}
