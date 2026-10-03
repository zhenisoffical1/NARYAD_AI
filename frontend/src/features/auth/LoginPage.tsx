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
    <main className="flex min-h-dvh flex-col bg-bg text-ink md:flex-row">
      {/* Фирменная часть: синий, изолинии карьера, бирка-логотип */}
      <section className="relative overflow-hidden bg-bar text-on-bar contours md:flex md:w-[44%] md:flex-col md:justify-between">
        <div className="flex items-start justify-between gap-4 px-5 pt-[max(20px,env(safe-area-inset-top))] pb-12 md:px-10 md:pt-10">
          <div className="flex items-stretch gap-3">
            <span aria-hidden className="relative w-3.5 rounded-[2px] hatch-red">
              <span className="absolute top-2 left-1/2 size-2 -translate-x-1/2 rounded-full bg-bar" />
            </span>
            <div className="py-0.5">
              <p className="cond text-[40px] leading-none font-bold md:text-[56px]">{t('app.name')}</p>
              <p className="mt-2 text-body-lg opacity-90">{t('app.slogan')}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setLanguage(i18n.language === 'kk' ? 'ru' : 'kk')}
            className="min-h-12 shrink-0 rounded-control border-2 border-white/40 px-3 font-semibold active:bg-white/10"
          >
            {t('common.switchLanguage')}
          </button>
        </div>
        <ul className="hidden flex-col gap-4 px-10 pb-12 text-body-lg md:flex">
          {(['loginFeature1', 'loginFeature2', 'loginFeature3'] as const).map((key) => (
            <li key={key} className="flex items-center gap-3">
              <span aria-hidden className="h-6 w-1.5 rounded-[1px] bg-yellow" />
              {t(`login.${key}`)}
            </li>
          ))}
        </ul>
      </section>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (pin.length === PIN_LENGTH) mutation.mutate(pin)
        }}
        className="relative -mt-6 flex flex-1 flex-col rounded-t-[20px] bg-surface shadow-overlay md:mt-0 md:items-center md:justify-center md:rounded-none md:shadow-none"
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
