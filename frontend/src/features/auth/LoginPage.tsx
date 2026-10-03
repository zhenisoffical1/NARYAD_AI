import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useSearchParams } from 'react-router'

import { setLanguage } from '@/i18n'
import { login } from '@/shared/api/auth'
import { homeFor, useSession } from '@/shared/lib/session'
import { PinPad, TextField } from '@/shared/ui'

const PIN_LENGTH = 4

export function LoginPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { user, signIn } = useSession()
  const [loginName, setLoginName] = useState(params.get('login') ?? '')
  const [pin, setPin] = useState('')

  const mutation = useMutation({
    mutationFn: (code: string) => login(loginName.trim(), code),
    onSuccess: (data) => {
      navigator.vibrate?.(30)
      signIn(data.access_token, data.user)
      navigate(params.get('next') ?? homeFor(data.user.role), { replace: true })
    },
    onError: () => {
      navigator.vibrate?.([40, 60, 40])
      setPin('')
    },
  })

  if (user && !mutation.isPending) return <Navigate to={homeFor(user.role)} replace />

  const onPin = (value: string) => {
    setPin(value)
    if (mutation.isError) mutation.reset()
    if (value.length === PIN_LENGTH && loginName.trim()) mutation.mutate(value)
  }

  return (
    <main className="flex min-h-dvh flex-col bg-surface text-ink md:flex-row">
      <section className="relative flex flex-col bg-hero contours-blue dark:contours md:w-[44%] md:justify-center">
        <div className="flex justify-end px-5 pt-[max(16px,env(safe-area-inset-top))] md:absolute md:top-8 md:right-8 md:p-0">
          <button
            type="button"
            onClick={() => setLanguage(i18n.language === 'kk' ? 'ru' : 'kk')}
            className="min-h-11 rounded-control border border-line bg-surface px-3 text-small font-medium text-ink-2 active:bg-plate"
          >
            {t('common.switchLanguage')}
          </button>
        </div>
        <div className="flex flex-col items-center gap-4 px-6 pt-2 pb-10 text-center md:pb-0">
          <img
            src="/brand/km-logo.png"
            alt="АО «Костанайские Минералы»"
            className="h-24 w-auto dark:hidden md:h-36"
          />
          <img
            src="/brand/km-logo-white.png"
            alt=""
            aria-hidden
            className="hidden h-24 w-auto dark:block md:h-36"
          />
          <div>
            <p className="text-[32px] leading-tight font-bold text-accent md:text-[40px]">
              {t('app.name')}
            </p>
            <p className="mt-1 text-body text-ink-2">{t('app.slogan')}</p>
          </div>
        </div>
      </section>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (pin.length === PIN_LENGTH) mutation.mutate(pin)
        }}
        className="flex flex-1 flex-col md:items-center md:justify-center"
      >
        <div className="mx-auto flex w-full max-w-sm flex-col gap-6 px-5 py-6">
          <h1 className="text-h1 font-semibold">{t('login.title')}</h1>
          <TextField
            label={t('login.login')}
            value={loginName}
            onChange={(e) => setLoginName(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            required
          />
          <div className="flex flex-col gap-3">
            <p className="text-small font-semibold text-ink-2">
              {t('login.pin')} · {t('login.pinHint')}
            </p>
            <PinPad
              value={pin}
              onChange={onPin}
              length={PIN_LENGTH}
              disabled={mutation.isPending || !loginName.trim()}
              error={mutation.isError}
            />
          </div>
          <div aria-live="assertive" className="min-h-14">
            {mutation.isPending && <p className="text-center text-ink-2">{t('login.checking')}</p>}
            {mutation.error && (
              <p className="rounded-tag border-l-4 border-red bg-red-soft px-4 py-3 text-body" role="alert">
                {mutation.error.message}
              </p>
            )}
            {!loginName.trim() && !mutation.error && (
              <p className="text-center text-small text-ink-3">{t('login.enterLoginFirst')}</p>
            )}
          </div>
        </div>
      </form>
    </main>
  )
}
