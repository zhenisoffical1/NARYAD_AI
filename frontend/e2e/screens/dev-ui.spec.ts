import { expect, test } from '@playwright/test'

/** Скриншоты каталога компонентов в обеих темах и на казахском — для разбора в docs/screenshots. */
for (const theme of ['light', 'dark'] as const) {
  test(`dev-ui ${theme}`, async ({ page }, info) => {
    await page.addInitScript((t) => localStorage.setItem('naryad.theme', t), theme)
    await page.goto('/dev/ui')
    await expect(page.getByRole('heading', { name: 'OrderTag' })).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({
      path: `../docs/screenshots/dev-ui-${info.project.name}-${theme}.png`,
      fullPage: true,
    })
  })
}

test('dev-ui kk', async ({ page }, info) => {
  await page.addInitScript(() => {
    localStorage.setItem('naryad.lang', 'kk')
    localStorage.setItem('naryad.theme', 'light')
  })
  await page.goto('/dev/ui')
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({
    path: `../docs/screenshots/dev-ui-${info.project.name}-kk.png`,
    fullPage: true,
  })
})

test('emergency overlay', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', 'оверлей — экран телефона')
  await page.addInitScript(() => localStorage.setItem('naryad.theme', 'light'))
  await page.goto('/dev/ui')
  await page.getByRole('button', { name: 'Аварийный наряд' }).click()
  await expect(page.getByRole('alertdialog')).toBeVisible()
  await page.screenshot({ path: '../docs/screenshots/emergency-mobile.png' })
})

test('bottom sheet', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', 'лист — экран телефона')
  await page.addInitScript(() => localStorage.setItem('naryad.theme', 'light'))
  await page.goto('/dev/ui')
  await page.getByRole('button', { name: 'Выбор причины' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.screenshot({ path: '../docs/screenshots/sheet-mobile.png' })
})
