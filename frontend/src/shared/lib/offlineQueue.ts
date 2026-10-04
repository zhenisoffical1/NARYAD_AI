import { create } from 'zustand'

import { ApiError } from '@/shared/api/client'
import { orderAction } from '@/shared/api/orders'

/**
 * Офлайн-очередь действий исполнителя (в цеху и в карьере связь пропадает).
 *
 * Действие без сети не теряется: оно ложится в IndexedDB, на экране видно «ожидает
 * отправки», а при появлении сети уходит на сервер в том же порядке. Если сервер ответил
 * отказом (наряд уже переназначен, отменён) — действие снимается с очереди с понятной ошибкой.
 */

export interface PendingAction {
  id: string
  orderId: number
  number: number
  action: string
  reason?: string
  comment?: string
  createdAt: number
}

/** Действия, которые безопасно отложить: они не зависят от фото и формы закрытия. */
export const OFFLINE_ACTIONS = new Set(['accept', 'queue', 'reject', 'start', 'pause', 'resume', 'resume_rework'])

const DB_NAME = 'naryad-offline'
const STORE = 'actions'

export const usePending = create<{ items: PendingAction[] }>(() => ({ items: [] }))

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: 'id' })
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('IndexedDB недоступна'))
  })
}

async function tx<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb()
  try {
    return await new Promise<T>((resolve, reject) => {
      const request = run(db.transaction(STORE, mode).objectStore(STORE))
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error ?? new Error('Ошибка IndexedDB'))
    })
  } finally {
    db.close()
  }
}

async function readAll(): Promise<PendingAction[]> {
  const items = await tx<PendingAction[]>('readonly', (s) => s.getAll() as IDBRequest<PendingAction[]>)
  return items.sort((a, b) => a.createdAt - b.createdAt)
}

export async function loadPending(): Promise<void> {
  try {
    usePending.setState({ items: await readAll() })
  } catch {
    // Приватный режим или запрет хранилища — очередь просто недоступна
  }
}

export async function enqueue(item: Omit<PendingAction, 'id' | 'createdAt'>): Promise<void> {
  const pending: PendingAction = { ...item, id: crypto.randomUUID(), createdAt: Date.now() }
  await tx('readwrite', (s) => s.put(pending))
  await loadPending()
}

async function remove(id: string): Promise<void> {
  await tx('readwrite', (s) => s.delete(id))
}

let flushing = false

/**
 * Отправить очередь по порядку. Возвращает отправленные и отклонённые сервером действия.
 * Без сети останавливается на первом же действии — порядок для одного наряда важен.
 */
export async function flushPending(): Promise<{ sent: PendingAction[]; rejected: [PendingAction, string][] }> {
  const sent: PendingAction[] = []
  const rejected: [PendingAction, string][] = []
  if (flushing) return { sent, rejected }
  flushing = true
  try {
    for (const item of await readAll()) {
      try {
        await orderAction(item.orderId, item.action, { reason: item.reason, comment: item.comment })
        sent.push(item)
      } catch (error) {
        if (error instanceof ApiError && error.status === 0) break // связи всё ещё нет
        rejected.push([item, error instanceof Error ? error.message : String(error)])
      }
      await remove(item.id)
    }
  } finally {
    flushing = false
    await loadPending()
  }
  return { sent, rejected }
}

export function isOffline(error: unknown): boolean {
  return error instanceof ApiError && error.status === 0
}
