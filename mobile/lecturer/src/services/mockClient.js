// Simulation (offline) client for the Lecturer app.
// Fully stateful — every mutating call (approve/edit/delete/publish/score) persists
// in memory so the UI reflects real changes. All data seeded from mockData.js.
import AsyncStorage from '@react-native-async-storage/async-storage'

const SIMULATION = process.env.EXPO_PUBLIC_SIMULATION === '1'
const BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://10.0.2.2:8000'
const DELAY = 450

import {
  LECTURER, CURRENT_CLASS, CLASSES, SESSIONS, STUDENTS, QUIZZES,
  BREAKDOWN_ROWS, ANALYTICS_ATT_BARS, ANALYTICS_ATT_LABELS,
  ANALYTICS_PAR_BARS, ANALYTICS_PAR_LABELS, AT_RISK,
} from '../data/mockData'

const delay = (ms) => new Promise((r) => setTimeout(r, ms))
const pad = (n) => String(n).padStart(2, '0')
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

const enrolled = CURRENT_CLASS.enrolled ?? CURRENT_CLASS.students ?? 26
const questionBank = [
  // Draft questions (status 'draft' / 'approved')
  {
    id: 1, course_id: CURRENT_CLASS.code, type: 'mcq',
    question: 'What does SOLID stand for in object-oriented design?',
    options: ['Single, Open, Liskov, Interface, Dependency', 'Simple, Object, Local, Interface, Design', 'Solid, Open, Linked, Integrated, Dynamic', 'Standard, Object, Logic, Interface, Data'],
    correct_answer: 'Single, Open, Liskov, Interface, Dependency',
    suggested_answer: null, level: 'beginner', topic: 'SOLID principles', score: 1, status: 'draft',
  },
  {
    id: 2, course_id: CURRENT_CLASS.code, type: 'mcq',
    question: 'Which HTTP method is idempotent and used to retrieve a resource?',
    options: ['POST', 'GET', 'DELETE', 'PATCH'],
    correct_answer: 'GET', suggested_answer: null, level: 'beginner', topic: 'HTTP basics', score: 1, status: 'draft',
  },
  {
    id: 3, course_id: CURRENT_CLASS.code, type: 'short_answer',
    question: 'Explain the difference between an abstract class and an interface in Java.',
    options: [], correct_answer: null,
    suggested_answer: 'An abstract class can have implemented methods and state; an interface defines a contract. A class extends one abstract class but can implement many interfaces.',
    level: 'intermediate', topic: 'Java OOP', score: 2, status: 'draft',
  },
  {
    id: 4, course_id: CURRENT_CLASS.code, type: 'mcq',
    question: 'In React, what is the purpose of the useEffect hook?',
    options: ['To manage side effects in functional components', 'To style components', 'To create class components', 'To route between pages'],
    correct_answer: 'To manage side effects in functional components',
    suggested_answer: null, level: 'beginner', topic: 'React hooks', score: 1, status: 'draft',
  },
]
let nextQuestionId = questionBank.length + 1

// Published quizzes (student-facing)
const publishedQuizzes = QUIZZES.map((q, i) => ({
  id: q.id, course_id: CURRENT_CLASS.code, title: q.question ? `Quiz · ${q.topic || 'Course'}` : `Quiz ${i + 1}`,
  status: q.status, time_limit_minutes: q.timer ? Number(q.timer.replace('s', '')) / 60 || 30 : 30,
  opens_at: null, closes_at: null, attempts_allowed: 1, review_visible: true,
  question_count: q.options ? q.options.length : 0, created_at: `2025-05-${pad(20 - i)}T09:00:00`,
}))
let nextQuizId = publishedQuizzes.length + 1

// Draft quiz sets (created via save-as-draft / quick-add)
const draftQuizzes = []
let nextDraftQuizId = 1

// Student attempts
const attempts = [
  { attempt_id: 'a1', quiz_id: 'q1', student_id: 101, student_name: 'Ahmad Izzul Hakim', status: 'submitted', score: '72', correct: 18, wrong: 5, skipped: 2, total: 25, submitted_at: nowIso, auto_submitted: false, total_enrolled: enrolled },
  { attempt_id: 'a2', quiz_id: 'q1', student_id: 102, student_name: 'Siti Nurhaliza', status: 'submitted', score: '88', correct: 22, wrong: 2, skipped: 1, total: 25, submitted_at: nowIso, auto_submitted: false, total_enrolled: enrolled },
  { attempt_id: 'a3', quiz_id: 'q1', student_id: 103, student_name: 'Ali Farhan', status: 'started', score: null, correct: 0, wrong: 0, skipped: 0, total: 25, submitted_at: null, auto_submitted: false, total_enrolled: enrolled },
]
let nextAttemptId = attempts.length + 1

