import { api } from './client'

export type AdminKind = 'employees' | 'equipment' | 'sections' | 'brigades' | 'fault-codes' | 'materials'

/** Запись справочника как её отдаёт /api/admin/{kind}: набор полей зависит от справочника. */
export type AdminRecord = { id: number } & Record<string, unknown>

export interface ImportResult {
  created: number
  updated: number
  errors: string[]
}

export interface LlmCall {
  id: number
  purpose: string
  model: string
  latency_ms: number
  ok: boolean
  error: string | null
  created_at: string
}

export interface SystemStatus {
  llm_mode: 'mock' | 'anthropic'
  llm_model: string
  llm_fast_model: string
  telegram: boolean
  telegram_bot: string | null
  demo_mode: boolean
  employees_active: number
  employees_telegram: number
  equipment: number
  orders_total: number
  orders_active: number
  llm_calls_24h: number
  llm_ok_share: number | null
  llm_avg_latency_ms: number | null
  llm_recent: LlmCall[]
}

export const adminKeys = {
  list: (kind: AdminKind) => ['admin', kind] as const,
  system: ['admin', 'system'] as const,
}

export const fetchAdminList = (kind: AdminKind) => api<AdminRecord[]>(`/admin/${kind}`)

export const createAdminRecord = (kind: AdminKind, data: Record<string, unknown>) =>
  api<AdminRecord>(`/admin/${kind}`, { method: 'POST', json: data })

export const updateAdminRecord = (kind: AdminKind, id: number, data: Record<string, unknown>) =>
  api<AdminRecord>(`/admin/${kind}/${id}`, { method: 'PATCH', json: data })

export const deleteAdminRecord = (kind: AdminKind, id: number) =>
  api<undefined>(`/admin/${kind}/${id}`, { method: 'DELETE' })

export function importAdminCsv(kind: AdminKind, file: File) {
  const body = new FormData()
  body.append('file', file)
  return api<ImportResult>(`/admin/${kind}/import`, { method: 'POST', body })
}

export const fetchSystemStatus = () => api<SystemStatus>('/admin/system')
