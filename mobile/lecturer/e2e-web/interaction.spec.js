// Lecturer live interaction in the browser (plan-shino.md S37; FR-501–FR-519). Real backend data: a
// WIA0000 lecture three days ahead is started with M3's Start now (backend/scripts/e2e_interaction.py),
// and enrolled students act through the real API with their own tokens while the lecturer watches the
// screen update live over WS /interaction/{id}/ws. At 1280 px: questions (named + anonymous, upvote,
// answer, pin, hide), a poll, a quick question, reactions, confusion, pause/resume, the summary and its
// CSV. At phone width: the tabbed layout, then the class ends and the screen and summary show it.
// The only stub: GET /lecturer/sessions is narrowed to this session, so another open class on the dev
// DB can't take the dashboard's session card.
const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')

const BACKEND = path.join(__dirname, '..', '..', '..', 'backend')
const API_PORT = Number(process.env.E2E_WEB_API_PORT || 8001)
const API = `http://localhost:${API_PORT}`
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
// Malaysia (UTC+8) weekday three days from now (live-session.spec.js uses two)
const DAY = DAYS[new Date(Date.now() + 8 * 3600e3 + 3 * 86400e3).getUTCDay()]
const script = (...args) =>
  execFileSync('python', ['scripts/e2e_interaction.py', ...args], { cwd: BACKEND, stdio: 'pipe' }).toString()

const visible = (locator) => locator.filter({ visible: true }).first()
const all = (page, id) => page.getByTestId(id).filter({ visible: true })

let ctx   // { session_id, students: [{ name, token }] }

test.beforeAll(() => {
  ctx = JSON.parse(script('setup', '--course', 'WIA0000', '--day', DAY, '--students', '3').trim().split('\n').pop())
  expect(ctx.students.length).toBeGreaterThanOrEqual(3)
})
test.afterAll(() => { script('teardown') })

// A student's call to the real API
async function as(request, i, method, p, data) {
  const res = await request.fetch(`${API}${p}`, {
    method, data, headers: { Authorization: `Bearer ${ctx.students[i].token}` },
  })
  return res
}
const ix = (p = '') => `/interaction/${ctx.session_id}${p}`

