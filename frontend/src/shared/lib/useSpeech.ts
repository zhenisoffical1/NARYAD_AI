import { useCallback, useEffect, useRef, useState } from 'react'

/** Минимальный тип Web Speech API — в стандартных типах TypeScript его нет. */
interface RecognitionResultEvent {
  resultIndex: number
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>
}

interface Recognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: RecognitionResultEvent) => void) | null
  onend: (() => void) | null
  onerror: ((event: { error: string }) => void) | null
  start: () => void
  stop: () => void
}

type RecognitionCtor = new () => Recognition

function recognitionCtor(): RecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor
    webkitSpeechRecognition?: RecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

/**
 * Голосовой ввод через Web Speech API (Chrome на Android). Распознанные фразы
 * добавляются к тексту через onText. Если браузер не умеет — supported=false и кнопки нет.
 */
export function useSpeech(lang: string, onText: (text: string) => void) {
  const [listening, setListening] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const recognition = useRef<Recognition | null>(null)
  const onTextRef = useRef(onText)
  useEffect(() => {
    onTextRef.current = onText
  })
  const supported = recognitionCtor() !== null

  const stop = useCallback(() => {
    recognition.current?.stop()
  }, [])

  const start = useCallback(() => {
    const Ctor = recognitionCtor()
    if (!Ctor) return
    const rec = new Ctor()
    rec.lang = lang === 'kk' ? 'kk-KZ' : 'ru-RU'
    rec.continuous = true
    rec.interimResults = false
    rec.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result?.isFinal) onTextRef.current(result[0].transcript.trim())
      }
    }
    rec.onend = () => setListening(false)
    rec.onerror = (event) => {
      setError(event.error === 'not-allowed' ? 'mic-denied' : 'failed')
      setListening(false)
    }
    recognition.current = rec
    setError(null)
    setListening(true)
    navigator.vibrate?.(20)
    rec.start()
  }, [lang])

  useEffect(() => () => recognition.current?.stop(), [])

  return { supported, listening, error, start, stop }
}
