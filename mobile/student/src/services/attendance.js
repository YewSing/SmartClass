// Pure helpers for the student attendance screens (FR-308, FR-309).
// No React or React Native here, so they run under `npm test`.

export const STATUSES = ['present', 'late', 'excused', 'absent']

const STATUS_INFO = {
  present:      { label: 'Present',          badge: 'green' },
  late:         { label: 'Late',             badge: 'yellow' },
  excused:      { label: 'Excused',          badge: 'blue' },
  absent:       { label: 'Absent',           badge: 'red' },
  not_recorded: { label: 'Not yet recorded', badge: 'gray' },
}

export function statusInfo(status) {
  return STATUS_INFO[status] ?? { label: status ?? '—', badge: 'gray' }
}

// ─── Times ────────────────────────────────────────────────────────────────────
// The server sends Malaysia time without a zone ("2026-11-16T08:00:00"), so read the
// digits as they are instead of letting the phone's own time zone shift them.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

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

export function dayMonth(iso) {
  const p = parseLocal(iso)
  return p ? { day: String(p.d).padStart(2, '0'), month: MONTHS[p.mo - 1] } : { day: '', month: '' }
}

export function dateLabel(isoDate) {
  const p = parseLocal(isoDate)
  if (!p) return ''
  const wd = DAYS[new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay()]
  return `${wd} ${p.d} ${MONTHS[p.mo - 1]}`
}

// ─── Course views ─────────────────────────────────────────────────────────────

export function rateText(rate) {
  if (rate == null) return '—'
  return `${Math.round(rate * 10) / 10}%`
}

export function rateNote(course) {
  if (course.counted_sessions > 0) {
    return `${course.present + course.late} of ${course.counted_sessions} classes attended`
  }
  if (course.closed_sessions === 0) return 'No finished classes yet'
  return 'All finished classes were excused'
}

export function classLabel(s) {
  return s.class_label || (s.class_type === 'TUTORIAL' ? 'Tutorial' : 'Lecture')
}

export function toSessionView(s, course, meta = {}) {
  const info = statusInfo(s.status)
  const dateIso = s.date ?? s.starts_at
  return {
    id: String(s.session_id),
    courseId: course.course_id,
    status: s.status,
    label: info.label,
    badge: info.badge,
    ...dayMonth(dateIso),
    title: `${course.course_code} · ${classLabel(s)}`,
    sub: [dateLabel(dateIso), hhmm(s.starts_at)].filter(Boolean).join(' · '),
    dateLong: dateLabel(dateIso),
    time: hhmm(s.starts_at) || null,
    checkinTime: hhmm(s.detected_at) || null,
    isLive: s.session_status === 'open',
    overridden: !!s.overridden,
    venue: meta.venue || '—',
    lecturer: meta.lecturer || '—',
    courseName: course.course_name,
    courseCode: course.course_code,
    classLabel: classLabel(s),
  }
}

export function toCourseView(c, occLookup = {}) {
  return {
    id: c.course_id,
    code: c.course_code,
    name: c.course_name,
    rate: c.rate,
    rateText: rateText(c.rate),
    note: rateNote(c),
    counts: { present: c.present, late: c.late, excused: c.excused, absent: c.absent },
    sessions: c.sessions.map(s => toSessionView(s, c, occLookup[s.occurrence_id])),
  }
}

export function findSession(courses, courseId, sessionId) {
  for (const course of courses ?? []) {
    if (String(course.id) !== String(courseId)) continue
    const session = course.sessions.find(s => String(s.id) === String(sessionId))
    if (session) return { course, session }
  }
  return null
}

// ─── "I'm here" flags (FR-318, FR-319, FR-406) ───────────────────────────────

// The flag button: the class is open now, the student has no record and hasn't flagged it
export function canFlag(session, flag) {
  return !!session && session.isLive && session.status === 'not_recorded' && !flag
}

const FLAG_VIEWS = {
  pending: {
    title: 'Waiting for your lecturer',
    sub: "Your lecturer will check you're in class and confirm it. Until then this class shows as not recorded, or Absent once it ends.",
    badge: 'yellow',
    icon: 'hourglass-outline',
  },
  confirmed: {
    title: 'Confirmed',
    badge: 'green',
    icon: 'checkmark-circle-outline',
  },
  rejected: {
    title: 'Not accepted',
    badge: 'red',
    icon: 'close-circle-outline',
  },
}

// What the session detail and the flag status screen show for a flag
export function flagView(flag) {
  if (!flag) return null
  const state = FLAG_VIEWS[flag.status] ? flag.status : 'pending'
  const base = FLAG_VIEWS[state]
  let sub = base.sub
  if (state === 'confirmed') {
    sub = `Your lecturer confirmed you were in class. You're marked ${statusInfo(flag.record_status ?? 'present').label}.`
  } else if (state === 'rejected') {
    sub = flag.reject_reason
      ? `Your lecturer did not accept it: ${flag.reject_reason}`
      : 'Your lecturer did not accept it.'
  }
  return {
    state,
    title: base.title,
    sub,
    badge: base.badge,
    icon: base.icon,
    classText: `${flag.class_code} — ${flag.class_name}`,
    dateText: dateLabel(flag.class_date) || '—',
    flaggedText: hhmm(flag.flagged_at) || '—',
    resolvedText: flag.resolved_at ? hhmm(flag.resolved_at) : null,
  }
}

// The global banner text for an attendance_recorded event (FR-406)
export function recordedBannerText(event) {
  const base = event?.message || `Attendance recorded for ${event?.course_code ?? ''}`
  return `${base} · ${statusInfo(event?.status).label}`
}
