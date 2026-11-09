// Face self-enrolment helpers (FR-109, FR-110, FR-115). Plain JS so node --test can check them.

// What each status means to the student (FR-115)
export const STATUS_INFO = {
  not_enrolled: {
    label: 'Not enrolled',
    variant: 'gray',
    text: 'Enrol your face so the classroom camera can take your attendance.',
  },
  pending_review: {
    label: 'Pending review',
    variant: 'orange',
    text: "Your photos couldn't be checked automatically. A lecturer of one of your courses will review them.",
  },
  active: {
    label: 'Active',
    variant: 'green',
    text: 'Your face is enrolled. The classroom camera can take your attendance.',
  },
  rejected: {
    label: 'Rejected',
    variant: 'red',
    text: 'Your enrolment was not approved. Read the reason below and try again.',
  },
}

export function statusInfo(status) {
  return STATUS_INFO[status] ?? STATUS_INFO.not_enrolled
}

// A new enrolment can start only when nothing is enrolled or waiting for review
export function canStartEnrolment(status) {
  return status === 'not_enrolled' || status === 'rejected'
}

// The notice must be accepted again when there is no consent or the notice has changed
export function consentNeeded(consent) {
  if (!consent || !consent.active) return true
  return consent.version !== consent.current_version
}

// Guided selfies at several angles (UC-105 step 3)
export const SELFIE_STEPS = [
  { key: 'front', title: 'Look straight at the camera', hint: 'Keep your whole face inside the oval.' },
  { key: 'left',  title: 'Turn your head slightly left', hint: 'Just a little. Keep both eyes visible.' },
  { key: 'right', title: 'Turn your head slightly right', hint: 'Just a little. Keep both eyes visible.' },
]

export const CARD_STEP = {
  key: 'card',
  title: 'Photo of your matric card',
  hint: 'Fit the card inside the frame, front side up. Avoid glare from lights.',
}

export const TOTAL_STEPS = SELFIE_STEPS.length + 1

// Reasons the card quality check can give (T15); a 422 with only these means "retake the card"
const CARD_REASONS = new Set([
  'too_dark', 'no_card_found', 'card_too_small', 'angled', 'blurry', 'glare', 'no_face_on_card',
])

// Turns a failed submission into what the app should ask the student to retake, or null when
// the error isn't a retake (then the app shows the error message as it is).
export function retakeFromError(err) {
  const d = err?.detail
  if (err?.status !== 422 || !d || typeof d !== 'object' || !Array.isArray(d.reasons)) return null
  let retake = 'all'
  if (d.reasons.includes('no_face_in_selfies')) retake = 'selfies'
  else if (d.reasons.length > 0 && d.reasons.every(r => CARD_REASONS.has(r))) retake = 'card'
  return {
    retake,
    reasons: d.reasons,
    message: d.message || 'Please retake the photos.',
    blockedAttempts: d.blocked_attempts ?? 0,
    canSubmitAnyway: retake === 'card' && !!d.can_submit_anyway,
  }
}

// The multipart fields of POST /student/me/face-enrolment, as [name, value] pairs.
// Photos are { uri } from the camera; React Native's FormData uploads { uri, name, type }.
export function enrolmentParts(selfies, card, submitAnyway = false) {
  const file = (photo, name) => ({ uri: photo.uri, name, type: 'image/jpeg' })
  const parts = selfies.map((p, i) => ['selfies', file(p, `selfie-${i + 1}.jpg`)])
  parts.push(['card', file(card, 'card.jpg')])
  if (submitAnyway) parts.push(['submit_anyway', 'true'])
  return parts
}
