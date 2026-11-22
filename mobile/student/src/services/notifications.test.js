import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  initialFeed, feedReducer, mergeItems, parseTime, timeLabel, countLabel, bellLabel,
  priorityBadge, linkTarget, courseForSession, prefsUpdate,
} from './notifications.js'
import { connectNotificationsLive } from './notificationsLive.js'
import { registerPush, unregisterPush } from './pushRegistration.js'

const item = (id, created_at, extra = {}) => ({
  id, event: 'announcement.posted', priority: 'important', title: `t${id}`, message: `m${id}`,
  link: null, read: false, read_at: null, created_at, ...extra,
})

// ─── feed state ──────────────────────────────────────────────────────────────

test('first page replaces the list, newest first, with cursor and unread count', () => {
  const s = feedReducer(initialFeed, { type: 'page', page: {
    items: [item(1, '2026-11-22T09:00:00'), item(3, '2026-11-22T10:00:00')], next_cursor: 'c1', unread_count: 5,
  } })
  assert.deepEqual(s.items.map(n => n.id), [3, 1])
  assert.equal(s.nextCursor, 'c1')
  assert.equal(s.unread, 5)
  assert.equal(s.loaded, true)
})

test('load more appends older items without repeats; the last page clears the cursor', () => {
  let s = feedReducer(initialFeed, { type: 'page', page: { items: [item(5, '2026-11-22T10:05:00'), item(4, '2026-11-22T10:04:00')], next_cursor: 'c', unread_count: 2 } })
  s = feedReducer(s, { type: 'page', append: true, page: { items: [item(4, '2026-11-22T10:04:00'), item(2, '2026-11-22T10:02:00')], next_cursor: null, unread_count: 2 } })
  assert.deepEqual(s.items.map(n => n.id), [5, 4, 2])
  assert.equal(s.nextCursor, null)
})

test('a refresh replaces older pages with the first page', () => {
  let s = feedReducer(initialFeed, { type: 'page', page: { items: [item(2, '2026-11-22T10:00:00')], next_cursor: 'c', unread_count: 1 } })
  s = feedReducer(s, { type: 'page', append: true, page: { items: [item(1, '2026-11-22T09:00:00')], next_cursor: null, unread_count: 1 } })
  s = feedReducer(s, { type: 'page', page: { items: [item(9, '2026-11-22T11:00:00'), item(2, '2026-11-22T10:00:00')], next_cursor: 'c2', unread_count: 2 } })
  assert.deepEqual(s.items.map(n => n.id), [9, 2])
  assert.equal(s.nextCursor, 'c2')
})

test('a live notification goes on top once, with the new unread count', () => {
  let s = feedReducer(initialFeed, { type: 'page', page: { items: [item(1, '2026-11-22T09:00:00')], next_cursor: null, unread_count: 1 } })
  const n = item(2, '2026-11-22T09:30:00')
  s = feedReducer(s, { type: 'live', notification: n, unread: 2 })
  s = feedReducer(s, { type: 'live', notification: n, unread: 2 })   // same message twice (two sockets)
  assert.deepEqual(s.items.map(x => x.id), [2, 1])
  assert.equal(s.unread, 2)
})

test('same time is ordered by id, newest id first', () => {
  const at = '2026-11-22T09:00:00'
  assert.deepEqual(mergeItems([item(1, at)], [item(3, at), item(2, at)]).map(n => n.id), [3, 2, 1])
})

test('reading one replaces it with the server copy; read-all marks every item read', () => {
  let s = feedReducer(initialFeed, { type: 'page', page: { items: [item(1, '2026-11-22T09:00:00'), item(2, '2026-11-22T09:01:00')], next_cursor: null, unread_count: 2 } })
  s = feedReducer(s, { type: 'read', notification: item(1, '2026-11-22T09:00:00', { read: true, read_at: '2026-11-22T09:05:00' }), unread: 1 })
  assert.deepEqual(s.items.map(n => n.read), [false, true])
  assert.equal(s.items[1].read_at, '2026-11-22T09:05:00')
  assert.equal(s.unread, 1)
  s = feedReducer(s, { type: 'read_all', unread: 0, readAt: 'X' })
  assert.deepEqual(s.items.map(n => n.read), [true, true])
  assert.equal(s.items[0].read_at, 'X')
  assert.equal(s.items[1].read_at, '2026-11-22T09:05:00')   // keeps the first read_at
  assert.equal(s.unread, 0)
})

