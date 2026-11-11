// Change EXPO_PUBLIC_API_URL in .env to your laptop's local IP
import AsyncStorage from '@react-native-async-storage/async-storage'

const BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://10.0.2.2:8000'

// In-memory cache so getToken() is synchronous after initStorage()
let _token = null
let _refreshToken = null

// ─── Storage init (call once on app startup) ──────────────────────────────────

export async function initStorage() {
  _token = await AsyncStorage.getItem('token')
  _refreshToken = await AsyncStorage.getItem('refresh_token')
}

// ─── Token accessors ──────────────────────────────────────────────────────────

export function getToken() { return _token }

export function setToken(t) {
  _token = t
  AsyncStorage.setItem('token', t)
}

export function clearToken() {
  _token = null
  AsyncStorage.removeItem('token')
}

export function getRefreshToken() { return _refreshToken }

export function setRefreshToken(t) {
  _refreshToken = t
  AsyncStorage.setItem('refresh_token', t)
}

export function clearRefreshToken() {
  _refreshToken = null
  AsyncStorage.removeItem('refresh_token')
}

// ─── Auth expiry listeners (replaces window.dispatchEvent) ───────────────────

const _authListeners = []

export function onAuthExpired(fn) {
  _authListeners.push(fn)
  return () => {
    const idx = _authListeners.indexOf(fn)
    if (idx !== -1) _authListeners.splice(idx, 1)
  }
}

function _fireAuthExpired() {
  _authListeners.forEach(fn => fn())
}

// ─── Singleton refresh promise ────────────────────────────────────────────────

let _refreshPromise = null

async function _doRefresh() {
  if (_refreshPromise) return _refreshPromise
  _refreshPromise = (async () => {
    const rt = getRefreshToken()
    if (!rt) return false
    try {
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: rt }),
      })
      if (!res.ok) return false
      const data = await res.json()
      setToken(data.access_token)
      return true
    } catch {
      return false
    } finally {
      _refreshPromise = null
    }
  })()
  return _refreshPromise
}

function _forceLogout() {
  clearToken()
  clearRefreshToken()
  _fireAuthExpired()
}

// A 401 from a sign-in request means wrong credentials, not an expired session
const LOGIN_PATHS = ['/auth/login', '/auth/moodle-login']

// ─── API call ─────────────────────────────────────────────────────────────────

export async function apiCall(method, path, body, _isRetry = false) {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && !_isRetry && !LOGIN_PATHS.includes(path)) {
    const refreshed = await _doRefresh()
    if (refreshed) return apiCall(method, path, body, true)
    _forceLogout()
    throw new Error('Session expired. Please log in again.')
  }

  return _result(res)
}

// Multipart upload (photos). `makeForm` builds a fresh FormData, so a retry after a refresh can resend it.
export async function apiUpload(method, path, makeForm, _isRetry = false) {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: makeForm(),
  })

  if (res.status === 401 && !_isRetry) {
    const refreshed = await _doRefresh()
    if (refreshed) return apiUpload(method, path, makeForm, true)
    _forceLogout()
    throw new Error('Session expired. Please log in again.')
  }

  return _result(res)
}

// A non-2xx response becomes an Error with `status` and the raw `detail` (which may be an object)
async function _result(res) {
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

// For requests that can't go through apiCall (file downloads): try a refresh after a 401
export async function refreshAccessToken() {
  const ok = await _doRefresh()
  if (!ok) _forceLogout()
  return ok
}

export { BASE }
