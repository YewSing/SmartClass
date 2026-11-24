// Lecturer live interaction (Module 5, plan-shino.md S37). No React here, so it runs under `npm test`.
// Data comes from the S31–S36 REST endpoints; WS /interaction/{id}/ws only says which topic changed
// (S35), and the screen re-reads that topic.
import { hhmm, timeRange, dayMonth } from './attendance.js'

export const TOPICS = ['questions', 'polls', 'quick_questions', 'reactions', 'confusion']

// What to re-read for one websocket message. Nothing is replayed, so `connected` re-reads all.
export function topicsFor(message) {
  if (!message || typeof message.type !== 'string') return []
  if (message.type === 'connected') return ['session', ...TOPICS]
  if (message.type === 'changed') return TOPICS.includes(message.topic) ? [message.topic] : []
  if (message.type === 'opened' || message.type === 'closed') return ['session']
  return []
}

// The interaction's state for the header badge and what the lecturer may do
export function interactionState(s) {
  if (!s) return { label: 'Loading', variant: 'gray', open: false, ended: false, canReopen: false }
  const classRunning = s.class_status === 'open'
  if (s.status === 'open') return { label: 'Open', variant: 'green', open: true, ended: false, canReopen: false }
  if (classRunning) return { label: 'Paused', variant: 'orange', open: false, ended: false, canReopen: true }
  if (s.closed_reason === 'not_started' || s.class_status === 'scheduled') {
    return { label: 'Not started', variant: 'gray', open: false, ended: false, canReopen: false }
  }
  return { label: 'Class ended', variant: 'gray', open: false, ended: true, canReopen: false }
}

// Soft status badges of one question, in display order
export function questionBadges(q) {
  const out = []
  if (q.pinned) out.push({ label: 'Pinned', variant: 'blue' })
  if (q.answered) out.push({ label: 'Answered', variant: 'green' })
  if (q.hidden) out.push({ label: 'Hidden', variant: 'gray' })
  return out
}

// The asker as the lecturer may see it: anonymous questions never carry a name (FR-504)
export function askerLabel(q) {
  return q.anonymous || !q.author_name ? 'Anonymous' : q.author_name
}

// Bars of a poll: share of voters per option (multiple choice can pass 100% in total)
export function pollBars(poll) {
  const total = poll?.total_voters ?? 0
  return (poll?.options ?? []).map(o => {
    const votes = o.votes ?? 0
    return { id: o.id, text: o.text, votes, pct: total ? Math.round((votes / total) * 100) : 0 }
  })
}

export const POLL_MIN_OPTIONS = 2
export const POLL_MAX_OPTIONS = 6

// A poll the server will take (S32: question ≤ 300, 2–6 distinct options ≤ 120), or an error
export function validatePoll({ question, options }) {
  const q = (question ?? '').trim()
  const opts = (options ?? []).map(o => (o ?? '').trim()).filter(Boolean)
  if (!q) return { error: 'Write the poll question.' }
  if (q.length > 300) return { error: 'The question can be at most 300 characters.' }
  if (opts.length < POLL_MIN_OPTIONS) return { error: 'Give at least 2 options.' }
  if (opts.length > POLL_MAX_OPTIONS) return { error: 'A poll can have at most 6 options.' }
  if (opts.some(o => o.length > 120)) return { error: 'Each option can be at most 120 characters.' }
  if (new Set(opts.map(o => o.toLowerCase())).size !== opts.length) return { error: 'Options must be different.' }
  return { question: q, options: opts }
}

// A quick question (S33: prompt ≤ 300, answers 1–500 characters)
export function validateQuick({ prompt, maxChars }) {
  const p = (prompt ?? '').trim()
  if (!p) return { error: 'Write the question.' }
  if (p.length > 300) return { error: 'The question can be at most 300 characters.' }
  const n = Number(maxChars)
  if (!Number.isInteger(n) || n < 1 || n > 500) return { error: 'Answer length must be 1–500 characters.' }
  return { prompt: p, max_chars: n }
}

export const REACTIONS = [
  { kind: 'thumbs_up', label: 'Thumbs up', emoji: '👍' },
  { kind: 'clear', label: 'Clear', emoji: '✅' },
  { kind: 'too_fast', label: 'Too fast', emoji: '🚀' },
  { kind: 'too_slow', label: 'Too slow', emoji: '🐢' },
]

export function reactionRows(counts) {
  return REACTIONS.map(r => ({ ...r, count: counts?.[r.kind] ?? 0 }))
}

// The reaction sent most (null before the first one); the first listed wins a tie
export function topReaction(counts) {
  const best = reactionRows(counts).reduce((a, b) => (b.count > a.count ? b : a))
  return best.count > 0 ? best : null
}

