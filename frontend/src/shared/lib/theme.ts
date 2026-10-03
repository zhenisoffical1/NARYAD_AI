import { useEffect } from 'react'
import { create } from 'zustand'

/** auto — тёмная в ночную смену (20:00–08:00), светлая днём. */
export type ThemeMode = 'auto' | 'light' | 'dark'

const STORAGE_KEY = 'naryad.theme'
const NIGHT_START = 20
const DAY_START = 8

function readMode(): ThemeMode {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : 'auto'
  } catch {
    return 'auto'
  }
}

export function resolveTheme(mode: ThemeMode, now = new Date()): 'light' | 'dark' {
  if (mode !== 'auto') return mode
  const hour = now.getHours()
  return hour >= NIGHT_START || hour < DAY_START ? 'dark' : 'light'
}

function apply(mode: ThemeMode): void {
  document.documentElement.dataset.theme = resolveTheme(mode)
}

export const useTheme = create<{ mode: ThemeMode; setMode: (mode: ThemeMode) => void }>(
  (set) => ({
    mode: readMode(),
    setMode: (mode) => {
      try {
        localStorage.setItem(STORAGE_KEY, mode)
      } catch {
        // Тема просто не запомнится
      }
      apply(mode)
      set({ mode })
    },
  }),
)

/** Применяет тему и в режиме «авто» переключает её на смене смен. */
export function useThemeSync(): void {
  const mode = useTheme((s) => s.mode)
  useEffect(() => {
    apply(mode)
    if (mode !== 'auto') return
    const timer = window.setInterval(() => apply(mode), 5 * 60_000)
    return () => window.clearInterval(timer)
  }, [mode])
}

apply(readMode())
