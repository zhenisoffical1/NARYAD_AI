import { expect, test } from '@playwright/test'

/** Экран входа и вход мастера — нужен запущенный бэкенд с сидом. */
test('login', async ({ page }, info) => {
  await page.addInitScript(() => localStorage.setItem('naryad.theme', 'light'))
  await page.goto('/login')
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: `../docs/screenshots/login-${info.project.name}.png` })

  await page.getByLabel('Логин').fill('master1')
  for (const digit of '2222') await page.getByRole('button', { name: digit, exact: true }).click()
  await expect(page).toHaveURL(/\/(panel|m)/)
  await page.screenshot({ path: `../docs/screenshots/after-login-${info.project.name}.png` })
})
