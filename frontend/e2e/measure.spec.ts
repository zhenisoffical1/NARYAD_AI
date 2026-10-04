import { expect, test } from '@playwright/test'

/**
 * Замеры из плана (этап 8): выдача → наряд у исполнителя (цель ≤ 2 с) и загрузка фото на
 * профиле «Fast 3G» Chrome DevTools (цель ≤ 10 с). Результат печатается в консоль.
 */

const PHOTO = 'e2e/fixtures/leak.jpg'

test('время доставки наряда и загрузки фото', async ({ browser, request, isMobile }) => {
  test.skip(isMobile, 'замер делается в одном проекте')
  test.setTimeout(120_000)
  expect((await request.post('/api/demo/reset')).ok()).toBeTruthy()

  const loginAs = async (login: string, pin: string) => {
    const r = await request.post('/api/auth/login', { data: { login, pin } })
    return (await r.json()) as { access_token: string; user: { id: number } }
  }
  const master = await loginAs('master1', '2222')
  const worker = await loginAs('kovalchuk', '1234')

  const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
  await context.addInitScript((s) => {
    localStorage.setItem('naryad.session', JSON.stringify({ state: { token: s.access_token, user: s.user }, version: 0 }))
  }, worker)
  const page = await context.newPage()
  await page.goto('/w')
  await expect(page.getByText('На связи').or(page.getByRole('status')).first()).toBeAttached()
  await page.waitForTimeout(1500) // WebSocket подключился

  // 1. Выдача → наряд в списке исполнителя
  const equipment = (await (await request.get('/api/equipment', {
    headers: { Authorization: `Bearer ${master.access_token}` },
  })).json()) as { id: number; inv_number: string }[]
  const started = Date.now()
  const created = await request.post('/api/orders', {
    headers: { Authorization: `Bearer ${master.access_token}` },
    data: {
      description: 'Замер доставки: ослаб крепёж опоры',
      equipment_id: equipment.find((e) => e.inv_number === 'ДР-005')?.id,
      priority: 'normal',
      assignee_id: worker.user.id,
    },
  })
  const { number } = (await created.json()) as { number: number }
  await expect(page.getByText(`№${number}`).first()).toBeVisible({ timeout: 10_000 })
  const delivery = (Date.now() - started) / 1000
  console.log(`ЗАМЕР доставка наряда исполнителю: ${delivery.toFixed(2)} с`)
  expect(delivery).toBeLessThan(2)

  // 2. Загрузка фото на «Fast 3G»
  const cdp = await context.newCDPSession(page)
  await cdp.send('Network.enable')
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false,
    latency: 562.5,
    downloadThroughput: (1.6 * 1024 * 1024) / 8,
    uploadThroughput: (750 * 1024) / 8,
  })
  const id = ((await created.json()) as { id: number }).id
  const uploadStarted = Date.now()
  const status = await page.evaluate(
    async ({ id, token, bytes }) => {
      const form = new FormData()
      form.append('files', new Blob([new Uint8Array(bytes)], { type: 'image/jpeg' }), 'p.jpg')
      const r = await fetch(`/api/orders/${id}/photos?kind=before`, {
        method: 'POST',
        body: form,
        headers: { Authorization: `Bearer ${token}` },
      })
      return r.status
    },
    { id, token: master.access_token, bytes: [...(await import('node:fs')).readFileSync(PHOTO)] },
  )
  const upload = (Date.now() - uploadStarted) / 1000
  console.log(`ЗАМЕР загрузка фото на Fast 3G: ${upload.toFixed(2)} с`)
  expect(status).toBe(201)
  expect(upload).toBeLessThan(10)
  await context.close()
})
