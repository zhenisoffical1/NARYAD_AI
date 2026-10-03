import { useTranslation } from 'react-i18next'

import { setLanguage } from '@/i18n'
import { useSession } from '@/shared/lib/session'
import { Button, EmptyState, TopBar } from '@/shared/ui'

/** Временный экран раздела. Заменяется настоящими экранами на этапах 3–6. */
export function StubScreen({ title }: { title: string }) {
  const { t, i18n } = useTranslation()
  const user = useSession((s) => s.user)
  const signOut = useSession((s) => s.signOut)

  return (
    <div className="min-h-dvh bg-bg text-ink">
      <TopBar
        title={title}
        subtitle={user ? `${user.short_name} · ${t(`roles.${user.role}`)}` : undefined}
      />
      <main className="mx-auto flex max-w-xl flex-col gap-4 px-4 py-6">
        <EmptyState icon="wrench" title={title} hint={t('screens.comingNext')} />
        <div className="flex flex-wrap gap-3">
          <Button
            variant="secondary"
            icon="globe"
            onClick={() => setLanguage(i18n.language === 'kk' ? 'ru' : 'kk')}
          >
            {t('common.switchLanguage')}
          </Button>
          <Button variant="secondary" icon="logout" onClick={signOut}>
            {t('common.logout')}
          </Button>
        </div>
      </main>
    </div>
  )
}
