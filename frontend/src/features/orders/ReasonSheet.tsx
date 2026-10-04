import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { BottomSheet, Button, TextArea } from '@/shared/ui'

import type { ReasonKey } from './reasons'

/** Выбор причины крупными пунктами; «Другое» — короткий текст. Причина обязательна. */
export function ReasonSheet({
  open,
  title,
  reasons,
  onClose,
  onSubmit,
  busy = false,
}: {
  open: boolean
  title: string
  reasons: ReasonKey[]
  onClose: () => void
  onSubmit: (reason: string) => void
  busy?: boolean
}) {
  const { t } = useTranslation()
  const [other, setOther] = useState<string | null>(null)

  const close = () => {
    setOther(null)
    onClose()
  }

  return (
    <BottomSheet
      open={open}
      title={title}
      onClose={close}
      footer={
        other !== null ? (
          <Button
            block
            size="xl"
            disabled={other.trim().length < 3}
            loading={busy}
            onClick={() => onSubmit(`${t('reasons.other')}: ${other.trim()}`)}
          >
            {t('reasons.confirm')}
          </Button>
        ) : undefined
      }
    >
      {other === null ? (
        <ul className="flex flex-col gap-2.5">
          {reasons.map((key) => (
            <li key={key}>
              <Button
                variant="secondary"
                size="lg"
                block
                className="justify-start text-left"
                disabled={busy}
                onClick={() => onSubmit(t(`reasons.${key}`))}
              >
                {t(`reasons.${key}`)}
              </Button>
            </li>
          ))}
          <li>
            <Button
              variant="quiet"
              size="lg"
              block
              className="justify-start border-2 border-dashed border-line"
              onClick={() => setOther('')}
            >
              {t('reasons.other')}
            </Button>
          </li>
        </ul>
      ) : (
        <TextArea
          label={t('reasons.other')}
          placeholder={t('reasons.otherPlaceholder')}
          value={other}
          onChange={(e) => setOther(e.target.value)}
          autoFocus
          rows={3}
        />
      )}
    </BottomSheet>
  )
}
