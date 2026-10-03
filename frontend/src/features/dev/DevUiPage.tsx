import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { setLanguage } from '@/i18n'
import type { OrderStatus, PersonState, Priority } from '@/shared/api/types'
import type { PickedPhoto } from '@/shared/lib/photos'
import { type ThemeMode, useTheme } from '@/shared/lib/theme'
import { toast } from '@/shared/lib/toast'
import {
  BottomSheet,
  Button,
  Counter,
  CounterBoard,
  EmergencyOverlay,
  EmptyState,
  OrderTag,
  PersonBadge,
  PersonStatusRow,
  PhotoCompare,
  PhotoPicker,
  PinPad,
  PriorityPicker,
  Select,
  StatusBadge,
  Stepper,
  Tabs,
  TagSkeleton,
  TextArea,
  TextField,
  Timeline,
  TopBar,
  VerdictCard,
} from '@/shared/ui'

import { SAMPLE_ASSESSMENTS, SAMPLE_EVENTS, SAMPLE_ORDERS } from './samples'

const STATUSES: OrderStatus[] = [
  'ISSUED',
  'QUEUED',
  'ACCEPTED',
  'REJECTED',
  'IN_PROGRESS',
  'PAUSED',
  'DONE',
  'AI_REVIEW',
  'REWORK',
  'CLOSED',
  'CANCELLED',
]
const PEOPLE: PersonState[] = ['free', 'busy', 'queue', 'off_shift']
const REASONS = ['Нет материалов', 'Нет допуска', 'Занят аварийным', 'Ждёт запчасти', 'Ждёт остановки оборудования', 'Другое']

