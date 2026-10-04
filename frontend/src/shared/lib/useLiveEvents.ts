import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { create } from 'zustand'

import type { LiveMessage } from '@/shared/api/types'
import { useSession } from '@/shared/lib/session'

export type LiveStatus = 'connecting' | 'online' | 'offline'

export const useLiveStatus = create<{ status: LiveStatus }>(() => ({ status: 'connecting' }))

/** Когда наряд последний раз менялся по живому событию — для краткой подсветки карточки. */
export const useRecentChanges = create<{ changed: Record<number, number> }>(() => ({ changed: {} }))

type Listener = (message: LiveMessage) => void
const listeners = new Set<Listener>()

const PING_INTERVAL_MS = 25_000
const MAX_BACKOFF_MS = 10_000

function socketUrl(token: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws?token=${encodeURIComponent(token)}`
}

function orderIdOf(message: LiveMessage): number | null {
  const id = message.payload.order_id
  return typeof id === 'number' ? id : null
}

/**
 * Держит одно WebSocket-соединение на всё приложение: переподключается с нарастающей
 * паузой, после переподключения перезапрашивает данные (вдруг что-то пропустили),
 * на каждое событие обновляет кэш запросов и оповещает подписчиков useLiveEvent.
 * Вызывается один раз — в разметке защищённых маршрутов.
 */
export function useLiveEvents(): void {
  const token = useSession((s) => s.token)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!token) return
    let socket: WebSocket | null = null
    let attempt = 0
    let reconnectTimer: number | undefined
    let pingTimer: number | undefined
    let stopped = false
    let wasConnected = false

    const connect = () => {
      useLiveStatus.setState({ status: attempt === 0 ? 'connecting' : 'offline' })
      socket = new WebSocket(socketUrl(token))

      socket.onopen = () => {
        attempt = 0
        useLiveStatus.setState({ status: 'online' })
        if (wasConnected) void queryClient.invalidateQueries()
        wasConnected = true
        pingTimer = window.setInterval(() => socket?.send('ping'), PING_INTERVAL_MS)
      }

      socket.onmessage = (event: MessageEvent<string>) => {
        if (event.data === 'pong') return
        let message: LiveMessage
        try {
          message = JSON.parse(event.data) as LiveMessage
        } catch {
          return
        }
        if (message.type.startsWith('order.') || message.type === 'assessment.done') {
          void queryClient.invalidateQueries({ queryKey: ['orders'] })
          void queryClient.invalidateQueries({ queryKey: ['shift'] })
          const id = orderIdOf(message)
          if (id !== null) markChanged(id)
        }
        if (message.type === 'demo.reset') void queryClient.invalidateQueries()
        if (message.type === 'notification.created') {
          void queryClient.invalidateQueries({ queryKey: ['notifications'] })
        }
        listeners.forEach((listener) => listener(message))
      }

      socket.onclose = () => {
        window.clearInterval(pingTimer)
        if (stopped) return
        useLiveStatus.setState({ status: 'offline' })
        const delay = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** attempt)
        attempt += 1
        reconnectTimer = window.setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(reconnectTimer)
      window.clearInterval(pingTimer)
      socket?.close()
    }
  }, [token, queryClient])
}

/** Подписка на живые события: тип события или '*' для всех. */
export function useLiveEvent(type: string, handler: Listener): void {
  const handlerRef = useRef(handler)
  useEffect(() => {
    handlerRef.current = handler
  })

  useEffect(() => {
    const listener: Listener = (message) => {
      if (type === '*' || message.type === type) handlerRef.current(message)
    }
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  }, [type])
}

const HIGHLIGHT_MS = 1600

function markChanged(orderId: number): void {
  const at = Date.now()
  useRecentChanges.setState((s) => ({ changed: { ...s.changed, [orderId]: at } }))
  window.setTimeout(() => {
    useRecentChanges.setState((s) => {
      if (s.changed[orderId] !== at) return s
      return {
        changed: Object.fromEntries(
          Object.entries(s.changed).filter(([id]) => Number(id) !== orderId),
        ),
      }
    })
  }, HIGHLIGHT_MS)
}

/** Метка последнего живого изменения наряда (или undefined). Как ключ — перезапускает подсветку. */
export function useHighlight(orderId: number): number | undefined {
  return useRecentChanges((s) => s.changed[orderId])
}
