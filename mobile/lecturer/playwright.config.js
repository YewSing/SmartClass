// Playwright E2E for the lecturer app running in a browser (Expo web).
// Run: npm run e2e:web   (starts `expo start --web` on :8082 unless it is already running)
const { defineConfig, devices } = require('@playwright/test')

const PORT = 8082

module.exports = defineConfig({
  testDir: './e2e-web',
  timeout: 120_000,
  expect: { timeout: 60_000 },   // first web bundle can take a while
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npx expo start --web --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: true,
    timeout: 180_000,
    env: { CI: '1', BROWSER: 'none', EXPO_PUBLIC_API_URL: 'http://localhost:8000' },
  },
})