async function login(page) {
  // Only this flow's session, so the session card is its class
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

async function openInteraction(page) {
  await visible(page.getByTestId('home-interaction')).click()
  await expect(visible(page.getByText('Class interaction', { exact: true }))).toBeVisible()
  await expect(visible(page.getByText('Open', { exact: true }))).toBeVisible()
}

test.describe('at 1280 px', () => {
  test('moderates questions, runs a poll and a quick question, sees signals live, exports the summary', async ({ page, request }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    const [a, b, c] = ctx.students
    await login(page)
    await openInteraction(page)
    await expect(visible(page.getByTestId('ix-questions-empty'))).toBeVisible()
    // Wide layout: reactions and confusion sit beside the tabs, no Signals tab
    await expect(visible(page.getByTestId('ix-signals'))).toBeVisible()
    await expect(all(page, 'ix-tab-signals')).toHaveCount(0)

    // ── Questions arrive live; the anonymous one never shows a name ──
    expect((await as(request, 0, 'POST', ix('/questions'), { text: 'E2E what makes a sort stable?', anonymous: false })).status()).toBe(201)
    expect((await as(request, 1, 'POST', ix('/questions'), { text: 'E2E anonymous: is quicksort stable?', anonymous: true })).status()).toBe(201)
    const named = visible(all(page, 'ix-question').filter({ hasText: 'E2E what makes a sort stable?' }))
    const anon = visible(all(page, 'ix-question').filter({ hasText: 'E2E anonymous: is quicksort stable?' }))
    await expect(named).toContainText(a.name)
    await expect(anon).toContainText('Anonymous')
    await expect(anon).not.toContainText(b.name)

    const qid = (await (await as(request, 1, 'GET', ix('/questions'))).json())
      .questions.find((q) => q.text.startsWith('E2E what makes')).id
    expect((await as(request, 1, 'POST', ix(`/questions/${qid}/upvote`))).status()).toBe(200)
    expect((await as(request, 2, 'POST', ix(`/questions/${qid}/upvote`))).status()).toBe(200)
    await expect(named.getByTestId('ix-question-upvotes')).toHaveText('2')
    await expect(visible(page.getByTestId('ix-tab-questions'))).toHaveText('Questions (2)')

    await named.getByTestId('ix-q-answer').click()
    await expect(named).toContainText('Answered')
    await named.getByTestId('ix-q-pin').click()
    await expect(named).toContainText('Pinned')
    await anon.getByTestId('ix-q-hide').click()
    await expect(anon).toContainText('Hidden')
    // Students no longer get the hidden one
    const studentView = (await (await as(request, 2, 'GET', ix('/questions'))).json()).questions.map((q) => q.text)
    expect(studentView).not.toContain('E2E anonymous: is quicksort stable?')
    await expect(visible(page.getByTestId('ix-tab-questions'))).toHaveText('Questions')

    // ── Poll: checked form, start, live votes, close ──
    await visible(page.getByTestId('ix-tab-polls')).click()
    await visible(page.getByTestId('ix-poll-new')).click()
    await visible(page.getByTestId('ix-poll-question')).fill('E2E which sort is stable?')
    await visible(page.getByTestId('ix-poll-option-input-0')).fill('Merge sort')
    await visible(page.getByTestId('ix-poll-create-start')).click()
    await expect(visible(page.getByTestId('ix-poll-error'))).toHaveText('Give at least 2 options.')
    await visible(page.getByTestId('ix-poll-option-input-1')).fill('Quicksort')
    await visible(page.getByTestId('ix-poll-add-option')).click()
    await visible(page.getByTestId('ix-poll-option-input-2')).fill('Heap sort')
    await visible(page.getByTestId('ix-poll-create-start')).click()
    const poll = visible(all(page, 'ix-poll').filter({ hasText: 'E2E which sort is stable?' }))
    await expect(poll).toContainText('Live')
    await expect(poll.getByTestId('ix-poll-total')).toContainText('0 voted')

    const polls = (await (await as(request, 0, 'GET', ix('/polls'))).json()).polls
    const live = polls.find((p) => p.question === 'E2E which sort is stable?')
    const opt = Object.fromEntries(live.options.map((o) => [o.text, o.id]))
    for (const [i, choice] of [[0, 'Merge sort'], [1, 'Quicksort'], [2, 'Merge sort']]) {
      expect((await as(request, i, 'POST', ix(`/polls/${live.id}/vote`), { option_ids: [opt[choice]] })).status()).toBe(200)
    }
    await expect(poll.getByTestId('ix-poll-total')).toContainText('3 voted')
    await expect(poll.getByTestId('ix-poll-option').filter({ hasText: 'Merge sort' })).toContainText('2 · 67%')
    await expect(poll.getByTestId('ix-poll-option').filter({ hasText: 'Quicksort' })).toContainText('1 · 33%')
    await expect(poll.getByTestId('ix-poll-option').filter({ hasText: 'Heap sort' })).toContainText('0 · 0%')
    await poll.getByTestId('ix-poll-close').click()
    await expect(poll).toContainText('Closed')
    expect((await as(request, 1, 'POST', ix(`/polls/${live.id}/vote`), { option_ids: [opt['Heap sort']] })).status()).toBe(409)

    // ── Quick question: answers arrive live without names ──
    await visible(page.getByTestId('ix-tab-quick')).click()
    await visible(page.getByTestId('ix-quick-prompt')).fill('E2E one word: what does stable mean?')
    await visible(page.getByTestId('ix-quick-max')).fill('40')
    await visible(page.getByTestId('ix-quick-create')).click()
    const quick = visible(all(page, 'ix-quick').filter({ hasText: 'E2E one word' }))
    await expect(quick).toContainText('0 answers · up to 40 characters')
    const qq = (await (await as(request, 0, 'GET', ix('/quick-questions'))).json()).quick_questions[0]
    expect((await as(request, 0, 'POST', ix(`/quick-questions/${qq.id}/answer`), { text: 'E2E order kept' })).status()).toBe(200)
    expect((await as(request, 1, 'POST', ix(`/quick-questions/${qq.id}/answer`), { text: 'E2E ties stay' })).status()).toBe(200)
    await expect(quick.getByTestId('ix-quick-answer')).toHaveCount(2)
    await expect(quick).toContainText('E2E order kept')
    for (const s of [a, b]) await expect(quick).not.toContainText(s.name)
    await quick.getByTestId('ix-quick-close').click()
    await expect(quick).toContainText('Closed')

    // ── Reactions and confusion (lecturer only, live) ──
    for (const [i, kind] of [[0, 'thumbs_up'], [1, 'thumbs_up'], [2, 'too_fast']]) {
      expect((await as(request, i, 'POST', ix('/reactions'), { kind })).status()).toBe(201)
    }
    await expect(visible(page.getByTestId('ix-reaction-thumbs_up'))).toHaveText('2')
    await expect(visible(page.getByTestId('ix-reaction-too_fast'))).toHaveText('1')
    await expect(visible(page.getByTestId('ix-reactions-total'))).toHaveText('3 in total')
    for (const i of [0, 1]) {
      expect((await as(request, i, 'POST', ix('/confusion'), { topic: 'recursion' })).status()).toBe(201)
    }
    await expect(visible(page.getByTestId('ix-confusion-total'))).toHaveText('2')
    await expect(visible(page.getByTestId('ix-confusion-recent'))).toContainText('2 of ')
    await expect(all(page, 'ix-confusion-bar').first()).toBeVisible()
    await expect(visible(page.getByTestId('ix-confusion-topic'))).toContainText('recursion')
    await expect(visible(page.getByTestId('ix-signals'))).not.toContainText(a.name)

    // ── Pause stops student posts; resume lets them in again ──
    await visible(page.getByTestId('ix-pause')).click()
    await expect(visible(page.getByText('Paused', { exact: true }))).toBeVisible()
    expect((await as(request, 2, 'POST', ix('/questions'), { text: 'E2E while paused', anonymous: false })).status()).toBe(409)
    await visible(page.getByTestId('ix-resume')).click()
    await expect(visible(page.getByText('Open', { exact: true }))).toBeVisible()

    // ── Summary and CSV (works while the class runs) ──
    await visible(page.getByTestId('ix-summary')).click()
    await expect(visible(page.getByText('Interaction summary', { exact: true }))).toBeVisible()
    await expect(visible(page.getByTestId('ix-summary-asked'))).toHaveText('2')
    await expect(visible(page.getByTestId('ix-summary-answered'))).toHaveText('1')
    await expect(visible(page.getByTestId('ix-summary-anonymous'))).toHaveText('1')
    await expect(visible(page.getByTestId('ix-summary-upvotes'))).toHaveText('2')
    await expect(visible(page.getByTestId('ix-summary-reactions-total'))).toHaveText('3 in total')
    await expect(visible(page.getByTestId('ix-summary-confusion-total'))).toHaveText('2')
    await expect(visible(page.getByTestId('ix-summary-poll'))).toContainText('3 voted')
    await expect(all(page, 'ix-summary-quick-answer')).toHaveCount(2)
    const summaryAnon = visible(all(page, 'ix-summary-question').filter({ hasText: 'E2E anonymous' }))
    await expect(summaryAnon).toContainText('Anonymous')
    await expect(summaryAnon).not.toContainText(b.name)

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      visible(page.getByTestId('ix-summary-csv')).click(),
    ])
    expect(download.suggestedFilename()).toMatch(new RegExp(`^interaction_WIA0000_\\d{8}_${ctx.session_id}\\.csv$`))
    const csv = fs.readFileSync(await download.path(), 'utf-8')
    expect(csv).toContain('Section,Time,Text,Author,Status,Count')
    expect(csv).toContain('E2E what makes a sort stable?')
    expect(csv).toContain(a.name)
    expect(csv).toMatch(/E2E anonymous: is quicksort stable\?,Anonymous/)
    expect(csv).not.toContain(b.name)
    expect(csv).not.toContain(c.name)
    await expect(visible(page.getByText(/Downloaded interaction_WIA0000/))).toBeVisible()
    expect(errors).toEqual([])
  })
})

