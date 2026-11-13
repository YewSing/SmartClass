// T22: the admin area inside the lecturer web app (FR-103, FR-108, FR-117, FR-104).
// An administrator signs in with the browser-only email sign-in, lands on the admin area,
// deactivates and reactivates a Moodle student, and opens the other admin screens.
// A lecturer never sees the admin navigation, and the server answers 403 to them.
// Uses the dev DB's student6 (from the Moodle sync) and needs the local Moodle for "Sync now".
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')

const API = `http://localhost:${process.env.E2E_WEB_API_PORT || 8001}`
const BACKEND = path.join(__dirname, '..', '..', '..', 'backend')
const TARGET = 'student6@example.com'

const visible = (locator) => locator.filter({ visible: true }).first()

async function signIn(page, email, password) {
  await page.goto('/')
  await expect(page.getByText('Welcome back')).toBeVisible()
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill(email)
  await page.getByPlaceholder('Enter password').fill(password)
  await page.getByText('Sign In', { exact: true }).click()
}

async function apiToken(request, email, password) {
  const res = await request.post(`${API}/auth/login`, { data: { email, password } })
  expect(res.status()).toBe(200)
  return (await res.json()).access_token
}

// If a run stops halfway, student6 must not stay deactivated in the dev DB
test.afterAll(async ({ request }) => {
  const token = await apiToken(request, 'admin@um.edu.my', 'Admin@1234')
  const headers = { Authorization: `Bearer ${token}` }
  const list = await (await request.get(`${API}/admin/users?q=${encodeURIComponent(TARGET)}`, { headers })).json()
  for (const u of list.items) {
    if (u.status !== 'active') await request.post(`${API}/admin/users/${u.id}/reactivate`, { headers })
  }
})

test('admin lands on the admin area and deactivates then reactivates an account', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))

  await signIn(page, 'admin@um.edu.my', 'Admin@1234')
  for (const tab of ['Accounts', 'Verification', 'AuditLog', 'MoodleSync', 'Devices']) {
    await expect(page.getByTestId(`sidenav-${tab}`)).toBeVisible()
  }
  // None of the lecturer screens
  await expect(page.getByTestId('sidenav-Home')).toHaveCount(0)
  await expect(page.getByTestId('sidenav-Attendance')).toHaveCount(0)

  await visible(page.getByTestId('account-search')).fill(TARGET)
  const row = visible(page.getByTestId('account-row').filter({ hasText: TARGET }))
  await expect(row).toBeVisible()
  await expect(page.getByTestId('account-row')).toHaveCount(1)
  await expect(row.getByText(/^Student · \d+ · SPeCTRUM$/)).toBeVisible()
  await expect(row.getByTestId('account-status')).toHaveText('Active')

  // Deactivate asks first, then the badge changes
  await row.getByText('Deactivate', { exact: true }).click()
  await expect(row.getByText(/can't sign in until reactivated/)).toBeVisible()
  await row.getByText('Confirm deactivate', { exact: true }).click()
  await expect(row.getByTestId('account-status')).toHaveText('Deactivated')

  // The status filter finds them under "Deactivated"
  await visible(page.getByTestId('status-inactive')).click()
  await expect(row).toBeVisible()

  await row.getByText('Reactivate', { exact: true }).click()
  await row.getByText('Confirm reactivate', { exact: true }).click()
  // Reactivated, so they no longer match the "Deactivated" filter
  await expect(page.getByTestId('account-row').filter({ hasText: TARGET })).toHaveCount(0)
  await visible(page.getByTestId('status-active')).click()
  await expect(visible(page.getByTestId('account-row').filter({ hasText: TARGET })).getByTestId('account-status'))
    .toHaveText('Active')

  // Both changes are in the audit log
  await page.getByTestId('sidenav-AuditLog').click()
  await expect(visible(page.getByText('Reactivated account', { exact: true }))).toBeVisible()
  await expect(visible(page.getByText('Deactivated account', { exact: true }))).toBeVisible()

  // Verification fallback lists every pending submission
  await page.getByTestId('sidenav-Verification').click()
  await expect(visible(page.getByText('Every enrolment waiting for review'))).toBeVisible()

  // SPeCTRUM sync: status and "Sync now"
  await page.getByTestId('sidenav-MoodleSync').click()
  await visible(page.getByText('Sync now', { exact: true })).click()
  await expect(visible(page.getByTestId('sync-status'))).toHaveText(/^Succeeded · /)
  await expect(visible(page.getByText('Enrolments added', { exact: true }))).toBeVisible()

  expect(errors).toEqual([])
})

