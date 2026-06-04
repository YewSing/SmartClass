import { createContext, useContext, useReducer, useCallback, useEffect } from 'react'
import * as api from '../services/api'

const AdminContext = createContext(null)

const initialState = {
  isLoggedIn: false,
  currentView: 'dashboard',
  users: [],
  allClasses: [],
  allCourses: [],
  selectedUserId: null,
  modal: null,
  toasts: [],
  unrecognisedQueue: [],     // no backend endpoint yet — stays empty
  env: {
    temperature: 28.4,
    humidity: 65,
    lightLevel: 420,
    co2: 812,
    occupancy: 12,
    acStatus: 'auto',
    lightStatus: 'auto',
    lastUpdated: '09:15:04',
    sensors: {
      'Temp Sensor':          'ok',
      'LDR Sensor':           'ok',
      'CO₂ Sensor':           'fault',
      'Camera (Front-Left)':  'ok',
      'Camera (Front-Right)': 'ok',
    },
  },
}

function reducer(state, action) {
  switch (action.type) {
    case 'LOGIN':
      return { ...state, isLoggedIn: true }

    case 'LOGOUT':
      return { ...state, isLoggedIn: false, currentView: 'dashboard', users: [], modal: null }

    case 'SET_VIEW':
      return { ...state, currentView: action.payload }

    case 'OPEN_MODAL':
      return { ...state, modal: action.payload }

    case 'CLOSE_MODAL':
      return { ...state, modal: null }

    case 'SELECT_USER':
      return { ...state, selectedUserId: action.payload }

    case 'SET_USERS':
      return { ...state, users: action.payload }

    case 'CREATE_USER':
      return { ...state, users: [...state.users, action.payload] }

    case 'UPDATE_USER':
      return {
        ...state,
        users: state.users.map(u => u.id === action.payload.id ? { ...u, ...action.payload } : u),
      }

    case 'DELETE_USER':
      return { ...state, users: state.users.filter(u => u.id !== action.payload) }

    case 'SET_ALL_CLASSES':
      return { ...state, allClasses: action.payload }

    case 'SET_ALL_COURSES':
      return { ...state, allCourses: action.payload }

    case 'TOGGLE_ENROLLMENT': {
      const { userId, classObj, enrolled } = action.payload
      return {
        ...state,
        users: state.users.map(u => {
          if (u.id !== userId) return u
          const classes = enrolled
            ? u.classes.some(c => c.id === classObj.id) ? u.classes : [...u.classes, classObj]
            : u.classes.filter(c => c.id !== classObj.id)
          // keep occurrences in sync if classObj has full occurrence fields
          const occObj = classObj.type ? {
            id: classObj.id,
            course_code: classObj.code,
            course_name: classObj.name,
            type: classObj.type,
            label: classObj.label ?? null,
            day_of_week: classObj.day_of_week,
            start_time: classObj.start_time,
            end_time: classObj.end_time,
          } : null
          const occurrences = occObj
            ? enrolled
              ? (u.occurrences ?? []).some(o => o.id === occObj.id) ? u.occurrences : [...(u.occurrences ?? []), occObj]
              : (u.occurrences ?? []).filter(o => o.id !== occObj.id)
            : u.occurrences
          return { ...u, classes, occurrences }
        }),
      }
    }

    case 'TOGGLE_OCCURRENCE_ENROLLMENT': {
      const { userId, occObj, enrolled } = action.payload
      return {
        ...state,
        users: state.users.map(u => {
          if (u.id !== userId) return u
          const occurrences = enrolled
            ? (u.occurrences ?? []).some(o => o.id === occObj.id)
              ? u.occurrences
              : [...(u.occurrences ?? []), occObj]
            : (u.occurrences ?? []).filter(o => o.id !== occObj.id)
          // keep classes in sync
          const classes = occurrences.map(o => ({ id: o.id, code: o.course_code, name: o.course_name }))
          return { ...u, occurrences, classes }
        }),
      }
    }

    case 'ENROLL_FACE':
      return {
        ...state,
        users: state.users.map(u =>
          u.id === action.payload.id
            ? { ...u, face: true, faceDate: new Date().toISOString().slice(0, 10), faceSamples: action.payload.count }
            : u
        ),
      }

    case 'REMOVE_FACE':
      return {
        ...state,
        users: state.users.map(u =>
          u.id === action.payload
            ? { ...u, face: false, faceDate: null, faceSamples: 0 }
            : u
        ),
      }

    case 'SET_REVIEW_QUEUE':
      return { ...state, unrecognisedQueue: action.payload }

    case 'DISMISS_REVIEW':
      return {
        ...state,
        unrecognisedQueue: state.unrecognisedQueue.filter(e => e.id !== action.payload),
      }

    case 'PROMOTE_REVIEW': {
      const { reviewId, userId } = action.payload
      return {
        ...state,
        unrecognisedQueue: state.unrecognisedQueue.filter(e => e.id !== reviewId),
        users: state.users.map(u =>
          u.id === userId
            ? { ...u, face: true, faceDate: new Date().toISOString().slice(0, 10), faceSamples: 1 }
            : u
        ),
      }
    }

    case 'ENV_OVERRIDE':
      return { ...state, env: { ...state.env, ...action.payload } }

    case 'ADD_TOAST':
      return { ...state, toasts: [...state.toasts, action.payload] }

    case 'REMOVE_TOAST':
      return { ...state, toasts: state.toasts.filter(t => t.id !== action.payload) }

    default:
      return state
  }
}