test('count updates only the number; reset empties everything', () => {
  let s = feedReducer(initialFeed, { type: 'count', unread: 4 })
  assert.equal(s.unread, 4)
  assert.equal(s.loaded, false)
  assert.deepEqual(feedReducer(s, { type: 'reset' }), initialFeed)
})

// ─── display ─────────────────────────────────────────────────────────────────

test('naive API times are Malaysia time; explicit offsets are kept', () => {
  assert.equal(parseTime('2026-11-22T09:00:00').toISOString(), '2026-11-22T01:00:00.000Z')
  assert.equal(parseTime('2026-11-22T09:00:00Z').toISOString(), '2026-11-22T09:00:00.000Z')
  assert.equal(parseTime('2026-11-22T09:00:00+00:00').toISOString(), '2026-11-22T09:00:00.000Z')
  assert.equal(parseTime(null), null)
  assert.equal(parseTime('nonsense'), null)
})

test('time labels: just now, minutes, hours today, yesterday, a date', () => {
  const now = new Date('2026-11-22T12:00:00+08:00')
  assert.equal(timeLabel('2026-11-22T11:59:40', now), 'Just now')
  assert.equal(timeLabel('2026-11-22T11:55:00', now), '5 min ago')
  assert.equal(timeLabel('2026-11-22T08:30:00', now), '3 h ago')
  assert.equal(timeLabel('2026-11-21T23:00:00', now), 'Yesterday')
  assert.equal(timeLabel('2026-11-19T10:00:00', now), '19 Nov')
  assert.equal(timeLabel(null, now), '')
})

test('bell count and label', () => {
  assert.equal(countLabel(0), '')
  assert.equal(countLabel(7), '7')
  assert.equal(countLabel(100), '99+')
  assert.equal(bellLabel(0), 'Notifications, none unread')
  assert.equal(bellLabel(3), 'Notifications, 3 unread')
})

test('priority badges', () => {
  assert.deepEqual(priorityBadge('urgent'), { variant: 'red', label: 'Urgent' })
  assert.deepEqual(priorityBadge('important'), { variant: 'orange', label: 'Important' })
  assert.deepEqual(priorityBadge('general'), { variant: 'gray', label: 'General' })
  assert.deepEqual(priorityBadge('weird'), { variant: 'gray', label: 'General' })
})

// ─── deep links (student) ────────────────────────────────────────────────────

test('student links open their screens; links without a screen yet open nothing', () => {
  assert.deepEqual(linkTarget('/attendance/sessions/42'), { kind: 'session', sessionId: 42 })
  assert.deepEqual(linkTarget('/profile/face'), { kind: 'screen', tab: 'Profile', screen: 'FaceEnrolment' })
  assert.deepEqual(linkTarget('/home'), { kind: 'screen', tab: 'Home', screen: 'HomeScreen' })
  for (const l of ['/announcements/3', '/quizzes/7', '/interaction/5', '/attendance/sessions/x',
                   'https://evil.example/home', '//home', null, undefined, 42]) {
    assert.equal(linkTarget(l), null, String(l))
  }
})

test('the course holding a session', () => {
  const courses = [{ id: 1, sessions: [{ id: 10 }] }, { id: 2, sessions: [{ id: 42 }] }]
  assert.equal(courseForSession(courses, 42).id, 2)
  assert.equal(courseForSession(courses, '10').id, 1)
  assert.equal(courseForSession(courses, 99), null)
  assert.equal(courseForSession(null, 1), null)
})

test('preferences only change general', () => {
  assert.deepEqual(prefsUpdate('push', true), { push: { general: true } })
  assert.deepEqual(prefsUpdate('email', 0), { email: { general: false } })
})

// ─── live channel ────────────────────────────────────────────────────────────

class FakeWebSocket {
  static instances = []
  constructor(url) { this.url = url; this.closed = false; FakeWebSocket.instances.push(this) }
  close() { this.closed = true }
}

