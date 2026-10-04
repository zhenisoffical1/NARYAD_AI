import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { setLanguage } from '@/i18n'
import {
  type DemoAccount,
  type DemoOrder,
  demoKeys,
  fetchDemoState,
  type Fired,
  makeOverdue,
  makeUnaccepted,
  resetScene,
  sendTestNotification,
} from '@/shared/api/demo'
import { cn } from '@/shared/lib/format'
import { toast } from '@/shared/lib/toast'
import {
  Button,
  EmptyState,
  Icon,
  Panel,
  Select,
  Skeleton,
  StatusBadge,
} from '@/shared/ui'
import { QrCode } from '@/shared/ui/QrCode'

/** Пульт без входа и без WebSocket — обновляется опросом. */
const POLL_MS = 3000

/** Кого показать QR-кодами в первую очередь: роли из сценария защиты. */
const KEY_ACCOUNTS: { login: string; label: 'roleMaster' | 'roleWorkerFree' | 'roleWorkerQueue' | 'roleBoss' }[] = [
  { login: 'master1', label: 'roleMaster' },
  { login: 'akhmetov', label: 'roleWorkerFree' },
  { login: 'baizhanov', label: 'roleWorkerQueue' },
  { login: 'boss', label: 'roleBoss' },
]

const STEPS = [
  'stepPanel',
  'stepIssue',
  'stepAccept',
  'stepOverdue',
  'stepClose',
  'stepReview',
  'stepRework',
  'stepReport',
  'stepAnalytics',
] as const

const RULE_KEYS = {
  overdue: 'ruleOverdue',
  escalation: 'ruleEscalation',
  alarm: 'ruleAlarm',
  reminder: 'ruleReminder',
  boss: 'ruleBoss',
} as const

function isLocalHost(url: string): boolean {
  try {
    const host = new URL(url).hostname
    return host === 'localhost' || host === '127.0.0.1' || host === '[::1]'
  } catch {
    return true
  }
}

/** Адрес, который откроют телефоны: PUBLIC_URL, если он не localhost, иначе адрес пульта. */
function phoneBase(publicUrl: string): string {
  return isLocalHost(publicUrl) ? window.location.origin : publicUrl.replace(/\/$/, '')
}

/** Пульт оператора демо: сцена, промотка сроков, вход по QR, проверка уведомлений. */
export function DemoPage() {
  const { t, i18n } = useTranslation()
  const state = useQuery({ queryKey: demoKeys.state, queryFn: fetchDemoState, refetchInterval: POLL_MS })
  const data = state.data

  return (
    <div className="min-h-dvh bg-bg text-ink">
      <header className="flex min-h-16 flex-wrap items-center gap-x-4 gap-y-2 bg-bar bg-grad-bar px-4 py-2 text-on-bar md:px-6">
        <img src="/brand/km-logo-white.png" alt="АО «Костанайские Минералы»" className="h-9 w-auto" />
        <span aria-hidden className="hidden h-8 w-px bg-white/25 sm:block" />
        <div className="min-w-0">
          <h1 className="text-h2 leading-tight font-semibold">{t('demo.title')}</h1>
          <p className="text-small opacity-80">{t('demo.subtitle')}</p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {data && (
            <>
              <HeaderStamp ok>
                {t('demo.llm')}: {data.llm === 'mock' ? t('demo.llmMock') : data.llm}
              </HeaderStamp>
              <HeaderStamp ok={data.telegram}>
                {data.telegram && data.telegram_bot
                  ? t('demo.telegramOn', { bot: data.telegram_bot.replace(/^@/, '') })
                  : t('demo.telegramOff')}
              </HeaderStamp>
            </>
          )}
          <button
            type="button"
            onClick={() => setLanguage(i18n.language === 'kk' ? 'ru' : 'kk')}
            className="inline-flex min-h-11 items-center gap-2 rounded-control px-3 font-medium hover:bg-white/10"
          >
            <Icon name="globe" size={20} />
            {t('common.switchLanguage')}
          </button>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1440px] gap-4 px-4 py-4 md:px-6 lg:grid-cols-[minmax(0,1fr)_400px] lg:py-6">
        <div className="flex min-w-0 flex-col gap-4">
          <ScenePanel />
          <OrdersPanel orders={data?.orders} loading={state.isPending} />
          <ScriptPanel />
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <PhonesPanel accounts={data?.accounts} publicUrl={data?.public_url} />
          <TestPanel accounts={data?.accounts} />
        </div>
      </main>
    </div>
  )
}

function HeaderStamp({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <span className="stamp inline-flex min-h-8 items-center gap-2 rounded-full border border-white/30 px-3">
      <span aria-hidden className={cn('size-2 rounded-full', ok ? 'bg-green' : 'bg-off')} />
      {children}
    </span>
  )
}

function useFiredToast() {
  const { t } = useTranslation()
  return (fired: Fired) => {
    const what = fired.rules
      .filter((rule): rule is keyof typeof RULE_KEYS => rule in RULE_KEYS)
      .map((rule) => t(`demo.${RULE_KEYS[rule]}`))
    toast(what.length ? t('demo.fired', { what: what.join(', ') }) : t('demo.firedNothing'), what.length ? 'ok' : 'info')
  }
}

