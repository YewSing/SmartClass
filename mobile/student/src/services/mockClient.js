// Simulation (offline) client for the Student app.
// Fully stateful — taking/submitting a quiz persists the attempt, and the result
// reflects grading_complete / score / answers. All data seeded from mockData.js.
import AsyncStorage from '@react-native-async-storage/async-storage'

const SIMULATION = process.env.EXPO_PUBLIC_SIMULATION === '1'
const BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://10.0.2.2:8000'
const DELAY = 450

import { PART_SUMMARY, PARTICIPATION_GROUPS, SESSION_PERFS } from '../data/mockData'

const delay = (ms) => new Promise((r) => setTimeout(r, ms))
const nowIso = new Date().toISOString()
const todayIso = new Date().toISOString().slice(0, 10)

// ═══ Token storage ════════════════════════════════════════════════════════

let _token = null
let _refreshToken = null

export async function initStorage() {
  try {
    _token = await AsyncStorage.getItem('token')
    _refreshToken = await AsyncStorage.getItem('refresh_token')
  } catch { _token = null; _refreshToken = null }
}

export function getToken() { return _token }
export function setToken(t) { _token = t; AsyncStorage.setItem('token', t).catch(() => {}) }
export function clearToken() { _token = null; AsyncStorage.removeItem('token').catch(() => {}) }
export function getRefreshToken() { return _refreshToken }
export function setRefreshToken(t) { _refreshToken = t; AsyncStorage.setItem('refresh_token', t).catch(() => {}) }
export function clearRefreshToken() { _refreshToken = null; AsyncStorage.removeItem('refresh_token').catch(() => {}) }

// ═══ Auth expiry listeners ══════════════════════════════════════════════

const _authListeners = []
export function onAuthExpired(fn) {
  _authListeners.push(fn)
  return () => { const i = _authListeners.indexOf(fn); if (i !== -1) _authListeners.splice(i, 1) }
}
function _fireAuthExpired() { _authListeners.forEach((f) => f()) }

let _refreshPromise = null
async function _doRefresh() {
  if (_refreshPromise) return _refreshPromise
  _refreshPromise = (async () => {
    const rt = getRefreshToken()
    if (!rt) return false
    try { await delay(DELAY); setToken('sim-token'); return true } catch { return false } finally { _refreshPromise = null }
  })()
  return _refreshPromise
}
function _forceLogout() { clearToken(); clearRefreshToken(); _fireAuthExpired() }

const LOGIN_PATHS = ['/auth/login', '/auth/moodle-login']

// ═════════════════════════════════════════════════════════════════════════
// STATEFUL IN-MEMORY DATABASE
// ═════════════════════════════════════════════════════════════════════════

