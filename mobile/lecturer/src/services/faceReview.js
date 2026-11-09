// Face verification queue (FR-113): plain helpers for the review screen, kept free of
// React Native so `npm test` can run them under Node.

// Why a submission wasn't auto-approved, as the backend's check and quality codes (T16/T18b)
const REASONS = {
  face_mismatch:        'Selfie does not match the card photo',
  no_face_on_card:      'No face found on the card',
  no_face_in_selfies:   'No face found in the selfies',
  selfie_without_face:  'A selfie has no face in it',
  selfies_inconsistent: 'Selfies look like different people',
  matric_unreadable:    'Matric number on the card is unreadable',
  matric_mismatch:      'Matric number on the card is different',
  name_mismatch:        'Name on the card is different',
  not_um_card:          'Not a UM matric card',
  too_dark:             'Card photo too dark',
  no_card_found:        'No card found in the photo',
  card_too_small:       'Card too far from the camera',
  angled:               'Card photo taken at an angle',
  blurry:               'Card photo blurry',
  glare:                'Glare on the card',
  submitted_anyway:     'Student chose "submit anyway"',
}

export function reasonLabel(code) {
  return REASONS[code] ?? code.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase())
}

// Similarity scores (0–1) as a whole percentage; missing ones as a dash
export function percent(score) {
  return typeof score === 'number' ? `${Math.round(score * 100)}%` : '—'
}

// Card matric vs the account's, so the reviewer sees at a glance whether they agree
export function matricCheck(sub) {
  if (!sub.ocr_matric) return { text: 'Not readable', ok: false }
  return { text: sub.ocr_matric, ok: sub.ocr_matric === sub.matric_no }
}

// Selfies in order, then the card photo (the API already sorts them this way)
export function splitImages(images = []) {
  const selfies = images.filter(i => i.kind === 'selfie').sort((a, b) => a.position - b.position)
  const card = images.find(i => i.kind === 'card') ?? null
  return { selfies, card }
}

export const REJECT_REASON_MAX = 500

// The student sees this reason (FR-114), so one is required. Returns an error message or null.
export function rejectReasonError(text) {
  const t = (text ?? '').trim()
  if (!t) return 'Give a reason. The student sees it and can try again.'
  if (t.length > REJECT_REASON_MAX) return `Keep the reason under ${REJECT_REASON_MAX} characters.`
  return null
}

// Pending count on the dashboard banner
export function pendingLabel(n) {
  return n === 1 ? '1 face enrolment waiting for review' : `${n} face enrolments waiting for review`
}
