import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  statusLabel, statusBadge, overrideReasonError, cleanReason, rosterStatus, groupRoster, countStatuses,
  hhmm, timeRange, dayMonth, minutesBetween, timeRangeError, weeklyScheduleError,
  sessionStateLabel, syncInfo, moodleValueLabel, canTakeMoodle, OVERRIDE_REASON_MAX, STATUSES,
  sessionCounts, followsLive,
} from './attendance.js'

test('all four statuses have a label and a colour; no record shows "Not yet"', () => {
  assert.deepEqual(STATUSES.map(statusLabel), ['Present', 'Late', 'Excused', 'Absent'])
  assert.deepEqual(STATUSES.map(statusBadge), ['green', 'orange', 'blue', 'red'])
  assert.equal(statusLabel('not_recorded'), 'Not yet')
})

test('the override reason is optional, trimmed and at most 500 characters', () => {
  assert.equal(overrideReasonError(''), null)
  assert.equal(overrideReasonError(undefined), null)
  assert.equal(overrideReasonError(`  ${'x'.repeat(OVERRIDE_REASON_MAX)}  `), null)
  assert.match(overrideReasonError('x'.repeat(OVERRIDE_REASON_MAX + 1)), /under 500/)
  assert.equal(cleanReason('   '), null)
  assert.equal(cleanReason(' Medical certificate '), 'Medical certificate')
})

test('no record yet is "not yet" while open and absent once closed', () => {
  assert.equal(rosterStatus('not_recorded', true), 'not_recorded')
  assert.equal(rosterStatus('not_recorded', false), 'absent')
  assert.equal(rosterStatus('late', true), 'late')
})

test('late students are listed in their own section first', () => {
  const roster = [
    { id: 'a', status: 'present' }, { id: 'b', status: 'late' }, { id: 'c', status: 'not_recorded' },
    { id: 'd', status: 'late' },
  ]
  const sections = groupRoster(roster)
  assert.deepEqual(sections.map(s => s.key), ['late', 'rest'])
  assert.deepEqual(sections[0].data.map(s => s.id), ['b', 'd'])
  assert.equal(sections[0].title, 'Late (2)')
  assert.deepEqual(sections[1].data.map(s => s.id), ['a', 'c'])
  assert.equal(groupRoster([{ id: 'a', status: 'present' }])[0].title, null)
  assert.deepEqual(groupRoster([]), [])
  assert.deepEqual(countStatuses(roster), { present: 1, late: 2, excused: 0, absent: 0, not_recorded: 1 })
})

test('server times are Malaysia time and read without the phone zone', () => {
  assert.equal(hhmm('2026-11-16T08:05:00'), '08:05')
  assert.equal(hhmm('2026-11-16T23:59:59.123'), '23:59')
  assert.equal(hhmm(null), '')
  assert.deepEqual(dayMonth('2026-11-16T08:05:00'), { day: 16, month: 'Nov' })
  assert.equal(minutesBetween('2026-11-16T08:00:00', '2026-11-16T09:45:00'), 105)
  assert.equal(minutesBetween('2026-11-16T23:30:00', '2026-11-17T00:15:00'), 45)
  assert.equal(minutesBetween(null, '2026-11-16T09:45:00'), null)
  assert.equal(timeRange('2026-11-16T08:00:00', '2026-11-16T10:00:00'), '08:00–10:00')
  assert.equal(timeRange('2026-11-16T13:09:00', '2026-11-17T13:08:00'), '13:09–13:08 (next day)')
  assert.equal(timeRange(null, '2026-11-16T10:00:00'), '')
})

test('a start and end need two 24-hour times in order', () => {
  assert.equal(timeRangeError('08:00', '10:00'), null)
  assert.match(timeRangeError('8:00', '10:00'), /24-hour/)
  assert.match(timeRangeError('10:00', '10:00'), /after the start/)
  assert.match(timeRangeError('11:00', '10:00'), /after the start/)
})

test('the weekly schedule is all three fields or none', () => {
  assert.equal(weeklyScheduleError({ day: 'Mon', start: '08:00', end: '10:00' }), null)
  assert.equal(weeklyScheduleError({ day: null, start: '', end: '' }), null)
  assert.match(weeklyScheduleError({ day: 'Mon', start: '08:00', end: '' }), /Pick a day, a start and an end/)
  assert.match(weeklyScheduleError({ day: 'Mon', start: '10:00', end: '08:00' }), /after the start/)
})

test('session states read as words', () => {
  assert.equal(sessionStateLabel('needs_confirmation'), 'Confirm if held')
  assert.equal(sessionStateLabel('open'), 'Open now')
})

test('sync status: none before closing, retry offered unless synced', () => {
  assert.equal(syncInfo({ moodle_sync_status: null }), null)
  const synced = syncInfo({ moodle_sync_status: 'synced', moodle_synced_at: '2026-11-16T10:01:00' })
  assert.equal(synced.label, 'Synced to SPeCTRUM')
  assert.equal(synced.canRetry, false)
  assert.equal(synced.detail, 'Last sent 10:01')
  const failed = syncInfo({
    moodle_sync_status: 'failed', moodle_sync_error: 'Moodle unreachable', moodle_sync_next_at: '2026-11-16T10:05:00',
  })
  assert.equal(failed.canRetry, true)
  assert.equal(failed.detail, 'Moodle unreachable · Tries again at 10:05')
  assert.equal(syncInfo({ moodle_sync_status: 'pending' }).canRetry, true)
  assert.equal(syncInfo({ moodle_sync_status: 'conflict' }).badge, 'orange')
})

test("a conflict shows Moodle's value; only one of the four statuses can be taken", () => {
  assert.equal(moodleValueLabel('none'), 'No mark')
  assert.equal(moodleValueLabel('other'), 'Another status')
  assert.equal(moodleValueLabel('excused'), 'Excused')
  assert.equal(canTakeMoodle({ moodle_status: 'late' }), true)
  assert.equal(canTakeMoodle({ moodle_status: 'none' }), false)
  assert.equal(canTakeMoodle({ moodle_status: 'other' }), false)
})

test('Home shows the same five counts as the live roster (T38b)', () => {
  // 6 enrolled: 2 present, 1 late, 0 excused, 1 overridden absent, 2 not recorded yet.
  // The API's `absent` counts everyone not attended (3); `not_recorded` (2) splits it.
  const session = { present: 2, late: 1, excused: 0, absent: 3, not_recorded: 2, unid: 4 }
  const roster = ['present', 'present', 'late', 'absent', 'not_recorded', 'not_recorded'].map(status => ({ status }))
  assert.deepEqual(sessionCounts(session), countStatuses(roster))
  assert.deepEqual(sessionCounts({ present: 1, absent: 2 }), { present: 1, late: 0, excused: 0, absent: 2, not_recorded: 0 })
  assert.deepEqual(sessionCounts(null), { present: 0, late: 0, excused: 0, absent: 0, not_recorded: 0 })
})

test('live updates follow a session until SPeCTRUM has it (T38b)', () => {
  assert.equal(followsLive({ open: true, moodle_sync_status: null }), true)
  assert.equal(followsLive({ open: false, moodle_sync_status: 'pending' }), true)
  assert.equal(followsLive({ open: false, moodle_sync_status: 'failed' }), true)
  assert.equal(followsLive({ open: false, moodle_sync_status: 'synced' }), false)
  assert.equal(followsLive({ open: false, moodle_sync_status: 'conflict' }), false)
  assert.equal(followsLive({ open: false, moodle_sync_status: null }), false)
  assert.equal(followsLive(null), false)
})