// Per-attempt answers (lecturer review + student result)
const attemptAnswers = {
  a1: [
    { question_id: 1, answer: 'GET', score: 1.0, max_score: 1.0, auto_graded: true, question: 'Which HTTP method is idempotent and used to retrieve a resource?', type: 'mcq', options: ['POST', 'GET', 'DELETE', 'PATCH'], correct_answer: 'GET', suggested_answer: null, learning_hint: null },
    { question_id: 2, answer: 'Single, Open, Liskov, Interface, Dependency', score: 1.0, max_score: 1.0, auto_graded: true, question: 'What does SOLID stand for in object-oriented design?', type: 'mcq', options: ['Single, Open, Liskov, Interface, Dependency', 'Simple, Object, Local, Interface, Design', 'Solid, Open, Linked, Integrated, Dynamic', 'Standard, Object, Logic, Interface, Data'], correct_answer: 'Single, Open, Liskov, Interface, Dependency', suggested_answer: null, learning_hint: null },
    { question_id: 3, answer: 'Abstraction lets you hide implementation details while showing only essential features.', score: null, max_score: 2.0, auto_graded: false, question: 'Explain the difference between an abstract class and an interface in Java.', type: 'short_answer', options: [], correct_answer: null, suggested_answer: 'An abstract class can have implemented methods and state; an interface defines a contract.', learning_hint: 'See Week 3 – Java OOP, Chapter 4, pages 12-15' },
  ],
  a2: [
    { question_id: 1, answer: 'GET', score: 1.0, max_score: 1.0, auto_graded: true, question: 'Which HTTP method is idempotent and used to retrieve a resource?', type: 'mcq', options: ['POST', 'GET', 'DELETE', 'PATCH'], correct_answer: 'GET', suggested_answer: null, learning_hint: null },
    { question_id: 2, answer: 'Simple, Object, Local, Interface, Design', score: 0.0, max_score: 1.0, auto_graded: true, question: 'What does SOLID stand for in object-oriented design?', type: 'mcq', options: ['Single, Open, Liskov, Interface, Dependency', 'Simple, Object, Local, Interface, Design', 'Solid, Open, Linked, Integrated, Dynamic', 'Standard, Object, Logic, Interface, Data'], correct_answer: 'Single, Open, Liskov, Interface, Dependency', suggested_answer: null, learning_hint: null },
    { question_id: 3, answer: 'Abstract class can have methods, interface cannot.', score: null, max_score: 2.0, auto_graded: false, question: 'Explain the difference between an abstract class and an interface in Java.', type: 'short_answer', options: [], correct_answer: null, suggested_answer: 'An abstract class can have implemented methods and state; an interface defines a contract.', learning_hint: 'See Week 3 – Java OOP, Chapter 4, pages 12-15' },
  ],
}

// Sessions (attendance)
const sessions = SESSIONS.map((s) => ({
  id: s.id, class_id: 1, class_code: CURRENT_CLASS.code, class_name: CURRENT_CLASS.name,
  status: s.open ? 'open' : 'closed',
  opened_at: s.open ? `2025-05-${pad(s.day)}T08:05:00` : `2025-05-${pad(s.day)}T08:05:00`,
  closed_at: s.open ? null : `2025-05-${pad(s.day)}T10:00:00`,
  class_date: `2025-05-${pad(s.day)}`,
  starts_at: `2025-05-${pad(s.day)}T08:00:00`,
  ends_at: `2025-05-${pad(s.day)}T10:00:00`,
  present: s.present, late: 0, excused: 0, absent: s.absent, not_recorded: enrolled - s.present - s.absent, unid: s.unid,
  time: s.open ? '08:05 AM' : '08:05 AM',
  moodle_sync_status: s.open ? null : 'synced',
  moodle_synced_at: s.open ? null : `2025-05-${pad(s.day)}T10:05:00`,
  moodle_sync_next_at: null, moodle_sync_error: null, moodle_conflicts: [],
}))

// Students
const students = STUDENTS.map((s, i) => ({
  id: i + 1, name: s.name, matric_no: s.id, face_enrolled: true,
}))

// Interaction session with live question + poll
const interactions = [
  {
    id: 1, occurrence_id: 1, class_code: CURRENT_CLASS.code, class_name: CURRENT_CLASS.name,
    status: 'open', opened_at: nowIso, closed_by: null, closed_at: null,
    current_poll: {
      id: 1, question: 'How confident are you about today\'s topic?',
      is_open: true,
      options: [
        { id: 1, option_text: 'Very confident', votes: 4 },
        { id: 2, option_text: 'Somewhat confident', votes: 7 },
        { id: 3, option_text: 'Not confident', votes: 2 },
      ],
    },
    live_question: {
      id: 1, question: 'Does anyone need clarification on dependency injection?',
      is_active: true, my_response: null,
      responses: [
        { id: 1, student_name: 'Ahmad Izzul Hakim', response: 'Yes, can you explain the constructor injection part again?', created_at: nowIso },
        { id: 2, student_name: 'Siti Nurhaliza', response: 'I understood it, thanks', created_at: nowIso },
      ],
    },
  },
  {
    id: 2, occurrence_id: 1, class_code: CURRENT_CLASS.code, class_name: CURRENT_CLASS.name,
    status: 'closed', opened_at: `2025-05-${pad(new Date().getDate()-7)}T10:00:00`, closed_at: nowIso,
    current_poll: {
      id: 2, question: 'Was the pace of today\'s class comfortable?',
      is_open: false,
      options: [
        { id: 1, option_text: 'Too fast', votes: 3 },
        { id: 2, option_text: 'Just right', votes: 9 },
        { id: 3, option_text: 'Too slow', votes: 1 },
      ],
    },
    live_question: {
      id: 2, question: 'Should we review the quiz answers before next class?',
      is_active: false,
      responses: [
        { id: 3, student_name: 'Ahmad Izzul Hakim', response: 'Yes please, especially Q4', created_at: nowIso },
        { id: 4, student_name: 'Siti Nurhaliza', response: 'Yes', created_at: nowIso },
        { id: 5, student_name: 'Ali Farhan', response: 'Maybe just the hard ones', created_at: nowIso },
      ],
    },
    reaction_counts: { understood: 6, confused: 2, pace_too_fast: 1 },
    questions: [
      { id: 10, text: 'Can we go over the SOLID principles again?', answered: true, anonymous: false, student_name: 'Ahmad Izzul Hakim' },
      { id: 11, text: 'Is the final exam cumulative?', answered: false, anonymous: true, student_name: null },
      { id: 12, text: 'What textbook do you recommend?', answered: true, anonymous: false, student_name: 'Siti Nurhaliza' },
    ],
    idu_distinct_students: 1,
  },
]

