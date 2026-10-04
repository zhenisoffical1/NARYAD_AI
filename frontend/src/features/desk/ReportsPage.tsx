import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  downloadReport,
  fetchReport,
  type Report,
  reportFile,
  reportKeys,
  type ReportKind,
  type ReportPeriod,
  type ReportQuery,
} from '@/shared/api/insights'
import { cn } from '@/shared/lib/format'
import { toast } from '@/shared/lib/toast'
import { Button, Counter, CounterBoard, EmptyState, Icon, Skeleton, Tabs } from '@/shared/ui'

import { DeskHeader, PeriodPicker } from './DeskHeader'
import { SectionFilter } from './filters'

const KINDS: ReportKind[] = ['orders', 'materials', 'downtime', 'rating']
const PERIODS: ReportPeriod[] = ['shift', 'day', 'week', 'month', 'custom']
const PERIOD_KEY = {
  shift: 'periodShift',
  day: 'periodDay',
  week: 'periodWeek',
  month: 'periodMonth',
  custom: 'periodCustom',
} as const

function isoDay(offset = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toISOString().slice(0, 10)
}

/** Отчёты с выгрузкой в Excel и PDF. На экране — те же цифры, что в файле. */
export function ReportsPage() {
  const { t } = useTranslation()
  const [kind, setKind] = useState<ReportKind>('orders')
  const [period, setPeriod] = useState<ReportPeriod>('shift')
  const [dateFrom, setDateFrom] = useState(isoDay(-6))
  const [dateTo, setDateTo] = useState(isoDay())
  const [section, setSection] = useState<number | null>(null)

  const query: ReportQuery = { kind, period, dateFrom, dateTo, sectionId: kind === 'rating' ? null : section }
  const report = useQuery({
    queryKey: reportKeys.get(query),
    queryFn: () => fetchReport(query),
    placeholderData: keepPreviousData,
  })
  const download = useMutation({
    mutationFn: (format: 'xlsx' | 'pdf') => downloadReport(reportFile(query, format)),
    onError: (error: Error) => toast(error.message, 'error'),
  })

  return (
    <div className="flex min-h-dvh flex-col bg-bg text-ink">
      <DeskHeader title={t('reports.title')} subtitle={report.data?.period_label} />

      <main className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-5 py-4">
        <div className="max-w-xl">
          <Tabs<ReportKind>
            label={t('reports.kind')}
            value={kind}
            onChange={setKind}
            items={KINDS.map((k) => ({ value: k, label: t(`reports.${k}`) }))}
          />
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <PeriodPicker
            value={period}
            onChange={setPeriod}
            label={t('desk.period')}
            options={PERIODS.map((p) => ({ value: p, label: t(`reports.${PERIOD_KEY[p]}`) }))}
          />
          {period === 'custom' && (
            <>
              <DateField label={t('reports.from')} value={dateFrom} onChange={setDateFrom} />
              <DateField label={t('reports.to')} value={dateTo} onChange={setDateTo} />
            </>
          )}
          {kind !== 'rating' && <SectionFilter value={section} onChange={setSection} />}
          <div className="ml-auto flex gap-2">
            <Button
              variant="secondary"
              size="md"
              icon="doc"
              loading={download.isPending && download.variables === 'xlsx'}
              disabled={download.isPending}
              onClick={() => download.mutate('xlsx')}
            >
              {t('reports.excel')}
            </Button>
            <Button
              variant="secondary"
              size="md"
              icon="report"
              loading={download.isPending && download.variables === 'pdf'}
              disabled={download.isPending}
              onClick={() => download.mutate('pdf')}
            >
              {t('reports.pdf')}
            </Button>
          </div>
        </div>

        {report.isError && (
          <EmptyState icon="alert" title={t('desk.loadError')} hint={report.error.message} />
        )}
        {!report.data && !report.isError && <Skeleton className="h-96" />}
        {report.data && (
          <div className={cn('flex flex-col gap-4 transition-opacity', report.isPlaceholderData && 'opacity-60')}>
            <ReportView report={report.data} />
          </div>
        )}
      </main>
    </div>
  )
}

function DateField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-stamp font-semibold text-ink-3">{label}</span>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 rounded-control border-2 border-line bg-surface px-2.5 text-small"
      />
    </label>
  )
}

function ReportView({ report }: { report: Report }) {
  const { t } = useTranslation()
  return (
    <>
      {report.kpis.length > 0 && (
        <CounterBoard columns={Math.min(report.kpis.length, 6)}>
          {report.kpis.map((k) => (
            <Counter key={k.label} label={k.label} value={k.value} alert={k.tone === 'danger' && k.value !== '0'} />
          ))}
        </CounterBoard>
      )}

      {report.summary && (
        <section className="rounded-[6px] border-l-4 border-accent bg-surface px-4 py-3">
          <p className="mb-1 flex items-center gap-1.5 text-small font-semibold text-accent">
            {report.summary_source === 'llm' && <Icon name="spark" size={16} />}
            {report.summary_source === 'llm' ? t('reports.summaryLlm') : t('reports.summary')}
          </p>
          <p className="max-w-[90ch] whitespace-pre-line">{report.summary}</p>
        </section>
      )}

      {report.tables.map((table) => (
        <section key={table.title} className="rounded-[6px] border border-line bg-surface">
          <header className="flex items-baseline justify-between gap-3 border-b border-line px-4 py-2.5">
            <h2 className="text-small font-semibold text-ink-2">{table.title}</h2>
            <span className="text-small text-ink-3">{t('reports.rows', { n: table.rows.length })}</span>
          </header>
          {table.rows.length === 0 ? (
            <p className="px-4 py-6 text-center text-ink-3">{t('reports.empty')}</p>
          ) : (
            <div className="max-h-[560px] overflow-auto">
              <table className="w-full border-collapse text-small">
                {table.columns[0]?.title && (
                  <thead className="sticky top-0 z-10 bg-plate">
                    <tr>
                      {table.columns.map((c) => (
                        <th
                          key={c.key}
                          scope="col"
                          className={cn(
                            'border-b-2 border-ink/70 px-3 py-2 font-semibold whitespace-nowrap text-ink-2',
                            c.align === 'right' ? 'text-right' : 'text-left',
                          )}
                        >
                          {c.title}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {table.rows.map((row, i) => {
                    const flagged = Boolean(table.highlight && row[table.highlight])
                    return (
                      <tr key={i} className={cn('border-b border-line/70', flagged && 'bg-red-soft/70')}>
                        {table.columns.map((c, ci) => (
                          <td
                            key={c.key}
                            className={cn(
                              'px-3 py-1.5 align-top',
                              c.align === 'right' && 'cond text-right tabular',
                              !table.columns[0]?.title && ci === 0 && 'w-40 text-ink-3',
                              flagged && ci === 0 && 'shadow-[inset_3px_0_0_var(--red-strong)]',
                            )}
                          >
                            {row[c.key] ?? ''}
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          {table.note && <p className="px-4 py-2 text-small text-ink-3">{table.note}</p>}
        </section>
      ))}
    </>
  )
}
