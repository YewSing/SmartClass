// Playwright E2E for the lecturer app running in a browser (Expo web).
// Run: npm run e2e:web
// Starts its own backend (:8001, LLM_FAKE=1, dev DB from backend/.env) and Expo web (:8092),
// on ports the everyday dev servers don't use, so it never tests some other app that
// happens to be running. Needs docker postgres up, the seed data (devlecturer@um.edu.my) and the local Moodle.
const path = require('path')
const { defineConfig, devices } = require('@playwright/test')

// E2E_WEB_PORT / E2E_WEB_API_PORT move both servers, so a loop in a second worktree can run
// its own Playwright tests at the same time (e.g. 8093 / 8011).
const WEB_PORT = Number(process.env.E2E_WEB_PORT || 8092)
const API_PORT = Number(process.env.E2E_WEB_API_PORT || 8001)

module.exports = defineConfig({
  testDir: './e2e-web',
  timeout: 120_000,
  expect: { timeout: 60_000 },   // first web bundle can take a while
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } }],
  webServer: [
    {
      command: `python -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: path.join(__dirname, '..', '..', 'backend'),
      url: `http://localhost:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 180_000,
      // No schedule job, and test sessions are never written into Moodle
      env: {
        LLM_FAKE: '1',
        YOUTUBE_API_KEY: '',        // never the real YouTube API in E2E
        SESSION_SCHEDULER_INTERVAL_SECONDS: '0',
        MOODLE_ATTENDANCE_SYNC_INTERVAL_SECONDS: '0',
        MOODLE_ATTENDANCE_CHECK_INTERVAL_SECONDS: '0',
      },
    },
    {
      command: `npx expo start --web --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 180_000,
      env: { CI: '1', BROWSER: 'none', EXPO_PUBLIC_API_URL: `http://localhost:${API_PORT}` },
    },
  ],
})
