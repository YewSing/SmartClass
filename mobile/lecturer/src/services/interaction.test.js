import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  TOPICS, topicsFor, interactionState, questionBadges, askerLabel, pollBars, validatePoll, validateQuick,
  reactionRows, timelineBars, confusionRecentLabel, summaryCsvName, connectInteractionLive,
  openQuestions, newestUnanswered, latestPoll, latestQuick, newestAnswer, spikeLabel,
} from './interaction.js'

// ─── what to re-read ─────────────────────────────────────────────────────────

test('connected re-reads the session and every topic; changed only its topic', () => {
  assert.deepEqual(topicsFor({ type: 'connected', status: 'open' }), ['session', ...TOPICS])
  for (const t of TOPICS) assert.deepEqual(topicsFor({ type: 'changed', topic: t }), [t])
  assert.deepEqual(topicsFor({ type: 'opened' }), ['session'])
  assert.deepEqual(topicsFor({ type: 'closed', reason: 'lecturer' }), ['session'])
  for (const m of [{ type: 'changed', topic: 'secrets' }, { type: 'pong' }, {}, null, 'x']) {
    assert.deepEqual(topicsFor(m), [], JSON.stringify(m))
  }
})

// ─── state ───────────────────────────────────────────────────────────────────

test('open, paused by the lecturer, not started and ended', () => {
  const open = interactionState({ status: 'open', class_status: 'open' })
  assert.equal(open.label, 'Open'); assert.equal(open.open, true); assert.equal(open.ended, false)

  const paused = interactionState({ status: 'closed', closed_reason: 'lecturer', class_status: 'open' })
  assert.equal(paused.label, 'Paused'); assert.equal(paused.open, false); assert.equal(paused.canReopen, true)

  const notYet = interactionState({ status: 'closed', closed_reason: 'not_started', class_status: 'scheduled' })
  assert.equal(notYet.label, 'Not started'); assert.equal(notYet.canReopen, false); assert.equal(notYet.ended, false)

  for (const cs of ['closed', 'needs_confirmation', 'cancelled']) {
    const ended = interactionState({ status: 'closed', closed_reason: 'class_ended', class_status: cs })
    assert.equal(ended.label, 'Class ended', cs); assert.equal(ended.ended, true); assert.equal(ended.canReopen, false)
  }
  // An early close that the class end then overtook is ended, not paused
  assert.equal(interactionState({ status: 'closed', closed_reason: 'lecturer', class_status: 'closed' }).ended, true)
  assert.equal(interactionState(null).open, false)
})

// ─── questions ───────────────────────────────────────────────────────────────

test('question badges in order and anonymous askers never named', () => {
  assert.deepEqual(questionBadges({ pinned: true, answered: true, hidden: true }).map(b => b.label),
    ['Pinned', 'Answered', 'Hidden'])
  assert.deepEqual(questionBadges({ pinned: false, answered: false, hidden: false }), [])
  assert.equal(askerLabel({ anonymous: false, author_name: 'Ali' }), 'Ali')
  assert.equal(askerLabel({ anonymous: true, author_name: null }), 'Anonymous')
  // even if a name ever came with an anonymous question, it isn't shown
  assert.equal(askerLabel({ anonymous: true, author_name: 'Ali' }), 'Anonymous')
})

// ─── polls ───────────────────────────────────────────────────────────────────

test('poll bars are shares of voters, zero when nobody voted or counts are hidden', () => {
  const poll = { total_voters: 4, options: [{ id: 1, text: 'A', votes: 3 }, { id: 2, text: 'B', votes: 2 }] }
  assert.deepEqual(pollBars(poll), [
    { id: 1, text: 'A', votes: 3, pct: 75 }, { id: 2, text: 'B', votes: 2, pct: 50 },
  ])
  assert.deepEqual(pollBars({ total_voters: 0, options: [{ id: 1, text: 'A', votes: 0 }] })[0].pct, 0)
  assert.deepEqual(pollBars({ total_voters: null, options: [{ id: 1, text: 'A', votes: null }] })[0],
    { id: 1, text: 'A', votes: 0, pct: 0 })
  assert.deepEqual(pollBars(null), [])
})

