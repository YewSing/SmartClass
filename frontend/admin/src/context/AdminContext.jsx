import { createContext, useContext, useReducer, useCallback } from 'react'
import { INITIAL_USERS, AVATAR_COLORS, UNRECOGNISED_QUEUE } from '../data/users'

const AdminContext = createContext(null)

const initialState = {
  isLoggedIn: false,
  currentView: 'dashboard',
  users: INITIAL_USERS,
  selectedUserId: null,
  modal: null, // { type: string, data?: any }
  toasts: [],
  unrecognisedQueue: UNRECOGNISED_QUEUE,
  env: {
    temperature: 28.4,
    humidity: 65,
    lightLevel: 420,
    co2: 812,
    occupancy: 12,
    acStatus: 'auto',    // 'auto' | 'on' | 'off'
    lightStatus: 'auto', // 'auto' | 'on' | 'off'
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
      return { ...state, isLoggedIn: false, currentView: 'dashboard', modal: null }

    case 'SET_VIEW':
      return { ...state, currentView: action.payload }

    case 'OPEN_MODAL':
      return { ...state, modal: action.payload }

    case 'CLOSE_MODAL':
      return { ...state, modal: null }

    case 'SELECT_USER':
      return { ...state, selectedUserId: action.payload }

    case 'CREATE_USER': {
      const newUser = {
        ...action.payload,
        face: false, faceDate: null, faceSamples: 0, classes: [],
        color: AVATAR_COLORS[Math.floor(Math.random() * AVATAR_COLORS.length)],
      }
      return { ...state, users: [...state.users, newUser] }
    }

    case 'UPDATE_USER':
      return {
        ...state,
        users: state.users.map(u => u.id === action.payload.id ? { ...u, ...action.payload } : u),
      }

    case 'DELETE_USER':
      return { ...state, users: state.users.filter(u => u.id !== action.payload) }

    case 'TOGGLE_ENROLLMENT': {
      const { userId, classCode, enrolled } = action.payload
      return {
        ...state,
        users: state.users.map(u => {
          if (u.id !== userId) return u
          const classes = enrolled
            ? [...new Set([...u.classes, classCode])]
            : u.classes.filter(c => c !== classCode)
          return { ...u, classes }
        }),
      }
    }

    case 'ENROLL_FACE':
      return {
        ...state,
        users: state.users.map(u =>
          u.id === action.payload
            ? { ...u, face: true, faceDate: new Date().toISOString().slice(0, 10), faceSamples: 5 }
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
            ? { ...u, face: true, faceDate: new Date().toISOString().slice(0, 10), faceSamples: 5 }
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

  const value = { state, dispatch, toast, openModal, closeModal }

  return <AdminContext.Provider value={value}>{children}</AdminContext.Provider>
}

export function useAdmin() {
  const ctx = useContext(AdminContext)
  if (!ctx) throw new Error('useAdmin must be used inside AdminProvider')
  return ctx
}
