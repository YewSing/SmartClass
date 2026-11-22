import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  initialDashboard, dashboardReducer, attendanceBadge, sessionBadge, classTypeLabel, classMeta,
  rateLabel, rateVariant, overviewCounts, dueLabel, refreshedLabel, moodleLink,
} from './dashboard.js'

const data = (extra = {}) => ({
  date: '2026-11-22', today_classes: [], unread_count: 3,
  priority_notifications: [{ id: 1, priority: 'urgent' }, { id: 2, priority: 'important' }],
  ...extra,
})

// ─── load state ──────────────────────────────────────────────────────────────

test('first load: loading, then ready with the data', () => {
  let s = dashboardReducer(initialDashboard, { type: 'loading' })
  assert.equal(s.status, 'loading')
  s = dashboardReducer(s, { type: 'loaded', data: data() })
  assert.equal(s.status, 'ready')
  assert.equal(s.data.unread_count, 3)
  assert.equal(s.error, null)
})

test('a first load that fails is the error state', () => {
  const s = dashboardReducer(initialDashboard, { type: 'failed', error: 'Network down' })
  assert.deepEqual(s, { status: 'error', data: null, error: 'Network down' })
})

test('a re-load keeps the data on screen while loading and after it fails', () => {
  const ready = dashboardReducer(initialDashboard, { type: 'loaded', data: data() })
  assert.equal(dashboardReducer(ready, { type: 'loading' }), ready)
  const failed = dashboardReducer(ready, { type: 'failed', error: 'x' })
  assert.equal(failed.status, 'ready')
  assert.equal(failed.data, ready.data)
  assert.equal(failed.error, 'x')
  const again = dashboardReducer(failed, { type: 'loaded', data: data({ unread_count: 0 }) })
  assert.equal(again.error, null)
})

test('a read priority notification leaves the top, the others stay in order', () => {
  const ready = dashboardReducer(initialDashboard, { type: 'loaded', data: data() })
  const s = dashboardReducer(ready, { type: 'read', id: 1, unread: 2 })
  assert.deepEqual(s.data.priority_notifications.map(n => n.id), [2])
  assert.equal(s.data.unread_count, 2)
  assert.equal(dashboardReducer(initialDashboard, { type: 'read', id: 1 }), initialDashboard)
  assert.equal(dashboardReducer(s, { type: 'read', id: 99 }).data.unread_count, 2)
})

test('reset goes back to loading', () => {
  const ready = dashboardReducer(initialDashboard, { type: 'loaded', data: data() })
  assert.deepEqual(dashboardReducer(ready, { type: 'reset' }), initialDashboard)
})

// ─── classes ─────────────────────────────────────────────────────────────────

test('attendance badge for every status', () => {
  assert.deepEqual(attendanceBadge({ attendance_status: 'present' }), { variant: 'green', label: 'Present' })
  assert.equal(attendanceBadge({ attendance_status: 'late' }).label, 'Late')
  assert.equal(attendanceBadge({ attendance_status: 'excused' }).label, 'Excused')
  assert.equal(attendanceBadge({ attendance_status: 'absent' }).variant, 'red')
  assert.equal(attendanceBadge({ attendance_status: 'not_recorded', session_status: 'open' }).label, 'Not recorded yet')
  assert.equal(attendanceBadge({ attendance_status: null, session_status: 'needs_confirmation' }).label, 'Being checked')
  assert.equal(attendanceBadge({ attendance_status: null, session_status: null }).label, 'Not started')
  assert.equal(attendanceBadge({ attendance_status: 'weird', session_status: 'closed' }).label, 'Ended')
})

test('session badge for the lecturer', () => {
  assert.deepEqual(sessionBadge({ session_status: 'open' }), { variant: 'green', label: 'Live' })
  assert.equal(sessionBadge({ session_status: 'closed' }).label, 'Ended')
  assert.equal(sessionBadge({ session_status: 'needs_confirmation' }).label, 'Needs confirmation')
  assert.equal(sessionBadge({ session_status: null }).label, 'Not started')
})

test('class type and meta', () => {
  assert.equal(classTypeLabel({ class_type: 'LECTURE', class_label: null }), 'Lecture')
  assert.equal(classTypeLabel({ class_type: 'TUTORIAL', class_label: 'T2' }), 'T2')
  assert.equal(classTypeLabel({ class_type: 'TUTORIAL', class_label: null }), 'Tutorial')
  assert.equal(classMeta({ start_time: '09:00', end_time: '11:00', room: 'DK1' }), '09:00–11:00 · DK1')
  assert.equal(classMeta({ start_time: null, end_time: null, room: 'DK1' }), 'DK1')
  assert.equal(classMeta({ start_time: '09:00', end_time: null, room: null }), '09:00')
  assert.equal(classMeta(null), '')
})

test('rate label and colour (80% line, null = nothing counted)', () => {
  assert.equal(rateLabel(null), '—')
  assert.equal(rateLabel(100), '100%')
  assert.equal(rateLabel(87.5), '87.5%')
  assert.equal(rateVariant(80), 'green')
  assert.equal(rateVariant(79.9), 'orange')
  assert.equal(rateVariant(null), 'gray')
})

test('overview counts default to 0', () => {
  assert.deepEqual(overviewCounts({ present: 3, late: 1, excused: 0, absent: 2, not_recorded: 4 }),
    { present: 3, late: 1, excused: 0, absent: 2, not_recorded: 4 })
  assert.deepEqual(overviewCounts(null), { present: 0, late: 0, excused: 0, absent: 0, not_recorded: 0 })
})

// ─── Moodle ──────────────────────────────────────────────────────────────────

test('due label uses MYT days', () => {
  const now = new Date('2026-11-22T02:00:00Z')               // 10:00 MYT, 22 Nov
  assert.equal(dueLabel('2026-11-22T23:59:00+08:00', now), 'Due today, 23:59')
  assert.equal(dueLabel('2026-11-23T09:00:00+08:00', now), 'Due tomorrow, 09:00')
  assert.equal(dueLabel('2026-11-25T09:05:00+08:00', now), 'Due 25 Nov, 09:05')
  // 23:30 MYT on 22 Nov is still "today" even though it's 15:30 UTC
  assert.equal(dueLabel('2026-11-22T15:30:00Z', now), 'Due today, 23:30')
  assert.equal(dueLabel(null, now), '')
  assert.equal(dueLabel('not a date', now), '')
})

test('refreshed label', () => {
  const now = new Date('2026-11-22T02:00:00Z')
  assert.equal(refreshedLabel('2026-11-22T01:55:00Z', now), 'Updated 5 min ago')
  assert.equal(refreshedLabel('2026-11-22T02:00:00Z', now), 'Updated just now')
  assert.match(refreshedLabel(null, now), /^Not synced yet/)
})

test('only http(s) Moodle links open', () => {
  assert.equal(moodleLink({ link: 'http://localhost:8080/mod/forum/discuss.php?d=3' }),
    'http://localhost:8080/mod/forum/discuss.php?d=3')
  assert.equal(moodleLink({ link: 'https://spectrum.um.edu.my/calendar/view.php?view=day' }),
    'https://spectrum.um.edu.my/calendar/view.php?view=day')
  assert.equal(moodleLink({ link: 'javascript:alert(1)' }), null)
  assert.equal(moodleLink({ link: '/relative' }), null)
  assert.equal(moodleLink({ link: null }), null)
  assert.equal(moodleLink(null), null)
})
