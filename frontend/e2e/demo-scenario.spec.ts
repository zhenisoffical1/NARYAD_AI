import { type APIRequestContext, type Browser, type BrowserContext, expect, type Page, test } from '@playwright/test'

/**
 * Сквозной сценарий защиты (ТЗ, раздел 11) — 9 шагов на живой системе в DEMO_MODE.
 * Три окна: мастер с телефона, мастер за панелью и исполнитель с телефона.
 * Перед прогоном демо-сцена пересоздаётся, поэтому тест можно запускать сколько угодно раз.
 */

const LEAK = 'e2e/fixtures/leak.jpg'
const FIXED = 'e2e/fixtures/fixed.jpg'
const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }
const DESK = { viewport: { width: 1440, height: 900 } }

interface Session {
  token: string
  user: { id: number; login: string }
}

async function login(request: APIRequestContext, login: string, pin: string): Promise<Session> {
  const resp = await request.post('/api/auth/login', { data: { login, pin } })
  expect(resp.ok()).toBeTruthy()
  const body = (await resp.json()) as { access_token: string; user: Session['user'] }
  return { token: body.access_token, user: body.user }
}

async function open(browser: Browser, session: Session, options: object): Promise<[BrowserContext, Page]> {
  const context = await browser.newContext({ ...options, baseURL: test.info().project.use.baseURL })
  await context.addInitScript((s) => {
    localStorage.setItem('naryad.session', JSON.stringify({ state: { token: s.token, user: s.user }, version: 0 }))
    localStorage.setItem('naryad.theme', 'light')
  }, session)
  return [context, await context.newPage()]
}

function auth(s: Session) {
  return { Authorization: `Bearer ${s.token}` }
}

async function order(request: APIRequestContext, s: Session, id: number) {
  const resp = await request.get(`/api/orders/${id}`, { headers: auth(s) })
  return (await resp.json()) as { id: number; number: number; status: string; assessment: { verdict: string | null } | null }
}

/** Наряд через API — для второго и третьего наряда сценария, где важна не форма выдачи. */
async function issueViaApi(request: APIRequestContext, master: Session, workerId: number, description: string) {
  const equipment = (await (await request.get('/api/equipment', { headers: auth(master) })).json()) as {
    id: number
    inv_number: string
  }[]
  const pump = equipment.find((e) => e.inv_number === 'ОБ-007')
  const codes = (await (await request.get('/api/fault-codes', { headers: auth(master) })).json()) as {
    id: number
    code: string
  }[]
  const leak = codes.find((c) => c.code === 'Г-02') // шифр, который подсказал бы ИИ по описанию
  const resp = await request.post('/api/orders', {
    headers: auth(master),
    data: { description, equipment_id: pump?.id, priority: 'high', assignee_id: workerId, fault_code_id: leak?.id },
  })
  expect(resp.ok(), await resp.text()).toBeTruthy()
  return (await resp.json()) as { id: number; number: number }
}

test.describe.configure({ mode: 'serial' })

