import { api } from './client'

export interface AssistantReply {
  question: string
  intent: 'free_people' | 'overdue' | 'shift' | 'report' | 'analytics'
  text: string
  items: { title: string; subtitle: string; tone: 'ok' | 'work' | 'queue' | 'danger' | 'info' }[]
  /** Параметры отчёта, если ответ — сводка: можно открыть полный отчёт */
  report: { kind: string; period: string; section_id: number | null } | null
  source: 'llm' | 'rules'
}

export const askAssistant = (question: string) =>
  api<AssistantReply>('/assistant/ask', { method: 'POST', json: { question } })

export interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
}

export interface ChatReply {
  text: string
  /** llm — ответила модель; rules — ассистент на правилах (модель недоступна) */
  source: 'llm' | 'rules'
  model: string | null
  tools: string[]
  items: AssistantReply['items']
  report: AssistantReply['report']
}

export const chatAssistant = (messages: ChatTurn[]) =>
  api<ChatReply>('/assistant/chat', { method: 'POST', json: { messages } })
