// Change EXPO_PUBLIC_API_URL in .env to your laptop's local IP

const BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://10.0.2.2:8000'


// ─── Real network client ────────────────────────────────────────────────

// In-memory cache so getToken() is synchronous after initStorage()
let _token = null
let _refreshToken = null

export async function realInitStorage() {
  try {
    _token = await AsyncStorage.getItem('token')
    _refreshToken = await AsyncStorage.getItem('refresh_token')
  } catch {
    _token = null
    _refreshToken = null
  }
}

const ignore = () => {}

export function realGetToken() { return _token }

export function realSetToken(t) {
  _token = t
  AsyncStorage.setItem('token', t).catch(ignore)
}

export function realClearToken() {
  _token = null
  AsyncStorage.removeItem('token').catch(ignore)
}

export function realGetRefreshToken() { return _refreshToken }

export function realSetRefreshToken(t) {
  _refreshToken = t
  AsyncStorage.setItem('refresh_token', t).catch(ignore)
}

export function realClearRefreshToken() {
  _refreshToken = null
  AsyncStorage.removeItem('refresh_token').catch(ignore)
}

// ─── Auth expiry listeners (replaces window.dispatchEvent) ────────────

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

  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    const err = new Error(e.detail ?? `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return res.status === 204 ? null : res.json()
}

export async function realApiCallRaw(method, path, _isRetry = false) {
  const token = realGetToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  if (res.status === 401 && !_isRetry && !LOGIN_PATHS.includes(path)) {
    const refreshed = await realDoRefresh()
    if (refreshed) return realApiCallRaw(method, path, true)
    realForceLogout()
    throw new Error('Session expired. Please log in again.')
  }

  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail ?? `HTTP ${res.status}`)
  }
  return res
}

export async function realRefreshAccessToken() {
  return realDoRefresh()
}

// ─── Exported API (always the real backend) ───────────────────────────

export async function initStorage() { return realInitStorage() }

export function getToken() { return realGetToken() }

export function setToken(t) { realSetToken(t) }

export function clearToken() { realClearToken() }

export function getRefreshToken() { return realGetRefreshToken() }

export function setRefreshToken(t) { realSetRefreshToken(t) }

export function clearRefreshToken() { realClearRefreshToken() }

export function onAuthExpired(fn) { return realOnAuthExpired(fn) }

export async function apiCall(method, path, body, _isRetry = false) {
  return realApiCall(method, path, body, _isRetry)
}

export async function apiCallRaw(method, path, _isRetry = false) {
  return realApiCallRaw(method, path, _isRetry)
}

export async function refreshAccessToken() { return realRefreshAccessToken() }

export { BASE }
