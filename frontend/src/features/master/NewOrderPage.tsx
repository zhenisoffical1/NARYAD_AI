import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { TopBar } from '@/shared/ui'

import { IssueOrderForm } from './IssueOrderForm'

/** Выдача наряда с телефона мастера. */
export function NewOrderPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  return (
    <div className="flex min-h-dvh flex-col bg-bg text-ink">
      <TopBar title={t('issue.title')} onBack={() => navigate('/m')} />
      <div className="mx-auto flex w-full max-w-xl flex-1 flex-col">
        <IssueOrderForm onIssued={() => navigate('/m', { replace: true })} />
      </div>
    </div>
  )
}
