// Lecturer dashboard in the browser (plan-shino.md S20; FR-202, FR-208). Real data: unread urgent and
// important notifications sit at the top until opened (a new one arrives live), today's classes are
// listed. Stubbed API answers: the loading, error/retry and empty states, and the latest-session
// overview. At 1280 px and at phone width.
// Seeds devlecturer's notifications with backend/scripts/e2e_notifications.py and restores them after.
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')

const BACKEND = path.join(__dirname, '..', '..', '..', 'backend')
const USER = 'devlecturer@um.edu.my'
const API_PORT = Number(process.env.E2E_WEB_API_PORT || 8001)
const API = `http://localhost:${API_PORT}`
const notifData = (...args) =>
  execFileSync('python', ['scripts/e2e_notifications.py', ...args, '--user', USER], { cwd: BACKEND, stdio: 'pipe' })

const visible = (locator) => locator.filter({ visible: true }).first()
const apiPath = (p) => (url) => url.port === String(API_PORT) && url.pathname === p
const priority = (page) => page.getByTestId('dash-priority').filter({ visible: true })

async function login(page) {
  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill(USER)
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()
  await expect(visible(page.getByTestId('home-class-card'))).toBeVisible()
}

const dashboardBody = (extra = {}) => ({
  date: '2026-11-22',
  today_classes: [],
  attendance_overview: null,
  priority_notifications: [],
  unread_count: 0,
  participation: null,
  quizzes: null,
  at_risk_alerts: null,
  ...extra,
})

test.afterEach(() => { notifData('clean') })

test.describe('at 1280 px', () => {
  test('priority notifications stay on top until read; today\'s classes; live arrival', async ({ page }) => {
    notifData('seed')
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    await login(page)

    // Urgent then important; general ones are only in the feed
    await expect(priority(page)).toHaveCount(2)
    await expect(priority(page).nth(0)).toContainText('E2E urgent notice')
    await expect(priority(page).nth(0)).toContainText('Urgent')
    await expect(priority(page).nth(1)).toContainText('E2E face enrolment to review')
    await expect(priority(page).filter({ hasText: 'E2E general update' })).toHaveCount(0)

    // They sit above everything else on the page
    const top = await visible(page.getByTestId('dash-priority-list')).boundingBox()
    const header = await visible(page.getByTestId('home-class-card')).boundingBox()
    expect(top.y).toBeLessThan(header.y)

    // Today's classes (WIA0000 has a slot every day)
    await expect(visible(page.getByTestId('dash-today-class').filter({ hasText: 'WIA0000' }))).toBeVisible()

    // Opening one marks it read: it leaves the top, the bell goes down
    await priority(page).filter({ hasText: 'E2E urgent notice' }).click()
    await expect(priority(page)).toHaveCount(1)
    await expect(visible(page.getByTestId('notif-bell-count'))).toHaveText('2')

    // A new important one arrives live, without a reload
    notifData('send', '--api', API)
    await expect(priority(page).filter({ hasText: 'Test notification' })).toHaveCount(1)
    await expect(priority(page)).toHaveCount(2)

    // One with a link opens its screen; back on the dashboard it's gone from the top
    await priority(page).filter({ hasText: 'E2E face enrolment to review' }).click()
    await expect(visible(page.getByText('Face verification', { exact: true }))).toBeVisible()
    await visible(page.getByLabel('Back')).click()
    await expect(priority(page)).toHaveCount(1)
    await expect(priority(page).first()).toContainText('Test notification')
    expect(errors).toEqual([])
  })

  test('loading, then an error with retry', async ({ page }) => {
    let fail = true
    await page.route(apiPath('/lecturer/dashboard'), async (route) => {
      if (!fail) return route.fallback()
      await new Promise((r) => setTimeout(r, 1500))
      return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Server error' }) })
    })
    await page.goto('/')
    await page.getByText('Administrator sign-in', { exact: true }).click()
    await page.getByPlaceholder('your@um.edu.my').fill(USER)
    await page.getByPlaceholder('Enter password').fill('DevTest@1234')
    await page.getByText('Sign In', { exact: true }).click()

    await expect(visible(page.getByTestId('dash-loading'))).toBeVisible()
    await expect(visible(page.getByTestId('dash-error'))).toContainText("Couldn't load the dashboard")
    // The M3 parts of the page still work
    await expect(visible(page.getByTestId('home-class-card'))).toBeVisible()

    fail = false
    await visible(page.getByTestId('dash-retry')).click()
    await expect(visible(page.getByTestId('dash-today-class').filter({ hasText: 'WIA0000' }))).toBeVisible()
    await expect(page.getByTestId('dash-error').filter({ visible: true })).toHaveCount(0)
  })

  test('empty states, then the latest class overview', async ({ page }) => {
    let body = dashboardBody()
    // No live class, so the overview shows (a live class has its own card above)
    await page.route(apiPath('/lecturer/sessions'), (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }))
    await page.route(apiPath('/lecturer/dashboard'), (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) }))
    await login(page)

    await expect(visible(page.getByTestId('dash-today-empty'))).toHaveText('No classes today.')
    await expect(visible(page.getByTestId('dash-overview-empty'))).toHaveText('No attendance taken yet.')
    await expect(page.getByTestId('dash-priority-list').filter({ visible: true })).toHaveCount(0)

    body = dashboardBody({
      today_classes: [{
        occurrence_id: 9001, course_id: 1, course_code: 'WIX1002', course_name: 'Fundamentals of Programming',
        class_type: 'TUTORIAL', class_label: 'T3', room: 'DK1', start_time: '09:00', end_time: '11:00',
        session_id: 77, session_status: 'closed',
      }],
      attendance_overview: {
        session_id: 77, occurrence_id: 9001, course_id: 1, course_code: 'WIX1002',
        course_name: 'Fundamentals of Programming', class_type: 'TUTORIAL', class_label: 'T3',
        session_status: 'closed', date: '2026-11-22', starts_at: '2026-11-22T09:00:00',
        enrolled: 20, present: 16, late: 2, excused: 1, absent: 1, not_recorded: 0, rate: 94.7,
      },
    })
    await page.reload()
    const cls = visible(page.getByTestId('dash-today-class'))
    await expect(cls).toContainText('WIX1002 · T3')
    await expect(cls).toContainText('09:00–11:00 · DK1')
    await expect(cls).toContainText('Ended')
    const overview = visible(page.getByTestId('dash-overview'))
    await expect(overview).toContainText('94.7%')
    await expect(overview).toContainText('20 enrolled')
    await expect(visible(page.getByTestId('dash-count-present'))).toHaveText('16')
    await expect(visible(page.getByTestId('dash-count-late'))).toHaveText('2')
    await expect(visible(page.getByTestId('dash-count-excused'))).toHaveText('1')
    await expect(visible(page.getByTestId('dash-count-absent'))).toHaveText('1')
    await expect(page.getByTestId('dash-count-not-yet').filter({ visible: true })).toHaveCount(0)
  })
})

test.describe('at phone width', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('priority notifications and today\'s classes fit the phone layout', async ({ page }) => {
    notifData('seed')
    await login(page)
    await expect(priority(page)).toHaveCount(2)
    for (const loc of [priority(page).first(), visible(page.getByTestId('dash-today-class'))]) {
      const box = await loc.boundingBox()
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(390)
    }
    await priority(page).first().click()
    await expect(priority(page)).toHaveCount(1)
  })
})
