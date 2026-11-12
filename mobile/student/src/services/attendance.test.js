import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  STATUSES, statusInfo, parseLocal, hhmm, dayMonth, dateLabel, rateText, rateNote,
  classLabel, toSessionView, toCourseView, findSession,
  canFlag, flagView, recordedBannerText,
} from './attendance.js'

const COURSE = {
  course_id: 7,
  course_code: 'WIA1002',
  course_name: 'Data Structures',
  present: 0,
  late: 1,
  excused: 0,
  absent: 0,
  closed_sessions: 1,
  counted_sessions: 1,
  rate: 100,
  sessions: [
    {
      session_id: 11, occurrence_id: 5, class_type: 'LECTURE', class_label: null,
      date: '2026-10-19', starts_at: '2026-10-19T08:00:00', session_status: 'closed',
      status: 'late', detected_at: '2026-10-19T08:25:00', overridden: false,
    },
    {
      session_id: 12, occurrence_id: 6, class_type: 'TUTORIAL', class_label: 'Tutorial Group 1',
      date: '2026-10-20', starts_at: '2026-10-20T10:00:00', session_status: 'open',
      status: 'not_recorded', detected_at: null, overridden: true,
    },
  ],
}

const OCC = { 5: { venue: 'DK1', lecturer: 'Dr Lee' } }

test('every status has a label and badge, and unknown ones keep the raw value', () => {
  assert.deepEqual(STATUSES, ['present', 'late', 'excused', 'absent'])
  assert.deepEqual(statusInfo('present'), { label: 'Present', badge: 'green' })
  assert.deepEqual(statusInfo('late'), { label: 'Late', badge: 'yellow' })
  assert.deepEqual(statusInfo('excused'), { label: 'Excused', badge: 'blue' })
  assert.deepEqual(statusInfo('absent'), { label: 'Absent', badge: 'red' })
  assert.deepEqual(statusInfo('not_recorded'), { label: 'Not yet recorded', badge: 'gray' })
  assert.deepEqual(statusInfo('something_new'), { label: 'something_new', badge: 'gray' })
})

test('the rate is shown to one decimal, never recomputed here', () => {
  assert.equal(rateText(66.7), '66.7%')
  assert.equal(rateText(100), '100%')
  assert.equal(rateText(0), '0%')
  assert.equal(rateText(null), '—')
  assert.equal(rateText(undefined), '—')
})

test('the note spells out what counted towards the rate', () => {
  assert.equal(rateNote({ present: 1, late: 1, counted_sessions: 3, closed_sessions: 4 }),
    '2 of 3 classes attended')
  assert.equal(rateNote({ present: 0, late: 0, counted_sessions: 0, closed_sessions: 0 }),
    'No finished classes yet')
  assert.equal(rateNote({ present: 0, late: 0, counted_sessions: 0, closed_sessions: 2 }),
    'All finished classes were excused')
})

test('times are read from the digits, whatever the phone zone is', () => {
  assert.deepEqual(parseLocal('2026-10-05T08:25:00'), { y: 2026, mo: 10, d: 5, h: 8, mi: 25 })
  assert.equal(hhmm('2026-10-05T08:25:00'), '08:25')
  assert.equal(hhmm('2026-10-05T23:30:00'), '23:30')
  assert.equal(hhmm(null), '')
})

test('dates are read from the digits too', () => {
  assert.equal(dateLabel('2026-10-19'), 'Mon 19 Oct')
  assert.deepEqual(dayMonth('2026-10-05'), { day: '05', month: 'Oct' })
})

test('a class label wins over the type, otherwise the type is spelled out', () => {
  assert.equal(classLabel({ class_type: 'TUTORIAL', class_label: 'Tutorial Group 1' }), 'Tutorial Group 1')
  assert.equal(classLabel({ class_type: 'TUTORIAL', class_label: null }), 'Tutorial')
  assert.equal(classLabel({ class_type: 'LECTURE', class_label: null }), 'Lecture')
})

test('a session view keeps the API order and reads the venue from the class lookup', () => {
  const view = toCourseView(COURSE, OCC)
  assert.deepEqual(view.counts, { present: 0, late: 1, excused: 0, absent: 0 })
  assert.equal(view.rateText, '100%')
  assert.equal(view.note, '1 of 1 classes attended')
  assert.deepEqual(view.sessions.map(s => s.id), ['11', '12'])
  assert.equal(typeof view.sessions[0].id, 'string')

  const [late, open] = view.sessions
  assert.equal(late.status, 'late')
  assert.equal(late.label, 'Late')
  assert.equal(late.badge, 'yellow')
  assert.equal(late.day, '19')
  assert.equal(late.month, 'Oct')
  assert.equal(late.isLive, false)
  assert.equal(late.checkinTime, '08:25')
  assert.equal(late.venue, 'DK1')
  assert.equal(late.lecturer, 'Dr Lee')
  assert.equal(late.overridden, false)

  assert.equal(open.isLive, true)
  assert.equal(open.checkinTime, null)
  assert.equal(open.venue, '—')
  assert.equal(open.lecturer, '—')
  assert.equal(open.overridden, true)
  assert.equal(open.title, 'WIA1002 · Tutorial Group 1')
})

