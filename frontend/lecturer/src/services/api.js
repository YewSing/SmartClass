import { apiCall, getToken, setToken, clearToken, setRefreshToken, clearRefreshToken } from './client'
import {
  QUIZZES, BREAKDOWN_ROWS, SENSORS,
  ANALYTICS_PAR_BARS, ANALYTICS_PAR_LABELS,
} from '../data/mockData'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function initials(name = '') {
  return name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase()
}

function durationStr(openedAt, closedAt) {
  const ms = new Date(closedAt) - new Date(openedAt)
  const mins = Math.round(ms / 60000)
  return `${mins} min`
}

function sessionAdapter(s) {
  const d = new Date(s.opened_at)
  return {
    id: s.id,
    class_id: s.class_id,
    class_code: s.class_code,
    class_name: s.class_name,
    day: d.getDate(),
    month: d.toLocaleString('en-MY', { month: 'short', timeZone: 'Asia/Kuala_Lumpur' }),
    time: d.toLocaleTimeString('en-MY', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kuala_Lumpur' }),
    duration: s.closed_at ? durationStr(s.opened_at, s.closed_at) : null,
    open: s.status === 'open',
    present: s.present ?? 0,
    absent: s.absent ?? 0,
    unid: s.unid ?? 0,
  }
}

const AVATAR_COLORS = [
  { bg: 'var(--blue-lt)',   color: 'var(--blue-dk)' },
  { bg: 'var(--green-lt)',  color: 'var(--green-dk)' },
  { bg: 'var(--orange-lt)', color: 'var(--orange-dk)' },
]

function studentAdapter(s, idx) {
  const c = AVATAR_COLORS[idx % AVATAR_COLORS.length]
  return {
    id: s.matric_no,
    recordId: s.record_id,
    studentId: s.student_id,
    name: s.name,
    initials: initials(s.name),
    avatarBg: c.bg,
    avatarColor: c.color,
    status: s.status === 'not_recorded' ? 'absent' : s.status,
    overridden: s.overridden ?? false,
  }
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const login = async (email, password) => {
  const data = await apiCall('POST', '/auth/login', { email, password })
  setToken(data.access_token)
  setRefreshToken(data.refresh_token)
  return {
    user: {
      name: data.user.name,
      email: data.user.email,
      role: data.user.role,
      initials: initials(data.user.name),
    },
  }
}

export const getLecturer = async () => {
  const u = await apiCall('GET', '/auth/me')
  return {
    name: u.name,
    email: u.email,
    initials: initials(u.name),
    staffId: u.lecturer?.staff_id ?? '',
    faculty: u.lecturer?.dept ?? '',
    role: 'Lecturer',
  }
}

export const changePassword = async (current, next) => {
  return apiCall('PUT', '/auth/me/password', { current_password: current, new_password: next })
}

export const logout = async () => { clearToken(); clearRefreshToken() }

// ─── Classes ──────────────────────────────────────────────────────────────────

export const getClasses = async () => {
  const list = await apiCall('GET', '/classes')
  return list.map(c => ({ id: c.id, code: c.course_code, name: c.course_name }))
}

export const getLecturerAllClasses = async () => {
  const list = await apiCall('GET', '/classes?full=1')
  return list.map(c => ({
    id: c.id,
    code: c.course_code,
    name: c.course_name,
    type: c.type,
    label: c.label ?? null,
    day_of_week: c.day_of_week,
    start_time: c.start_time,
    end_time: c.end_time,
    enrolled_count: c.enrolled_count ?? 0,
    room: c.room ?? null,
  }))
}

export const getCurrentClass = async () => {
  const list = await getClasses()
  return list[0] ?? null
}

// ─── Sessions ─────────────────────────────────────────────────────────────────

export const getSessions = async () => {
  const list = await apiCall('GET', '/lecturer/sessions')
  return list.map(sessionAdapter)
}

export const openSession = async (classId) => {
  const s = await apiCall('POST', '/lecturer/sessions', { occurrence_id: classId })
  return sessionAdapter(s)
}

export const closeSession = async (sessionId) => {
  const s = await apiCall('PUT', `/lecturer/sessions/${sessionId}/close`)
  return sessionAdapter(s)
}

// ─── Attendance ───────────────────────────────────────────────────────────────

export const getStudents = async (sessionId) => {
  const list = await apiCall('GET', `/lecturer/sessions/${sessionId}/attendance`)
  return list.map(studentAdapter)
}

export const overrideAttendance = async (recordId, newStatus) => {
  return apiCall('PUT', `/attendance/${recordId}/override`, { status: newStatus })
}

export const exportReport = async (sessionId, format = 'csv') => {
  const token = getToken()
  const res = await fetch(`http://localhost:8000/lecturer/sessions/${sessionId}/export?format=${format}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`Export failed: HTTP ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `attendance_${sessionId}.${format}`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export const getAnalytics = async (occurrenceId) => {
  return apiCall('GET', `/lecturer/analytics?occurrence_id=${occurrenceId}`)
}

// ─── Mocked (Module 3/4 — quiz; Module 5/6 — sensors) ────────────────────────

const delay = (ms) => new Promise(res => setTimeout(res, ms))

export const getQuizzes        = async (_id)  => { await delay(300); return QUIZZES }
export const createQuiz        = async (data) => { await delay(400); return { id: `q${Date.now()}`, ...data, status: 'draft' } }
export const pushQuiz          = async (_id)  => { await delay(300); return { success: true } }
export const closeQuiz         = async (_id)  => { await delay(300); return { success: true } }
export const getBreakdown      = async (_id)  => { await delay(300); return BREAKDOWN_ROWS }
export const getSensors        = async ()     => { await delay(200); return SENSORS }
export const setActuatorOverride = async ()   => { await delay(300); return { success: true } }
export const resetConfusion    = async ()     => { await delay(300); return { success: true } }
export const getAnalyticsPar   = async ()     => ({ bars: ANALYTICS_PAR_BARS, labels: ANALYTICS_PAR_LABELS })
