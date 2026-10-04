import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'

import type { Photo } from '@/shared/api/types'
import { hhmm } from '@/shared/lib/format'

import { Icon } from './Icon'

/** Миниатюры фото наряда; по нажатию — во весь экран с листанием. */
export function PhotoStrip({ photos, label }: { photos: Photo[]; label?: string }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState<number | null>(null)
  if (photos.length === 0) return null
  const current = open !== null ? photos[open] : undefined

  return (
    <div className="flex flex-col gap-2">
      {label && <p className="text-small font-semibold text-ink-2">{label}</p>}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {photos.map((photo, i) => (
          <button
            key={photo.id}
            type="button"
            onClick={() => setOpen(i)}
            className="relative size-24 shrink-0 overflow-hidden rounded-[6px] bg-plate"
            aria-label={`${t('ui.photo')} ${i + 1}`}
          >
            <img src={photo.thumb_url} alt="" className="size-full object-cover" loading="lazy" />
            {photo.taken_at && (
              <span className="cond absolute right-1 bottom-1 rounded-[3px] bg-steel/80 px-1 text-stamp text-white">
                {hhmm(photo.taken_at)}
              </span>
            )}
          </button>
        ))}
      </div>
      {current &&
        open !== null &&
        createPortal(
          <div
            role="dialog"
            aria-modal="true"
            className="fixed inset-0 z-50 flex flex-col bg-black/95 text-white"
            onClick={() => setOpen(null)}
          >
            <div className="flex items-center justify-between px-4 pt-[max(12px,env(safe-area-inset-top))] pb-2">
              <span className="cond text-small">
                {open + 1} / {photos.length}
              </span>
              <button
                type="button"
                className="inline-flex size-12 items-center justify-center"
                aria-label={t('common.close')}
              >
                <Icon name="x" size={28} />
              </button>
            </div>
            <div className="flex flex-1 items-center justify-center p-2">
              <img src={current.url} alt="" className="max-h-full max-w-full object-contain" />
            </div>
            {photos.length > 1 && (
              <div className="flex justify-center gap-4 pb-[max(16px,env(safe-area-inset-bottom))]">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setOpen((open - 1 + photos.length) % photos.length)
                  }}
                  className="inline-flex size-14 items-center justify-center rounded-full bg-white/15"
                  aria-label={t('common.back')}
                >
                  <Icon name="chevronLeft" size={28} />
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setOpen((open + 1) % photos.length)
                  }}
                  className="inline-flex size-14 items-center justify-center rounded-full bg-white/15"
                  aria-label={t('ui.next')}
                >
                  <Icon name="chevronRight" size={28} />
                </button>
              </div>
            )}
          </div>,
          document.body,
        )}
    </div>
  )
}
