import { api } from './client'
import type {
  AppNotification,
  Brigade,
  Equipment,
  FaultCode,
  Material,
  MyRating,
  NotificationFeed,
  PersonStatus,
  RatingReport,
  Section,
  ShiftSummary,
} from './types'

/** Справочники меняются редко — кэшируются надолго. */
export const REFERENCE_STALE = 10 * 60_000

export const refKeys = {
  sections: ['ref', 'sections'] as const,
  equipment: ['ref', 'equipment'] as const,
  recentEquipment: ['ref', 'equipment', 'recent'] as const,
  faultCodes: ['ref', 'fault-codes'] as const,
  materials: ['ref', 'materials'] as const,
  brigades: ['ref', 'brigades'] as const,
}

export const fetchSections = () => api<Section[]>('/sections')
export const fetchEquipment = () => api<Equipment[]>('/equipment')
export const fetchRecentEquipment = () => api<Equipment[]>('/equipment/recent')
export const fetchEquipmentByQr = (code: string) =>
  api<Equipment>(`/equipment/by-qr/${encodeURIComponent(code)}`)
export const fetchFaultCodes = () => api<FaultCode[]>('/fault-codes')
export const fetchMaterials = () => api<Material[]>('/materials')
export const fetchBrigades = () => api<Brigade[]>('/brigades')

/** Люди и счётчики смены меняются вместе с нарядами — живое событие обновляет их по 'shift'. */
export const shiftKeys = {
  people: ['shift', 'people'] as const,
  summary: ['shift', 'summary'] as const,
}

export const fetchPeople = () => api<PersonStatus[]>('/people/shift')
export const fetchSummary = () => api<ShiftSummary>('/shift/summary')

export const ratingKeys = {
  mine: (days: number) => ['rating', 'me', days] as const,
  all: (days: number) => ['rating', 'all', days] as const,
}

export const fetchMyRating = (days: number) => api<MyRating>(`/rating/me?days=${days}`)
export const fetchRating = (days: number) => api<RatingReport>(`/rating?days=${days}`)

export const notificationKeys = { feed: ['notifications'] as const }

export const fetchNotifications = () => api<NotificationFeed>('/notifications')
export const markNotificationsRead = (ids?: number[]) =>
  api<undefined>('/notifications/read', { method: 'POST', json: { ids: ids ?? null } })

export type { AppNotification }