test('a session view falls back to the start time when there is no class date', () => {
  const view = toSessionView(
    { session_id: 3, class_type: 'LECTURE', date: null, starts_at: '2026-10-19T08:00:00',
      session_status: 'open', status: 'not_recorded', detected_at: null },
    COURSE,
  )
  assert.equal(view.day, '19')
  assert.equal(view.month, 'Oct')
  assert.equal(view.title, 'WIA1002 · Lecture')
  assert.equal(view.sub, 'Mon 19 Oct · 08:00')
})

test('findSession finds a session by course and session id as strings', () => {
  const courses = [toCourseView(COURSE, OCC)]
  const found = findSession(courses, 7, '11')
  assert.equal(found.course.code, 'WIA1002')
  assert.equal(found.session.id, '11')
  assert.equal(findSession(courses, 7, '999'), null)
  assert.equal(findSession(courses, 8, '11'), null)
  assert.equal(findSession([], 7, '11'), null)
})

// ─── Flags (FR-318, FR-319, FR-406) ──────────────────────────────────────────

const FLAG = {
  id: 1, session_id: 12, class_code: 'WIA1002', class_name: 'Data Structures',
  class_date: '2026-10-20', flagged_at: '2026-11-13T10:12:30', status: 'pending',
  record_status: null, reject_reason: null, resolved_at: null,
}

test('the flag button needs an open class, no record and no flag yet', () => {
  const open = { isLive: true, status: 'not_recorded' }
  assert.equal(canFlag(open, null), true)
  assert.equal(canFlag(open, undefined), true)
  assert.equal(canFlag({ isLive: false, status: 'not_recorded' }, null), false)
  assert.equal(canFlag({ isLive: true, status: 'present' }, null), false)
  assert.equal(canFlag({ isLive: true, status: 'absent' }, null), false)
  assert.equal(canFlag(open, FLAG), false)
  assert.equal(canFlag(null, null), false)
})

test('a pending flag says the lecturer will check, in yellow', () => {
  const view = flagView(FLAG)
  assert.equal(view.state, 'pending')
  assert.equal(view.title, 'Waiting for your lecturer')
  assert.equal(view.badge, 'yellow')
  assert.equal(view.icon, 'hourglass-outline')
  assert.equal(view.classText, 'WIA1002 — Data Structures')
  assert.equal(view.dateText, 'Tue 20 Oct')
  assert.equal(view.flaggedText, '10:12')
  assert.equal(view.resolvedText, null)
})

test('a confirmed flag shows the mark the lecturer recorded', () => {
  const late = flagView({ ...FLAG, status: 'confirmed', record_status: 'late', resolved_at: '2026-11-13T10:20:00' })
  assert.equal(late.state, 'confirmed')
  assert.equal(late.title, 'Confirmed')
  assert.equal(late.badge, 'green')
  assert.match(late.sub, /You're marked Late/)
  assert.equal(late.resolvedText, '10:20')

  const present = flagView({ ...FLAG, status: 'confirmed', record_status: null })
  assert.match(present.sub, /You're marked Present/)
})

test('a rejected flag shows the reason, or just that it was not accepted', () => {
  const withReason = flagView({ ...FLAG, status: 'rejected', reject_reason: 'You were not in the room' })
  assert.equal(withReason.state, 'rejected')
  assert.equal(withReason.title, 'Not accepted')
  assert.equal(withReason.badge, 'red')
  assert.match(withReason.sub, /You were not in the room/)

  const noReason = flagView({ ...FLAG, status: 'rejected', reject_reason: null })
  assert.equal(noReason.sub, 'Your lecturer did not accept it.')
})

test('an unknown flag status is treated as pending', () => {
  const view = flagView({ ...FLAG, status: 'something_new' })
  assert.equal(view.state, 'pending')
  assert.equal(view.title, 'Waiting for your lecturer')
})

test('the recorded banner is the event message plus the status', () => {
  assert.equal(recordedBannerText({ message: 'Attendance recorded for CS101', status: 'late' }),
    'Attendance recorded for CS101 · Late')
  assert.equal(recordedBannerText({ course_code: 'CS101', status: 'present' }),
    'Attendance recorded for CS101 · Present')
})
