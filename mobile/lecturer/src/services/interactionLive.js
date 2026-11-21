import { BASE, getToken } from './client'

export function connectInteractionLive({ interactionId, baseUrl = BASE, onEvent }) {
  const token = getToken()
  if (!token) return { close() {} }
  const wsBase = baseUrl.replace(/^http/, 'ws').replace(/\/$/, '')
  const ws = new WebSocket(`${wsBase}/interaction/sessions/${interactionId}/ws?token=${encodeURIComponent(token)}`)
  ws.onmessage = event => {
    try {
      const data = JSON.parse(event.data)
      if (data?.event) onEvent(data)
    } catch {}
  }
  return ws
}
