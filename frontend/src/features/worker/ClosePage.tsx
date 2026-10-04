import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { completeOrder, fetchOrder, orderKeys, uploadPhotos } from '@/shared/api/orders'
import {
  fetchFaultCodes,
  fetchMaterials,
  REFERENCE_STALE,
  refKeys,
} from '@/shared/api/reference'
import type { FaultCode, Material, OrderDetail } from '@/shared/api/types'
import { duration } from '@/shared/lib/format'
import type { PickedPhoto } from '@/shared/lib/photos'
import { toast } from '@/shared/lib/toast'
import { useSpeech } from '@/shared/lib/useSpeech'
import {
  ActionBar,
  Button,
  Icon,
  Panel,
  PhotoPicker,
  Select,
  Stepper,
  TagSkeleton,
  TextArea,
  ToggleRow,
  TopBar,
} from '@/shared/ui'

interface Line {
  material_id: number
  quantity: number
}

interface Draft {
  works: string
  codeId: number | null
  lines: Line[]
  noMaterials: boolean
  comment: string
}

const draftKey = (id: number) => `naryad.draft.${id}`

function loadDraft(id: number): Draft | null {
  try {
    const raw = localStorage.getItem(draftKey(id))
    return raw ? (JSON.parse(raw) as Draft) : null
  } catch {
    return null
  }
}

function saveDraft(id: number, draft: Draft): void {
  try {
    localStorage.setItem(draftKey(id), JSON.stringify(draft))
  } catch {
    // Черновик просто не сохранится — форма продолжит работать
  }
}

function clearDraft(id: number): void {
  try {
    localStorage.removeItem(draftKey(id))
  } catch {
    // нечего удалять
  }
}

/** Шаг количества по единице: штуки по одной, литры и килограммы по половине. */
function stepFor(unit: string): number {
  return unit === 'шт' || unit === 'м' ? 1 : 0.5
}

export function ClosePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const orderId = Number(useParams().id)
  const detail = useQuery({ queryKey: orderKeys.detail(orderId), queryFn: () => fetchOrder(orderId) })
  const codes = useQuery({ queryKey: refKeys.faultCodes, queryFn: fetchFaultCodes, staleTime: REFERENCE_STALE })
  const materials = useQuery({ queryKey: refKeys.materials, queryFn: fetchMaterials, staleTime: REFERENCE_STALE })

  return (
    <div className="flex min-h-dvh flex-col bg-bg">
      <TopBar
        title={detail.data ? t('close.title', { n: detail.data.number }) : '…'}
        subtitle={detail.data?.equipment.name}
        onBack={() => navigate(`/w/orders/${orderId}`)}
      />
      {detail.data && codes.data && materials.data ? (
        <CloseForm order={detail.data} codes={codes.data} materials={materials.data} />
      ) : (
        <main className="p-4">
          <TagSkeleton />
        </main>
      )}
    </div>
  )
}

