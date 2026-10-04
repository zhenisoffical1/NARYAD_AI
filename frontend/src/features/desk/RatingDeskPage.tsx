import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { fetchRating, ratingKeys } from '@/shared/api/reference'
import type { RatingComponent } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'
import { BarList, Icon, Panel, Skeleton } from '@/shared/ui'

import { DeskHeader, PeriodPicker } from './DeskHeader'
import { useDays } from './useDays'

function num(v: number): string {
  return v.toFixed(1).replace(/\.0$/, '').replace('.', ',')
}

/** Составляющая рейтинга — тонкая шкала «набрано из возможного», без цветов статусов. */
function ComponentMeter({ c }: { c: RatingComponent }) {
  const max = c.weight * 100
  return (
    <div className="flex min-w-[88px] flex-col gap-1" title={c.detail}>
      <span className="cond text-small tabular">
        {num(c.points)} <span className="text-ink-3">/ {num(max)}</span>
      </span>
      <span aria-hidden className="h-1.5 overflow-hidden rounded-full bg-plate">
        <span className="block h-full bg-chart-accent" style={{ width: `${(c.points / max) * 100}%` }} />
      </span>
    </div>
  )
}

/** Рейтинг исполнителей и бригад для мастера и руководителя. */
export function RatingDeskPage() {
  const { t } = useTranslation()
  const [days, setDays, dayOptions] = useDays(30)
  const [open, setOpen] = useState<number | null>(null)
  const rating = useQuery({
    queryKey: ratingKeys.all(days),
    queryFn: () => fetchRating(days),
    placeholderData: keepPreviousData,
  })
  const workers = rating.data?.workers ?? []
  const rated = workers.filter((w) => w.score !== null)
  const columns = workers[0]?.components ?? []

  return (
    <div className="flex min-h-dvh flex-col bg-bg bg-grad-page text-ink">
      <DeskHeader title={t('ratingDesk.title')} subtitle={t('boss.period', { days })} />
      <main
        className={cn(
          'mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-5 py-4 transition-opacity',
          rating.isPlaceholderData && 'opacity-60',
        )}
      >
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <PeriodPicker value={days} onChange={setDays} options={dayOptions} label={t('desk.period')} />
          <p className="text-small text-ink-3">{t('ratingDesk.formula')}</p>
        </div>

        {!rating.data ? (
          <Skeleton className="h-96" />
        ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
            <section className="overflow-hidden rounded-[6px] border border-line bg-surface">
              <header className="border-b border-line px-4 py-2.5">
                <h2 className="text-small font-semibold text-ink-2">{t('ratingDesk.workers')}</h2>
              </header>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-small">
                  <thead className="bg-plate">
                    <tr>
                      <th scope="col" className="px-3 py-2 text-right font-semibold text-ink-2">{t('ratingDesk.rank')}</th>
                      <th scope="col" className="px-3 py-2 text-left font-semibold text-ink-2">{t('ratingDesk.name')}</th>
                      <th scope="col" className="px-3 py-2 text-right font-semibold text-ink-2">{t('ratingDesk.orders')}</th>
                      <th scope="col" className="px-3 py-2 text-right font-semibold text-ink-2">{t('ratingDesk.score')}</th>
                      {columns.map((c) => (
                        <th key={c.key} scope="col" className="px-3 py-2 text-left font-semibold text-ink-2">
                          {c.label}
                        </th>
                      ))}
                      <th aria-hidden className="w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {workers.map((w) => {
                      const expanded = open === w.employee.id
                      return (
                        <Fragment key={w.employee.id}>
                          <tr
                            className={cn('cursor-pointer border-t border-line/70 hover:bg-plate/40', expanded && 'bg-plate/40')}
                            onClick={() => setOpen(expanded ? null : w.employee.id)}
                          >
                            <td className="cond px-3 py-2 text-right text-body font-semibold tabular">{w.rank ?? '—'}</td>
                            <td className="px-3 py-2">
                              <span className="font-medium">{w.employee.full_name}</span>
                              <span className="block text-ink-3">{w.employee.specialty}</span>
                            </td>
                            <td className="cond px-3 py-2 text-right tabular">{w.orders}</td>
                            <td className="cond px-3 py-2 text-right text-h2 font-semibold tabular">
                              {w.score !== null ? num(w.score) : <span className="text-small font-normal text-ink-3">{t('ratingDesk.insufficient')}</span>}
                            </td>
                            {w.components.map((c) => (
                              <td key={c.key} className="px-3 py-2">
                                <ComponentMeter c={c} />
                              </td>
                            ))}
                            <td className="px-2 py-2 text-ink-3">
                              <button
                                type="button"
                                aria-expanded={expanded}
                                aria-label={t('ratingDesk.explain')}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setOpen(expanded ? null : w.employee.id)
                                }}
                                className="inline-flex size-9 items-center justify-center rounded-control hover:bg-plate"
                              >
                                <Icon name={expanded ? 'chevronDown' : 'chevronRight'} size={18} />
                              </button>
                            </td>
                          </tr>
                          {expanded && w.explanation && (
                            <tr className="bg-plate/40">
                              <td />
                              <td colSpan={columns.length + 4} className="px-3 pb-3">
                                <p className="flex max-w-[100ch] gap-2 text-body">
                                  <Icon name="spark" size={18} className="mt-0.5 shrink-0 text-accent" />
                                  {w.explanation}
                                </p>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </section>

            <div className="flex flex-col gap-4">
              <Panel title={t('ratingDesk.chart')}>
                <BarList
                  max={100}
                  format={num}
                  rows={rated.map((w) => ({ label: w.employee.short_name, value: w.score ?? 0, accent: true }))}
                />
              </Panel>
              <Panel title={t('ratingDesk.brigades')}>
                <BarList
                  max={100}
                  format={num}
                  rows={rating.data.brigades
                    .filter((b) => b.score !== null)
                    .map((b) => ({
                      label: b.brigade.name,
                      value: b.score ?? 0,
                      accent: true,
                      hint: `${b.members} ${t('ratingDesk.members').toLowerCase()}`,
                    }))}
                />
              </Panel>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
