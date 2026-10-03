// Типы ответов API. Совпадают с Pydantic-схемами backend/app/schemas.

export type Role = 'master' | 'worker' | 'boss' | 'admin'
export type Shift = 'day' | 'night'

export interface Employee {
  id: number
  login: string
  full_name: string
  short_name: string
  role: Role
  specialty: string | null
  grade: number | null
  brigade_id: number | null
  shift: Shift | null
  on_shift: boolean
  telegram_linked: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  user: Employee
}

export interface LiveMessage {
  type: string
  payload: Record<string, unknown>
}
