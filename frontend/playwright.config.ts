import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: 'list',
  timeout: 120_000,
  expect: { timeout: 10_000 },
  use: { baseURL: 'http://127.0.0.1:5173', browserName: 'chromium', headless: true, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
})
