// Типы ответов API. Совпадают с Pydantic-схемами backend/app/schemas.

export type Role = 'master' | 'worker' | 'boss' | 'admin'
export type Shift = 'day' | 'night'
export type Criticality = 'A' | 'B' | 'C'

export type OrderStatus =
  | 'ISSUED'
  | 'QUEUED'
  | 'ACCEPTED'
  | 'REJECTED'
  | 'IN_PROGRESS'
  | 'PAUSED'
  | 'DONE'
  | 'AI_REVIEW'
  | 'REWORK'
  | 'CLOSED'
  | 'CANCELLED'

export type Priority = 'emergency' | 'high' | 'normal' | 'planned'
export type OrderType = 'planned' | 'unplanned'
export type Verdict = 'accepted' | 'accepted_with_remarks' | 'rework'
export type CheckStatus = 'ok' | 'warn' | 'fail' | 'skip'
export type PhotoKind = 'before' | 'after'
export type PersonState = 'free' | 'busy' | 'queue' | 'off_shift'

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

export interface RefShort {
  id: number
  name: string
}

export interface EquipmentShort {
  id: number
  name: string
  inv_number: string
  section_id: number
  type: string
  criticality: Criticality
}

export interface Equipment extends EquipmentShort {
  qr_code: string | null
  external_id: string | null
}

export interface PersonShort {
  id: number
  full_name: string
  short_name: string
  specialty: string | null
}

export interface FaultCode {
  id: number
  code: string
  category: string
  name: string
  norm_hours: string | null
  norm_materials: { material_id: number; name: string; unit: string; quantity: string }[]
}

export interface Material {
  id: number
  name: string
  unit: string
  category: string | null
}

export interface OrderListItem {
  id: number
  number: number
  type: OrderType
  priority: Priority
  status: OrderStatus
  description: string
  equipment: EquipmentShort
  section: RefShort
  assignee: PersonShort | null
  master: PersonShort
  deadline_at: string
  created_at: string
  issued_at: string | null
  accepted_at: string | null
  started_at: string | null
  done_at: string | null
  closed_at: string | null
  updated_at: string
  equipment_stopped: boolean
  is_overdue: boolean
  overdue_minutes: number
  ai_score: number | null
  ai_verdict: Verdict | null
}

export interface OrderEvent {
  id: number
  action: string
  from_status: OrderStatus | null
  to_status: OrderStatus | null
  actor: PersonShort | null
  reason: string | null
  comment: string | null
  data: Record<string, unknown> | null
  created_at: string
}

export interface Photo {
  id: number
  kind: PhotoKind
  url: string
  thumb_url: string
  taken_at: string | null
  uploaded_at: string
  author_id: number | null
}

export interface Check {
  key: string
  label: string
  status: CheckStatus
  detail: string
  critical: boolean
  penalty: number
  items: string[]
}

export interface Assessment {
  id: number
  status: 'running' | 'done' | 'failed'
  mode: string
  verdict: Verdict | null
  score_0_100: number | null
  score_1_5: number | null
  confidence: number | null
  needs_master_review: boolean
  explanation_worker: string | null
  explanation_master: string | null
  checks: Check[] | null
  master_override_score: number | null
  master_comment: string | null
  final_score: number | null
  created_at: string
  finished_at: string | null
}

export interface OrderDetail extends OrderListItem {
  comment: string | null
  norm_hours: string | null
  fault_code: { id: number; code: string; name: string } | null
  works_done: string | null
  no_materials: boolean
  closing_comment: string | null
  downtime_minutes: number | null
  events: OrderEvent[]
  photos: Photo[]
  materials: { material_id: number; name: string; quantity: string; unit: string }[]
  assessment: Assessment | null
  actions: string[]
}

export interface PersonStatus {
  employee: PersonShort
  brigade_id: number | null
  on_shift: boolean
  state: PersonState
  current_order: { id: number; number: number } | null
  queue_count: number
}

export interface ShiftSummary {
  shift_start: string
  shift_end: string
  issued: number
  done: number
  overdue: number
  rejected: number
  equipment_down: number
  in_progress: number
}