test('admin cannot deactivate themselves', async ({ page }) => {
  await signIn(page, 'admin@um.edu.my', 'Admin@1234')
  await visible(page.getByTestId('account-search')).fill('admin@um.edu.my')
  const me = visible(page.getByTestId('account-row').filter({ hasText: '(you)' }))
  await expect(me).toBeVisible()
  await expect(me.getByText('Deactivate', { exact: true })).toHaveCount(0)
})

// T23a/T23c: a pending submission shows "Pending review" in Accounts, whose link opens Face verification; approving it shows up in Accounts on return, without signing in again.
test.describe('approve then Accounts', () => {
  const STUDENT = 'student8@example.com'
  const faceData = (action) =>
    execFileSync('python', ['scripts/e2e_face_review.py', action, '--student', STUDENT], { cwd: BACKEND, stdio: 'pipe' })
  test.beforeAll(() => { faceData('seed') })
  test.afterAll(() => { faceData('clean') })

  test('admin sees a pending face, reviews it from Accounts, and Accounts shows it on return', async ({ page }) => {
    await signIn(page, 'admin@um.edu.my', 'Admin@1234')
    await visible(page.getByTestId('account-search')).fill(STUDENT)
    const row = visible(page.getByTestId('account-row').filter({ hasText: STUDENT }))
    await expect(row.getByText('Pending review', { exact: true })).toBeVisible()
    await expect(row.getByText('No face data', { exact: true })).toHaveCount(0)

    await row.getByTestId('account-face-review').click()
    const card = visible(page.getByTestId('face-submission').filter({ hasText: '23004908' }))
    await expect(card).toBeVisible()
    await card.getByText('Approve', { exact: true }).click()
    await card.getByText('Confirm approve', { exact: true }).click()
    await expect(visible(page.getByText(/^Approved /))).toBeVisible()

    await page.getByTestId('sidenav-Accounts').click()
    await expect(row.getByText('Face enrolled', { exact: true })).toBeVisible()
  })
})

test('a reload keeps the administrator signed in', async ({ page }) => {
  await signIn(page, 'admin@um.edu.my', 'Admin@1234')
  await expect(page.getByTestId('sidenav-Accounts')).toBeVisible()
  await page.reload()
  await expect(page.getByTestId('sidenav-Accounts')).toBeVisible()
  await expect(page.getByText('Welcome back')).toHaveCount(0)

  // An expired access token is refreshed with the stored refresh token
  await page.evaluate(() => window.localStorage.setItem('token', 'expired.or.garbage'))
  await page.reload()
  await expect(page.getByTestId('sidenav-Accounts')).toBeVisible()

  // Signing out and reloading shows Login again
  await page.evaluate(() => { window.localStorage.removeItem('token'); window.localStorage.removeItem('refresh_token') })
  await page.reload()
  await expect(page.getByText('Welcome back')).toBeVisible()
})

test('a lecturer stays signed in after a reload too', async ({ page }) => {
  await signIn(page, 'devlecturer@um.edu.my', 'DevTest@1234')
  await expect(page.getByTestId('sidenav-Home')).toBeVisible()
  await page.reload()
  await expect(page.getByTestId('sidenav-Home')).toBeVisible()
})

test('administrator sign-in with a non-email asks for an email address', async ({ page }) => {
  await signIn(page, 'admin', 'Admin@1234')
  await expect(page.getByText('Enter your email address.', { exact: true })).toBeVisible()
  await expect(page.getByText(/value is not a valid email|HTTP 422|\[object Object\]/)).toHaveCount(0)
})

test('a lecturer sees no admin navigation and gets 403 from an admin endpoint', async ({ page }) => {
  await signIn(page, 'devlecturer@um.edu.my', 'DevTest@1234')
  await expect(page.getByTestId('sidenav-Home')).toBeVisible()
  for (const tab of ['Accounts', 'Verification', 'AuditLog', 'MoodleSync', 'Devices']) {
    await expect(page.getByTestId(`sidenav-${tab}`)).toHaveCount(0)
  }
  await expect(page.getByText('Accounts', { exact: true })).toHaveCount(0)

  // The token the app holds is refused by the admin endpoints
  const token = await page.evaluate(() => window.localStorage.getItem('token'))
  expect(token).toBeTruthy()
  const headers = { Authorization: `Bearer ${token}` }
  for (const path of ['/admin/users', '/admin/audit-logs', '/admin/moodle/sync']) {
    expect((await page.request.get(`${API}${path}`, { headers })).status()).toBe(403)
  }
})
