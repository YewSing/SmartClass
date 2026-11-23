import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  TOPICS, topicsFor, interactionState, liveClasses, validateQuestion, askerLabel, questionBadges, canUpvote,
  toggleChoice, voteAction, pollResultsVisible, pollBars, sortPolls, validateQuickAnswer, charsLeft,
  nextAllowedAt, secondsLeft, cooldownLabel, myQuestionMeta, myQuestionBadge, mergeQuestionPages,
  connectInteractionLive, classRunning, QUESTION_MAX_CHARS,
  latestPoll, latestQuick, newestQuestions, questionTags, QUESTIONS_ON_PAGE,
} from './interaction.js'

// ─── one-page layout (S38c) ──────────────────────────────────────────────────

test('the page shows only the latest poll: the newest open one, else the newest', () => {
  const polls = [
    { id: 1, status: 'closed', created_at: '2026-11-23T08:00:00Z' },
    { id: 2, status: 'open', created_at: '2026-11-23T08:10:00Z' },
    { id: 3, status: 'closed', created_at: '2026-11-23T08:20:00Z' },
  ]
  assert.equal(latestPoll(polls).id, 2, 'an open poll wins over a newer closed one')
  assert.equal(latestPoll(polls.filter(p => p.id !== 2)).id, 3, 'none open: the newest')
  assert.equal(latestPoll([]), null)
  assert.equal(latestPoll(undefined), null)
  // Same created_at: the higher id is newer
  assert.equal(latestPoll([{ id: 4, status: 'closed', created_at: 'x' }, { id: 5, status: 'closed', created_at: 'x' }]).id, 5)
})

test('the page shows only the latest quick question', () => {
  const quick = [
    { id: 7, status: 'closed', created_at: '2026-11-23T08:00:00Z', my_answer: 'old' },
    { id: 8, status: 'closed', created_at: '2026-11-23T08:30:00Z', my_answer: null },
  ]
  assert.equal(latestQuick(quick).id, 8)
  assert.equal(latestQuick([...quick, { id: 9, status: 'open', created_at: '2026-11-23T08:40:00Z' }]).id, 9)
  assert.equal(latestQuick(null), null)
})

test('the page lists the newest 3 questions, newest first, without changing the input', () => {
  const qs = [1, 2, 3, 4, 5].map(i => ({ id: i, created_at: `2026-11-23T08:0${i}:00Z`, upvotes: 6 - i }))
  const before = qs.map(q => q.id)
  assert.equal(QUESTIONS_ON_PAGE, 3)
  assert.deepEqual(newestQuestions(qs).map(q => q.id), [5, 4, 3])
  assert.deepEqual(qs.map(q => q.id), before)
  assert.deepEqual(newestQuestions(qs, 1).map(q => q.id), [5])
  assert.deepEqual(newestQuestions(undefined), [])
})

test('own questions carry a Mine tag before the status badges', () => {
  assert.deepEqual(questionTags({ mine: true, pinned: true, answered: true }).map(b => b.label), ['Mine', 'Pinned', 'Answered'])
  assert.deepEqual(questionTags({ mine: false, answered: true }).map(b => b.label), ['Answered'])
  assert.deepEqual(questionTags(null), [])
})

// ─── websocket topics and state ──────────────────────────────────────────────

test('students re-read only their own topics', () => {
  assert.deepEqual(TOPICS, ['questions', 'polls', 'quick_questions'])
  assert.deepEqual(topicsFor({ type: 'connected' }), ['session', 'questions', 'polls', 'quick_questions'])
  assert.deepEqual(topicsFor({ type: 'changed', topic: 'polls' }), ['polls'])
  assert.deepEqual(topicsFor({ type: 'changed', topic: 'reactions' }), [], 'lecturer-only topic')
  assert.deepEqual(topicsFor({ type: 'changed', topic: 'nonsense' }), [])
  assert.deepEqual(topicsFor({ type: 'closed', reason: 'class_ended' }), ['session'])
  assert.deepEqual(topicsFor({ type: 'opened' }), ['session'])
  assert.deepEqual(topicsFor(null), [])
  assert.deepEqual(topicsFor({ type: 7 }), [])
})