function CloseForm({
  order,
  codes,
  materials,
}: {
  order: OrderDetail
  codes: FaultCode[]
  materials: Material[]
}) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [restored] = useState(() => loadDraft(order.id))
  const [works, setWorks] = useState(() => restored?.works ?? order.works_done ?? '')
  const [codeId, setCodeId] = useState<number | null>(
    () => restored?.codeId ?? order.fault_code?.id ?? null,
  )
  const [lines, setLines] = useState<Line[]>(() => restored?.lines ?? [])
  const [noMaterials, setNoMaterials] = useState(() => restored?.noMaterials ?? false)
  const [comment, setComment] = useState(() => restored?.comment ?? '')
  const [photos, setPhotos] = useState<PickedPhoto[]>([])
  const [photoWarned, setPhotoWarned] = useState(false)
  const [uploaded, setUploaded] = useState<Set<string>>(new Set())
  const [progress, setProgress] = useState<string | null>(null)
  const [showMissing, setShowMissing] = useState(false)

  const speech = useSpeech(i18n.language, (text) =>
    setWorks((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text)),
  )

  useEffect(() => {
    if (restored) toast(t('close.draftRestored'), 'info')
  }, [restored, t])

  useEffect(() => {
    saveDraft(order.id, { works, codeId, lines, noMaterials, comment })
  }, [order.id, works, codeId, lines, noMaterials, comment])

  const byId = useMemo(() => new Map(materials.map((m) => [m.id, m])), [materials])
  const code = codes.find((c) => c.id === codeId)
  const afterExisting = order.photos.filter((p) => p.kind === 'after').length
  const photoRequired = order.type === 'unplanned'
  const hasPhoto = afterExisting + photos.length > 0

  const missing = [
    works.trim().length < 3 && t('close.missingWorks'),
    !codeId && t('close.missingCode'),
    !noMaterials && lines.length === 0 && t('close.missingMaterials'),
  ].filter(Boolean) as string[]

  const addLine = (materialId: number, quantity?: number) => {
    setNoMaterials(false)
    setLines((prev) =>
      prev.some((l) => l.material_id === materialId)
        ? prev
        : [...prev, { material_id: materialId, quantity: quantity ?? stepFor(byId.get(materialId)?.unit ?? 'шт') }],
    )
  }

  const submit = useMutation({
    mutationFn: async () => {
      const pending = photos.filter((p) => !uploaded.has(p.id))
      for (const [i, photo] of pending.entries()) {
        setProgress(t('close.uploading', { i: i + 1, n: pending.length }))
        await uploadPhotos(order.id, 'after', [photo.file])
        setUploaded((prev) => new Set(prev).add(photo.id))
      }
      setProgress(t('close.sending'))
      return completeOrder(order.id, {
        works_done: works.trim(),
        fault_code_id: codeId as number,
        materials: noMaterials
          ? []
          : lines.map((l) => ({ material_id: l.material_id, quantity: String(l.quantity) })),
        no_materials: noMaterials,
        comment: comment.trim() || null,
      })
    },
    onSuccess: (result) => {
      clearDraft(order.id)
      navigator.vibrate?.(40)
      queryClient.setQueryData(orderKeys.detail(order.id), result)
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      navigate(`/w/orders/${order.id}/result`, { replace: true })
    },
    onError: (error) => toast(error.message, 'error'),
    onSettled: () => setProgress(null),
  })

  // Без фото «после» закрыть можно, но не случайно: первое нажатие предупреждает, что ИИ вернёт
  // наряд на доработку, — решает проверка (ТЗ, сценарий защиты, шаг 7), а не запрет формы.
  const photoMissing = photoRequired && !hasPhoto
  const onSubmit = () => {
    if (missing.length || (photoMissing && !photoWarned)) {
      setShowMissing(true)
      if (!missing.length) setPhotoWarned(true)
      navigator.vibrate?.([40, 60, 40])
      return
    }
    submit.mutate()
  }

  return (
    <>
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-4 px-4 pt-4 pb-6">
        <Panel>
          <TextArea
            label={t('close.works')}
            placeholder={t('close.worksPlaceholder')}
            value={works}
            onChange={(e) => setWorks(e.target.value)}
            rows={4}
            error={showMissing && works.trim().length < 3 ? t('close.missingWorks') : null}
            action={
              speech.supported ? (
                <Button
                  size="sm"
                  variant={speech.listening ? 'primary' : 'quiet'}
                  icon="mic"
                  onClick={speech.listening ? speech.stop : speech.start}
                >
                  {speech.listening ? t('close.listening') : t('close.voice')}
                </Button>
              ) : undefined
            }
          />
          {speech.error === 'mic-denied' && (
            <p className="mt-2 text-small text-red">{t('close.micDenied')}</p>
          )}
        </Panel>

        <Panel>
          <Select
            label={t('close.code')}
            value={codeId}
            onChange={setCodeId}
            searchable
            error={showMissing && !codeId ? t('close.missingCode') : null}
            options={codes.map((c) => ({
              value: c.id,
              label: `${c.code} · ${c.name}`,
              hint: c.norm_hours ? t('close.codeHint', { h: duration(Number(c.norm_hours) * 60) }) : undefined,
            }))}
          />
        </Panel>

        <Panel title={t('close.materials')}>
          <div className="flex flex-col gap-4">
            {!noMaterials &&
              lines.map((line) => {
                const material = byId.get(line.material_id)
                if (!material) return null
                const norm = code?.norm_materials.find((m) => m.material_id === line.material_id)
                return (
                  <div key={line.material_id} className="flex flex-col gap-1.5">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium [overflow-wrap:anywhere]">{material.name}</p>
                        {norm && (
                          <p className="text-small text-ink-3">
                            {t('close.normQty', { q: Number(norm.quantity).toString().replace('.', ','), u: norm.unit })}
                          </p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => setLines((prev) => prev.filter((l) => l.material_id !== line.material_id))}
                        className="inline-flex min-h-11 items-center gap-1 rounded-control px-2 text-small font-medium text-ink-2 active:bg-plate"
                      >
                        <Icon name="trash" size={18} />
                        {t('close.remove')}
                      </button>
                    </div>
                    <Stepper
                      label={material.name}
                      unit={material.unit}
                      value={line.quantity}
                      step={stepFor(material.unit)}
                      min={stepFor(material.unit)}
                      onChange={(quantity) =>
                        setLines((prev) =>
                          prev.map((l) => (l.material_id === line.material_id ? { ...l, quantity } : l)),
                        )
                      }
                    />
                  </div>
                )
              })}

            {!noMaterials && code && code.norm_materials.some((m) => !lines.some((l) => l.material_id === m.material_id)) && (
              <Button
                variant="secondary"
                icon="plus"
                block
                onClick={() =>
                  code.norm_materials.forEach((m) => addLine(m.material_id, Number(m.quantity)))
                }
              >
                {t('close.addByNorm', { code: code.code })}
              </Button>
            )}

            {!noMaterials && (
              <Select
                label={t('close.addMaterial')}
                value={null}
                placeholder={t('ui.search')}
                onChange={(id) => addLine(id)}
                searchable
                options={materials
                  .filter((m) => !lines.some((l) => l.material_id === m.id))
                  .map((m) => ({ value: m.id, label: m.name, hint: [m.category, m.unit].filter(Boolean).join(' · ') }))}
              />
            )}

            <ToggleRow
              checked={noMaterials}
              onChange={setNoMaterials}
              label={t('close.noMaterials')}
              hint={t('close.noMaterialsHint')}
            />
            {showMissing && !noMaterials && lines.length === 0 && (
              <p className="text-small font-medium text-red" role="alert">
                {t('close.missingMaterials')}
              </p>
            )}
          </div>
        </Panel>

        <Panel>
          <PhotoPicker
            label={t('close.photosAfter')}
            value={photos}
            onChange={setPhotos}
            max={5 - afterExisting}
            required={photoRequired}
            error={showMissing && photoRequired && !hasPhoto ? t('close.photosRequired') : null}
          />
          <p className="mt-2 text-small text-ink-3">
            {photoRequired ? t('close.photosRequired') : t('close.photosOptional')}
          </p>
        </Panel>

        <Panel>
          <TextArea
            label={t('close.comment')}
            placeholder={t('close.commentPlaceholder')}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
          />
        </Panel>

        {showMissing && !missing.length && photoMissing && (
          <section role="alert" className="rounded-[8px] border-2 border-red bg-red-soft p-4">
            <p className="font-semibold text-red">{t('close.noPhotoTitle')}</p>
            <p className="mt-1">{t('close.noPhotoHint')}</p>
          </section>
        )}
        {showMissing && missing.length > 0 && (
          <section role="alert" className="rounded-[8px] border-2 border-red bg-red-soft p-4">
            <p className="font-semibold text-red">{t('close.missingTitle')}</p>
            <ul className="mt-1 list-disc pl-5">
              {missing.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </section>
        )}
      </main>

      <ActionBar>
        <Button size="xl" block icon="check" loading={submit.isPending} onClick={onSubmit}>
          {progress ?? t('close.submit')}
        </Button>
      </ActionBar>
    </>
  )
}
