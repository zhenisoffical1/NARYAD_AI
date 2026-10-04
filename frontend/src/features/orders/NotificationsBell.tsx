import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import {
  fetchNotifications,
  markNotificationsRead,
  notificationKeys,
} from '@/shared/api/reference'
import { cn, ddmm, hhmm, isToday } from '@/shared/lib/format'
import { useSession } from '@/shared/lib/session'
import { BottomSheet, Button, EmptyState, Icon } from '@/shared/ui'

import { orderPath } from './paths'

/** Колокольчик в шапке: лента уведомлений PWA (дублирует Telegram). */
export function NotificationsBell({ tone = 'bar' }: { tone?: 'bar' | 'surface' }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const role = useSession((s) => s.user?.role)
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const feed = useQuery({ queryKey: notificationKeys.feed, queryFn: fetchNotifications })
  const unread = feed.data?.unread ?? 0

  const readAll = useMutation({
    mutationFn: () => markNotificationsRead(),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: notificationKeys.feed }),
  })

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`${t('notifications.title')}${unread ? `: ${unread}` : ''}`}
        className={cn(
          'relative inline-flex size-12 items-center justify-center rounded-control',
          tone === 'bar' ? 'active:bg-white/10' : 'text-ink-2 hover:bg-plate',
        )}
      >
        <Icon name="bell" size={24} />
        {unread > 0 && (
          <span className="cond absolute top-1.5 right-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-strong px-1 text-stamp text-white ring-2 ring-bar">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      <BottomSheet
        open={open}
        title={t('notifications.title')}
        onClose={() => setOpen(false)}
        footer={
          unread > 0 ? (
            <Button variant="secondary" block onClick={() => readAll.mutate()} loading={readAll.isPending}>
              {t('notifications.markAll')}
            </Button>
          ) : undefined
        }
      >
        {feed.data && feed.data.items.length === 0 && (
          <EmptyState icon="bell" title={t('notifications.empty')} hint={t('notifications.emptyHint')} />
        )}
        <ul className="flex flex-col divide-y divide-line">
          {feed.data?.items.map((note) => (
            <li key={note.id}>
              <button
                type="button"
                disabled={!note.order_id || !role}
                onClick={() => {
                  if (!note.order_id || !role) return
                  setOpen(false)
                  navigate(orderPath(role, note.order_id))
                }}
                className="flex w-full gap-3 py-3 text-left"
              >
                <span
                  aria-hidden
                  className={cn('mt-2 size-2 shrink-0 rounded-full', note.read_at ? 'bg-transparent' : 'bg-accent')}
                />
                <span className="min-w-0 flex-1">
                  <span className={cn('block', note.read_at ? 'font-medium text-ink-2' : 'font-semibold')}>
                    {note.title}
                  </span>
                  <span className="mt-0.5 block whitespace-pre-line text-small text-ink-2 [overflow-wrap:anywhere]">
                    {note.body}
                  </span>
                </span>
                <span className="cond shrink-0 text-small text-ink-3">
                  {isToday(note.created_at) ? hhmm(note.created_at) : ddmm(note.created_at)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </BottomSheet>
    </>
  )
}
