import { useNavigate } from 'react-router'

import { ProfilePage } from './ProfilePage'

/** Профиль мастера с телефона — с кнопкой «назад» к смене. */
export function MasterProfilePage() {
  const navigate = useNavigate()
  return (
    <div className="flex min-h-dvh flex-col bg-bg text-ink">
      <ProfilePage onBack={() => navigate('/m')} />
    </div>
  )
}
