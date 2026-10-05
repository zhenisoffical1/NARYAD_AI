import i18n from '@/i18n'
import { useSession } from '@/shared/lib/session'

import { api, ApiError } from './client'

// --- аналитика -------------------------------------------------------------------------

export interface SeriesPoint {
  label: string
  value: number
  accent: boolean
}

export interface Insight {
  kind: string
  title: string
  subject: string
  severity: 'high' | 'medium' | 'info'
  facts: string
  conclusion: string
  recommendation: string
  numbers: Record<string, string | number | null>
  series: SeriesPoint[]
  chart: 'bars' | 'weeks' | 'pair'
  refs: { equipment_id?: number; section_id?: number; worker_id?: number }
  source: 'llm' | 'rules'
}

export interface AnalyticsResult {
  scope_label: string
  days: number
  section_id: number | null
  equipment_id: number | null
  items: Insight[]
}

export interface AnswerResult extends AnalyticsResult {
  question: string
  source: 'llm' | 'rules'
}

export const analyticsKeys = {
  list: (days: number, section: number | null) => ['analytics', days, section] as const,
}

export function fetchAnalytics(days: number, sectionId: number | null) {
  const params = new URLSearchParams({ days: String(days) })
  if (sectionId) params.set('section_id', String(sectionId))
  return api<AnalyticsResult>(`/analytics?${params}`)
}

export const askAnalytics = (question: string) =>
  api<AnswerResult>('/analytics/ask', { method: 'POST', json: { question } })

// --- дашборд руководителя ----------------------------------------------------------------

export interface Dashboard {
  days: number
  in_work: number
  overdue_now: number
  issued: number
  done: number
  overdue_share: number
  reaction_minutes: number | null
  completion_hours: number | null
  downtime_hours: number
  unplanned_share: number
  trend: { label: string; value: number }[]
  top_equipment: {
    equipment_id: number
    name: string
    section: string
    unplanned: number
    downtime_hours: number
  }[]
  best_workers: { employee_id: number; name: string; score: number; orders: number }[]
}

export const dashboardKeys = {
  get: (days: number, section: number | null) => ['dashboard', days, section] as const,
}

export function fetchDashboard(days: number, sectionId: number | null) {
  const params = new URLSearchParams({ days: String(days) })
  if (sectionId) params.set('section_id', String(sectionId))
  return api<Dashboard>(`/dashboard?${params}`)
}

// --- отчёты -----------------------------------------------------------------------------

export type ReportKind = 'orders' | 'rating' | 'materials' | 'downtime'
export type ReportPeriod = 'shift' | 'day' | 'week' | 'month' | 'custom'

export interface ReportColumn {
  key: string
  title: string
  align: 'left' | 'right'
  width: number
}

export interface Report {
  kind: string
  title: string
  period_label: string
  generated_at: string
  kpis: { label: string; value: string; tone: 'default' | 'danger' | 'ok' }[]
  summary: string | null
  summary_source: 'llm' | 'rules' | null
  tables: {
    title: string
    columns: ReportColumn[]
    rows: Record<string, string | number | null>[]
    note: string | null
    highlight: string | null
  }[]
  filters: string | null
}

export interface ReportQuery {
  kind: ReportKind
  period: ReportPeriod
  dateFrom?: string
  dateTo?: string
  sectionId?: number | null
  equipmentId?: number | null
  employeeId?: number | null
  brigadeId?: number | null
}

function reportParams(q: ReportQuery, format: 'json' | 'xlsx' | 'pdf'): string {
  const params = new URLSearchParams({ period: q.period, format })
  if (q.period === 'custom' && q.dateFrom && q.dateTo) {
    params.set('date_from', q.dateFrom)
    params.set('date_to', q.dateTo)
  }
  if (q.sectionId) params.set('section_id', String(q.sectionId))
  if (q.equipmentId) params.set('equipment_id', String(q.equipmentId))
  if (q.employeeId) params.set('employee_id', String(q.employeeId))
  if (q.brigadeId) params.set('brigade_id', String(q.brigadeId))
  return `/reports/${q.kind}?${params}`
}

export const reportKeys = { get: (q: ReportQuery) => ['report', q] as const }

export const fetchReport = (q: ReportQuery) => api<Report>(reportParams(q, 'json'))

/** Скачать файл отчёта с токеном (обычная ссылка не передаст заголовок авторизации). */
export async function downloadReport(path: string): Promise<void> {
  const token = useSession.getState().token
  const response = await fetch(`/api${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null)
    const detail =
      data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string'
        ? data.detail
        : i18n.t('errors.server', { status: response.status })
    throw new ApiError(response.status, detail)
  }
  const disposition = response.headers.get('content-disposition') ?? ''
  const encoded = /filename\*=UTF-8''([^;]+)/.exec(disposition)?.[1]
  const name = encoded ? decodeURIComponent(encoded) : 'report'
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

export const reportFile = (q: ReportQuery, format: 'xlsx' | 'pdf') => reportParams(q, format)
