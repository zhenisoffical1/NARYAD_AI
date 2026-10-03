import { create } from 'zustand'

export type ToastTone = 'ok' | 'error' | 'info'

export interface ToastItem {
  id: number
  text: string
  tone: ToastTone
}

export const useToasts = create<{ items: ToastItem[] }>(() => ({ items: [] }))
let nextId = 1

/** Короткое сообщение о результате действия. Ошибки висят дольше. */
export function toast(text: string, tone: ToastTone = 'ok'): void {
  const id = nextId++
  useToasts.setState((s) => ({ items: [...s.items.slice(-2), { id, text, tone }] }))
  if (tone !== 'info') navigator.vibrate?.(tone === 'error' ? [40, 60, 40] : 25)
  window.setTimeout(
    () => useToasts.setState((s) => ({ items: s.items.filter((i) => i.id !== id) })),
    tone === 'error' ? 6000 : 3500,
  )
}