function liveSetup({ token = 'a b', refresh = async () => true } = {}) {
  FakeWebSocket.instances = []
  const messages = []
  const scheduled = []
  let refreshes = 0
  const live = connectNotificationsLive({
    baseUrl: 'https://host:8000', getToken: () => token,
    refreshToken: async () => { refreshes += 1; return refresh() },
    onMessage: (m) => messages.push(m), WebSocketImpl: FakeWebSocket,
    schedule: (fn, ms) => { const t = { fn, ms }; scheduled.push(t); return t }, cancel: () => {},
  })
  return { live, messages, scheduled, refreshes: () => refreshes }
}

test('connects to /notifications/ws with the encoded token and passes every typed message on', () => {
  const { messages } = liveSetup()
  const [ws] = FakeWebSocket.instances
  assert.equal(ws.url, 'wss://host:8000/notifications/ws?token=a%20b')
  ws.onmessage({ data: JSON.stringify({ type: 'connected', unread_count: 2 }) })
  ws.onmessage({ data: JSON.stringify({ type: 'notification', notification: { id: 1 }, unread_count: 3 }) })
  ws.onmessage({ data: 'not json' })
  ws.onmessage({ data: JSON.stringify({ no: 'type' }) })
  assert.deepEqual(messages.map(m => m.type), ['connected', 'notification'])
})

test('no token: no socket', () => {
  liveSetup({ token: null })
  assert.equal(FakeWebSocket.instances.length, 0)
})

test('a dropped socket reconnects after a pause', () => {
  const { scheduled } = liveSetup()
  FakeWebSocket.instances[0].onclose({ code: 1006 })
  assert.equal(scheduled.length, 1)
  assert.equal(scheduled[0].ms, 3000)
  scheduled[0].fn()
  assert.equal(FakeWebSocket.instances.length, 2)
})

test('1008 refreshes the token once; a second 1008 stops', async () => {
  const { scheduled, refreshes } = liveSetup()
  await FakeWebSocket.instances[0].onclose({ code: 1008 })
  assert.equal(refreshes(), 1)
  scheduled[0].fn()
  await FakeWebSocket.instances[1].onclose({ code: 1008 })
  assert.equal(refreshes(), 1)
  assert.equal(scheduled.length, 1)
})

test('1008 with a failed refresh stops', async () => {
  const { scheduled } = liveSetup({ refresh: async () => false })
  await FakeWebSocket.instances[0].onclose({ code: 1008 })
  assert.equal(scheduled.length, 0)
})

test('after a working reconnect, a later 1008 may refresh again', async () => {
  const { scheduled, refreshes } = liveSetup()
  await FakeWebSocket.instances[0].onclose({ code: 1008 })
  scheduled[0].fn()
  FakeWebSocket.instances[1].onmessage({ data: JSON.stringify({ type: 'connected', unread_count: 0 }) })
  await FakeWebSocket.instances[1].onclose({ code: 1008 })
  assert.equal(refreshes(), 2)
})

test('close() stops reconnecting', () => {
  const { live, scheduled } = liveSetup()
  live.close()
  assert.equal(FakeWebSocket.instances[0].closed, true)
  FakeWebSocket.instances[0].onclose({ code: 1006 })
  assert.equal(scheduled.length, 0)
})

// ─── push registration ───────────────────────────────────────────────────────

function fakeN({ granted = true, grantOnAsk = true, token = 'ExponentPushToken[abc]', fail } = {}) {
  const calls = []
  return {
    calls,
    AndroidImportance: { HIGH: 4 },
    getPermissionsAsync: async () => { calls.push('get'); return { granted } },
    requestPermissionsAsync: async () => { calls.push('ask'); return { granted: grantOnAsk } },
    setNotificationChannelAsync: async (id) => { calls.push(`channel:${id}`) },
    getExpoPushTokenAsync: async ({ projectId }) => {
      calls.push(`token:${projectId}`)
      if (fail) throw new Error('no network')
      return { data: token }
    },
  }
}
function memStore(initial = null) {
  let v = initial
  return { get: async () => v, set: async (t) => { v = t }, clear: async () => { v = null }, peek: () => v }
}

