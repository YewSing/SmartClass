// Lecturer Interaction tab (plan-shino.md S38d): past and current class sessions with interaction data,
// newest first, and each session's summary with category pills (Questions, Polls, Quick questions,
// Reactions, Confusion) instead of one long page, plus the CSV download.
// Real backend data: a WIA0000 lecture four days ahead is started with M3's Start now
// (backend/scripts/e2e_interaction.py; interaction.spec.js uses three days, live-session.spec.js two),
// students ask, vote, answer, react and press "I don't understand" through the real API with their
// own tokens, the lecturer runs a poll and a quick question through the API, and the class is ended.
// Nothing is stubbed.
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')

const BACKEND = path.join(__dirname, '..', '..', '..', 'backend')
const API_PORT = Number(process.env.E2E_WEB_API_PORT || 8001)
const API = `http://localhost:${API_PORT}`
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const DAY = DAYS[new Date(Date.now() + 8 * 3600e3 + 4 * 86400e3).getUTCDay()]
const script = (...args) =>
  execFileSync('python', ['scripts/e2e_interaction.py', ...args], { cwd: BACKEND, stdio: 'pipe' }).toString()

const visible = (locator) => locator.filter({ visible: true }).first()
const all = (page, id) => page.getByTestId(id).filter({ visible: true })
const PILLS = ['questions', 'polls', 'quick', 'reactions', 'confusion']

let ctx            // { session_id, students: [{ name, token }] }
let ran = false    // the class is run once (by whichever test comes first), then both tests read it

test.beforeAll(() => {
  ctx = JSON.parse(script('setup', '--course', 'WIA0000', '--day', DAY, '--students', '3').trim().split('\n').pop())
  expect(ctx.students.length).toBeGreaterThanOrEqual(3)
})
test.afterAll(() => { script('teardown') })

const ix = (p = '') => `/interaction/${ctx.session_id}${p}`
const lx = (p = '') => `/lecturer/interaction/${ctx.session_id}${p}`

async function call(request, token, method, p, data, expected) {
  const res = await request.fetch(`${API}${p}`, { method, data, headers: { Authorization: `Bearer ${token}` } })
  if (expected) expect(res.status(), `${method} ${p}`).toBe(expected)
  return res
}

async function login(page) {
  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()
  await expect(visible(page.getByTestId('home-class-card'))).toBeVisible()
  return page.evaluate(() => localStorage.getItem('token'))
}

// 2 questions (one anonymous), a poll with 3 votes, a quick question with 2 answers, 3 reactions and
// 2 confusion presses; then the class ends
async function runClass(request, lecturer) {
  if (ran) return
  ran = true
  const st = ctx.students.map((s) => s.token)
  await call(request, st[0], 'POST', ix('/questions'), { text: 'E2E history: named question', anonymous: false }, 201)
  await call(request, st[1], 'POST', ix('/questions'), { text: 'E2E history: anonymous question', anonymous: true }, 201)

  const poll = await (await call(request, lecturer, 'POST', lx('/polls'),
    { question: 'E2E history poll', options: ['Yes', 'No'] }, 201)).json()
  await call(request, lecturer, 'POST', lx(`/polls/${poll.id}/start`), undefined, 200)
  for (const [i, o] of [[0, 0], [1, 1], [2, 0]]) {
    await call(request, st[i], 'POST', ix(`/polls/${poll.id}/vote`), { option_ids: [poll.options[o].id] }, 200)
  }
  await call(request, lecturer, 'POST', lx(`/polls/${poll.id}/close`), undefined, 200)

  const qq = await (await call(request, lecturer, 'POST', lx('/quick-questions'), { prompt: 'E2E history quick' }, 201)).json()
  await call(request, st[0], 'POST', ix(`/quick-questions/${qq.id}/answer`), { text: 'E2E answer one' }, 200)
  await call(request, st[1], 'POST', ix(`/quick-questions/${qq.id}/answer`), { text: 'E2E answer two' }, 200)

  for (const [i, kind] of [[0, 'thumbs_up'], [1, 'clear'], [2, 'too_fast']]) {
    await call(request, st[i], 'POST', ix('/reactions'), { kind }, 201)
  }
  for (const i of [0, 1]) await call(request, st[i], 'POST', ix('/confusion'), { topic: 'E2E recursion' }, 201)

  await call(request, lecturer, 'PUT', `/lecturer/sessions/${ctx.session_id}/close`, undefined, 200)
}

