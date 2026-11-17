// Change EXPO_PUBLIC_API_URL in .env to your laptop's local IP
import AsyncStorage from '@react-native-async-storage/async-storage'
import * as mock from './mockClient'

const SIMULATION = process.env.EXPO_PUBLIC_SIMULATION === '1'
const BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://10.0.2.2:8000'

// ─── Real network client ────────────────────────────────────────────────

let _token = null
let _refreshToken = null

export async function realInitStorage() {
  _token = await AsyncStorage.getItem('token')
  _refreshToken = await AsyncStorage.getItem('refresh_token')
}

export function realGetToken() { return _token }

export function realSetToken(t) {
  _token = t
  AsyncStorage.setItem('token', t)
}

export function realClearToken() {
  _token = null
  AsyncStorage.removeItem('token')
}

export function realGetRefreshToken() { return _refreshToken }

export function realSetRefreshToken(t) {
  _refreshToken = t
  AsyncStorage.setItem('refresh_token', t)
}

export function realClearRefreshToken() {
  _refreshToken = null
  AsyncStorage.removeItem('refresh_token')
}

// ─── Auth expiry listeners (replaces window.dispatchEvent) ───────────

const _authListeners = []

export function realOnAuthExpired(fn) {
  _authListeners.push(fn)
  return () => {
    const idx = _authListeners.indexOf(fn)
    if (idx !== -1) _authListeners.splice(idx, 1)
  }
}

function _fireAuthExpired() {
  _authListeners.forEach(fn => fn())
}

// ─── Singleton refresh promise ────────────────────────────────────────

let _refreshPromise = null

async function realDoRefresh() {
  if (_refreshPromise) return _refreshPromise
  _refreshPromise = (async () => {
    const rt = realGetRefreshToken()
    if (!rt) return false
    try {
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: rt }),
      })
      if (!res.ok) return false
      const data = await res.json()
      realSetToken(data.access_token)
      return true
    } catch {
      return false
    } finally {
      _refreshPromise = null
    }
  })()
  return _refreshPromise
}

function realForceLogout() {
  realClearToken()
  realClearRefreshToken()
  _fireAuthExpired()
}

// A 401 from a sign-in request means wrong credentials, not an expired session
const LOGIN_PATHS = ['/auth/login', '/auth/moodle-login']

export async function realApiCall(method, path, body, _isRetry = false) {
  const token = realGetToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && !_isRetry && !LOGIN_PATHS.includes(path)) {
    const refreshed = await realDoRefresh()
    if (refreshed) return realApiCall(method, path, body, true)
    realForceLogout()
    throw new Error('Session expired. Please log in again.')
  }

  return realResult(res)
}

export async function realApiUpload(method, path, makeForm, _isRetry = false) {
  const token = realGetToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: makeForm(),
  })

  if (res.status === 401 && !_isRetry) {
    const refreshed = await realDoRefresh()
    if (refreshed) return realApiUpload(method, path, makeForm, true)
    realForceLogout()
    throw new Error('Session expired. Please log in again.')
  }

  return realResult(res)
}

async function realResult(res) {
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    const d = e.detail
    const msg = typeof d === 'string' ? d : (d?.message ?? `HTTP ${res.status}`)
    const err = new Error(msg)
    err.status = res.status
    err.detail = d
    throw err
  }
  return res.status === 204 ? null : res.json()
}

export async function realRefreshAccessToken() {
  const ok = await realDoRefresh()
  if (!ok) realForceLogout()
  return ok
}

// ─── Exported simulation-aware API ────────────────────────────────────
// When EXPO_PUBLIC_SIMULATION=1 every call (including token storage) goes to
// the in-memory mock client, so the app runs without a backend.

export async function initStorage() {
  return SIMULATION ? mock.initStorage() : realInitStorage()
}

export function getToken() { return SIMULATION ? mock.getToken() : realGetToken() }

export function setToken(t) {
  if (SIMULATION) { mock.setToken(t); return }
  realSetToken(t)
}

export function clearToken() {
  if (SIMULATION) { mock.clearToken(); return }
  realClearToken()
}

export function getRefreshToken() { return SIMULATION ? mock.getRefreshToken() : realGetRefreshToken() }

export function setRefreshToken(t) {
  if (SIMULATION) { mock.setRefreshToken(t); return }
  realSetRefreshToken(t)
}

export function clearRefreshToken() {
  if (SIMULATION) { mock.clearRefreshToken(); return }
  realClearRefreshToken()
}

export function onAuthExpired(fn) {
  return SIMULATION ? mock.onAuthExpired(fn) : realOnAuthExpired(fn)
}

export async function apiCall(method, path, body, _isRetry = false) {
  return SIMULATION ? mock.apiCall(method, path, body, _isRetry) : realApiCall(method, path, body, _isRetry)
}

export async function apiUpload(method, path, makeForm, _isRetry = false) {
  return SIMULATION ? mock.apiUpload(method, path, makeForm, _isRetry) : realApiUpload(method, path, makeForm, _isRetry)
}

export async function refreshAccessToken() {
  return SIMULATION ? mock.refreshAccessToken() : realRefreshAccessToken()
}

export { BASE, SIMULATION }
