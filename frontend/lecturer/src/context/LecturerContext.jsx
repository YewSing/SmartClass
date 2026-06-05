import { createContext, useContext, useReducer, useCallback, useEffect, useRef } from 'react'
import * as api from '../services/api'

const LecturerContext = createContext(null)

const initialState = {
  isLoggedIn: false,
  currentView: 'dashboard',
  prevView: 'dashboard',
  navData: null,
  lecturer: null,
  classes: [],
  allClasses: [],
  sessions: [],
  selectedSession: null,
  students: [],
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
      return { ...state, isLoggedIn: true, loading: false, error: null }
    case 'LOGOUT':
      return { ...initialState }
    case 'SET_VIEW':
      return { ...state, prevView: state.currentView, currentView: action.payload.view, navData: action.payload.data ?? null }
    case 'GO_BACK':
      return { ...state, currentView: state.prevView, navData: null }
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
    case 'UPDATE_SESSION':
      return {
        ...state,
        sessions: state.sessions.map(s => s.id === action.payload.id ? action.payload : s),
        selectedSession: state.selectedSession?.id === action.payload.id ? action.payload : state.selectedSession,
      }
    case 'SET_SELECTED_SESSION':
      return { ...state, selectedSession: action.payload }
    case 'SET_STUDENTS':
      return { ...state, students: action.payload }
    case 'SET_ANALYTICS':
      return { ...state, analytics: action.payload, analyticsLoading: false }
    case 'SET_ANALYTICS_LOADING':
      return { ...state, analyticsLoading: action.payload }
    case 'UPDATE_STUDENT':
      return {
        ...state,
        students: state.students.map(s =>
          s.recordId === action.payload.record_id
            ? { ...s, status: action.payload.status, overridden: true }
            : s
        ),
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
  const [state, dispatch] = useReducer(reducer, initialState)
  const wsRef = useRef(null)

  const navigate   = useCallback((view, data = null) => dispatch({ type: 'SET_VIEW', payload: { view, data } }), [])
  const goBack     = useCallback(() => dispatch({ type: 'GO_BACK' }), [])
  const openModal  = useCallback((type, data) => dispatch({ type: 'OPEN_MODAL', payload: { type, data } }), [])
  const closeModal = useCallback(() => dispatch({ type: 'CLOSE_MODAL' }), [])
  const showToast  = useCallback((message, variant = 'info') =>
    dispatch({ type: 'SHOW_TOAST', payload: { message, variant } }), [])

  const login = useCallback(async (email, password) => {
    dispatch({ type: 'SET_LOADING', payload: true })
    try {
      await api.login(email, password)
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

  const loadStudents = useCallback(async (sessionId) => {
    try {
      const students = await api.getStudents(sessionId)
      dispatch({ type: 'SET_STUDENTS', payload: students })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  const overrideStudent = useCallback(async (recordId, newStatus) => {
    try {
      await api.overrideAttendance(recordId, newStatus)
      dispatch({ type: 'UPDATE_STUDENT', payload: { record_id: recordId, status: newStatus } })
      showToast(`Marked ${newStatus}`, 'success')
    } catch (e) { showToast(e.message, 'error'); throw e }
  }, [showToast])

  const selectSession = useCallback((session) => {
    dispatch({ type: 'SET_SELECTED_SESSION', payload: session })
  }, [])

  const loadAnalytics = useCallback(async (occurrenceId) => {
    dispatch({ type: 'SET_ANALYTICS_LOADING', payload: true })
    try {
      const data = await api.getAnalytics(occurrenceId)
      dispatch({ type: 'SET_ANALYTICS', payload: data })
    } catch (e) {
      dispatch({ type: 'SET_ANALYTICS_LOADING', payload: false })
      showToast(e.message, 'error')
    }
  }, [showToast])

  useEffect(() => {
    const handle = () => {
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
      api.logout()
      dispatch({ type: 'LOGOUT' })
    }
    window.addEventListener('auth:expired', handle)
    return () => window.removeEventListener('auth:expired', handle)
  }, [])

  // WebSocket: connect when an open session exists
  useEffect(() => {
    const openSession = state.sessions.find(s => s.open)
    if (!openSession || !state.isLoggedIn) {
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
      return
    }
    if (wsRef.current && wsRef.current._sessionId === openSession.id) return
    if (wsRef.current) wsRef.current.close()

    const token = localStorage.getItem('token')
    const ws = new WebSocket(`ws://localhost:8000/ws/sessions/${openSession.id}?token=${token}`)
    ws._sessionId = openSession.id

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.event === 'attendance_update' || data.event === 'attendance_override') {
        if (data.student) dispatch({ type: 'UPDATE_STUDENT', payload: data.student })
        if (data.counts) {
          dispatch({
            type: 'UPDATE_SESSION',
            payload: { ...openSession, present: data.counts.present ?? openSession.present, absent: data.counts.absent ?? openSession.absent, unid: data.counts.unidentified ?? openSession.unid },
          })
        }
      }
    }
    ws.onerror = () => showToast('Live updates disconnected', 'error')
    wsRef.current = ws
  }, [state.sessions, state.isLoggedIn, showToast])

  const value = {
    state,
    dispatch,
    navigate,
    goBack,
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
    loadStudents,
    overrideStudent,
    selectSession,
    loadAnalytics,
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