test('сценарий защиты: 9 шагов', async ({ browser, request, isMobile }) => {
  test.skip(isMobile, 'сценарий сам открывает телефонные и десктопные окна')
  test.setTimeout(180_000)

  expect((await request.post('/api/demo/reset')).ok(), 'нужен DEMO_MODE=true').toBeTruthy()
  const master = await login(request, 'master1', '2222')
  const worker = await login(request, 'akhmetov', '1234')

  const [deskCtx, desk] = await open(browser, master, DESK)
  const [phoneCtx, phone] = await open(browser, master, PHONE)
  const [workerCtx, mobile] = await open(browser, worker, PHONE)

  // 1. Мастер видит панель смены: кто свободен, кто занят
  await desk.goto('/panel')
  await expect(desk.getByText('Люди смены')).toBeVisible()
  await expect(desk.getByRole('button', { name: /Ахметов Ерлан Каиртаевич/ })).toBeVisible()

  // 2. Фото течи, аварийный наряд на насос, ИИ подсказал свободного слесаря
  await phone.goto('/m/new')
  await phone.locator('input[type=file]').first().setInputFiles(LEAK)
  await phone.getByPlaceholder('Например: течь масла из-под уплотнения').fill(
    'Течь масла из-под торцевого уплотнения насоса, лужа под насосом',
  )
  await phone.getByRole('button', { name: /Найти оборудование/ }).click()
  await phone.getByPlaceholder('Название или инвентарный номер').fill('Н-7')
  await phone.getByRole('button', { name: /Насос гидравлический Н-7/ }).click()
  await phone.getByRole('radio', { name: 'Аварийный' }).click()
  await expect(phone.getByText('Рекомендация ИИ')).toBeVisible()
  await expect(phone.getByText(/Ахметов Ерлан/).first()).toBeVisible()
  const created = phone.waitForResponse((r) => r.url().endsWith('/api/orders') && r.request().method() === 'POST')
  await phone.getByRole('button', { name: 'Выдать', exact: true }).click()
  const first = ((await (await created).json()) as { id: number }).id
  await phone.waitForURL(/\/m$/) // после выдачи мастер возвращается к табло смены

  // 3. Push исполнителю: «Принять» → «Начать»; у мастера статус меняется сразу
  await mobile.goto('/w')
  await expect(mobile.getByText('Аварийный наряд')).toBeVisible({ timeout: 10_000 })
  await mobile.locator('[aria-labelledby="emergency-title"]').getByRole('button', { name: 'Принять в работу' }).click()
  await expect(mobile.getByRole('alertdialog')).toBeHidden({ timeout: 10_000 })
  await expect.poll(async () => (await order(request, master, first)).status).toBe('ACCEPTED')
  await mobile.goto(`/w/orders/${first}`)
  await mobile.getByRole('button', { name: 'Начать', exact: true }).click()
  await expect(mobile.getByRole('button', { name: 'Исполнено', exact: true })).toBeVisible()
  await expect(desk.getByText('В РАБОТЕ №', { exact: false }).first()).toBeVisible({ timeout: 5_000 })
  expect((await order(request, master, first)).status).toBe('IN_PROGRESS')

  // 4. Второй наряд — в очередь; срок истекает → сообщение исполнителю и мастеру
  const second = await issueViaApi(request, master, worker.user.id, 'Подтекает фланец напорной линии насоса')
  await mobile.goto(`/w/orders/${second.id}`)
  await mobile.getByRole('button', { name: 'Поставить в очередь' }).click()
  await expect(mobile.getByText('В очереди').first()).toBeVisible()
  const fired = await request.post(`/api/demo/orders/${second.id}/overdue`)
  expect(((await fired.json()) as { rules: string[] }).rules).toContain('overdue')
  for (const s of [worker, master]) {
    const feed = (await (await request.get('/api/notifications', { headers: auth(s) })).json()) as {
      items: { body: string }[]
    }
    expect(feed.items.some((n) => n.body.startsWith(`Наряд №${second.number} просрочен на`))).toBeTruthy()
  }

  // 5. Исполнитель закрывает первый наряд: работы, шифр, материалы, фото «после»
  await mobile.goto(`/w/orders/${first}`)
  await mobile.getByRole('button', { name: 'Исполнено', exact: true }).click()
  await mobile.getByLabel('Что сделано').fill('Заменена манжета уплотнения вала, долито масло, течь устранена')
  await mobile.getByRole('button', { name: /Добавить по норме/ }).click()
  await mobile.locator('input[type=file]').first().setInputFiles(FIXED)
  await mobile.getByRole('button', { name: 'Исполнено', exact: true }).click()
  await mobile.waitForURL(/\/result$/)

  // 6. ИИ проверяет и ставит оценку: исполнителю — его отчёт, мастеру — полный
  await expect(mobile.getByText(/из 100/).first()).toBeVisible({ timeout: 20_000 })
  await phone.goto(`/m/orders/${first}`)
  await expect(phone.getByRole('button', { name: 'Подтвердить закрытие' })).toBeVisible({ timeout: 20_000 })
  await phone.getByRole('button', { name: 'Подтвердить закрытие' }).click()
  await expect.poll(async () => (await order(request, master, first)).status).toBe('CLOSED')

  // 7. Третий наряд — без фото и с лишними материалами → «требует доработки»
  const third = await issueViaApi(request, master, worker.user.id, 'Течь масла на насосе, мокрый корпус')
  for (const action of ['accept', 'start']) {
    await request.post(`/api/orders/${third.id}/actions/${action}`, { headers: auth(worker), data: {} })
  }
  await mobile.goto(`/w/orders/${third.id}/close`)
  await mobile.getByLabel('Что сделано').fill('Заменено уплотнение, долито масло')
  await mobile.getByRole('button', { name: /Добавить по норме/ }).click()
  const more = mobile.getByRole('button', { name: /^Больше: Масло/ })
  for (let i = 0; i < 6; i += 1) await more.click()
  await mobile.getByRole('button', { name: 'Исполнено', exact: true }).click()
  await expect(mobile.getByText('Нет фото «после»')).toBeVisible()
  await mobile.getByRole('button', { name: 'Исполнено', exact: true }).click()
  await mobile.waitForURL(/\/result$/)
  await expect.poll(async () => (await order(request, master, third.id)).status, { timeout: 20_000 }).toBe('REWORK')
  await expect(mobile.getByText(/доработк/i).first()).toBeVisible({ timeout: 20_000 })

  // 8. Отчёт за смену и рейтинг исполнителей
  await desk.goto('/panel/reports')
  await expect(desk.getByText('Выдано').first()).toBeVisible()
  await expect(desk.getByRole('heading', { name: 'Наряды' })).toBeVisible()
  await desk.goto('/panel/rating')
  await expect(desk.getByRole('heading', { name: 'Бригады' })).toBeVisible()

  // 9. Аналитика за 3 месяца: закономерности и рекомендации
  await desk.goto('/panel/analytics')
  await expect(desk.getByRole('heading', { name: 'Конвейер К-3' }).first()).toBeVisible()
  await expect(desk.getByText('Что сделать').first()).toBeVisible()

  await Promise.all([deskCtx.close(), phoneCtx.close(), workerCtx.close()])
})
