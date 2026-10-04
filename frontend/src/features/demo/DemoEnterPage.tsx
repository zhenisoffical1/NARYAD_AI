import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router'

import { demoLogin } from '@/shared/api/demo'
import { homeFor, useSession } from '@/shared/lib/session'
import { Button, Icon } from '@/shared/ui'

/** Вход по QR с пульта демо: /demo/enter?login=akhmetov → сразу на экран роли. */
export function DemoEnterPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const signIn = useSession((s) => s.signIn)
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)
  const login = params.get('login') ?? ''

  useEffect(() => {
    if (started.current) return
    started.current = true
    demoLogin(login)
      .then(({ access_token, user }) => {
        signIn(access_token, user)
        navigate(homeFor(user.role), { replace: true })
      })
      .catch((e: Error) => setError(e.message))
  }, [login, navigate, signIn])

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-bg px-6 text-center text-ink">
      <img src="/brand/km-logo.png" alt="АО «Костанайские Минералы»" className="h-12 w-auto" />
      {error ? (
        <>
          <Icon name="alert" size={32} className="text-red" />
          <h1 className="text-h2 font-semibold">{t('demo.enterFailed')}</h1>
          <p className="max-w-sm text-ink-2">{error}</p>
          <Button variant="secondary" onClick={() => navigate('/login', { replace: true })}>
            {t('login.title')}
          </Button>
        </>
      ) : (
        <p role="status" className="text-h2 font-semibold">
          {t('demo.enterTitle')}
        </p>
      )}
    </main>
  )
}
