import { createContext, useContext, useReducer, useCallback } from 'react'

const LecturerContext = createContext(null)

const initialState = {
  isLoggedIn: false,
  currentView: 'dashboard',
  prevView: 'dashboard',
  sessionOpen: true,
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
      return { ...state, prevView: state.currentView, currentView: action.payload }
    case 'GO_BACK':
      return { ...state, currentView: state.prevView }
    case 'TOGGLE_SESSION':
      return { ...state, sessionOpen: !state.sessionOpen }
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

  const navigate   = useCallback((view) => dispatch({ type: 'SET_VIEW', payload: view }), [])
  const goBack     = useCallback(() => dispatch({ type: 'GO_BACK' }), [])
  const openModal  = useCallback((type, data) => dispatch({ type: 'OPEN_MODAL', payload: { type, data } }), [])
  const closeModal = useCallback(() => dispatch({ type: 'CLOSE_MODAL' }), [])
  const showToast  = useCallback((message, variant = 'info') =>
    dispatch({ type: 'SHOW_TOAST', payload: { message, variant } }), [])

  return (
    <LecturerContext.Provider value={{ state, dispatch, navigate, goBack, openModal, closeModal, showToast }}>
      {children}
    </LecturerContext.Provider>
  )
}

export function useLecturer() {
  const ctx = useContext(LecturerContext)
  if (!ctx) throw new Error('useLecturer must be used inside LecturerProvider')
  return ctx
}
