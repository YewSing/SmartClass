import { apiCall, apiCallRaw, getToken, setToken, clearToken, setRefreshToken, clearRefreshToken, BASE } from './client'
import { saveCsv } from './saveCsv'
import { dayMonth, hhmm, minutesBetween, rosterStatus, cleanReason } from './attendance'
import {
  QUIZZES, BREAKDOWN_ROWS,
  ANALYTICS_PAR_BARS, ANALYTICS_PAR_LABELS,
} from '../data/mockData'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function initials(name = '') {
  return name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase()
}

// Times come as Malaysia time without a zone, so they are read as written (see attendance.js)
function sessionAdapter(s) {
  const shownAt = s.opened_at ?? s.starts_at   // a missed class never opened
  const { day, month } = dayMonth(shownAt)
  const mins = s.opened_at && s.closed_at ? minutesBetween(s.opened_at, s.closed_at) : null
  return {
    id: s.id,
    class_id: s.class_id,
    class_code: s.class_code,
    class_name: s.class_name,
    day,
    month,
    time: hhmm(shownAt),
    duration: mins != null ? `${mins} min` : null,
    open: s.status === 'open',
    status: s.status,
    class_date: s.class_date ?? null,
    starts_at: s.starts_at ?? null,
    ends_at: s.ends_at ?? null,
    present: s.present ?? 0,
    late: s.late ?? 0,
    excused: s.excused ?? 0,
    absent: s.absent ?? 0,
    not_recorded: s.not_recorded ?? 0,
    unid: s.unid ?? 0,
    moodle_sync_status: s.moodle_sync_status ?? null,
    moodle_synced_at: s.moodle_synced_at ?? null,
    moodle_sync_next_at: s.moodle_sync_next_at ?? null,
    moodle_sync_error: s.moodle_sync_error ?? null,
    moodle_conflicts: s.moodle_conflicts ?? [],
  }
}

const AVATAR_COLORS = [
  { bg: '#EFF6FF', color: '#1D4ED8' },
  { bg: '#F0FDF4', color: '#15803D' },
  { bg: '#FFF7ED', color: '#C2410C' },
]

