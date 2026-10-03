/** Образцы данных для каталога компонентов /dev/ui — в том числе длинные русские и казахские тексты. */
import type { Assessment, Check, OrderEvent, OrderListItem } from '@/shared/api/types'

const minutes = (n: number) => new Date(Date.now() + n * 60_000).toISOString()

const base: OrderListItem = {
  id: 1,
  number: 147,
  type: 'unplanned',
  priority: 'emergency',
  status: 'IN_PROGRESS',
  description: 'Течь масла из-под торцевого уплотнения, под насосом лужа',
  equipment: {
    id: 1,
    name: 'Насос гидравлический Н-7',
    inv_number: 'ОБ-007',
    section_id: 1,
    type: 'Насос',
    criticality: 'A',
  },
  section: { id: 1, name: 'Обогащение' },
  assignee: { id: 5, full_name: 'Ахметов Ерлан Каиртаевич', short_name: 'Ахметов Е.', specialty: null },
  master: { id: 2, full_name: 'Ковалёв Андрей Петрович', short_name: 'Ковалёв А.', specialty: null },
  deadline_at: minutes(42),
  created_at: minutes(-30),
  issued_at: minutes(-30),
  accepted_at: minutes(-27),
  started_at: minutes(-24),
  done_at: null,
  closed_at: null,
  updated_at: minutes(-1),
  equipment_stopped: true,
  is_overdue: false,
  overdue_minutes: 0,
  ai_score: null,
  ai_verdict: null,
}

export const SAMPLE_ORDERS: OrderListItem[] = [
  base,
  {
    ...base,
    id: 2,
    number: 1148,
    priority: 'high',
    status: 'ISSUED',
    description: 'Повышенный шум и нагрев подшипника приводного барабана',
    equipment: { ...base.equipment, name: 'Конвейер К-3', inv_number: 'КТ-003' },
    section: { id: 3, name: 'Конвейерный транспорт' },
    deadline_at: minutes(-45),
    is_overdue: true,
    overdue_minutes: 45,
    equipment_stopped: false,
  },
  {
    ...base,
    id: 3,
    number: 562,
    priority: 'normal',
    status: 'QUEUED',
    description:
      'Электромагнитный железоотделитель подвесной над конвейером периодически даёт ложные срабатывания, при этом защита отключает питание всей линии подачи руды на дробление',
    equipment: {
      ...base.equipment,
      name: 'Железоотделитель электромагнитный подвесной ЭП-120 с системой автоматической разгрузки',
      inv_number: 'ДР-007',
    },
    section: { id: 2, name: 'Ремонтно-механический цех' },
    assignee: {
      id: 9,
      full_name: 'Жаксыбеков Нурлан Серикович',
      short_name: 'Жаксыбеков Н.',
      specialty: null,
    },
    deadline_at: minutes(300),
    equipment_stopped: false,
  },
  {
    ...base,
    id: 4,
    number: 98,
    priority: 'planned',
    status: 'CLOSED',
    type: 'planned',
    description: 'ППР по графику: дробилка конусная КМД-1750',
    equipment: { ...base.equipment, name: 'Дробилка КМД-1750', inv_number: 'ДР-001' },
    section: { id: 4, name: 'Дробление' },
    equipment_stopped: false,
    ai_score: 94,
    ai_verdict: 'accepted',
  },
  {
    ...base,
    id: 5,
    number: 563,
    priority: 'high',
    status: 'REWORK',
    description: 'Ұңғыма сорғысының өнімділігі төмендеді, үйкеліс күшейіп, қақпақ қызды; һ, і, ә, ғ — тексеру',
    equipment: { ...base.equipment, name: 'Сорғы шламды ГрАТ-1400', inv_number: 'ОБ-006' },
    section: { id: 1, name: 'Байыту' },
    assignee: { id: 7, full_name: 'Омаров Ержан Сабитович', short_name: 'Омаров Е.', specialty: null },
    equipment_stopped: false,
  },
]

const ev = (id: number, action: string, to: OrderEvent['to_status'], ago: number, extra: Partial<OrderEvent> = {}): OrderEvent => ({
  id,
  action,
  from_status: null,
  to_status: to,
  actor: { id: 5, full_name: 'Ахметов Ерлан Каиртаевич', short_name: 'Ахметов Е.', specialty: null },
  reason: null,
  comment: null,
  data: null,
  created_at: minutes(-ago),
  ...extra,
})

