import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { analyticsKeys, dashboardKeys, fetchAnalytics, fetchDashboard } from '@/shared/api/insights'
import { cn } from '@/shared/lib/format'
import { BarList, ColumnChart, Counter, CounterBoard, Icon, Panel, Skeleton } from '@/shared/ui'

import { DeskHeader, PeriodPicker } from './DeskHeader'
import { InsightCard } from './InsightCard'
import { SectionFilter } from './filters'
import { useDays } from './useDays'

function num(value: number, digits = 1): string {
  return value.toFixed(digits).replace(/\.0+$/, '').replace('.', ',')
}

/** Обзор руководителя: состояние сейчас и итоги периода на одном экране. */
export function BossPage() {
  const { t } = useTranslation()
  const [days, setDays, dayOptions] = useDays(30)
  const [section, setSection] = useState<number | null>(null)
  const dashboard = useQuery({
    queryKey: dashboardKeys.get(days, section),
    queryFn: () => fetchDashboard(days, section),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  })
  const insights = useQuery({
    queryKey: analyticsKeys.list(90, section),
    queryFn: () => fetchAnalytics(90, section),
    staleTime: 5 * 60_000,
  })
  const d = dashboard.data
  const reaction = d?.reaction_minutes
  const completion = d?.completion_hours

  return (
    <div className="flex min-h-dvh flex-col bg-bg text-ink">
      <DeskHeader title={t('boss.title')} subtitle={t('boss.period', { days })} />

      <main
        className={cn(
          'mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-5 py-4 transition-opacity',
          dashboard.isPlaceholderData && 'opacity-60',
        )}
      >
        <div className="flex flex-wrap items-end gap-3">
          <PeriodPicker value={days} onChange={setDays} options={dayOptions} label={t('desk.period')} />
          <SectionFilter value={section} onChange={setSection} />
        </div>

        {!d ? (
          <Skeleton className="h-28" />
        ) : (
          <CounterBoard className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6">
            <Counter label={t('boss.inWork')} value={d.in_work} />
            <Counter label={t('boss.overdueNow')} value={d.overdue_now} alert={d.overdue_now > 0} />
            <Counter
              label={t('boss.reaction')}
              value={reaction == null ? '—' : `${num(reaction, 0)} ${t('boss.min')}`}
              hint={t('boss.reactionHint')}
            />
            <Counter
              label={t('boss.completion')}
              value={completion == null ? '—' : `${num(completion)} ${t('boss.hours')}`}
              hint={t('boss.completionHint')}
            />
            <Counter
              label={t('boss.downtime')}
              value={`${num(d.downtime_hours, 0)} ${t('boss.hours')}`}
              alert={d.downtime_hours > 0}
              hint={t('boss.downtimeHint')}
            />
            <Counter
              label={t('boss.lateShare')}
              value={`${Math.round(d.overdue_share * 100)}%`}
              alert={d.overdue_share > 0.15}
              hint={`${t('boss.issued')}: ${d.issued}`}
            />
          </CounterBoard>
        )}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <Panel title={t('boss.trend')}>
            {d ? (
              <ColumnChart
                data={d.trend.map((p, i) => ({ ...p, accent: i >= d.trend.length - 7 }))}
                label={t('boss.trend')}
                unit={t('boss.trendUnit')}
                height={200}
                accentNote={t('boss.last7')}
              />
            ) : (
              <Skeleton className="h-[200px]" />
            )}
          </Panel>
          <Panel title={t('boss.topEquipment')} action={<span className="text-small text-ink-3">{t('boss.topHint')}</span>}>
            {d ? (
              <BarList
                rows={d.top_equipment.map((e, i) => ({
                  label: e.name,
                  value: e.unplanned,
                  accent: i === 0,
                  hint: `${num(e.downtime_hours, 0)} ${t('boss.hours')}`,
                }))}
              />
            ) : (
              <Skeleton className="h-40" />
            )}
          </Panel>
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <section className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-small font-semibold text-ink-2">{t('boss.insightsTitle')}</h2>
              <Link
                to="/panel/analytics"
                className="inline-flex items-center gap-1 text-small font-semibold text-accent hover:underline"
              >
                {t('boss.allInsights')}
                <Icon name="chevronRight" size={16} />
              </Link>
            </div>
            {insights.data
              ? insights.data.items
                  .filter((i) => i.severity === 'high')
                  .slice(0, 3)
                  .map((item) => <InsightCard key={`${item.kind}-${item.subject}`} item={item} compact />)
              : [0, 1].map((i) => <Skeleton key={i} className="h-36" />)}
          </section>
          <Panel title={t('boss.bestWorkers')} action={<span className="text-small text-ink-3">{t('boss.bestHint')}</span>}>
            {d ? (
              <BarList
                max={100}
                format={(v) => num(v)}
                rows={d.best_workers.map((w) => ({ label: w.name, value: w.score, accent: true }))}
              />
            ) : (
              <Skeleton className="h-40" />
            )}
          </Panel>
        </div>
      </main>
    </div>
  )
}
