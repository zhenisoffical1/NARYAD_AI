import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { OrderHeader } from '@/features/orders/OrderHeader'
import { ReasonSheet } from '@/features/orders/ReasonSheet'
import { PAUSE_REASONS, REJECT_REASONS } from '@/features/orders/reasons'
import { useOrderAction } from '@/features/orders/useOrderAction'
import { fetchOrder, orderKeys } from '@/shared/api/orders'
import type { OrderDetail } from '@/shared/api/types'
import { duration } from '@/shared/lib/format'
import {
  ActionBar,
  Button,
  Countdown,
  Fact,
  Panel,
  PhotoStrip,
  TagSkeleton,
  Timeline,
  TopBar,
  VerdictCard,
} from '@/shared/ui'

const PRIMARY = ['accept', 'start', 'complete', 'resume', 'resume_rework'] as const

/** Карточка наряда у исполнителя: всё о работе и одна главная кнопка следующего шага внизу. */
export function WorkerOrderPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const orderId = Number(useParams().id)
  const detail = useQuery({ queryKey: orderKeys.detail(orderId), queryFn: () => fetchOrder(orderId) })
  const order = detail.data

  return (
    <div className="flex min-h-dvh flex-col bg-bg">
      <TopBar
        title={order ? t('manage.order', { n: order.number }) : '…'}
        subtitle={order ? t(`status.${order.status}`) : undefined}
        onBack={() => navigate('/w')}
      />
      {!order ? (
        <main className="flex flex-col gap-3 p-4">
          <TagSkeleton />
        </main>
      ) : (
        <OrderBody order={order} />
      )}
    </div>
  )
}

function OrderBody({ order }: { order: OrderDetail }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const action = useOrderAction(order)
  const [sheet, setSheet] = useState<'reject' | 'pause' | null>(null)
  const can = (a: string) => order.actions.includes(a)
  const primary = PRIMARY.find(can)
  const before = order.photos.filter((p) => p.kind === 'before')
  const after = order.photos.filter((p) => p.kind === 'after')
  const reworkReason = [...order.events].reverse().find((e) => e.action === 'send_to_rework')?.reason
  const reviewStatuses = ['DONE', 'AI_REVIEW', 'CLOSED']

  const runPrimary = () => {
    if (primary === 'complete') navigate(`/w/orders/${order.id}/close`)
    else if (primary) action.mutate({ action: primary })
  }

  return (
    <>
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-4 px-4 pt-4 pb-6">
        <OrderHeader order={order} />

        {order.status === 'REWORK' && (
          <section className="rounded-[12px] border-2 border-red bg-red-soft p-4">
            <p className="text-h2 font-semibold text-red">{t('worker.reworkTitle')}</p>
            <p className="mt-1 [overflow-wrap:anywhere]">{reworkReason ?? t('worker.reworkHint')}</p>
          </section>
        )}

        <Panel title={t('worker.problem')}>
          <p className="text-body-lg whitespace-pre-line [overflow-wrap:anywhere]">{order.description}</p>
          {order.comment && (
            <p className="mt-3 border-l-4 border-line pl-3 text-ink-2">
              <span className="block text-small font-semibold">{t('worker.masterComment')}</span>
              {order.comment}
            </p>
          )}
          {before.length > 0 && (
            <div className="mt-4">
              <PhotoStrip photos={before} label={t('worker.beforePhotos')} />
            </div>
          )}
        </Panel>

        <Panel>
          <dl>
            <Fact label={t('worker.deadline')}>
              <Countdown deadline={order.deadline_at} stopped={reviewStatuses.includes(order.status) || order.status === 'CANCELLED'} />
            </Fact>
            {order.norm_hours && (
              <Fact label={t('worker.norm')}>{duration(Number(order.norm_hours) * 60)}</Fact>
            )}
            <Fact label={t('worker.master')}>{order.master.short_name}</Fact>
          </dl>
        </Panel>

        {reviewStatuses.includes(order.status) || order.status === 'REWORK' ? (
          <>
            {order.assessment ? (
              <VerdictCard assessment={order.assessment} audience="worker" />
            ) : (
              <Button variant="secondary" block icon="spark" onClick={() => navigate(`/w/orders/${order.id}/result`)}>
                {t('worker.checking')}
              </Button>
            )}
            {order.status === 'AI_REVIEW' && order.assessment?.status === 'done' && (
              <p className="text-center text-small text-ink-3">{t('worker.waitingMaster')}</p>
            )}
            {after.length > 0 && (
              <Panel>
                <PhotoStrip photos={after} label={t('close.photosAfter')} />
              </Panel>
            )}
          </>
        ) : null}

        <Panel title={t('worker.progress')}>
          <Timeline events={order.events} />
        </Panel>
      </main>

      {(primary || can('queue') || can('pause') || can('reject')) && (
        <ActionBar>
          {primary && (
            <Button size="xl" block loading={action.isPending} onClick={runPrimary}>
              {t(`actions.${primary}`)}
            </Button>
          )}
          {(can('queue') || can('pause') || can('reject')) && (
            <div className="grid auto-cols-fr grid-flow-col gap-4">
              {can('queue') && order.priority !== 'emergency' && (
                <Button variant="secondary" disabled={action.isPending} onClick={() => action.mutate({ action: 'queue' })}>
                  {t('actions.queue')}
                </Button>
              )}
              {can('pause') && (
                <Button variant="secondary" icon="pause" disabled={action.isPending} onClick={() => setSheet('pause')}>
                  {t('actions.pause')}
                </Button>
              )}
              {can('reject') && (
                <Button variant="danger" disabled={action.isPending} onHoldConfirm={() => setSheet('reject')}>
                  {t('actions.reject')}
                </Button>
              )}
            </div>
          )}
        </ActionBar>
      )}

      <ReasonSheet
        open={sheet !== null}
        title={sheet === 'pause' ? t('reasons.pauseTitle') : t('reasons.rejectTitle')}
        reasons={sheet === 'pause' ? PAUSE_REASONS : REJECT_REASONS}
        busy={action.isPending}
        onClose={() => setSheet(null)}
        onSubmit={(reason) =>
          action.mutate(
            { action: sheet === 'pause' ? 'pause' : 'reject', reason },
            {
              onSuccess: () => {
                setSheet(null)
                if (sheet === 'reject') navigate('/w')
              },
            },
          )
        }
      />
    </>
  )
}
