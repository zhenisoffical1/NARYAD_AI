import { api } from './client'
import type { OrderStatus, Priority, Role, TokenResponse } from './types'

export interface DemoAccount {
  id: number
  login: string
  full_name: string
  short_name: string
  role: Role
  specialty: string | null
  state: 'free' | 'busy' | 'queue' | 'off_shift' | null
  telegram_linked: boolean
}

export interface DemoOrder {
  id: number
  number: number
  status: OrderStatus
  status_label: string
  priority: Priority
  equipment: string
  assignee: string | null
  deadline_local: string
  overdue: boolean
  can_overdue: boolean
  can_escalate: boolean
}

export interface DemoState {
  llm: string
  telegram: boolean
  telegram_bot: string | null
  public_url: string
  accounts: DemoAccount[]
  orders: DemoOrder[]
}

export interface Fired {
  rules: string[]
}

export const demoKeys = { state: ['demo'] as const }

export const fetchDemoState = () => api<DemoState>('/demo')
export const resetScene = () => api<Fired>('/demo/reset', { method: 'POST' })
export const makeOverdue = (orderId: number) =>
  api<Fired>(`/demo/orders/${orderId}/overdue`, { method: 'POST' })
export const makeUnaccepted = (orderId: number) =>
  api<Fired>(`/demo/orders/${orderId}/unaccepted`, { method: 'POST' })
export const sendTestNotification = (employeeId: number) =>
  api<undefined>('/demo/notify', { method: 'POST', json: { employee_id: employeeId } })
export const demoLogin = (login: string) =>
  api<TokenResponse>('/demo/login', { method: 'POST', json: { login } })
