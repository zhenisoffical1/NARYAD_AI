import { api } from './client'
import type {
  Assist,
  CompleteBody,
  OrderCreate,
  OrderDetail,
  OrderListItem,
  OrderStatus,
  Photo,
  PhotoKind,
  Priority,
} from './types'

export interface OrderQuery {
  status?: OrderStatus[]
  priority?: Priority[]
  active?: boolean
  overdue?: boolean
  section_id?: number
  equipment_id?: number
  assignee_id?: number
  created_from?: string
  sort?: 'recent' | 'urgency'
  limit?: number
}

/** Все ключи нарядов начинаются с 'orders' — живое событие обновляет их разом. */
export const orderKeys = {
  all: ['orders'] as const,
  list: (query: OrderQuery) => ['orders', 'list', query] as const,
  detail: (id: number) => ['orders', 'detail', id] as const,
}

function toSearch(query: OrderQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)))
    else params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const fetchOrders = (query: OrderQuery = {}) =>
  api<OrderListItem[]>(`/orders${toSearch(query)}`)

export const fetchOrder = (id: number) => api<OrderDetail>(`/orders/${id}`)

export const createOrder = (body: OrderCreate) =>
  api<OrderDetail>('/orders', { method: 'POST', json: body })

export const orderAction = (
  id: number,
  action: string,
  body: { reason?: string; comment?: string } = {},
) => api<OrderDetail>(`/orders/${id}/actions/${action}`, { method: 'POST', json: body })

export const completeOrder = (id: number, body: CompleteBody) =>
  api<OrderDetail>(`/orders/${id}/complete`, { method: 'POST', json: body })

export const reassignOrder = (id: number, assigneeId: number, comment?: string) =>
  api<OrderDetail>(`/orders/${id}/reassign`, {
    method: 'POST',
    json: { assignee_id: assigneeId, comment },
  })

export const changePriority = (id: number, priority: Priority, comment?: string) =>
  api<OrderDetail>(`/orders/${id}/priority`, { method: 'POST', json: { priority, comment } })

export const overrideAssessment = (id: number, score: number, comment: string) =>
  api<OrderDetail>(`/orders/${id}/assessment/override`, {
    method: 'POST',
    json: { score, comment },
  })

export function uploadPhotos(id: number, kind: PhotoKind, files: File[]): Promise<Photo[]> {
  const form = new FormData()
  files.forEach((file) => form.append('files', file, file.name))
  return api<Photo[]>(`/orders/${id}/photos?kind=${kind}`, { method: 'POST', body: form })
}

export const deletePhoto = (id: number, photoId: number) =>
  api<undefined>(`/orders/${id}/photos/${photoId}`, { method: 'DELETE' })

export const fetchAssist = (body: {
  equipment_id: number
  description: string
  priority: Priority | null
}) => api<Assist>('/orders/assist', { method: 'POST', json: body })
