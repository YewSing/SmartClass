const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export function getToken()          { return localStorage.getItem('token') }
export function setToken(t)         { localStorage.setItem('token', t) }
export function clearToken()        { localStorage.removeItem('token') }

export function getRefreshToken()   { return localStorage.getItem('refresh_token') }
export function setRefreshToken(t)  { localStorage.setItem('refresh_token', t) }
export function clearRefreshToken() { localStorage.removeItem('refresh_token') }

// Singleton promise — concurrent 401s all wait on the same refresh instead of racing
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
  window.dispatchEvent(new Event('auth:expired'))
}

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

export async function apiUpload(method, path, formData, _isRetry = false) {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })

  if (res.status === 401 && !_isRetry) {
    const refreshed = await _doRefresh()
    if (refreshed) return apiUpload(method, path, formData, true)
    _forceLogout()
    throw new Error('Session expired. Please log in again.')
  }

  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail ?? `HTTP ${res.status}`)
  }
  return res.status === 204 ? null : res.json()
}
