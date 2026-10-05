import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import { askAssistant, type AssistantReply } from '@/shared/api/assistant'
import { cn } from '@/shared/lib/format'
import { useSpeech } from '@/shared/lib/useSpeech'
import { Button, Drawer, Icon } from '@/shared/ui'

const TONE = {
  ok: 'bg-green',
  work: 'bg-yellow',
  queue: 'bg-queue',
  danger: 'bg-red',
  info: 'bg-accent',
} as const

type Message = { id: number; question: string; reply?: AssistantReply; error?: string }

/** Кнопка в шапке: открывает ассистента мастера. */
export function AssistantButton({ variant = 'desk' }: { variant?: 'desk' | 'phone' }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t('assistant.open')}
        className={cn(
          'inline-flex items-center gap-2 rounded-control font-semibold hover:bg-white/12 active:bg-white/12',
          variant === 'desk' ? 'min-h-10 px-3 text-small' : 'size-12 justify-center',
        )}
      >
        <Icon name="spark" size={variant === 'desk' ? 20 : 24} />
        {variant === 'desk' && t('assistant.title')}
      </button>
      {open && <AssistantDrawer onClose={() => setOpen(false)} />}
    </>
  )
}

/** Ассистент мастера (ТЗ 6.7): вопросы о смене текстом или голосом, ответы — из базы. */
function AssistantDrawer({ onClose }: { onClose: () => void }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  const ask = useMutation({
    mutationFn: (q: string) => askAssistant(q),
    onMutate: (q) => {
      const id = Date.now()
      setMessages((m) => [...m, { id, question: q }])
      return { id }
    },
    onSuccess: (reply, _q, ctx) =>
      setMessages((m) => m.map((msg) => (msg.id === ctx.id ? { ...msg, reply } : msg))),
    onError: (error: Error, _q, ctx) =>
      setMessages((m) => m.map((msg) => (msg.id === ctx?.id ? { ...msg, error: error.message } : msg))),
  })
  const send = (q: string) => {
    const text = q.trim()
    if (!text || ask.isPending) return
    setQuestion('')
    ask.mutate(text)
  }
  const speech = useSpeech(i18n.language, (text) => send(text))

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  const examples = [t('assistant.ex1'), t('assistant.ex2'), t('assistant.ex3'), t('assistant.ex4')]

  return (
    <Drawer
      open
      onClose={onClose}
      width={520}
      title={t('assistant.title')}
      subtitle={t('assistant.subtitle')}
      footer={
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            send(question)
          }}
        >
          <label className="flex-1">
            <span className="sr-only">{t('assistant.placeholder')}</span>
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={t('assistant.placeholder')}
              className="min-h-12 w-full rounded-control border-2 border-line bg-surface px-3 text-body focus:border-accent focus:outline-none"
            />
          </label>
          {speech.supported && (
            <Button
              variant={speech.listening ? 'primary' : 'secondary'}
              size="md"
              icon="mic"
              aria-label={t('assistant.voice')}
              onClick={speech.listening ? speech.stop : speech.start}
            >
              <span className="sr-only">{t('assistant.voice')}</span>
            </Button>
          )}
          <Button type="submit" size="md" icon="send" loading={ask.isPending} disabled={!question.trim()}>
            {t('assistant.ask')}
          </Button>
        </form>
      }
    >
      <div className="flex flex-col gap-4 p-5">
        {messages.length === 0 && (
          <div className="flex flex-col gap-3">
            <p className="text-ink-2">{t('assistant.hello')}</p>
            <div className="flex flex-wrap gap-2">
              {examples.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => send(ex)}
                  className="rounded-full border border-accent/40 bg-accent-soft px-3 py-1.5 text-left text-small font-medium text-accent hover:border-accent"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className="flex flex-col gap-2">
            <p className="ml-auto max-w-[85%] rounded-[14px] rounded-br-[4px] bg-accent bg-grad-primary px-3.5 py-2 text-on-accent">
              {m.question}
            </p>
            {m.error ? (
              <p role="alert" className="max-w-[90%] rounded-[14px] bg-red-soft px-3.5 py-2 text-red">
                {m.error}
              </p>
            ) : m.reply ? (
              <Answer
                reply={m.reply}
                onOpenReport={(r) => {
                  onClose()
                  navigate(`/panel/reports?${new URLSearchParams(r).toString()}`)
                }}
              />
            ) : (
              <p className="text-small text-ink-3">{t('assistant.thinking')}</p>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </Drawer>
  )
}

function Answer({ reply, onOpenReport }: { reply: AssistantReply; onOpenReport: (r: Record<string, string>) => void }) {
  const { t } = useTranslation()
  return (
    <div className="max-w-[92%] rounded-[14px] rounded-bl-[4px] border border-line bg-surface px-3.5 py-3 shadow-card">
      <p className="whitespace-pre-line">{reply.text}</p>
      {reply.items.length > 0 && (
        <ul className="mt-2 flex flex-col divide-y divide-line/70">
          {reply.items.map((item) => (
            <li key={`${item.title}-${item.subtitle}`} className="flex gap-2.5 py-1.5 text-small">
              <span aria-hidden className={cn('mt-1.5 size-2 shrink-0 rounded-full', TONE[item.tone])} />
              <span>
                <span className="font-semibold">{item.title}</span>
                {item.subtitle && <span className="text-ink-2"> — {item.subtitle}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-stamp font-normal text-ink-3">
          {reply.source === 'llm' ? t('assistant.sourceLlm') : t('assistant.sourceRules')}
        </span>
        {reply.report && (
          <Button
            variant="quiet"
            size="sm"
            icon="report"
            onClick={() =>
              onOpenReport(
                Object.fromEntries(
                  Object.entries(reply.report ?? {})
                    .filter(([, v]) => v !== null && v !== undefined)
                    .map(([k, v]) => [k, String(v)]),
                ),
              )
            }
          >
            {t('assistant.openReport')}
          </Button>
        )}
      </div>
    </div>
  )
}
