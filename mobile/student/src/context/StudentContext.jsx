import { createContext, useContext, useReducer, useCallback, useEffect, useRef } from 'react'
import { AppState } from 'react-native'
import * as api from '../services/api'
import { onAuthExpired, getToken, refreshAccessToken, BASE } from '../services/client'
import { connectStudentLive } from '../services/live'
import { recordedBannerText } from '../services/attendance'
import { connectNotificationsLive } from '../services/notificationsLive'
import { feedReducer, initialFeed, linkTarget, courseForSession } from '../services/notifications'
import { onPushTapped } from '../services/pushDevice'
import { navigateTo } from '../navigation/navigationRef'

const StudentContext = createContext(null)

const initialState = {
  isLoggedIn: false,
  student: null,
  classes: [],
  attendanceCourses: null,
  attendanceError: null,
  flags: {},      // session_id -> the student's flag for it (FR-319)
  banner: null,   // the global "Attendance recorded for …" banner (FR-406)
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
    case 'SET_STUDENT':
      return { ...state, student: action.payload }
    case 'SET_CLASSES':
      return { ...state, classes: action.payload }
    case 'SET_ATTENDANCE_COURSES':
      return { ...state, attendanceCourses: action.payload, attendanceError: null }
    case 'SET_ATTENDANCE_ERROR':
      return { ...state, attendanceError: action.payload }
    case 'SET_FLAG': {
      const flag = action.payload
      if (!flag) return state
      // API ids are numbers; merge so student-only fields survive a lecturer-shaped FlagOut
      const key = Number(flag.session_id)
      return { ...state, flags: { ...state.flags, [key]: { ...(state.flags[key] ?? {}), ...flag } } }
    }
    case 'SHOW_BANNER':
      return { ...state, banner: { id: Date.now(), ...action.payload } }
    case 'HIDE_BANNER':
      if (!state.banner || state.banner.id !== action.payload) return state
      return { ...state, banner: null }
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
  // The notification centre (S19): feed, unread count (the bell), live over /notifications/ws
  const [feed, feedDispatch] = useReducer(feedReducer, initialFeed)

  const openModal  = useCallback((type, data) => dispatch({ type: 'OPEN_MODAL', payload: { type, data } }), [])
  const closeModal = useCallback(() => dispatch({ type: 'CLOSE_MODAL' }), [])
  const showToast  = useCallback((message, variant = 'info') =>
    dispatch({ type: 'SHOW_TOAST', payload: { message, variant } }), [])

  const login = useCallback(async (username, password) => {
    dispatch({ type: 'SET_LOADING', payload: true })
    try {
      await api.login(username, password)
      const student = await api.getStudent()
      dispatch({ type: 'SET_STUDENT', payload: student })
      dispatch({ type: 'LOGIN' })
      api.registerForPush()          // in the background; a phone without push still works in-app
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: e.message })
      throw e
    }
  }, [])

  const logout = useCallback(async () => {
    await api.logout()
    dispatch({ type: 'LOGOUT' })
    feedDispatch({ type: 'reset' })
  }, [])

  // Listen for auth expiry from client.js
  useEffect(() => {
    const cleanup = onAuthExpired(() => {
      api.logout()
      dispatch({ type: 'LOGOUT' })
      feedDispatch({ type: 'reset' })
    })
    return cleanup
  }, [])

  // ─── Notifications (FR-208, FR-209, FR-213) ────────────────────────────────

  const loadNotifications = useCallback(async ({ more = false } = {}) => {
    try {
      const page = await api.getNotifications(more ? feedRef.current.nextCursor : null)
      feedDispatch({ type: 'page', page, append: more })
      return true
    } catch (e) {
      showToast(e.message, 'error')
      return false
    }
  }, [showToast])

  // true once it is read on the server (the dashboard drops it from the top only then)
  const markNotificationRead = useCallback(async (n) => {
    if (n.read) return true
    try {
      const r = await api.markNotificationRead(n.id)
      feedDispatch({ type: 'read', notification: r.notification, unread: r.unread_count })
      return true
    } catch (e) { showToast(e.message, 'error'); return false }
  }, [showToast])

  const markAllNotificationsRead = useCallback(async () => {
    try {
      const r = await api.markAllNotificationsRead()
      feedDispatch({ type: 'read_all', unread: r.unread_count })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  // A notification's link (feed tap or push tap) → its screen; false when there is none yet
  const openNotificationLink = useCallback(async (link) => {
    const target = linkTarget(link)
    if (!target) return false
    if (target.kind === 'screen') {
      // initial: false keeps the tab's main page under it, so Back returns there
      navigateTo(target.tab, { screen: target.screen, initial: target.screen === 'HomeScreen' })
      return true
    }
    // An attendance session: its screen needs the course it belongs to
    let courses = stateRef.current.attendanceCourses
    let course = courseForSession(courses, target.sessionId)
    if (!course) {
      try {
        courses = await api.getAttendanceCourses()
        dispatch({ type: 'SET_ATTENDANCE_COURSES', payload: courses })
        course = courseForSession(courses, target.sessionId)
      } catch (e) { showToast(e.message, 'error'); return false }
    }
    if (!course) { navigateTo('Attendance', { screen: 'AttendanceScreen' }); return true }
    navigateTo('Attendance', {
      screen: 'AttSessionDetail', params: { courseId: course.id, sessionId: target.sessionId },
      initial: false,
    })
    return true
  }, [showToast])

  const feedRef = useRef(feed)
  feedRef.current = feed
  const stateRef = useRef(state)
  stateRef.current = state

  // Live: every (re)connect re-reads the first page, since nothing is replayed (S12). Phones drop
  // sockets in the background, so a return to the app reconnects.
  useEffect(() => {
    if (!state.isLoggedIn) return undefined
    let active = true            // a reply that lands after sign-out must not refill the feed
    const onMessage = (m) => {
      if (!active) return
      if (m.type === 'connected') {
        feedDispatch({ type: 'count', unread: m.unread_count })
        api.getNotifications().then(page => { if (active) feedDispatch({ type: 'page', page }) }).catch(() => {})
      } else if (m.type === 'notification' && m.notification) {
        feedDispatch({ type: 'live', notification: m.notification, unread: m.unread_count })
      } else if (m.type === 'unread_count') {
        feedDispatch({ type: 'count', unread: m.unread_count })
      }
    }
    const connect = () => connectNotificationsLive({
      baseUrl: BASE, getToken, refreshToken: refreshAccessToken, onMessage,
    })
    let live = connect()
    const sub = AppState.addEventListener('change', (next) => {
      if (next !== 'active') return
      live.close()
      live = connect()
    })
    const unTap = onPushTapped((link) => { openLinkRef.current?.(link) })
    return () => {
      active = false
      sub?.remove?.()
      live.close()
      unTap()
    }
  }, [state.isLoggedIn])

  const openLinkRef = useRef(openNotificationLink)
  openLinkRef.current = openNotificationLink

  const loadClasses = useCallback(async () => {
    try {
      const classes = await api.getEnrolledClasses()
      dispatch({ type: 'SET_CLASSES', payload: classes })
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  const loadAttendanceCourses = useCallback(async () => {
    try {
      const courses = await api.getAttendanceCourses()
      dispatch({ type: 'SET_ATTENDANCE_COURSES', payload: courses })
    } catch (e) {
      showToast(e.message, 'error')
      dispatch({ type: 'SET_ATTENDANCE_ERROR', payload: e.message })
    }
  }, [showToast])

  // The student's own flag for one session (FR-319)
  const loadFlag = useCallback(async (sessionId) => {
    try {
      const flags = await api.getMyFlags(sessionId)
      const flag = flags?.[0] ?? null
      if (flag) dispatch({ type: 'SET_FLAG', payload: flag })
      return flag
    } catch (e) {
      showToast(e.message, 'error')
      return null
    }
  }, [showToast])

  // "I'm here — not recognised" (FR-318)
  const sendFlag = useCallback(async (sessionId) => {
    try {
      const flag = await api.flagNotRecognised(sessionId)
      dispatch({ type: 'SET_FLAG', payload: flag })
      return flag
    } catch (e) {
      showToast(e.message, 'error')
      // The 409 text says why (already recorded, already flagged): re-read the truth
      loadFlag(sessionId)
      loadAttendanceCourses()
      throw e
    }
  }, [showToast, loadFlag, loadAttendanceCourses])

  const dismissBanner = useCallback(() =>
    dispatch({ type: 'HIDE_BANNER', payload: state.banner?.id }), [state.banner])

  // The latest loadAttendanceCourses for the live channel (so the effect depends on the login only)
  const loadCoursesRef = useRef(loadAttendanceCourses)
  loadCoursesRef.current = loadAttendanceCourses

  // The student's own channel: a recognition banner (FR-406) and a flag result (FR-319) arrive
  // without polling. Phones drop sockets in the background, so a return to the app reconnects.
  useEffect(() => {
    if (!state.isLoggedIn) return undefined

    const onEvent = (data) => {
      if (data.event === 'attendance_recorded') {
        dispatch({ type: 'SHOW_BANNER', payload: {
          text: recordedBannerText(data), sessionId: data.session_id,
        } })
        loadCoursesRef.current?.()
      } else if (data.event === 'attendance_flag_resolved' && data.flag) {
        dispatch({ type: 'SET_FLAG', payload: data.flag })
        loadCoursesRef.current?.()
      }
    }
    const connect = () => connectStudentLive({
      baseUrl: BASE, getToken, refreshToken: refreshAccessToken, onEvent,
    })

    let live = connect()
    const sub = AppState.addEventListener('change', (next) => {
      if (next !== 'active') return
      live.close()      // no duplicate sockets (duplicate banners)
      live = connect()
    })
    return () => {
      sub?.remove?.()
      live.close()
    }
  }, [state.isLoggedIn])

  const value = {
    state,
    dispatch,
    openModal,
    closeModal,
    showToast,
    login,
    logout,
    loadClasses,
    loadAttendanceCourses,
    loadFlag,
    sendFlag,
    dismissBanner,
    feed,
    loadNotifications,
    markNotificationRead,
    markAllNotificationsRead,
    openNotificationLink,
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
