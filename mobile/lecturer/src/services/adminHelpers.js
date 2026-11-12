// Pure helpers for the browser admin area (T22). No React Native imports, so `npm test` runs them.

// Audit actions written by the backend (`write_log(..., "<ACTION>", ...)`). Tone picks the chip colour.
const AUDIT_ACTIONS = {
  USER_CREATE:            { label: 'Created account',          tone: 'good' },
  USER_UPDATE:            { label: 'Updated profile',          tone: 'info' },
  USER_DEACTIVATE:        { label: 'Deactivated account',      tone: 'bad' },
  USER_REACTIVATE:        { label: 'Reactivated account',      tone: 'good' },
  PASSWORD_RESET:         { label: 'Reset password',           tone: 'neutral' },
  MOODLE_ACCOUNT_CREATE:  { label: 'Account from SPeCTRUM',    tone: 'good' },
  MOODLE_ROLE_CHANGE:     { label: 'Role changed by SPeCTRUM', tone: 'info' },
  MOODLE_SYNC:            { label: 'Synced from SPeCTRUM',     tone: 'neutral' },
  ENROLL_ADD:             { label: 'Added to class',           tone: 'good' },
  ENROLL_REMOVE:          { label: 'Removed from class',       tone: 'bad' },
  OCCURRENCE_ASSIGN_LECTURER:   { label: 'Lecturer assigned',   tone: 'good' },
  OCCURRENCE_UNASSIGN_LECTURER: { label: 'Lecturer unassigned', tone: 'bad' },
  FACE_CONSENT_GIVE:      { label: 'Gave face data consent',   tone: 'good' },
  FACE_CONSENT_WITHDRAW:  { label: 'Withdrew face consent',    tone: 'bad' },
  FACE_ENROL_AUTO_APPROVE:{ label: 'Face enrolled (automatic)',tone: 'good' },
  FACE_ENROL_SUBMIT:      { label: 'Face sent for review',     tone: 'info' },
  FACE_ENROL_APPROVE:     { label: 'Approved face enrolment',  tone: 'good' },
  FACE_ENROL_REJECT:      { label: 'Rejected face enrolment',  tone: 'bad' },
  FACE_ENROLL:            { label: 'Registered face data',     tone: 'good' },
  FACE_REMOVE:            { label: 'Reset face data',          tone: 'bad' },
  FACE_REVIEW_DISMISS:    { label: 'Dismissed face alert',     tone: 'neutral' },
  FACE_PROMOTE:           { label: 'Resolved face alert',      tone: 'info' },
  ATTENDANCE_OVERRIDE:    { label: 'Overrode attendance',      tone: 'warn' },
  CLASS_SCHEDULE_SET:     { label: 'Set class schedule',       tone: 'info' },
  SESSION_START_NOW:      { label: 'Started class now',        tone: 'info' },
  SESSION_TIME_CHANGED:   { label: 'Changed class time',       tone: 'info' },
  SESSION_EXTENDED:       { label: 'Extended class',           tone: 'info' },
  SESSION_ENDED:          { label: 'Ended class',              tone: 'info' },
  SESSION_CANCELLED:      { label: 'Cancelled class',          tone: 'warn' },
  SESSION_CONFIRMED_HELD: { label: 'Confirmed class was held', tone: 'good' },
  SESSION_CONFIRMED_NOT_HELD: { label: 'Confirmed class was not held', tone: 'warn' },
}

const tidy = (code) => {
  const s = String(code ?? '').toLowerCase().replace(/_/g, ' ').trim()
  return s ? s[0].toUpperCase() + s.slice(1) : ''
}

export function auditAction(action) {
  return AUDIT_ACTIONS[action] ?? { label: tidy(action), tone: 'neutral' }
}

function parse(val) {
  if (val == null || val === '') return null
  try { return JSON.parse(val) } catch { return val }
}

function describe(val) {
  if (val == null) return ''
  if (typeof val !== 'object') return String(val)
  return Object.entries(val)
    .filter(([, v]) => v !== null && v !== '' && !(Array.isArray(v) && v.length === 0) && v !== 0)
    .map(([k, v]) => `${tidy(k)}: ${Array.isArray(v) ? v.join(', ') : typeof v === 'object' ? JSON.stringify(v) : v}`)
    .join(' · ')
}

// One line of detail for an audit entry: "old → new" when both exist, else whichever is there
export function auditDetail(entry) {
  const before = describe(parse(entry.old_val))
  const after = describe(parse(entry.new_val))
  if (before && after) return `${before} → ${after}`
  return after || before
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// Checks the administrator sign-in form before it is sent, so a non-email gets a plain
// message instead of the server's raw 422. Returns a message or null.
export function adminSignInError({ email = '', password = '' }) {
  if (!email.trim() || !password) return 'Enter your email and password.'
  if (!EMAIL.test(email.trim())) return 'Enter your email address.'
  return null
}

// Checks the "Create administrator" form before it is sent (FR-108). Returns a message or null.
export function newAdminError({ name = '', email = '', password = '', confirm = '' }) {
  if (!name.trim() || !email.trim() || !password || !confirm) return 'Fill in every field.'
  if (!EMAIL.test(email.trim())) return 'Enter a valid email address.'
  if (password.length < 8) return 'The password must be at least 8 characters.'
  if (password !== confirm) return "The passwords don't match."
  return null
}

const ROLE_LABELS = { admin: 'Administrator', lecturer: 'Lecturer', student: 'Student' }

// "Student · 23004901 · SPeCTRUM" under an account's name
export function accountSubtitle(u) {
  const number = u.role === 'student' ? u.student?.matric_no : u.role === 'lecturer' ? u.lecturer?.staff_id : null
  return [ROLE_LABELS[u.role] ?? tidy(u.role), number, u.moodle_linked ? 'SPeCTRUM' : 'Local account']
    .filter(Boolean).join(' · ')
}

// Face enrolment on an account row (FR-115, FR-117). Falls back to face_enrolled for an older server.
const FACE_STATUS = {
  active:         { label: 'Face enrolled',  tone: 'good' },
  pending_review: { label: 'Pending review', tone: 'warn' },
  rejected:       { label: 'Face rejected',  tone: 'bad' },
  not_enrolled:   { label: 'No face data',   tone: 'neutral' },
}
export function faceStatus(u) {
  if (u.role !== 'student') return null
  const key = u.face_status ?? (u.face_enrolled ? 'active' : 'not_enrolled')
  return { key, ...(FACE_STATUS[key] ?? FACE_STATUS.not_enrolled) }
}

const SYNC_ROWS = [
  ['accounts_created', 'Accounts created'],
  ['courses_created', 'Courses created'],
  ['courses_updated', 'Courses updated'],
  ['enrolments_added', 'Enrolments added'],
  ['enrolments_removed', 'Enrolments removed'],
  ['lecturers_assigned', 'Lecturers assigned'],
  ['lecturers_unassigned', 'Lecturers unassigned'],
  ['profiles_updated', 'Profiles updated'],
  ['unlinked_users', 'Not linked to SPeCTRUM'],
]

// The counts of a sync report (POST or GET /admin/moodle/sync) as label/value rows
export function syncRows(report) {
  if (!report) return []
  return SYNC_ROWS.filter(([key]) => key in report).map(([key, label]) => ({ key, label, value: report[key] }))
}
