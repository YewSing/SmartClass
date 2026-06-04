import { createContext, useContext, useReducer, useCallback, useEffect } from 'react'
import * as api from '../services/api'

const StudentContext = createContext(null)

const initialState = {
  isLoggedIn: false,
  currentView: 'home',
  prevView: 'home',
  navData: null,
  student: null,
  classes: [],
  attendanceSummary: null,
  attendanceGroups: [],
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
      return {
        ...state,
        prevView: state.currentView,
        currentView: action.payload.view,
        navData: action.payload.data ?? null,
      }
    case 'GO_BACK':
      return { ...state, currentView: state.prevView, navData: null }
    case 'SET_STUDENT':
      return { ...state, student: action.payload }
    case 'SET_CLASSES':
      return { ...state, classes: action.payload }
    case 'SET_ATTENDANCE_SUMMARY':
      return { ...state, attendanceSummary: action.payload }
    case 'SET_ATTENDANCE_GROUPS':
      return { ...state, attendanceGroups: action.payload }
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

export function StudentProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)

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
      const student = await api.getStudent()
      dispatch({ type: 'SET_STUDENT', payload: student })
      dispatch({ type: 'LOGIN' })
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: e.message })
      throw e
    }
  }, [])

  const logout = useCallback(async () => {
    await api.logout()
    dispatch({ type: 'LOGOUT' })
  }, [])

  useEffect(() => {
    const handle = () => { api.logout(); dispatch({ type: 'LOGOUT' }) }
    window.addEventListener('auth:expired', handle)
    return () => window.removeEventListener('auth:expired', handle)
  }, [])

  const loadClasses = useCallback(async () => {
    try {
      const classes = await api.getEnrolledClasses()
      dispatch({ type: 'SET_CLASSES', payload: classes })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  const loadAttendanceSummary = useCallback(async () => {
    try {
      const summary = await api.getAttendanceSummary()
      dispatch({ type: 'SET_ATTENDANCE_SUMMARY', payload: summary })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  const loadAttendanceGroups = useCallback(async () => {
    try {
      const groups = await api.getAttendanceGroups()
      dispatch({ type: 'SET_ATTENDANCE_GROUPS', payload: groups })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

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
    loadAttendanceSummary,
    loadAttendanceGroups,
  }

  return (
    <StudentContext.Provider value={value}>
      {children}
    </StudentContext.Provider>
  )
}

export function useStudent() {
  const ctx = useContext(StudentContext)
  if (!ctx) throw new Error('useStudent must be used inside StudentProvider')
  return ctx
}
