// Lecturer live interaction (Module 5, plan-shino.md S37). No React here, so it runs under `npm test`.
// Data comes from the S31–S36 REST endpoints; WS /interaction/{id}/ws only says which topic changed
// (S35), and the screen re-reads that topic.
import { hhmm } from './attendance.js'

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
  { kind: 'thumbs_up', label: 'Thumbs up', icon: 'thumbs-up-outline' },
  { kind: 'clear', label: 'Clear', icon: 'checkmark-circle-outline' },
  { kind: 'too_fast', label: 'Too fast', icon: 'speedometer-outline' },
  { kind: 'too_slow', label: 'Too slow', icon: 'hourglass-outline' },
]

export function reactionRows(counts) {
  return REACTIONS.map(r => ({ ...r, count: counts?.[r.kind] ?? 0 }))
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

// "3 of 20 students in the last 2 min"
export function confusionRecentLabel(c) {
  if (!c) return ''
  const mins = Math.max(1, Math.round((c.window_seconds ?? 120) / 60))
  return `${c.recent_students ?? 0} of ${c.class_size ?? 0} students in the last ${mins} min`
}

// The CSV file name the server also gives (S36): interaction_<course>_<yyyymmdd>_<id>.csv
export function summaryCsvName(summary) {
  const code = String(summary?.course_code ?? 'class').replace(/[^A-Za-z0-9]+/g, '')
  const date = String(summary?.class_date ?? '').replace(/-/g, '') || 'undated'
  return `interaction_${code}_${date}_${summary?.attendance_session_id ?? ''}.csv`
}

// ─── Live client ─────────────────────────────────────────────────────────────
// Reconnects while the class runs. A 1008 close (bad or expired token) refreshes the token once
// before reconnecting. After `closed` with reason `class_ended` the server closes the socket and
// nothing reconnects (the class is over).

export function connectInteractionLive({
  baseUrl, sessionId, getToken, refreshToken, onMessage,
  WebSocketImpl = globalThis.WebSocket, schedule = setTimeout, cancel = clearTimeout,
  retryMs = 3000,
}) {
  let ws = null
  let closed = false
  let ended = false
  let timer = null
  let refreshedOnce = false

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
      if (closed || ended) return
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
