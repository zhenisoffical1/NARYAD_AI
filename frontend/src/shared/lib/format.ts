/** Время и длительности для интерфейса. Время показывается в поясе устройства. */

export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ')
}

export function hhmm(iso: string | Date): string {
  const date = typeof iso === 'string' ? new Date(iso) : iso
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

export function ddmm(iso: string | Date): string {
  const date = typeof iso === 'string' ? new Date(iso) : iso
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

/** «0:42», «12:05» — часы:минуты для таймеров. */
export function clock(minutes: number): string {
  const total = Math.max(0, Math.round(minutes))
  const h = Math.floor(total / 60)
  const m = total % 60
  return `${h}:${m.toString().padStart(2, '0')}`
}

/** «1 ч 40 мин», «25 мин». */
export function duration(minutes: number): string {
  const total = Math.max(0, Math.round(minutes))
  const h = Math.floor(total / 60)
  const m = total % 60
  if (h && m) return `${h} ч ${m} мин`
  if (h) return `${h} ч`
  return `${m} мин`
}

export function minutesUntil(iso: string, now = Date.now()): number {
  return (new Date(iso).getTime() - now) / 60_000
}

export function isToday(iso: string, now = new Date()): boolean {
  const date = new Date(iso)
  return date.toDateString() === now.toDateString()
}
