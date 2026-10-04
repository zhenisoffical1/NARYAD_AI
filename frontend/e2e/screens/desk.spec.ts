import { type APIRequestContext, expect, type Page, test } from '@playwright/test'

/**
 * Десктопные экраны мастера и руководителя: обзор, аналитика, отчёты, рейтинг.
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
})
