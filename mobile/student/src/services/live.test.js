import { test } from 'node:test'
import assert from 'node:assert/strict'
import { connectStudentLive } from './live.js'

// Records every socket the client opens. `close()` only marks it; a test triggers onclose itself.
class FakeWebSocket {
  static instances = []
  constructor(url) {
    this.url = url
    this.closed = false
    this.onopen = null
    this.onmessage = null
    this.onclose = null
    this.onerror = null
    FakeWebSocket.instances.push(this)
  }
  close() { this.closed = true }
}

function setup({
  baseUrl = 'http://host:8000',
  token = 'abc',
  refresh = async () => true,
  retryMs,
} = {}) {
  FakeWebSocket.instances = []
  const events = []
  const scheduled = []
  const cancelled = []
  let refreshes = 0
  const live = connectStudentLive({
    baseUrl,
    getToken: () => token,
    refreshToken: async () => { refreshes += 1; return refresh() },
    onEvent: (e) => events.push(e),
    WebSocketImpl: FakeWebSocket,
    schedule: (fn, ms) => { const t = { fn, ms }; scheduled.push(t); return t },
    cancel: (t) => cancelled.push(t),
    ...(retryMs != null ? { retryMs } : {}),
  })
  return {
    live, events, scheduled, cancelled,
    instances: () => FakeWebSocket.instances,
    refreshes: () => refreshes,
  }
}

test('the channel URL is built from the API base and the current token', () => {
  const first = setup({ baseUrl: 'http://host:8000' })
  assert.equal(first.instances().length, 1)
  assert.equal(first.instances()[0].url, 'ws://host:8000/ws/me?token=abc')

  const secure = setup({ baseUrl: 'https://host:8000' })
  assert.equal(secure.instances()[0].url, 'wss://host:8000/ws/me?token=abc')

  const encoded = setup({ token: 'a b&c' })
  assert.equal(encoded.instances()[0].url, 'ws://host:8000/ws/me?token=a%20b%26c')
})

test('only real events reach onEvent: connected, invalid JSON and event-less messages are ignored', () => {
  const { instances, events } = setup()
  const ws = instances()[0]
  ws.onmessage({ data: JSON.stringify({ event: 'connected', user_id: 3 }) })
  ws.onmessage({ data: 'not json' })
  ws.onmessage({ data: JSON.stringify({ session_id: 4 }) })
  ws.onmessage({ data: JSON.stringify({ event: 'attendance_recorded', course_code: 'CS101' }) })
  assert.deepEqual(events, [{ event: 'attendance_recorded', course_code: 'CS101' }])
})

test('an unexpected close reconnects after retryMs', () => {
  const { instances, scheduled } = setup()
  instances()[0].onclose({ code: 1006 })
  assert.equal(scheduled.length, 1)
  assert.equal(scheduled[0].ms, 3000)
  scheduled[0].fn()
  assert.equal(instances().length, 2)
})

test('a 1008 close refreshes the token once, then reconnects', async () => {
  const { instances, scheduled, refreshes } = setup()
  await instances()[0].onclose({ code: 1008 })
  assert.equal(refreshes(), 1)
  assert.equal(scheduled.length, 1)
  scheduled[0].fn()
  assert.equal(instances().length, 2)
})

test('a refused refresh means no reconnect', async () => {
  const { instances, scheduled, refreshes } = setup({ refresh: async () => false })
  await instances()[0].onclose({ code: 1008 })
  assert.equal(refreshes(), 1)
  assert.equal(scheduled.length, 0)
})

test('a second 1008 in a row stops instead of refreshing again', async () => {
  const { instances, scheduled, refreshes } = setup()
  const ws = instances()[0]
  await ws.onclose({ code: 1008 })
  const afterFirst = scheduled.length
  await ws.onclose({ code: 1008 })
  assert.equal(refreshes(), 1)
  assert.equal(scheduled.length, afterFirst)
})

test('close() stops reconnecting and cancels a pending timer', () => {
  const { live, instances, scheduled, cancelled } = setup()
  instances()[0].onclose({ code: 1006 })
  const timer = scheduled[0]

  live.close()
  assert.deepEqual(cancelled, [timer])

  instances()[0].onclose({ code: 1006 })
  assert.equal(scheduled.length, 1)
  assert.equal(instances()[0].closed, true)
})

test('no token means no socket', () => {
  const { instances } = setup({ token: null })
  assert.equal(instances().length, 0)
})