test('a poll needs a question and 2–6 distinct options of at most 120 characters', () => {
  assert.deepEqual(validatePoll({ question: '  Best? ', options: [' A ', '', 'B'] }), { question: 'Best?', options: ['A', 'B'] })
  assert.match(validatePoll({ question: ' ', options: ['A', 'B'] }).error, /question/)
  assert.match(validatePoll({ question: 'Q', options: ['A', ' '] }).error, /at least 2/)
  assert.match(validatePoll({ question: 'Q', options: ['1', '2', '3', '4', '5', '6', '7'] }).error, /at most 6/)
  assert.match(validatePoll({ question: 'Q', options: ['A', 'a'] }).error, /different/)
  assert.match(validatePoll({ question: 'Q', options: ['A', 'x'.repeat(121)] }).error, /120/)
  assert.match(validatePoll({ question: 'x'.repeat(301), options: ['A', 'B'] }).error, /300/)
})

test('a quick question needs a prompt and an answer length of 1–500', () => {
  assert.deepEqual(validateQuick({ prompt: ' Why? ', maxChars: '140' }), { prompt: 'Why?', max_chars: 140 })
  assert.match(validateQuick({ prompt: '', maxChars: '140' }).error, /Write/)
  for (const n of ['0', '501', '', 'abc', '1.5']) assert.match(validateQuick({ prompt: 'Q', maxChars: n }).error, /1–500/, n)
  assert.match(validateQuick({ prompt: 'x'.repeat(301), maxChars: 10 }).error, /300/)
})

// ─── reactions and confusion ─────────────────────────────────────────────────

test('every reaction kind is listed, missing ones as 0', () => {
  const rows = reactionRows({ thumbs_up: 3, too_fast: 1 })
  assert.deepEqual(rows.map(r => [r.kind, r.count]), [['thumbs_up', 3], ['clear', 0], ['too_fast', 1], ['too_slow', 0]])
  assert.equal(reactionRows(null).every(r => r.count === 0), true)
})

test('timeline bars scale to the busiest minute and show the time', () => {
  const bars = timelineBars([{ start: '2026-11-23T09:01:00', count: 2 }, { start: '2026-11-23T09:02:00', count: 4 }])
  assert.deepEqual(bars.map(b => [b.label, b.count, b.height]), [['09:01', 2, 0.5], ['09:02', 4, 1]])
  assert.deepEqual(timelineBars([]), [])
  assert.deepEqual(timelineBars(null), [])
  assert.equal(timelineBars([{ start: '2026-11-23T09:01:00', count: 0 }])[0].height, 0)
})

test('recent confusion label', () => {
  assert.equal(confusionRecentLabel({ recent_students: 3, class_size: 20, window_seconds: 120 }),
    '3 of 20 students in the last 2 min')
  assert.equal(confusionRecentLabel(null), '')
})

