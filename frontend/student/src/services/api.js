import { apiCall, setToken, clearToken, setRefreshToken, clearRefreshToken } from './client'
import { PART_SUMMARY, PARTICIPATION_GROUPS, SESSION_PERFS } from '../data/mockData'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function initials(name = '') {
  return name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase()
}

function mapStatus(status) {
  if (status === 'present') return 'present'
  if (status === 'unidentified') return 'unid'
  return 'absent'
}

// Build the attendance item + detail structure the views expect
function sessionToAttItem(s) {
  const date = new Date(s.date)
  const variant = mapStatus(s.status)
  const day   = String(date.getDate()).padStart(2, '0')
  const month = date.toLocaleString('en-MY', { month: 'short', timeZone: 'Asia/Kuala_Lumpur' })
  const dateBg    = variant === 'present' ? 'var(--green-lt)'  : variant === 'absent' ? 'var(--red-lt)'    : 'var(--orange-lt)'
  const dateColor = variant === 'present' ? 'var(--green)'     : variant === 'absent' ? 'var(--red)'       : 'var(--orange)'

  const checkinTime = s.detected_at
    ? new Date(s.detected_at).toLocaleTimeString('en-MY', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kuala_Lumpur' })
    : null

  const dateLabel = date.toLocaleDateString('en-MY', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Kuala_Lumpur' })

  return {
    id: String(s.session_id),
    day, month, dateBg, dateColor,
    title: `${s.class_code} — Session`,
    sub: `${date.toLocaleDateString('en-MY', { weekday: 'short', timeZone: 'Asia/Kuala_Lumpur' })} · ${s.class_name}`,
    status: variant,
    isLive: false,
    variant,
    detail: {
      title: `${s.class_code} — ${s.class_name}`,
      meta: dateLabel,
      checkinTime,
      checkinNote: null,
      sessionTime: s.date,
      venue: '—',
      lecturer: '—',
      classPresent: null,
      classAbsent: null,
      classUnid: null,
      isLive: false,
    },
  }
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const login = async (email, password) => {
  const data = await apiCall('POST', '/auth/login', { email, password })
  setToken(data.access_token)
  setRefreshToken(data.refresh_token)
  return { user: data.user }
}

export const getStudent = async () => {
  const u = await apiCall('GET', '/auth/me')
  return {
    name: u.name,
    email: u.email,
    initials: initials(u.name),
    matricNo: u.student?.matric_no ?? '',
    programme: u.student?.programme ?? '',
    faculty: u.student?.faculty ?? '',
    yearSem: u.student?.year_sem ?? '',
  }
}

export const logout = async () => { clearToken(); clearRefreshToken() }

// ─── Classes ──────────────────────────────────────────────────────────────────

export const getEnrolledClasses = async () => {
  const list = await apiCall('GET', '/classes')
  const ACCENT_COLORS = ['#0E6FBF', '#7C3AED', '#E03A3A', '#12A564']
  return list.map((c, i) => ({
    id: c.id,
    code: c.code,
    name: c.name,
    venue: c.venue ?? '',
    lecturer: '—',
    accentColor: ACCENT_COLORS[i % ACCENT_COLORS.length],
    liveSession: false,
    attendedCount: 0,
    totalSessions: 0,
    status: 'ok',
    nextSchedule: null,
  }))
}

// ─── Attendance ───────────────────────────────────────────────────────────────

export const getAttendanceSummary = async () => {
  const s = await apiCall('GET', '/student/me/attendance/summary')
  return {
    present: s.present,
    absent: s.absent,
    late: 0,
    rate: s.rate,
  }
}

export const getAttendanceGroups = async () => {
  const groups = await apiCall('GET', '/student/me/attendance')
  return groups.map(g => ({
    id: g.class_code.toLowerCase().replace(/\W+/g, ''),
    label: `${g.class_code} · ${g.class_name}`,
    sessions: g.sessions.map(sessionToAttItem),
  }))
}

// ─── Mocked (Module 3/4 — participation/quiz) ─────────────────────────────────

const delay = (ms) => new Promise(res => setTimeout(res, ms))

export const getParticipationSummary = async () => { await delay(200); return PART_SUMMARY }
export const getParticipationGroups  = async () => { await delay(300); return PARTICIPATION_GROUPS }
export const getSessionPerf = async (perfKey) => { await delay(200); return SESSION_PERFS[perfKey] ?? null }
export const submitReport = async () => { await delay(400); return { refNo: `RPT-${Date.now()}`, status: 'pending' } }
export const sendPasswordReset = async () => { await delay(400); return { success: true } }