const db = {
  me: {
    id: 101, name: 'Ahmad Izzul Hakim', email: 'ahmad.izzul@siswa.um.edu.my',
    role: 'student',
    student: { matric_no: 'U2300124', programme: 'Bachelor of Computer Science', faculty: 'Computer Science & IT', year_sem: 'Year 3, Sem 2' },
  },
  classes: [
    {
      id: 1, course_id: 'WIA2005', course_code: 'WIA2005', course_name: 'Software Engineering',
      type: 'lecture', label: 'Lec 12', room: 'DK 6, BLI Building', lecturer_name: 'Dr. Tan Wei Liang',
      day_of_week: 'Mon', start_time: '10:00', end_time: '12:00', venue: 'DK 6, BLI Building',
      accentColor: '#0E6FBF', venue_line: 'DK 6, BLI Building · Mon 10:00–12:00',
    },
    {
      id: 2, course_id: 'WIA2004', course_code: 'WIA2004', course_name: 'Data Mining',
      type: 'lecture', label: 'Lec 11', room: 'DK 5, BLI Building', lecturer_name: 'Dr. Lim Wei Hao',
      day_of_week: 'Wed', start_time: '14:00', end_time: '16:00', venue: 'DK 5, BLI Building',
      accentColor: '#12A564', venue_line: 'DK 5, BLI Building · Wed 14:00–16:00',
    },
  ],
  attendanceCourses: [
    {
      id: 1, occurrence_id: 1,
      course_id: 'WIA2005', course_code: 'WIA2005', course_name: 'Software Engineering',
      rate: 88.9, rateText: '88.9%', note: 'Late counts as attended',
      present: 8, late: 0, excused: 0, absent: 1, counted_sessions: 9, closed_sessions: 9,
      counts: { present: 8, late: 0, excused: 0, absent: 1 },
      sessions: [
        { id: 101, day: 'Mon', month: 'May 26', date: '2025-05-26', title: 'Software Engineering', sub: 'DK 6, BLI Building · 10:00–12:00', status: 'present', label: 'Present', badge: 'green', isLive: false, starts_at: '2025-05-26T10:05:00', detected_at: '2025-05-26T10:05:00', overridden: false, session_status: 'closed', occurrence_id: 1 },
        { id: 102, day: 'Mon', month: 'May 19', date: '2025-05-19', title: 'Software Engineering', sub: 'DK 6, BLI Building · 10:00–12:00', status: 'absent', label: 'Absent', badge: 'red', isLive: false, starts_at: '2025-05-19T08:00:00', detected_at: null, overridden: false, session_status: 'closed', occurrence_id: 1 },
        { id: 103, day: 'Mon', month: 'May 12', date: '2025-05-12', title: 'Software Engineering', sub: 'DK 6, BLI Building · 10:00–12:00', status: 'present', label: 'Present', badge: 'green', isLive: false, starts_at: '2025-05-12T08:00:00', detected_at: '2025-05-12T08:00:00', overridden: false, session_status: 'closed', occurrence_id: 1 },
      ],
    },
    {
      id: 2, occurrence_id: 2,
      course_id: 'WIA2004', course_code: 'WIA2004', course_name: 'Data Mining',
      rate: 71.4, rateText: '71.4%', note: 'Late counts as attended',
      present: 5, late: 0, excused: 0, absent: 2, counted_sessions: 7, closed_sessions: 7,
      counts: { present: 5, late: 0, excused: 0, absent: 2 },
      sessions: [
        { id: 201, day: 'Wed', month: 'May 21', date: '2025-05-21', title: 'Data Mining', sub: 'DK 5, BLI Building · 14:00–16:00', status: 'present', label: 'Present', badge: 'green', isLive: false, starts_at: '2025-05-21T14:00:00', detected_at: '2025-05-21T14:05:00', overridden: false, session_status: 'closed', occurrence_id: 2 },
        { id: 202, day: 'Wed', month: 'May 14', date: '2025-05-14', title: 'Data Mining', sub: 'DK 5, BLI Building · 14:00–16:00', status: 'absent', label: 'Absent', badge: 'red', isLive: false, starts_at: '2025-05-14T14:00:00', detected_at: null, overridden: false, session_status: 'closed', occurrence_id: 2 },
      ],
    },
  ],
  interactions: [
    {
      id: 1, class_code: 'WIA2005', class_name: 'Software Engineering', status: 'open',
      opened_at: nowIso, current_poll: {
        id: 1, question: 'How confident are you about today\'s topic?',
        is_open: true,
        options: [
          { id: 1, option_text: 'Very confident', votes: 4 },
          { id: 2, option_text: 'Somewhat confident', votes: 7 },
          { id: 3, option_text: 'Not confident', votes: 2 },
        ],
        my_option_id: null,
      },
      live_question: {
        id: 1, question: 'Does anyone need clarification on dependency injection?',
        is_active: true, my_response: null, responses: [],
      },
      reaction_counts: { understood: 4, confused: 1, pace_too_fast: 2 },
      my_reaction: null, idu_distinct_students: 2, idu_has_signal: false,
      questions: [], my_questions: [],
    },
  ],
  quizzes: [
    {
      id: 'q1', course_id: 'WIA2005', title: 'Sprint Planning Quiz', status: 'published',
      time_limit_minutes: 30, opens_at: null, closes_at: null,
      attempts_allowed: 1, review_visible: true,
      attempts_used: 0, attempt_id: null, has_attempt: false, deadline: null,
      questions: [
        { id: 1, type: 'mcq', question: 'Which HTTP method is idempotent and used to retrieve a resource?', options: ['POST', 'GET', 'DELETE', 'PATCH'], correct_answer: 'GET', suggested_answer: null, level: 'beginner', score: 1, topic: 'HTTP basics' },
        { id: 2, type: 'mcq', question: 'What does SOLID stand for in object-oriented design?', options: ['Single, Open, Liskov, Interface, Dependency', 'Simple, Object, Local, Interface, Design', 'Solid, Open, Linked, Integrated, Dynamic', 'Standard, Object, Logic, Interface, Data'], correct_answer: 'Single, Open, Liskov, Interface, Dependency', suggested_answer: null, level: 'beginner', score: 1, topic: 'SOLID principles' },
      ],
    },
    {
      id: 'q2', course_id: 'WIA2005', title: 'SOLID Principles Quiz', status: 'published',
      time_limit_minutes: 60, opens_at: null, closes_at: null,
      attempts_allowed: 1, review_visible: false,
      attempts_used: 1, attempt_id: 'a1', has_attempt: true, deadline: null,
      questions: [],
    },
  ],
  attempts: {
    a1: {
      id: 'a1', quiz_id: 'q2', answers: {}, submitted: true, score: '72%', correct: 18, wrong: 5, skipped: 2, total: 25, submitted_at: nowIso, auto_submitted: false,
    },
  },
  attemptAnswers: {
    a1: [
      { question_id: 1, answer: 'GET', score: 1.0, max_score: 1.0, auto_graded: true, question: 'Which HTTP method is idempotent and used to retrieve a resource?', type: 'mcq', options: ['POST', 'GET', 'DELETE', 'PATCH'], correct_answer: 'GET', suggested_answer: null, learning_hint: null },
      { question_id: 2, answer: 'Single, Open, Liskov, Interface, Dependency', score: 1.0, max_score: 1.0, auto_graded: true, question: 'What does SOLID stand for in object-oriented design?', type: 'mcq', options: ['Single, Open, Liskov, Interface, Dependency', 'Simple, Object, Local, Interface, Design', 'Solid, Open, Linked, Integrated, Dynamic', 'Standard, Object, Logic, Interface, Data'], correct_answer: 'Single, Open, Liskov, Interface, Dependency', suggested_answer: null, learning_hint: null },
      { question_id: 3, answer: 'Abstraction hides implementation details while showing essential features.', score: null, max_score: 2.0, auto_graded: false, question: 'Explain the difference between an abstract class and an interface in Java.', type: 'short_answer', options: [], correct_answer: null, suggested_answer: 'An abstract class can have implemented methods and state; an interface defines a contract.', learning_hint: 'See Week 3 – Java OOP, Chapter 4, pages 12-15' },
    ],
  },
  chatSessions: [],
  messages: {},
  faceConsent: { version: 1, given: false },
  faceEnrolment: { status: 'none' },
  flags: {},
  participation: { summary: PART_SUMMARY, groups: PARTICIPATION_GROUPS, sessionPerfs: SESSION_PERFS },
}