const flags = []
const roster = {}
const analytics = {
  sessions: SESSIONS.map((s, i) => {
    const total = enrolled
    const present = s.present
    const rate = Math.round((present / total) * 100)
    return {
      session_id: s.id,
      label: `Week ${6 - i}`,
      date: `2025-05-${pad(s.day)}`,
      present_count: present,
      absent_count: s.absent,
      total,
      rate,
      is_dangerous: rate < 80, // Dangerous attendance rate (<80% UM barring threshold)
    }
  }),
  at_risk_students: AT_RISK.map((r, i) => ({
    student_id: 'U2300' + (312 + i),
    matric_no: 'U2300' + (312 + i),
    name: r.name,
    present: 5,
    total: 9,
    rate: Number(r.pct.replace('%', '')) || 55,
    condition: i === 0 ? 'Attendance < 80%' : i === 1 ? 'Consecutive 2 absences' : 'Participation drop',
  })),
  enrolled_count: CURRENT_CLASS.enrolled,
  avg_attendance_rate: 78,
  sessions_held: SESSIONS.length,
}
const facePending = [
  {
    id: 1,
    student_user_id: 105,
    student_name: 'Ali Farhan',
    matric_no: 'U2300312',
    courses: ['WIA2005'],
    submitted_at: nowIso,
    submitted_anyway: false,
    check_reasons: ['face_mismatch'],
    face_score: 0.82,
    ocr_matric: 'U2300312',
    ocr_matric_confidence: 0.95,
    name_score: 0.88,
    ocr_lines: ['UNIVERSITI MALAYA', 'ALI FARHAN', 'U2300312'],
    quality_scores: { glare: false, blurry: false },
    images: [
      { id: 101, kind: 'selfie', position: 0, url: null },
      { id: 102, kind: 'selfie', position: 1, url: null },
      { id: 103, kind: 'card', position: 0, url: null },
    ],
  },
]

// ═══ Helpers ═════════════════════════════════════════════════════════════

function ensureRoster(sessionId) {
  if (!roster[sessionId]) {
    roster[sessionId] = students.map((s, i) => {
      const statuses = ['present', 'late', 'absent', 'not_recorded']
      const status = statuses[i % statuses.length]
      return {
        record_id: 1000 + i, student_id: s.id, matric_no: s.matric_no, name: s.name,
        status, detected_at: status === 'present' ? nowIso : null, overridden: false,
      }
    })
  }
  return roster[sessionId]
}

function segId(p, prefix) {
  const rest = p.slice(prefix.length)
  const first = rest.split('?')[0].split('/')[0]
  return first === '' ? null : first
}

// Find a question by id (draft bank)
function findQuestion(id) {
  return questionBank.find(q => String(q.id) === String(id))
}

// ═══ Route dispatcher ═══════════════════════════════════════════════════

