import { test } from 'node:test'
import assert from 'node:assert/strict'
import { auditAction, auditDetail, newAdminError, adminSignInError, accountSubtitle, syncRows, faceStatus } from './adminHelpers.js'

test('administrator sign-in asks for an email address instead of sending a non-email', () => {
  assert.equal(adminSignInError({ email: '', password: 'x' }), 'Enter your email and password.')
  assert.equal(adminSignInError({ email: 'a@b.co', password: '' }), 'Enter your email and password.')
  assert.equal(adminSignInError({ email: 'admin', password: 'x' }), 'Enter your email address.')
  assert.equal(adminSignInError({ email: 'devlecturer', password: 'x' }), 'Enter your email address.')
  assert.equal(adminSignInError({ email: ' admin@smartclass.local ', password: 'x' }), null)
})

test('every face enrolment and consent action has a label', () => {
  for (const a of ['FACE_CONSENT_GIVE', 'FACE_CONSENT_WITHDRAW', 'FACE_ENROL_AUTO_APPROVE',
    'FACE_ENROL_SUBMIT', 'FACE_ENROL_APPROVE', 'FACE_ENROL_REJECT']) {
    assert.notEqual(auditAction(a).label, a)
  }
  assert.deepEqual(auditAction('USER_DEACTIVATE'), { label: 'Deactivated account', tone: 'bad' })
})

test('unknown audit actions get a tidied label', () => {
  assert.deepEqual(auditAction('SOME_NEW_THING'), { label: 'Some new thing', tone: 'neutral' })
})

test('audit detail shows old → new and skips empty values', () => {
  assert.equal(auditDetail({ old_val: '{"status": "active"}', new_val: '{"status": "inactive"}' }),
    'Status: active → Status: inactive')
  assert.equal(auditDetail({ old_val: null, new_val: '{"email": "a@um.edu.my", "role": "admin"}' }),
    'Email: a@um.edu.my · Role: admin')
  assert.equal(auditDetail({ new_val: '{"courses_created": 0, "skipped": [], "enrolments_added": 3}' }),
    'Enrolments added: 3')
  assert.equal(auditDetail({ old_val: null, new_val: null }), '')
  assert.equal(auditDetail({ new_val: 'not json' }), 'not json')
})

test('create administrator form checks', () => {
  const ok = { name: 'New Admin', email: 'new@um.edu.my', password: 'Secret@123', confirm: 'Secret@123' }
  assert.equal(newAdminError(ok), null)
  assert.equal(newAdminError({ ...ok, name: '  ' }), 'Fill in every field.')
  assert.equal(newAdminError({ ...ok, email: 'not-an-email' }), 'Enter a valid email address.')
  assert.equal(newAdminError({ ...ok, password: 'short', confirm: 'short' }), 'The password must be at least 8 characters.')
  assert.equal(newAdminError({ ...ok, confirm: 'Secret@124' }), "The passwords don't match.")
})

test('account subtitle shows role, number and where it signs in', () => {
  assert.equal(accountSubtitle({ role: 'student', student: { matric_no: '23004901' }, moodle_linked: true }),
    'Student · 23004901 · SPeCTRUM')
  assert.equal(accountSubtitle({ role: 'lecturer', lecturer: { staff_id: 'S1' }, moodle_linked: false }),
    'Lecturer · S1 · Local account')
  assert.equal(accountSubtitle({ role: 'admin', moodle_linked: false }), 'Administrator · Local account')
})

test('face status on an account row', () => {
  assert.deepEqual(faceStatus({ role: 'student', face_status: 'pending_review' }),
    { key: 'pending_review', label: 'Pending review', tone: 'warn' })
  assert.equal(faceStatus({ role: 'student', face_status: 'active' }).label, 'Face enrolled')
  assert.equal(faceStatus({ role: 'student', face_status: 'rejected' }).label, 'Face rejected')
  assert.equal(faceStatus({ role: 'student', face_status: 'not_enrolled' }).label, 'No face data')
  assert.equal(faceStatus({ role: 'student', face_enrolled: true }).label, 'Face enrolled')
  assert.equal(faceStatus({ role: 'student' }).label, 'No face data')
  assert.equal(faceStatus({ role: 'student', face_status: 'weird' }).label, 'No face data')
  assert.equal(faceStatus({ role: 'lecturer' }), null)
})

test('sync rows keep the order and only known keys', () => {
  const rows = syncRows({ ok: true, enrolments_added: 2, accounts_created: 1, skipped: ['x'] })
  assert.deepEqual(rows.map(r => [r.label, r.value]), [['Accounts created', 1], ['Enrolments added', 2]])
  assert.deepEqual(syncRows(null), [])
})
