import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from './Icon'

/** Сравнение «до / после»: шторка двигается пальцем или с клавиатуры. */
export function PhotoCompare({ before, after }: { before?: string | null; after?: string | null }) {
  const { t } = useTranslation()
  const [position, setPosition] = useState(50)
  const box = useRef<HTMLDivElement>(null)

  if (!before || !after) {
    const single = before ?? after
    return (
      <div className="relative aspect-[4/3] w-full overflow-hidden rounded-tag bg-plate">
        {single ? (
          <>
            <img src={single} alt="" className="size-full object-cover" />
            <Label side={before ? 'left' : 'right'} text={before ? t('ui.before') : t('ui.after')} />
          </>
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-2 text-ink-3 hatch-plate">
            <Icon name="image" size={32} />
            {t('ui.noPhoto')}
          </div>
        )}
      </div>
    )
  }

  const moveTo = (clientX: number) => {
    const rect = box.current?.getBoundingClientRect()
    if (!rect) return
    setPosition(Math.min(100, Math.max(0, ((clientX - rect.left) / rect.width) * 100)))
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div
        ref={box}
        className="relative aspect-[4/3] w-full touch-none overflow-hidden rounded-tag bg-plate select-none"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId)
          moveTo(e.clientX)
        }}
        onPointerMove={(e) => {
          if (e.buttons) moveTo(e.clientX)
        }}
      >
        <img src={after} alt={t('ui.after')} className="absolute inset-0 size-full object-cover" />
        <img
          src={before}
          alt={t('ui.before')}
          className="absolute inset-0 size-full object-cover"
          style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}
        />
        <span
          aria-hidden
          className="absolute inset-y-0 w-1 -translate-x-1/2 bg-on-steel shadow-[0_0_0_1px_rgb(0_0_0/0.4)]"
          style={{ left: `${position}%` }}
        >
          <span className="absolute top-1/2 left-1/2 inline-flex size-11 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-steel bg-on-steel text-steel">
            <Icon name="swap" size={20} />
          </span>
        </span>
        <Label side="left" text={t('ui.before')} />
        <Label side="right" text={t('ui.after')} />
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={Math.round(position)}
        onChange={(e) => setPosition(Number(e.target.value))}
        aria-label={t('ui.compareHint')}
        className="sr-only"
      />
      <p className="text-small text-ink-3">{t('ui.compareHint')}</p>
    </div>
  )
}

function Label({ side, text }: { side: 'left' | 'right'; text: string }) {
  return (
    <span
      className={`stamp absolute top-2 ${side === 'left' ? 'left-2' : 'right-2'} rounded-tag bg-steel/85 px-2 py-1 text-on-steel`}
    >
      {text}
    </span>
  )
}
