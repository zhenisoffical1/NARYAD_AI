import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { fetchOrder, orderKeys } from '@/shared/api/orders'
import type { OrderDetail } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'
import { useLiveEvent } from '@/shared/lib/useLiveEvents'
import { ActionBar, Button, TopBar, VerdictCard } from '@/shared/ui'

const STEPS = ['completeness', 'time', 'materials', 'works_match', 'photos']
const STEP_MS = 380 // каждый шаг виден хотя бы мгновение, даже если проверка уже готова

/** После «Исполнено»: прогресс проверки ИИ по шагам, затем отчёт исполнителю. */
export function ResultPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const orderId = Number(useParams().id)
  const detail = useQuery({
    queryKey: orderKeys.detail(orderId),
    queryFn: () => fetchOrder(orderId),
    // Подстраховка к WebSocket: пока проверка идёт, спрашиваем раз в 1,5 с
    refetchInterval: (query) => (isFinished(query.state.data) ? false : 1500),
  })
  const order = detail.data
  const shown = useStagedSteps(orderId, isFinished(order))
  const finished = isFinished(order) && shown.length === STEPS.length

  return (
    <div className="flex min-h-dvh flex-col bg-bg">
      <TopBar
        title={finished ? t('worker.reportTitle') : t('worker.checking')}
        subtitle={order ? t('manage.order', { n: order.number }) : undefined}
        onBack={() => navigate('/w')}
      />
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-4 px-4 pt-4 pb-6">
        {!finished || !order?.assessment ? (
          <>
            <VerdictCard assessment={null} audience="worker" progress={shown} />
            <p className="text-center text-small text-ink-3">{t('worker.checkingHint')}</p>
          </>
        ) : (
          <>
            <ScorePlate order={order} />
            <VerdictCard assessment={order.assessment} audience="worker" />
          </>
        )}
      </main>
      {finished && order && (
        <ActionBar>
          {order.status === 'REWORK' ? (
            <Button size="xl" block onClick={() => navigate(`/w/orders/${order.id}`)}>
              {t('worker.openOrder')}
            </Button>
          ) : (
            <Button size="xl" block onClick={() => navigate('/w')}>
              {t('worker.toOrders')}
            </Button>
          )}
        </ActionBar>
      )}
    </div>
  )
}

function isFinished(order: OrderDetail | undefined): boolean {
  return Boolean(order?.assessment && order.assessment.status !== 'running')
}

/** Шаги, пройденные проверкой: из живых событий, с минимальной паузой между ними. */
function useStagedSteps(orderId: number, finished: boolean): string[] {
  const [shown, setShown] = useState<string[]>([])
  const queue = useRef<string[]>([])

  useLiveEvent('assessment.progress', (message) => {
    if (message.payload.order_id !== orderId) return
    const step = String(message.payload.step)
    if (!queue.current.includes(step)) queue.current.push(step)
  })

  useEffect(() => {
    if (finished) {
      // Проверка готова — догоняем оставшиеся шаги
      for (const step of STEPS) if (!queue.current.includes(step)) queue.current.push(step)
    }
    const timer = window.setInterval(() => {
      setShown((prev) => {
        const next = queue.current.find((s) => !prev.includes(s))
        return next ? [...prev, next] : prev
      })
    }, STEP_MS)
    return () => window.clearInterval(timer)
  }, [finished])

  return shown
}

function ScorePlate({ order }: { order: OrderDetail }) {
  const { t } = useTranslation()
  const a = order.assessment
  if (!a) return null
  const score = a.final_score ?? a.score_0_100
  const verdict = a.verdict ?? 'review'
  return (
    <section
      className={cn(
        'flex items-center justify-between gap-4 rounded-[8px] border-2 bg-surface px-5 py-4',
        verdict === 'rework' ? 'border-red' : verdict === 'review' ? 'border-accent' : 'border-green',
      )}
    >
      <div>
        <p className="stamp text-ink-3">{t('manage.order', { n: order.number })}</p>
        <p className={cn('mt-1 text-h2 font-semibold', verdict === 'rework' && 'text-red')}>
          {t(`verdict.${verdict}`)}
        </p>
      </div>
      {score !== null && (
        <p className="flex items-baseline gap-1">
          <span className="cond text-[56px] leading-none font-bold">{score}</span>
          <span className="text-ink-2">{t('verdict.score')}</span>
        </p>
      )}
    </section>
  )
}
