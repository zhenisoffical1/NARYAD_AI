import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'

import { Button } from './Button'
import { InvPlate } from './OrderTag'

interface EmergencyOverlayProps {
  open: boolean
  number: number
  equipment: string
  inv: string
  section: string
  description: string
  onAccept: () => void
  onReject: () => void
  busy?: boolean
}

/**
 * Аварийный наряд: на весь экран, со звуком и вибрацией.
 * Смахнуть нельзя — только «Принять в работу» или «Не могу — отклонить».
 */
export function EmergencyOverlay({
  open,
  number,
  equipment,
  inv,
  section,
  description,
  onAccept,
  onReject,
  busy = false,
}: EmergencyOverlayProps) {
  const { t } = useTranslation()
  useAlarm(open)

  useEffect(() => {
    if (!open) return
    // Кнопка «назад» на Android не закрывает аварийное уведомление
    history.pushState({ emergency: true }, '')
    const keep = () => history.pushState({ emergency: true }, '')
    window.addEventListener('popstate', keep)
    return () => window.removeEventListener('popstate', keep)
  }, [open])

  if (!open) return null
  return createPortal(
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="emergency-title"
      className="fixed inset-0 z-[60] flex flex-col bg-red-strong text-white"
    >
      <div aria-hidden className="h-4 shrink-0 hatch-red" />
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-6">
        <p className="stamp text-white/85">{t('ui.emergencyTitle')}</p>
        <h1 id="emergency-title" className="cond text-[56px] leading-none font-bold">
          №{number}
        </h1>
        <div className="flex flex-wrap items-center gap-2 text-steel">
          <InvPlate inv={inv} />
        </div>
        <p className="text-h1 font-semibold">{equipment}</p>
        <p className="text-body-lg">{section}</p>
        <p className="rounded-tag bg-white/12 p-3 text-body-lg [overflow-wrap:anywhere]">
          {description}
        </p>
      </div>
      <div className="flex flex-col gap-4 bg-red-strong px-4 pt-3 pb-[max(16px,env(safe-area-inset-bottom))]">
        <Button variant="inverse" size="xl" block onClick={onAccept} loading={busy}>
          {t('ui.emergencyAccept')}
        </Button>
        <button
          type="button"
          onClick={onReject}
          className="min-h-14 rounded-control border-2 border-white/70 text-body font-semibold"
        >
          {t('ui.emergencyReject')}
        </button>
      </div>
      <div aria-hidden className="h-4 shrink-0 hatch-red" />
    </div>,
    document.body,
  )
}

/** Сирена и вибрация, пока открыт аварийный наряд. Звук — генератор WebAudio, без файлов. */
function useAlarm(active: boolean): void {
  useEffect(() => {
    if (!active) return
    let context: AudioContext | null = null
    try {
      context = new AudioContext()
    } catch {
      context = null
    }
    const beep = () => {
      navigator.vibrate?.([300, 150, 300])
      if (!context) return
      const osc = context.createOscillator()
      const gain = context.createGain()
      osc.type = 'square'
      osc.frequency.setValueAtTime(880, context.currentTime)
      osc.frequency.setValueAtTime(660, context.currentTime + 0.25)
      gain.gain.setValueAtTime(0.18, context.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.5)
      osc.connect(gain).connect(context.destination)
      osc.start()
      osc.stop(context.currentTime + 0.5)
    }
    beep()
    const timer = window.setInterval(beep, 1500)
    return () => {
      window.clearInterval(timer)
      navigator.vibrate?.(0)
      void context?.close()
    }
  }, [active])
}
