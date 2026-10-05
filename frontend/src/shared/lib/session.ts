import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

import type { Employee, Role } from '@/shared/api/types'

interface SessionState {
  token: string | null
  user: Employee | null
  signIn: (token: string, user: Employee) => void
  setUser: (user: Employee) => void
  signOut: () => void
}

export const useSession = create<SessionState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      signIn: (token, user) => set({ token, user }),
      setUser: (user) => set({ user }),
      signOut: () => set({ token: null, user: null }),
    }),
    { name: 'naryad.session', storage: createJSONStorage(() => localStorage) },
  ),
)

const DESKTOP_MIN_WIDTH = 1024

/** Стартовый экран роли. Мастер с телефона попадает в мобильную выдачу, с компьютера — в панель. */
export function homeFor(role: Role): string {
  switch (role) {
    case 'worker':
      return '/w'
    case 'master':
      return window.innerWidth >= DESKTOP_MIN_WIDTH ? '/panel' : '/m'
    case 'boss':
      return '/boss'
    case 'admin':
      return '/admin'
  }
}

const AREAS: { prefix: string; roles: Role[] }[] = [
  { prefix: '/w', roles: ['worker'] },
  { prefix: '/m', roles: ['master', 'admin'] },
  { prefix: '/panel', roles: ['master', 'boss', 'admin'] },
  { prefix: '/boss', roles: ['boss', 'admin'] },
  { prefix: '/admin', roles: ['admin'] },
]

/** Можно ли роли открыть адрес — чтобы после входа не вести человека в чужой раздел. */
export function canOpen(role: Role, path: string): boolean {
  const area = AREAS.find((a) => path === a.prefix || path.startsWith(`${a.prefix}/`) || path.startsWith(`${a.prefix}?`))
  return area ? area.roles.includes(role) : false
}