test('csv name matches the server pattern', () => {
  assert.equal(summaryCsvName({ course_code: 'WIA0000', class_date: '2026-11-23', attendance_session_id: 7 }),
    'interaction_WIA0000_20261123_7.csv')
  assert.equal(summaryCsvName({ course_code: 'A/B', class_date: null, attendance_session_id: 1 }),
    'interaction_AB_undated_1.csv')
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
  const got = []
  let token = 'tok 1'
  let refreshes = 0
  const live = connectInteractionLive({
    baseUrl: 'http://api.test:8000', sessionId: 42, getToken: () => token,
    refreshToken: async () => { refreshes += 1; token = 'tok2'; return over.refreshOk ?? true },
    onMessage: (m) => got.push(m),
    WebSocketImpl: FakeWS, schedule: (fn) => { timers.push(fn); return timers.length }, cancel: () => {},
  })
  return { made, timers, got, live, refreshes: () => refreshes }
}

test('connects to the session socket with the token and passes messages on', () => {
  const c = client()
  assert.equal(c.made[0].url, 'ws://api.test:8000/interaction/42/ws?token=tok%201')
  c.made[0].send('connected', { status: 'open', class_status: 'open' })
  c.made[0].send('changed', { topic: 'questions' })
  c.made[0].onmessage({ data: 'not json' })
  c.made[0].onmessage({ data: '{"no":"type"}' })
  assert.deepEqual(c.got.map(m => m.type), ['connected', 'changed'])
})

test('reconnects after a dropped socket, but not after the class ended or close()', async () => {
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
  assert.equal(d.timers.length, 0, 'a class that already ended is not retried')

  const e = client()
  e.live.close()
  assert.equal(e.made[0].closedByClient, true)
  await e.made[0].onclose({ code: 1000 })
  assert.equal(e.timers.length, 0)
})

test('a lecturer pause keeps the socket; a 1008 refreshes the token once', async () => {
  const c = client()
  c.made[0].send('closed', { reason: 'lecturer' })
  await c.made[0].onclose({ code: 1006 })
  assert.equal(c.timers.length, 1, 'paused is not ended: it reconnects')

  const r = client()
  await r.made[0].onclose({ code: 1008 })
  assert.equal(r.refreshes(), 1)
  r.timers[0]()
  assert.match(r.made[1].url, /token=tok2$/)
  await r.made[1].onclose({ code: 1008 })
  assert.equal(r.refreshes(), 1, 'the refreshed token was refused too: stop')
  assert.equal(r.timers.length, 1)

  const f = client({ refreshOk: false })
  await f.made[0].onclose({ code: 1008 })
  assert.equal(f.timers.length, 0)
})

// ─── one-page layout (S38b) ──────────────────────────────────────────────────

test('newest open questions skip answered and hidden ones, newest first, at most n', () => {
  const qs = [
    { id: 1, created_at: '2026-11-23T01:00:00Z', answered: false, hidden: false, pinned: true },
    { id: 2, created_at: '2026-11-23T01:05:00Z', answered: true, hidden: false },
    { id: 3, created_at: '2026-11-23T01:06:00Z', answered: false, hidden: true },
    { id: 4, created_at: '2026-11-23T01:07:00Z', answered: false, hidden: false },
    { id: 5, created_at: '2026-11-23T01:07:00Z', answered: false, hidden: false },
    { id: 6, created_at: '2026-11-23T01:02:00Z', answered: false, hidden: false },
  ]
  assert.deepEqual(newestUnanswered(qs, 3).map(q => q.id), [5, 4, 6])
  assert.deepEqual(newestUnanswered(qs, 1).map(q => q.id), [5])
  assert.equal(openQuestions(qs).length, 4)
  assert.deepEqual(newestUnanswered([], 3), [])
  assert.deepEqual(newestUnanswered(undefined), [])
  // The input list is not reordered
  assert.deepEqual(qs.map(q => q.id), [1, 2, 3, 4, 5, 6])
})

test('latest poll / quick question: the newest open one, else the newest', () => {
  const polls = [
    { id: 1, status: 'open', created_at: '2026-11-23T01:00:00Z' },
    { id: 2, status: 'closed', created_at: '2026-11-23T01:10:00Z' },
    { id: 3, status: 'draft', created_at: '2026-11-23T01:20:00Z' },
  ]
  assert.equal(latestPoll(polls).id, 1)
  assert.equal(latestPoll(polls.filter(p => p.status !== 'open')).id, 3)
  assert.equal(latestPoll([]), null)
  assert.equal(latestPoll(undefined), null)
  const quick = [
    { id: 7, status: 'closed', created_at: '2026-11-23T01:00:00Z' },
    { id: 8, status: 'closed', created_at: '2026-11-23T01:30:00Z' },
  ]
  assert.equal(latestQuick(quick).id, 8)
  assert.equal(latestQuick([...quick, { id: 9, status: 'open', created_at: '2026-11-23T00:10:00Z' }]).id, 9)
})

test('newest answer of a quick question is the last one listed', () => {
  assert.equal(newestAnswer({ answers: [{ id: 1, text: 'a' }, { id: 2, text: 'b' }] }).text, 'b')
  assert.equal(newestAnswer({ answers: [] }), null)
  assert.equal(newestAnswer(null), null)
})

test('spike label: running now, earlier spikes, or none', () => {
  assert.deepEqual(spikeLabel({ spike_active: true, spikes: 2 }), { text: 'Many confused now', variant: 'red' })
  assert.equal(spikeLabel({ spike_active: false, spikes: 1 }).text, '1 spike earlier')
  assert.equal(spikeLabel({ spike_active: false, spikes: 3 }).text, '3 spikes earlier')
  assert.equal(spikeLabel({ spike_active: false, spikes: 0 }), null)
  assert.equal(spikeLabel(null), null)
})