const sum = (counts) => Object.values(counts ?? {}).reduce((n, x) => n + (x ?? 0), 0)

// The numbers on Home's interaction card, from the session summary (S36; works during class too).
// Reactions and confusion are what is on now while the class runs, after it how many students (S38g).
export function homeCounts(summary) {
  const questions = summary?.questions ?? []
  const live = summary?.class_status === 'open'
  return {
    waiting: openQuestions(questions).length,
    questions: summary?.question_counts?.asked ?? questions.length,
    polls: summary?.polls?.length ?? 0,
    answers: (summary?.quick_questions ?? []).reduce((n, q) => n + (q.answer_count ?? 0), 0),
    reactions: live ? sum(summary.reactions_active) : summary?.reactors ?? 0,
    confused: (live ? summary.confusion?.active : summary?.confusion?.people) ?? 0,
  }
}

// Confusion timeline as bars (heights 0–1 of the busiest minute), oldest first
export function timelineBars(timeline) {
  const list = timeline ?? []
  const max = Math.max(0, ...list.map(b => b.count ?? 0))
  return list.map(b => ({
    start: b.start,
    label: hhmm(b.start),
    count: b.count ?? 0,
    height: max ? (b.count ?? 0) / max : 0,
  }))
}

// The after-class reaction timeline as rows: "10:05" and the reactions that were on then
export function reactionTimelineRows(timeline) {
  return (timeline ?? []).map(b => ({
    start: b.start, label: hhmm(b.start), items: reactionRows(b.counts).filter(r => r.count > 0),
  })).filter(r => r.items.length)
}

// "2 of 20 students"
export function confusionNowLabel(c) {
  return c ? `${c.active ?? 0} of ${c.class_size ?? 0} students` : ''
}

// "3 of 20 students in the last 2 min"
export function confusionRecentLabel(c) {
  if (!c) return ''
  const mins = Math.max(1, Math.round((c.window_seconds ?? 120) / 60))
  return `${c.recent_students ?? 0} of ${c.class_size ?? 0} students in the last ${mins} min`
}

// ─── One-page layout (S38b) ──────────────────────────────────────────────────

const newestFirst = (a, b) =>
  String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')) || (b.id ?? 0) - (a.id ?? 0)

// Questions still waiting for the lecturer: not answered, not hidden
export function openQuestions(questions) {
  return (questions ?? []).filter(q => !q.answered && !q.hidden)
}

// The newest `n` open questions, newest first (the server lists by pinned/upvotes)
export function newestUnanswered(questions, n = 3) {
  return [...openQuestions(questions)].sort(newestFirst).slice(0, n)
}

// The newest item still open, else the newest of all (polls: drafts count, so a saved draft shows)
function latest(list) {
  const sorted = [...(list ?? [])].sort(newestFirst)
  return sorted.find(x => x.status === 'open') ?? sorted[0] ?? null
}
export const latestPoll = (polls) => latest(polls)
export const latestQuick = (quick) => latest(quick)

// The newest answer of a quick question (the server lists answers oldest first)
export function newestAnswer(qq) {
  const list = qq?.answers ?? []
  return list.length ? list[list.length - 1] : null
}

// "Many confused now" while a spike runs, else how many spikes this class had (null when none)
export function spikeLabel(c) {
  if (!c) return null
  if (c.spike_active) return { text: 'Many confused now', variant: 'red' }
  if (c.spikes > 0) return { text: c.spikes === 1 ? '1 spike earlier' : `${c.spikes} spikes earlier`, variant: 'orange' }
  return null
}

// The CSV file name the server also gives (S36): interaction_<course>_<yyyymmdd>_<id>.csv
export function summaryCsvName(summary) {
  const code = String(summary?.course_code ?? 'class').replace(/[^A-Za-z0-9]+/g, '')
  const date = String(summary?.class_date ?? '').replace(/-/g, '') || 'undated'
  return `interaction_${code}_${date}_${summary?.attendance_session_id ?? ''}.csv`
}

