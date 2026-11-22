// Live notifications: WS /notifications/ws (FR-213, S12). No React here, so it runs under `npm test`.
// Messages: {type:"connected", unread_count}, {type:"notification", notification, unread_count},
// {type:"unread_count", unread_count}. Nothing is replayed, so the caller re-reads the feed on
// every "connected".
//
// Reconnects while open; a 1008 close (bad or expired token) refreshes the token once before
// reconnecting and stops if the refreshed token is refused too.

export function connectNotificationsLive({
  baseUrl, getToken, refreshToken, onMessage,
  WebSocketImpl = globalThis.WebSocket, schedule = setTimeout, cancel = clearTimeout,
  retryMs = 3000,
}) {
  let ws = null
  let closed = false
  let timer = null
  let refreshedOnce = false

  function open() {
    const token = getToken()
    if (!token || closed) return
    const url = baseUrl.replace(/^http/, 'ws') + '/notifications/ws?token=' + encodeURIComponent(token)
    ws = new WebSocketImpl(url)

    ws.onmessage = (e) => {
      let data
      try { data = JSON.parse(e.data) } catch { return }
      if (!data || typeof data.type !== 'string') return
      if (data.type === 'connected') refreshedOnce = false   // this token works
      onMessage(data)
    }

    ws.onclose = async (e) => {
      if (closed) return
      if (e?.code === 1008) {
        if (refreshedOnce) return          // the refreshed token was refused too
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
