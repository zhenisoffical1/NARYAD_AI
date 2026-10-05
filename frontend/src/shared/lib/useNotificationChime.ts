import { useSession } from '@/shared/lib/session'
import { toast } from '@/shared/lib/toast'
import { useLiveEvent } from '@/shared/lib/useLiveEvents'

let context: AudioContext | null = null

/** Короткий двухтоновый сигнал (WebAudio, без файлов — работает офлайн). */
function chime(): void {
  try {
    context ??= new AudioContext()
    const now = context.currentTime
    for (const [i, freq] of [988, 1319].entries()) {
      const osc = context.createOscillator()
      const gain = context.createGain()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(freq, now + i * 0.16)
      gain.gain.setValueAtTime(0.0001, now + i * 0.16)
      gain.gain.exponentialRampToValueAtTime(0.25, now + i * 0.16 + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.16 + 0.3)
      osc.connect(gain).connect(context.destination)
      osc.start(now + i * 0.16)
      osc.stop(now + i * 0.16 + 0.32)
    }
  } catch {
    // Браузер запретил звук до первого касания — остаются вибрация и сообщение на экране
  }
}

/**
 * Новый наряд или напоминание — звук, вибрация и сообщение на экране (ТЗ 5.3: уведомление со звуком).
 * Аварийный наряд у исполнителя звучит сиреной полноэкранного оповещения, поэтому здесь пропускается.
 */
export function useNotificationChime(): void {
  const role = useSession((s) => s.user?.role)
  useLiveEvent('notification.created', (message) => {
    const urgent = message.payload.urgent === true
    if (urgent && role === 'worker') return
    chime()
    navigator.vibrate?.(urgent ? [200, 100, 200] : 120)
    const title = typeof message.payload.title === 'string' ? message.payload.title : ''
    if (title) toast(title, urgent ? 'error' : 'info')
  })
}
