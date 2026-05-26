import {
  LECTURER, CURRENT_CLASS, SESSIONS, STUDENTS, QUIZZES,
  BREAKDOWN_ROWS, SENSORS, ANALYTICS_ATT_BARS, ANALYTICS_ATT_LABELS,
  ANALYTICS_PAR_BARS, ANALYTICS_PAR_LABELS, AT_RISK, CLASSES,
} from '../data/mockData'

// All functions return Promises to mirror real API calls.
// Swap these implementations for fetch() calls when the backend is ready.

export const login = async (email, password) => {
  await delay(400)
  if (email && password) return { user: LECTURER }
  throw new Error('Invalid credentials')
}

export const getLecturer = async () => {
  await delay(200)
  return LECTURER
}

export const getCurrentClass = async () => {
  await delay(200)
  return CURRENT_CLASS
}

export const getClasses = async () => {
  await delay(200)
  return CLASSES
}

export const getSessions = async () => {
  await delay(300)
  return SESSIONS
}

export const getStudents = async (sessionId) => {
  await delay(300)
  return STUDENTS
}

export const getQuizzes = async (sessionId) => {
  await delay(300)
  return QUIZZES
}

export const createQuiz = async (data) => {
  await delay(400)
  return { id: `q${Date.now()}`, ...data, status: 'draft' }
}

export const pushQuiz = async (quizId) => {
  await delay(300)
  return { success: true }
}

export const closeQuiz = async (quizId) => {
  await delay(300)
  return { success: true }
}

export const getBreakdown = async (quizId) => {
  await delay(300)
  return BREAKDOWN_ROWS
}

export const getSensors = async () => {
  await delay(200)
  return SENSORS
}

export const setActuatorOverride = async (device, mode, state, temp) => {
  await delay(300)
  return { success: true }
}

export const toggleSession = async (open) => {
  await delay(300)
  return { open }
}

export const overrideAttendance = async (studentId, sessionId, status) => {
  await delay(300)
  return { success: true }
}

export const resetConfusion = async (sessionId) => {
  await delay(300)
  return { success: true }
}

export const exportReport = async (type, format) => {
  await delay(500)
  return { url: '#' }
}

export const changePassword = async (current, next) => {
  await delay(400)
  return { success: true }
}

export const logout = async () => {
  await delay(200)
  return { success: true }
}

const delay = (ms) => new Promise((res) => setTimeout(res, ms))
