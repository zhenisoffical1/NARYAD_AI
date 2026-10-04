import { useTranslation } from 'react-i18next'

import type { Insight } from '@/shared/api/insights'
import { cn } from '@/shared/lib/format'
import { BarList, ColumnChart, Icon } from '@/shared/ui'

/** Как подписать значения пары «о ком находка — остальные». */
function pairFormat(kind: string): (value: number) => string {
  if (kind === 'material_overuse') return (v) => `×${String(v).replace('.', ',')}`
  if (kind === 'worker_returns' || kind === 'after_ppr') return (v) => `${v}%`
  return (v) => String(v)
}

/** «Конвейер К-3: 45 поломок…» под заголовком «Конвейер К-3» — название не повторяем. */
function withoutSubject(text: string, subject: string): string {
  const prefix = `${subject}: `
  if (!subject || !text.startsWith(prefix)) return text
  const rest = text.slice(prefix.length)
  return rest.charAt(0).toUpperCase() + rest.slice(1)
}

/**
 * Находка аналитики в виде бирки: полоса слева — важность (красная — нужно решение,
 * стальная — обратить внимание), крупно — о чём находка, ниже вывод, мини-график
 * и «что сделать». Цифры всегда из базы; если вывод писала модель — это помечено.
 */
export function InsightCard({ item, compact = false }: { item: Insight; compact?: boolean }) {
  const { t } = useTranslation()
  const high = item.severity === 'high'
  const info = item.severity === 'info'

  return (
    <article
      className={cn(
        'relative overflow-hidden rounded-[6px] border border-line bg-surface pl-5',
        info && 'bg-plate/40',
      )}
    >
      <span
        aria-hidden
        className={cn('absolute inset-y-0 left-0 w-1.5', high ? 'bg-red' : info ? 'bg-chart-muted' : 'bg-accent')}
      />
      <div className="flex flex-col gap-3 py-4 pr-5">
        <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <div className="min-w-0">
            <p className="text-small font-semibold text-ink-3">
              {t(`analytics.kinds.${item.kind}` as 'analytics.kinds.overview', { defaultValue: item.title })}
              <span className={cn('ml-2', high ? 'text-red' : 'text-ink-3')}>· {t(`analytics.${item.severity}`)}</span>
            </p>
            {item.subject && (
              <h3 className="text-h2 leading-snug font-semibold [overflow-wrap:break-word]">{item.subject}</h3>
            )}
          </div>
          {item.source === 'llm' && (
            <span className="inline-flex items-center gap-1 text-small font-medium text-accent">
              <Icon name="spark" size={16} />
              {t('analytics.byLlm')}
            </span>
          )}
        </header>

        <div className={cn('grid gap-4', !compact && item.series.length > 0 && 'md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]')}>
          <p className="max-w-prose text-body leading-relaxed">{withoutSubject(item.conclusion, item.subject)}</p>
          {!compact && item.series.length > 0 && (
            <div className="min-w-0">
              {item.chart === 'weeks' ? (
                <ColumnChart
                  data={item.series}
                  label={`${item.title}: ${item.subject}`}
                  unit={t('analytics.weeksUnit')}
                  height={120}
                  accentNote={t('analytics.weeksNote')}
                />
              ) : (
                <BarList
                  className="pt-1"
                  format={pairFormat(item.kind)}
                  rows={item.series.map((p) => ({ label: p.label, value: p.value, accent: p.accent }))}
                />
              )}
            </div>
          )}
        </div>

        {item.recommendation && (
          <div className="flex gap-3 rounded-[8px] bg-accent-soft/70 px-3.5 py-3">
            <Icon name="wrench" size={20} className="mt-0.5 shrink-0 text-ink-2" />
            <div>
              <p className="text-small font-semibold text-ink-2">{t('analytics.recommendation')}</p>
              <p className="text-body">{item.recommendation}</p>
            </div>
          </div>
        )}

        {!compact && item.source === 'llm' && (
          <details className="text-small text-ink-2">
            <summary className="cursor-pointer font-semibold">{t('analytics.facts')}</summary>
            <p className="mt-1.5">{item.facts}</p>
          </details>
        )}
      </div>
    </article>
  )
}