test('interaction state: live, paused, not started, ended', () => {
  assert.equal(interactionState(null).label, 'Loading')
  const live = interactionState({ status: 'open', class_status: 'open' })
  assert.deepEqual([live.label, live.open, live.ended], ['Live', true, false])
  const paused = interactionState({ status: 'closed', closed_reason: 'lecturer', class_status: 'open' })
  assert.deepEqual([paused.label, paused.open, paused.ended], ['Paused', false, false])
  const early = interactionState({ status: 'closed', closed_reason: 'not_started', class_status: 'scheduled' })
  assert.deepEqual([early.label, early.ended], ['Not started', false])
  for (const cs of ['closed', 'needs_confirmation', 'cancelled']) {
    const s = interactionState({ status: 'closed', closed_reason: 'class_ended', class_status: cs })
    assert.deepEqual([s.label, s.open, s.ended], ['Class ended', false, true], cs)
  }
  // An early lecturer close on a class that has since ended reads as ended
  assert.equal(interactionState({ status: 'closed', closed_reason: 'lecturer', class_status: 'closed' }).ended, true)
})

test('only open class sessions of today can be joined', () => {
  const today = [
    { occurrence_id: 1, session_id: 10, session_status: 'open' },
    { occurrence_id: 2, session_id: 11, session_status: 'closed' },
    { occurrence_id: 3, session_id: null, session_status: null },
    { occurrence_id: 4, session_id: 12, session_status: 'needs_confirmation' },
  ]
  assert.deepEqual(liveClasses(today).map(c => c.session_id), [10])
  assert.deepEqual(liveClasses(null), [])
})

// ─── questions ───────────────────────────────────────────────────────────────

test('question text is trimmed and limited to 500 characters', () => {
  assert.deepEqual(validateQuestion('  Why O(n log n)?  '), { text: 'Why O(n log n)?' })
  assert.ok(validateQuestion('   ').error)
  assert.ok(validateQuestion(undefined).error)
  assert.ok(validateQuestion('x'.repeat(QUESTION_MAX_CHARS + 1)).error)
  assert.deepEqual(validateQuestion('x'.repeat(QUESTION_MAX_CHARS)), { text: 'x'.repeat(QUESTION_MAX_CHARS) })
})

test('asker label never names an anonymous asker and marks your own', () => {
  assert.equal(askerLabel({ anonymous: false, author_name: 'Ali', mine: false }), 'Ali')
  assert.equal(askerLabel({ anonymous: true, author_name: null, mine: false }), 'Anonymous')
  // even if a name slipped through, an anonymous question shows none
  assert.equal(askerLabel({ anonymous: true, author_name: 'Ali', mine: false }), 'Anonymous')
  assert.equal(askerLabel({ anonymous: false, author_name: 'Me', mine: true }), 'You')
  assert.equal(askerLabel({ anonymous: true, author_name: null, mine: true }), 'You (anonymous)')
})

test('badges and upvote rules', () => {
  assert.deepEqual(questionBadges({ pinned: true, answered: true }).map(b => b.label), ['Pinned', 'Answered'])
  assert.deepEqual(questionBadges({}), [])
  assert.equal(canUpvote({ mine: false, upvoted_by_me: false }, true), true)
  assert.equal(canUpvote({ mine: true, upvoted_by_me: false }, true), false, 'own question')
  assert.equal(canUpvote({ mine: false, upvoted_by_me: true }, true), false, 'once only')
  assert.equal(canUpvote({ mine: false, upvoted_by_me: false }, false), false, 'interaction closed')
})

// ─── polls ───────────────────────────────────────────────────────────────────

test('choosing options: single replaces, multiple toggles', () => {
  assert.deepEqual(toggleChoice([1], 2, false), [2])
  assert.deepEqual(toggleChoice([], 2, false), [2])
  assert.deepEqual(toggleChoice([1], 2, true), [1, 2])
  assert.deepEqual(toggleChoice([1, 2], 1, true), [2])
  assert.deepEqual(toggleChoice(undefined, 3, true), [3])
})

