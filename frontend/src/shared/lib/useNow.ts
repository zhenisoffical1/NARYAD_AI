import { useEffect, useState } from 'react'

/** Текущее время с обновлением раз в `interval` мс (null — не обновлять). */
export function useNow(interval: number | null): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (interval === null) return
    const timer = window.setInterval(() => setNow(Date.now()), interval)
    return () => window.clearInterval(timer)
  }, [interval])
  return now
}
