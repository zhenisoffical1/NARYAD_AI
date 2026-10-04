import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { analyticsKeys, type AnswerResult, askAnalytics, fetchAnalytics } from '@/shared/api/insights'
import { cn } from '@/shared/lib/format'
import { toast } from '@/shared/lib/toast'
import { Button, EmptyState, Icon, Skeleton } from '@/shared/ui'

import { DeskHeader, PeriodPicker } from './DeskHeader'
import { SectionFilter } from './filters'
import { InsightCard } from './InsightCard'
import { useDays } from './useDays'

/** Аналитика: закономерности за период и вопрос свободным текстом. */
export function AnalyticsPage() {
  const { t } = useTranslation()
  const [days, setDays, dayOptions] = useDays(90)
  const [section, setSection] = useState<number | null>(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<AnswerResult | null>(null)

  const list = useQuery({
    queryKey: analyticsKeys.list(days, section),
    queryFn: () => fetchAnalytics(days, section),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  })
  const ask = useMutation({
    mutationFn: askAnalytics,
    onSuccess: setAnswer,
    onError: (error: Error) => toast(error.message, 'error'),
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (question.trim().length >= 3) ask.mutate(question.trim())
  }

  const shown = answer ?? list.data
  const findings = shown?.items.filter((i) => i.severity !== 'info') ?? []
  const overview = shown?.items.find((i) => i.severity === 'info')

  return (
    <div className="flex min-h-dvh flex-col bg-bg bg-grad-page text-ink">
      <DeskHeader title={t('analytics.title')} subtitle={t('analytics.subtitle')} />

      <main className="mx-auto flex w-full max-w-[1100px] flex-col gap-4 px-5 py-5">
        <form onSubmit={submit} className="flex flex-col gap-2">
          <label htmlFor="ask" className="text-small font-semibold text-ink-2">
            {t('analytics.askLabel')}
          </label>
          <div className="flex gap-2">
            <div className="flex min-h-12 flex-1 items-center gap-2 rounded-control border-2 border-line bg-surface px-3 focus-within:border-accent">
              <Icon name="search" className="shrink-0 text-ink-3" />
              <input
                id="ask"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={t('analytics.askPlaceholder')}
                maxLength={300}
                className="min-w-0 flex-1 bg-transparent text-body outline-none placeholder:text-ink-3"
              />
            </div>
            <Button type="submit" size="lg" loading={ask.isPending} disabled={question.trim().length < 3}>
              {ask.isPending ? t('analytics.asking') : t('analytics.ask')}
            </Button>
          </div>
        </form>

        {answer ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-[6px] border border-accent/40 bg-surface px-4 py-3">
            <p className="font-semibold">{t('analytics.answerFor', { scope: answer.scope_label })}</p>
            <Button variant="quiet" size="sm" icon="undo" onClick={() => setAnswer(null)}>
              {t('analytics.clearAnswer')}
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <PeriodPicker value={days} onChange={setDays} options={dayOptions} label={t('desk.period')} />
            <SectionFilter value={section} onChange={setSection} />
            {list.data && (
              <p className="ml-auto text-small text-ink-3">{t('analytics.found', { n: findings.length })}</p>
            )}
          </div>
        )}

        <div className={cn('flex flex-col gap-3 transition-opacity', list.isPlaceholderData && !answer && 'opacity-60')}>
          {!shown && [0, 1, 2].map((i) => <Skeleton key={i} className="h-44" />)}
          {overview && <InsightCard item={overview} />}
          {findings.map((item) => (
            <InsightCard key={`${item.kind}-${item.subject}`} item={item} />
          ))}
          {shown && findings.length === 0 && (
            <EmptyState icon="chart" title={t('analytics.none')} hint={t('analytics.noneHint')} />
          )}
        </div>

        {shown && shown.items.every((i) => i.source === 'rules') && (
          <p className="text-small text-ink-3">{t('analytics.sourceRules')}</p>
        )}
      </main>
    </div>
  )
}
