// Pure helpers for the live session, class controls and Moodle sync screens (FR-301–FR-320).
// No React here, so they run under `npm test`.

export const STATUSES = ['present', 'late', 'excused', 'absent']

const STATUS_LABELS = {
  present: 'Present', late: 'Late', excused: 'Excused', absent: 'Absent', not_recorded: 'Not yet',
}
const STATUS_BADGES = {
  present: 'green', late: 'orange', excused: 'blue', absent: 'red', not_recorded: 'gray',
}

export const statusLabel = (s) => STATUS_LABELS[s] ?? s
export const statusBadge = (s) => STATUS_BADGES[s] ?? 'gray'

export const OVERRIDE_REASON_MAX = 500

// The reason is optional (FR-305); blank counts as none, the server rejects more than 500 chars
export function overrideReasonError(reason) {
  return (reason ?? '').trim().length > OVERRIDE_REASON_MAX
    ? `Keep the reason under ${OVERRIDE_REASON_MAX} characters.`
    : null
}

export function cleanReason(reason) {
  const r = (reason ?? '').trim()
  return r || null
}

// A student with no record yet shows "Not yet" while the class runs; a closed class counts it absent
export function rosterStatus(apiStatus, sessionOpen) {
  if (apiStatus !== 'not_recorded') return apiStatus
  return sessionOpen ? 'not_recorded' : 'absent'
}

// Roster split for the session screen: late students are listed on their own (T38)
export function groupRoster(students) {
  const late = students.filter(s => s.status === 'late')
  const rest = students.filter(s => s.status !== 'late')
  const sections = []
  if (late.length) sections.push({ key: 'late', title: `Late (${late.length})`, data: late })
  if (rest.length) sections.push({ key: 'rest', title: late.length ? `Everyone else (${rest.length})` : null, data: rest })
  return sections
}

export function countStatuses(students) {
  const counts = { present: 0, late: 0, excused: 0, absent: 0, not_recorded: 0 }
  for (const s of students) if (s.status in counts) counts[s.status] += 1
  return counts
}

// The five counts of a session from its API counts (Home pane), the same numbers the live roster
// gives (countStatuses): the server's `absent` includes students not recorded yet (T38b).
export function sessionCounts(session) {
  const notYet = session?.not_recorded ?? 0
  return {
    present: session?.present ?? 0,
    late: session?.late ?? 0,
    excused: session?.excused ?? 0,
    absent: Math.max(0, (session?.absent ?? 0) - notYet),
    not_recorded: notYet,
  }
}

// The websocket stays on a session while it runs, and after it ends until SPeCTRUM has it
// (the sync's outcome arrives as a `moodle_sync` event, T38b)
export const followsLive = (session) =>
  Boolean(session && (session.open || ['pending', 'failed'].includes(session.moodle_sync_status)))

// ─── Times ────────────────────────────────────────────────────────────────────
// The server sends Malaysia time without a zone ("2026-11-16T08:00:00"), so read the
// digits as they are instead of letting the phone's own time zone shift them.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function parseLocal(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(iso ?? '')
  if (!m) return null
  return { y: +m[1], mo: +m[2], d: +m[3], h: m[4] != null ? +m[4] : null, mi: m[5] != null ? +m[5] : null }
}

export function hhmm(iso) {
  const p = parseLocal(iso)
  if (!p || p.h == null) return ''
  return `${String(p.h).padStart(2, '0')}:${String(p.mi).padStart(2, '0')}`
}

// "08:00–10:00", with "(next day)" when the class ends after midnight
export function timeRange(startIso, endIso) {
  const a = parseLocal(startIso)
  const b = parseLocal(endIso)
  if (!a || !b) return ''
  const nextDay = Date.UTC(b.y, b.mo - 1, b.d) > Date.UTC(a.y, a.mo - 1, a.d)
  return `${hhmm(startIso)}–${hhmm(endIso)}${nextDay ? ' (next day)' : ''}`
}

export function dayMonth(iso) {
  const p = parseLocal(iso)
  return p ? { day: p.d, month: MONTHS[p.mo - 1] } : { day: '', month: '' }
}

export function minutesBetween(fromIso, toIso) {
  const a = parseLocal(fromIso)
  const b = parseLocal(toIso)
  if (!a || !b || a.h == null || b.h == null) return null
  const ms = Date.UTC(b.y, b.mo - 1, b.d, b.h, b.mi) - Date.UTC(a.y, a.mo - 1, a.d, a.h, a.mi)
  return Math.round(ms / 60000)
}

export const isHHMM = (v) => /^([01]\d|2[0-3]):[0-5]\d$/.test(v ?? '')

// Checks a start/end pair (the weekly schedule); null when fine
export function timeRangeError(start, end) {
  if (!isHHMM(start) || !isHHMM(end)) return 'Use 24-hour times like 08:00.'
  if (end <= start) return 'The end time must be after the start time.'
  return null
}

export const WEEK_DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

// The weekly slot: all of day/start/end, or none to clear it (matches WeeklyScheduleRequest)
export function weeklyScheduleError({ day, start, end }) {
  if (!day || !start || !end) return 'Pick a day, a start and an end time.'
  if (!WEEK_DAYS.includes(day)) return 'Pick a day.'
  return timeRangeError(start, end)
}

// ─── Session state ────────────────────────────────────────────────────────────

export function sessionStateLabel(status) {
  return {
    open: 'Open now',
    closed: 'Closed',
    needs_confirmation: 'Confirm if held',
    cancelled: 'Cancelled',
    scheduled: 'Scheduled',
  }[status] ?? status
}

export function sessionStateBadge(status) {
  return { open: 'green', needs_confirmation: 'yellow', cancelled: 'gray', closed: 'gray' }[status] ?? 'gray'
}

// ─── Moodle sync (FR-312, FR-320) ─────────────────────────────────────────────

export function syncInfo(session) {
  const st = session?.moodle_sync_status
  if (!st) return null
  switch (st) {
    case 'synced':
      return {
        label: 'Synced to SPeCTRUM', badge: 'green', canRetry: false,
        detail: session.moodle_synced_at ? `Last sent ${hhmm(session.moodle_synced_at)}` : null,
      }
    case 'pending':
      return { label: 'Waiting to sync', badge: 'yellow', canRetry: true, detail: 'Sends within a minute.' }
    case 'failed':
      return {
        label: 'Sync failed', badge: 'red', canRetry: true,
        detail: [
          session.moodle_sync_error,
          session.moodle_sync_next_at ? `Tries again at ${hhmm(session.moodle_sync_next_at)}` : null,
        ].filter(Boolean).join(' · ') || null,
      }
    case 'conflict':
      return {
        label: 'Changed in SPeCTRUM', badge: 'orange', canRetry: true,
        detail: 'Some marks were changed in SPeCTRUM. Choose which value to keep.',
      }
    default:
      return { label: st, badge: 'gray', canRetry: true, detail: null }
  }
}

const MOODLE_VALUE_LABELS = { none: 'No mark', other: 'Another status' }

export const moodleValueLabel = (v) => MOODLE_VALUE_LABELS[v] ?? statusLabel(v)

// Only a status SmartClass has can be taken from Moodle (the server answers 409 otherwise)
export const canTakeMoodle = (conflict) => STATUSES.includes(conflict.moodle_status)