// The tab, the newest row (this class), its counts, then the summary and every pill
async function checkListAndSummary(page, width) {
  await expect(visible(page.getByTestId('ix-history-count'))).toContainText('with interaction')
  const row = visible(page.getByTestId('ix-history-row'))      // newest first: the class just run
  await expect(row).toContainText('WIA0000')
  for (const [key, label] of [['questions', '2 questions'], ['polls', '1 poll'], ['quick', '1 quick question'],
    ['reactions', '3 reactions'], ['confusion', '2 confused']]) {
    await expect(row.getByTestId(`ix-history-chip-${key}`)).toHaveText(label)
  }
  for (const s of ctx.students) await expect(row).not.toContainText(s.name)
  const rowBox = await row.boundingBox()
  expect(rowBox.x + rowBox.width).toBeLessThanOrEqual(width)

  await row.click()
  await expect(visible(page.getByText('Interaction summary', { exact: true }))).toBeVisible()
  await expect(visible(page.getByText('Ended', { exact: true }))).toBeVisible()
  await expect(visible(page.getByTestId('ix-summary-csv'))).toBeVisible()
  for (const key of PILLS) {
    const box = await visible(page.getByTestId(`ix-pill-${key}`)).boundingBox()
    expect(box, key).not.toBeNull()
  }
  await expect(visible(page.getByTestId('ix-pill-questions'))).toContainText('2')
  await expect(visible(page.getByTestId('ix-pill-reactions'))).toContainText('3')

  // Questions first; only one category shows at a time
  const only = async (key) => {
    await expect(visible(page.getByTestId(`ix-summary-part-${key}`))).toBeVisible()
    for (const other of PILLS.filter((k) => k !== key)) {
      await expect(all(page, `ix-summary-part-${other}`)).toHaveCount(0)
    }
  }
  await only('questions')
  await expect(visible(page.getByTestId('ix-summary-asked'))).toHaveText('2')
  await expect(visible(page.getByTestId('ix-summary-anonymous'))).toHaveText('1')
  const anon = visible(all(page, 'ix-summary-question').filter({ hasText: 'E2E history: anonymous question' }))
  await expect(anon).toContainText('Anonymous')
  await expect(anon).not.toContainText(ctx.students[1].name)

  await visible(page.getByTestId('ix-pill-polls')).click()
  await only('polls')
  await expect(visible(page.getByTestId('ix-summary-poll'))).toContainText('3 voted')

  await visible(page.getByTestId('ix-pill-quick')).click()
  await only('quick')
  await expect(all(page, 'ix-summary-quick-answer')).toHaveCount(2)

  await visible(page.getByTestId('ix-pill-reactions')).click()
  await only('reactions')
  await expect(visible(page.getByTestId('ix-summary-reactions-total'))).toHaveText('3 in total')

  await visible(page.getByTestId('ix-pill-confusion')).click()
  await only('confusion')
  await expect(visible(page.getByTestId('ix-summary-confusion-total'))).toHaveText('2')
  await expect(visible(page.getByTestId('ix-summary-topic'))).toContainText('E2E recursion')
  const pageWidth = await page.evaluate(() => document.documentElement.scrollWidth)
  expect(pageWidth).toBeLessThanOrEqual(width)

  // Back to the list
  await visible(page.getByLabel('Back')).click()
  await expect(visible(page.getByTestId('ix-history-row'))).toBeVisible()
}

test.describe('at 1280 px', () => {
  test('the Interaction side-menu item lists the class; its summary switches category with pills', async ({ page, request }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    const token = await login(page)
    await runClass(request, token)
    await page.getByTestId('sidenav-Interaction').click()
    await expect(visible(page.getByText('Interaction', { exact: true }))).toBeVisible()
    await checkListAndSummary(page, 1280)
    expect(errors).toEqual([])
  })
})

test.describe('at phone width', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('the Interaction bottom tab lists the class; the pills fit the phone', async ({ page, request }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    const token = await login(page)
    await runClass(request, token)
    await visible(page.getByRole('tab', { name: 'Interaction' }).or(page.getByRole('link', { name: 'Interaction' }))).click()
    await checkListAndSummary(page, 390)
    expect(errors).toEqual([])
  })
})
