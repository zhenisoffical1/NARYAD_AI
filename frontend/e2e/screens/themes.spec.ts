import { type APIRequestContext, expect, type Page, test } from '@playwright/test'

/** Тёмная тема и казахский язык на ключевых экранах — для проверки полировки (этап 8). */

const SHOTS = '../docs/screenshots'

async function signIn(page: Page, request: APIRequestContext, login: string, pin: string, opts: { theme: string; lang: string }) {
  const resp = await request.post('/api/auth/login', { data: { login, pin } })
  const body = (await resp.json()) as { access_token: string; user: unknown }
  await page.addInitScript(
    ({ session, theme, lang }) => {
      localStorage.setItem('naryad.session', JSON.stringify({ state: session, version: 0 }))
      localStorage.setItem('naryad.theme', theme)
      localStorage.setItem('naryad.lang', lang)
    },
    { session: { token: body.access_token, user: body.user }, ...opts },
  )
}

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForLoadState('networkidle')
}

test('исполнитель: тёмная тема и казахский', async ({ page, request, isMobile }) => {
  test.skip(!isMobile, 'телефон')
  await signIn(page, request, 'baizhanov', '1234', { theme: 'dark', lang: 'kk' })
  await page.goto('/w')
  await expect(page.getByRole('navigation').or(page.getByRole('button').first()).first()).toBeVisible()
  await settle(page)
  await page.screenshot({ path: `${SHOTS}/worker-home-dark-kk.png`, fullPage: true })
})

test('мастер: тёмная тема', async ({ page, request, isMobile }) => {
  test.skip(!isMobile, 'телефон')
  await signIn(page, request, 'master1', '2222', { theme: 'dark', lang: 'ru' })
  await page.goto('/m')
  await expect(page.getByRole('button', { name: 'Новый наряд' })).toBeVisible()
  await settle(page)
  await page.screenshot({ path: `${SHOTS}/master-home-dark.png`, fullPage: true })
})

test('руководитель: тёмная тема и казахский', async ({ page, request, isMobile }) => {
  test.skip(isMobile, 'десктоп')
  await signIn(page, request, 'boss', '1111', { theme: 'dark', lang: 'kk' })
  await page.goto('/boss')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await settle(page)
  await page.screenshot({ path: `${SHOTS}/boss-dark-kk.png` })
  await page.goto('/panel/analytics')
  await settle(page)
  await page.screenshot({ path: `${SHOTS}/analytics-dark-kk.png` })
})
