import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { homeFor, useSession } from '@/shared/lib/session'

function SystemScreen({ title, text }: { title: string; text: string }) {
  const { t } = useTranslation()
  const user = useSession((s) => s.user)
  return (
    <main className="flex min-h-dvh flex-col items-start justify-center gap-4 bg-bg px-6 text-ink">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="max-w-md text-lg">{text}</p>
      <Link
        to={user ? homeFor(user.role) : '/login'}
        className="inline-flex min-h-14 items-center rounded-control bg-accent bg-grad-primary px-6 text-lg font-semibold text-on-accent"
      >
        {t('common.toHome')}
      </Link>
    </main>
  )
}

export function NotFoundScreen() {
  const { t } = useTranslation()
  return <SystemScreen title={t('errors.notFoundTitle')} text={t('errors.notFoundText')} />
}
