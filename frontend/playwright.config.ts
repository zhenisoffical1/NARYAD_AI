import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'

/**
 * e2e — сквозной демо-сценарий (нужен запущенный бэкенд в DEMO_MODE);
 * screens — скриншоты экранов в docs/screenshots для критического разбора.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL,
    // PW_CHANNEL=chrome — взять установленный Chrome вместо скачиваемого Chromium
    channel: process.env.PW_CHANNEL,
    locale: 'ru-RU',
    timezoneId: 'Asia/Qostanay',
    trace: 'retain-on-failure',
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: 'npm run dev',
        url: baseURL,
        reuseExistingServer: true,
        timeout: 60_000,
      },
  projects: [
    { name: 'mobile', use: { ...devices['Pixel 7'], viewport: { width: 390, height: 844 } } },
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
  ],
})