function route(method, path, body) {
  const p = path.split('?')[0]

  // ── Auth ──
  if (method === 'POST' && p === '/auth/moodle-login') {
    return { status: 200, json: { user: { name: 'Dr. Tan Wei Liang', email: 'drtan.wl@um.edu.my', role: 'lecturer', id: 1 }, access_token: 'sim-access', refresh_token: 'sim-refresh' } }
  }
  if (method === 'POST' && p === '/auth/login') {
    const role = (body && body.email === 'admin@um.edu.my') ? 'admin' : 'lecturer'
    const tok = role === 'admin' ? 'sim-admin-token' : 'sim-access'
    return { status: 200, json: { user: { name: role === 'admin' ? 'Administrator' : 'Dr. Tan Wei Liang', email: body && body.email, role, id: role === 'admin' ? 9 : 1 }, access_token: tok, refresh_token: 'sim-refresh' } }
  }
  if (method === 'GET' && p === '/auth/me') {
    const isAdmin = _token === 'sim-admin-token'
    if (isAdmin) {
      return { status: 200, json: { id: 9, name: 'Administrator', email: 'admin@um.edu.my', role: 'admin', lecturer: null } }
    }
    return { status: 200, json: { id: 1, name: 'Dr. Tan Wei Liang', email: 'drtan.wl@um.edu.my', role: 'lecturer', lecturer: { staff_id: 'WL001', dept: 'Computer Science' } } }
  }

  // ── Classes ──
  if (method === 'GET' && p === '/classes') {
    return { status: 200, json: CLASSES.map((c, i) => ({
      id: i + 1, course_id: c.code, course_code: c.code, course_name: c.name,
      day_of_week: 'Mon', start_time: '10:00', end_time: '12:00',
      room: 'DK 6, BLI Building', type: 'lecture', label: 'Lec', enrolled_count: c.students,
    })) }
  }
  if (method === 'GET' && p.startsWith('/classes/') && p.endsWith('/students')) {
    return { status: 200, json: students.map((s, i) => ({ id: i + 1, name: s.name, matric_no: s.matric_no, face_enrolled: s.face_enrolled })) }
  }
  if (method === 'PUT' && p.match(/\/classes\/[^/]+\/schedule$/)) {
    return { status: 200, json: { day_of_week: body && body.day_of_week, start_time: body && body.start_time, end_time: body && body.end_time, room: body && body.room } }
  }

  // ── Sessions ──
  if (method === 'GET' && p === '/lecturer/sessions') {
    return { status: 200, json: sessions }
  }
  if (method === 'POST' && p === '/lecturer/sessions') {
    const s = { id: sessions.length + 1, class_id: body && body.occurrence_id, class_code: CURRENT_CLASS.code, class_name: CURRENT_CLASS.name, status: 'open', opened_at: nowIso, closed_at: null, class_date: todayIso, starts_at: nowIso, ends_at: null, present: 0, late: 0, excused: 0, absent: 0, not_recorded: enrolled, unid: 0, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), moodle_sync_status: null, moodle_synced_at: null, moodle_sync_next_at: null, moodle_sync_error: null, moodle_conflicts: [] }
    sessions.unshift(s)
    return { status: 200, json: s }
  }
  if (method === 'PUT' && p.match(/\/sessions\/[^/]+\/close$/)) {
    const id = segId(p, '/lecturer/sessions/')
    const s = sessions.find(x => String(x.id) === id)
    if (s) { s.status = 'closed'; s.closed_at = nowIso }
    return { status: 200, json: s || { id } }
  }
  if (method === 'POST' && p.match(/\/sessions\/[^/]+\/extend$/)) {
    const id = segId(p, '/lecturer/sessions/')
    const s = sessions.find(x => String(x.id) === id)
    return { status: 200, json: s || { id } }
  }
  if (method === 'POST' && p.match(/\/sessions\/[^/]+\/confirm$/)) {
    const id = segId(p, '/lecturer/sessions/')
    const s = sessions.find(x => String(x.id) === id)
    if (s) s.status = body && body.held ? 'closed' : 'not_held'
    return { status: 200, json: s || { id } }
  }
  if (method === 'POST' && p.match(/\/sessions\/[^/]+\/moodle-sync$/)) {
    const id = segId(p, '/lecturer/sessions/')
    const s = sessions.find(x => String(x.id) === id)
    if (s) { s.moodle_sync_status = 'synced'; s.moodle_synced_at = nowIso }
    return { status: 200, json: s || { id } }
  }
  if (method === 'POST' && p.match(/\/sessions\/[^/]+\/moodle-conflicts\/[^/]+$/)) {
    const id = segId(p, '/lecturer/sessions/')
    const s = sessions.find(x => String(x.id) === id)
    return { status: 200, json: s || { id } }
  }
  if (method === 'GET' && p.startsWith('/lecturer/sessions/') && p.endsWith('/attendance')) {
    const id = segId(p, '/lecturer/sessions/')
    return { status: 200, json: ensureRoster(id) }
  }

  // ── Flags ──
  if (method === 'GET' && p === '/lecturer/flags') {
    const qs = new URLSearchParams(path.split('?')[1] ?? '')
    const sessionId = qs.get('session_id')
    return { status: 200, json: flags.filter((f) => sessionId == null || String(f.session_id) === sessionId) }
  }
  if (method === 'POST' && p.match(/\/flags\/[^/]+\/confirm$/)) {
    const id = segId(p, '/lecturer/flags/')
    const f = flags.find((x) => String(x.id) === id)
    if (f) f.status = 'confirmed'
    return { status: 200, json: f || { id } }
  }
  if (method === 'POST' && p.match(/\/flags\/[^/]+\/reject$/)) {
    const id = segId(p, '/lecturer/flags/')
    const f = flags.find((x) => String(x.id) === id)
    if (f) f.status = 'rejected'
    return { status: 200, json: f || { id } }
  }

  // ── Override ──
  if (method === 'PUT' && (p.match(/\/attendance\/[^/]+\/override$/) || p.match(/\/sessions\/[^/]+\/attendance\/override$/))) {
    const sessionId = body && body.session_id
    const rList = sessionId ? ensureRoster(String(sessionId)) : []
    if (body && body.student_id) {
      const r = rList.find((x) => x.student_id === body.student_id || x.matric_no === body.student_id)
      if (r) { r.status = body.status; r.overridden = true; r.detected_at = nowIso }
    }
    return { status: 200, json: { record_id: body && body.record_id, student_id: body && body.student_id, status: body && body.status } }
  }

  // ── CSV export ──
  if (method === 'GET' && (p.match(/\/sessions\/[^/]+\/export/) || p.match(/\/occurrences\/[^/]+\/attendance\/export/))) {
    const header = 'id,name,matric_no,status,detected_at\n'
    const rows = students.map(s => `${s.id},${s.name},${s.matric_no},present,${nowIso}`).join('\n')
    return { status: 200, json: null, _raw: header + rows + '\n' }
  }

  // ── Analytics ──
  if (method === 'GET' && p === '/lecturer/analytics') {
    return { status: 200, json: analytics }
  }

  // ── Interaction ──
  if (method === 'GET' && p === '/lecturer/interactions/open') {
    return { status: 200, json: interactions.filter(i => i.status === 'open') }
  }
  if (method === 'GET' && p === '/lecturer/interactions') {
    return { status: 200, json: interactions }
  }
  if (method === 'GET' && p.match(/\/interactions\/[^/]+$/)) {
    const id = segId(p, '/lecturer/interactions/')
    const i = interactions.find((x) => String(x.id) === id)
    return { status: 200, json: i || { id, status: 'open', current_poll: null, live_question: null } }
  }
  if (method === 'POST' && p === '/lecturer/interactions') {
    return { status: 200, json: { id: interactions.length + 1 } }
  }
  if (method === 'POST' && p.match(/\/interactions\/[^/]+\/close$/)) {
    return { status: 200, json: {} }
  }
  if (method === 'POST' && p.match(/\/interactions\/[^/]+\/extend$/)) {
    return { status: 200, json: {} }
  }
  if (method === 'POST' && p.match(/\/interactions\/[^/]+\/polls$/)) {
    return { status: 200, json: { id: 2 } }
  }
  if (method === 'POST' && p.match(/\/interactions\/[^/]+\/polls\/[^/]+\/close$/)) {
    return { status: 200, json: {} }
  }
  if (method === 'GET' && p.match(/\/interactions\/[^/]+\/polls$/)) {
    const i = interactions.find((x) => String(x.id) === segId(p, '/lecturer/interactions/'))
    return { status: 200, json: i ? [i.current_poll].filter(Boolean) : [] }
  }
  if (method === 'GET' && p.match(/\/interactions\/[^/]+\/questions$/)) {
    const i = interactions.find((x) => String(x.id) === segId(p, '/lecturer/interactions/'))
    return { status: 200, json: i?.questions ?? [] }
  }
  if (method === 'POST' && p.match(/\/interactions\/[^/]+\/live-question$/)) {
    return { status: 200, json: {} }
  }
  if (method === 'GET' && p.match(/\/interactions\/[^/]+\/live-question$/)) {
    const i = interactions.find((x) => String(x.id) === segId(p, '/lecturer/interactions/'))
    return { status: 200, json: i ? i.live_question : { question: null, responses: [], is_active: false } }
  }
  if (method === 'POST' && p.match(/\/interactions\/[^/]+\/questions\/[^/]+\/answered$/)) {
    return { status: 200, json: {} }
  }
  if (method === 'GET' && p.match(/\/interactions\/[^/]+\/reactions$/)) {
    const i = interactions.find((x) => String(x.id) === segId(p, '/lecturer/interactions/'))
    const counts = i?.reaction_counts ?? {}
    return { status: 200, json: Object.entries(counts).map(([reaction, count]) => ({ reaction, count })) }
  }
  if (method === 'GET' && p.match(/\/interactions\/[^/]+\/idu$/)) {
    const i = interactions.find((x) => String(x.id) === segId(p, '/lecturer/interactions/'))
    return { status: 200, json: { distinct_students: i?.idu_distinct_students ?? 0 } }
  }

  // ── Face verification ──
  if (method === 'GET' && p === '/face-verification/pending') {
    // Face review is exclusively handled by administrators in simulation (not lecturer)
    const isAdmin = _token === 'sim-admin-token'
    return { status: 200, json: isAdmin ? facePending : [] }
  }
  if (method === 'POST' && p.match(/\/face-verification\/[^/]+\/approve$/)) {
    return { status: 200, json: {} }
  }
  if (method === 'POST' && p.match(/\/face-verification\/[^/]+\/reject$/)) {
    return { status: 200, json: {} }
  }

  // ── Admin ──
  if (method === 'GET' && p === '/admin/users') {
    return { status: 200, json: { items: [], total: 0, page: 1, limit: 50 } }
  }
  if (method === 'DELETE' && p.match(/\/admin\/users\/[^/]+$/)) {
    return { status: 200, json: {} }
  }
  if (method === 'POST' && p.match(/\/admin\/users\/[^/]+\/reactivate$/)) {
    return { status: 200, json: {} }
  }
  if (method === 'POST' && p === '/admin/users') {
    return { status: 200, json: { id: 9 } }
  }
  if (method === 'DELETE' && p.match(/\/admin\/students\/[^/]+\/face-data$/)) {
    return { status: 200, json: {} }
  }
  if (method === 'GET' && p === '/admin/audit-logs') {
    return { status: 200, json: { items: [], total: 0, page: 1, limit: 50 } }
  }
  if (method === 'GET' && p === '/admin/moodle/sync') {
    return { status: 200, json: { last_sync: null } }
  }
  if (method === 'POST' && p === '/admin/moodle/sync') {
    return { status: 200, json: { started: true } }
  }
  if (method === 'GET' && p === '/admin/devices') {
    return { status: 200, json: [] }
  }
  if (method === 'POST' && p === '/admin/devices') {
    return { status: 200, json: { id: 1 } }
  }
  if (method === 'POST' && p.match(/\/admin\/devices\/[^/]+\/regenerate-key$/)) {
    return { status: 200, json: { key: 'sim-device-key' } }
  }

  // ── AI Assistant ──
  if (method === 'GET' && p === '/lecturer/assistant/courses') {
    return { status: 200, json: CLASSES.map((c, i) => ({ course_id: c.code, code: c.code, name: c.name, indexed_materials: 3 })) }
  }
  if (method === 'GET' && p.match(/\/kb\/courses\/[^/]+\/materials$/)) {
    return { status: 200, json: [
      { id: 'm1', title: 'Week 1 – Introduction to Software Engineering', status: 'indexed', section: 'Chapter 1', chunks: 12 },
      { id: 'm2', title: 'Week 3 – SOLID Principles & Design Patterns', status: 'indexed', section: 'Chapter 4', chunks: 9 },
      { id: 'm3', title: 'Week 5 – Testing Strategies', status: 'indexed', section: 'Chapter 7', chunks: 7 },
    ] }
  }
  if (method === 'POST' && p.match(/\/kb\/courses\/[^/]+\/sync$/)) {
    return { status: 200, json: { started: true } }
  }
  if (method === 'GET' && p.match(/\/lecturer\/assistant\/trends\/[^/]+$/)) {
    return { status: 200, json: {
      most_asked_topics: [
        { topic: 'Dependency injection', students: 8 },
        { topic: 'SOLID principles', students: 6 },
        { topic: 'Unit testing', students: 5 },
      ],
      most_cited_materials: [
        { title: 'Week 3 – SOLID Principles & Design Patterns', students: 7 },
        { title: 'Week 1 – Introduction to Software Engineering', students: 5 },
      ],
      topics_materials_dont_cover: [
        { topic: 'Deployment to AWS', students: 4 },
      ],
    } }
  }
  if (method === 'GET' && p === '/lecturer/assistant/sessions') {
    return { status: 200, json: [] }
  }
  if (method === 'POST' && p === '/lecturer/assistant/sessions') {
    return { status: 200, json: { id: 1, course_id: body && body.course_id, title: 'New chat', created_at: nowIso, updated_at: nowIso } }
  }
  if (method === 'GET' && p.match(/\/lecturer\/assistant\/sessions\/[^/]+\/messages$/)) {
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
          'Here `EmailService` is injected into `UserController` via the constructor.\n\n' +
          'This is covered in **Week 3 – SOLID Principles & Design Patterns**, Chapter 4.',
        kind: 'chat', citations: [{ n: 1, title: 'Week 3 – SOLID Principles & Design Patterns', section: 'Chapter 4', page: 12 }], source_type: 'materials', created_at: nowIso,
      },
    ] }
  }
  if (method === 'POST' && p.match(/\/lecturer\/assistant\/sessions\/[^/]+\/messages$/)) {
    return { status: 200, json: { id: 99, role: 'assistant', content: 'This is a simulated reply — no backend is connected. In production this would answer from your course materials with citations.', kind: 'chat', citations: [], source_type: 'general', created_at: nowIso } }
  }
  if (method === 'GET' && p.match(/\/lecturer\/assistant\/before-class\/[^/]+$/)) {
    return { status: 200, json: {
      summary: 'Students most often ask about dependency injection and SOLID principles. Revisit Chapter 4 before next class.',
      materials: [{ title: 'Week 3 – SOLID Principles & Design Patterns', section: 'Chapter 4', pages: [12, 15, 18] }],
    } }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // QUIZ — CreateQuiz / QuizList / LiveResults / ResultsClosed flow
  // ═══════════════════════════════════════════════════════════════════════════

  // Draft questions for a course (CreateQuiz review panel)
  if (method === 'GET' && p === '/lecturer/quizzes/drafts') {
    const qs = new URLSearchParams(path.split('?')[1] ?? '')
    const quizId = qs.get('quiz_id')
    const unlinkedOnly = qs.get('unlinked_only') === 'true'
    let list = questionBank
    if (quizId != null) {
      // questions linked to a draft quiz set
      const dq = draftQuizzes.find(d => String(d.id) === quizId)
      list = dq ? dq.question_ids.map(id => findQuestion(id)).filter(Boolean) : []
    } else if (unlinkedOnly) {
      const linked = new Set(draftQuizzes.flatMap(d => d.question_ids))
      list = questionBank.filter(q => !linked.has(q.id))
    }
    return { status: 200, json: list }
  }

  // Edit a draft question
  if (method === 'PUT' && p.match(/\/quizzes\/questions\/[^/]+$/)) {
    const id = segId(p, '/lecturer/quizzes/questions/')
    const q = findQuestion(id)
    if (!q) return { status: 404, json: { detail: 'Question not found' } }
    if (body.question != null) q.question = body.question
    if (body.score != null) q.score = parseFloat(body.score)
    if (body.options != null) q.options = body.options
    if (body.correct_answer != null) q.correct_answer = body.correct_answer
    if (body.suggested_answer != null) q.suggested_answer = body.suggested_answer
    if (body.level != null) q.level = body.level
    if (body.topic != null) q.topic = body.topic
    return { status: 200, json: q }
  }

  // Approve (draft→approved) or revert (approved→draft) a question
  if (method === 'POST' && p.match(/\/quizzes\/questions\/[^/]+\/approve$/)) {
    const id = segId(p, '/lecturer/quizzes/questions/')
    const q = findQuestion(id)
    if (!q) return { status: 404, json: { detail: 'Question not found' } }
    q.status = q.status === 'approved' ? 'draft' : 'approved'
    return { status: 200, json: q }
  }

  // Delete a draft question
  if (method === 'DELETE' && p.match(/\/quizzes\/questions\/[^/]+$/)) {
    const id = segId(p, '/lecturer/quizzes/questions/')
    const idx = questionBank.findIndex(q => String(q.id) === String(id))
    if (idx !== -1) questionBank.splice(idx, 1)
    return { status: 200, json: {} }
  }

  // Publish draft questions as a quiz (CreateQuiz "Publish")
  if (method === 'POST' && p === '/lecturer/quizzes') {
    const { question_ids, course_ids, title, time_limit_minutes, opens_at, closes_at, attempts_allowed, review_visible } = body || {}
    const created = []
    const targets = course_ids && course_ids.length ? course_ids : [CURRENT_CLASS.code]
    for (const courseId of targets) {
      const quiz = {
        id: nextQuizId++, course_id: courseId,
        title: title || `Quiz · ${CURRENT_CLASS.code}`,
        time_limit_minutes, opens_at, closes_at, attempts_allowed, review_visible,
        question_count: (question_ids || []).length, status: 'published', created_at: nowIso,
      }
      publishedQuizzes.push(quiz)
      created.push({ id: quiz.id, course_id: courseId })
    }
    return { status: 200, json: created }
  }

  // Get one quiz (LiveResults, QuizList)
  if (method === 'GET' && p.match(/\/quizzes\/[^/]+$/)) {
    const id = segId(p, '/lecturer/quizzes/')
    const q = publishedQuizzes.find(x => String(x.id) === String(id)) || questionBank.find(q => String(q.id) === String(id))
    if (q) return { status: 200, json: q }
    return { status: 404, json: { detail: 'Quiz not found' } }
  }

  // All quizzes of a course (QuizList)
  if (method === 'GET' && p.match(/\/courses\/[^/]+\/quizzes$/)) {
    return { status: 200, json: [...publishedQuizzes, ...draftQuizzes.map(d => ({ ...d, status: 'draft' }))] }
  }

  // Questions of a quiz (LiveResults questions tab, CreateQuiz draft editing)
  if (method === 'GET' && p.match(/\/quizzes\/[^/]+\/questions$/)) {
    const id = segId(p, '/lecturer/quizzes/')
    const dq = draftQuizzes.find(d => String(d.id) === id)
    if (dq) {
      return { status: 200, json: dq.question_ids.map(qid => findQuestion(qid)).filter(Boolean) }
    }
    // Published quiz — return its questions (mock: reuse questionBank)
    const q = publishedQuizzes.find(x => String(x.id) === String(id))
    if (q) return { status: 200, json: questionBank.slice(0, q.question_count || 3) }
    return { status: 200, json: [] }
  }

  // Save a draft quiz set
  if (method === 'POST' && p === '/lecturer/quizzes/draft') {
    const { question_ids, title, time_limit_minutes, opens_at, closes_at, attempts_allowed, review_visible } = body || {}
    const dq = {
      id: nextDraftQuizId++, course_id: CURRENT_CLASS.code,
      title: title || `Draft quiz ${nextDraftQuizId}`,
      time_limit_minutes, opens_at, closes_at, attempts_allowed, review_visible,
      question_ids: question_ids || [], status: 'draft', created_at: nowIso,
    }
    draftQuizzes.push(dq)
    return { status: 200, json: { id: dq.id, course_id: dq.course_id } }
  }

  // Update a draft quiz's details
  if (method === 'PUT' && p.match(/\/quizzes\/[^/]+$/)) {
    const id = segId(p, '/lecturer/quizzes/')
    const dq = draftQuizzes.find(d => String(d.id) === id)
    if (dq) {
      if (body.title != null) dq.title = body.title
      if (body.question_ids != null) dq.question_ids = body.question_ids
      if (body.time_limit_minutes != null) dq.time_limit_minutes = body.time_limit_minutes
      if (body.opens_at != null) dq.opens_at = body.opens_at
      if (body.closes_at != null) dq.closes_at = body.closes_at
      if (body.attempts_allowed != null) dq.attempts_allowed = body.attempts_allowed
      if (body.review_visible != null) dq.review_visible = body.review_visible
      return { status: 200, json: dq }
    }
    const pq = publishedQuizzes.find(x => String(x.id) === id)
    if (pq) return { status: 200, json: pq }
    return { status: 404, json: { detail: 'Quiz not found' } }
  }

  // Publish a draft quiz set
  if (method === 'POST' && p.match(/\/quizzes\/[^/]+\/publish$/)) {
    const id = segId(p, '/lecturer/quizzes/')
    const dq = draftQuizzes.find(d => String(d.id) === id)
    if (!dq) return { status: 404, json: { detail: 'Draft not found' } }
    dq.status = 'published'
    const created = [{ id: dq.id, course_id: dq.course_id }]
    publishedQuizzes.push({ ...dq, status: 'published', id: nextQuizId++ })
    return { status: 200, json: created }
  }

  // Add a question manually
  if (method === 'POST' && p === '/lecturer/quizzes/questions') {
    const { course_id, type, question, options, correct_answer, suggested_answer, level, topic, score } = body || {}
    const q = {
      id: nextQuestionId++, course_id, type, question,
      options: options || [], correct_answer, suggested_answer,
      level: level || 'beginner', topic: topic || null,
      score: score != null ? parseFloat(score) : 1, status: 'draft',
    }
    questionBank.push(q)
    return { status: 200, json: { id: q.id } }
  }

  // Quick-add quiz (AI) — create draft + questions
  if (method === 'POST' && p.match(/\/courses\/[^/]+\/quizzes\/quick-add$/)) {
    const { prompt, material_ids, level } = body || {}
    const mcqCount = prompt.match(/(\d+)\s*mcq/i)?.[1] || 3
    const saCount = prompt.match(/(\d+)\s*short.?answer/i)?.[1] || 0
    const timeMatch = prompt.match(/duration\s*(\d+)/i)
    const daysMatch = prompt.match(/valid\s*(\d+)\s*days/i)
    const qList = []
    for (let i = 0; i < parseInt(mcqCount); i++) {
      qList.push({
        id: nextQuestionId++, course_id: CURRENT_CLASS.code, type: 'mcq',
        question: `Generated MCQ ${i + 1} about ${prompt.slice(0, 40)}`,
        options: ['Option A', 'Option B', 'Option C', 'Option D'],
        correct_answer: 'Option A', suggested_answer: null,
        level: level || 'beginner', topic: 'Generated', score: 1, status: 'draft',
      })
    }
    for (let i = 0; i < parseInt(saCount); i++) {
      qList.push({
        id: nextQuestionId++, course_id: CURRENT_CLASS.code, type: 'short_answer',
        question: `Generated short answer ${i + 1} about ${prompt.slice(0, 40)}`,
        options: [], correct_answer: null,
        suggested_answer: 'The ideal answer here.', level: level || 'beginner', topic: 'Generated', score: 2, status: 'draft',
      })
    }
    questionBank.push(...qList)
    const closesAt = daysMatch ? new Date(Date.now() + parseInt(daysMatch) * 86400000).toISOString() : null
    const dq = {
      id: nextDraftQuizId++, course_id: CURRENT_CLASS.code,
      title: `AI Quiz · ${new Date().toLocaleDateString()}`,
      time_limit_minutes: timeMatch ? parseInt(timeMatch[1]) : 15,
      opens_at: nowIso, closes_at: closesAt,
      attempts_allowed: 1, review_visible: true,
      question_ids: qList.map(q => q.id), status: 'draft', created_at: nowIso,
    }
    draftQuizzes.push(dq)
    return { status: 200, json: { id: dq.id, course_id: dq.course_id, time_limit_minutes: dq.time_limit_minutes, title: dq.title, closes_at: dq.closes_at } }
  }

  // Attempts for a quiz (LiveResults)
  if (method === 'GET' && p.match(/\/quizzes\/[^/]+\/attempts$/)) {
    return { status: 200, json: attempts }
  }

  // All answers for an attempt (ResultsClosed)
  if (method === 'GET' && p.match(/\/quizzes\/attempts\/[^/]+\/all-answers$/)) {
    const id = segId(p, '/lecturer/quizzes/attempts/')
    const list = attemptAnswers[String(id)] || []
    return { status: 200, json: list }
  }

  // Unscored short answers (ResultsClosed)
  if (method === 'GET' && p.match(/\/quizzes\/attempts\/[^/]+\/answers$/)) {
    const id = segId(p, '/lecturer/quizzes/attempts/')
    const list = (attemptAnswers[String(id)] || []).filter(a => a.auto_graded === false && a.score == null)
    return { status: 200, json: list }
  }

  // Score a short answer
  if (method === 'POST' && p.match(/\/quizzes\/attempts\/[^/]+\/answers\/[^/]+\/score$/)) {
    const aid = segId(p, '/lecturer/quizzes/attempts/')
    const ansId = segId(p, '/answers/') // not used, we match by answer position
    const { score } = body || {}
    const list = attemptAnswers[String(aid)] || []
    if (list.length > 0) {
      list[0].score = parseFloat(score)
      // recompute attempt score
      const att = attempts.find(a => a.attempt_id === String(aid))
      if (att) {
        const scored = list.filter(a => a.score != null)
        att.score = scored.length ? String(Math.round((scored.reduce((s, a) => s + a.score, 0) / list.reduce((s, a) => s + (a.max_score ?? 1), 0)) * 100)) : null
        att.grading_complete = list.every(a => a.score != null)
      }
    }
    return { status: 200, json: {} }
  }

  // AI-suggested score for a short answer
  if (method === 'POST' && p.match(/\/quizzes\/attempts\/[^/]+\/answers\/[^/]+\/suggest-score$/)) {
    return { status: 200, json: { suggested_score: 75, reasoning: 'Covers the key concepts but misses the interface distinction.' } }
  }

  // Student attempt result (shared endpoint)
  if (method === 'GET' && p.match(/\/student\/quizzes\/attempts\/[^/]+\/result$/)) {
    const id = segId(p, '/student/quizzes/attempts/')
    const list = attemptAnswers[String(id)] || []
    const att = attempts.find(a => a.attempt_id === String(id))
    const total = list.reduce((s, a) => s + (a.max_score ?? 1), 0)
    const scored = list.filter(a => a.score != null)
    const pct = scored.length ? Math.round((scored.reduce((s, a) => s + a.score, 0) / total) * 100) : null
    const grading_complete = list.every(a => a.score != null)
    return { status: 200, json: {
      attempt_id: String(id), status: att?.status ?? 'submitted',
      score: att?.score ?? (pct != null ? String(pct) : null),
      percentage_score: pct, raw_score: scored.reduce((s, a) => s + a.score, 0),
      max_score: total, auto_submitted: att?.auto_submitted ?? false,
      grading_complete, student_score_visible: grading_complete, review_visible: true,
      answers: list,
    } }
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

export async function apiCallRaw(method, path, _isRetry = false) {
  return handle(method, path, null, true, _isRetry)
}

export async function refreshAccessToken() {
  return _doRefresh()
}

export { BASE, SIMULATION }
