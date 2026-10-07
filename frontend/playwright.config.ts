import { defineConfig, devices } from '@playwright/test';

/**
 * Pruebas de extremo a extremo contra el stack real (make up). Usan el Chrome instalado en el
 * equipo, asi que no descargan navegadores. El certificado local es autofirmado.
 *
 * Antes de correrlas: python -m app.cli e2e-users > frontend/e2e/.auth/credentials.json
 */
const chrome = { channel: 'chrome' as const, ignoreHTTPSErrors: true, locale: 'es-CO' };

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env['E2E_BASE_URL'] ?? 'https://localhost',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], ...chrome } },
    { name: 'mobile', testMatch: /a11y\.spec\.ts/, use: { ...devices['Pixel 7'], ...chrome } },
  ],
});