export const SAMPLE_EVENTS: OrderEvent[] = [
  ev(1, 'create', 'ISSUED', 30, {
    actor: { id: 2, full_name: 'Ковалёв Андрей Петрович', short_name: 'Ковалёв А.', specialty: null },
    comment: 'Срочно — насос стоит',
  }),
  ev(2, 'accept', 'ACCEPTED', 27),
  ev(3, 'start', 'IN_PROGRESS', 24),
  ev(4, 'pause', 'PAUSED', 18, { reason: 'ждёт запчасти: манжета 50×70 со склада' }),
  ev(5, 'resume', 'IN_PROGRESS', 9),
  ev(6, 'complete', 'DONE', 2),
  ev(7, 'begin_review', 'AI_REVIEW', 2, { actor: null }),
]

const okCompleteness: Check = { key: 'completeness', label: 'Полнота закрытия', status: 'ok', detail: 'Заполнено: работы, шифр Г-02, материалов: 2, фото «после»: 1.', critical: false, penalty: 0, items: [] }
const okWorks: Check = { key: 'works_match', label: 'Работы соответствуют проблеме', status: 'ok', detail: 'Работы закрывают заявленную проблему: течь/уплотнение.', critical: false, penalty: 0, items: [] }

const assessment: Assessment = {
  id: 1,
  status: 'done',
  mode: 'llm',
  verdict: 'accepted',
  score_0_100: 92,
  score_1_5: 5,
  confidence: 0.86,
  needs_master_review: false,
  explanation_worker:
    'Наряд №147: 92 из 100. Итог: принято.\nХорошо: работы точно закрывают заявленную проблему; расход материалов в норме; фото «после» подтверждает результат.\nВремя: 1 ч 20 мин при нормативе 1 ч 30 мин.',
  explanation_master:
    'Вердикт ИИ: принято, 92 из 100. Течь устранена: на фото «после» под насосом сухо, уплотнение заменено.',
  checks: [
    okCompleteness,
    { key: 'time', label: 'Время и срок', status: 'ok', detail: 'Выполнено в срок: 1 ч 20 мин при нормативе 1 ч 30 мин.', critical: false, penalty: 0, items: [] },
    { key: 'materials', label: 'Расход материалов', status: 'ok', detail: 'Расход 2 поз. в пределах нормы для шифра Г-02.', critical: false, penalty: 0, items: [] },
    okWorks,
    { key: 'photos', label: 'Фото до и после', status: 'ok', detail: 'То же оборудование, течь устранена. Оценка 5 из 5.', critical: false, penalty: 0, items: [] },
  ],
  master_override_score: null,
  master_comment: null,
  final_score: 92,
  created_at: minutes(-2),
  finished_at: minutes(-2),
}

export const SAMPLE_ASSESSMENTS: Record<'accepted' | 'remarks' | 'rework' | 'review', Assessment> = {
  accepted: assessment,
  remarks: {
    ...assessment,
    verdict: 'accepted_with_remarks',
    score_0_100: 76,
    final_score: 80,
    master_override_score: 80,
    master_comment: 'Проверил на месте — масло долито до уровня',
    checks: [
      okCompleteness,
      { key: 'time', label: 'Время и срок', status: 'warn', detail: 'Срок нарушен на 25 мин.', critical: false, penalty: 8, items: ['Срок нарушен на 25 мин.'] },
      { key: 'materials', label: 'Расход материалов', status: 'warn', detail: 'Списано 2,6 л «Масло индустриальное И-40А» при норме 1,5 л для шифра Г-02 (в 1,7 раза больше).', critical: false, penalty: 12, items: ['Списано 2,6 л «Масло индустриальное И-40А» при норме 1,5 л для шифра Г-02 (в 1,7 раза больше).'] },
      okWorks,
    ],
  },
  rework: {
    ...assessment,
    verdict: 'rework',
    score_0_100: 23,
    final_score: 23,
    confidence: 0.9,
    checks: [
      { key: 'completeness', label: 'Полнота закрытия', status: 'fail', detail: 'Нет фото «после» — для внепланового наряда оно обязательно.', critical: true, penalty: 35, items: ['Нет фото «после» — для внепланового наряда оно обязательно.'] },
      { key: 'materials', label: 'Расход материалов', status: 'fail', detail: 'Списано 6 л «Масло индустриальное И-40А» при норме 1,5 л для шифра Г-02 (в 4 раза больше).', critical: true, penalty: 30, items: ['Списано 6 л «Масло индустриальное И-40А» при норме 1,5 л для шифра Г-02 (в 4 раза больше).', '«Кабель КГ 3×16» (электрика) не типичен для шифра Г-02 «Течь гидравлической системы». Проверьте, что материал списан на этот наряд.'] },
    ],
  },
  review: { ...assessment, verdict: null, needs_master_review: true, confidence: 0.48, score_0_100: 71, final_score: 71 },
}