let nextAttemptId = 1
let nextChatId = 1
let nextMessageId = 1

// ═══ Helpers ═════════════════════════════════════════════════════════════

function segId(p, prefix) {
  const rest = p.slice(prefix.length)
  const first = rest.split('?')[0].split('/')[0]
  return first === '' ? null : first
}

function computeResult(attemptId) {
  const att = db.attempts[String(attemptId)]
  if (!att) return null
  const q = db.quizzes.find((x) => x.id === att.quiz_id)
  const reviewVisible = q ? q.review_visible : true
  const list = db.attemptAnswers[String(attemptId)] || []
  const total = list.reduce((s, a) => s + (a.max_score ?? 1), 0)
  const scored = list.filter(a => a.score != null)
  const pct = scored.length ? Math.round((scored.reduce((s, a) => s + a.score, 0) / total) * 100) : null
  const grading_complete = list.every(a => a.score != null)
  return {
    attempt_id: String(attemptId), status: att.status,
    score: att.score ?? (pct != null ? String(pct) : null),
    percentage_score: pct,
    raw_score: scored.reduce((s, a) => s + a.score, 0),
    max_score: total, auto_submitted: att.auto_submitted ?? false,
    grading_complete, student_score_visible: grading_complete && reviewVisible, review_visible: reviewVisible,
    answers: list,
  }
}