function ScenePanel() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const reset = useMutation({
    mutationFn: resetScene,
    onSuccess: () => {
      toast(t('demo.resetDone'))
      void queryClient.invalidateQueries()
    },
    onError: (error: Error) => toast(error.message, 'error'),
  })

  return (
    <Panel title={t('demo.scene')}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-prose text-ink-2">{t('demo.resetHint')}</p>
        <Button
          variant="danger"
          icon="undo"
          className="shrink-0"
          loading={reset.isPending}
          onHoldConfirm={() => reset.mutate()}
        >
          {t('demo.reset')}
        </Button>
      </div>
    </Panel>
  )
}

function OrdersPanel({ orders, loading }: { orders?: DemoOrder[]; loading: boolean }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const showFired = useFiredToast()
  const done = (fired: Fired) => {
    showFired(fired)
    void queryClient.invalidateQueries({ queryKey: demoKeys.state })
  }
  const overdue = useMutation({ mutationFn: makeOverdue, onSuccess: done, onError: (e: Error) => toast(e.message, 'error') })
  const unaccepted = useMutation({
    mutationFn: makeUnaccepted,
    onSuccess: done,
    onError: (e: Error) => toast(e.message, 'error'),
  })
  const busyId = overdue.isPending ? overdue.variables : unaccepted.isPending ? unaccepted.variables : null

  return (
    <Panel title={t('demo.orders')} className="overflow-hidden">
      {loading && (
        <div className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      )}
      {orders && orders.length === 0 && <EmptyState icon="list" title={t('demo.noOrders')} />}
      {orders && orders.length > 0 && (
        <div role="table" aria-label={t('demo.orders')} className="-mx-4 -my-4">
          <div
            role="row"
            className="hidden grid-cols-[64px_minmax(0,1.4fr)_minmax(0,1fr)_150px_72px_220px] gap-3 border-b border-line bg-plate/50 px-4 py-2 text-small font-semibold text-ink-3 md:grid"
          >
            <span role="columnheader">{t('demo.colNumber')}</span>
            <span role="columnheader">{t('demo.colEquipment')}</span>
            <span role="columnheader">{t('demo.colAssignee')}</span>
            <span role="columnheader">{t('demo.colStatus')}</span>
            <span role="columnheader">{t('demo.colDeadline')}</span>
            <span role="columnheader" className="sr-only">
              {t('demo.overdue')}
            </span>
          </div>
          {orders.map((order) => (
            <div
              key={order.id}
              role="row"
              className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-2 border-b border-line px-4 py-3 last:border-b-0 md:grid-cols-[64px_minmax(0,1.4fr)_minmax(0,1fr)_150px_72px_220px]"
            >
              <span role="cell" className="cond text-h2 font-semibold tabular">
                №{order.number}
              </span>
              <span role="cell" className="min-w-0 font-medium [overflow-wrap:break-word]">
                <span
                  aria-hidden
                  className={cn(
                    'mr-2 inline-block h-3 w-1.5 align-middle',
                    order.priority === 'emergency' ? 'hatch-red' : order.priority === 'high' ? 'bg-red' : 'bg-steel',
                    order.priority === 'planned' && 'border border-dashed border-ink-3 bg-transparent',
                  )}
                />
                {/* «ПП-2-12» не рвётся на дефисе */}
                {order.equipment.replace(/-(?=\d)/g, '‑')}
              </span>
              {/* На телефоне — одна строка «исполнитель · статус · срок», на десктопе — ячейки таблицы */}
              <span
                role="presentation"
                className="col-start-2 flex flex-wrap items-center gap-x-3 gap-y-1 md:contents"
              >
                <span role="cell" className="text-ink-2">
                  {order.assignee ?? '—'}
                </span>
                <span role="cell">
                  <StatusBadge status={order.status} size="sm" />
                </span>
                <span
                  role="cell"
                  className={cn(
                    'cond inline-flex items-center gap-1 tabular',
                    order.overdue ? 'font-semibold text-red' : 'text-ink-2',
                  )}
                >
                  <Icon name="clock" size={16} />
                  {order.deadline_local}
                </span>
              </span>
              <span role="cell" className="col-start-2 flex flex-wrap gap-2 md:col-start-auto md:justify-end">
                {order.can_overdue && (
                  <Button
                    size="sm"
                    variant="secondary"
                    icon="clock"
                    title={t('demo.overdueHint')}
                    loading={busyId === order.id && overdue.isPending}
                    disabled={busyId !== null}
                    onClick={() => overdue.mutate(order.id)}
                  >
                    {t('demo.overdue')}
                  </Button>
                )}
                {order.can_escalate && (
                  <Button
                    size="sm"
                    variant="secondary"
                    icon="alert"
                    title={t('demo.unacceptedHint')}
                    loading={busyId === order.id && unaccepted.isPending}
                    disabled={busyId !== null}
                    onClick={() => unaccepted.mutate(order.id)}
                  >
                    {t('demo.unaccepted')}
                  </Button>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

function PhonesPanel({ accounts, publicUrl }: { accounts?: DemoAccount[]; publicUrl?: string }) {
  const { t } = useTranslation()
  const [other, setOther] = useState<string>('')
  const base = publicUrl ? phoneBase(publicUrl) : window.location.origin
  const keyLogins = new Set(KEY_ACCOUNTS.map((a) => a.login))
  const byLogin = new Map(accounts?.map((a) => [a.login, a]))
  const cards = KEY_ACCOUNTS.flatMap(({ login, label }) => {
    const account = byLogin.get(login)
    return account ? [{ account, label: t(`demo.${label}`) }] : []
  })
  const otherAccount = other ? byLogin.get(other) : undefined
  if (otherAccount) cards.push({ account: otherAccount, label: t(`roles.${otherAccount.role}`) })

  return (
    <Panel title={t('demo.phones')}>
      <p className="mb-3 text-small text-ink-2">{t('demo.phonesHint')}</p>
      {isLocalHost(base) && (
        <p className="mb-3 flex gap-2 rounded-[6px] border border-red/40 bg-red-soft px-3 py-2 text-small text-ink">
          <Icon name="alert" size={18} className="mt-0.5 shrink-0 text-red" />
          {t('demo.localhostWarning')}
        </p>
      )}
      {!accounts && (
        <div className="grid grid-cols-2 gap-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="aspect-[3/4]" />
          ))}
        </div>
      )}
      <ul className="grid grid-cols-2 gap-3">
        {cards.map(({ account, label }) => (
          <li key={account.login} className="flex flex-col gap-2 rounded-[6px] border border-line bg-bg/60 p-2.5">
            <QrCode
              value={`${base}/demo/enter?login=${encodeURIComponent(account.login)}`}
              label={`${label}: ${account.full_name}`}
              className="w-full rounded-[3px]"
            />
            <div className="min-w-0">
              <p className="truncate text-stamp font-semibold text-ink-3" title={label}>{label}</p>
              <p className="truncate text-small font-semibold" title={account.full_name}>
                {account.short_name}
              </p>
              <p className="cond flex items-center gap-1.5 text-stamp text-ink-3">
                {account.login}
                {account.telegram_linked && (
                  <span className="inline-flex items-center gap-0.5 text-green-strong" title={t('demo.tgLinked')}>
                    <Icon name="send" size={12} />
                    TG
                  </span>
                )}
              </p>
            </div>
          </li>
        ))}
      </ul>
      {accounts && (
        <div className="mt-3">
          <Select<string>
            label={t('demo.otherAccount')}
            value={other}
            onChange={setOther}
            options={accounts
              .filter((a) => !keyLogins.has(a.login))
              .map((a) => ({
                value: a.login,
                label: a.full_name,
                hint: [t(`roles.${a.role}`), a.specialty].filter(Boolean).join(' · '),
              }))}
          />
        </div>
      )}
    </Panel>
  )
}

function TestPanel({ accounts }: { accounts?: DemoAccount[] }) {
  const { t } = useTranslation()
  const [employeeId, setEmployeeId] = useState<number>(0)
  const target = accounts?.find((a) => a.id === employeeId)
  const send = useMutation({
    mutationFn: sendTestNotification,
    onSuccess: () => toast(t('demo.testDone', { name: target?.short_name ?? '' })),
    onError: (error: Error) => toast(error.message, 'error'),
  })

  return (
    <Panel title={t('demo.test')}>
      <div className="flex flex-col gap-3">
        <p className="text-small text-ink-2">{t('demo.testHint')}</p>
        {accounts && (
          <Select<number>
            label={t('demo.colAssignee')}
            value={employeeId}
            onChange={setEmployeeId}
            options={accounts.map((a) => ({
              value: a.id,
              label: a.full_name,
              hint: [t(`roles.${a.role}`), a.telegram_linked ? t('demo.tgLinked') : null]
                .filter(Boolean)
                .join(' · '),
            }))}
          />
        )}
        <Button
          variant="secondary"
          icon="bell"
          block
          disabled={!target}
          loading={send.isPending}
          onClick={() => target && send.mutate(target.id)}
        >
          {t('demo.testSend')}
        </Button>
      </div>
    </Panel>
  )
}

function ScriptPanel() {
  const { t } = useTranslation()
  return (
    <Panel title={t('demo.script')}>
      <ol className="grid gap-x-6 gap-y-2.5 md:grid-cols-2">
        {STEPS.map((step, index) => (
          <li key={step} className="flex gap-3">
            <span
              aria-hidden
              className="cond inline-flex size-7 shrink-0 items-center justify-center rounded-[3px] bg-bar text-small font-semibold text-on-bar tabular"
            >
              {index + 1}
            </span>
            <span className="pt-0.5 text-small">{t(`demo.${step}`)}</span>
          </li>
        ))}
      </ol>
    </Panel>
  )
}
