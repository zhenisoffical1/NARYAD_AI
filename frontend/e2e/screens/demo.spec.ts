import { expect, test } from '@playwright/test'

/**
 * Пульт демо и профиль (нужен бэкенд с DEMO_MODE=true и `python -m seed`).
 * Скриншоты — в docs/screenshots.
 */

const SHOTS = '../docs/screenshots'

test('пульт демо', async ({ page, isMobile }) => {
  await page.addInitScript(() => localStorage.setItem('naryad.theme', 'light'))
  await page.goto('/demo')
  await expect(page.getByRole('button', { name: /Пересоздать смену/ })).toBeVisible()
  await expect(page.getByRole('img', { name: /Мастер смены/ })).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: `${SHOTS}/demo${isMobile ? '-mobile' : ''}.png`, fullPage: !isMobile })
})

test('вход по QR и профиль исполнителя', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'профиль — телефон')
  await page.addInitScript(() => localStorage.setItem('naryad.theme', 'light'))
  await page.goto('/demo/enter?login=akhmetov')
  await expect(page).toHaveURL(/\/w$/)
  await page.getByRole('button', { name: 'Профиль' }).click()
  await expect(page.getByText('Ахметов Ерлан Каиртаевич')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: `${SHOTS}/worker-profile.png`, fullPage: true })
})
