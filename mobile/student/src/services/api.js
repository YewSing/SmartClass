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

// Role dashboard and notification centre (M2)
export const getDashboard = () => apiCall('GET', '/student/me/dashboard')
export const getNotifications = (beforeId = null) =>
  apiCall('GET', `/notifications?limit=50${beforeId != null ? `&before_id=${beforeId}` : ''}`)
export const getNotificationUnreadCount = async () => {
  let before = null, count = 0
  do {
    const page = await getNotifications(before)
    count += page.filter(note => !note.read_at).length
    if (page.length < 50) return count
    before = page[page.length - 1].id
  } while (before != null)
  return count
}
export const markNotificationRead = (id) => apiCall('POST', `/notifications/${id}/read`)
export const markAllNotificationsRead = () => apiCall('POST', '/notifications/read-all')

// Module 6: quizzes are delivered by the server; answers are autosaved per question.
export const getQuizzes = () => apiCall('GET', '/quizzes')
export const startQuizAttempt = id => apiCall('POST', `/quizzes/${id}/attempts`)
export const saveQuizAnswer = (quizId, attemptId, index, answer) =>
  apiCall('PUT', `/quizzes/${quizId}/attempts/${attemptId}/answers/${index}`, { answer })
export const submitQuizAttempt = (quizId, attemptId) => apiCall('POST', `/quizzes/${quizId}/attempts/${attemptId}/submit`)
export const getQuizResult = id => apiCall('GET', `/quizzes/${id}/results/me`)
export const getGameLeaderboard = id => apiCall('GET', `/quizzes/${id}/leaderboard`)

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

// All chats (history panel), or one course's
export const getChatSessions = (courseId = null) =>
  apiCall('GET', courseId != null ? `/student/assistant/sessions?course_id=${courseId}` : '/student/assistant/sessions')

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

// A study tool inside a chat (FR-810/811): the request and the result are saved as chat messages
export const runChatTool = (sessionId, kind, topic) =>
  apiCall('POST', `/student/assistant/sessions/${sessionId}/tools`, { kind, topic })

// Remember the last score on a practice set
export const savePracticeScore = (messageId, correct, total) =>
  apiCall('PATCH', `/student/assistant/messages/${messageId}/score`, { correct, total })

// Related YouTube videos and search keywords for a topic (FR-812)
export const getRelatedVideos = (courseId, topic) =>
  apiCall('POST', '/student/assistant/youtube', { course_id: courseId, topic })

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

// Module 5 live-class adapters.  These keep the screen focused on one active
// lecturer prompt/poll while using the current interaction-session contract.
const interactionPath = (sessionId, suffix = '') => `/interaction/sessions/${sessionId}${suffix}`
const optionRows = (poll) => (poll?.options ?? []).map((option_text, id) => ({
  id,
  option_text,
  votes: poll.results?.option_counts?.[id] ?? 0,
}))
const activeLast = (items) => [...items].reverse().find(item => item.status === 'open') ?? null

export const getOpenInteractions = async () => [] // LiveClass is entered from the live session on Home.
export const getInteractionState = async (sessionId) => {
  const state = await apiCall('GET', interactionPath(sessionId))
  const sourcePoll = activeLast(state.polls ?? [])
  const sourcePrompt = activeLast(state.quick_prompts ?? [])
  return {
    ...state,
    current_poll: sourcePoll && {
      ...sourcePoll,
      question: sourcePoll.prompt,
      is_open: sourcePoll.status === 'open',
      options: optionRows(sourcePoll),
      my_option_id: sourcePoll.my_option_indexes?.[0] ?? null,
    },
    live_question: sourcePrompt && {
      ...sourcePrompt,
      question: sourcePrompt.prompt,
      is_active: sourcePrompt.status === 'open',
      my_response: sourcePrompt.answered_by_me ? 'Response sent' : null,
    },
    my_questions: state.questions?.filter(question => question.is_mine) ?? [],
    idu_distinct_students: 0,
    idu_has_signal: false,
  }
}
export const askInteractionQuestion = (sessionId, body) =>
  apiCall('POST', interactionPath(sessionId, '/questions'), body)
export const respondToLiveQuestion = (sessionId, promptId, text) =>
  apiCall('POST', interactionPath(sessionId, `/quick-prompts/${promptId}/answers`), { text })
export const voteInteractionPoll = (pollId, optionId, sessionId) => {
  if (!Number.isSafeInteger(sessionId)) throw new Error('Live poll session is unavailable.')
  return apiCall('PUT', interactionPath(sessionId, `/polls/${pollId}/vote`), { option_indexes: [Number(optionId)] })
}
export const sendInteractionReaction = (sessionId, kind) =>
  apiCall('POST', interactionPath(sessionId, '/reactions'), { kind })
export const sendInteractionIDU = (sessionId) =>
  apiCall('POST', interactionPath(sessionId, '/confusion'), {})