function studentAdapter(s, idx, sessionOpen) {
  const c = AVATAR_COLORS[idx % AVATAR_COLORS.length]
  return {
    id: s.matric_no,
    recordId: s.record_id,
    studentId: s.student_id,
    name: s.name,
    initials: initials(s.name),
    avatarBg: c.bg,
    avatarColor: c.color,
    status: rosterStatus(s.status, sessionOpen),
    arrivedAt: s.detected_at ? hhmm(s.detected_at) : null,
    overridden: s.overridden ?? false,
  }
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

// Turns a failed sign-in into a message the user can act on
function signInError(e, wrongCredentials, local) {
  if (e.status === 401) return new Error(wrongCredentials)
  // The server's check of the email field; never show its raw 422 body
  if (e.status === 422 && local) return new Error('Enter your email address.')
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
    throw signInError(e, local ? 'Wrong email or password.' : 'Wrong SPeCTRUM username or password.', local)
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
    role: u.role === 'admin' ? 'Administrator' : 'Lecturer',
    roleKey: u.role,
    id: u.id,
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

// End the class early (FR-315)
export const closeSession = async (sessionId) => {
  const s = await apiCall('PUT', `/lecturer/sessions/${sessionId}/close`)
  return sessionAdapter(s)
}

export const extendSession = async (sessionId, minutes) =>
  sessionAdapter(await apiCall('POST', `/lecturer/sessions/${sessionId}/extend`, { minutes }))

// A class the job couldn't tell was held (FR-317)
export const confirmSession = async (sessionId, held) =>
  sessionAdapter(await apiCall('POST', `/lecturer/sessions/${sessionId}/confirm`, { held }))

// Moodle sync now instead of at the next try (FR-312)
export const retryMoodleSync = async (sessionId) =>
  sessionAdapter(await apiCall('POST', `/lecturer/sessions/${sessionId}/moodle-sync`))

// keep: 'smartclass' | 'moodle' (FR-320)
export const resolveMoodleConflict = async (sessionId, recordId, keep) =>
  sessionAdapter(await apiCall('POST', `/lecturer/sessions/${sessionId}/moodle-conflicts/${recordId}`, { keep }))

// ─── Class schedule (FR-301) ──────────────────────────────────────────

// All of day/start/end, or all null to clear the weekly slot. Moodle sync never overwrites it.
export const setWeeklySchedule = async (classId, { day, start, end, room }) => {
  const c = await apiCall('PUT', `/lecturer/classes/${classId}/schedule`, {
    day_of_week: day || null,
    start_time: start || null,
    end_time: end || null,
    room: room?.trim() || null,
  })
  return { day_of_week: c.day_of_week, start_time: c.start_time, end_time: c.end_time, room: c.room }
}

// ─── Attendance ───────────────────────────────────────────────────────────────

export const getStudents = async (sessionId, { sessionOpen = false } = {}) => {
  const list = await apiCall('GET', `/lecturer/sessions/${sessionId}/attendance`)
  return list.map((s, i) => studentAdapter(s, i, sessionOpen))
}

// Any of the four statuses, with an optional reason that is audited (FR-305)
export const overrideAttendance = async (recordId, newStatus, sessionId, studentId, reason) => {
  const body = { status: newStatus, reason: cleanReason(reason) }
  if (recordId) {
    return apiCall('PUT', `/attendance/${recordId}/override`, body)
  }
  return apiCall('PUT', `/lecturer/sessions/${sessionId}/attendance/override`, { student_id: studentId, ...body })
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

// ─── Admin area (browser only; the server answers 403 to anyone but an admin) ───

const query = (params) => {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
  return parts.length ? `?${parts.join('&')}` : ''
}

// Accounts (FR-103, FR-108): { items, total, page, limit }
export const adminListUsers = async ({ q, role, status, page = 1, limit = 50 } = {}) =>
  apiCall('GET', `/admin/users${query({ q: q?.trim(), role, status, page, limit })}`)

export const adminDeactivateUser = async (id) => apiCall('DELETE', `/admin/users/${id}`)

export const adminReactivateUser = async (id) => apiCall('POST', `/admin/users/${id}/reactivate`)

export const adminCreateAdmin = async ({ name, email, password }) =>
  apiCall('POST', '/admin/users', { name: name.trim(), email: email.trim(), password, role: 'admin' })

// Deletes the student's face data and closes a pending submission (FR-117)
export const adminResetFaceData = async (userId) => apiCall('DELETE', `/admin/students/${userId}/face-data`)

export const adminAuditLogs = async ({ page = 1, limit = 50 } = {}) =>
  apiCall('GET', `/admin/audit-logs${query({ page, limit })}`)

// Moodle sync (FR-104): the last full sync (null before the first) and "Sync now"
export const adminLastSync = async () => apiCall('GET', '/admin/moodle/sync')

export const adminSyncNow = async () => apiCall('POST', '/admin/moodle/sync')

// ─── AI Learning Assistant (Module 8) ────────────────────────────────────────

// Courses the lecturer teaches, with how many materials are indexed (FR-815)
export const getAssistantCourses = async () => {
  const list = await apiCall('GET', '/lecturer/assistant/courses')
  return list.map(c => ({
    id: c.course_id,
    code: c.code,
    name: courseName(c.code, c.name),
    indexedMaterials: c.indexed_materials ?? 0,
  }))
}

// Each material's processing status (FR-804)
export const getMaterials = async (courseId) => {
  const list = await apiCall('GET', `/kb/courses/${courseId}/materials`)
  return list.map(m => ({
    id: m.id,
    title: m.title,
    fileName: m.file_name,
    section: m.section_name ?? null,
    status: m.status,
    errorText: m.error_text ?? null,
    units: m.unit_count ?? null,
    chunks: m.chunk_count ?? 0,
  }))
}

// "Sync now": pull changes from Moodle immediately (FR-803)
export const syncMaterials = async (courseId) => apiCall('POST', `/kb/courses/${courseId}/sync`)

// Anonymised question trends (FR-813, NFR-09)
export const getQuestionTrends = async (courseId) => {
  const t = await apiCall('GET', `/lecturer/assistant/trends/${courseId}`)
  return {
    mostAsked: t.most_asked_topics ?? [],
    mostCited: t.most_cited_materials ?? [],
    uncovered: t.topics_materials_dont_cover ?? [],
  }
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
