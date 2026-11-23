// Student live class (Module 5, plan-shino.md S38). No React here, so it runs under `npm test`.
// Data comes from the S31–S36 REST endpoints (shaped for students by the server); WS
// /interaction/{id}/ws only says which topic changed (S35), and the screen re-reads that topic.
import { parseTime } from './notifications.js'

// The topics a student's socket can be told about (reactions/confusion go to the lecturer only)
export const TOPICS = ['questions', 'polls', 'quick_questions']

// What to re-read for one websocket message. Nothing is replayed, so `connected` re-reads all.
export function topicsFor(message) {
  if (!message || typeof message.type !== 'string') return []
  if (message.type === 'connected') return ['session', ...TOPICS]
  if (message.type === 'changed') return TOPICS.includes(message.topic) ? [message.topic] : []
  if (message.type === 'opened' || message.type === 'closed') return ['session']
  return []
}

// The class's interaction for the header badge and whether the student may post
export function interactionState(s) {
  if (!s) return { label: 'Loading', variant: 'gray', open: false, ended: false, text: '' }
  if (s.status === 'open') {
    return { label: 'Live', variant: 'green', open: true, ended: false, text: 'Ask, vote, answer and react.' }
  }
  if (s.class_status === 'open') {
    return {
      label: 'Paused', variant: 'orange', open: false, ended: false,
      text: 'The lecturer paused interaction. You can read, but not post for now.',
    }
  }
  if (s.closed_reason === 'not_started' || s.class_status === 'scheduled') {
    return { label: 'Not started', variant: 'gray', open: false, ended: false, text: 'Interaction opens when the class starts.' }
  }
  return { label: 'Class ended', variant: 'gray', open: false, ended: true, text: 'The class has ended.' }
}

// The classes of today the student can join now (FR-501: only while the class session is open)
export function liveClasses(todayClasses) {
  return (todayClasses ?? []).filter(c => c.session_status === 'open' && c.session_id != null)
}

// ─── Questions (FR-503–FR-506) ───────────────────────────────────────────────

export const QUESTION_MAX_CHARS = 500

export function validateQuestion(text) {
  const t = (text ?? '').trim()
  if (!t) return { error: 'Write your question first.' }
  if (t.length > QUESTION_MAX_CHARS) return { error: `A question can be at most ${QUESTION_MAX_CHARS} characters.` }
  return { text: t }
}

// Who asked, as the student sees it: their own question says so; anonymous ones never carry a name
export function askerLabel(q) {
  if (q?.mine) return q.anonymous ? 'You (anonymous)' : 'You'
  return q?.anonymous || !q?.author_name ? 'Anonymous' : q.author_name
}

export function questionBadges(q) {
  const out = []
  if (q?.pinned) out.push({ label: 'Pinned', variant: 'blue' })
  if (q?.answered) out.push({ label: 'Answered', variant: 'green' })
  return out
}

// A student upvotes once, never their own question, only while the interaction is open
export function canUpvote(q, open) {
  return !!open && !!q && !q.mine && !q.upvoted_by_me
}

// ─── Polls (FR-507–FR-509) ───────────────────────────────────────────────────

// The new choice after tapping an option: single choice replaces, multiple choice toggles
export function toggleChoice(selected, optionId, multiple) {
  const cur = selected ?? []
  if (!multiple) return [optionId]
  return cur.includes(optionId) ? cur.filter(id => id !== optionId) : [...cur, optionId]
}

const sameSet = (a, b) => a.length === b.length && a.every(x => b.includes(x))

// What the vote button says and whether it can be pressed
export function voteAction(poll, selected, open) {
  const mine = poll?.my_option_ids ?? []
  const sel = selected ?? []
  const pollOpen = !!open && poll?.status === 'open'
  if (!pollOpen) return { label: mine.length ? 'Voted' : 'Closed', enabled: false }
  if (!sel.length) return { label: mine.length ? 'Change vote' : 'Vote', enabled: false }
  if (mine.length && sameSet(sel, mine)) return { label: 'Voted', enabled: false }
  return { label: mine.length ? 'Change vote' : 'Vote', enabled: true }
}

