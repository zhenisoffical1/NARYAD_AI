import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { EquipmentHistory } from '@/features/orders/EquipmentHistory'
import { OrderHeader } from '@/features/orders/OrderHeader'
import { ReasonSheet } from '@/features/orders/ReasonSheet'
import { CANCEL_REASONS } from '@/features/orders/reasons'
import { useOrderAction } from '@/features/orders/useOrderAction'
import type { OrderDetail } from '@/shared/api/types'
import { ddmm, duration, hhmm } from '@/shared/lib/format'
import {
  Button,
  Countdown,
  Fact,
  Panel,
  PhotoCompare,
  PhotoStrip,
  Timeline,
  VerdictCard,
} from '@/shared/ui'

import { OverrideSheet, PrioritySheet, ReassignSheet, ReworkSheet } from './ManageSheets'

type Sheet = 'reassign' | 'priority' | 'override' | 'rework' | 'cancel' | null

const PRE_DONE = ['ISSUED', 'QUEUED', 'ACCEPTED', 'REJECTED', 'IN_PROGRESS', 'PAUSED']

/** Всё о наряде для мастера: содержимое — сверху, решения — в панели действий. */
export function OrderManageBody({ order }: { order: OrderDetail }) {
  const { t } = useTranslation()
  const before = order.photos.filter((p) => p.kind === 'before')
  const after = order.photos.filter((p) => p.kind === 'after')
  const finished = ['DONE', 'AI_REVIEW', 'CLOSED', 'CANCELLED'].includes(order.status)

  return (
    <div className="flex flex-col gap-4">
      <OrderHeader order={order} />

      <Panel>
        <dl>
          <Fact label={t('manage.assignee')}>{order.assignee?.full_name ?? '—'}</Fact>
          <Fact label={t('worker.deadline')}>
            <Countdown deadline={order.deadline_at} stopped={finished} />
          </Fact>
          {order.norm_hours && <Fact label={t('worker.norm')}>{duration(Number(order.norm_hours) * 60)}</Fact>}
          <Fact label={t('manage.created')}>
            {ddmm(order.created_at)} {hhmm(order.created_at)} · {order.master.short_name}
          </Fact>
          {order.downtime_minutes !== null && (
            <Fact label={t('manage.downtime')}>{duration(order.downtime_minutes)}</Fact>
          )}
        </dl>
      </Panel>

      <Panel title={t('worker.problem')}>
        <p className="text-body whitespace-pre-line [overflow-wrap:anywhere]">{order.description}</p>
        {order.comment && <p className="mt-2 border-l-4 border-line pl-3 text-ink-2">{order.comment}</p>}
      </Panel>

      {(before.length > 0 || after.length > 0) && (
        <Panel title={t('manage.photos')}>
          <div className="flex flex-col gap-3">
            {before[0] && after[0] ? (
              <PhotoCompare before={before[0].url} after={after[0].url} />
            ) : null}
            {before.length > 0 && <PhotoStrip photos={before} label={t('ui.before')} />}
            {after.length > 0 && <PhotoStrip photos={after} label={t('ui.after')} />}
          </div>
        </Panel>
      )}

      {order.assessment && <VerdictCard assessment={order.assessment} audience="master" />}

      {order.works_done && (
        <Panel title={t('manage.closure')}>
          <dl>
            <Fact label={t('manage.works')}>
              <span className="whitespace-pre-line">{order.works_done}</span>
            </Fact>
            {order.fault_code && (
              <Fact label={t('manage.faultCode')}>
                {order.fault_code.code} · {order.fault_code.name}
              </Fact>
            )}
            <Fact label={t('manage.materials')}>
              {order.no_materials || order.materials.length === 0 ? (
                t('manage.noMaterials')
              ) : (
                <ul className="flex flex-col gap-0.5">
                  {order.materials.map((m) => (
                    <li key={m.material_id}>
                      {m.name} — <span className="cond font-semibold">{Number(m.quantity).toString().replace('.', ',')} {m.unit}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Fact>
            {order.closing_comment && <Fact label={t('manage.comment')}>{order.closing_comment}</Fact>}
          </dl>
        </Panel>
      )}

      <Panel title={t('worker.progress')}>
        <Timeline events={order.events} />
      </Panel>

      <EquipmentHistory equipmentId={order.equipment.id} currentOrderId={order.id} />
    </div>
  )
}

/** Решения мастера по наряду. Вид кнопок зависит от статуса и прав (actions с сервера). */
export function OrderManageActions({ order, layout = 'stack' }: { order: OrderDetail; layout?: 'stack' | 'row' }) {
  const { t } = useTranslation()
  const [sheet, setSheet] = useState<Sheet>(null)
  const action = useOrderAction(order, () => setSheet(null))
  const can = (a: string) => order.actions.includes(a)
  const preDone = PRE_DONE.includes(order.status)

  const buttons: ReactNode[] = []
  if (can('close')) {
    buttons.push(
      <Button key="close" size={layout === 'stack' ? 'xl' : 'lg'} icon="check" loading={action.isPending && action.variables?.action === 'close'} onClick={() => action.mutate({ action: 'close' })}>
        {t('actions.close')}
      </Button>,
    )
  }
  if (order.status === 'REJECTED' && can('reassign')) {
    buttons.push(
      <Button key="reassign-main" size={layout === 'stack' ? 'xl' : 'lg'} icon="swap" onClick={() => setSheet('reassign')}>
        {t('actions.reassign')}
      </Button>,
    )
  }
  const secondary: ReactNode[] = []
  if (can('send_to_rework')) {
    secondary.push(
      <Button key="rework" variant="secondary" icon="undo" onClick={() => setSheet('rework')}>
        {t('actions.send_to_rework')}
      </Button>,
    )
  }
  if (can('override_assessment')) {
    secondary.push(
      <Button key="override" variant="secondary" icon="edit" onClick={() => setSheet('override')}>
        {t('actions.override_assessment')}
      </Button>,
    )
  }
  if (preDone && order.status !== 'REJECTED' && can('reassign')) {
    secondary.push(
      <Button key="reassign" variant="secondary" icon="swap" onClick={() => setSheet('reassign')}>
        {t('actions.reassign')}
      </Button>,
    )
  }
  if (preDone && can('change_priority')) {
    secondary.push(
      <Button key="priority" variant="secondary" icon="flag" onClick={() => setSheet('priority')}>
        {t('actions.change_priority')}
      </Button>,
    )
  }
  if (preDone && can('cancel')) {
    secondary.push(
      <Button key="cancel" variant="danger" onHoldConfirm={() => setSheet('cancel')}>
        {t('actions.cancel')}
      </Button>,
    )
  }

  if (!buttons.length && !secondary.length) return null

  return (
    <>
      <div className="flex flex-col gap-3">
        {buttons}
        {secondary.length > 0 && (
          // Две в ряд, только если обе подписи помещаются в строку; на телефоне — столбиком на всю ширину.
          <div className="grid grid-cols-[repeat(auto-fit,minmax(13rem,1fr))] gap-3">{secondary}</div>
        )}
      </div>

      {sheet === 'reassign' && <ReassignSheet order={order} onClose={() => setSheet(null)} />}
      {sheet === 'priority' && <PrioritySheet order={order} onClose={() => setSheet(null)} />}
      {sheet === 'override' && <OverrideSheet order={order} onClose={() => setSheet(null)} />}
      {sheet === 'rework' && (
        <ReworkSheet
          order={order}
          busy={action.isPending}
          onClose={() => setSheet(null)}
          onSubmit={(text) => action.mutate({ action: 'send_to_rework', reason: text.slice(0, 200), comment: text })}
        />
      )}
      <ReasonSheet
        open={sheet === 'cancel'}
        title={t('reasons.cancelTitle')}
        reasons={CANCEL_REASONS}
        busy={action.isPending}
        onClose={() => setSheet(null)}
        onSubmit={(reason) => action.mutate({ action: 'cancel', reason })}
      />
    </>
  )
}
