import type { Role } from '@/shared/api/types'

const DESKTOP_MIN_WIDTH = 1024

/** Куда вести по ссылке на наряд: у каждой роли своя карточка. */
export function orderPath(role: Role, id: number): string {
  if (role === 'worker') return `/w/orders/${id}`
  if (role === 'boss' || window.innerWidth >= DESKTOP_MIN_WIDTH) return `/panel?order=${id}`
  return `/m/orders/${id}`
}
