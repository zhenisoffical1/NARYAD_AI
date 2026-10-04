import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  fetchEquipment,
  fetchEquipmentByQr,
  fetchRecentEquipment,
  fetchSections,
  REFERENCE_STALE,
  refKeys,
} from '@/shared/api/reference'
import type { Equipment } from '@/shared/api/types'
import { cn } from '@/shared/lib/format'
import { toast } from '@/shared/lib/toast'
import { BottomSheet, Button, Icon, InvPlate } from '@/shared/ui'

interface BarcodeDetectorLike {
  detect: (source: HTMLVideoElement) => Promise<{ rawValue: string }[]>
}
type BarcodeDetectorCtor = new (options: { formats: string[] }) => BarcodeDetectorLike

function barcodeDetector(): BarcodeDetectorCtor | null {
  return (window as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector ?? null
}

/** Выбор оборудования: недавние одним нажатием, поиск по названию/инв. номеру, QR-код. */
export function EquipmentPicker({
  value,
  onChange,
  error,
}: {
  value: Equipment | null
  onChange: (equipment: Equipment | null) => void
  error?: string | null
}) {
  const { t } = useTranslation()
  const [searching, setSearching] = useState(false)
  const [scanning, setScanning] = useState(false)
  const recent = useQuery({ queryKey: refKeys.recentEquipment, queryFn: fetchRecentEquipment })
  const sections = useQuery({ queryKey: refKeys.sections, queryFn: fetchSections, staleTime: REFERENCE_STALE })
  const sectionName = (id: number) => sections.data?.find((s) => s.id === id)?.name ?? ''

  if (value) {
    return (
      <div className="flex items-start justify-between gap-3 rounded-[8px] border-2 border-accent bg-surface p-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <InvPlate inv={value.inv_number} />
          </div>
          <p className="mt-1.5 font-semibold [overflow-wrap:anywhere]">{value.name}</p>
          <p className="text-small text-ink-2">
            {sectionName(value.section_id)} · <span className="text-ink-3">{t('issue.sectionAuto')}</span>
          </p>
        </div>
        <Button size="sm" variant="secondary" className="shrink-0" onClick={() => onChange(null)}>
          {t('issue.change')}
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2.5">
      {recent.data && recent.data.length > 0 && (
        <>
          <p className="text-small text-ink-3">{t('issue.recent')}</p>
          <div className="grid grid-cols-2 gap-2">
            {recent.data.slice(0, 6).map((eq) => (
              <button
                key={eq.id}
                type="button"
                onClick={() => onChange(eq)}
                className="flex min-h-16 flex-col items-start justify-center gap-1 rounded-control border-2 border-line bg-surface px-3 py-2 text-left active:border-accent active:bg-queue-soft"
              >
                <span className="cond text-small font-semibold text-ink-2">{eq.inv_number}</span>
                <span className="line-clamp-2 text-small leading-tight font-medium">{eq.name}</span>
              </button>
            ))}
          </div>
        </>
      )}
      <div className="flex gap-2">
        <Button
          variant="secondary"
          icon="search"
          className={cn('flex-1', error && 'border-red text-red')}
          onClick={() => setSearching(true)}
        >
          {t('issue.find')}
        </Button>
        {barcodeDetector() && (
          <Button variant="secondary" icon="qr" onClick={() => setScanning(true)} aria-label={t('issue.scanTitle')}>
            {t('issue.qr')}
          </Button>
        )}
      </div>
      {error && (
        <p className="text-small font-medium text-red" role="alert">
          {error}
        </p>
      )}
      {searching && (
        <SearchSheet
          onClose={() => setSearching(false)}
          onPick={(eq) => {
            onChange(eq)
            setSearching(false)
          }}
          sectionName={sectionName}
        />
      )}
      {scanning && (
        <QrSheet
          onClose={() => setScanning(false)}
          onPick={(eq) => {
            onChange(eq)
            setScanning(false)
          }}
        />
      )}
    </div>
  )
}

function SearchSheet({
  onClose,
  onPick,
  sectionName,
}: {
  onClose: () => void
  onPick: (eq: Equipment) => void
  sectionName: (id: number) => string
}) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const all = useQuery({ queryKey: refKeys.equipment, queryFn: fetchEquipment, staleTime: REFERENCE_STALE })

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase()
    const items = (all.data ?? []).filter(
      (e) => !q || e.name.toLowerCase().includes(q) || e.inv_number.toLowerCase().includes(q),
    )
    const map = new Map<number, Equipment[]>()
    items.forEach((e) => map.set(e.section_id, [...(map.get(e.section_id) ?? []), e]))
    return [...map.entries()]
  }, [all.data, query])

  return (
    <BottomSheet open title={t('issue.find')} onClose={onClose}>
      <div className="sticky top-0 -mx-4 -mt-3 mb-2 bg-surface px-4 pt-3 pb-2">
        <label className="flex min-h-14 items-center gap-2 rounded-control border-2 border-line px-3 focus-within:border-accent">
          <Icon name="search" className="text-ink-3" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('issue.search')}
            aria-label={t('issue.search')}
            className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-ink-3"
          />
        </label>
      </div>
      {groups.map(([sectionId, items]) => (
        <section key={sectionId} className="mb-3">
          <p className="py-1 text-small font-semibold text-ink-3">{sectionName(sectionId)}</p>
          <ul>
            {items.map((eq) => (
              <li key={eq.id}>
                <button
                  type="button"
                  onClick={() => onPick(eq)}
                  className="flex min-h-14 w-full items-center gap-3 border-b border-line py-2 text-left active:bg-plate"
                >
                  <span className="cond w-16 shrink-0 text-small font-semibold text-ink-2">{eq.inv_number}</span>
                  <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{eq.name}</span>
                  <span className="stamp shrink-0 text-ink-3">{eq.criticality}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {groups.length === 0 && all.isSuccess && <p className="py-6 text-center text-ink-2">{t('ui.nothingFound')}</p>}
    </BottomSheet>
  )
}

function QrSheet({ onClose, onPick }: { onClose: () => void; onPick: (eq: Equipment) => void }) {
  const { t } = useTranslation()
  const video = useRef<HTMLVideoElement>(null)
  const [failed, setFailed] = useState(false)
  const onPickRef = useRef(onPick)
  useEffect(() => {
    onPickRef.current = onPick
  })

  useEffect(() => {
    const Detector = barcodeDetector()
    if (!Detector) return
    const detector = new Detector({ formats: ['qr_code'] })
    let stream: MediaStream | null = null
    let timer: number | undefined
    let stopped = false

    const scan = async () => {
      if (stopped || !video.current) return
      try {
        const [code] = await detector.detect(video.current)
        if (code?.rawValue) {
          stopped = true
          navigator.vibrate?.(40)
          try {
            onPickRef.current(await fetchEquipmentByQr(code.rawValue))
          } catch {
            toast(t('issue.scanNotFound'), 'error')
            stopped = false
          }
        }
      } catch {
        // кадр не готов — попробуем следующий
      }
      if (!stopped) timer = window.setTimeout(scan, 250)
    }

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        stream = s
        if (video.current) {
          video.current.srcObject = s
          void video.current.play()
        }
        void scan()
      })
      .catch(() => setFailed(true))

    return () => {
      stopped = true
      window.clearTimeout(timer)
      stream?.getTracks().forEach((track) => track.stop())
    }
  }, [t])

  return (
    <BottomSheet open title={t('issue.scanTitle')} onClose={onClose}>
      {failed ? (
        <p className="py-6 text-center text-ink-2">{t('issue.scanUnsupported')}</p>
      ) : (
        <div className="relative aspect-square w-full overflow-hidden rounded-[8px] bg-black">
          <video ref={video} playsInline muted className="size-full object-cover" />
          <span aria-hidden className="absolute inset-[18%] rounded-[12px] border-4 border-white/85" />
        </div>
      )}
    </BottomSheet>
  )
}
