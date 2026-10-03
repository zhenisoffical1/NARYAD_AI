import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useSearchParams } from 'react-router'

import { setLanguage } from '@/i18n'
import { login } from '@/shared/api/auth'
import { homeFor, useSession } from '@/shared/lib/session'
import { PinPad, TextField } from '@/shared/ui'

const PIN_LENGTH = 4
const VERSION = '1.0'

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

  const languageButton = (
    <button
      type="button"
      onClick={() => setLanguage(i18n.language === 'kk' ? 'ru' : 'kk')}
      className="min-h-11 rounded-control px-3 text-small font-medium text-ink-2 hover:bg-plate active:bg-plate"
    >
      {t('common.switchLanguage')}
    </button>
  )

  return (
    <main className="flex min-h-dvh flex-col bg-bg text-ink md:flex-row">
      {/* Фирменная часть */}
      <section className="flex flex-col items-center justify-center gap-5 bg-hero px-6 pt-[max(28px,env(safe-area-inset-top))] pb-8 text-center contours md:w-[42%] md:gap-8">
        <img
          src="/brand/km-logo-white.png"
          alt="АО «Костанайские Минералы»"
          className="h-20 w-auto md:h-32"
        />
        <p className="border-t border-white/20 pt-4 text-[28px] leading-none font-semibold tracking-tight text-white md:pt-6 md:text-[36px]">
          {t('app.name')}
        </p>
      </section>

      {/* Форма */}
      <section className="flex flex-1 flex-col">
        <div className="hidden justify-end px-6 pt-5 md:flex">{languageButton}</div>
        <div className="flex flex-1 items-start justify-center px-4 py-5 md:items-center md:py-8">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (pin.length === PIN_LENGTH) mutation.mutate(pin)
            }}
            className="flex w-full max-w-[400px] flex-col gap-6 rounded-[10px] border border-line bg-surface px-5 py-6 shadow-[0_1px_2px_rgb(29_45_62/0.06),0_8px_24px_rgb(29_45_62/0.08)] md:px-8 md:py-8"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h1 className="text-h1 font-semibold">{t('login.title')}</h1>
                <p className="mt-1 text-small text-ink-3">{t('login.subtitle')}</p>
              </div>
              <div className="md:hidden">{languageButton}</div>
            </div>
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
            <div aria-live="assertive" className="min-h-12">
              {mutation.isPending && (
                <p className="text-center text-ink-2">{t('login.checking')}</p>
              )}
              {mutation.error && (
                <p
                  className="rounded-tag border-l-4 border-red bg-red-soft px-4 py-3 text-body"
                  role="alert"
                >
                  {mutation.error.message}
                </p>
              )}
              {!loginName.trim() && !mutation.error && (
                <p className="text-center text-small text-ink-3">{t('login.enterLoginFirst')}</p>
              )}
            </div>
          </form>
        </div>
        <footer className="px-6 pb-[max(16px,env(safe-area-inset-bottom))] text-center text-stamp text-ink-3">
          © {new Date().getFullYear()} {t('login.company')} · {t('app.name')} {VERSION}
        </footer>
      </section>
    </main>
  )
}
