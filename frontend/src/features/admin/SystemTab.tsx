import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { adminKeys, fetchSystemStatus } from '@/shared/api/admin'
import { cn, ddmm, hhmm } from '@/shared/lib/format'
import { Counter, CounterBoard, Icon, Panel, Skeleton } from '@/shared/ui'

/** Состояние системы: режим ИИ, Telegram, демо, объём данных и журнал вызовов модели. */
export function SystemTab() {
  const { t } = useTranslation()
  const status = useQuery({
    queryKey: adminKeys.system,
    queryFn: fetchSystemStatus,
    refetchInterval: 30_000,
  })
  const s = status.data
  if (!s) return <Skeleton className="h-64" />

  return (
    <div className="flex flex-col gap-5">
      <CounterBoard className="grid grid-cols-2 lg:grid-cols-4">
        <Counter
          tone="blue"
          label={t('admin.sys.people')}
          value={s.employees_active}
          hint={t('admin.sys.telegramLinked', { count: s.employees_telegram })}
        />
        <Counter tone="green" label={t('admin.sys.equipment')} value={s.equipment} />
        <Counter
          label={t('admin.sys.orders')}
          value={s.orders_total}
          hint={t('admin.sys.ordersActive', { count: s.orders_active })}
        />
        <Counter
          label={t('admin.sys.llmCalls')}
          value={s.llm_calls_24h}
          hint={
            s.llm_avg_latency_ms !== null ? t('admin.sys.latency', { ms: s.llm_avg_latency_ms }) : undefined
          }
        />
      </CounterBoard>

      <div className="grid gap-4 lg:grid-cols-3">
        <Status
          ok={s.llm_mode === 'anthropic'}
          title={t('admin.sys.ai')}
          value={s.llm_mode === 'anthropic' ? t('admin.sys.aiLive') : t('admin.sys.aiMock')}
          hint={
            s.llm_mode === 'anthropic' ? `${s.llm_model} / ${s.llm_fast_model}` : t('admin.sys.aiMockHint')
          }
        />
        <Status
          ok={s.telegram}
          title={t('admin.sys.telegram')}
          value={
            s.telegram ? (s.telegram_bot ? `@${s.telegram_bot}` : t('admin.sys.on')) : t('admin.sys.off')
          }
          hint={s.telegram ? t('admin.sys.telegramHint') : t('admin.sys.telegramOffHint')}
        />
        <Status
          ok={!s.demo_mode}
          neutral={s.demo_mode}
          title={t('admin.sys.demo')}
          value={s.demo_mode ? t('admin.sys.on') : t('admin.sys.off')}
          hint={s.demo_mode ? t('admin.sys.demoHint') : t('admin.sys.prodHint')}
        />
      </div>

      <Panel
        title={t('admin.sys.journal')}
        action={
          s.llm_ok_share !== null && (
            <span className="text-small text-ink-3">
              {t('admin.sys.okShare', {
                pct: Math.round(s.llm_ok_share * 100),
              })}
            </span>
          )
        }
      >
        {s.llm_recent.length === 0 ? (
          <p className="text-small text-ink-3">{t('admin.sys.journalEmpty')}</p>
        ) : (
          <table className="w-full text-left text-small">
            <thead className="text-ink-3">
              <tr>
                <th className="py-1.5 font-semibold">{t('admin.sys.when')}</th>
                <th className="py-1.5 font-semibold">{t('admin.sys.purpose')}</th>
                <th className="py-1.5 font-semibold">{t('admin.sys.model')}</th>
                <th className="py-1.5 text-right font-semibold">{t('admin.sys.ms')}</th>
                <th className="py-1.5 text-right font-semibold">{t('admin.sys.result')}</th>
              </tr>
            </thead>
            <tbody>
              {s.llm_recent.map((c) => (
                <tr key={c.id} className="border-t border-line/70">
                  <td className="cond py-2">
                    {ddmm(c.created_at)} {hhmm(c.created_at)}
                  </td>
                  <td className="py-2">{c.purpose}</td>
                  <td className="py-2 text-ink-2">{c.model}</td>
                  <td className="cond py-2 text-right">{c.latency_ms}</td>
                  <td
                    className={cn(
                      'py-2 text-right font-semibold',
                      c.ok ? 'text-green-strong dark:text-green' : 'text-red',
                    )}
                    title={c.error ?? undefined}
                  >
                    {c.ok ? t('admin.sys.ok') : t('admin.sys.fail')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  )
}

function Status({
  ok,
  neutral = false,
  title,
  value,
  hint,
}: {
  ok: boolean
  neutral?: boolean
  title: string
  value: string
  hint: string
}) {
  return (
    <section className="flex gap-3 rounded-[12px] border border-line bg-surface p-4 shadow-card">
      <span
        aria-hidden
        className={cn(
          'flex size-10 shrink-0 items-center justify-center rounded-full',
          neutral
            ? 'bg-yellow-soft text-amber'
            : ok
              ? 'bg-green-soft text-green-strong dark:text-green'
              : 'bg-plate text-ink-3',
        )}
      >
        <Icon name={ok && !neutral ? 'check' : 'alert'} size={20} />
      </span>
      <div className="min-w-0">
        <p className="text-small text-ink-3">{title}</p>
        <p className="font-semibold">{value}</p>
        <p className="mt-0.5 text-small text-ink-2 [overflow-wrap:anywhere]">{hint}</p>
      </div>
    </section>
  )
}