// ─── Interaction tab (S38d) ──────────────────────────────────────────────────

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`

// One row of the Interaction tab from GET /lecturer/interaction/sessions: date block, time, live flag
// and the non-zero counts as chips (questions first)
export function historyRow(item) {
  const c = item?.counts ?? {}
  const { day, month } = dayMonth(item?.class_date ?? item?.starts_at)
  const live = item?.class_status === 'open'
  const chips = [
    ['questions', c.questions, 'question', 'questions'],
    ['polls', c.polls, 'poll', 'polls'],
    ['quick', c.quick_questions, 'quick question', 'quick questions'],
    ['reactions', c.reactions, 'reacted', 'reacted'],
    ['confusion', c.confusion, 'confused', 'confused'],
  ].filter(([, n]) => n > 0).map(([key, n, one, many]) => ({ key, label: plural(n, one, many) }))
  const type = item?.class_label || (item?.class_type ? item.class_type[0] + item.class_type.slice(1).toLowerCase() : '')
  const start = hhmm(item?.starts_at)
  const time = live ? (start ? `from ${start}` : '') : (timeRange(item?.starts_at, item?.ends_at) || start)
  return {
    id: item?.attendance_session_id,
    title: [item?.course_code, item?.course_name].filter(Boolean).join(' — ') || 'Class',
    sub: [type, time].filter(Boolean).join(' · '),
    day, month, live, chips,
  }
}

// Pages of the Interaction tab: append the next page, dropping a session already shown (a new class
// may have pushed rows down between pages)
export function mergeHistory(current, page) {
  const seen = new Set((current ?? []).map(s => s.attendance_session_id))
  return [...(current ?? []), ...(page ?? []).filter(s => !seen.has(s.attendance_session_id))]
}

export const SUMMARY_PILLS = ['questions', 'polls', 'quick', 'reactions', 'confusion']

// The summary's category pills with their counts
export function summaryPills(summary) {
  return [
    { key: 'questions', label: 'Questions', count: summary?.question_counts?.asked ?? 0 },
    { key: 'polls', label: 'Polls', count: summary?.polls?.length ?? 0 },
    { key: 'quick', label: 'Quick questions', count: summary?.quick_questions?.length ?? 0 },
    { key: 'reactions', label: 'Reactions', count: summary?.reactors ?? 0 },
    { key: 'confusion', label: 'Confusion', count: summary?.confusion?.people ?? 0 },
  ]
}

// ─── Live client ─────────────────────────────────────────────────────────────
// Reconnects while the class runs. A 1008 close (bad or expired token) refreshes the token once
// before reconnecting. After `closed` with reason `class_ended` (or a `connected` saying the class
// isn't running) the server closes the socket. With `checkStatus` (S38e) the client then re-reads
// the class status every `watchMs` and reconnects once it is open again: the lecturer may reopen the
// class in its slot with the same session id (S38a), or a not-started class may start. Without
// `checkStatus` nothing reconnects after the end.

// True when the status read says the class runs again (GET /interaction/{id} answer)
export function classRunning(status) {
  return status?.class_status === 'open'
}

export function connectInteractionLive({
  baseUrl, sessionId, getToken, refreshToken, onMessage, checkStatus, onReopen,
  WebSocketImpl = globalThis.WebSocket, schedule = setTimeout, cancel = clearTimeout,
  retryMs = 3000, watchMs = 5000,
}) {
  let ws = null
  let closed = false
  let ended = false
  let timer = null
  let refreshedOnce = false
  let watching = false

  // After the class ended: a slow re-check of its status until it runs again
  async function watch() {
    timer = null
    if (closed) return
    let status = null
    try { status = await checkStatus() } catch { status = null }
    if (closed) return
    if (classRunning(status)) {
      watching = false
      ended = false
      refreshedOnce = false
      onReopen?.(status)
      open()
    } else {
      timer = schedule(watch, watchMs)
    }
  }

  function open() {
    const token = getToken()
    if (!token || closed || ended) return
    const url = `${baseUrl.replace(/^http/, 'ws')}/interaction/${encodeURIComponent(sessionId)}/ws?token=${encodeURIComponent(token)}`
    ws = new WebSocketImpl(url)

    ws.onmessage = (e) => {
      let data
      try { data = JSON.parse(e.data) } catch { return }
      if (!data || typeof data.type !== 'string') return
      if (data.type === 'connected') {
        refreshedOnce = false
        if (data.class_status && data.class_status !== 'open') ended = true
      }
      if (data.type === 'closed' && data.reason === 'class_ended') ended = true
      onMessage(data)
    }

    ws.onclose = async (e) => {
      if (closed) return
      if (ended) {
        if (checkStatus && !watching) {
          watching = true
          timer = schedule(watch, watchMs)
        }
        return
      }
      if (e?.code === 1008) {
        if (refreshedOnce) return
        refreshedOnce = true
        const ok = await refreshToken()
        if (!ok || closed) return
      }
      timer = schedule(open, retryMs)
    }

    ws.onerror = () => {}
  }

  open()

  return {
    close() {
      closed = true
      cancel(timer)
      ws?.close()
    },
  }
}
