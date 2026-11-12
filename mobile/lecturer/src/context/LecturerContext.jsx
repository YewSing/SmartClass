import { createContext, useContext, useReducer, useCallback, useEffect, useRef } from 'react'
import * as api from '../services/api'
import { getToken, getRefreshToken, onAuthExpired, BASE } from '../services/client'
import { restoreSession } from '../services/session'
import { hhmm, statusLabel, followsLive, flagAlertText, upsertFlag } from '../services/attendance'

const LecturerContext = createContext(null)

const COUNT_KEYS = ['present', 'late', 'excused', 'absent', 'not_recorded', 'unid']
const pickCounts = (counts) =>
  Object.fromEntries(COUNT_KEYS.filter(k => counts?.[k] != null).map(k => [k, counts[k]]))

const initialState = {
  isLoggedIn: false,
  restoring: false,   // checking a stored session at start-up (shows a spinner, not Login)
  lecturer: null,
  classes: [],
  allClasses: [],
  sessions: [],
  selectedSession: null,
  students: [],
  flags: [],
  analytics: null,
  analyticsLoading: false,
  modal: null,
  toasts: [],
  loading: false,
  error: null,
}

function reducer(state, action) {
  switch (action.type) {
    case 'LOGIN':
      return { ...state, isLoggedIn: true, restoring: false, loading: false, error: null }
    case 'LOGOUT':
      return { ...initialState }
    case 'RESTORE_DONE':
      return { ...state, restoring: false }
    case 'SET_LECTURER':
      return { ...state, lecturer: action.payload }
    case 'SET_CLASSES':
      return { ...state, classes: action.payload }
    case 'SET_ALL_CLASSES':
      return { ...state, allClasses: action.payload }
    case 'SET_SESSIONS':
      return { ...state, sessions: action.payload }
    case 'ADD_SESSION': {
      const without = state.sessions.filter(s => !(s.class_id === action.payload.class_id && s.open))
      return { ...state, sessions: [action.payload, ...without] }
    }
    case 'UPDATE_SESSION': {
      const known = state.sessions.some(s => s.id === action.payload.id)
      return {
        ...state,
        sessions: known
          ? state.sessions.map(s => s.id === action.payload.id ? action.payload : s)
          : [action.payload, ...state.sessions],
        selectedSession: state.selectedSession?.id === action.payload.id ? action.payload : state.selectedSession,
      }
    }
    case 'PATCH_SESSION': {
      // payload: { id, ...fields } — e.g. live counts from the websocket
      const { id, ...patch } = action.payload
      return {
        ...state,
        sessions: state.sessions.map(s => s.id === id ? { ...s, ...patch } : s),
        selectedSession: state.selectedSession?.id === id ? { ...state.selectedSession, ...patch } : state.selectedSession,
      }
    }
    case 'SET_SELECTED_SESSION':
      return { ...state, selectedSession: action.payload, students: [], flags: [] }
    case 'SET_STUDENTS':
      if (action.sessionId != null && action.sessionId !== state.selectedSession?.id) return state
      return { ...state, students: action.payload }
    case 'SET_FLAGS':
      if (action.sessionId != null && action.sessionId !== state.selectedSession?.id) return state
      return { ...state, flags: action.payload }
    case 'UPSERT_FLAG':
      if (action.payload.session_id !== state.selectedSession?.id) return state
      return { ...state, flags: upsertFlag(state.flags, action.payload) }
    case 'SET_ANALYTICS':
      return { ...state, analytics: action.payload, analyticsLoading: false }
    case 'SET_ANALYTICS_LOADING':
      return { ...state, analyticsLoading: action.payload }
    case 'UPDATE_STUDENT': {
      // payload: { session_id, record_id, student_id, status, detected_at?, overridden }
      // Only the roster on screen changes; an update for another session is ignored.
      const p = action.payload
      if (p.session_id != null && p.session_id !== state.selectedSession?.id) return state
      const students = state.students.map(s => {
        const byRecordId = p.record_id != null && s.recordId === p.record_id
        const byStudentId = p.student_id != null && s.studentId === p.student_id
        if (!byRecordId && !byStudentId) return s
        return {
          ...s,
          recordId: p.record_id ?? s.recordId,
          status: p.status,
          arrivedAt: p.detected_at ? hhmm(p.detected_at) : s.arrivedAt,
          overridden: s.overridden || Boolean(p.overridden),
        }
      })
      return { ...state, students }
    }
    case 'SET_CLASS_SCHEDULE':
      return {
        ...state,
        allClasses: state.allClasses.map(c => c.id === action.payload.id ? { ...c, ...action.payload } : c),
        classes: state.classes.map(c => c.id === action.payload.id ? { ...c, ...action.payload } : c),
      }
    case 'OPEN_MODAL':
      return { ...state, modal: action.payload }
    case 'CLOSE_MODAL':
      return { ...state, modal: null }
    case 'SHOW_TOAST':
      return { ...state, toasts: [...state.toasts, { id: Date.now(), ...action.payload }] }
    case 'DISMISS_TOAST':
      return { ...state, toasts: state.toasts.filter(t => t.id !== action.payload) }
    case 'SET_LOADING':
      return { ...state, loading: action.payload }
    case 'SET_ERROR':
      return { ...state, error: action.payload, loading: false }
    default:
      return state
  }
}

