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
    <main className="flex min-h-dvh flex-col bg-bg text-ink">
      <header className="flex items-start justify-between gap-4 bg-steel px-4 pt-[max(20px,env(safe-area-inset-top))] pb-5 text-on-steel">
        <div className="flex items-center gap-3">
          <span aria-hidden className="h-12 w-3 rounded-[1px] hatch-red" />
          <div>
            <p className="cond text-[34px] leading-none font-bold">{t('app.name')}</p>
            <p className="mt-1 text-small text-on-steel/75">{t('app.slogan')}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setLanguage(i18n.language === 'kk' ? 'ru' : 'kk')}
          className="min-h-12 rounded-control px-3 font-semibold active:bg-white/10"
        >
          {t('common.switchLanguage')}
        </button>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (pin.length === PIN_LENGTH) mutation.mutate(pin)
        }}
        className="mx-auto flex w-full max-w-sm flex-1 flex-col gap-6 px-4 py-6"
      >
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
            <p className="rounded-tag border-l-4 border-red bg-surface px-4 py-3 text-body" role="alert">
              {mutation.error.message}
            </p>
          )}
          {!loginName.trim() && !mutation.error && (
            <p className="text-center text-small text-ink-3">{t('login.enterLoginFirst')}</p>
          )}
        </div>
      </form>
    </main>
  )
}
