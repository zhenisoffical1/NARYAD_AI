import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/shared/lib/format'
import { compressPhoto, type PickedPhoto } from '@/shared/lib/photos'

import { Icon } from './Icon'

interface PhotoPickerProps {
  value: PickedPhoto[]
  onChange: (photos: PickedPhoto[]) => void
  max?: number
  label: string
  required?: boolean
  error?: string | null
  /** Идёт сжатие выбранных фото — форма должна дождаться, прежде чем отправлять */
  onBusyChange?: (busy: boolean) => void
}

export function PhotoPicker({
  value,
  onChange,
  max = 5,
  label,
  required,
  error,
  onBusyChange,
}: PhotoPickerProps) {
  const { t } = useTranslation()
  const camera = useRef<HTMLInputElement>(null)
  const gallery = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const latest = useRef(value)
  useEffect(() => {
    latest.current = value
  })

  const add = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    onBusyChange?.(true)
    try {
      const room = max - latest.current.length
      const picked = await Promise.all(
        Array.from(files)
          .slice(0, room)
          .map(async (file) => {
            const compressed = await compressPhoto(file).catch(() => file)
            return { id: crypto.randomUUID(), file: compressed, url: URL.createObjectURL(compressed) }
          }),
      )
      onChange([...latest.current, ...picked])
    } finally {
      setBusy(false)
      onBusyChange?.(false)
      if (camera.current) camera.current.value = ''
      if (gallery.current) gallery.current.value = ''
    }
  }

  const remove = (id: string) => {
    const photo = value.find((p) => p.id === id)
    if (photo) URL.revokeObjectURL(photo.url)
    onChange(value.filter((p) => p.id !== id))
  }

  const full = value.length >= max
  const tile =
    'flex size-[88px] shrink-0 flex-col items-center justify-center gap-1 rounded-control border-2 border-dashed text-small font-semibold'

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-end justify-between">
        <span className="text-small font-semibold text-ink-2">
          {label}
          {required && <span className="text-red"> *</span>}
        </span>
        <span className="cond text-small text-ink-3">
          {t('ui.photosCount', { count: value.length, max })}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {value.map((photo) => (
          <div key={photo.id} className="relative size-[88px] overflow-hidden rounded-control bg-plate">
            <img src={photo.url} alt="" className="size-full object-cover" />
            <button
              type="button"
              onClick={() => remove(photo.id)}
              aria-label={t('ui.removePhoto')}
              className="absolute top-0 right-0 inline-flex size-10 items-start justify-end p-1"
            >
              <span className="inline-flex size-7 items-center justify-center rounded-full bg-steel/85 text-on-steel">
                <Icon name="x" size={16} />
              </span>
            </button>
          </div>
        ))}
        {!full && (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={() => camera.current?.click()}
              className={cn(tile, error ? 'border-red text-red' : 'border-ink-2 text-ink')}
            >
              <Icon name="camera" size={28} />
              {busy ? '…' : t('ui.camera')}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => gallery.current?.click()}
              className={cn(tile, 'border-line text-ink-2')}
            >
              <Icon name="image" size={28} />
              {t('ui.gallery')}
            </button>
          </>
        )}
      </div>
      {busy && <p className="text-small text-ink-2">{t('ui.compressing')}</p>}
      {full && <p className="text-small text-ink-3">{t('ui.photosLimit', { max })}</p>}
      {error && (
        <p className="text-small font-medium text-red" role="alert">
          {error}
        </p>
      )}
      <input
        ref={camera}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => void add(e.target.files)}
      />
      <input
        ref={gallery}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => void add(e.target.files)}
      />
    </div>
  )
}
