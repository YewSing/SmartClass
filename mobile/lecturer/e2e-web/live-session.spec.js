// Live session in the browser (T38, FR-305, FR-315, FR-316): start a class now, override a student to
// Excused with a reason, end the class. Uses a WIA0000 lecture two days ahead, so it isn't the one the
// dev backend's schedule keeps open today; the session it makes is deleted afterwards.
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')

const BACKEND = path.join(__dirname, '..', '..', '..', 'backend')
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
// Malaysia (UTC+8) weekday two days from now
const DAY = DAYS[new Date(Date.now() + 8 * 3600e3 + 2 * 86400e3).getUTCDay()]
const liveSession = (action) =>
  execFileSync('python', ['scripts/e2e_live_session.py', action, '--course', 'WIA0000', '--day', DAY],
    { cwd: BACKEND, stdio: 'pipe' })

const visible = (locator) => locator.filter({ visible: true }).first()

test.beforeAll(() => { liveSession('setup') })
test.afterAll(() => { liveSession('teardown') })

test('lecturer starts a class, excuses a student with a reason and ends it', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()

  await visible(page.getByTestId('home-my-class').filter({ hasText: `${DAY} 00:00` })).click()
  await expect(visible(page.getByTestId('weekly-schedule'))).toHaveText(new RegExp(`^${DAY} 00:00–23:59`))
  await visible(page.getByTestId('class-start-now')).click()

  await expect(visible(page.getByText('Live — updates as students are recognised'))).toBeVisible()
  await expect(visible(page.getByText('Open now', { exact: true }))).toBeVisible()
  await expect(visible(page.getByTestId('count-excused'))).toHaveText('0')

  const student = visible(page.getByTestId('attendance-student'))
  const name = (await student.innerText()).split('\n')[1]   // initials, then the name
  await student.click()
  await expect(visible(page.getByText('Change status to'))).toBeVisible()
  await visible(page.getByTestId('status-option-excused')).click()
  await visible(page.getByTestId('override-reason')).fill('Medical certificate')
  await visible(page.getByText('Mark Excused', { exact: true })).click()

  await expect(visible(page.getByText('Marked Excused', { exact: true }))).toBeVisible()
  await expect(visible(page.getByTestId('count-excused'))).toHaveText('1')
  const row = visible(page.getByTestId('attendance-student').filter({ hasText: name }))
  await expect(row).toContainText('Excused')

  await visible(page.getByTestId('session-end')).click()
  await visible(page.getByTestId('session-end-confirm')).click()
  await expect(visible(page.getByText('SPeCTRUM attendance', { exact: true }))).toBeVisible()
  await expect(visible(page.getByText('Closed', { exact: true }))).toBeVisible()
  await expect(visible(page.getByText('Waiting to sync', { exact: true }))).toBeVisible()
  await expect(visible(page.getByTestId('count-excused'))).toHaveText('1')
  await expect(visible(page.getByTestId('sync-retry'))).toBeVisible()
  // Still closed once the app has re-read the session (the close event comes before the commit)
  await page.waitForTimeout(3000)
  await expect(visible(page.getByText('Closed', { exact: true }))).toBeVisible()
  await expect(page.getByTestId('session-end')).toHaveCount(0)
  expect(errors).toEqual([])
})
