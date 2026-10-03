import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useSearchParams } from 'react-router'

import { login } from '@/shared/api/auth'
import { homeFor, useSession } from '@/shared/lib/session'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { user, signIn } = useSession()
  const [loginName, setLoginName] = useState(params.get('login') ?? '')
  const [pin, setPin] = useState('')

  const mutation = useMutation({
    mutationFn: () => login(loginName, pin),
    onSuccess: (data) => {
      signIn(data.access_token, data.user)
      navigate(params.get('next') ?? homeFor(data.user.role), { replace: true })
    },
    onError: () => setPin(''),
  })

  if (user && !mutation.isPending) return <Navigate to={homeFor(user.role)} replace />

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <main className="flex min-h-dvh flex-col justify-center bg-mineral px-4 text-steel">
      <form onSubmit={onSubmit} className="mx-auto flex w-full max-w-sm flex-col gap-5">
        <div>
          <p className="text-3xl font-bold">{t('app.name')}</p>
          <p className="text-lg text-steel/80">{t('app.slogan')}</p>
        </div>
        <h1 className="text-xl font-semibold">{t('login.title')}</h1>
        <label className="flex flex-col gap-2 text-lg">
          {t('login.login')}
          <input
            value={loginName}
            onChange={(e) => setLoginName(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            required
            className="min-h-14 rounded-md border-2 border-steel/40 bg-white px-4 text-xl"
          />
        </label>
        <label className="flex flex-col gap-2 text-lg">
          {t('login.pin')} <span className="text-base text-steel/70">{t('login.pinHint')}</span>
          <input
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
            inputMode="numeric"
            autoComplete="current-password"
            type="password"
            pattern="\d{4}"
            required
            className="min-h-14 rounded-md border-2 border-steel/40 bg-white px-4 text-xl tracking-[0.5em]"
          />
        </label>
        {mutation.error && (
          <p role="alert" className="rounded-md border-l-4 border-signal-red bg-white px-4 py-3 text-lg">
            {mutation.error.message}
          </p>
        )}
        <button
          type="submit"
          disabled={mutation.isPending || pin.length !== 4 || !loginName}
          className="min-h-16 rounded-md bg-km-blue text-xl font-semibold text-white disabled:opacity-50"
        >
          {mutation.isPending ? t('login.checking') : t('login.submit')}
        </button>
      </form>
    </main>
  )
}
