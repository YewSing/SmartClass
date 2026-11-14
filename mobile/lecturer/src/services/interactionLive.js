// Live updates for an interaction session room /ws/interactions/{id} (FR-502..FR-508).
// Reconnects while open; a 1008 close (expired token) refreshes the token once before
// reconnecting and stops if that second attempt is refused too. No React here, so it runs
// under `node --test`.

export function connectInteractionLive({
  interactionId,
  baseUrl,
  getToken,
  refreshToken,
  onEvent,
  WebSocketImpl = globalThis.WebSocket,
  schedule = setTimeout,
  cancel = clearTimeout,
  retryMs = 3000,
}) {
  let ws = null
  let closed = false
  let timer = null
  let refreshedOnce = false

  function open() {
    const token = getToken()
    if (!token) return
    const url = baseUrl.replace(/^http/, 'ws') + `/ws/interactions/${interactionId}?token=` + encodeURIComponent(token)
    ws = new WebSocketImpl(url)

    ws.onopen = () => { refreshedOnce = false }

    ws.onmessage = (e) => {
      let data
      try { data = JSON.parse(e.data) } catch { return }
      if (data?.event) onEvent(data)
    }

    ws.onclose = async (e) => {
      if (closed) return
      if (e?.code === 1008) {
        if (refreshedOnce) return
        refreshedOnce = true
        const ok = await refreshToken()
        if (!ok || closed) return
      }
      timer = schedule(open, retryMs)
    }

    ws.onerror = () => {}                  // onclose follows
  }

  open()

  return {
    close() {
      closed = true
      cancel(timer)
      ws?.close()
    },
  }
}
