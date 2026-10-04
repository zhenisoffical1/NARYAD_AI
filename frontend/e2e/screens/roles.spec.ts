import { type APIRequestContext, expect, type Page, test } from '@playwright/test'

/**
 * Скриншоты экранов всех ролей на демо-сцене (нужен бэкенд с `python -m seed`).
 * Складываются в docs/screenshots для разбора и README.
 */

const SHOTS = '../docs/screenshots'

async function signIn(page: Page, request: APIRequestContext, login: string, pin: string) {
  const resp = await request.post('/api/auth/login', { data: { login, pin } })
  expect(resp.ok()).toBeTruthy()
  const body = (await resp.json()) as { access_token: string; user: unknown }
  await page.addInitScript((session) => {
    localStorage.setItem('naryad.session', JSON.stringify({ state: session, version: 0 }))
    localStorage.setItem('naryad.theme', 'light')
  }, { token: body.access_token, user: body.user })
  return body.access_token
}

async function orders(request: APIRequestContext, token: string) {
  const resp = await request.get('/api/orders?active=true&limit=200', {
    headers: { Authorization: `Bearer ${token}` },
  })
  return (await resp.json()) as { id: number; status: string; assignee: { full_name: string } | null }[]
}

function present<T>(value: T | undefined): T {
  expect(value).toBeTruthy()
  if (value === undefined) throw new Error('в демо-сцене нет нужного наряда')
  return value
}

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForLoadState('networkidle')
}

test.describe('исполнитель', () => {
  test.skip(({ isMobile }) => !isMobile, 'экраны исполнителя — телефон')

  test('мои наряды с очередью', async ({ page, request }) => {
    await signIn(page, request, 'baizhanov', '1234')
    await page.goto('/w')
    await expect(page.getByText('Очередь')).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/worker-home.png`, fullPage: true })
  })

  test('наряд в работе и форма закрытия', async ({ page, request }) => {
    const token = await signIn(page, request, 'sidorenko', '1234')
    const mine = present((await orders(request, token)).find((o) => o.status === 'IN_PROGRESS'))
    await page.goto(`/w/orders/${mine.id}`)
    await expect(page.getByRole('button', { name: 'Исполнено' })).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/worker-order.png`, fullPage: true })

    await page.getByRole('button', { name: 'Исполнено' }).click()
    await expect(page.getByText('Материалы и запчасти')).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/worker-close.png`, fullPage: true })
  })

  test('рейтинг', async ({ page, request }) => {
    await signIn(page, request, 'akhmetov', '1234')
    await page.goto('/w/rating')
    await expect(page.getByText('Из чего складывается')).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/worker-rating.png`, fullPage: true })
  })
})

test.describe('мастер с телефона', () => {
  test.skip(({ isMobile }) => !isMobile, 'мобильные экраны мастера')

  test('смена и выдача', async ({ page, request }) => {
    const token = await signIn(page, request, 'master1', '2222')
    await page.goto('/m')
    await expect(page.getByRole('button', { name: 'Новый наряд' })).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/master-home.png`, fullPage: true })

    await page.goto('/m/new')
    await page.getByPlaceholder('Например: течь масла из-под уплотнения').fill('Течь масла из-под торцевого уплотнения, лужа под насосом')
    await page.getByRole('button', { name: /Найти оборудование/ }).click()
    await page.getByPlaceholder('Название или инвентарный номер').fill('Н-7')
    await page.getByRole('button', { name: /Насос гидравлический Н-7/ }).click()
    await page.getByRole('radio', { name: 'Аварийный' }).click()
    await expect(page.getByText('Рекомендация ИИ')).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/master-new.png`, fullPage: true })

    const review = present((await orders(request, token)).find((o) => o.status === 'AI_REVIEW'))
    await page.goto(`/m/orders/${review.id}`)
    await expect(page.getByRole('button', { name: 'Подтвердить закрытие' })).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/master-order.png`, fullPage: true })
  })
})

test.describe('панель', () => {
  test.skip(({ isMobile }) => isMobile, 'панель — десктоп')

  test('канбан, карточка, выдача', async ({ page, request }) => {
    const token = await signIn(page, request, 'master1', '2222')
    await page.goto('/panel')
    await expect(page.getByText('Люди смены')).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/panel.png` })

    const review = present((await orders(request, token)).find((o) => o.status === 'AI_REVIEW'))
    await page.goto(`/panel?order=${review.id}`)
    await expect(page.getByRole('button', { name: 'Подтвердить закрытие' })).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/panel-order.png` })

    await page.goto('/panel?new=1')
    await expect(page.getByRole('button', { name: 'Выдать' })).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/panel-new.png` })
  })
})