test('registers the Expo token with the server and remembers it', async () => {
  const N = fakeN(); const store = memStore(); const sent = []
  const r = await registerPush({ platform: 'android', isExpoGo: false, projectId: 'p1', getNotifications: () => N,
    sendToken: async (t, p) => sent.push([t, p]), store })
  assert.deepEqual(r, { status: 'registered', token: 'ExponentPushToken[abc]' })
  assert.deepEqual(sent, [['ExponentPushToken[abc]', 'android']])
  assert.equal(store.peek(), 'ExponentPushToken[abc]')
  assert.deepEqual(N.calls, ['get', 'channel:default', 'token:p1'])
})

test('asks for permission when not granted; denied means no token', async () => {
  const N = fakeN({ granted: false, grantOnAsk: false }); const sent = []
  const r = await registerPush({ platform: 'ios', isExpoGo: false, projectId: 'p', getNotifications: () => N,
    sendToken: async (t) => sent.push(t), store: memStore() })
  assert.equal(r.status, 'denied')
  assert.deepEqual(N.calls, ['get', 'ask'])
  assert.deepEqual(sent, [])
})

test('iOS gets no Android channel', async () => {
  const N = fakeN()
  await registerPush({ platform: 'ios', isExpoGo: false, projectId: 'p', getNotifications: () => N,
    sendToken: async () => {}, store: memStore() })
  assert.deepEqual(N.calls, ['get', 'token:p'])
})

test('browser, Expo Go on Android and a build without a project id skip push without loading it', async () => {
  const load = () => { throw new Error('must not load expo-notifications') }
  const args = { getNotifications: load, sendToken: async () => { throw new Error('no') }, store: memStore() }
  assert.equal((await registerPush({ ...args, platform: 'web', isExpoGo: false, projectId: 'p' })).status, 'unsupported')
  assert.equal((await registerPush({ ...args, platform: 'android', isExpoGo: true, projectId: 'p' })).status, 'expo-go')
  assert.equal((await registerPush({ ...args, platform: 'android', isExpoGo: false, projectId: null })).status, 'no-project')
})

test('a failure is reported, never thrown, and nothing is remembered', async () => {
  const store = memStore(); const logs = []
  const r = await registerPush({ platform: 'android', isExpoGo: false, projectId: 'p', getNotifications: () => fakeN({ fail: true }),
    sendToken: async () => {}, store, log: (m) => logs.push(m) })
  assert.equal(r.status, 'error')
  assert.equal(store.peek(), null)
  assert.deepEqual(logs, ['push registration failed: Error'])
  const r2 = await registerPush({ platform: 'android', isExpoGo: false, projectId: 'p', getNotifications: () => fakeN(),
    sendToken: async () => { throw Object.assign(new Error('422'), { status: 422 }) }, store })
  assert.equal(r2.status, 'error')
  assert.equal(store.peek(), null)
})

test('sign-out deletes the remembered token from the server and forgets it', async () => {
  const store = memStore('ExponentPushToken[abc]'); const deleted = []
  const r = await unregisterPush({ store, deleteToken: async (t) => deleted.push(t) })
  assert.deepEqual(r, { status: 'removed' })
  assert.deepEqual(deleted, ['ExponentPushToken[abc]'])
  assert.equal(store.peek(), null)
})

test('sign-out without a token does nothing; a failed delete keeps the token for the next sign-in', async () => {
  assert.deepEqual(await unregisterPush({ store: memStore(), deleteToken: async () => { throw new Error('x') } }), { status: 'none' })
  const store = memStore('T')
  assert.deepEqual(await unregisterPush({ store, deleteToken: async () => { throw new Error('offline') } }), { status: 'error' })
  assert.equal(store.peek(), 'T')
  const store500 = memStore('T')
  assert.deepEqual(await unregisterPush({ store: store500, deleteToken: async () => { throw Object.assign(new Error('x'), { status: 500 }) } }), { status: 'error' })
  assert.equal(store500.peek(), 'T')
  const store404 = memStore('T')
  assert.deepEqual(await unregisterPush({ store: store404, deleteToken: async () => { throw Object.assign(new Error('nf'), { status: 404 }) } }), { status: 'removed' })
})