// Results only when the lecturer shows them (the server sends null counts otherwise)
export function pollResultsVisible(poll) {
  return !!poll && poll.total_voters != null && (poll.options ?? []).every(o => o.votes != null)
}

export function pollBars(poll) {
  if (!pollResultsVisible(poll)) return []
  const total = poll.total_voters
  return poll.options.map(o => ({
    id: o.id, text: o.text, votes: o.votes, pct: total ? Math.round((o.votes / total) * 100) : 0,
    mine: (poll.my_option_ids ?? []).includes(o.id),
  }))
}

// Students never see drafts (the server leaves them out); open polls first, then newest
export function sortPolls(polls) {
  return [...(polls ?? [])].sort((a, b) => {
    if ((a.status === 'open') !== (b.status === 'open')) return a.status === 'open' ? -1 : 1
    return (b.id ?? 0) - (a.id ?? 0)
  })
}

// ─── Quick questions (FR-510, FR-511) ────────────────────────────────────────

export function validateQuickAnswer(text, maxChars) {
  const t = (text ?? '').trim()
  if (!t) return { error: 'Write your answer first.' }
  if (maxChars && t.length > maxChars) return { error: `Your answer can be at most ${maxChars} characters.` }
  return { text: t }
}

export function charsLeft(text, maxChars) {
  return (maxChars ?? 0) - (text ?? '').length
}

// ─── Reactions and "I don't understand" (FR-512, FR-514) ────────────────────

export const REACTIONS = [
  { kind: 'thumbs_up', label: 'Thumbs up', icon: 'thumbs-up-outline' },
  { kind: 'clear', label: 'Clear', icon: 'checkmark-circle-outline' },
  { kind: 'too_fast', label: 'Too fast', icon: 'speedometer-outline' },
  { kind: 'too_slow', label: 'Too slow', icon: 'hourglass-outline' },
]

export const CONFUSION_TOPIC_MAX_CHARS = 60

// When the next press is allowed (ms since epoch): from a 201's `next_allowed_at`, or a 429's
// Retry-After seconds. null when nothing says.
export function nextAllowedAt({ ack, error, now = Date.now() } = {}) {
  if (ack?.next_allowed_at) {
    const t = parseTime(ack.next_allowed_at)
    if (t) return t.getTime()
  }
  const secs = Number(error?.retryAfter)
  if (error?.status === 429 && Number.isFinite(secs) && secs >= 0) return now + secs * 1000
  return null
}

// Whole seconds left of a cooldown (0 = allowed now)
export function secondsLeft(until, now = Date.now()) {
  if (!until) return 0
  return Math.max(0, Math.ceil((until - now) / 1000))
}

export function cooldownLabel(secs) {
  if (secs <= 0) return ''
  if (secs < 60) return `Again in ${secs}s`
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `Again in ${m}:${String(s).padStart(2, '0')}`
}

// ─── Past questions (FR-520) ─────────────────────────────────────────────────

// "WIA0000 · 23 Nov" for one of the student's own past questions
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export function myQuestionMeta(q) {
  let date = ''
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(q?.class_date ?? '')
  if (m) date = `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]}`
  return [q?.course_code, date, q?.anonymous ? 'Anonymous' : null].filter(Boolean).join(' · ')
}

export function myQuestionBadge(q) {
  return q?.answered ? { label: 'Answered', variant: 'green' } : { label: 'Not answered yet', variant: 'gray' }
}

// Appends the next page, skipping anything already listed
export function mergeQuestionPages(current, page) {
  const seen = new Set((current ?? []).map(q => q.id))
  return [...(current ?? []), ...(page ?? []).filter(q => !seen.has(q.id))]
}

// ─── Live client ─────────────────────────────────────────────────────────────
// Reconnects while the class runs. A 1008 close (bad or expired token) refreshes the token once
// before reconnecting. After `closed` with reason `class_ended` (or a `connected` saying the class
// isn't running) the server closes the socket and nothing reconnects (the class is over).

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