test('vote button: vote, change, already voted, closed', () => {
  const open = { status: 'open', my_option_ids: [] }
  assert.deepEqual(voteAction(open, [], true), { label: 'Vote', enabled: false })
  assert.deepEqual(voteAction(open, [5], true), { label: 'Vote', enabled: true })
  const voted = { status: 'open', my_option_ids: [5] }
  assert.deepEqual(voteAction(voted, [5], true), { label: 'Voted', enabled: false })
  assert.deepEqual(voteAction(voted, [6], true), { label: 'Change vote', enabled: true })
  assert.deepEqual(voteAction({ status: 'open', my_option_ids: [5, 6] }, [6, 5], true),
    { label: 'Voted', enabled: false }, 'same set in another order')
  assert.deepEqual(voteAction({ status: 'closed', my_option_ids: [5] }, [5], true), { label: 'Voted', enabled: false })
  assert.deepEqual(voteAction({ status: 'closed', my_option_ids: [] }, [], true), { label: 'Closed', enabled: false })
  assert.equal(voteAction(open, [5], false).enabled, false, 'interaction paused')
})

test('results only when the lecturer shows them', () => {
  const hidden = { total_voters: null, options: [{ id: 1, text: 'A', votes: null }], my_option_ids: [1] }
  assert.equal(pollResultsVisible(hidden), false)
  assert.deepEqual(pollBars(hidden), [])
  const shown = { total_voters: 4, my_option_ids: [2], options: [{ id: 1, text: 'A', votes: 1 }, { id: 2, text: 'B', votes: 3 }] }
  assert.equal(pollResultsVisible(shown), true)
  assert.deepEqual(pollBars(shown), [
    { id: 1, text: 'A', votes: 1, pct: 25, mine: false },
    { id: 2, text: 'B', votes: 3, pct: 75, mine: true },
  ])
  assert.deepEqual(pollBars({ total_voters: 0, my_option_ids: [], options: [{ id: 1, text: 'A', votes: 0 }] })[0].pct, 0)
})

test('open polls come first, then newest', () => {
  const polls = [{ id: 1, status: 'closed' }, { id: 3, status: 'closed' }, { id: 2, status: 'open' }]
  assert.deepEqual(sortPolls(polls).map(p => p.id), [2, 3, 1])
  assert.deepEqual(sortPolls(null), [])
})

// ─── quick questions ─────────────────────────────────────────────────────────

test('quick answers respect the lecturer limit', () => {
  assert.deepEqual(validateQuickAnswer('  hash  ', 10), { text: 'hash' })
  assert.ok(validateQuickAnswer('  ', 10).error)
  assert.match(validateQuickAnswer('x'.repeat(11), 10).error, /10 characters/)
  assert.equal(charsLeft('abc', 10), 7)
  assert.equal(charsLeft('', 140), 140)
})

// ─── cooldowns ───────────────────────────────────────────────────────────────

test('cooldown from next_allowed_at or a 429 Retry-After', () => {
  const now = Date.parse('2026-11-23T02:00:00Z')
  assert.equal(nextAllowedAt({ ack: { next_allowed_at: '2026-11-23T10:00:05' }, now }), now + 5000, 'naive MYT')
  assert.equal(nextAllowedAt({ ack: { next_allowed_at: '2026-11-23T02:02:00Z' }, now }), now + 120000)
  assert.equal(nextAllowedAt({ error: { status: 429, retryAfter: '90' }, now }), now + 90000)
  assert.equal(nextAllowedAt({ error: { status: 409, retryAfter: '90' }, now }), null)
  assert.equal(nextAllowedAt({ error: { status: 429 }, now }), null)
  assert.equal(nextAllowedAt({}), null)
  assert.equal(secondsLeft(now + 4200, now), 5)
  assert.equal(secondsLeft(now - 1, now), 0)
  assert.equal(secondsLeft(null, now), 0)
  assert.equal(cooldownLabel(0), '')
  assert.equal(cooldownLabel(5), 'Again in 5s')
  assert.equal(cooldownLabel(95), 'Again in 1:35')
})

