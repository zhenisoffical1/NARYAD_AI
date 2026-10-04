import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { Assessment, CheckStatus } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'

import { Icon, type IconName } from './Icon'

const CHECK_ICON: Record<CheckStatus, { icon: IconName; className: string }> = {
  ok: { icon: 'check', className: 'text-green' },
  warn: { icon: 'alert', className: 'text-ink' },
  fail: { icon: 'x', className: 'text-red' },
  skip: { icon: 'minus', className: 'text-ink-3' },
}

const STEPS = ['completeness', 'time', 'materials', 'works_match', 'photos'] as const

/**
 * Вердикт ИИ с разбором по проверкам.
 * audience="worker" — уважительный отчёт исполнителю, "master" — полный разбор.
 */
export function VerdictCard({
  assessment,
  audience,
  progress,
}: {
  assessment: Assessment | null
  audience: 'worker' | 'master'
  /** Ключи уже пройденных проверок, пока ИИ работает */
  progress?: string[]
}) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(audience === 'worker')

  if (!assessment || assessment.status === 'running') {
    return (
      <section className="rounded-tag border border-line bg-surface p-4" aria-live="polite">
        <p className="flex items-center gap-2 font-semibold">
          <span className="inline-block size-4 animate-spin rounded-full border-2 border-accent border-r-transparent" />
          {t('verdict.running')}
        </p>
        <ul className="mt-3 flex flex-col gap-2">
          {STEPS.map((step) => {
            const done = progress?.includes(step)
            return (
              <li key={step} className={cn('flex items-center gap-2', done ? 'text-ink' : 'text-ink-3')}>
                <Icon name={done ? 'check' : 'clock'} size={18} className={done ? 'text-green' : ''} />
                {t(`checkStep.${step}`)}
              </li>
            )
          })}
        </ul>
      </section>
    )
  }

  const verdictKey = assessment.verdict ?? 'review'
  const score = assessment.final_score ?? assessment.score_0_100
  const explanation =
    audience === 'worker' ? assessment.explanation_worker : assessment.explanation_master

  return (
    <section className="overflow-hidden rounded-[12px] border border-line bg-surface shadow-card">
      <header
        className={cn(
          'flex items-center justify-between gap-3 border-b-2 px-4 py-3',
          verdictKey === 'accepted' && 'border-green bg-[linear-gradient(90deg,var(--green-soft),var(--surface))]',
          verdictKey === 'accepted_with_remarks' &&
            'border-dashed border-green bg-[linear-gradient(90deg,var(--green-soft),var(--surface))]',
          verdictKey === 'rework' && 'border-red bg-[linear-gradient(90deg,var(--red-soft),var(--surface))]',
          verdictKey === 'review' && 'border-accent bg-[linear-gradient(90deg,var(--accent-soft),var(--surface))]',
        )}
      >
        <div className="flex min-w-0 flex-col gap-1">
          <span className="stamp flex items-center gap-1.5 text-ink-3">
            <Icon name="spark" size={14} /> НарядAI
          </span>
          <span
            className={cn(
              'text-h2 font-semibold',
              verdictKey === 'rework' && 'text-red',
              verdictKey === 'review' && 'text-accent',
            )}
          >
            {t(`verdict.${verdictKey}`)}
          </span>
          {assessment.confidence !== null && (
            <span className="text-small text-ink-3">
              {t('verdict.confidence', { value: Math.round(assessment.confidence * 100) })}
            </span>
          )}
        </div>
        {score !== null && (
          <div className="flex shrink-0 items-baseline gap-1">
            <span className="cond text-display font-semibold">{score}</span>
            <span className="text-small text-ink-2">{t('verdict.score')}</span>
          </div>
        )}
      </header>

      {assessment.master_override_score !== null && (
        <p className="border-b border-line bg-queue-soft px-4 py-2 text-small">
          <span className="font-semibold">
            {t('verdict.masterScore', { score: assessment.master_override_score })}
          </span>
          {assessment.master_comment && <> — «{assessment.master_comment}»</>}
        </p>
      )}

      {assessment.checks && assessment.checks.length > 0 && (
        <ul className="flex flex-col divide-y divide-line">
          {assessment.checks.map((check) => {
            const style = CHECK_ICON[check.status]
            return (
              <li key={check.key} className="flex gap-3 px-4 py-3">
                <Icon name={style.icon} className={cn('mt-0.5 shrink-0', style.className)} />
                <div className="min-w-0">
                  <p className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-semibold">{check.label}</span>
                    <span className={cn('text-small', check.status === 'fail' ? 'text-red' : 'text-ink-3')}>
                      {t(`check.${check.status}`)}
                    </span>
                  </p>
                  <p className="text-small text-ink-2 [overflow-wrap:anywhere]">{check.detail}</p>
                  {check.items.length > 1 && (
                    <ul className="mt-1 flex list-disc flex-col gap-0.5 pl-5 text-small text-ink">
                      {check.items.slice(1).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {explanation && (
        <div className="border-t border-line px-4 py-3">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="flex min-h-11 items-center gap-1 font-semibold text-accent"
          >
            <Icon name={expanded ? 'chevronDown' : 'chevronRight'} size={20} />
            {audience === 'worker' ? t('verdict.reportWorker') : t('verdict.reportMaster')}
          </button>
          {expanded && (
            <p className="mt-1 whitespace-pre-line text-body [overflow-wrap:anywhere]">{explanation}</p>
          )}
        </div>
      )}
    </section>
  )
}