// ═══ Route dispatcher ═══════════════════════════════════════════════════

function route(method, path, body) {
  const p = path.split('?')[0]

  // ── Auth ──
  if (method === 'POST' && p === '/auth/moodle-login') {
    return { status: 200, json: { user: { name: 'Ahmad Izzul Hakim', email: 'ahmad.izzul@siswa.um.edu.my', role: 'student', id: 101 }, access_token: 'sim-access', refresh_token: 'sim-refresh' } }
  }
  if (method === 'GET' && p === '/auth/me') {
    return { status: 200, json: db.me }
  }

  // ── Classes ──
  if (method === 'GET' && p === '/classes') {
    return { status: 200, json: db.classes }
  }

  // ── Attendance ──
  if (method === 'GET' && p === '/student/me/attendance/courses') {
    return { status: 200, json: db.attendanceCourses }
  }
  if (method === 'POST' && p.match(/\/student\/me\/sessions\/[^/]+\/flag$/)) {
    return { status: 200, json: { id: 1, session_id: Number(segId(p, '/student/me/sessions/')), status: 'pending' } }
  }
  if (method === 'GET' && p === '/student/me/flags') {
    return { status: 200, json: Object.values(db.flags) }
  }
  if (method === 'GET' && p.startsWith('/student/me/flags')) {
    const qs = new URLSearchParams(path.split('?')[1] ?? '')
    const sessionId = qs.get('session_id')
    return { status: 200, json: Object.values(db.flags).filter((f) => sessionId == null || String(f.session_id) === sessionId) }
  }

  // ── Interaction ──
  if (method === 'GET' && p === '/student/interactions') {
    return { status: 200, json: db.interactions.filter(i => i.status === 'open') }
  }
  if (method === 'GET' && p.match(/\/student\/interactions\/[^/]+$/)) {
    const id = segId(p, '/student/interactions/')
    const i = db.interactions.find((x) => String(x.id) === id)
    return { status: 200, json: i || { id, status: 'open', current_poll: null, live_question: null, reaction_counts: {}, questions: [], my_questions: [] } }
  }
  if (method === 'POST' && p.match(/\/student\/interactions\/[^/]+\/questions$/)) {
    return { status: 200, json: { id: 1 } }
  }
  if (method === 'POST' && p.match(/\/student\/interactions\/[^/]+\/live-question\/[^/]+\/response$/)) {
    return { status: 200, json: { recorded: true } }
  }
  if (method === 'POST' && p.match(/\/student\/polls\/[^/]+\/vote$/)) {
    return { status: 200, json: { voted: true } }
  }
  if (method === 'POST' && p.match(/\/student\/interactions\/[^/]+\/reactions$/)) {
    return { status: 200, json: {} }
  }
  if (method === 'POST' && p.match(/\/student\/interactions\/[^/]+\/idu$/)) {
    return { status: 200, json: { has_signal: true } }
  }

  // ── Analytics (FR-706, S43) ──
  if (method === 'GET' && p === '/student/me/analytics') {
    return {
      status: 200,
      json: {
        student_id: 101,
        overall_attendance_rate: 82.5,
        courses: [
          {
            course_id: 1,
            course_code: 'WIA2005',
            course_name: 'Software Engineering',
            attendance: { rate: 88.9, absence_frequency: 1, attended: 8, total: 9 },
            participation: { frequency: 18, questions: 4, votes: 7, responses: 3, reactions: 3, idu_signals: 1 },
            quizzes: {
              scores: [88.0, 72.0, 84.0],
              average_score: 81.3,
              trend: [
                { quiz_id: 'q1', title: 'Sprint Planning Quiz', score: 88.0 },
                { quiz_id: 'q2', title: 'SOLID Principles Quiz', score: 72.0 },
                { quiz_id: 'q3', title: 'UML Design Patterns', score: 84.0 },
              ],
            },
          },
          {
            course_id: 2,
            course_code: 'WIA2004',
            course_name: 'Data Mining',
            attendance: { rate: 71.4, absence_frequency: 2, attended: 5, total: 7 },
            participation: { frequency: 9, questions: 1, votes: 5, responses: 2, reactions: 1, idu_signals: 0 },
            quizzes: {
              scores: [65.0, 70.0],
              average_score: 67.5,
              trend: [
                { quiz_id: 'dm1', title: 'Decision Trees Quiz', score: 65.0 },
                { quiz_id: 'dm2', title: 'Clustering Algorithms', score: 70.0 },
              ],
            },
          },
        ],
      },
    }
  }

  // ── AI Assistant ──
  if (method === 'GET' && p === '/student/assistant/courses') {
    return { status: 200, json: db.classes.map((c) => ({ course_id: c.course_id, code: c.course_code, name: c.course_name, indexed_materials: 3 })) }
  }
  if (method === 'GET' && p === '/student/assistant/sessions') {
    return { status: 200, json: db.chatSessions }
  }
  if (method === 'GET' && p.startsWith('/student/assistant/sessions')) {
    return { status: 200, json: db.chatSessions }
  }
  if (method === 'POST' && p === '/student/assistant/sessions') {
    const s = { id: nextChatId++, course_id: body && body.course_id, title: 'New chat', created_at: nowIso, updated_at: nowIso }
    db.chatSessions.push(s)
    db.messages[s.id] = []
    return { status: 200, json: s }
  }
  if (method === 'PATCH' && p.match(/\/student\/assistant\/sessions\/[^/]+$/)) {
    const id = segId(p, '/student/assistant/sessions/')
    const s = db.chatSessions.find((x) => x.id === id)
    if (s && body) s.title = body.title
    return { status: 200, json: s || {} }
  }
  if (method === 'DELETE' && p.match(/\/student\/assistant\/sessions\/[^/]+$/)) {
    const id = segId(p, '/student/assistant/sessions/')
    db.chatSessions = db.chatSessions.filter((x) => x.id !== id)
    delete db.messages[id]
    return { status: 200, json: {} }
  }
  if (method === 'GET' && p.match(/\/student\/assistant\/sessions\/[^/]+\/messages$/)) {
    const id = segId(p, '/student/assistant/sessions/')
    if (db.messages[id] && db.messages[id].length > 0) {
      return { status: 200, json: db.messages[id] }
    }
    return { status: 200, json: [
      { id: 1, role: 'user', content: 'Explain dependency injection with a code example', kind: 'chat', created_at: nowIso },
      {
        id: 2, role: 'assistant', content:
          'Dependency Injection (DI) is a design pattern where a class receives its dependencies from external sources rather than creating them itself.\n\n' +
          '**Example (Java):**\n' +
          '```java\n' +
          'class EmailService { send(msg) { console.log(msg) } }\n' +
          'class UserController {\n' +
          '  constructor(emailService) { this.emailService = emailService }\n' +
          '  signup(user) { this.emailService.send(\'Welcome ' + '${user}\') }\n' +
          '}\n' +
          '```\n\n' +
          'Here `EmailService` is injected into `UserController` via the constructor, making the controller easier to test and decoupled.\n\n' +
          'This is covered in **Week 3 – SOLID Principles & Design Patterns**, Chapter 4.',
        kind: 'chat', citations: [{ n: 1, title: 'Week 3 – SOLID Principles & Design Patterns', section: 'Chapter 4', page: 12 }], source_type: 'materials', created_at: nowIso,
      },
    ] }
  }
  if (method === 'POST' && p.match(/\/student\/assistant\/sessions\/[^/]+\/messages$/)) {
    const id = segId(p, '/student/assistant/sessions/')
    const userMsg = { id: nextMessageId++, role: 'user', content: body && body.content, kind: 'chat', created_at: nowIso }
    const assistantMsg = { id: nextMessageId++, role: 'assistant', content: 'This is a simulated reply — no backend is connected. In production this would answer from your course materials with citations.', kind: 'chat', citations: [], source_type: 'general', created_at: nowIso }
    ;(db.messages[id] || []).push(userMsg, assistantMsg)
    return { status: 200, json: assistantMsg }
  }
  if (method === 'POST' && p.match(/\/student\/assistant\/sessions\/[^/]+\/tools$/)) {
    return { status: 200, json: { id: nextMessageId++, role: 'assistant', content: 'Study tool result (simulated).', kind: 'chat', citations: [], source_type: 'general', created_at: nowIso } }
  }
  if (method === 'PATCH' && p.match(/\/student\/assistant\/messages\/[^/]+\/score$/)) {
    return { status: 200, json: { saved: true } }
  }
  if (method === 'POST' && p === '/student/assistant/youtube') {
    return { status: 200, json: { videos: [], keywords: [body && body.topic] } }
  }

  // ── Face enrolment ──
  if (method === 'GET' && p === '/student/me/face-consent') {
    return { status: 200, json: db.faceConsent }
  }
  if (method === 'POST' && p === '/student/me/face-consent') {
    db.faceConsent = { version: body && body.version, given: true }
    return { status: 200, json: db.faceConsent }
  }
  if (method === 'DELETE' && p === '/student/me/face-consent') {
    db.faceConsent = { version: 1, given: false }
    return { status: 200, json: {} }
  }
  if (method === 'GET' && p === '/student/me/face-enrolment') {
    return { status: 200, json: db.faceEnrolment }
  }
  if (method === 'POST' && p === '/student/me/face-enrolment') {
    db.faceEnrolment = { status: 'submitted', submitted_at: nowIso }
    return { status: 200, json: {} }
  }

  // ── Quizzes ──
  if (method === 'GET' && p === '/student/quizzes') {
    return { status: 200, json: db.quizzes }
  }
  if (method === 'GET' && p.match(/\/student\/quizzes\/[^/]+$/)) {
    const id = p.match(/\/student\/quizzes\/([^/]+)$/)[1]
    const q = db.quizzes.find((x) => x.id === id)
    return { status: 200, json: q || { id, title: 'Simulated Quiz', questions: [] } }
  }

  // Quiz detail for taking (questions + active attempt)
  if (method === 'GET' && p.match(/\/student\/quizzes\/[^/]+$/)) {
    const id = p.match(/\/student\/quizzes\/([^/]+)$/)[1]
    const q = db.quizzes.find((x) => x.id === id)
    if (!q) return { status: 404, json: { detail: 'Quiz not found' } }
    const activeAttemptId = q.attempt_id
    const activeDeadline = q.deadline
    return { status: 200, json: {
      questions: q.questions,
      active_attempt_id: activeAttemptId,
      active_deadline: activeDeadline,
      saved_answers: q.attempts_used > 0 ? db.attempts[String(q.attempt_id)]?.answers ?? {} : {},
    } }
  }

  // Start attempt
  if (method === 'POST' && p.match(/\/student\/quizzes\/[^/]+\/attempt$/)) {
    const quizId = p.match(/\/student\/quizzes\/([^/]+)\/attempt$/)[1]
    const q = db.quizzes.find((x) => x.id === quizId)
    if (!q) return { status: 404, json: { detail: 'Quiz not found' } }
    if (q.attempts_used >= q.attempts_allowed) {
      return { status: 409, json: { detail: 'already_attempted' } }
    }
    const attemptId = String(nextAttemptId++)
    const startedAt = nowIso
    const deadline = new Date(Date.now() + q.time_limit_minutes * 60000).toISOString()
    db.attempts[attemptId] = {
      id: attemptId, quiz_id: quizId, answers: {}, submitted: false,
      score: null, correct: 0, wrong: 0, skipped: 0, total: q.questions.length,
      submitted_at: null, auto_submitted: false, started_at: startedAt, deadline,
    }
    q.attempts_used += 1
    q.attempt_id = attemptId
    q.has_attempt = true
    q.deadline = deadline
    return { status: 201, json: { attempt_id: attemptId, started_at: startedAt, deadline } }
  }

  // Save progress
  if (method === 'PUT' && p.match(/\/student\/quizzes\/attempts\/[^/]+\/answers$/)) {
    const id = segId(p, '/student/quizzes/attempts/')
    if (db.attempts[id]) db.attempts[id].answers = body && body.answers
    return { status: 200, json: { saved: true } }
  }

  // Submit attempt → returns result data so TakeQuiz can navigate to QuizResult
  if (method === 'POST' && p.match(/\/student\/quizzes\/attempts\/[^/]+\/submit$/)) {
    const id = segId(p, '/student/quizzes/attempts/')
    const att = db.attempts[String(id)]
    if (!att) return { status: 404, json: { detail: 'attempt_not_found' } }
    if (att.submitted) return { status: 409, json: { detail: 'already_submitted' } }
    att.submitted = true
    att.submitted_at = nowIso
    // Auto-grade MCQs
    const answers = body && body.answers || []
    const list = (db.attemptAnswers[String(id)] || []).map(a => {
      const userAns = answers.find(ans => ans.question_id === a.question_id)
      if (a.type === 'mcq' && userAns) {
        const correct = userAns.answer === a.correct_answer
        return { ...a, answer: userAns.answer, score: correct ? a.max_score : 0, auto_graded: true }
      }
      return a
    })
    db.attemptAnswers[String(id)] = list
    const scored = list.filter(a => a.score != null)
    const total = list.reduce((s, a) => s + (a.max_score ?? 1), 0)
    const pct = scored.length ? Math.round((scored.reduce((s, a) => s + a.score, 0) / total) * 100) : null
    att.score = pct != null ? String(pct) : null
    att.correct = scored.filter(a => a.score >= (a.max_score ?? 1)).length
    att.wrong = scored.length - att.correct
    att.skipped = list.length - scored.length
    const grading_complete = list.every(a => a.score != null)
    return { status: 200, json: {
      attempt_id: String(id), status: 'submitted', score: att.score,
      auto_submitted: false, answers: list,
    } }
  }

  // Attempt result
  if (method === 'GET' && p.match(/\/student\/quizzes\/attempts\/[^/]+\/result$/)) {
    const id = segId(p, '/student/quizzes/attempts/')
    const result = computeResult(String(id))
    if (!result) return { status: 404, json: { detail: 'attempt_not_found' } }
    return { status: 200, json: result }
  }

  // ── Fallback ──
  return { status: 200, json: {} }
}

// ═══ API call ═══════════════════════════════════════════════════════════

async function handle(method, path, body, makeForm, _isRetry = false) {
  await delay(DELAY)
  const token = getToken()
  if (!LOGIN_PATHS.includes(path) && !token) {
    _forceLogout()
    throw new Error('Session expired. Please log in again.')
  }
  const res = route(method, path, body)
  if (res.status === 401 && !_isRetry && !LOGIN_PATHS.includes(path)) {
    const refreshed = await _doRefresh()
    if (refreshed) return handle(method, path, body, makeForm, true)
    _forceLogout()
    throw new Error('Session expired. Please log in again.')
  }
  if (res.status >= 400) {
    const e = new Error(res.json && res.json.detail ? res.json.detail : `HTTP ${res.status}`)
    e.status = res.status
    throw e
  }
  if (makeForm) return res
  return res._raw !== undefined ? res._raw : res.json
}

export async function apiCall(method, path, body, _isRetry = false) {
  return handle(method, path, body, false, _isRetry)
}

export async function apiUpload(method, path, makeForm, _isRetry = false) {
  return handle(method, path, null, makeForm, _isRetry)
}

export async function refreshAccessToken() {
  return _doRefresh()
}

export { BASE, SIMULATION }
