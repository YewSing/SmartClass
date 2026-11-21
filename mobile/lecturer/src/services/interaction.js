import { apiCall, BASE, getToken } from './client'

export const interactionRequest = (sessionId, method = 'GET', suffix = '', body) =>
  apiCall(method, `/interaction/sessions/${sessionId}${suffix}`, body)

export function interactionSocket(sessionId) {
  const token = getToken()
  if (!token) return null
  const base = BASE.replace(/^http/, 'ws').replace(/\/$/, '')
  return new WebSocket(`${base}/interaction/sessions/${sessionId}/ws?token=${encodeURIComponent(token)}`)
}
