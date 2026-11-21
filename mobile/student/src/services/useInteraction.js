import { useCallback, useRef, useState } from 'react'
import { AppState } from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { getInteraction, openInteractionSocket, sendInteraction } from './interaction'
import { applyInteractionStatus, readInteractionEvent } from './interactionEvents'
import { createInteractionRefresh } from './interactionRefresh'

export function useInteraction(sessionId) {
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [connected, setConnected] = useState(false)
  const scope = useRef(null)
  const refresh = useCallback(() => scope.current?.refresh(), [])

  useFocusEffect(useCallback(() => {
    if (!Number.isSafeInteger(sessionId) || sessionId <= 0) {
      setError('This class link is unavailable.')
      return
    }
    let socket, retry
    let active = true
    const reads = createInteractionRefresh(
      () => getInteraction(sessionId),
      result => {
        setState(result)
        setError('')
      },
      err => {
        if ([401, 403, 404].includes(err.status)) setState(null)
        setError(err.message || 'Could not load this class.')
      },
    )
    const current = { writing: false, refresh: reads.refresh }
    scope.current = current
    setState(null)
    setError('')
    setBusy(false)

    async function connect() {
      await current.refresh()
      if (!active) return
      try { socket = openInteractionSocket(sessionId) } catch {
        retry = setTimeout(connect, 3000)
        return
      }
      if (!socket) return
      socket.onmessage = message => {
        if (!active) return
        const event = readInteractionEvent(message.data, sessionId)
        if (!event) return
        setConnected(true)
        setState(value => applyInteractionStatus(value, event))
        const lifecycleChange = ['interaction.state', 'interaction.session_status'].includes(event.event)
        current.refresh({ lifecycleChange })
      }
      socket.onclose = () => {
        if (!active) return
        setConnected(false)
        retry = setTimeout(connect, 3000)
      }
    }
    connect()
    const fallback = setInterval(() => current.refresh(), 15000)
    const foreground = AppState.addEventListener('change', next => {
      if (next === 'active') current.refresh()
    })
    return () => {
      active = false
      reads.stop()
      scope.current = null
      clearInterval(fallback)
      clearTimeout(retry)
      foreground.remove()
      socket?.close()
      setConnected(false)
    }
  }, [sessionId]))

  async function submit(method, path, body) {
    const current = scope.current
    if (!current || current.writing || !state?.can_participate) return false
    current.writing = true
    setBusy(true)
    try {
      await sendInteraction(sessionId, method, path, body)
      await current.refresh()
      return scope.current === current
    } catch (err) {
      if ([401, 403, 404, 409].includes(err.status)) current.refresh()
      throw err
    } finally {
      current.writing = false
      if (scope.current === current) setBusy(false)
    }
  }

  return { state, error, busy, connected, refresh, submit }
}