export function LecturerProvider({ children }) {
  // initStorage() has run (App.js), so a stored session is known before the first render
  const [state, dispatch] = useReducer(reducer, initialState,
    s => ({ ...s, restoring: !!(getToken() || getRefreshToken()) }))
  const wsRef = useRef(null)

  // Stay signed in across reloads and restarts: load /auth/me with the stored token
  // (client.js refreshes it on a 401) instead of always showing Login.
  useEffect(() => {
    let cancelled = false
    restoreSession({ hasStoredSession: !!(getToken() || getRefreshToken()), fetchMe: api.getLecturer })
      .then(({ user, signOut }) => {
        if (cancelled) return
        if (user) {
          dispatch({ type: 'SET_LECTURER', payload: user })
          dispatch({ type: 'LOGIN' })
          return
        }
        if (signOut) api.logout()
        dispatch({ type: 'RESTORE_DONE' })
      })
    return () => { cancelled = true }
  }, [])

  const openModal  = useCallback((type, data) => dispatch({ type: 'OPEN_MODAL', payload: { type, data } }), [])
  const closeModal = useCallback(() => dispatch({ type: 'CLOSE_MODAL' }), [])
  const showToast  = useCallback((message, variant = 'info') =>
    dispatch({ type: 'SHOW_TOAST', payload: { message, variant } }), [])

  const login = useCallback(async (identifier, password, options) => {
    dispatch({ type: 'SET_LOADING', payload: true })
    try {
      await api.login(identifier, password, options)
      const lecturer = await api.getLecturer()
      dispatch({ type: 'SET_LECTURER', payload: lecturer })
      dispatch({ type: 'LOGIN' })
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: e.message })
      throw e
    }
  }, [])

  const logout = useCallback(async () => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
    await api.logout()
    dispatch({ type: 'LOGOUT' })
  }, [])

  const loadClasses = useCallback(async () => {
    try {
      const classes = await api.getClasses()
      dispatch({ type: 'SET_CLASSES', payload: classes })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  const loadAllClasses = useCallback(async () => {
    try {
      const classes = await api.getLecturerAllClasses()
      dispatch({ type: 'SET_ALL_CLASSES', payload: classes })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  const loadSessions = useCallback(async () => {
    try {
      const sessions = await api.getSessions()
      dispatch({ type: 'SET_SESSIONS', payload: sessions })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  const doOpenSession = useCallback(async (classId) => {
    try {
      const session = await api.openSession(classId)
      dispatch({ type: 'ADD_SESSION', payload: session })
      return session
    } catch (e) { showToast(e.message, 'error'); throw e }
  }, [showToast])

  const doCloseSession = useCallback(async (sessionId) => {
    try {
      const session = await api.closeSession(sessionId)
      dispatch({ type: 'UPDATE_SESSION', payload: session })
      return session
    } catch (e) { showToast(e.message, 'error'); throw e }
  }, [showToast])

  // Runs a call that returns the updated session, keeps it in state and shows `done` (FR-312–FR-320)
  const sessionAction = useCallback(async (call, done) => {
    try {
      const session = await call()
      dispatch({ type: 'UPDATE_SESSION', payload: session })
      if (done) showToast(done, 'success')
      return session
    } catch (e) { showToast(e.message, 'error'); throw e }
  }, [showToast])

  const doExtendSession = useCallback((sessionId, minutes) =>
    sessionAction(() => api.extendSession(sessionId, minutes), `Extended by ${minutes} min`), [sessionAction])

  const doConfirmSession = useCallback((sessionId, held) =>
    sessionAction(() => api.confirmSession(sessionId, held),
      held ? 'Marked as held; anyone not recorded is Absent' : 'Marked as not held'), [sessionAction])

  const doRetrySync = useCallback((sessionId) =>
    sessionAction(() => api.retryMoodleSync(sessionId), null), [sessionAction])

  const doResolveConflict = useCallback((sessionId, recordId, keep) =>
    sessionAction(() => api.resolveMoodleConflict(sessionId, recordId, keep),
      keep === 'moodle' ? "Took SPeCTRUM's value" : "Kept SmartClass's value"), [sessionAction])

  const doSetWeeklySchedule = useCallback(async (classId, slot) => {
    try {
      const saved = await api.setWeeklySchedule(classId, slot)
      dispatch({ type: 'SET_CLASS_SCHEDULE', payload: { id: classId, ...saved } })
      showToast(saved.day_of_week ? 'Weekly schedule saved' : 'Weekly schedule cleared', 'success')
      return saved
    } catch (e) { showToast(e.message, 'error'); throw e }
  }, [showToast])

  const loadStudents = useCallback(async (sessionId, { sessionOpen = false } = {}) => {
    try {
      const students = await api.getStudents(sessionId, { sessionOpen })
      dispatch({ type: 'SET_STUDENTS', payload: students, sessionId })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  // The session's "Says they're here" flags (FR-318, FR-319)
  const loadFlags = useCallback(async (sessionId) => {
    try {
      const flags = await api.getSessionFlags(sessionId)
      dispatch({ type: 'SET_FLAGS', payload: flags, sessionId })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  const doConfirmFlag = useCallback(async (flag) => {
    try {
      const saved = await api.confirmFlag(flag.id)
      dispatch({ type: 'UPSERT_FLAG', payload: saved })
      showToast(`Confirmed ${flag.name}`, 'success')
      return saved
    } catch (e) {
      showToast(e.message, 'error')
      if (state.selectedSession?.id) loadFlags(state.selectedSession.id)
      throw e
    }
  }, [showToast, loadFlags, state.selectedSession])

  const doRejectFlag = useCallback(async (flag, reason) => {
    try {
      const saved = await api.rejectFlag(flag.id, reason)
      dispatch({ type: 'UPSERT_FLAG', payload: saved })
      showToast(`Rejected ${flag.name}'s flag`, 'success')
      return saved
    } catch (e) {
      showToast(e.message, 'error')
      if (state.selectedSession?.id) loadFlags(state.selectedSession.id)
      throw e
    }
  }, [showToast, loadFlags, state.selectedSession])

  // Any of the four statuses with an optional reason (FR-305)
  const overrideStudent = useCallback(async (recordId, newStatus, studentId, reason) => {
    const sessionId = state.selectedSession?.id
    try {
      const result = await api.overrideAttendance(recordId, newStatus, sessionId, studentId, reason)
      dispatch({
        type: 'UPDATE_STUDENT',
        payload: { session_id: sessionId, record_id: result.record_id, student_id: result.student_id,
                   status: result.status, overridden: true },
      })
      showToast(`Marked ${statusLabel(newStatus)}`, 'success')
      // An override on a closed class re-queues the Moodle sync (FR-312)
      if (state.selectedSession && !state.selectedSession.open) {
        api.getSessions()
          .then(list => { const s = list.find(x => x.id === sessionId); if (s) dispatch({ type: 'UPDATE_SESSION', payload: s }) })
          .catch(() => {})
      }
    } catch (e) { showToast(e.message, 'error'); throw e }
  }, [showToast, state.selectedSession])

  const selectSession = useCallback((session) => {
    dispatch({ type: 'SET_SELECTED_SESSION', payload: session })
  }, [])

  const loadAnalytics = useCallback(async (occurrenceId, dateParams = {}) => {
    dispatch({ type: 'SET_ANALYTICS_LOADING', payload: true })
    try {
      const data = await api.getAnalytics(occurrenceId, dateParams)
      dispatch({ type: 'SET_ANALYTICS', payload: data })
    } catch (e) {
      dispatch({ type: 'SET_ANALYTICS_LOADING', payload: false })
      showToast(e.message, 'error')
    }
  }, [showToast])

  const exportCsv = useCallback(async ({ scope, id, filename, dateParams = {} }) => {
    try {
      const message = scope === 'session'
        ? await api.exportSessionCsv(id, filename)
        : await api.exportOccurrenceCsv(id, filename, dateParams)
      if (message) showToast(message, 'success')
    } catch (e) {
      showToast(e.message ?? 'Export failed', 'error')
      throw e
    }
  }, [showToast])

  // Listen for auth expiry from client.js
  useEffect(() => {
    const cleanup = onAuthExpired(() => {
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
      api.logout()
      dispatch({ type: 'LOGOUT' })
    })
    return cleanup
  }, [])

  // WebSocket: follow the session on screen while it is open or still on its way to SPeCTRUM
  // (its sync status arrives as a `moodle_sync` event, T38b), else the first open one
  const selectedOpenId = followsLive(state.selectedSession) ? state.selectedSession.id : null
  const liveSessionId = selectedOpenId ?? state.sessions.find(s => s.open)?.id ?? null
  const selectedIdRef = useRef(null)
  selectedIdRef.current = state.selectedSession?.id ?? null

  useEffect(() => {
    if (!liveSessionId || !state.isLoggedIn) {
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
      return
    }
    if (wsRef.current && wsRef.current._sessionId === liveSessionId) return
    if (wsRef.current) wsRef.current.close()

    const sessionId = liveSessionId
    const token = getToken()
    const wsUrl = BASE.replace(/^http/, 'ws')
    const ws = new WebSocket(`${wsUrl}/ws/sessions/${sessionId}?token=${token}`)
    ws._sessionId = sessionId

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.event === 'attendance_update' || data.event === 'attendance_override') {
        if (data.student) {
          dispatch({
            type: 'UPDATE_STUDENT',
            payload: {
              session_id: sessionId,
              record_id: data.student.record_id,
              student_id: data.student.id,
              status: data.student.status,
              detected_at: data.student.detected_at,
              overridden: data.event === 'attendance_override',
            },
          })
        }
        if (data.counts) {
          dispatch({ type: 'PATCH_SESSION', payload: { id: sessionId, ...pickCounts(data.counts) } })
        }
        if (data.moodle_sync_status) {   // an override on a closed class re-queues the sync (FR-312)
          dispatch({ type: 'PATCH_SESSION', payload: { id: sessionId, moodle_sync_status: data.moodle_sync_status } })
        }
        // A face matched after an unidentified entry was resolved: the event has counts only
        if (!data.student && selectedIdRef.current === sessionId) {
          api.getStudents(sessionId, { sessionOpen: true })
            .then(list => dispatch({ type: 'SET_STUDENTS', payload: list, sessionId }))
            .catch(() => {})
        }
      }
      if (data.event === 'session_closed') {
        // Ended by the lecturer (maybe on another device) or by the schedule. Sent after the
        // close commits, so a re-read already sees it closed.
        const status = data.status ?? 'closed'
        dispatch({ type: 'PATCH_SESSION', payload: { id: sessionId, status, open: false, ...pickCounts(data.counts) } })
        rereadSession(sessionId)
        if (selectedIdRef.current === sessionId) {
          api.getStudents(sessionId, { sessionOpen: false })
            .then(list => dispatch({ type: 'SET_STUDENTS', payload: list, sessionId }))
            .catch(() => {})
        }
      }
      if (data.event === 'moodle_sync') {
        // The background sync finished (synced / failed / conflict): show it without Retry, then
        // re-read for the conflict list and the error text
        dispatch({ type: 'PATCH_SESSION', payload: {
          id: sessionId,
          moodle_sync_status: data.moodle_sync_status,
          moodle_synced_at: data.moodle_synced_at ?? null,
          moodle_sync_next_at: data.moodle_sync_next_at ?? null,
          moodle_sync_error: data.moodle_sync_error ?? null,
        } })
        rereadSession(sessionId)
      }
      if (data.event === 'attendance_flagged' && data.flag) {
        showToast(flagAlertText(data.flag), 'info')
        dispatch({ type: 'UPSERT_FLAG', payload: data.flag })
      }
      if (data.event === 'attendance_flag_resolved' && data.flag) {
        dispatch({ type: 'UPSERT_FLAG', payload: data.flag })   // the lecturer did it
      }
      if (data.event === 'attendance_alert' && data.type === 'low_attendance') {
        showToast(
          `Low attendance — only ${Math.round(data.rate * 100)}% present (${data.present}/${data.enrolled} students)`,
          'error'
        )
      }
    }
    function rereadSession(id) {
      api.getSessions().then(list => {
        const s = list.find(x => x.id === id)
        if (s) dispatch({ type: 'UPDATE_SESSION', payload: s })
      }).catch(() => {})
    }
    // An event sent before this socket connected (e.g. a quick sync after an override) is
    // caught by one re-read once it is open
    ws.onopen = () => rereadSession(sessionId)
    ws.onerror = () => showToast('Live updates disconnected', 'error')
    wsRef.current = ws
  }, [liveSessionId, state.isLoggedIn, showToast])

  const value = {
    state,
    dispatch,
    openModal,
    closeModal,
    showToast,
    login,
    logout,
    loadClasses,
    loadAllClasses,
    loadSessions,
    doOpenSession,
    doCloseSession,
    doExtendSession,
    doConfirmSession,
    doRetrySync,
    doResolveConflict,
    doSetWeeklySchedule,
    loadStudents,
    loadFlags,
    doConfirmFlag,
    doRejectFlag,
    overrideStudent,
    selectSession,
    loadAnalytics,
    exportCsv,
  }

  return (
    <LecturerContext.Provider value={value}>
      {children}
    </LecturerContext.Provider>
  )
}

export function useLecturer() {
  const ctx = useContext(LecturerContext)
  if (!ctx) throw new Error('useLecturer must be used inside LecturerProvider')
  return ctx
}
