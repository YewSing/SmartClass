// Dashboard helpers (FR-201, FR-202, FR-208; plan-shino.md S20). No React here, so it runs under
// `npm test`. The same file is in the lecturer app.
import { parseTime, timeLabel } from './notifications.js'

// ─── Load state ──────────────────────────────────────────────────────────────
// { status: 'loading' | 'ready' | 'error', data, error }. A failed re-load keeps the last good data
// on screen (status stays 'ready', error set), so a flaky network doesn't blank the dashboard.

export const initialDashboard = { status: 'loading', data: null, error: null }

export function dashboardReducer(state, action) {
  switch (action.type) {
    case 'loading':
      return state.data ? state : { status: 'loading', data: null, error: null }
    case 'loaded':
      return { status: 'ready', data: action.data, error: null }
    case 'failed':
      return state.data
        ? { ...state, error: action.error }
        : { status: 'error', data: null, error: action.error }
    case 'read': {
      // A priority notification was opened (marked read): it leaves the top (FR-208)
      if (!state.data) return state
      const list = state.data.priority_notifications ?? []
      return {
        ...state,
        data: {
          ...state.data,
          priority_notifications: list.filter(n => n.id !== action.id),
          unread_count: action.unread ?? state.data.unread_count,
        },
      }
    }
    case 'reset':
      return initialDashboard
    default:
      return state
  }
}

// ─── Classes and attendance ──────────────────────────────────────────────────

const ATTENDANCE = {
  present:      { variant: 'green',  label: 'Present' },
  late:         { variant: 'orange', label: 'Late' },
  excused:      { variant: 'blue',   label: 'Excused' },
  absent:       { variant: 'red',    label: 'Absent' },
  not_recorded: { variant: 'yellow', label: 'Not recorded yet' },
}

// The student's status in today's class; before the session opens there is nothing to show yet
export function attendanceBadge(cls) {
  if (cls?.attendance_status && ATTENDANCE[cls.attendance_status]) return ATTENDANCE[cls.attendance_status]
  if (cls?.session_status === 'needs_confirmation') return { variant: 'yellow', label: 'Being checked' }
  if (cls?.session_status === 'closed') return { variant: 'gray', label: 'Ended' }
  return { variant: 'gray', label: 'Not started' }
}

const SESSION = {
  open:               { variant: 'green',  label: 'Live' },
  closed:             { variant: 'gray',   label: 'Ended' },
  needs_confirmation: { variant: 'yellow', label: 'Needs confirmation' },
}

// The class session's state, for the lecturer's list of today's classes
export function sessionBadge(cls) {
  return SESSION[cls?.session_status] ?? { variant: 'blue', label: 'Not started' }
}

export function classTypeLabel(cls) {
  if (!cls) return ''
  return cls.class_type === 'LECTURE' ? 'Lecture' : (cls.class_label || 'Tutorial')
}

// "09:00–11:00 · DK1" (either part may be missing)
export function classMeta(cls) {
  if (!cls) return ''
  const time = cls.start_time && cls.end_time ? `${cls.start_time}–${cls.end_time}` : cls.start_time ?? null
  return [time, cls.room || null].filter(Boolean).join(' · ')
}

// FR-308: below 80% is a warning (orange), no counted session yet shows a dash
export function rateLabel(rate) {
  return rate == null ? '—' : `${Number(rate).toFixed(rate % 1 === 0 ? 0 : 1)}%`
}
export function rateVariant(rate) {
  if (rate == null) return 'gray'
  return rate >= 80 ? 'green' : 'orange'
}

// The five numbers of AttendanceCounts from the S18 overview (closed sessions have no "not yet")
export function overviewCounts(o) {
  return {
    present: o?.present ?? 0,
    late: o?.late ?? 0,
    excused: o?.excused ?? 0,
    absent: o?.absent ?? 0,
    not_recorded: o?.not_recorded ?? 0,
  }
}

// ─── Moodle (FR-203) ─────────────────────────────────────────────────────────

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const mytDay = (d) => Math.floor((d.getTime() + 8 * 3600000) / 86400000)

function mytParts(d) {
  const m = new Date(d.getTime() + 8 * 3600000)
  return {
    day: m.getUTCDate(), month: MONTHS[m.getUTCMonth()],
    hhmm: `${String(m.getUTCHours()).padStart(2, '0')}:${String(m.getUTCMinutes()).padStart(2, '0')}`,
  }
}

// "Due today, 23:59" / "Due tomorrow, 09:00" / "Due 25 Nov, 09:00" (MYT, any phone time zone)
export function dueLabel(iso, now = new Date()) {
  const t = parseTime(iso)
  if (!t) return ''
  const p = mytParts(t)
  const days = mytDay(t) - mytDay(now)
  if (days === 0) return `Due today, ${p.hhmm}`
  if (days === 1) return `Due tomorrow, ${p.hhmm}`
  return `Due ${p.day} ${p.month}, ${p.hhmm}`
}

// When the snapshot was taken; null = never (the student hasn't signed in with SPeCTRUM yet)
export function refreshedLabel(iso, now = new Date()) {
  if (!iso) return 'Not synced yet. Sign in again to load SPeCTRUM items.'
  const label = timeLabel(iso, now)
  return label ? `Updated ${label === 'Just now' ? 'just now' : label}` : ''
}

// Only web links leave the app (the snapshot builds them from the Moodle URL; anything else is ignored)
export function moodleLink(item) {
  const link = item?.link
  return typeof link === 'string' && /^https?:\/\/[^\s]+$/i.test(link) ? link : null
}
