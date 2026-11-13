// T46: admin Devices page (FR-408, NFR-23). Registers a device in a unique "E2E T46 <time>" room,
// checks the key is shown once and works for a heartbeat, regenerates it, and checks the old key is
// refused. `scripts/e2e_devices.py clean` removes the test devices.
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')

const API = `http://localhost:${process.env.E2E_WEB_API_PORT || 8001}`
const BACKEND = path.join(__dirname, '..', '..', '..', 'backend')

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

const cleanDevices = () =>
  execFileSync('python', ['scripts/e2e_devices.py', 'clean'], { cwd: BACKEND, stdio: 'pipe' })

// A crashed earlier run must not leave a device in the room this run will use
test.beforeAll(() => { cleanDevices() })
test.afterAll(() => { cleanDevices() })

test('admin registers a device, sees it online after a heartbeat, and regenerates its key', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  const ROOM = `E2E T46 ${Date.now()}`
  const NAME = 'E2E door camera'

  await signIn(page, 'admin@um.edu.my', 'Admin@1234')
  await page.getByTestId('sidenav-Devices').click()
  await expect(visible(page.getByText('Camera devices', { exact: true }))).toBeVisible()

  // The form checks its fields before sending
  await page.getByTestId('device-register-open').click()
  await page.getByTestId('new-device-submit').click()
  await expect(page.getByText('Enter a device name and a room.', { exact: true })).toBeVisible()

  await page.getByTestId('new-device-name').fill(NAME)
  await page.getByTestId('new-device-room').fill(ROOM)
  await page.getByTestId('new-device-submit').click()

  // The key is shown once, right after registering
  await expect(visible(page.getByTestId('device-key-panel'))).toBeVisible()
  const key1 = (await visible(page.getByTestId('device-key')).textContent()).trim()
  expect(key1).toMatch(/^scd_[A-Za-z0-9_-]{20,}$/)

  const row = visible(page.getByTestId('device-row').filter({ hasText: ROOM }))
  await expect(row).toBeVisible()
  await expect(row.getByTestId('device-status')).toHaveText('Never connected')

  // A heartbeat with the key makes it online
  const beat1 = await page.request.post(`${API}/device/heartbeat`, { headers: { 'X-Device-Key': key1 } })
  expect(beat1.status()).toBe(200)
  await page.getByTestId('devices-refresh').click()
  await expect(row.getByTestId('device-status')).toHaveText('Online')

  // Done hides the key for good
  await page.getByTestId('device-key-done').click()
  await expect(page.getByTestId('device-key-panel')).toHaveCount(0)
  await expect(page.getByText(key1)).toHaveCount(0)

  // One device per room
  await page.getByTestId('device-register-open').click()
  await page.getByTestId('new-device-name').fill(NAME)
  await page.getByTestId('new-device-room').fill(ROOM)
  await page.getByTestId('new-device-submit').click()
  await expect(visible(page.getByText(/already has a device/))).toBeVisible()
  await expect(page.getByTestId('device-key-panel')).toHaveCount(0)
  await visible(page.getByTestId('register-device-form')).getByText('Cancel', { exact: true }).click()

  // Regenerating asks first, then shows the new key and revokes the old one
  await row.getByTestId('device-regenerate').click()
  await expect(row.getByText(/old key stops working/)).toBeVisible()
  await row.getByTestId('device-regenerate-confirm').click()

  const panel2 = visible(page.getByTestId('device-key-panel'))
  await expect(panel2).toBeVisible()
  await expect(panel2).toContainText('The old key has stopped working.')
  const key2 = (await visible(page.getByTestId('device-key')).textContent()).trim()
  expect(key2).toMatch(/^scd_[A-Za-z0-9_-]{20,}$/)
  expect(key2).not.toBe(key1)

  expect((await page.request.post(`${API}/device/heartbeat`, { headers: { 'X-Device-Key': key1 } })).status()).toBe(401)
  expect((await page.request.post(`${API}/device/heartbeat`, { headers: { 'X-Device-Key': key2 } })).status()).toBe(200)

  // Both changes are in the audit log
  await page.getByTestId('sidenav-AuditLog').click()
  await expect(visible(page.getByText('Registered camera device', { exact: true }))).toBeVisible()
  await expect(visible(page.getByText('New camera device key', { exact: true }))).toBeVisible()

  expect(errors).toEqual([])
})

test('a lecturer gets 403 from the device endpoints', async ({ page }) => {
  await signIn(page, 'devlecturer@um.edu.my', 'DevTest@1234')
  await expect(page.getByTestId('sidenav-Home')).toBeVisible()
  await expect(page.getByTestId('sidenav-Devices')).toHaveCount(0)

  // The token the app holds is refused by the device endpoints
  const token = await page.evaluate(() => window.localStorage.getItem('token'))
  expect(token).toBeTruthy()
  const headers = { Authorization: `Bearer ${token}` }
  expect((await page.request.get(`${API}/admin/devices`, { headers })).status()).toBe(403)
  expect((await page.request.post(`${API}/admin/devices`, { headers, data: { name: 'x', room: 'E2E T46 lecturer' } })).status())
    .toBe(403)
})
