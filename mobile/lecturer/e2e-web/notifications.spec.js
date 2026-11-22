// Notification centre in the browser (plan-shino.md S19; FR-208, FR-209, FR-213, FR-214).
// The bell shows the unread count, the feed loads older pages, opening a notification marks it read
// and follows its link, a new one arrives live over the websocket, "Mark all as read" clears the
// count, and the preferences save. At 1280 px and at phone width.
// Seeds devlecturer's notifications with backend/scripts/e2e_notifications.py and restores them after.
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')

const BACKEND = path.join(__dirname, '..', '..', '..', 'backend')
const USER = 'devlecturer@um.edu.my'
const API = `http://localhost:${Number(process.env.E2E_WEB_API_PORT || 8001)}`
const notifData = (...args) =>
  execFileSync('python', ['scripts/e2e_notifications.py', ...args, '--user', USER], { cwd: BACKEND, stdio: 'pipe' })

const visible = (locator) => locator.filter({ visible: true }).first()

async function login(page) {
  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill(USER)
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()
  await expect(visible(page.getByTestId('home-class-card'))).toBeVisible()
}

const bellCount = (page) => visible(page.getByTestId('notif-bell-count'))
const item = (page, title) => visible(page.getByTestId('notif-item').filter({ hasText: title }))

test.afterEach(() => { notifData('clean') })

test.describe('at 1280 px', () => {
  test.beforeEach(() => { notifData('seed', '--older', '22') })

  test('bell, feed, read one, live arrival, deep link, mark all read', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    await login(page)

    await expect(bellCount(page)).toHaveText('3')
    await visible(page.getByTestId('notif-bell')).click()
    await expect(visible(page.getByText('3 unread', { exact: true }))).toBeVisible()

    // Newest first; urgent and important carry a badge
    const titles = page.getByTestId('notif-item').filter({ visible: true })
    await expect(titles.first()).toContainText('E2E general update')
    await expect(item(page, 'E2E urgent notice').getByText('Urgent', { exact: true })).toBeVisible()
    await expect(item(page, 'E2E face enrolment to review').getByText('Important', { exact: true })).toBeVisible()
    await expect(titles).toHaveCount(20)                       // the first page

    // Older pages load on scroll
    await titles.last().scrollIntoViewIfNeeded()
    await page.mouse.wheel(0, 4000)
    await expect(item(page, 'E2E old 0')).toBeVisible()
    await expect(titles).toHaveCount(25)

    // Opening one without a link marks it read and stays here
    await item(page, 'E2E general update').click()
    await expect(visible(page.getByText('2 unread', { exact: true }))).toBeVisible()
    await expect(item(page, 'E2E general update').getByTestId('notif-read')).toHaveCount(1)

    // A new one arrives live, without a reload
    notifData('send', '--api', API)
    await expect(item(page, 'Test notification')).toBeVisible()
    await expect(visible(page.getByText('3 unread', { exact: true }))).toBeVisible()
    await expect(titles.first()).toContainText('Test notification')

    // Its link opens the face verification queue
    await item(page, 'E2E face enrolment to review').click()
    await expect(visible(page.getByText('Face verification', { exact: true }))).toBeVisible()
    await visible(page.getByLabel('Back')).click()
    await expect(visible(page.getByText('2 unread', { exact: true }))).toBeVisible()

    await visible(page.getByTestId('notif-mark-all')).click()
    await expect(visible(page.getByText('All caught up', { exact: true }))).toBeVisible()
    await expect(page.getByTestId('notif-unread').filter({ visible: true })).toHaveCount(0)
    await visible(page.getByLabel('Back')).click()
    await expect(page.getByTestId('notif-bell-count').filter({ visible: true })).toHaveCount(0)
    expect(errors).toEqual([])
  })

  test('preferences: general can be switched and stays saved; urgent/important are locked on', async ({ page }) => {
    await login(page)
    await visible(page.getByTestId('notif-bell')).click()
    await visible(page.getByTestId('notif-prefs')).click()
    await expect(visible(page.getByText('Notification settings', { exact: true }))).toBeVisible()

    const toggle = (name) => visible(page.getByRole('switch', { name, exact: true }))
    const pushGeneral = toggle('Push notifications: General')
    const emailGeneral = toggle('Email: General')
    await expect(pushGeneral).not.toBeChecked()
    await expect(emailGeneral).not.toBeChecked()
    for (const channel of ['Push notifications', 'Email']) {
      for (const level of ['Urgent', 'Important']) {
        await expect(toggle(`${channel}: ${level}, always on`)).toBeChecked()
        await expect(toggle(`${channel}: ${level}, always on`)).toBeDisabled()
      }
    }

    await pushGeneral.click()
    await expect(visible(page.getByText('Preferences saved', { exact: true }))).toBeVisible()
    await expect(pushGeneral).toBeChecked()

    // Saved on the server: a fresh load shows it on
    await page.reload()
    await expect(visible(page.getByTestId('home-class-card'))).toBeVisible()
    await visible(page.getByTestId('notif-bell')).click()
    await visible(page.getByTestId('notif-prefs')).click()
    await expect(toggle('Push notifications: General')).toBeChecked()
    await expect(toggle('Email: General')).not.toBeChecked()

    // The test notification lands in the feed (live)
    await visible(page.getByTestId('prefs-send-test')).click()
    await expect(visible(page.getByText('Test notification sent', { exact: true }))).toBeVisible()
    await visible(page.getByLabel('Back')).click()
    await expect(item(page, 'Test notification')).toBeVisible()
  })
})

test.describe('at phone width', () => {
  test.use({ viewport: { width: 390, height: 844 } })
  test.beforeEach(() => { notifData('seed') })

  test('bell and feed fit the phone layout', async ({ page }) => {
    await login(page)
    await expect(bellCount(page)).toHaveText('3')
    await visible(page.getByTestId('notif-bell')).click()
    const urgent = item(page, 'E2E urgent notice')
    await expect(urgent).toBeVisible()
    const box = await urgent.boundingBox()
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(390)
    await visible(page.getByTestId('notif-mark-all')).click()
    await expect(visible(page.getByText('All caught up', { exact: true }))).toBeVisible()
    notifData('send', '--api', API)
    await expect(item(page, 'Test notification')).toBeVisible()
    await expect(visible(page.getByText('1 unread', { exact: true }))).toBeVisible()
  })
})
