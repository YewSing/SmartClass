import test from 'node:test'
import assert from 'node:assert/strict'
import { attendanceLabel, formatMoodleDate, isDashboardStale, notificationRoute, safeMoodleUrl } from './dashboard.js'

test('routes only known app-relative notification links', () => {
  assert.deepEqual(notificationRoute('/attendance/sessions/12'), { tab: 'Attendance' })
  assert.equal(notificationRoute('https://evil.example'), null)
  assert.equal(notificationRoute('//evil.example'), null)
  assert.equal(notificationRoute('/unknown'), null)
})

test('formats attendance state for people', () => assert.equal(attendanceLabel('not_recorded'), 'Not recorded'))

test('Moodle epoch dates and links are handled safely', () => {
  assert.notEqual(formatMoodleDate(1735689600), 'Date unavailable')
  assert.equal(formatMoodleDate(null), 'Date unavailable')
  assert.equal(safeMoodleUrl('javascript:alert(1)'), null)
  assert.equal(safeMoodleUrl('http://moodle.example/item'), null)
  assert.equal(safeMoodleUrl('https://moodle.example/item'), 'https://moodle.example/item')
})

test('dashboard cache is stale after 24 hours', () => {
  const now = Date.parse('2026-11-21T00:00:00Z')
  assert.equal(isDashboardStale('2026-11-20T12:00:00Z', now), false)
  assert.equal(isDashboardStale('2026-11-19T12:00:00Z', now), true)
})
