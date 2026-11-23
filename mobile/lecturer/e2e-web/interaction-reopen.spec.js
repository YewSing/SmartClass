// Lecturer live interaction after a class is reopened (plan-shino.md S38e, S38a). Real backend data:
// a WIA0000 lecture three days ahead is started with M3's Start now (backend/scripts/e2e_interaction.py);
// the class is ended with M3's close while the lecturer watches LiveInteraction, then started again in
// its slot (`e2e_interaction.py reopen`: M3's own Start now reopens the same session id). Without
// leaving the screen, it must turn Live again within a few seconds, reconnect its websocket and show
// a student's new question live. The only stub: GET /lecturer/sessions is narrowed to this session,
// so another open class on the dev DB can't take the dashboard's session card.
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')

const BACKEND = path.join(__dirname, '..', '..', '..', 'backend')
const API_PORT = Number(process.env.E2E_WEB_API_PORT || 8001)
const API = `http://localhost:${API_PORT}`
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const DAY = DAYS[new Date(Date.now() + 8 * 3600e3 + 3 * 86400e3).getUTCDay()]
const script = (...args) =>
  execFileSync('python', ['scripts/e2e_interaction.py', ...args], { cwd: BACKEND, stdio: 'pipe' }).toString()
const lastJson = (out) => JSON.parse(out.trim().split('\n').pop())

const visible = (locator) => locator.filter({ visible: true }).first()
const all = (page, id) => page.getByTestId(id).filter({ visible: true })
// "within a few seconds": the client re-checks every 5 s, so a reopen shows well inside this
const PICKUP_MS = 20_000

let ctx   // { session_id, students: [{ name, token }] }
let leftEnded = false

test.beforeAll(() => {
  ctx = lastJson(script('setup', '--course', 'WIA0000', '--day', DAY, '--students', '2'))
  expect(ctx.students.length).toBeGreaterThanOrEqual(2)
})
test.afterAll(() => { script('teardown') })

const ix = (p = '') => `/interaction/${ctx.session_id}${p}`
// A fresh connection per call: the waits between calls outlast uvicorn's keep-alive, and reusing a
// connection the server just dropped fails with ECONNRESET
const auth = (token) => ({ Authorization: `Bearer ${token}`, Connection: 'close' })
const ask = (request, i, text) => request.post(`${API}${ix('/questions')}`, {
  data: { text, anonymous: false }, headers: auth(ctx.students[i].token),
})

async function login(page) {
  await page.route((url) => url.port === String(API_PORT) && url.pathname === '/lecturer/sessions', async (route) => {
    const res = await route.fetch()
    const list = (await res.json()).filter((s) => s.id === ctx.session_id)
    await route.fulfill({ response: res, body: JSON.stringify(list) })
  })
  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()
  await expect(visible(page.getByTestId('home-class-card'))).toBeVisible()
}

for (const [name, viewport] of [['at 1280 px', { width: 1280, height: 800 }], ['at phone width', { width: 390, height: 844 }]]) {
  test.describe(name, () => {
    test.use({ viewport })

    test('the class ends, is reopened in its slot, and the open screen goes live again by itself', async ({ page, request }) => {
      const errors = []
      page.on('pageerror', (e) => errors.push(e.message))
      // The earlier viewport's run left the class ended: start it again for this one
      if (leftEnded) lastJson(script('reopen', '--session', String(ctx.session_id)))
      const sockets = []
      page.on('websocket', (ws) => { if (ws.url().includes(`/interaction/${ctx.session_id}/ws`)) sockets.push(ws) })
      await login(page)
      await visible(page.getByTestId('home-interaction')).click()
      await expect(visible(page.getByText('Class interaction', { exact: true }))).toBeVisible()
      await expect(visible(page.getByText('Open', { exact: true }))).toBeVisible()
      const tag = `E2E ${viewport.width}`
      expect((await ask(request, 0, `${tag} before the end`)).status()).toBe(201)
      await expect(visible(all(page, 'ix-question').filter({ hasText: `${tag} before the end` }))).toBeVisible()

      // M3's close (as Home's End class does): the screen turns to "ended" by itself
      const token = await page.evaluate(() => localStorage.getItem('token'))
      const closed = await request.put(`${API}/lecturer/sessions/${ctx.session_id}/close`, { headers: auth(token) })
      expect(closed.status()).toBe(200)
      await expect(visible(page.getByTestId('ix-ended'))).toBeVisible()
      await expect(visible(page.getByText('Class ended', { exact: true }))).toBeVisible()
      expect((await ask(request, 1, `${tag} while ended`)).status()).toBe(409)
      const socketsBefore = sockets.length

      // Started again inside its slot: the same session (S38a)
      expect(lastJson(script('reopen', '--session', String(ctx.session_id)))).toEqual({
        session_id: ctx.session_id, reopened: true,
      })

      // Same screen, no navigation: Live again, a new socket, the earlier question still there
      await expect(visible(page.getByText('Open', { exact: true }))).toBeVisible({ timeout: PICKUP_MS })
      await expect(all(page, 'ix-ended')).toHaveCount(0)
      await expect(visible(page.getByText('The class is live again'))).toBeVisible()
      await expect.poll(() => sockets.length, { timeout: PICKUP_MS }).toBeGreaterThan(socketsBefore)
      await expect(visible(page.getByTestId('ix-pause'))).toBeEnabled()
      await expect(visible(page.getByTestId('ix-poll-new'))).toBeEnabled()
      await expect(visible(all(page, 'ix-question').filter({ hasText: `${tag} before the end` }))).toBeVisible()

      // A new question arrives live over the reconnected socket (no reload, no re-check needed)
      expect((await ask(request, 1, `${tag} after the reopen`)).status()).toBe(201)
      await expect(visible(all(page, 'ix-question').filter({ hasText: `${tag} after the reopen` })))
        .toBeVisible({ timeout: 4_000 })
      expect(errors).toEqual([])

      // Leave the class ended for the next run / test
      expect((await request.put(`${API}/lecturer/sessions/${ctx.session_id}/close`, { headers: auth(token) }))
        .status()).toBe(200)
      leftEnded = true
    })
  })
}