let toastId = 0

export function AdminProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  const toast = useCallback((msg, type = 'info') => {
    const id = ++toastId
    dispatch({ type: 'ADD_TOAST', payload: { id, msg, type } })
    setTimeout(() => dispatch({ type: 'REMOVE_TOAST', payload: id }), 3000)
  }, [])

  const openModal = useCallback((type, data = null) => {
    dispatch({ type: 'OPEN_MODAL', payload: { type, data } })
  }, [])

  const closeModal = useCallback(() => {
    dispatch({ type: 'CLOSE_MODAL' })
  }, [])

  // ── Auth ────────────────────────────────────────────────────────────────────
  const login = useCallback(async (email, password) => {
    const user = await api.login(email, password)
    dispatch({ type: 'LOGIN' })
    // load review queue in background after login
    api.getReviewQueue().then(queue => dispatch({ type: 'SET_REVIEW_QUEUE', payload: queue })).catch(() => {})
    return user
  }, [])

  const logout = useCallback(() => {
    api.logout()
    dispatch({ type: 'LOGOUT' })
  }, [])

  useEffect(() => {
    const handle = () => { api.logout(); dispatch({ type: 'LOGOUT' }) }
    window.addEventListener('auth:expired', handle)
    return () => window.removeEventListener('auth:expired', handle)
  }, [])

  // ── Classes / Courses ────────────────────────────────────────────────────────
  const loadAllClasses = useCallback(async () => {
    try {
      const classes = await api.getAllClasses()
      dispatch({ type: 'SET_ALL_CLASSES', payload: classes })
    } catch (e) { toast(e.message, 'error') }
  }, [toast])

  const loadAllCourses = useCallback(async () => {
    try {
      const courses = await api.getCourses()
      dispatch({ type: 'SET_ALL_COURSES', payload: courses })
    } catch (e) { toast(e.message, 'error') }
  }, [toast])

  // ── Users ───────────────────────────────────────────────────────────────────
  const loadUsers = useCallback(async () => {
    try {
      const data = await api.getUsers()
      dispatch({ type: 'SET_USERS', payload: data.items })
    } catch (e) { toast(e.message, 'error') }
  }, [toast])

  const createUser = useCallback(async (body) => {
    const user = await api.createUser(body)
    dispatch({ type: 'CREATE_USER', payload: user })
    return user
  }, [])

  const updateUser = useCallback(async (id, body) => {
    const user = await api.updateUser(id, body)
    dispatch({ type: 'UPDATE_USER', payload: user })
    return user
  }, [])

  const deactivateUser = useCallback(async (id) => {
    await api.deactivateUser(id)
    dispatch({ type: 'DELETE_USER', payload: id })
  }, [])

  // ── Enrollment ──────────────────────────────────────────────────────────────
  const toggleEnrollment = useCallback(async (userId, classObj, enrolled) => {
    if (enrolled) {
      await api.enrollStudentInClass(userId, classObj.id)
    } else {
      await api.removeStudentFromClass(userId, classObj.id)
    }
    dispatch({ type: 'TOGGLE_ENROLLMENT', payload: { userId, classObj, enrolled } })
  }, [])

  const toggleOccurrenceEnrollment = useCallback(async (userId, occObj, enrolled) => {
    if (enrolled) {
      await api.enrollInOccurrence(occObj.id, userId)
    } else {
      await api.unenrollFromOccurrence(occObj.id, userId)
    }
    dispatch({ type: 'TOGGLE_OCCURRENCE_ENROLLMENT', payload: { userId, occObj, enrolled } })
  }, [])

  // ── Face ────────────────────────────────────────────────────────────────────
  const enrollFace = useCallback(async (studentUserId, blobs) => {
    await api.enrollFace(studentUserId, blobs)
    dispatch({ type: 'ENROLL_FACE', payload: { id: studentUserId, count: blobs.length } })
  }, [])

  const removeFace = useCallback(async (studentUserId) => {
    await api.removeFace(studentUserId)
    dispatch({ type: 'REMOVE_FACE', payload: studentUserId })
  }, [])

  // ── Face Review Queue ────────────────────────────────────────────────────────
  const loadReviewQueue = useCallback(async () => {
    try {
      const queue = await api.getReviewQueue()
      dispatch({ type: 'SET_REVIEW_QUEUE', payload: queue })
    } catch (e) { toast(e.message, 'error') }
  }, [toast])

  const dismissReview = useCallback(async (id) => {
    await api.dismissReviewEntry(id)
    dispatch({ type: 'DISMISS_REVIEW', payload: id })
  }, [])

  const promoteReview = useCallback(async (reviewId, studentUserId) => {
    await api.promoteReviewEntry(reviewId, studentUserId)
    dispatch({ type: 'PROMOTE_REVIEW', payload: { reviewId, userId: studentUserId } })
  }, [])

  const value = {
    state,
    dispatch,
    toast,
    openModal,
    closeModal,
    // Action creators
    login,
    logout,
    loadAllClasses,
    loadAllCourses,
    loadUsers,
    createUser,
    updateUser,
    deactivateUser,
    toggleEnrollment,
    toggleOccurrenceEnrollment,
    enrollFace,
    removeFace,
    loadReviewQueue,
    dismissReview,
    promoteReview,
  }

  return <AdminContext.Provider value={value}>{children}</AdminContext.Provider>
}

export function useAdmin() {
  const ctx = useContext(AdminContext)
  if (!ctx) throw new Error('useAdmin must be used inside AdminProvider')
  return ctx
}
