import {
  STUDENT, ENROLLED_CLASSES, ATT_SUMMARY, ATTENDANCE_GROUPS,
  PART_SUMMARY, PARTICIPATION_GROUPS, SESSION_PERFS,
} from '../data/mockData'

// All functions return Promises to mirror real API calls.
// Swap these implementations for fetch() calls when the backend is ready.

export const login = async (email, password) => {
  await delay(400)
  if (email && password) return { user: STUDENT }
  throw new Error('Invalid credentials')
}

export const getStudent = async () => {
  await delay(200)
  return STUDENT
}

export const getEnrolledClasses = async () => {
  await delay(300)
  return ENROLLED_CLASSES
}

export const getAttendanceSummary = async () => {
  await delay(200)
  return ATT_SUMMARY
}

export const getAttendanceGroups = async () => {
  await delay(300)
  return ATTENDANCE_GROUPS
}

export const getParticipationSummary = async () => {
  await delay(200)
  return PART_SUMMARY
}

export const getParticipationGroups = async () => {
  await delay(300)
  return PARTICIPATION_GROUPS
}

export const getSessionPerf = async (perfKey) => {
  await delay(200)
  return SESSION_PERFS[perfKey] ?? null
}

export const submitReport = async (sessionId, reason, notes) => {
  await delay(400)
  return { refNo: `RPT-${Date.now()}`, status: 'pending' }
}

export const sendPasswordReset = async (email) => {
  await delay(400)
  return { success: true }
}

export const logout = async () => {
  await delay(200)
  return { success: true }
}

const delay = (ms) => new Promise((res) => setTimeout(res, ms))