// ─── past questions ──────────────────────────────────────────────────────────

test('past questions: meta, answered badge, paging without duplicates', () => {
  assert.equal(myQuestionMeta({ course_code: 'WIA0000', class_date: '2026-11-23', anonymous: true }),
    'WIA0000 · 23 Nov · Anonymous')
  assert.equal(myQuestionMeta({ course_code: 'WIA0000', class_date: null, anonymous: false }), 'WIA0000')
  assert.deepEqual(myQuestionBadge({ answered: true }), { label: 'Answered', variant: 'green' })
  assert.equal(myQuestionBadge({ answered: false }).label, 'Not answered yet')
  assert.deepEqual(mergeQuestionPages([{ id: 3 }, { id: 2 }], [{ id: 2 }, { id: 1 }]).map(q => q.id), [3, 2, 1])
  assert.deepEqual(mergeQuestionPages(null, [{ id: 1 }]).map(q => q.id), [1])
})

// ─── live client ─────────────────────────────────────────────────────────────

function fakeSockets() {
  const made = []
  class FakeWS {
    constructor(url) { this.url = url; this.closedByClient = false; made.push(this) }
    close() { this.closedByClient = true }
    send(type, extra = {}) { this.onmessage?.({ data: JSON.stringify({ type, ...extra }) }) }
  }
  return { made, FakeWS }
}

function client(over = {}) {
  const { made, FakeWS } = fakeSockets()
  const timers = []
  const delays = []
  const cancelled = []
  const got = []
  let token = 'tok 1'
  let refreshes = 0
  const live = connectInteractionLive({
    baseUrl: 'http://api.test:8000', sessionId: 42, getToken: () => token,
    refreshToken: async () => { refreshes += 1; token = 'tok2'; return over.refreshOk ?? true },
    onMessage: (m) => got.push(m),
    WebSocketImpl: FakeWS, schedule: (fn, ms) => { timers.push(fn); delays.push(ms); return timers.length },
    cancel: (id) => { cancelled.push(id) },
    checkStatus: over.checkStatus, onReopen: over.onReopen,
  })
  return { made, timers, delays, cancelled, got, live, refreshes: () => refreshes }
}

test('connects to the class socket with the token and passes messages on', () => {
  const c = client()
  assert.equal(c.made[0].url, 'ws://api.test:8000/interaction/42/ws?token=tok%201')
  c.made[0].send('connected', { status: 'open', class_status: 'open' })
  c.made[0].send('changed', { topic: 'questions' })
  c.made[0].onmessage({ data: 'not json' })
  assert.deepEqual(c.got.map(m => m.type), ['connected', 'changed'])
})

test('reconnects after a drop, not after the class ended or close()', async () => {
  const c = client()
  await c.made[0].onclose({ code: 1006 })
  assert.equal(c.timers.length, 1)
  c.timers[0]()
  assert.equal(c.made.length, 2)
  c.made[1].send('closed', { reason: 'class_ended' })
  await c.made[1].onclose({ code: 1000 })
  assert.equal(c.timers.length, 1, 'no reconnect once the class ended')

  const d = client()
  d.made[0].send('connected', { status: 'closed', class_status: 'closed' })
  await d.made[0].onclose({ code: 1000 })
  assert.equal(d.timers.length, 0)

  const e = client()
  e.live.close()
  assert.equal(e.made[0].closedByClient, true)
  await e.made[0].onclose({ code: 1000 })
  assert.equal(e.timers.length, 0)
})