test.describe('at phone width', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('tabs fit the phone; the class ends live and the summary opens from the dashboard', async ({ page, request }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    await login(page)
    await openInteraction(page)

    // Four tabs, Signals among them; everything inside 390 px
    for (const t of ['questions', 'polls', 'quick', 'signals']) await expect(visible(page.getByTestId(`ix-tab-${t}`))).toBeVisible()
    const named = visible(all(page, 'ix-question').filter({ hasText: 'E2E what makes a sort stable?' }))
    await expect(named).toBeVisible()
    for (const loc of [named, visible(page.getByTestId('ix-tab-signals')), visible(page.getByTestId('ix-summary'))]) {
      const box = await loc.boundingBox()
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(390)
    }
    expect((await as(request, 2, 'POST', ix('/questions'), { text: 'E2E phone question', anonymous: false })).status()).toBe(201)
    await expect(visible(all(page, 'ix-question').filter({ hasText: 'E2E phone question' }))).toBeVisible()

    await visible(page.getByTestId('ix-tab-signals')).click()
    await expect(visible(page.getByTestId('ix-signals'))).toBeVisible()
    expect((await as(request, 2, 'POST', ix('/confusion'), {})).status()).toBe(201)
    await expect(visible(page.getByTestId('ix-confusion-total'))).toHaveText('3')

    // The class ends (M3's close, as Home's End class does): the screen turns to "ended" by itself
    const token = await page.evaluate(() => localStorage.getItem('token'))
    const closed = await request.put(`${API}/lecturer/sessions/${ctx.session_id}/close`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(closed.status()).toBe(200)
    await expect(visible(page.getByTestId('ix-ended'))).toBeVisible()
    await expect(visible(page.getByText('Class ended', { exact: true }))).toBeVisible()
    await expect(all(page, 'ix-pause')).toHaveCount(0)
    await visible(page.getByTestId('ix-tab-questions')).click()
    await expect(visible(page.getByTestId('ix-q-answer'))).toBeDisabled()
    await visible(page.getByTestId('ix-ended-summary')).click()
    await expect(visible(page.getByTestId('ix-summary-asked'))).toHaveText('3')
    await expect(visible(page.getByText('Ended', { exact: true }))).toBeVisible()

    // After class, Home's latest-class card links to the same summary (dashboard answer narrowed to
    // this session, as another class may be newer on the dev DB)
    await page.route((url) => url.port === String(API_PORT) && url.pathname === '/lecturer/dashboard', async (route) => {
      const res = await route.fetch()
      const body = await res.json()
      body.attendance_overview = {
        ...(body.attendance_overview ?? {}), session_id: ctx.session_id, occurrence_id: 0, course_id: 0,
        course_code: 'WIA0000', course_name: 'Dev Test Class', class_type: 'LECTURE', class_label: null,
        session_status: 'closed', date: '2026-11-23', starts_at: null, enrolled: 3, present: 0, late: 0,
        excused: 0, absent: 3, not_recorded: 0, rate: 0,
      }
      await route.fulfill({ response: res, body: JSON.stringify(body) })
    })
    await page.goto('/')
    const link = visible(page.getByTestId('dash-overview-summary'))
    await expect(link).toBeVisible()
    const box = await link.boundingBox()
    expect(box.x + box.width).toBeLessThanOrEqual(390)
    await link.click()
    await expect(visible(page.getByTestId('ix-summary-confusion-total'))).toHaveText('3')
    expect(errors).toEqual([])
  })
})
