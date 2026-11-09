import { apiCall, apiCallRaw, getToken, setToken, clearToken, setRefreshToken, clearRefreshToken, BASE } from './client'
import { saveCsv } from './saveCsv'
import {
  QUIZZES, BREAKDOWN_ROWS,
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
  { bg: '#EFF6FF', color: '#1D4ED8' },
  { bg: '#F0FDF4', color: '#15803D' },
  { bg: '#FFF7ED', color: '#C2410C' },
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

// Turns a failed sign-in into a message the user can act on
function signInError(e, wrongCredentials) {
  if (e.status === 401) return new Error(wrongCredentials)
  if (e.status === 503) return new Error(e.message || 'SPeCTRUM is not reachable right now. Please try again later.')
  if (!e.status) return new Error("Can't reach the SmartClass server. Check your connection and try again.")
  return e
}

// Lecturers sign in with their SPeCTRUM (Moodle) account (FR-101). With `local`, the
// browser-only administrator sign-in uses a SmartClass email + password instead.
export const login = async (identifier, password, { local = false } = {}) => {
  let data
  try {
    data = local
      ? await apiCall('POST', '/auth/login', { email: identifier.trim(), password })
      : await apiCall('POST', '/auth/moodle-login', { username: identifier.trim(), password })
  } catch (e) {
    throw signInError(e, local ? 'Wrong email or password.' : 'Wrong SPeCTRUM username or password.')
  }
  const allowed = local ? ['lecturer', 'admin'] : ['lecturer']
  if (!allowed.includes(data.user.role)) {
    throw new Error('This app is for lecturers. Students use the SmartClass Student app.')
  }
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
    isAdmin: u.role === 'admin',
  }
}

export const changePassword = async (current, next) => {
  return apiCall('PUT', '/auth/me/password', { current_password: current, new_password: next })
}

export const logout = async () => { clearToken(); clearRefreshToken() }

// ─── Classes ──────────────────────────────────────────────────────────────────

// Moodle full names often start with the code ("WIA2005 Algorithm Design"), and screens show both
function courseName(code, name) {
  const rest = name.startsWith(code) ? name.slice(code.length).replace(/^[\s:–—-]+/, '') : name
  return rest || name
}

export const getClasses = async () => {
  const list = await apiCall('GET', '/classes')
  return list.map(c => ({
    id: c.id,
    code: c.course_code,
    name: courseName(c.course_code, c.course_name),
    day_of_week: c.day_of_week ?? null,
    start_time: c.start_time ?? null,
    end_time: c.end_time ?? null,
    room: c.room ?? null,
  }))
}

export const getLecturerAllClasses = async () => {
  const list = await apiCall('GET', '/classes?full=1')
  return list.map(c => ({
    id: c.id,
    code: c.course_code,
    name: courseName(c.course_code, c.course_name),
    type: c.type,
    label: c.label ?? null,
    day_of_week: c.day_of_week,
    start_time: c.start_time,
    end_time: c.end_time,
    enrolled_count: c.enrolled_count ?? 0,
    room: c.room ?? null,
  }))
}

export const getClassStudents = async (classId) => {
  const list = await apiCall('GET', `/classes/${classId}/students`)
  return list.map(s => ({
    id: s.id,
    name: s.name,
    matric: s.matric_no,
    initials: initials(s.name),
    faceEnrolled: s.face_enrolled,
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

export const overrideAttendance = async (recordId, newStatus, sessionId, studentId) => {
  if (recordId) {
    return apiCall('PUT', `/attendance/${recordId}/override`, { status: newStatus })
  }
  return apiCall('PUT', `/lecturer/sessions/${sessionId}/attendance/override`, { student_id: studentId, status: newStatus })
}

export const exportSessionCsv = async (sessionId, filename) => {
  const res = await apiCallRaw('GET', `/lecturer/sessions/${sessionId}/export?format=csv`)
  const csvText = await res.text()
  return saveCsv(csvText, filename)
}

export const exportOccurrenceCsv = async (occId, filename, dateParams = {}) => {
  const qs = Object.keys(dateParams).length
    ? '?' + Object.entries(dateParams).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&')
    : ''
  const res = await apiCallRaw('GET', `/lecturer/occurrences/${occId}/attendance/export${qs}`)
  const csvText = await res.text()
  return saveCsv(csvText, filename)
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export const getAnalytics = async (occurrenceId, dateParams = {}) => {
  const qs = Object.keys(dateParams).length
    ? '&' + Object.entries(dateParams).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&')
    : ''
  return apiCall('GET', `/lecturer/analytics?occurrence_id=${occurrenceId}${qs}`)
}

// ─── Face verification queue (FR-113) ────────────────────────────────────────

// Submissions waiting for review, oldest first; only students of the lecturer's courses
export const getPendingFaceSubmissions = async () => apiCall('GET', '/face-verification/pending')

export const approveFaceSubmission = async (id) => apiCall('POST', `/face-verification/${id}/approve`)

export const rejectFaceSubmission = async (id, reason) =>
  apiCall('POST', `/face-verification/${id}/reject`, { reason: reason.trim() })

// A review photo needs the token. An <img> can't send it, and Android's Image drops `headers`
// (new architecture), so the photo is fetched here: a blob URL on web (the caller revokes it),
// a data URI on phones.
export const fetchFaceImageUri = async (path, { web = false } = {}) => {
  const blob = await (await apiCallRaw('GET', path)).blob()
  if (web) return URL.createObjectURL(blob)
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error("Couldn't read the photo"))
    reader.readAsDataURL(blob)
  })
}

// ─── Mocked (Module 3/4 — quiz) ────────────────────────

const delay = (ms) => new Promise(res => setTimeout(res, ms))

export const getQuizzes        = async (_id)  => { await delay(300); return QUIZZES }
export const createQuiz        = async (data) => { await delay(400); return { id: `q${Date.now()}`, ...data, status: 'draft' } }
export const pushQuiz          = async (_id)  => { await delay(300); return { success: true } }
export const closeQuiz         = async (_id)  => { await delay(300); return { success: true } }
export const getBreakdown      = async (_id)  => { await delay(300); return BREAKDOWN_ROWS }
export const resetConfusion    = async ()     => { await delay(300); return { success: true } }
export const getAnalyticsPar   = async ()     => ({ bars: ANALYTICS_PAR_BARS, labels: ANALYTICS_PAR_LABELS })
