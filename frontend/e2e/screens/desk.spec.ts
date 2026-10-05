import { type APIRequestContext, expect, type Page, test } from '@playwright/test'

/**
 * Десктопные экраны мастера, руководителя и администратора: обзор, аналитика, отчёты, рейтинг, справочники.
 * Нужен бэкенд с `python -m seed`. Скриншоты — в docs/screenshots.
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

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForLoadState('networkidle')
}

test.describe('рабочие места на компьютере', () => {
  test.skip(({ isMobile }) => isMobile, 'десктоп')

  test('обзор руководителя', async ({ page, request }) => {
    await signIn(page, request, 'boss', '1111')
    await page.goto('/boss')
    await expect(page.getByRole('heading', { name: 'Проблемное оборудование' })).toBeVisible()
    await expect(page.getByText('Конвейер К-3').first()).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/boss.png`, fullPage: true })
  })

  test('аналитика и вопрос свободным текстом', async ({ page, request }) => {
    await signIn(page, request, 'master1', '2222')
    await page.goto('/panel/analytics')
    await expect(page.getByText('Найдено закономерностей')).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/analytics.png`, fullPage: true })

    await page.getByLabel('Спросите об участке или оборудовании').fill('что с К-3 за месяц')
    await page.getByRole('button', { name: 'Спросить' }).click()
    await expect(page.getByText('Ответ по срезу: Конвейер К-3, 30 дн.')).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/analytics-ask.png`, fullPage: true })
  })

  test('отчёты', async ({ page, request }) => {
    await signIn(page, request, 'master1', '2222')
    await page.goto('/panel/reports')
    await page.getByRole('radio', { name: '30 дней' }).click()
    await expect(page.getByRole('banner').getByText(/^30 дней/)).toBeVisible({ timeout: 15_000 })
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/reports.png` })

    await page.getByRole('tab', { name: 'Материалы' }).click()
    await expect(page.getByRole('heading', { name: 'Списания выше нормы' })).toBeVisible({ timeout: 15_000 })
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/reports-materials.png` })
  })

  test('рейтинг', async ({ page, request }) => {
    await signIn(page, request, 'boss', '1111')
    await page.goto('/panel/rating')
    await expect(page.getByText('Бригады')).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/rating-desk.png`, fullPage: true })
  })

  test('администратор: сотрудники, оборудование, система', async ({ page, request }) => {
    const token = await signIn(page, request, 'admin', '0000')
    await page.goto('/admin')
    await expect(page.getByRole('heading', { name: 'Администрирование' })).toBeVisible()
    await expect(page.getByText('Ахметов Ерлан Каиртаевич')).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/admin-employees.png` })

    // Новый сотрудник: логин уникальный на каждый прогон, затем отключаем его
    const login = `test${Date.now() % 100000}`
    await page.getByRole('button', { name: 'Добавить сотрудника' }).click()
    await page.getByLabel('ФИО *').fill('Тестов Тест Тестович')
    await page.getByLabel('Логин *').fill(login)
    await page.getByLabel('ПИН *').fill('4321')
    await page.screenshot({ path: `${SHOTS}/admin-new.png` })
    await page.getByRole('button', { name: 'Добавить', exact: true }).click()
    await expect(page.getByText('Запись добавлена')).toBeVisible()
    await page.getByPlaceholder('Фамилия, логин или специальность').fill(login)
    await page.getByText('Тестов Тест Тестович').click()
    await page.getByRole('switch', { name: /Доступ к системе/ }).click()
    await page.getByRole('button', { name: 'Сохранить' }).click()
    await expect(page.getByText('отключён')).toBeVisible()
    const auth = { Authorization: `Bearer ${token}` }
    const people = (await (await request.get('/api/admin/employees', { headers: auth })).json()) as {
      id: number
      login: string
    }[]
    const created = people.find((p) => p.login === login)
    expect(created).toBeTruthy()
    if (created) await request.delete(`/api/admin/employees/${created.id}`, { headers: auth })

    await page.getByRole('tab', { name: 'Оборудование' }).click()
    await page.getByText('Конвейер К-3').first().click()
    await expect(page.getByRole('img', { name: /QR-код оборудования/ })).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/admin-equipment.png` })
    await page.keyboard.press('Escape')

    await page.getByRole('tab', { name: 'Система' }).click()
    await expect(page.getByText('Журнал вызовов модели')).toBeVisible()
    await settle(page)
    await page.screenshot({ path: `${SHOTS}/admin-system.png`, fullPage: true })
  })
})