test('a pause keeps reconnecting; a 1008 refreshes the token once', async () => {
  const c = client()
  c.made[0].send('closed', { reason: 'lecturer' })
  await c.made[0].onclose({ code: 1006 })
  assert.equal(c.timers.length, 1)

  const r = client()
  await r.made[0].onclose({ code: 1008 })
  assert.equal(r.refreshes(), 1)
  r.timers[0]()
  assert.match(r.made[1].url, /token=tok2$/)
  await r.made[1].onclose({ code: 1008 })
  assert.equal(r.refreshes(), 1)
  assert.equal(r.timers.length, 1)

  const f = client({ refreshOk: false })
  await f.made[0].onclose({ code: 1008 })
  assert.equal(f.timers.length, 0)
})

// ─── S38e: reconnect after a reopen ─────────────────────────────────────────

test('classRunning reads the class status of GET /interaction/{id}', () => {
  assert.equal(classRunning({ status: 'closed', class_status: 'open' }), true)
  assert.equal(classRunning({ status: 'closed', class_status: 'closed' }), false)
  assert.equal(classRunning({ class_status: 'needs_confirmation' }), false)
  assert.equal(classRunning(null), false)
})

test('after the class ends it re-checks the status slowly and reconnects when the class is open again', async () => {
  const answers = [{ class_status: 'closed' }, new Error('offline'), { status: 'open', class_status: 'open' }]
  let reads = 0
  const reopened = []
  const c = client({
    checkStatus: async () => { const a = answers[reads++]; if (a instanceof Error) throw a; return a },
    onReopen: (s) => reopened.push(s),
  })
  c.made[0].send('connected', { status: 'open', class_status: 'open' })
  c.made[0].send('closed', { reason: 'class_ended' })
  await c.made[0].onclose({ code: 1000 })
  // one slow re-check is scheduled (not a socket retry), and only once even if close fires twice
  await c.made[0].onclose({ code: 1000 })
  assert.equal(c.timers.length, 1)
  assert.equal(c.delays[0], 5000)
  assert.equal(c.made.length, 1)

  await c.timers[0]()           // still closed: check again later, no socket
  assert.equal(c.made.length, 1)
  assert.equal(c.timers.length, 2)
  await c.timers[1]()           // a failed read keeps watching
  assert.equal(c.made.length, 1)
  assert.equal(c.timers.length, 3)
  await c.timers[2]()           // reopened (S38a, same session id): the socket comes back
  assert.equal(reads, 3)
  assert.equal(c.made.length, 2)
  assert.equal(c.made[1].url, 'ws://api.test:8000/interaction/42/ws?token=tok%201')
  assert.equal(reopened.length, 1)
  assert.equal(reopened[0].class_status, 'open')

  // live again: a drop is a normal fast retry, and a second end starts a new watch
  c.made[1].send('connected', { status: 'open', class_status: 'open' })
  await c.made[1].onclose({ code: 1006 })
  assert.equal(c.delays.at(-1), 3000)
  c.timers.at(-1)()
  assert.equal(c.made.length, 3)
  c.made[2].send('closed', { reason: 'class_ended' })
  await c.made[2].onclose({ code: 1000 })
  assert.equal(c.delays.at(-1), 5000)
})

test('a class not running at connect is watched too; close() stops the watch', async () => {
  let reads = 0
  const c = client({ checkStatus: async () => { reads += 1; return { class_status: 'closed' } } })
  c.made[0].send('connected', { status: 'closed', class_status: 'scheduled' })
  await c.made[0].onclose({ code: 1000 })
  assert.equal(c.timers.length, 1)
  c.live.close()
  assert.deepEqual(c.cancelled, [1])
  await c.timers[0]()           // a timer that fires anyway does nothing after close()
  assert.equal(reads, 0)
  assert.equal(c.made.length, 1)

  // close() while a status read is on its way: no socket after it answers
  let answer
  const d = client({ checkStatus: () => new Promise((r) => { answer = r }) })
  d.made[0].send('closed', { reason: 'class_ended' })
  await d.made[0].onclose({ code: 1000 })
  const pending = d.timers[0]()
  d.live.close()
  answer({ class_status: 'open' })
  await pending
  assert.equal(d.made.length, 1)
  assert.equal(d.timers.length, 1)
})