/** Каталог компонентов во всех состояниях: /dev/ui. Экраны собираются только из них. */
export function DevUiPage() {
  const { t, i18n } = useTranslation()
  const { mode, setMode } = useTheme()
  const [priority, setPriority] = useState<Priority | null>('emergency')
  const [qty, setQty] = useState(1.5)
  const [code, setCode] = useState<string | null>('Г-02')
  const [photos, setPhotos] = useState<PickedPhoto[]>([])
  const [pin, setPin] = useState('12')
  const [sheet, setSheet] = useState(false)
  const [emergency, setEmergency] = useState(false)
  const [tab, setTab] = useState<'active' | 'done'>('active')
  const [highlight, setHighlight] = useState(0)

  return (
    <div className="min-h-dvh bg-bg pb-16 text-ink">
      <TopBar
        title={t('screens.devUi')}
        subtitle="docs/DESIGN.md"
        right={
          <button
            type="button"
            onClick={() => setLanguage(i18n.language === 'kk' ? 'ru' : 'kk')}
            className="min-h-12 rounded-control px-3 font-semibold active:bg-white/10"
          >
            {t('common.switchLanguage')}
          </button>
        }
      />
      <main className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-6">
        <Section title={t('common.theme')}>
          <Tabs<ThemeMode>
            label={t('common.theme')}
            value={mode}
            onChange={setMode}
            items={[
              { value: 'auto', label: t('common.themeAuto') },
              { value: 'light', label: t('common.themeLight') },
              { value: 'dark', label: t('common.themeDark') },
            ]}
          />
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
            {['bg', 'surface', 'plate', 'line', 'ink', 'accent', 'yellow', 'red', 'green', 'queue', 'off', 'steel'].map(
              (token) => (
                <div key={token} className="flex flex-col gap-1">
                  <span className="h-12 rounded-tag border border-line" style={{ background: `var(--${token})` }} />
                  <span className="cond text-small text-ink-2">{token}</span>
                </div>
              ),
            )}
          </div>
          <div className="flex flex-col gap-1">
            <span className="cond text-display font-semibold">12 · 7 · 2</span>
            <span className="cond text-tagnum font-bold">№147 ОБ-007</span>
            <span className="text-h1 font-semibold">Заголовок экрана — Экран тақырыбы</span>
            <span className="text-body-lg">Текст исполнителя 19 px: ә ғ қ ң ө ұ ү һ і Ә Ғ Қ Ң Ө Ұ Ү Һ І</span>
            <span className="text-body">Основной текст 17 px — минимум на телефоне.</span>
            <span className="stamp text-ink-3">Штамп · инв · до</span>
          </div>
        </Section>

        <Section title="Button">
          <div className="grid items-start gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-3">
              <Button size="xl" block icon="check">
                Исполнено
              </Button>
              <Button variant="secondary" block icon="pause">
                Приостановить
              </Button>
              <Button variant="danger" block onHoldConfirm={() => toast('Наряд отклонён', 'error')}>
                Отклонить
              </Button>
            </div>
            <div className="flex flex-wrap items-start gap-3">
              <Button size="md" icon="plus">
                Выдать наряд
              </Button>
              <Button size="md" variant="secondary" icon="swap">
                Переназначить
              </Button>
              <Button size="md" variant="quiet" icon="history">
                История
              </Button>
              <Button size="md" loading>
                Сохраняем
              </Button>
              <Button size="md" disabled>
                Недоступно
              </Button>
              <Button size="sm" variant="secondary">
                Маленькая
              </Button>
              <Button size="md" variant="secondary" icon="eye" onClick={() => setHighlight((n) => n + 1)}>
                Подсветить бирку
              </Button>
            </div>
          </div>
        </Section>

        <Section title="OrderTag">
          <div className="grid gap-3 md:grid-cols-2">
            {SAMPLE_ORDERS.map((order, i) => (
              <OrderTag
                key={`${order.id}-${i === 0 ? highlight : 0}`}
                order={order}
                highlight={i === 0 && highlight > 0}
                onClick={() => toast(`Открыт наряд №${order.number}`, 'info')}
              />
            ))}
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
            {SAMPLE_ORDERS.map((order) => (
              <OrderTag key={order.id} order={order} variant="compact" selected={order.id === 2} />
            ))}
          </div>
        </Section>

        <Section title="StatusBadge · PersonBadge">
          <div className="flex flex-wrap gap-2">
            {STATUSES.map((s) => (
              <StatusBadge key={s} status={s} />
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {PEOPLE.map((p) => (
              <PersonBadge key={p} state={p} orderNumber={561} queueCount={2} />
            ))}
          </div>
        </Section>

        <Section title="PersonStatusRow">
          <div className="max-w-md divide-y divide-line rounded-tag border border-line bg-surface px-2">
            <PersonStatusRow
              name="Ахметов Ерлан Каиртаевич"
              specialty="слесарь-ремонтник, 6 разряд"
              state="free"
              recommendation="лучший рейтинг по насосам, свободен"
              selected
              onClick={() => undefined}
            />
            <PersonStatusRow name="Абенов Бауыржан" specialty="электромонтёр" state="busy" orderNumber={561} onClick={() => undefined} />
            <PersonStatusRow name="Байжанов Арман" specialty="слесарь-ремонтник" state="queue" queueCount={2} onClick={() => undefined} />
            <PersonStatusRow name="Нурпеисов Асхат" specialty="электромонтёр" state="off_shift" onClick={() => undefined} />
            <PersonStatusRow name="Жаксыбеков Нурлан Серикович-Абдрахманов" specialty="электромонтёр 4 разряда, бригада №3" state="queue" queueCount={12} dense />
          </div>
        </Section>

        <Section title="Counter">
          <CounterBoard>
            <Counter label="Выдано" value={12} />
            <Counter label="Выполнено" value={7} />
            <Counter label="Просрочено" value={2} alert />
            <Counter label="Оборудование в простое" value={1} alert hint="Насос Н-7" />
          </CounterBoard>
        </Section>

        <Section title="Field · Select · Stepper · PriorityPicker">
          <div className="grid items-start gap-5 md:grid-cols-2">
            <TextField label="Логин" placeholder="фамилия латиницей" />
            <TextField label="Шифр" defaultValue="Г-99" error="Шифр не найден в справочнике. Выберите из списка." />
            <TextArea
              label="Выполненные работы"
              placeholder="Что сделано"
              action={
                <Button size="sm" variant="quiet" icon="mic">
                  Голосом
                </Button>
              }
            />
            <Select
              label="Шифр неисправности"
              value={code}
              onChange={setCode}
              options={[
                { value: 'М-02', label: 'М-02 · Разрушение подшипникового узла', hint: 'норматив 4 ч' },
                { value: 'Г-02', label: 'Г-02 · Течь гидравлической системы', hint: 'норматив 1,5 ч' },
                { value: 'Э-01', label: 'Э-01 · Отказ электродвигателя', hint: 'норматив 5 ч' },
                ...Array.from({ length: 8 }, (_, i) => ({ value: `С-0${i}`, label: `С-0${i} · Смазка, вариант ${i}` })),
              ]}
            />
            <div className="flex flex-col gap-1.5">
              <span className="text-small font-semibold text-ink-2">Масло индустриальное И-40А</span>
              <Stepper label="Масло И-40А" value={qty} onChange={setQty} unit="л" step={0.5} />
            </div>
            <PriorityPicker label="Приоритет" value={priority} onChange={setPriority} />
          </div>
        </Section>

        <Section title="PhotoPicker · PhotoCompare">
          <div className="grid items-start gap-5 md:grid-cols-2">
            <div className="flex flex-col gap-4">
              <PhotoPicker label="Фото «после»" value={photos} onChange={setPhotos} required />
              <PhotoPicker label="Фото «после»" value={[]} onChange={() => undefined} required error="Для внепланового наряда нужно фото «после»." />
            </div>
            <div className="flex flex-col gap-4">
              <PhotoCompare before="/dev/before.svg" after="/dev/after.svg" />
              <PhotoCompare before={null} after={null} />
            </div>
          </div>
        </Section>

        <Section title="Timeline">
          <div className="max-w-md rounded-tag border border-line bg-surface p-3">
            <Timeline events={SAMPLE_EVENTS} />
          </div>
        </Section>

        <Section title="VerdictCard">
          <div className="grid items-start gap-4 md:grid-cols-2">
            <VerdictCard assessment={SAMPLE_ASSESSMENTS.accepted} audience="worker" />
            <VerdictCard assessment={SAMPLE_ASSESSMENTS.remarks} audience="master" />
            <VerdictCard assessment={SAMPLE_ASSESSMENTS.rework} audience="master" />
            <VerdictCard assessment={SAMPLE_ASSESSMENTS.review} audience="master" />
            <VerdictCard assessment={null} audience="worker" progress={['completeness', 'time']} />
          </div>
        </Section>

        <Section title="EmptyState · Skeleton · Tabs">
          <div className="grid items-start gap-4 md:grid-cols-2">
            <EmptyState
              icon="list"
              title="Нарядов нет"
              hint="Новые придут сюда и в Telegram."
            />
            <TagSkeleton />
            <Tabs
              label="Наряды"
              value={tab}
              onChange={setTab}
              items={[
                { value: 'active', label: 'Активные', count: 3 },
                { value: 'done', label: 'Закрытые', count: 128 },
              ]}
            />
          </div>
        </Section>

        <Section title="PinPad">
          <div className="max-w-xs">
            <PinPad value={pin} onChange={setPin} />
          </div>
        </Section>

        <Section title="BottomSheet · Toast · EmergencyOverlay">
          <div className="flex flex-wrap gap-3">
            <Button size="md" variant="secondary" onClick={() => setSheet(true)}>
              Выбор причины
            </Button>
            <Button size="md" variant="secondary" onClick={() => toast('Наряд №147 принят в работу')}>
              Тост: успех
            </Button>
            <Button size="md" variant="secondary" onClick={() => toast('Нет связи с сервером. Проверьте сеть и повторите.', 'error')}>
              Тост: ошибка
            </Button>
            <Button size="md" variant="danger" onClick={() => setEmergency(true)}>
              Аварийный наряд
            </Button>
          </div>
        </Section>
      </main>

      <BottomSheet open={sheet} title="Причина отклонения" onClose={() => setSheet(false)}>
        <ul className="flex flex-col gap-2">
          {REASONS.map((reason) => (
            <li key={reason}>
              <Button variant="secondary" block size="lg" className="justify-start" onClick={() => setSheet(false)}>
                {reason}
              </Button>
            </li>
          ))}
        </ul>
      </BottomSheet>

      <EmergencyOverlay
        open={emergency}
        number={148}
        equipment="Насос гидравлический Н-7"
        inv="ОБ-007"
        section="Обогащение"
        description="Течь масла из-под торцевого уплотнения, под насосом лужа. Насос остановлен."
        onAccept={() => setEmergency(false)}
        onReject={() => setEmergency(false)}
      />
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="cond border-b-2 border-ink pb-1 text-h2 font-semibold">{title}</h2>
      {children}
    </section>
  )
}
