import { useTranslation } from 'react-i18next'

import { setLanguage } from '@/i18n'
import { useSession } from '@/shared/lib/session'
import { useLiveStatus } from '@/shared/lib/useLiveEvents'

const LIVE_DOT: Record<string, string> = {
  online: 'bg-ok-green',
  connecting: 'bg-signal-yellow',
  offline: 'bg-signal-red',
}

/** Временный экран раздела: заголовок, кто вошёл, статус связи. Заменяется на этапах 3–6. */
export function StubScreen({ title }: { title: string }) {
  const { t, i18n } = useTranslation()
  const user = useSession((s) => s.user)
  const signOut = useSession((s) => s.signOut)
  const live = useLiveStatus((s) => s.status)

  return (
    <main className="min-h-dvh bg-mineral text-steel">
      <header className="flex items-center justify-between gap-3 bg-steel px-4 py-3 text-mineral">
        <span className="font-semibold">{t('app.name')}</span>
        <span className="flex items-center gap-2 text-sm" role="status">
          <span className={`size-2.5 rounded-full ${LIVE_DOT[live]}`} aria-hidden />
          {t(`live.${live}`)}
        </span>
      </header>
      <section className="flex flex-col gap-4 px-4 py-6">
        <h1 className="text-2xl font-semibold">{title}</h1>
        {user && (
          <p className="text-lg">
            {user.full_name} · {t(`roles.${user.role}`)}
          </p>
        )}
        <p className="text-lg text-steel/80">{t('screens.comingNext')}</p>
        <div className="flex flex-wrap gap-4">
          <button
            type="button"
            onClick={() => setLanguage(i18n.language === 'kk' ? 'ru' : 'kk')}
            className="min-h-14 rounded-md border-2 border-steel px-5 text-lg font-semibold"
          >
            {t('common.switchLanguage')}
          </button>
          <button
            type="button"
            onClick={signOut}
            className="min-h-14 rounded-md border-2 border-steel px-5 text-lg font-semibold"
          >
            {t('common.logout')}
          </button>
        </div>
      </section>
    </main>
  )
}
