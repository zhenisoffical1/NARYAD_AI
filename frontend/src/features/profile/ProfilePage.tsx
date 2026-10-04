import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { type Language, setLanguage } from '@/i18n'
import { fetchBrigades, REFERENCE_STALE, refKeys } from '@/shared/api/reference'
import {
  createTelegramLink,
  fetchTelegramStatus,
  telegramKeys,
  unlinkTelegram,
} from '@/shared/api/telegram'
import { useSession } from '@/shared/lib/session'
import { type ThemeMode, useTheme } from '@/shared/lib/theme'
import { toast } from '@/shared/lib/toast'
import { Button, Fact, Icon, Panel, Skeleton, Tabs, TopBar } from '@/shared/ui'

const WAIT_POLL_MS = 3000

/** Профиль: кто я, Telegram, язык, тема, выход. Один экран для исполнителя и мастера. */
export function ProfilePage({ onBack }: { onBack?: () => void }) {
  const { t, i18n } = useTranslation()
  const user = useSession((s) => s.user)
  const signOut = useSession((s) => s.signOut)
  const navigate = useNavigate()
  const { mode, setMode } = useTheme()
  const brigades = useQuery({
    queryKey: refKeys.brigades,
    queryFn: fetchBrigades,
    staleTime: REFERENCE_STALE,
  })

  if (!user) return null
  const brigade = brigades.data?.find((b) => b.id === user.brigade_id)

  return (
    <div className="flex flex-1 flex-col">
      <TopBar title={t('profile.title')} onBack={onBack} />
      <main className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-4">
        <section className="flex items-center gap-4 rounded-[8px] border border-line bg-surface p-4">
          <span
            aria-hidden
            className="cond inline-flex size-14 shrink-0 items-center justify-center rounded-[6px] bg-bar text-h2 font-semibold text-on-bar"
          >
            {user.full_name
              .split(' ')
              .slice(0, 2)
              .map((part) => part[0])
              .join('')}
          </span>
          <div className="min-w-0">
            <p className="text-body-lg font-semibold [overflow-wrap:anywhere]">{user.full_name}</p>
            <p className="text-ink-2">
              {[t(`roles.${user.role}`), user.specialty].filter(Boolean).join(' · ')}
            </p>
          </div>
        </section>

        <Panel>
          <dl>
            {brigade && <Fact label={t('profile.brigade')}>{brigade.name}</Fact>}
            {user.grade && <Fact label={t('profile.grade')}>{user.grade}</Fact>}
            {user.shift && (
              <Fact label={t('profile.shift')}>
                {user.shift === 'day' ? t('profile.shiftDay') : t('profile.shiftNight')}
              </Fact>
            )}
            <Fact label={t('profile.login')}>
              <span className="cond tabular">{user.login}</span>
            </Fact>
          </dl>
        </Panel>

        <TelegramPanel />

        <Panel title={t('profile.settings')}>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <span className="text-small font-semibold text-ink-2">{t('profile.language')}</span>
              <Tabs<Language>
                label={t('profile.language')}
                value={i18n.language === 'kk' ? 'kk' : 'ru'}
                onChange={setLanguage}
                items={[
                  { value: 'ru', label: t('profile.langRu') },
                  { value: 'kk', label: t('profile.langKk') },
                ]}
              />
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-small font-semibold text-ink-2">{t('common.theme')}</span>
              <Tabs<ThemeMode>
                label={t('common.theme')}
                value={mode}
                onChange={setMode}
                items={[
                  { value: 'light', label: t('common.themeLight') },
                  { value: 'auto', label: t('common.themeAuto') },
                  { value: 'dark', label: t('common.themeDark') },
                ]}
              />
            </div>
          </div>
        </Panel>

        <Button
          variant="secondary"
          icon="logout"
          block
          onClick={() => {
            signOut()
            navigate('/login', { replace: true })
          }}
        >
          {t('common.logout')}
        </Button>
      </main>
    </div>
  )
}

function TelegramPanel() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [waiting, setWaiting] = useState(false)
  const status = useQuery({
    queryKey: telegramKeys.status,
    queryFn: fetchTelegramStatus,
    refetchInterval: waiting ? WAIT_POLL_MS : false,
  })
  const linked = status.data?.linked ?? false

  useEffect(() => {
    if (waiting && linked) {
      toast(t('profile.tgLinked'))
      navigator.vibrate?.(25)
    }
  }, [waiting, linked, t])

  const link = useMutation({
    mutationFn: createTelegramLink,
    onSuccess: ({ url }) => {
      setWaiting(true)
      window.open(url, '_blank', 'noopener')
    },
    onError: (error: Error) => toast(error.message, 'error'),
  })
  const unlink = useMutation({
    mutationFn: unlinkTelegram,
    onSuccess: () => {
      setWaiting(false)
      toast(t('profile.tgUnlinked'))
      void queryClient.invalidateQueries({ queryKey: telegramKeys.status })
    },
    onError: (error: Error) => toast(error.message, 'error'),
  })

  return (
    <Panel
      title={t('profile.telegram')}
      action={
        linked ? (
          <span className="stamp inline-flex items-center gap-1.5 text-green-strong">
            <Icon name="check" size={16} />
            {t('profile.tgLinked')}
          </span>
        ) : undefined
      }
    >
      {status.isPending && <Skeleton className="h-14" />}
      {status.data && !status.data.available && !linked && (
        <p className="text-ink-2">{t('profile.tgUnavailable')}</p>
      )}
      {status.data && linked && (
        <div className="flex flex-col gap-3">
          <p className="text-ink-2">{t('profile.tgLinkedHint')}</p>
          <Button
            variant="quiet"
            size="md"
            className="self-start"
            loading={unlink.isPending}
            onClick={() => unlink.mutate()}
          >
            {t('profile.tgUnlink')}
          </Button>
        </div>
      )}
      {status.data?.available && !linked && (
        <div className="flex flex-col gap-3">
          <p className="text-ink-2">{waiting ? t('profile.tgWaiting') : t('profile.tgConnectHint')}</p>
          <Button icon="send" block loading={link.isPending} onClick={() => link.mutate()}>
            {t('profile.tgConnect')}
          </Button>
        </div>
      )}
    </Panel>
  )
}
