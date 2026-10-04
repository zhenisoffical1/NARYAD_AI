import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { NotificationsBell } from '@/features/orders/NotificationsBell'
import { fetchMyRating, ratingKeys } from '@/shared/api/reference'
import type { RatingComponent } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'
import { EmptyState, Icon, Panel, Skeleton, Tabs, TopBar } from '@/shared/ui'

type Period = '7' | '30' | '90'

/** «Мой рейтинг»: итог, место, из чего сложился и что поднимет его сильнее всего. */
export function RatingPage() {
  const { t } = useTranslation()
  const [period, setPeriod] = useState<Period>('30')
  const days = Number(period)
  const rating = useQuery({ queryKey: ratingKeys.mine(days), queryFn: () => fetchMyRating(days) })
  const data = rating.data

  return (
    <>
      <TopBar
        title={t('rating.title')}
        subtitle={t('rating.period', { days })}
        right={<NotificationsBell />}
      />
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-4 px-4 pt-4 pb-8">
        <Tabs<Period>
          label={t('rating.title')}
          value={period}
          onChange={setPeriod}
          items={[
            { value: '7', label: t('rating.days7') },
            { value: '30', label: t('rating.days30') },
            { value: '90', label: t('rating.days90') },
          ]}
        />

        {rating.isPending && <Skeleton className="h-40 w-full" />}

        {data && data.score === null && (
          <EmptyState icon="chart" title={t('rating.insufficient')} hint={data.explanation} />
        )}

        {data && data.score !== null && (
          <>
            <section className="flex items-end justify-between gap-4 rounded-[8px] border border-line bg-surface px-5 py-5">
              <div>
                <p className="text-small text-ink-3">{t('rating.orders', { n: data.orders })}</p>
                {data.rank && (
                  <p className="mt-1 text-h2 font-semibold">
                    {t('rating.rank', { rank: data.rank, total: data.total_rated })}
                  </p>
                )}
              </div>
              <p className="flex items-baseline gap-1">
                <span className="cond text-[64px] leading-none font-bold text-accent">
                  {Math.round(data.score)}
                </span>
                <span className="text-ink-2">{t('verdict.score')}</span>
              </p>
            </section>

            <Panel title={t('rating.explanation')}>
              <p className="flex gap-3 text-body">
                <Icon name="spark" className="mt-0.5 shrink-0 text-accent" />
                <span className="[overflow-wrap:anywhere]">{data.explanation}</span>
              </p>
            </Panel>

            <Panel title={t('rating.components')}>
              <ul className="flex flex-col gap-4">
                {data.components.map((c) => (
                  <ComponentRow key={c.key} component={c} />
                ))}
              </ul>
            </Panel>
          </>
        )}
      </main>
    </>
  )
}

function ComponentRow({ component: c }: { component: RatingComponent }) {
  const { t } = useTranslation()
  const pct = Math.round(c.value * 100)
  const weight = Math.round(c.weight * 100)
  return (
    <li className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-medium">{c.label}</span>
        <span className="cond shrink-0 text-small text-ink-2">
          {t('rating.points', { p: c.points.toString().replace('.', ','), w: weight })}
        </span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-plate" aria-hidden>
        <div
          className={cn('h-full rounded-full', pct >= 85 ? 'bg-green' : pct >= 65 ? 'bg-accent' : 'bg-red')}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-small text-ink-2">{c.detail}</p>
    </li>
  )
}
