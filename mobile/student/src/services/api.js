import { apiCall, apiUpload, setToken, clearToken, setRefreshToken, clearRefreshToken } from './client'
import { enrolmentParts } from './faceEnrolment'
import { toCourseView } from './attendance'
import { PART_SUMMARY, PARTICIPATION_GROUPS, SESSION_PERFS } from '../data/mockData'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function initials(name = '') {
  return name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase()
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

// Turns a failed sign-in into a message the student can act on
function signInError(e) {
  if (e.status === 401) return new Error('Wrong SPeCTRUM username or password.')
  if (e.status === 503) return new Error(e.message || 'SPeCTRUM is not reachable right now. Please try again later.')
  if (!e.status) return new Error("Can't reach the SmartClass server. Check your connection and try again.")
  return e
}

// Students sign in with their SPeCTRUM (Moodle) account (FR-101)
export const login = async (username, password) => {
  let data
  try {
    data = await apiCall('POST', '/auth/moodle-login', { username: username.trim(), password })
  } catch (e) {
    throw signInError(e)
  }
  if (data.user.role !== 'student') {
    throw new Error('This app is for students. Lecturers use the SmartClass Lecturer app.')
  }
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
    code: c.course_code,
    name: c.course_name,
    type: c.type,
    label: c.label ?? null,
    venue: c.room ?? '',
    lecturer: c.lecturer_name ?? '—',
    day_of_week: c.day_of_week ?? '',
    start_time: c.start_time ?? '',
    end_time: c.end_time ?? '',
    accentColor: ACCENT_COLORS[i % ACCENT_COLORS.length],
    liveSession: false,
    attendedCount: 0,
    totalSessions: 0,
    status: 'ok',
    nextSchedule: null,
  }))
}

// ─── Attendance ───────────────────────────────────────────────────────────────

// Per-course rate, counts and session history (FR-309, T32)
export const getAttendanceCourses = async () => {
  const [courses, classes] = await Promise.all([
    apiCall('GET', '/student/me/attendance/courses'),
    apiCall('GET', '/classes'),
  ])
  const occLookup = {}
  for (const c of classes) occLookup[c.id] = { venue: c.room ?? '', lecturer: c.lecturer_name ?? '' }
  return courses.map(c => toCourseView(c, occLookup))
}

// "I'm here but wasn't recognised" (FR-318): once per open session with no record
export const flagNotRecognised = (sessionId) =>
  apiCall('POST', `/student/me/sessions/${sessionId}/flag`)

// The student's own flags, newest first (FR-319)
export const getMyFlags = (sessionId) =>
  apiCall('GET', sessionId != null ? `/student/me/flags?session_id=${sessionId}` : '/student/me/flags')

// ─── AI Learning Assistant (Module 8) ─────────────────────────────────────────

export const getAssistantCourses = () => apiCall('GET', '/student/assistant/courses')

export const getChatSessions = (courseId) =>
  apiCall('GET', `/student/assistant/sessions?course_id=${courseId}`)

export const createChatSession = (courseId) =>
  apiCall('POST', '/student/assistant/sessions', { course_id: courseId })

export const renameChatSession = (sessionId, title) =>
  apiCall('PATCH', `/student/assistant/sessions/${sessionId}`, { title })

export const deleteChatSession = (sessionId) =>
  apiCall('DELETE', `/student/assistant/sessions/${sessionId}`)

export const getChatMessages = (sessionId) =>
  apiCall('GET', `/student/assistant/sessions/${sessionId}/messages`)

export const sendChatMessage = (sessionId, content) =>
  apiCall('POST', `/student/assistant/sessions/${sessionId}/messages`, { content })

// Summary / study guide (FR-810): exactly one of material_id / topic
export const generateSummary = (courseId, { materialId = null, topic = null, kind = 'summary' } = {}) =>
  apiCall('POST', '/student/assistant/summaries', {
    course_id: courseId, material_id: materialId, topic: topic, kind,
  })

// Flashcards / practice questions (FR-811)
export const generateStudyTools = (courseId, { materialId = null, topic = null, kind } = {}) =>
  apiCall('POST', '/student/assistant/study-tools', {
    course_id: courseId, material_id: materialId, topic: topic, kind,
  })

// ─── Face enrolment (FR-109, FR-110, FR-115, FR-116) ──────────────────────────

export const getFaceConsent = () => apiCall('GET', '/student/me/face-consent')

export const giveFaceConsent = (version) =>
  apiCall('POST', '/student/me/face-consent', { version })

export const withdrawFaceConsent = () => apiCall('DELETE', '/student/me/face-consent')

export const getFaceEnrolment = () => apiCall('GET', '/student/me/face-enrolment')

// selfies: [{ uri }], card: { uri }. A 422 carries `detail` = { reasons, message, can_submit_anyway, ... }
export const submitFaceEnrolment = (selfies, card, submitAnyway = false) =>
  apiUpload('POST', '/student/me/face-enrolment', () => {
    const form = new FormData()
    for (const [name, value] of enrolmentParts(selfies, card, submitAnyway)) form.append(name, value)
    return form
  })

// ─── Mocked (Module 3/4 — participation/quiz)─────────────────────────────────

const delay = (ms) => new Promise(res => setTimeout(res, ms))

export const getParticipationSummary = async () => { await delay(200); return PART_SUMMARY }
export const getParticipationGroups  = async () => { await delay(300); return PARTICIPATION_GROUPS }
export const getSessionPerf = async (perfKey) => { await delay(200); return SESSION_PERFS[perfKey] ?? null }
export const sendPasswordReset = async () => { await delay(400); return { success: true } }
