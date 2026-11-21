import { apiCall, BASE, getToken } from './client'

const pathFor = sessionId => `/interaction/sessions/${sessionId}`

export const getInteraction = sessionId => apiCall('GET', pathFor(sessionId))

export const sendInteraction = (sessionId, method, path, body) =>
  apiCall(method, pathFor(sessionId) + path, body)

export function openInteractionSocket(sessionId) {
  const token = getToken()
  if (!token) return null
  const base = BASE.replace(/^http/, 'ws').replace(/\/$/, '')
  return new WebSocket(`${base}${pathFor(sessionId)}/ws?token=${encodeURIComponent(token)}`)
}
