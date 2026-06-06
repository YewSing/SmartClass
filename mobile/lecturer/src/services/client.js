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

  if (res.status === 401 && !_isRetry && path !== '/auth/login') {
    const refreshed = await _doRefresh()
    if (refreshed) return apiCall(method, path, body, true)
    _forceLogout()
    throw new Error('Session expired. Please log in again.')
  }

  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail ?? `HTTP ${res.status}`)
  }
  return res.status === 204 ? null : res.json()
}

export async function apiCallRaw(method, path, _isRetry = false) {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  if (res.status === 401 && !_isRetry && path !== '/auth/login') {
    const refreshed = await _doRefresh()
    if (refreshed) return apiCallRaw(method, path, true)
    _forceLogout()
    throw new Error('Session expired. Please log in again.')
  }

  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail ?? `HTTP ${res.status}`)
  }
  return res
}

export { BASE }
