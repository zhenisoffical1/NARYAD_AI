import { api } from './client'

export interface TelegramStatus {
  available: boolean
  linked: boolean
  bot_username: string | null
}

export const telegramKeys = { status: ['telegram'] as const }

export const fetchTelegramStatus = () => api<TelegramStatus>('/telegram')
export const createTelegramLink = () =>
  api<{ url: string; expires_at: string }>('/telegram/link', { method: 'POST' })
export const unlinkTelegram = () => api<undefined>('/telegram/link', { method: 'DELETE' })
